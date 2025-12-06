"""Сервис поиска с кэшированием.

Оркестрирует поиск: кэш запросов → SemanticCore.search_chunks().
Преобразует ChunkResult в удобный для UI формат.

Classes:
    SearchService: Фасад для поиска с кэшем и фильтрацией.
    SearchResultItem: UI-friendly представление результата (чанк).
    DocumentResultItem: UI-friendly представление результата (документ).

Usage:
    service = SearchService(core, cache)
    results = service.search("python async", filters={"chunk_type": "code"})
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from semantic_core.domain import ChunkResult, ChunkType, MatchType, SearchResult
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


@dataclass
class DocumentResultItem:
    """UI-friendly представление результата поиска (документ).

    Используется в режиме результатов 'documents'.

    Attributes:
        doc_id: ID документа.
        title: Заголовок документа.
        source: Путь к исходному файлу.
        score: Релевантность (0.0-1.0).
        score_percent: Релевантность в процентах (0-100).
        score_class: CSS класс для визуализации score.
        match_type: Тип совпадения (vector, fts, hybrid).
        chunk_count: Количество чанков в документе.
        tags: Теги из метаданных.
        description: Краткое описание (из первых N символов).
    """

    doc_id: int
    title: str
    source: Optional[str]
    score: float
    score_percent: int
    score_class: str
    match_type: str
    chunk_count: int = 0
    tags: list[str] = field(default_factory=list)
    description: str = ""


def _score_to_class(score: float, match_type: MatchType) -> str:
    """Преобразовать score в CSS класс с учётом режима.

    Args:
        score: Значение релевантности.
        match_type: Режим поиска.

    Returns:
        CSS класс: 'score-high', 'score-medium', или 'score-low'.
    """
    if match_type == MatchType.HYBRID:
        # RRF пороги
        if score >= 0.02:
            return "score-high"
        elif score >= 0.01:
            return "score-medium"
        return "score-low"
    else:
        # Vector/FTS пороги (0.0-1.0)
        if score >= 0.7:
            return "score-high"
        elif score >= 0.4:
            return "score-medium"
        return "score-low"


def _normalize_score(score: float, match_type: MatchType) -> int:
    """Нормализовать score в проценты с учётом режима поиска.

    Args:
        score: Raw score из ядра.
        match_type: Режим поиска (HYBRID, VECTOR, FTS).

    Returns:
        Нормализованный процент (0-100).
    """
    if match_type == MatchType.HYBRID:
        # RRF score с k=1:
        # Max score (Rank 1 in both) = 1/(1+1) + 1/(1+1) = 0.5 + 0.5 = 1.0
        # Min score (Rank 100 in one) = 1/(1+100) = 0.0099
        # Так как max = 1.0, то просто умножаем на 100
        return int(min(score, 1.0) * 100)
    else:
        # Vector/FTS score: 0.0-1.0 → 0-100%
        return int(min(max(score, 0.0), 1.0) * 100)



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
        score_percent=_normalize_score(result.score, result.match_type),
        score_class=_score_to_class(result.score, result.match_type),
        match_type=result.match_type.value,
        parent_doc_id=result.parent_doc_id,
        parent_doc_title=result.parent_doc_title,
        highlight=result.highlight,
        context=context,
        tags=tags,
    )


def _search_result_to_item(result: SearchResult) -> DocumentResultItem:
    """Преобразовать SearchResult в DocumentResultItem.

    Args:
        result: Результат поиска из SemanticCore.search().

    Returns:
        DocumentResultItem для UI.
    """
    doc = result.document
    metadata = doc.metadata or {}

    # Извлекаем теги
    tags = metadata.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]

    # Извлекаем source из metadata (Document не имеет атрибута source)
    source = metadata.get("source", "")

    # Создаём описание из первых 200 символов content
    description = ""
    if doc.content:
        description = doc.content[:200].strip()
        if len(doc.content) > 200:
            description += "..."

    return DocumentResultItem(
        doc_id=doc.id or 0,
        title=metadata.get("title") or source or "Untitled",
        source=source,
        score=result.score,
        score_percent=_normalize_score(result.score, result.match_type),
        score_class=_score_to_class(result.score, result.match_type),
        match_type=result.match_type.value,
        chunk_count=metadata.get("chunk_count", 0),
        tags=tags,
        description=description,
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
        "text": ["text"],
        "code": ["code"],
        "image": ["image_ref"],
        "audio": ["audio_ref"],
        "video": ["video_ref"],
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
        min_score: int = 0,
    ) -> list[SearchResultItem]:
        """Выполнить поиск по базе знаний.

        Args:
            query: Текст поискового запроса.
            chunk_types: Список типов чанков для фильтрации
                         (text, code, image, audio). None = все.
            mode: Режим поиска (vector, fts, hybrid).
            limit: Максимальное количество результатов.
            min_score: Минимальный порог релевантности (0-100%).

        Returns:
            Список SearchResultItem для отображения в UI.
        """
        if not query or not query.strip():
            return []

        query = query.strip()
        # Гарантируем int для limit (защита от некорректных вызовов)
        limit = int(limit) if limit else 20
        logger.info(f"🔍 Поиск: '{query[:50]}...' mode={mode}, types={chunk_types}")

        # Получаем закешированный вектор (или генерируем новый)
        query_vector: Optional[list[float]] = None
        if self.cache and mode in ("vector", "hybrid"):
            cache_result = self.cache.get_or_embed(query)
            query_vector = cache_result.embedding
            cache_status = "HIT ✅" if cache_result.from_cache else "MISS ❌"
            logger.info(f"💾 Cache {cache_status}")

        results: list[SearchResultItem] = []

        # ВСЕГДА делаем ОДИН общий поиск (без фильтра по типу)
        # Это гарантирует корректный RRF ranking
        chunk_results = self.core.search_chunks(
            query=query,
            mode=mode,
            limit=limit * 4 if chunk_types else limit,  # Берём больше если есть фильтр
            k=1,
            query_vector=query_vector,
        )
        
        # Конвертируем в SearchResultItem
        all_results = [_chunk_result_to_item(r) for r in chunk_results]
        
        # Фильтруем по типам ПОСЛЕ поиска (если нужно)
        if chunk_types:
            # Собираем ChunkType фильтры
            allowed_types: set[str] = set()
            for chunk_type_ui in chunk_types:
                chunk_filters = self.CHUNK_TYPE_FILTER_MAP.get(chunk_type_ui)
                if chunk_filters:
                    allowed_types.update(chunk_filters)
            
            # Фильтруем результаты
            results = [r for r in all_results if r.chunk_type in allowed_types]
        else:
            results = all_results
        
        # Обрезаем до limit (уже отсортировано по score из core)
        results = results[:limit]

        # Фильтрация по минимальному score (в процентах)
        if min_score > 0:
            results = [r for r in results if r.score_percent >= min_score]

        results = results[:limit]

        logger.info(f"✅ Найдено {len(results)} результатов")
        return results

    def search_documents(
        self,
        query: str,
        mode: str = "hybrid",
        limit: int = 20,
        min_score: int = 0,
    ) -> list[DocumentResultItem]:
        """Выполнить поиск по документам (агрегация по документам).

        Args:
            query: Текст поискового запроса.
            mode: Режим поиска (vector, fts, hybrid).
            limit: Максимальное количество результатов.
            min_score: Минимальный порог релевантности (0-100%).

        Returns:
            Список DocumentResultItem для отображения в UI.
        """
        if not query or not query.strip():
            return []

        query = query.strip()
        limit = int(limit) if limit else 20
        logger.info(f"📄 Поиск документов: '{query[:50]}...' mode={mode}")

        # Получаем закешированный вектор
        query_vector: Optional[list[float]] = None
        if self.cache and mode in ("vector", "hybrid"):
            cache_result = self.cache.get_or_embed(query)
            query_vector = cache_result.embedding
            logger.info(f"💾 Cache {'HIT ✅' if cache_result.from_cache else 'MISS ❌'}")

        # Используем core.search() для поиска по документам
        search_results = self.core.search(
            query=query,
            mode=mode,
            limit=limit,
            k=1,
            query_vector=query_vector,
        )

        results = [_search_result_to_item(r) for r in search_results]

        # Фильтрация по минимальному score (в процентах)
        if min_score > 0:
            results = [r for r in results if r.score_percent >= min_score]

        logger.info(f"✅ Найдено {len(results)} документов")
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
