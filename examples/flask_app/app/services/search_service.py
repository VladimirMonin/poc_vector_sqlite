"""Сервис поиска с кэшированием.

Оркестрирует поиск: кэш запросов → SemanticCore.search_chunks().
Преобразует ChunkResult в удобный для UI формат.

Classes:
    SearchService: Фасад для поиска с кэшем и фильтрацией.
    SearchResultItem: UI-friendly представление результата.

Usage:
    service = SearchService(core, cache)
    results = service.search("python async", filters={"chunk_type": "code"})
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from semantic_core.domain import ChunkResult, ChunkType, MatchType
from semantic_core.utils.logger import get_logger

if TYPE_CHECKING:
    from semantic_core.pipeline import SemanticCore
    from app.services.cache_service import QueryCacheService

logger = get_logger("flask_app.search")


@dataclass
class SearchResultItem:
    """UI-friendly представление результата поиска.

    Содержит всё необходимое для отображения карточки результата.

    Attributes:
        chunk_id: ID чанка.
        content: Содержимое чанка.
        chunk_type: Тип чанка (text, code, image_ref, etc.).
        language: Язык программирования (для code).
        score: Релевантность (0.0-1.0).
        score_percent: Релевантность в процентах (0-100).
        score_class: CSS класс для визуализации score.
        match_type: Тип совпадения (vector, fts, hybrid).
        parent_doc_id: ID родительского документа.
        parent_doc_title: Заголовок документа.
        highlight: Подсвеченный фрагмент (для FTS).
        context: Иерархический контекст чанка.
        tags: Теги из метаданных.
    """

    chunk_id: int
    content: str
    chunk_type: str
    language: Optional[str]
    score: float
    score_percent: int
    score_class: str
    match_type: str
    parent_doc_id: int
    parent_doc_title: Optional[str]
    highlight: Optional[str] = None
    context: str = ""
    tags: list[str] = field(default_factory=list)


def _score_to_class(score: float) -> str:
    """Преобразовать score в CSS класс.

    Args:
        score: Значение релевантности.

    Returns:
        CSS класс: 'score-high', 'score-medium', или 'score-low'.
    """
    if score >= 0.02:
        return "score-high"
    elif score >= 0.01:
        return "score-medium"
    return "score-low"


def _chunk_result_to_item(result: ChunkResult) -> SearchResultItem:
    """Преобразовать ChunkResult в SearchResultItem.

    Args:
        result: Результат поиска из SemanticCore.

    Returns:
        SearchResultItem для UI.
    """
    # Извлекаем теги из метаданных родителя
    tags = []
    if result.parent_metadata:
        tags = result.parent_metadata.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]

    # Извлекаем контекст из чанка
    context = ""
    if result.chunk.metadata:
        context = result.chunk.metadata.get("heading_hierarchy", "")

    return SearchResultItem(
        chunk_id=result.chunk_id or 0,
        content=result.content,
        chunk_type=result.chunk_type.value,
        language=result.language,
        score=result.score,
        score_percent=int(result.score * 100),
        score_class=_score_to_class(result.score),
        match_type=result.match_type.value,
        parent_doc_id=result.parent_doc_id,
        parent_doc_title=result.parent_doc_title,
        highlight=result.highlight,
        context=context,
        tags=tags,
    )


class SearchService:
    """Сервис поиска с интеграцией кэша.

    Использует QueryCacheService для кэширования эмбеддингов,
    а SemanticCore.search_chunks() для гранулярного поиска.

    Attributes:
        core: SemanticCore для поиска.
        cache: QueryCacheService для кэширования (опционально).
    """

    # Маппинг фильтра UI → ChunkType
    CHUNK_TYPE_FILTER_MAP = {
        "text": "text",
        "code": "code",
        "image": "image_ref",
        "audio": "audio_ref",
        "video": "video_ref",
    }

    def __init__(
        self,
        core: "SemanticCore",
        cache: Optional["QueryCacheService"] = None,
    ) -> None:
        """Инициализировать сервис поиска.

        Args:
            core: SemanticCore для выполнения поиска.
            cache: QueryCacheService для кэширования (None = без кэша).
        """
        self.core = core
        self.cache = cache

    def search(
        self,
        query: str,
        chunk_types: Optional[list[str]] = None,
        mode: str = "hybrid",
        limit: int = 20,
    ) -> list[SearchResultItem]:
        """Выполнить поиск по базе знаний.

        Args:
            query: Текст поискового запроса.
            chunk_types: Список типов чанков для фильтрации
                         (text, code, image, audio). None = все.
            mode: Режим поиска (vector, fts, hybrid).
            limit: Максимальное количество результатов.

        Returns:
            Список SearchResultItem для отображения в UI.
        """
        if not query or not query.strip():
            return []

        query = query.strip()
        # Гарантируем int для limit (защита от некорректных вызовов)
        limit = int(limit) if limit else 20
        logger.info(f"🔍 Поиск: '{query[:50]}...' mode={mode}, types={chunk_types}")

        # Если есть кэш — используем кэшированный вектор
        # (но для search_chunks всё равно нужен core)
        if self.cache:
            cache_result = self.cache.get_or_embed(query)
            logger.debug(f"💾 Cache {'HIT' if cache_result.from_cache else 'MISS'}")

        results: list[SearchResultItem] = []

        # Если выбраны типы чанков — ищем по каждому типу
        if chunk_types:
            for chunk_type_ui in chunk_types:
                chunk_type_filter = self.CHUNK_TYPE_FILTER_MAP.get(chunk_type_ui)
                if not chunk_type_filter:
                    continue

                type_results = self.core.search_chunks(
                    query=query,
                    mode=mode,
                    limit=limit,
                    chunk_type_filter=chunk_type_filter,
                )
                results.extend(_chunk_result_to_item(r) for r in type_results)
        else:
            # Поиск без фильтра по типу
            chunk_results = self.core.search_chunks(
                query=query,
                mode=mode,
                limit=limit,
            )
            results = [_chunk_result_to_item(r) for r in chunk_results]

        # Сортируем по score и обрезаем до limit
        results.sort(key=lambda x: x.score, reverse=True)
        results = results[:limit]

        logger.info(f"✅ Найдено {len(results)} результатов")
        return results

    def get_available_types(self) -> list[dict]:
        """Получить доступные типы контента для фильтра.

        Returns:
            Список словарей с id, label, icon для UI.
        """
        return [
            {"id": "text", "label": "Текст", "icon": "bi-file-text"},
            {"id": "code", "label": "Код", "icon": "bi-code-square"},
            {"id": "image", "label": "Изображения", "icon": "bi-image"},
            {"id": "audio", "label": "Аудио", "icon": "bi-music-note-beamed"},
            {"id": "video", "label": "Видео", "icon": "bi-camera-video"},
        ]
