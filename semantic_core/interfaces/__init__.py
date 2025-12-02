"""Интерфейсы (контракты) для компонентов системы.

Классы:
    BaseEmbedder
        Абстрактный интерфейс для генераторов эмбеддингов.
    BaseVectorStore
        Абстрактный интерфейс для хранилища векторов.
    BaseSplitter
        Абстрактный интерфейс для нарезки текста.
    BaseContextStrategy
        Абстрактный интерфейс для формирования контекста.
    DocumentParser
        Протокол для парсеров документов.
    ParsingSegment
        Промежуточная структура между парсингом и чанкингом.
"""

from semantic_core.interfaces.embedder import BaseEmbedder
from semantic_core.interfaces.vector_store import BaseVectorStore
from semantic_core.interfaces.splitter import BaseSplitter
from semantic_core.interfaces.context import BaseContextStrategy
from semantic_core.interfaces.parser import DocumentParser, ParsingSegment

__all__ = [
    "BaseEmbedder",
    "BaseVectorStore",
    "BaseSplitter",
    "BaseContextStrategy",
    "DocumentParser",
    "ParsingSegment",
]
