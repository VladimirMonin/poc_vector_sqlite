"""Доменный слой с чистыми объектами данных (DTO).

Классы:
    Document
        Представление исходного документа.
    Chunk
        Фрагмент документа для векторного поиска.
    ChunkType
        Перечисление типов контента в чанке.
    SearchResult
        Унифицированный результат поиска.
    MediaType
        Перечисление типов медиа.
    MatchType
        Перечисление типов совпадения в поиске.
"""

from semantic_core.domain.document import Document, MediaType
from semantic_core.domain.chunk import Chunk, ChunkType
from semantic_core.domain.search_result import SearchResult, MatchType

__all__ = [
    "Document",
    "MediaType",
    "Chunk",
    "ChunkType",
    "SearchResult",
    "MatchType",
]
