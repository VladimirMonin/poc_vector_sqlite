"""Тесты Phase 2: Storage Layer (Peewee + RRF + Filters).

Проверяет:
- Parent-Child архитектуру (Document → Chunks).
- Векторный поиск через sqlite-vec.
- FTS5 полнотекстовый поиск.
- Гибридный поиск (RRF).
- Фильтрация по метаданным.
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from semantic_core.domain import Document, Chunk, MatchType
from semantic_core.infrastructure.storage import (
    PeeweeVectorStore,
    init_peewee_database,
)


class TestParentChildArchitecture:
    """Тесты Parent-Child связи между Document и Chunk."""

    @pytest.fixture
    def store(self):
        """Временное хранилище для тестов."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = init_peewee_database(db_path)
            yield PeeweeVectorStore(db)

    def test_save_document_with_chunks(self, store):
        """Проверка сохранения документа с чанками."""
        doc = Document(
            content="Полный текст документа",
            metadata={"title": "Тестовый документ", "category": "Python"},
        )

        # Создаём чанки с векторами
        chunks = [
            Chunk(
                content="Первый фрагмент",
                chunk_index=0,
                embedding=np.random.rand(768).astype(np.float32),
            ),
            Chunk(
                content="Второй фрагмент",
                chunk_index=1,
                embedding=np.random.rand(768).astype(np.float32),
            ),
        ]

        # Сохраняем
        saved_doc = store.save(doc, chunks)

        assert saved_doc.id is not None
        assert saved_doc.id > 0
        assert all(c.parent_doc_id == saved_doc.id for c in chunks)
        assert all(c.id is not None for c in chunks)

    def test_delete_document_cascades_chunks(self, store):
        """Проверка каскадного удаления чанков."""
        doc = Document(content="Текст", metadata={"title": "Del"})
        chunks = [
            Chunk(
                content="Chunk 1",
                chunk_index=0,
                embedding=np.random.rand(768).astype(np.float32),
            ),
        ]

        saved = store.save(doc, chunks)
        deleted = store.delete(saved.id)

        assert deleted == 1

        # Проверяем, что чанки тоже удалены
        from semantic_core.infrastructure.storage.peewee.models import ChunkModel

        chunk_count = ChunkModel.select().where(ChunkModel.document == saved.id).count()
        assert chunk_count == 0


class TestVectorSearch:
    """Тесты векторного поиска через sqlite-vec."""

    @pytest.fixture
    def store_with_data(self):
        """Хранилище с тестовыми данными."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = init_peewee_database(db_path)
            store = PeeweeVectorStore(db)

            # Добавляем документы
            doc1 = Document(
                content="Python — язык программирования",
                metadata={"title": "Python", "category": "Programming"},
            )
            doc2 = Document(
                content="JavaScript для веб-разработки",
                metadata={"title": "JS", "category": "Web"},
            )

            # Фиксированные векторы для предсказуемости
            vec1 = np.array([1.0] + [0.0] * 767, dtype=np.float32)
            vec2 = np.array([0.0, 1.0] + [0.0] * 766, dtype=np.float32)

            chunks1 = [Chunk(content=doc1.content, chunk_index=0, embedding=vec1)]
            chunks2 = [Chunk(content=doc2.content, chunk_index=0, embedding=vec2)]

            store.save(doc1, chunks1)
            store.save(doc2, chunks2)

            yield store

    def test_vector_search_basic(self, store_with_data):
        """Проверка базового векторного поиска."""
        query_vec = np.array([1.0] + [0.0] * 767, dtype=np.float32)

        results = store_with_data.search(
            query_vector=query_vec,
            limit=5,
            mode="vector",
        )

        assert len(results) > 0
        assert results[0].match_type == MatchType.VECTOR
        assert results[0].document.metadata["title"] == "Python"

    def test_vector_search_with_filters(self, store_with_data):
        """Проверка векторного поиска с фильтрами."""
        query_vec = np.random.rand(768).astype(np.float32)

        results = store_with_data.search(
            query_vector=query_vec,
            filters={"category": "Web"},
            limit=5,
            mode="vector",
        )

        assert all(r.document.metadata["category"] == "Web" for r in results)


class TestFTSSearch:
    """Тесты полнотекстового поиска через FTS5."""

    @pytest.fixture
    def store_with_data(self):
        """Хранилище с тестовыми данными."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = init_peewee_database(db_path)
            store = PeeweeVectorStore(db)

            doc1 = Document(
                content="Python для машинного обучения",
                metadata={"title": "ML", "category": "AI"},
            )
            doc2 = Document(
                content="JavaScript для веб-приложений",
                metadata={"title": "Web", "category": "Frontend"},
            )

            # Для FTS векторы не обязательны
            chunks1 = [
                Chunk(
                    content=doc1.content,
                    chunk_index=0,
                    embedding=np.random.rand(768).astype(np.float32),
                )
            ]
            chunks2 = [
                Chunk(
                    content=doc2.content,
                    chunk_index=0,
                    embedding=np.random.rand(768).astype(np.float32),
                )
            ]

            store.save(doc1, chunks1)
            store.save(doc2, chunks2)

            yield store

    def test_fts_search_basic(self, store_with_data):
        """Проверка базового FTS поиска."""
        results = store_with_data.search(
            query_text="Python",
            limit=5,
            mode="fts",
        )

        assert len(results) > 0
        assert results[0].match_type == MatchType.FTS
        assert "Python" in results[0].document.content

    def test_fts_search_with_filters(self, store_with_data):
        """Проверка FTS поиска с фильтрами."""
        results = store_with_data.search(
            query_text="для",
            filters={"category": "AI"},
            limit=5,
            mode="fts",
        )

        assert all(r.document.metadata["category"] == "AI" for r in results)


class TestHybridSearchRRF:
    """Тесты гибридного поиска с RRF алгоритмом."""

    @pytest.fixture
    def store_with_data(self):
        """Хранилище с данными для RRF тестов."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = init_peewee_database(db_path)
            store = PeeweeVectorStore(db)

            # Документ 1: хорошо для вектора И FTS
            doc1 = Document(
                content="Python скрипт для анализа данных",
                metadata={"title": "Script", "priority": "high"},
            )

            # Документ 2: хорошо только для FTS
            doc2 = Document(
                content="Срочный скрипт обработки",
                metadata={"title": "Urgent", "priority": "critical"},
            )

            # Документ 3: хорошо только для вектора
            doc3 = Document(
                content="Код на языке программирования",
                metadata={"title": "Code", "priority": "low"},
            )

            # Векторы: doc1 и doc3 близки, doc2 далеко
            vec1 = np.array([1.0, 0.5] + [0.0] * 766, dtype=np.float32)
            vec2 = np.array([0.0, 0.0, 1.0] + [0.0] * 765, dtype=np.float32)
            vec3 = np.array([0.9, 0.6] + [0.0] * 766, dtype=np.float32)

            chunks1 = [Chunk(content=doc1.content, chunk_index=0, embedding=vec1)]
            chunks2 = [Chunk(content=doc2.content, chunk_index=0, embedding=vec2)]
            chunks3 = [Chunk(content=doc3.content, chunk_index=0, embedding=vec3)]

            store.save(doc1, chunks1)
            store.save(doc2, chunks2)
            store.save(doc3, chunks3)

            yield store

    def test_hybrid_search_basic(self, store_with_data):
        """Проверка базового гибридного поиска."""
        query_vec = np.array([1.0, 0.5] + [0.0] * 766, dtype=np.float32)

        results = store_with_data.search(
            query_vector=query_vec,
            query_text="скрипт",
            limit=5,
            mode="hybrid",
        )

        assert len(results) > 0
        assert results[0].match_type == MatchType.HYBRID

        # Документ со словом "скрипт" + близкий вектор должен быть выше
        titles = [r.document.metadata["title"] for r in results]
        assert "Script" in titles or "Urgent" in titles

    def test_hybrid_search_with_filters(self, store_with_data):
        """Проверка гибридного поиска с фильтрами."""
        query_vec = np.random.rand(768).astype(np.float32)

        results = store_with_data.search(
            query_vector=query_vec,
            query_text="скрипт",
            filters={"priority": "critical"},
            limit=5,
            mode="hybrid",
        )

        assert all(r.document.metadata["priority"] == "critical" for r in results)

    def test_hybrid_search_rrf_k_parameter(self, store_with_data):
        """Проверка параметра k в RRF алгоритме."""
        query_vec = np.array([1.0, 0.5] + [0.0] * 766, dtype=np.float32)

        # k=60 (стандарт)
        results1 = store_with_data.search(
            query_vector=query_vec,
            query_text="скрипт",
            k=60,
            limit=5,
            mode="hybrid",
        )

        # k=10 (сильнее влияет ранг)
        results2 = store_with_data.search(
            query_vector=query_vec,
            query_text="скрипт",
            k=10,
            limit=5,
            mode="hybrid",
        )

        # Результаты могут отличаться из-за разных RRF скоров
        assert len(results1) > 0
        assert len(results2) > 0

    def test_hybrid_search_vector_only_fallback(self, store_with_data):
        """Проверка fallback на векторный поиск если нет текста."""
        query_vec = np.array([1.0, 0.5] + [0.0] * 766, dtype=np.float32)

        results = store_with_data.search(
            query_vector=query_vec,
            query_text=None,
            limit=5,
            mode="hybrid",
        )

        assert len(results) > 0
        # Должен использовать векторный поиск
        assert results[0].match_type == MatchType.VECTOR

    def test_hybrid_search_fts_only_fallback(self, store_with_data):
        """Проверка fallback на FTS поиск если нет вектора."""
        results = store_with_data.search(
            query_vector=None,
            query_text="скрипт",
            limit=5,
            mode="hybrid",
        )

        assert len(results) > 0
        # Должен использовать FTS поиск
        assert results[0].match_type == MatchType.FTS


class TestMetadataFilters:
    """Тесты фильтрации по метаданным."""

    @pytest.fixture
    def store_with_data(self):
        """Хранилище с разнообразными метаданными."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = init_peewee_database(db_path)
            store = PeeweeVectorStore(db)

            docs = [
                Document(
                    content=f"Документ {i}",
                    metadata={
                        "category": "AI" if i % 2 == 0 else "Web",
                        "year": 2024 if i < 3 else 2023,
                        "author": "Alice" if i % 3 == 0 else "Bob",
                    },
                )
                for i in range(6)
            ]

            for doc in docs:
                chunks = [
                    Chunk(
                        content=doc.content,
                        chunk_index=0,
                        embedding=np.random.rand(768).astype(np.float32),
                    )
                ]
                store.save(doc, chunks)

            yield store

    def test_filter_by_single_field(self, store_with_data):
        """Проверка фильтрации по одному полю."""
        query_vec = np.random.rand(768).astype(np.float32)

        results = store_with_data.search(
            query_vector=query_vec,
            filters={"category": "AI"},
            limit=10,
            mode="vector",
        )

        assert all(r.document.metadata["category"] == "AI" for r in results)

    def test_filter_by_multiple_fields(self, store_with_data):
        """Проверка фильтрации по нескольким полям."""
        query_vec = np.random.rand(768).astype(np.float32)

        results = store_with_data.search(
            query_vector=query_vec,
            filters={"category": "AI", "year": 2024},
            limit=10,
            mode="vector",
        )

        assert all(r.document.metadata["category"] == "AI" for r in results)
        assert all(r.document.metadata["year"] == 2024 for r in results)

    def test_filter_by_author(self, store_with_data):
        """Проверка фильтрации по автору."""
        results = store_with_data.search(
            query_text="Документ",
            filters={"author": "Alice"},
            limit=10,
            mode="fts",
        )

        assert all(r.document.metadata["author"] == "Alice" for r in results)
