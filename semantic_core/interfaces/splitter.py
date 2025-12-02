"""Интерфейс для сплиттеров текста.

Классы:
    BaseSplitter
        ABC для нарезки документов на чанки.
"""

from abc import ABC, abstractmethod

from semantic_core.domain import Document, Chunk


class BaseSplitter(ABC):
    """Абстрактный интерфейс для сплиттеров.
    
    Определяет контракт для всех стратегий нарезки
    (Simple, Markdown, Code-aware, Video Timestamps).
    """
    
    @abstractmethod
    def split(self, document: Document) -> list[Chunk]:
        """Разбивает документ на чанки.
        
        Args:
            document: Исходный документ.
            
        Returns:
            Список чанков БЕЗ векторов (embedding=None).
            
        Raises:
            ValueError: Если document пустой.
        """
        raise NotImplementedError
