"""Semantic Core - библиотека для локального семантического поиска.

Архитектура:
    Domain: Чистые DTO (Document, Chunk, SearchResult).
    Interfaces: Контракты (BaseEmbedder, BaseVectorStore, etc.).
    Infrastructure: Реализации (GeminiEmbedder, PeeweeVectorStore, etc.).
    Pipeline: Оркестратор (SemanticCore).

Пример:
    >>> from semantic_core import SemanticCore
    >>> from semantic_core.domain import Document
    >>> from semantic_core.infrastructure.gemini import GeminiEmbedder
    >>> from semantic_core.infrastructure.storage import (
    ...     PeeweeVectorStore,
    ...     init_peewee_database,
    ... )
    >>> from semantic_core.infrastructure.text_processing import (
    ...     SimpleSplitter,
    ...     BasicContextStrategy,
    ... )
    >>>
    >>> # Настройка компонентов
    >>> db = init_peewee_database("data.db")
    >>> embedder = GeminiEmbedder(api_key="...")
    >>> store = PeeweeVectorStore(db)
    >>> splitter = SimpleSplitter()
    >>> context = BasicContextStrategy()
    >>>
    >>> # Создание ядра
    >>> core = SemanticCore(
    ...     embedder=embedder,
    ...     store=store,
    ...     splitter=splitter,
    ...     context_strategy=context,
    ... )
    >>>
    >>> # Использование
    >>> doc = Document(content="Текст", metadata={"title": "Тест"})
    >>> core.ingest(doc)
    >>> results = core.search("запрос")
"""

# Domain Layer
from semantic_core.domain import (
    Document,
    Chunk,
    SearchResult,
    MediaType,
    MatchType,
)

# Interfaces Layer
from semantic_core.interfaces import (
    BaseEmbedder,
    BaseVectorStore,
    BaseSplitter,
    BaseContextStrategy,
)

# Infrastructure Layer
from semantic_core.infrastructure.gemini import GeminiEmbedder
from semantic_core.infrastructure.storage import (
    PeeweeVectorStore,
    init_peewee_database,
)
from semantic_core.infrastructure.text_processing import (
    SimpleSplitter,
    BasicContextStrategy,
)

# Pipeline Layer
from semantic_core.pipeline import SemanticCore

__all__ = [
    # Domain
    "Document",
    "Chunk",
    "SearchResult",
    "MediaType",
    "MatchType",
    # Interfaces
    "BaseEmbedder",
    "BaseVectorStore",
    "BaseSplitter",
    "BaseContextStrategy",
    # Infrastructure: Gemini
    "GeminiEmbedder",
    # Infrastructure: Storage
    "PeeweeVectorStore",
    "init_peewee_database",
    # Infrastructure: Text Processing
    "SimpleSplitter",
    "BasicContextStrategy",
    # Pipeline
    "SemanticCore",
]
