"""Тесты новой SOLID архитектуры (Фаза 1).

Проверяет:
- Domain Layer (DTO)
- Interfaces Layer (ABC)
- Infrastructure Layer (реализации)
- Pipeline Layer (SemanticCore)
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from semantic_core.domain import Document, Chunk, SearchResult, MediaType, MatchType
from semantic_core.infrastructure.gemini import GeminiEmbedder
from semantic_core.infrastructure.storage import (
    PeeweeVectorStore,
    init_peewee_database,
)
from semantic_core.infrastructure.text_processing import (
    SimpleSplitter,
    BasicContextStrategy,
)
from semantic_core.pipeline import SemanticCore


class TestDomainLayer:
    """Тесты чистых DTO без зависимостей."""

    def test_document_creation(self):
        """Проверка создания Document."""
        doc = Document(
            content="Тестовый текст",
            metadata={"title": "Тест", "author": "AI"},
            media_type=MediaType.TEXT,
        )

        assert doc.content == "Тестовый текст"
        assert doc.metadata["title"] == "Тест"
        assert doc.media_type == MediaType.TEXT
        assert doc.id is None  # До сохранения

    def test_chunk_creation(self):
        """Проверка создания Chunk."""
        chunk = Chunk(
            content="Фрагмент текста",
            chunk_index=0,
            parent_doc_id=1,
        )

        assert chunk.content == "Фрагмент текста"
        assert chunk.chunk_index == 0
        assert chunk.embedding is None  # До векторизации

    def test_search_result_creation(self):
        """Проверка создания SearchResult."""
        doc = Document(content="Текст", metadata={"title": "Тест"})
        result = SearchResult(
            document=doc,
            score=0.95,
            match_type=MatchType.VECTOR,
        )

        assert result.score == 0.95
        assert result.match_type == MatchType.VECTOR
        assert result.document.metadata["title"] == "Тест"


class TestInfrastructureLayer:
    """Тесты реализаций компонентов."""

    def test_simple_splitter(self):
        """Проверка SimpleSplitter."""
        doc = Document(
            content="A" * 500 + "\n" + "B" * 500 + "\n" + "C" * 500,
            metadata={"title": "Test"},
        )

        splitter = SimpleSplitter(chunk_size=600, overlap=100)
        chunks = splitter.split(doc)

        assert len(chunks) > 1
        assert all(isinstance(c, Chunk) for c in chunks)
        assert all(c.embedding is None for c in chunks)
        assert chunks[0].chunk_index == 0
        assert chunks[1].chunk_index == 1

    def test_basic_context_strategy(self):
        """Проверка BasicContextStrategy."""
        doc = Document(
            content="Основной текст",
            metadata={"title": "Заголовок", "category": "Python"},
        )
        chunk = Chunk(content="Фрагмент", chunk_index=0)

        strategy = BasicContextStrategy()
        vector_text = strategy.form_vector_text(chunk, doc)

        assert "Заголовок" in vector_text
        assert "Python" in vector_text
        assert "Фрагмент" in vector_text

    def test_peewee_vector_store_init(self):
        """Проверка инициализации PeeweeVectorStore."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = init_peewee_database(db_path)
            store = PeeweeVectorStore(db)

            # Проверяем, что таблицы созданы
            tables = db.get_tables()
            assert "documents" in tables
            assert "chunks" in tables


@pytest.mark.skipif(
    not Path(".env").exists(),
    reason="Требуется .env с GEMINI_API_KEY для реальных тестов",
)
class TestGeminiIntegration:
    """Интеграционные тесты с реальным Gemini API (опционально)."""

    def test_gemini_embedder(self):
        """Проверка GeminiEmbedder с реальным API."""
        from config import settings

        embedder = GeminiEmbedder(api_key=settings.gemini_api_key)

        # Тест embed_documents
        vectors = embedder.embed_documents(["Тест 1", "Тест 2"])
        assert len(vectors) == 2
        assert all(isinstance(v, np.ndarray) for v in vectors)
        assert all(v.shape == (768,) for v in vectors)

        # Тест embed_query
        query_vec = embedder.embed_query("Запрос")
        assert isinstance(query_vec, np.ndarray)
        assert query_vec.shape == (768,)


class TestPipelineIntegration:
    """Интеграционные тесты полного пайплайна."""

    @pytest.fixture
    def mock_embedder(self):
        """Мок эмбеддера для тестов без API."""

        class MockEmbedder:
            def embed_documents(self, texts):
                return [np.random.rand(768).astype(np.float32) for _ in texts]

            def embed_query(self, text):
                return np.random.rand(768).astype(np.float32)

        return MockEmbedder()

    @pytest.fixture
    def test_store(self):
        """Временное хранилище для тестов."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = init_peewee_database(db_path)
            yield PeeweeVectorStore(db)

    def test_semantic_core_ingest(self, mock_embedder, test_store):
        """Проверка метода ingest."""
        core = SemanticCore(
            embedder=mock_embedder,
            store=test_store,
            splitter=SimpleSplitter(chunk_size=500, overlap=100),
            context_strategy=BasicContextStrategy(),
        )

        doc = Document(
            content="A" * 1000 + "\n" + "B" * 1000,
            metadata={"title": "Тестовый документ"},
        )

        saved_doc = core.ingest(doc)

        assert saved_doc.id is not None
        assert saved_doc.id > 0

    def test_semantic_core_search(self, mock_embedder, test_store):
        """Проверка метода search."""
        core = SemanticCore(
            embedder=mock_embedder,
            store=test_store,
            splitter=SimpleSplitter(chunk_size=500, overlap=100),
            context_strategy=BasicContextStrategy(),
        )

        # Добавляем документ
        doc = Document(
            content="Python — язык программирования для ML и AI",
            metadata={"title": "Python AI"},
        )
        core.ingest(doc)

        # Поиск
        results = core.search("машинное обучение", limit=5, mode="vector")

        assert isinstance(results, list)
        # Может быть пустым из-за случайных векторов, но не должен падать

    def test_semantic_core_delete(self, mock_embedder, test_store):
        """Проверка метода delete."""
        core = SemanticCore(
            embedder=mock_embedder,
            store=test_store,
            splitter=SimpleSplitter(),
            context_strategy=BasicContextStrategy(),
        )

        doc = Document(content="Текст для удаления", metadata={"title": "Del"})
        saved = core.ingest(doc)

        deleted = core.delete(saved.id)
        assert deleted == 1


class TestSOLIDPrinciples:
    """Проверка соблюдения SOLID принципов."""

    def test_dependency_injection(self, tmp_path):
        """Проверка, что SemanticCore принимает зависимости."""
        from semantic_core.interfaces import (
            BaseEmbedder,
            BaseVectorStore,
            BaseSplitter,
            BaseContextStrategy,
        )

        # Мок-реализации
        class FakeEmbedder(BaseEmbedder):
            def embed_documents(self, texts):
                return [np.zeros(768, dtype=np.float32) for _ in texts]

            def embed_query(self, text):
                return np.zeros(768, dtype=np.float32)

        class FakeSplitter(BaseSplitter):
            def split(self, document):
                return [Chunk(content=document.content, chunk_index=0)]

        class FakeStrategy(BaseContextStrategy):
            def form_vector_text(self, chunk, document):
                return chunk.content

        db = init_peewee_database(tmp_path / "test.db")
        store = PeeweeVectorStore(db)

        # Создаём ядро с фейковыми зависимостями
        core = SemanticCore(
            embedder=FakeEmbedder(),
            store=store,
            splitter=FakeSplitter(),
            context_strategy=FakeStrategy(),
        )

        # Должно работать
        doc = Document(content="Test", metadata={})
        saved = core.ingest(doc)
        assert saved.id is not None

    def test_interface_segregation(self):
        """Проверка, что интерфейсы минимальны и сфокусированы."""
        from semantic_core.interfaces import BaseEmbedder, BaseVectorStore

        # BaseEmbedder имеет только 2 метода
        embedder_methods = [
            m
            for m in dir(BaseEmbedder)
            if not m.startswith("_") and callable(getattr(BaseEmbedder, m))
        ]
        assert len(embedder_methods) == 2

        # BaseVectorStore имеет 6 методов (save, search, delete, delete_by_metadata, search_chunks, bulk_update_vectors)
        store_methods = [
            m
            for m in dir(BaseVectorStore)
            if not m.startswith("_") and callable(getattr(BaseVectorStore, m))
        ]
        assert len(store_methods) == 6
