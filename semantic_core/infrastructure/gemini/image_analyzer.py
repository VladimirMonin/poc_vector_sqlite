"""Анализатор изображений через Gemini Vision API.

Классы:
    GeminiImageAnalyzer
        Анализирует изображения для семантического поиска.
"""

import json
import time
from typing import Optional

from pydantic import BaseModel

from semantic_core.domain.media import MediaRequest, MediaAnalysisResult
from semantic_core.infrastructure.gemini.resilience import retry_with_backoff
from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)


# Схема структурированного ответа для Gemini
class ImageAnalysisSchema(BaseModel):
    """Pydantic схема для structured output."""

    alt_text: str
    description: str
    keywords: list[str]
    ocr_text: Optional[str] = None


# Системный промпт для анализа изображений
SYSTEM_PROMPT = """You are an image analyst creating descriptions for semantic search indexing.

Analyze the image and provide:
1. alt_text: A concise accessibility description (1 sentence)
2. description: Detailed description of the image content (2-4 sentences)
3. keywords: List of 5-10 relevant keywords for search
4. ocr_text: Any visible text in the image (null if none)

Focus on:
- Main subject and objects
- Colors, mood, and style
- Text/OCR if present
- Context clues

Output valid JSON matching the schema."""


class GeminiImageAnalyzer:
    """Анализатор изображений через Gemini Vision API.

    Использует Gemini для генерации описаний изображений
    с структурированным выводом (JSON).

    Attributes:
        api_key: API ключ Google Gemini.
        model: Название модели Vision.

    Пример использования:
        >>> analyzer = GeminiImageAnalyzer(api_key="...")
        >>> request = MediaRequest(resource=resource, context_text="Travel blog")
        >>> result = analyzer.analyze(request)
        >>> print(result.description)
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash-lite",
    ):
        """Инициализация анализатора.

        Args:
            api_key: API ключ Google Gemini.
            model: Модель для Vision API.
        """
        self.api_key = api_key
        self.model = model
        self._client = None
        logger.debug(
            "Image analyzer initialized",
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
        """Анализирует изображение.

        Args:
            request: Запрос с медиа-ресурсом и контекстом.

        Returns:
            Результат анализа с описанием и ключевыми словами.

        Raises:
            MediaProcessingError: После исчерпания retry-попыток.
            ValueError: Если ответ невалидный.
        """
        from google.genai import types
        from PIL import Image

        start_time = time.perf_counter()
        image_path = str(request.resource.path)
        
        logger.debug(
            "Analyzing image",
            path=image_path,
            has_context=bool(request.context_text),
            has_prompt=bool(request.user_prompt),
        )

        # 1. Загружаем изображение
        image = Image.open(request.resource.path)
        width, height = image.size
        
        logger.trace(
            "Image loaded",
            width=width,
            height=height,
            mode=image.mode,
        )

        # 2. Собираем промпт
        prompt_parts = []
        if request.context_text:
            prompt_parts.append(f"Context: {request.context_text}")
        if request.user_prompt:
            prompt_parts.append(request.user_prompt)
        else:
            prompt_parts.append("Analyze this image for search indexing.")

        prompt = "\n".join(prompt_parts)

        # 3. Конфигурация запроса
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.4,
            max_output_tokens=1024,
            response_mime_type="application/json",
            response_schema=ImageAnalysisSchema,
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

        # 4. Вызываем API
        response = self.client.models.generate_content(
            model=self.model,
            contents=[prompt, image],
            config=config,
        )

        # 5. Парсим результат
        if not response.text:
            logger.error("Gemini returned empty response", path=image_path)
            raise ValueError("Gemini returned empty response")

        # Логируем AI вызов
        logger.trace_ai(
            operation="image_analysis",
            model=self.model,
            prompt_preview=prompt[:100] + "..." if len(prompt) > 100 else prompt,
            response_preview=response.text[:200] + "..." if len(response.text) > 200 else response.text,
        )

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse Gemini response as JSON",
                path=image_path,
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
            "Image analyzed",
            latency_ms=round(latency_ms, 2),
            tokens_used=tokens_used,
            keywords_count=len(data.get("keywords", [])),
            has_ocr=bool(data.get("ocr_text")),
        )

        return MediaAnalysisResult(
            description=data["description"],
            alt_text=data.get("alt_text"),
            keywords=data.get("keywords", []),
            ocr_text=data.get("ocr_text"),
            tokens_used=tokens_used,
        )
