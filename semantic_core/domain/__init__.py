"""Доменный слой с чистыми объектами данных (DTO).

Классы:
    Document
        Представление исходного документа.
    Chunk
        Фрагмент документа для векторного поиска.
    ChunkType
        Перечисление типов контента в чанке.
    SearchResult
        Унифицированный результат поиска (документ).
    ChunkResult
        Результат гранулярного поиска (отдельный чанк).
    MediaType
        Перечисление типов медиа.
    MatchType
        Перечисление типов совпадения в поиске.
    GoogleKeyring
        Контейнер для API-ключей Google с разделением биллинга.
"""

from semantic_core.domain.document import Document, MediaType
from semantic_core.domain.chunk import Chunk, ChunkType
from semantic_core.domain.search_result import SearchResult, ChunkResult, MatchType
from semantic_core.domain.auth import GoogleKeyring

__all__ = [
    "Document",
    "MediaType",
    "Chunk",
    "ChunkType",
    "SearchResult",
    "ChunkResult",
    "MatchType",
    "GoogleKeyring",
]
