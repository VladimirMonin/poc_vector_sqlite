"""Анализатор аудио через Gemini API.

Классы:
    GeminiAudioAnalyzer
        Анализирует аудио для транскрипции и семантического поиска.
"""

import json
import time
from typing import Optional

from pydantic import BaseModel

from semantic_core.domain.media import MediaAnalysisResult, MediaRequest
from semantic_core.infrastructure.gemini.resilience import retry_with_backoff
from semantic_core.infrastructure.media.utils.audio import (
    get_audio_duration,
    optimize_audio_to_bytes,
)
from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)


# Схема структурированного ответа для Gemini
class AudioAnalysisSchema(BaseModel):
    """Pydantic схема для structured output аудио."""

    transcription: str
    description: str
    keywords: list[str]
    participants: list[str] = []
    action_items: list[str] = []


# Системный промпт для анализа аудио
SYSTEM_PROMPT = """You are an audio analyst creating descriptions for semantic search indexing.

Analyze the audio and provide:
1. transcription: Full transcript of the spoken content
2. description: Summary of the audio content (2-4 sentences)
3. keywords: List of 5-10 relevant keywords for search
4. participants: List of speaker names/identifiers if mentioned
5. action_items: List of tasks or action items mentioned (if any)

Focus on:
- Main topics discussed
- Key points and conclusions
- Names, dates, and specific details
- Tasks or follow-up items

Output valid JSON matching the schema."""


class GeminiAudioAnalyzer:
    """Анализатор аудио через Gemini API.

    Использует gemini-2.5-flash-lite по умолчанию (в 4x дешевле flash).
    При дефолтных настройках обрабатывает до 83 минут аудио.

    Attributes:
        api_key: API ключ Google Gemini.
        model: Название модели.

    Пример использования:
        >>> analyzer = GeminiAudioAnalyzer(api_key="...")
        >>> request = MediaRequest(resource=resource, context_text="Meeting notes")
        >>> result = analyzer.analyze(request)
        >>> print(result.transcription)
    """

    # flash-lite: дешевле flash в 4x, достаточно для транскрипции
    DEFAULT_MODEL = "gemini-2.5-flash-lite"

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
    ):
        """Инициализация анализатора.

        Args:
            api_key: API ключ Google Gemini.
            model: Модель для Audio API (по умолчанию flash-lite).
        """
        self.api_key = api_key
        self.model = model
        self._client = None
        logger.debug(
            "Audio analyzer initialized",
            model=model,
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
    def analyze(self, request: MediaRequest) -> MediaAnalysisResult:
        """Анализирует аудио-файл.

        Автоматически оптимизирует аудио до 32kbps mono OGG
        для максимальной вместимости в 20MB лимит.

        Args:
            request: Запрос с медиа-ресурсом и контекстом.

        Returns:
            Результат анализа с транскрипцией и метаданными.

        Raises:
            MediaProcessingError: После исчерпания retry-попыток.
            ValueError: Если ответ невалидный.
        """
        from google.genai import types

        start_time = time.perf_counter()
        audio_path = str(request.resource.path)

        logger.debug(
            "Analyzing audio",
            path=audio_path,
            has_context=bool(request.context_text),
        )

        # 1. Получаем длительность
        duration = get_audio_duration(request.resource.path)
        logger.debug(
            "Audio duration",
            duration_sec=round(duration, 2),
        )

        # 2. Оптимизируем аудио для inline upload
        audio_bytes, mime_type = optimize_audio_to_bytes(request.resource.path)
        logger.debug(
            "Audio optimized",
            size_kb=round(len(audio_bytes) / 1024, 1),
            mime_type=mime_type,
        )

        # 3. Собираем промпт
        prompt_parts = []
        if request.context_text:
            prompt_parts.append(f"Context: {request.context_text}")
        if request.user_prompt:
            prompt_parts.append(request.user_prompt)
        else:
            prompt_parts.append("Transcribe and analyze this audio.")

        prompt = "\n".join(prompt_parts)

        # 4. Inline audio (до 20MB = ~83 мин при 32kbps)
        audio_part = types.Part.from_bytes(
            data=audio_bytes,
            mime_type=mime_type,
        )

        # 5. Конфигурация запроса
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.3,
            max_output_tokens=8192,  # Для длинных транскрипций
            response_mime_type="application/json",
            response_schema=AudioAnalysisSchema,
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

        # 6. Вызываем API
        response = self.client.models.generate_content(
            model=self.model,
            contents=[prompt, audio_part],
            config=config,
        )

        # 7. Парсим результат
        if not response.text:
            logger.error("Gemini returned empty response", path=audio_path)
            raise ValueError("Gemini returned empty response")

        # Логируем AI вызов
        logger.trace_ai(
            operation="audio_analysis",
            model=self.model,
            prompt_preview=prompt[:100] + "..." if len(prompt) > 100 else prompt,
            response_preview=response.text[:200] + "..."
            if len(response.text) > 200
            else response.text,
        )

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse Gemini response as JSON",
                path=audio_path,
                error=str(e),
                response_preview=response.text[:500],
            )
            raise ValueError(f"Invalid JSON in Gemini response: {e}")

        # Извлекаем usage_metadata (это Pydantic модель, не словарь)
        tokens_used = None
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            tokens_used = getattr(response.usage_metadata, "total_token_count", None)

        latency_ms = (time.perf_counter() - start_time) * 1000
        transcription = data.get("transcription", "")

        logger.info(
            "Audio analyzed",
            latency_ms=round(latency_ms, 2),
            duration_sec=round(duration, 2),
            tokens_used=tokens_used,
            transcription_length=len(transcription),
            participants_count=len(data.get("participants", [])),
        )

        return MediaAnalysisResult(
            description=data["description"],
            transcription=transcription,
            keywords=data.get("keywords", []),
            participants=data.get("participants", []),
            action_items=data.get("action_items", []),
            duration_seconds=duration,
            tokens_used=tokens_used,
        )
