"""Интерфейс для хранилища векторов.

Классы:
    BaseVectorStore
        ABC для баз данных с векторным поиском.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

from semantic_core.domain import Document, Chunk, SearchResult, ChunkResult


class BaseVectorStore(ABC):
    """Абстрактный интерфейс для хранилища векторов.

    Определяет контракт для всех БД-адаптеров (Peewee+SQLite, SQLAlchemy+Postgres).
    Скрывает детали реализации (ORM, векторные расширения).
    """

    @abstractmethod
    def save(self, document: Document, chunks: list[Chunk]) -> Document:
        """Сохраняет документ с чанками атомарно.

        Args:
            document: Родительский документ.
            chunks: Список чанков с векторами.

        Returns:
            Document с заполненным id.

        Raises:
            ValueError: Если данные некорректны.
            RuntimeError: Если БД вернула ошибку.
        """
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        query_vector: Optional[Any] = None,
        query_text: Optional[str] = None,
        filters: Optional[dict] = None,
        limit: int = 10,
        mode: str = "hybrid",
        k: int = 60,
    ) -> list[SearchResult]:
        """Выполняет поиск документов.

        Args:
            query_vector: Вектор запроса (для векторного поиска).
            query_text: Текст запроса (для FTS).
            filters: Словарь фильтров (metadata).
            limit: Максимальное количество результатов.
            mode: Режим поиска ('vector', 'fts', 'hybrid').
            k: Константа для RRF алгоритма (по умолчанию 60).

        Returns:
            Список SearchResult с документами и скорами.

        Raises:
            ValueError: Если не передан ни vector, ни text.
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, document_id: int) -> int:
        """Удаляет документ и все его чанки.

        Args:
            document_id: ID документа.

        Returns:
            Количество удалённых строк.
        """
        raise NotImplementedError

    @abstractmethod
    def delete_by_metadata(self, filters: dict) -> int:
        """Удаляет чанки по фильтрам метаданных.

        Используется для удаления всех чанков, связанных с объектом
        перед переиндексацией (например, при обновлении).

        Args:
            filters: Словарь фильтров по метаданным (например, {"source_id": "123"}).

        Returns:
            Количество удалённых чанков.
        """
        raise NotImplementedError

    @abstractmethod
    def search_chunks(
        self,
        query_vector: Optional[Any] = None,
        query_text: Optional[str] = None,
        filters: Optional[dict] = None,
        limit: int = 10,
        mode: str = "hybrid",
        k: int = 60,
        chunk_type_filter: Optional[str] = None,
    ) -> list[ChunkResult]:
        """Выполняет гранулярный поиск отдельных чанков.

        В отличие от search(), который группирует чанки по документам,
        этот метод возвращает конкретные фрагменты (чанки).

        Args:
            query_vector: Вектор запроса (для векторного поиска).
            query_text: Текст запроса (для FTS).
            filters: Словарь фильтров по метаданным документа.
            limit: Максимальное количество результатов.
            mode: Режим поиска ('vector', 'fts', 'hybrid').
            k: Константа для RRF алгоритма.
            chunk_type_filter: Фильтр по типу чанка ('text', 'code', 'table', 'image_ref').

        Returns:
            Список ChunkResult с чанками и их метаданными.

        Raises:
            ValueError: Если не передан ни vector, ни text.
        """
        raise NotImplementedError

    @abstractmethod
    def bulk_update_vectors(self, vectors_dict: dict[str, bytes]) -> int:
        """Массово обновляет векторы для чанков.
        
        Используется для высокоскоростной записи результатов батч-обработки.
        Применяет executemany() для максимальной производительности.
        
        Args:
            vectors_dict: Словарь {chunk_id -> vector_blob}.
                chunk_id должен быть строковым представлением int ID.
        
        Returns:
            Количество обновлённых чанков.
        
        Raises:
            ValueError: Если словарь пустой.
            RuntimeError: Если произошла ошибка БД.
        
        Examples:
            >>> vectors = {"1": b"...", "2": b"..."}
            >>> count = store.bulk_update_vectors(vectors)
        """
        raise NotImplementedError
