"""Оркестратор пайплайна обработки документов.

Классы:
    SemanticCore
        Фасад для всей системы семантического поиска.
"""

from typing import Optional

from semantic_core.interfaces import (
    BaseEmbedder,
    BaseVectorStore,
    BaseSplitter,
    BaseContextStrategy,
)
from semantic_core.domain import Document, SearchResult


class SemanticCore:
    """Главный оркестратор системы семантического поиска.

    Связывает все компоненты через Dependency Injection:
    - Splitter: Нарезка документов на чанки.
    - Context Strategy: Обогащение чанков контекстом.
    - Embedder: Генерация векторов.
    - Vector Store: Хранение и поиск.

    Пример использования:
        >>> from semantic_core import SemanticCore
        >>> from semantic_core.infrastructure.gemini import GeminiEmbedder
        >>> from semantic_core.infrastructure.storage import PeeweeVectorStore
        >>> from semantic_core.infrastructure.text_processing import (
        ...     SimpleSplitter,
        ...     BasicContextStrategy,
        ... )
        >>>
        >>> embedder = GeminiEmbedder(api_key="...")
        >>> store = PeeweeVectorStore(database=db)
        >>> splitter = SimpleSplitter()
        >>> context = BasicContextStrategy()
        >>>
        >>> core = SemanticCore(
        ...     embedder=embedder,
        ...     store=store,
        ...     splitter=splitter,
        ...     context_strategy=context,
        ... )
        >>>
        >>> doc = Document(content="Текст", metadata={"title": "Тест"})
        >>> core.ingest(doc)
        >>> results = core.search("запрос")
    """

    def __init__(
        self,
        embedder: BaseEmbedder,
        store: BaseVectorStore,
        splitter: BaseSplitter,
        context_strategy: BaseContextStrategy,
    ):
        """Инициализация оркестратора.

        Args:
            embedder: Генератор эмбеддингов.
            store: Хранилище векторов.
            splitter: Сплиттер документов.
            context_strategy: Стратегия формирования контекста.
        """
        self.embedder = embedder
        self.store = store
        self.splitter = splitter
        self.context_strategy = context_strategy

    def ingest(self, document: Document) -> Document:
        """Обрабатывает и сохраняет документ.

        Алгоритм:
        1. Нарезает документ на чанки (splitter.split).
        2. Формирует контекст для каждого чанка (context_strategy).
        3. Генерирует эмбеддинги (embedder.embed_documents).
        4. Записывает векторы в чанки.
        5. Сохраняет документ с чанками (store.save).

        Args:
            document: Исходный документ.

        Returns:
            Document с заполненным id.

        Raises:
            ValueError: Если данные некорректны.
            RuntimeError: Если произошла ошибка.
        """
        # 1. Нарезаем на чанки
        chunks = self.splitter.split(document)

        if not chunks:
            raise ValueError("Сплиттер вернул пустой список чанков")

        # 2. Формируем тексты для векторизации
        vector_texts = []
        for chunk in chunks:
            text = self.context_strategy.form_vector_text(chunk, document)
            vector_texts.append(text)

        # 3. Генерируем эмбеддинги
        embeddings = self.embedder.embed_documents(vector_texts)

        # 4. Записываем векторы в чанки
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding

        # 5. Сохраняем в БД
        saved_document = self.store.save(document, chunks)

        return saved_document

    def search(
        self,
        query: str,
        filters: Optional[dict] = None,
        limit: int = 10,
        mode: str = "hybrid",
        k: int = 60,
    ) -> list[SearchResult]:
        """Выполняет поиск документов.

        Args:
            query: Поисковый запрос.
            filters: Фильтры по метаданным.
            limit: Максимальное количество результатов.
            mode: Режим поиска ('vector', 'fts', 'hybrid').
            k: Константа для RRF алгоритма (по умолчанию 60).

        Returns:
            Список SearchResult с документами и скорами.

        Raises:
            ValueError: Если query пустой.
        """
        if not query or not query.strip():
            raise ValueError("Запрос не может быть пустым")

        # Генерируем вектор для поиска (для vector/hybrid режимов)
        query_vector = None
        if mode in ("vector", "hybrid"):
            query_vector = self.embedder.embed_query(query)

        # Выполняем поиск
        results = self.store.search(
            query_vector=query_vector,
            query_text=query if mode in ("fts", "hybrid") else None,
            filters=filters,
            limit=limit,
            mode=mode,
            k=k,
        )

        return results

    def delete(self, document_id: int) -> int:
        """Удаляет документ и все его чанки.

        Args:
            document_id: ID документа.

        Returns:
            Количество удалённых строк.
        """
        return self.store.delete(document_id)

    def delete_by_metadata(self, filters: dict) -> int:
        """Удаляет чанки по фильтрам метаданных.

        Используется для удаления всех чанков, связанных с объектом
        перед переиндексацией (например, при обновлении).

        Args:
            filters: Словарь фильтров по метаданным (например, {"source_id": "123"}).

        Returns:
            Количество удалённых чанков.
        """
        return self.store.delete_by_metadata(filters)
