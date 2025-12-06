"""Мультимодальный анализатор видео через Gemini API.

Классы:
    GeminiVideoAnalyzer
        Анализирует видео: кадры + аудио в одном запросе.
"""

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel

from semantic_core.domain.media import (
    MediaAnalysisResult,
    MediaRequest,
    MediaResource,
    VideoAnalysisConfig,
)
from semantic_core.infrastructure.gemini.resilience import retry_with_backoff
from semantic_core.infrastructure.media.utils.audio import (
    extract_audio_from_video,
    optimize_audio_to_bytes,
)
from semantic_core.infrastructure.media.utils.video import (
    extract_frames,
    frames_to_bytes,
    get_video_duration,
)
from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from semantic_core.infrastructure.gemini.audio_analyzer import GeminiAudioAnalyzer


# Схема структурированного ответа для Gemini
class VideoAnalysisSchema(BaseModel):
    """Pydantic схема для structured output видео."""

    description: str
    keywords: list[str]
    ocr_text: Optional[str] = None
    transcription: Optional[str] = None
    participants: list[str] = []
    action_items: list[str] = []


# Системный промпт для анализа видео
SYSTEM_PROMPT_TEMPLATE = """You are a video analyst for semantic search indexing.
Response language: {language}

Return a JSON with:

{{
  "description": "What happens in the video (3-5 sentences)",
  "keywords": ["keyword1", ...],
  "transcription": "MARKDOWN_FORMATTED_SPEECH_TRANSCRIPT",
  "ocr_text": "MARKDOWN_FORMATTED_VISUAL_TEXT",
  "participants": ["Person1", ...],
  "action_items": ["Task 1", ...],
  "duration_seconds": <number>
}}

CRITICAL INSTRUCTIONS FOR OCR_TEXT FIELD:
- Detect and preserve code blocks from screenshots/screencasts
- Wrap code in triple backticks with language:
  ```python
  class Example:
      pass
  ```
- Use `## Slide Title` headers for new slides
- Use bullet points for slide bullet lists:
  - Point 1
  - Point 2
- For UI text (buttons, labels), use plain text
- For diagrams/charts, describe structure in Markdown tables if possible

Example OCR output:

## Introduction to SOLID Principles

### Single Responsibility Principle

A class should have only one reason to change.

**Example:**

```python
class UserService:
    def validate(self, user): ...
    def save(self, user): ...
```

**Problem:** Mixes validation and persistence.

## Better Design

Split into two classes:

```python
class UserValidator:
    def validate(self, user): ...

class UserRepository:
    def save(self, user): ...
```

CRITICAL INSTRUCTIONS FOR TRANSCRIPTION FIELD:
- Use same Markdown formatting rules as OCR
- Split speech into paragraphs (every 3-5 sentences)
- Use `## Speaker Name` for speaker changes
- Wrap code mentioned in speech in triple backticks"""


class GeminiVideoAnalyzer:
    """Мультимодальный анализатор видео через Gemini API.

    Отправляет кадры + оптимизированное аудио в одном запросе.
    Использует gemini-2.5-flash-lite по умолчанию (самая экономичная модель).

    Attributes:
        api_key: API ключ Google Gemini.
        model: Название модели (pro для видео).
        audio_analyzer: Опциональный аудио-анализатор (для отдельной транскрипции).

    Пример использования:
        >>> analyzer = GeminiVideoAnalyzer(api_key="...")
        >>> config = VideoAnalysisConfig(frame_count=10, include_audio=True)
        >>> result = analyzer.analyze(request, config)
        >>> print(result.description)
    """

    DEFAULT_MODEL = "gemini-2.5-flash-lite"

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        audio_analyzer: Optional["GeminiAudioAnalyzer"] = None,
        max_output_tokens: int = 65_536,
        output_language: str = "Russian",
    ):
        """Инициализация анализатора.

        Args:
            api_key: API ключ Google Gemini.
            model: Модель для Vision API (pro для видео).
            audio_analyzer: Опциональный анализатор для отдельной аудио-транскрипции.
            max_output_tokens: Лимит токенов на вывод модели.
            output_language: Язык для ответов модели.
        """
        self.api_key = api_key
        self.model = model
        self.audio_analyzer = audio_analyzer
        self.max_output_tokens = max_output_tokens
        self.output_language = output_language
        self.system_prompt = SYSTEM_PROMPT_TEMPLATE.format(language=output_language)
        self._client = None
        logger.debug(
            "Video analyzer initialized",
            model=model,
            has_audio_analyzer=audio_analyzer is not None,
        )

    @property
    def client(self):
        """Lazy-инициализация клиента Gemini."""
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
            logger.debug("Gemini client created")
        return self._client

    @retry_with_backoff(max_retries=5, base_delay=1.0, max_delay=60.0)
    def analyze(
        self,
        request: MediaRequest,
        config: Optional[VideoAnalysisConfig] = None,
    ) -> MediaAnalysisResult:
        """Анализирует видео (кадры + опционально аудио).

        Извлекает кадры и аудио-дорожку, отправляет в Gemini Pro
        для мультимодального анализа.

        Args:
            request: Запрос с медиа-ресурсом и контекстом.
            config: Конфигурация анализа видео.

        Returns:
            Результат анализа с описанием, транскрипцией и метаданными.

        Raises:
            MediaProcessingError: После исчерпания retry-попыток.
            ValueError: Если ответ невалидный.
        """
        from google.genai import types

        start_time = time.perf_counter()
        config = config or VideoAnalysisConfig()
        video_path = request.resource.path

        logger.debug(
            "Analyzing video",
            path=str(video_path),
            frame_mode=config.frame_mode,
            frame_count=config.frame_count,
            include_audio=config.include_audio,
        )

        # 1. Получаем длительность
        duration = get_video_duration(video_path)
        logger.debug(
            "Video duration",
            duration_sec=round(duration, 2),
        )

        # 2. Извлекаем кадры
        frames = extract_frames(
            video_path,
            mode=config.frame_mode,
            fps=config.fps,
            frame_count=config.frame_count,
            interval_seconds=config.interval_seconds,
            quality=config.frame_quality,
            max_frames=config.max_frames,
        )
        logger.debug(
            "Frames extracted",
            frame_count=len(frames),
        )

        # Конвертируем кадры в bytes
        frame_bytes_list = frames_to_bytes(frames, format="JPEG", quality=85)

        # 3. Извлекаем и оптимизируем аудио (опционально)
        audio_bytes = None
        audio_mime = None
        if config.include_audio:
            try:
                audio_bytes, audio_mime = optimize_audio_to_bytes(
                    extract_audio_from_video(video_path)
                )
                logger.debug(
                    "Audio extracted and optimized",
                    size_kb=round(len(audio_bytes) / 1024, 1),
                )
            except Exception as e:
                # Продолжаем без аудио (некоторые видео без звука)
                logger.debug(
                    "No audio extracted",
                    reason=str(e)[:100],
                )

        # 4. Собираем промпт
        prompt_parts = []
        if request.context_text:
            prompt_parts.append(f"Context: {request.context_text}")
        if request.user_prompt:
            prompt_parts.append(request.user_prompt)
        else:
            prompt_parts.append("Analyze this video for search indexing.")

        if audio_bytes:
            prompt_parts.append("Audio track is included for transcription.")

        prompt = "\n".join(prompt_parts)

        # 5. Собираем контент для запроса
        contents: list = [prompt]

        # Добавляем кадры
        for frame_bytes, mime_type in frame_bytes_list:
            contents.append(
                types.Part.from_bytes(
                    data=frame_bytes,
                    mime_type=mime_type,
                )
            )

        # Добавляем аудио (если есть)
        if audio_bytes and audio_mime:
            contents.append(
                types.Part.from_bytes(
                    data=audio_bytes,
                    mime_type=audio_mime,
                )
            )

        # 6. Конфигурация запроса
        api_config = types.GenerateContentConfig(
            system_instruction=self.system_prompt,
            temperature=0.4,
            max_output_tokens=self.max_output_tokens,
            response_mime_type="application/json",
            response_schema=VideoAnalysisSchema,
            safety_settings=[
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                ),
            ],
        )

        # 7. Вызываем API
        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=api_config,
        )

        # 8. Парсим результат
        if not response.text:
            logger.error("Gemini returned empty response", path=str(video_path))
            raise ValueError("Gemini returned empty response")

        # Логируем AI вызов
        response_preview = (
            response.text[:200] + "..." if len(response.text) > 200 else response.text
        )
        logger.trace_ai(
            prompt="Video analysis with frames",
            response=response_preview,
            model=self.model,
            operation="video_analysis",
        )

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse Gemini response as JSON",
                path=str(video_path),
                error=str(e),
                response_preview=response.text[:500],
            )
            raise ValueError(f"Invalid JSON in Gemini response: {e}")

        # Извлекаем usage_metadata (это Pydantic модель, не словарь)
        tokens_used = None
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            tokens_used = getattr(response.usage_metadata, "total_token_count", None)

        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Video analyzed",
            latency_ms=round(latency_ms, 2),
            duration_sec=round(duration, 2),
            frames_count=len(frames),
            has_audio=audio_bytes is not None,
            tokens_used=tokens_used,
            keywords_count=len(data.get("keywords", [])),
        )

        return MediaAnalysisResult(
            description=data["description"],
            alt_text=None,  # Видео не имеют alt-text
            keywords=data.get("keywords", []),
            ocr_text=data.get("ocr_text"),
            transcription=data.get("transcription"),
            participants=data.get("participants", []),
            action_items=data.get("action_items", []),
            duration_seconds=duration,
            tokens_used=tokens_used,
        )
