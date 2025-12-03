"""Интерфейсы для провайдеров LLM (Language Models).

Классы:
    GenerationResult
        DTO с результатом генерации от LLM.
    BaseLLMProvider
        Абстрактный интерфейс для LLM провайдеров.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GenerationResult:
    """Результат генерации от LLM.

    Attributes:
        text: Сгенерированный текст.
        model: Название использованной модели.
        input_tokens: Количество входных токенов.
        output_tokens: Количество выходных токенов.
        finish_reason: Причина завершения генерации.
    """

    text: str
    model: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    finish_reason: Optional[str] = None

    @property
    def total_tokens(self) -> Optional[int]:
        """Общее количество токенов (input + output)."""
        if self.input_tokens is not None and self.output_tokens is not None:
            return self.input_tokens + self.output_tokens
        return None


class BaseLLMProvider(ABC):
    """Абстрактный интерфейс для провайдеров LLM.

    Определяет контракт для взаимодействия с языковыми моделями.
    Поддерживает системный промпт, температуру и ограничение токенов.

    Example:
        >>> class MyProvider(BaseLLMProvider):
        ...     def generate(self, prompt, **kwargs):
        ...         # Логика генерации
        ...         return GenerationResult(text="...", model="my-model")
        ...
        ...     @property
        ...     def model_name(self):
        ...         return "my-model"
    """

    @abstractmethod
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
            temperature: Температура генерации (0.0-2.0).
            max_tokens: Максимальное количество токенов в ответе.
            history: История чата как список dict с role и content.
                     Пример: [{"role": "user", "content": "Hi"}]

        Returns:
            GenerationResult с текстом и метаданными.

        Raises:
            RuntimeError: Если API вернул ошибку.
        """
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Название используемой модели."""
        pass


__all__ = ["GenerationResult", "BaseLLMProvider"]
