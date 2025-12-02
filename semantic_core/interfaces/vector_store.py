"""Интерфейс для хранилища векторов.

Классы:
    BaseVectorStore
        ABC для баз данных с векторным поиском.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

from semantic_core.domain import Document, Chunk, SearchResult


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
    ) -> list[SearchResult]:
        """Выполняет поиск документов.

        Args:
            query_vector: Вектор запроса (для векторного поиска).
            query_text: Текст запроса (для FTS).
            filters: Словарь фильтров (metadata).
            limit: Максимальное количество результатов.
            mode: Режим поиска ('vector', 'fts', 'hybrid').

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
