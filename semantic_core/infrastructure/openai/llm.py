"""Реализация BaseLLMProvider для OpenAI API.

Классы:
    OpenAILLMProvider
        Провайдер для генерации ответов через OpenAI API (GPT-4o, GPT-4o-mini, etc).
"""

import time
from typing import Optional, Iterator

from openai import OpenAI, RateLimitError, APIError, APITimeoutError
import tiktoken

from semantic_core.interfaces.llm import BaseLLMProvider, GenerationResult
from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)


class OpenAILLMProvider(BaseLLMProvider):
    """Провайдер LLM для OpenAI API.

    Поддерживает модели GPT-4o, GPT-4o-mini, GPT-3.5-turbo для RAG.
    Использует официальный OpenAI Python SDK.

    Attributes:
        model: Название модели.
        api_key: API ключ OpenAI.

    Example:
        >>> provider = OpenAILLMProvider(
        ...     api_key="sk-...",
        ...     model="gpt-4o-mini",
        ... )
        >>> result = provider.generate("Что такое RAG?")
        >>> print(result.text)

        >>> # С системным промптом
        >>> result = provider.generate(
        ...     prompt="Объясни векторный поиск",
        ...     system_prompt="Ты эксперт по поисковым системам"
        ... )

        >>> # Streaming
        >>> for chunk in provider.generate_stream("Напиши код"):
        ...     print(chunk, end="", flush=True)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        """Инициализация провайдера.

        Args:
            api_key: API ключ OpenAI (если None, берётся из OPENAI_API_KEY env).
            model: Название модели (gpt-4o, gpt-4o-mini, gpt-3.5-turbo).
            temperature: Температура генерации (0.0-2.0).
            max_tokens: Максимальное количество токенов в ответе.
            timeout: Таймаут запроса в секундах.
            max_retries: Максимальное количество повторов при ошибках.
        """
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout

        # Создаём клиент OpenAI
        self._client = OpenAI(
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )

        # Инициализируем tiktoken encoder для модели
        try:
            self._encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback для неизвестных моделей
            logger.warning(
                f"Unknown model '{model}', using cl100k_base encoding",
                model=model,
            )
            self._encoding = tiktoken.get_encoding("cl100k_base")

        logger.debug(
            "OpenAILLMProvider initialized",
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    @property
    def model_name(self) -> str:
        """Название используемой модели."""
        return self._model

    def _build_messages(
        self,
        prompt: str,
        system_prompt: Optional[str],
        history: Optional[list[dict]],
    ) -> list[dict]:
        """Построить список сообщений для API.

        Args:
            prompt: Текст запроса пользователя.
            system_prompt: Системный промпт.
            history: История чата.

        Returns:
            Список сообщений в формате OpenAI.
        """
        messages = []

        # Добавляем системный промпт
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Добавляем историю
        if history:
            messages.extend(history)

        # Добавляем текущий запрос
        messages.append({"role": "user", "content": prompt})

        return messages

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        history: Optional[list[dict]] = None,
    ) -> GenerationResult:
        """Генерирует ответ на основе промпта.

        Args:
            prompt: Текст запроса к модели.
            system_prompt: Системный промпт (инструкции для модели).
            temperature: Температура генерации (переопределяет default).
            max_tokens: Максимальное количество токенов (переопределяет default).
            history: История чата как список dict с role и content.

        Returns:
            GenerationResult с текстом и метаданными.

        Raises:
            RateLimitError: Если превышен лимит запросов.
            APIError: Если API вернул ошибку.
            RuntimeError: Для других ошибок.
        """
        logger.debug(
            "Generating response",
            model=self._model,
            prompt_length=len(prompt),
            has_system_prompt=system_prompt is not None,
            history_messages=len(history) if history else 0,
        )

        start_time = time.perf_counter()

        try:
            messages = self._build_messages(prompt, system_prompt, history)

            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens or self._max_tokens,
            )

            latency_ms = (time.perf_counter() - start_time) * 1000

            # Извлекаем текст из ответа
            choice = response.choices[0]
            text = choice.message.content or ""
            finish_reason = choice.finish_reason

            # Извлекаем метаданные токенов
            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else None
            output_tokens = usage.completion_tokens if usage else None

            result = GenerationResult(
                text=text,
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
            )

            return result

        except RateLimitError as e:
            logger.error(
                "Rate limit exceeded",
                model=self._model,
                error=str(e),
            )
            raise

        except APITimeoutError as e:
            logger.error(
                "API timeout",
                model=self._model,
                timeout=self._timeout,
                error=str(e),
            )
            raise RuntimeError(f"OpenAI API timeout: {e}") from e

        except APIError as e:
            logger.error(
                "OpenAI API error",
                model=self._model,
                status_code=e.status_code if hasattr(e, "status_code") else None,
                error=str(e),
            )
            raise

        except Exception as e:
            logger.error(
                "Unexpected error during generation",
                model=self._model,
                error=str(e),
            )
            raise RuntimeError(f"Ошибка генерации LLM: {e}") from e

    def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        history: Optional[list[dict]] = None,
    ) -> Iterator[str]:
        """Генерирует ответ в режиме streaming.

        Args:
            prompt: Текст запроса к модели.
            system_prompt: Системный промпт.
            temperature: Температура генерации.
            max_tokens: Максимальное количество токенов.
            history: История чата.

        Yields:
            Чанки текста по мере генерации.

        Raises:
            RateLimitError: Если превышен лимит запросов.
            APIError: Если API вернул ошибку.
        """
        logger.debug(
            "Generating streaming response",
            model=self._model,
            prompt_length=len(prompt),
        )

        try:
            messages = self._build_messages(prompt, system_prompt, history)

            stream = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens or self._max_tokens,
                stream=True,
            )

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except RateLimitError as e:
            logger.error("Rate limit exceeded during streaming", error=str(e))
            raise

        except APIError as e:
            logger.error("OpenAI API error during streaming", error=str(e))
            raise

        except Exception as e:
            logger.error("Unexpected error during streaming", error=str(e))
            raise RuntimeError(f"Ошибка streaming генерации: {e}") from e

    def count_tokens(self, text: str) -> int:
        """Подсчёт токенов в тексте через tiktoken.

        Args:
            text: Текст для подсчёта токенов.

        Returns:
            Количество токенов.

        Example:
            >>> provider = OpenAILLMProvider(model="gpt-4o-mini")
            >>> tokens = provider.count_tokens("Hello, world!")
            >>> print(tokens)  # 4
        """
        return len(self._encoding.encode(text))


__all__ = ["OpenAILLMProvider"]
