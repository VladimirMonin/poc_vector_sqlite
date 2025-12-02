"""Интерфейс для стратегий формирования контекста.

Классы:
    BaseContextStrategy
        ABC для обогащения чанков контекстом.
"""

from abc import ABC, abstractmethod

from semantic_core.domain import Document, Chunk


class BaseContextStrategy(ABC):
    """Абстрактный интерфейс для стратегий контекста.

    Определяет, как формировать текст для векторизации:
    - BasicContext: заголовок + текст чанка
    - HierarchicalContext: breadcrumbs (Глава > Раздел) + чанк
    - NoContext: только сырой текст чанка
    """

    @abstractmethod
    def form_vector_text(self, chunk: Chunk, document: Document) -> str:
        """Формирует текст для генерации эмбеддинга.

        Args:
            chunk: Чанк для обогащения.
            document: Родительский документ (источник метаданных).

        Returns:
            Строка, которая будет подана в embedder.
        """
        raise NotImplementedError
