"""Semantic Core - библиотека для локального семантического поиска.

Архитектура:
    Domain: Чистые DTO (Document, Chunk, SearchResult).
    Interfaces: Контракты (BaseEmbedder, BaseVectorStore, etc.).
    Infrastructure: Реализации (GeminiEmbedder, PeeweeVectorStore, etc.).
    Core: Бизнес-логика (MediaQueueProcessor).
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
    ChunkType,
    SearchResult,
    ChunkResult,
    MediaType,
    MatchType,
    GoogleKeyring,
    MediaConfig,
    TaskStatus,
    MediaResource,
    MediaRequest,
    MediaAnalysisResult,
)

# Interfaces Layer
from semantic_core.interfaces import (
    BaseEmbedder,
    BaseVectorStore,
    BaseSplitter,
    BaseContextStrategy,
    DocumentParser,
    ParsingSegment,
)

# Infrastructure Layer
from semantic_core.infrastructure.gemini import (
    GeminiEmbedder,
    GeminiBatchClient,
    GeminiImageAnalyzer,
    MediaProcessingError,
    RateLimiter,
)
from semantic_core.infrastructure.storage import (
    PeeweeVectorStore,
    init_peewee_database,
)
from semantic_core.infrastructure.text_processing import (
    SimpleSplitter,
    BasicContextStrategy,
)

# Processing Layer (Phase 4)
from semantic_core.processing import (
    MarkdownNodeParser,
    SmartSplitter,
    HierarchicalContextStrategy,
)

# Core Layer (Phase 6)
from semantic_core.core import MediaQueueProcessor

# Integration Layer
from semantic_core.integrations import SemanticIndex

# Pipeline Layer
from semantic_core.pipeline import SemanticCore
from semantic_core.batch_manager import BatchManager

__all__ = [
    # Domain
    "Document",
    "Chunk",
    "ChunkType",
    "SearchResult",
    "ChunkResult",
    "MediaType",
    "MatchType",
    "GoogleKeyring",
    "MediaConfig",
    "TaskStatus",
    "MediaResource",
    "MediaRequest",
    "MediaAnalysisResult",
    # Interfaces
    "BaseEmbedder",
    "BaseVectorStore",
    "BaseSplitter",
    "BaseContextStrategy",
    "DocumentParser",
    "ParsingSegment",
    # Infrastructure: Gemini
    "GeminiEmbedder",
    "GeminiBatchClient",
    "GeminiImageAnalyzer",
    "MediaProcessingError",
    "RateLimiter",
    # Infrastructure: Storage
    "PeeweeVectorStore",
    "init_peewee_database",
    # Infrastructure: Text Processing
    "SimpleSplitter",
    "BasicContextStrategy",
    # Processing: Phase 4
    "MarkdownNodeParser",
    "SmartSplitter",
    "HierarchicalContextStrategy",
    # Core: Phase 6
    "MediaQueueProcessor",
    # Integration
    "SemanticIndex",
    # Pipeline
    "SemanticCore",
    "BatchManager",
]
