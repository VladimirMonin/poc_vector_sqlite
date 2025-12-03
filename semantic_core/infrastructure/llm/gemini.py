"""Реализация BaseLLMProvider для Google Gemini API.

Классы:
    GeminiLLMProvider
        Адаптер для генерации текста через Gemini.
"""

import time
from typing import Optional

from google import genai
from google.genai import types

from semantic_core.interfaces.llm import BaseLLMProvider, GenerationResult
from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)


class GeminiLLMProvider(BaseLLMProvider):
    """Провайдер LLM на основе Google Gemini API.

    Использует google-genai SDK для генерации текста.
    Поддерживает системный промпт, температуру и ограничение токенов.

    Attributes:
        model: Название модели Gemini.

    Example:
        >>> provider = GeminiLLMProvider(api_key="...", model="gemini-2.0-flash")
        >>> result = provider.generate("Что такое RAG?")
        >>> print(result.text)
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
    ):
        """Инициализация провайдера.

        Args:
            api_key: API ключ Google Gemini.
            model: Название модели (по умолчанию gemini-2.0-flash).
        """
        self._client = genai.Client(api_key=api_key)
        self._model = model

        logger.debug(
            "GeminiLLMProvider initialized",
            model=model,
        )

    @property
    def model_name(self) -> str:
        """Название используемой модели."""
        return self._model

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> GenerationResult:
        """Генерирует ответ на основе промпта.

        Args:
            prompt: Текст запроса к модели.
            system_prompt: Системный промпт (инструкции для модели).
            temperature: Температура генерации (0.0-2.0).
            max_tokens: Максимальное количество токенов в ответе.

        Returns:
            GenerationResult с текстом и метаданными.

        Raises:
            RuntimeError: Если API вернул ошибку.
        """
        logger.debug(
            "Generating response",
            model=self._model,
            prompt_length=len(prompt),
            has_system_prompt=system_prompt is not None,
        )

        start_time = time.perf_counter()

        try:
            # Формируем конфигурацию
            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                system_instruction=system_prompt,
            )

            # Вызываем API
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=config,
            )

            latency_ms = (time.perf_counter() - start_time) * 1000

            # Извлекаем метаданные
            usage = response.usage_metadata
            input_tokens = usage.prompt_token_count if usage else None
            output_tokens = usage.candidates_token_count if usage else None

            # Определяем причину завершения
            finish_reason = None
            if response.candidates and response.candidates[0].finish_reason:
                finish_reason = str(response.candidates[0].finish_reason.name)

            result = GenerationResult(
                text=response.text or "",
                model=self._model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                finish_reason=finish_reason,
            )

            logger.info(
                "Response generated",
                latency_ms=round(latency_ms, 2),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                finish_reason=finish_reason,
            )

            # Логируем AI вызов для отладки
            prompt_preview = prompt[:100] + "..." if len(prompt) > 100 else prompt
            response_preview = (
                result.text[:100] + "..." if len(result.text) > 100 else result.text
            )

            logger.trace_ai(
                prompt=prompt_preview,
                response=response_preview,
                model=self._model,
                tokens_in=input_tokens,
                tokens_out=output_tokens,
                duration_ms=latency_ms,
                temperature=temperature,
            )

            return result

        except Exception as e:
            logger.error(
                "LLM generation failed",
                error_type=type(e).__name__,
                model=self._model,
            )
            raise RuntimeError(f"Ошибка генерации LLM: {e}") from e


__all__ = ["GeminiLLMProvider"]
