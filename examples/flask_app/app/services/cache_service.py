"""Сервис кэширования поисковых запросов.

Кэширует эмбеддинги запросов для экономии API-вызовов
и предоставляет автокомплит популярных запросов.

Classes:
    QueryCacheService: Сервис для кэширования query → embedding.
    CacheResult: Результат получения эмбеддинга (hit/miss).

Usage:
    cache = QueryCacheService(embedder, database)
    result = cache.get_or_embed("python tutorial")
    if result.from_cache:
        print("Cache hit!")
"""

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import numpy as np
from peewee import Database

from app.models.cache import SearchQueryModel
from semantic_core.utils.logger import get_logger

if TYPE_CHECKING:
    from semantic_core.interfaces import Embedder

logger = get_logger("flask_app.cache")


@dataclass
class CacheResult:
    """Результат получения эмбеддинга.

    Attributes:
        embedding: Numpy массив эмбеддинга.
        from_cache: True если взято из кэша, False если вызван API.
        frequency: Количество использований запроса.
    """

    embedding: np.ndarray
    from_cache: bool
    frequency: int


class QueryCacheService:
    """Сервис кэширования эмбеддингов поисковых запросов.

    Экономит API-вызовы за счёт кэширования в SQLite.
    Предоставляет автокомплит на основе частотности.

    Attributes:
        embedder: Embedder для генерации эмбеддингов.
        database: Peewee Database для хранения кэша.
    """

    def __init__(self, embedder: "Embedder", database: Database) -> None:
        """Инициализировать сервис кэширования.

        Args:
            embedder: Embedder для генерации эмбеддингов при cache miss.
            database: Peewee Database (общая с semantic_core).
        """
        self.embedder = embedder
        self.database = database

        # Привязываем модель к базе данных
        SearchQueryModel._meta.database = database

        # Создаём таблицу если не существует
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Создать таблицу кэша если не существует."""
        self.database.create_tables([SearchQueryModel], safe=True)
        logger.debug("📦 Таблица search_query_cache готова")

    def get_or_embed(self, query: str) -> CacheResult:
        """Получить эмбеддинг запроса (из кэша или через API).

        При cache hit:
        - Возвращает кэшированный эмбеддинг
        - Инкрементирует frequency
        - Обновляет last_used_at

        При cache miss:
        - Вызывает embedder.embed_query()
        - Сохраняет в кэш
        - Логирует экономию

        Args:
            query: Текст поискового запроса.

        Returns:
            CacheResult с эмбеддингом и информацией о кэше.
        """
        query_hash = SearchQueryModel.compute_hash(query)

        # Попытка найти в кэше
        cached = SearchQueryModel.get_or_none(
            SearchQueryModel.query_hash == query_hash
        )

        if cached:
            # Cache hit
            logger.info(f"💾 Cache HIT: '{query[:30]}...' (freq: {cached.frequency})")
            cached.increment_frequency()

            embedding = np.frombuffer(cached.embedding, dtype=np.float32)
            return CacheResult(
                embedding=embedding,
                from_cache=True,
                frequency=cached.frequency,
            )

        # Cache miss — вызываем API
        logger.info(f"🔄 Cache MISS: '{query[:30]}...' — вызов API")
        embedding = self.embedder.embed_query(query)

        # Сохраняем в кэш
        SearchQueryModel.create(
            query_hash=query_hash,
            query_text=query,
            embedding=embedding.tobytes(),
            frequency=1,
            created_at=datetime.now(),
            last_used_at=datetime.now(),
        )

        return CacheResult(
            embedding=embedding,
            from_cache=False,
            frequency=1,
        )

    def suggest(self, partial_query: str, limit: int = 5) -> list[str]:
        """Получить автокомплит по частичному запросу.

        Возвращает популярные запросы, начинающиеся с partial_query.
        Сортировка по frequency (убывание).

        Args:
            partial_query: Начало запроса для автокомплита.
            limit: Максимальное количество предложений.

        Returns:
            Список текстов запросов (отсортирован по популярности).
        """
        if not partial_query or len(partial_query) < 2:
            return []

        normalized = partial_query.lower().strip()

        # Поиск по LIKE с сортировкой по частоте
        suggestions = (
            SearchQueryModel.select(SearchQueryModel.query_text)
            .where(SearchQueryModel.query_text.ilike(f"{normalized}%"))
            .order_by(SearchQueryModel.frequency.desc())
            .limit(limit)
        )

        return [s.query_text for s in suggestions]

    def get_stats(self) -> dict:
        """Получить статистику кэша.

        Returns:
            Словарь с total_queries, total_hits (sum of frequencies),
            unique_queries, avg_frequency.
        """
        from peewee import fn

        stats = SearchQueryModel.select(
            fn.COUNT(SearchQueryModel.id).alias("unique"),
            fn.SUM(SearchQueryModel.frequency).alias("total_hits"),
            fn.AVG(SearchQueryModel.frequency).alias("avg_freq"),
        ).dicts().get()

        return {
            "unique_queries": stats["unique"] or 0,
            "total_hits": stats["total_hits"] or 0,
            "avg_frequency": round(stats["avg_freq"] or 0, 2),
            "cache_savings": max(0, (stats["total_hits"] or 0) - (stats["unique"] or 0)),
        }

    def clear(self) -> int:
        """Очистить весь кэш.

        Returns:
            Количество удалённых записей.
        """
        count = SearchQueryModel.delete().execute()
        logger.warning(f"🗑️ Кэш очищен: {count} записей удалено")
        return count
