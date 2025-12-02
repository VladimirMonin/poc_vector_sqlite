"""Прокси-объект для выполнения поисковых запросов.

Классы:
    SearchProxy
        Прокси для выполнения поиска через SemanticCore с возвратом ORM объектов.
"""

from typing import Any, Optional, TYPE_CHECKING

from semantic_core.domain import SearchResult, ChunkResult

if TYPE_CHECKING:
    from semantic_core.pipeline import SemanticCore
    from semantic_core.integrations.base import SemanticIndex


class SearchProxy:
    """Прокси для выполнения поисковых запросов.

    Предоставляет удобный API для поиска через SemanticCore.
    Автоматически преобразует результаты поиска в ORM объекты.

    Пример:
        >>> results = Article.search.hybrid("python tutorial", limit=5)
        >>> for obj, score in results:
        ...     print(f"{obj.title}: {score}")

    Attributes:
        core: Экземпляр SemanticCore для выполнения поиска.
        model: Класс ORM модели.
        descriptor: Родительский дескриптор SemanticIndex.
    """

    def __init__(
        self,
        core: "SemanticCore",
        model: type,
        descriptor: "SemanticIndex",
    ):
        self.core = core
        self.model = model
        self.descriptor = descriptor

    def hybrid(
        self,
        query: str,
        limit: int = 10,
        k: int = 60,
        **filters: Any,
    ) -> list[tuple[Any, float]]:
        """Выполняет гибридный поиск (RRF: Vector + FTS).

        Args:
            query: Поисковый запрос.
            limit: Максимальное количество результатов.
            k: Константа для RRF алгоритма (по умолчанию 60).
            **filters: Фильтры по метаданным (передаются как kwargs).

        Returns:
            Список кортежей (ORM объект, скор).

        Raises:
            ValueError: Если query пустой.
        """
        # Выполняем поиск через core
        results = self.core.search(
            query=query,
            filters=filters or None,
            limit=limit,
            mode="hybrid",
            k=k,
        )

        # Преобразуем результаты в ORM объекты
        return self._results_to_objects(results)

    def vector(
        self,
        query: str,
        limit: int = 10,
        **filters: Any,
    ) -> list[tuple[Any, float]]:
        """Выполняет векторный семантический поиск.

        Args:
            query: Поисковый запрос.
            limit: Максимальное количество результатов.
            **filters: Фильтры по метаданным.

        Returns:
            Список кортежей (ORM объект, скор).

        Raises:
            ValueError: Если query пустой.
        """
        results = self.core.search(
            query=query,
            filters=filters or None,
            limit=limit,
            mode="vector",
        )

        return self._results_to_objects(results)

    def fts(
        self,
        query: str,
        limit: int = 10,
        **filters: Any,
    ) -> list[tuple[Any, float]]:
        """Выполняет полнотекстовый поиск (FTS5).

        Args:
            query: Поисковый запрос.
            limit: Максимальное количество результатов.
            **filters: Фильтры по метаданным.

        Returns:
            Список кортежей (ORM объект, скор).

        Raises:
            ValueError: Если query пустой.
        """
        results = self.core.search(
            query=query,
            filters=filters or None,
            limit=limit,
            mode="fts",
        )

        return self._results_to_objects(results)

    def chunks(
        self,
        query: str,
        limit: int = 10,
        mode: str = "hybrid",
        k: int = 60,
        chunk_type: Optional[str] = None,
        **filters: Any,
    ) -> list[ChunkResult]:
        """Выполняет гранулярный поиск отдельных чанков.

        В отличие от обычных методов поиска, которые возвращают
        целые документы (ORM объекты), этот метод возвращает
        конкретные фрагменты с их контекстом.

        Args:
            query: Поисковый запрос.
            limit: Максимальное количество результатов.
            mode: Режим поиска ('vector', 'fts', 'hybrid').
            k: Константа для RRF алгоритма.
            chunk_type: Фильтр по типу чанка ('text', 'code', 'table', 'image_ref').
            **filters: Фильтры по метаданным документа.

        Returns:
            Список ChunkResult.

        Raises:
            ValueError: Если query пустой.

        Example:
            >>> # Найти только блоки кода Python
            >>> code_chunks = Article.search.chunks(
            ...     "сортировка списка",
            ...     chunk_type="code",
            ...     limit=5
            ... )
            >>> for chunk_result in code_chunks:
            ...     print(f"Язык: {chunk_result.chunk.language}")
            ...     print(f"Код: {chunk_result.chunk.content}")
            ...     print(f"Из: {chunk_result.parent_doc_title}")
        """
        results = self.core.storage.search_chunks(
            query_vector=self.core.embedder.embed_query(query) if mode in ("vector", "hybrid") else None,
            query_text=query if mode in ("fts", "hybrid") else None,
            filters=filters or None,
            limit=limit,
            mode=mode,
            k=k,
            chunk_type_filter=chunk_type,
        )

        return results

    def _results_to_objects(
        self, results: list[SearchResult]
    ) -> list[tuple[Any, float]]:
        """Преобразует SearchResult в ORM объекты.

        Args:
            results: Список SearchResult из core.

        Returns:
            Список кортежей (ORM объект, скор).
        """
        if not results:
            return []

        # Извлекаем source_id из метаданных документа
        source_ids = []
        for result in results:
            source_id = result.document.metadata.get("source_id")
            if source_id is not None:
                source_ids.append(source_id)

        if not source_ids:
            return []

        # Получаем объекты из БД (используем Peewee напрямую для простоты)
        # В идеале здесь должен быть вызов адаптера, но пока делаем напрямую
        from semantic_core.integrations.peewee.utils import fetch_objects_ordered

        objects = fetch_objects_ordered(self.model, source_ids)

        # Создаем словарь для быстрого доступа
        objects_dict = {getattr(obj, "id"): obj for obj in objects}

        # Склеиваем объекты со скорами
        result_tuples = []
        for result in results:
            source_id = result.document.metadata.get("source_id")
            if source_id in objects_dict:
                result_tuples.append((objects_dict[source_id], result.score))

        return result_tuples
