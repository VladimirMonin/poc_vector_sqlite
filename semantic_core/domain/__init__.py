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
    MediaConfig
        Конфигурация для обработки медиа.
    TaskStatus
        Статусы задачи на обработку медиа.
    MediaResource
        Контейнер для медиа-файла.
    MediaRequest
        Запрос на анализ медиа.
    MediaAnalysisResult
        Результат анализа.
    VideoAnalysisConfig
        Конфигурация анализа видео (Phase 6.2).
"""

from semantic_core.domain.document import Document, MediaType
from semantic_core.domain.chunk import Chunk, ChunkType
from semantic_core.domain.search_result import SearchResult, ChunkResult, MatchType
from semantic_core.domain.auth import GoogleKeyring
from semantic_core.domain.config import MediaConfig
from semantic_core.domain.media import (
    TaskStatus,
    MediaResource,
    MediaRequest,
    MediaAnalysisResult,
    VideoAnalysisConfig,
)

__all__ = [
    "Document",
    "MediaType",
    "Chunk",
    "ChunkType",
    "SearchResult",
    "ChunkResult",
    "MatchType",
    "GoogleKeyring",
    "MediaConfig",
    "TaskStatus",
    "MediaResource",
    "MediaRequest",
    "MediaAnalysisResult",
    "VideoAnalysisConfig",
]
