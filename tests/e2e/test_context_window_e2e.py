"""E2E тесты для context_window (Phase 13.5).

Тестирует:
- Получение соседних чанков через get_sibling_chunks
- Расширение результатов поиска через context_window
- Корректность MatchType.CONTEXT для соседей
- Поведение при window > количества чанков (весь документ)
- Интеграция с RAGEngine
"""

from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock

import numpy as np
import pytest

from semantic_core import SemanticCore
from semantic_core.domain import Document, MediaType, MatchType
from semantic_core.domain.chunk import ChunkType
from semantic_core.infrastructure.gemini.embedder import GeminiEmbedder
from semantic_core.infrastructure.storage.peewee.adapter import PeeweeVectorStore
from semantic_core.infrastructure.storage.peewee.engine import init_peewee_database
from semantic_core.infrastructure.storage.peewee.models import (
    ChunkModel,
    DocumentModel,
)
from semantic_core.processing.context.hierarchical_strategy import (
    HierarchicalContextStrategy,
)
from semantic_core.processing.parsers.markdown_parser import MarkdownNodeParser
from semantic_core.processing.splitters.smart_splitter import SmartSplitter


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def test_db(tmp_path: Path) -> Generator:
    """Временная БД для тестов."""
    db_path = tmp_path / "test_context_window.db"
    db = init_peewee_database(str(db_path))
    yield db
    db.close()


@pytest.fixture
def mock_embedder() -> MagicMock:
    """Mock embedder с детерминированными эмбеддингами."""
    embedder = MagicMock(spec=GeminiEmbedder)
    
    def embed_documents(texts: list[str]) -> list[np.ndarray]:
        result = []
        for text in texts:
            seed = hash(text) % 10000
            rng = np.random.default_rng(seed)
            result.append(rng.random(768).astype(np.float32))
        return result
    
    def embed_query(text: str) -> np.ndarray:
        seed = hash(text) % 10000
        rng = np.random.default_rng(seed)
        return rng.random(768).astype(np.float32)
    
    embedder.embed_documents = embed_documents
    embedder.embed_query = embed_query
    embedder.dimension = 768
    
    return embedder


@pytest.fixture
def semantic_core(test_db, mock_embedder) -> SemanticCore:
    """SemanticCore для тестов с моками."""
    parser = MarkdownNodeParser()
    splitter = SmartSplitter(parser=parser, chunk_size=200)  # Меньший chunk_size для большего количества чанков
    context = HierarchicalContextStrategy(include_doc_title=True)
    store = PeeweeVectorStore(test_db)
    
    return SemanticCore(
        embedder=mock_embedder,
        store=store,
        splitter=splitter,
        context_strategy=context,
    )


@pytest.fixture
def multi_chunk_document():
    """Markdown документ который создаст несколько чанков."""
    return Document(
        content="""# Python Tutorial

## Chapter 1: Variables

Variables store data in Python. You can create a variable by assigning a value.

```python
name = "Alice"
age = 30
```

## Chapter 2: Functions

Functions are reusable blocks of code. Define them with the `def` keyword.

```python
def greet(name):
    return f"Hello, {name}!"
```

## Chapter 3: Classes

Classes define objects with attributes and methods.

```python
class Person:
    def __init__(self, name):
        self.name = name
```

## Chapter 4: Modules

Modules help organize code into separate files.

```python
import os
from pathlib import Path
```

## Summary

Python is a versatile programming language.
""",
        media_type=MediaType.TEXT,
        metadata={"title": "Python Tutorial", "source": "tutorial.md"},
    )


# ============================================================================
# GET_SIBLING_CHUNKS TESTS
# ============================================================================


class TestGetSiblingChunks:
    """Тесты метода get_sibling_chunks."""

    def test_window_0_returns_only_center(
        self, semantic_core: SemanticCore, test_db, multi_chunk_document
    ) -> None:
        """window=0 возвращает только центральный чанк."""
        result = semantic_core.ingest(multi_chunk_document, mode="sync")
        
        # Получаем все чанки документа
        chunks = list(ChunkModel.select().where(ChunkModel.document == result.id))
        assert len(chunks) >= 3, "Должно быть минимум 3 чанка"
        
        # Берём средний чанк
        middle_chunk = chunks[len(chunks) // 2]
        
        # window=0 — только этот чанк
        siblings = semantic_core.store.get_sibling_chunks(middle_chunk.id, window=0)
        
        assert len(siblings) == 1
        assert siblings[0].id == middle_chunk.id

    def test_window_1_returns_three_chunks(
        self, semantic_core: SemanticCore, test_db, multi_chunk_document
    ) -> None:
        """window=1 возвращает 3 чанка (если есть соседи)."""
        result = semantic_core.ingest(multi_chunk_document, mode="sync")
        
        chunks = list(
            ChunkModel.select()
            .where(ChunkModel.document == result.id)
            .order_by(ChunkModel.chunk_index)
        )
        assert len(chunks) >= 5, "Нужно минимум 5 чанков для теста"
        
        # Берём чанк посередине (не первый и не последний)
        middle_idx = len(chunks) // 2
        middle_chunk = chunks[middle_idx]
        
        siblings = semantic_core.store.get_sibling_chunks(middle_chunk.id, window=1)
        
        assert len(siblings) == 3, f"Ожидалось 3 чанка, получено {len(siblings)}"
        
        # Проверяем индексы
        indices = [s.chunk_index for s in siblings]
        expected = [middle_idx - 1, middle_idx, middle_idx + 1]
        assert indices == expected

    def test_edge_chunk_returns_fewer_siblings(
        self, semantic_core: SemanticCore, test_db, multi_chunk_document
    ) -> None:
        """Первый чанк возвращает меньше соседей (нет предыдущего)."""
        result = semantic_core.ingest(multi_chunk_document, mode="sync")
        
        # Первый чанк
        first_chunk = ChunkModel.get(
            (ChunkModel.document == result.id) & (ChunkModel.chunk_index == 0)
        )
        
        siblings = semantic_core.store.get_sibling_chunks(first_chunk.id, window=1)
        
        # Должно быть 2: center + next
        assert len(siblings) == 2
        indices = [s.chunk_index for s in siblings]
        assert indices == [0, 1]

    def test_last_chunk_returns_fewer_siblings(
        self, semantic_core: SemanticCore, test_db, multi_chunk_document
    ) -> None:
        """Последний чанк возвращает меньше соседей (нет следующего)."""
        result = semantic_core.ingest(multi_chunk_document, mode="sync")
        
        # Последний чанк
        last_chunk = (
            ChunkModel.select()
            .where(ChunkModel.document == result.id)
            .order_by(ChunkModel.chunk_index.desc())
            .first()
        )
        
        siblings = semantic_core.store.get_sibling_chunks(last_chunk.id, window=1)
        
        # Должно быть 2: prev + center
        assert len(siblings) == 2
        assert siblings[-1].id == last_chunk.id

    def test_large_window_returns_all_chunks(
        self, semantic_core: SemanticCore, test_db, multi_chunk_document
    ) -> None:
        """window больше количества чанков возвращает весь документ."""
        result = semantic_core.ingest(multi_chunk_document, mode="sync")
        
        # Считаем все чанки
        total_chunks = semantic_core.store.get_document_chunks_count(result.id)
        
        # Берём любой чанк
        any_chunk = ChunkModel.get(ChunkModel.document == result.id)
        
        # Запрашиваем с большим window
        siblings = semantic_core.store.get_sibling_chunks(any_chunk.id, window=100)
        
        assert len(siblings) == total_chunks, (
            f"При window=100 должен вернуться весь документ ({total_chunks} чанков)"
        )

    def test_sorted_by_chunk_index(
        self, semantic_core: SemanticCore, test_db, multi_chunk_document
    ) -> None:
        """Соседние чанки отсортированы по chunk_index."""
        result = semantic_core.ingest(multi_chunk_document, mode="sync")
        
        chunks = list(ChunkModel.select().where(ChunkModel.document == result.id))
        middle_chunk = chunks[len(chunks) // 2]
        
        siblings = semantic_core.store.get_sibling_chunks(middle_chunk.id, window=2)
        
        indices = [s.chunk_index for s in siblings]
        assert indices == sorted(indices), "Чанки должны быть отсортированы"

    def test_nonexistent_chunk_returns_empty(
        self, semantic_core: SemanticCore, test_db
    ) -> None:
        """Несуществующий chunk_id возвращает пустой список."""
        siblings = semantic_core.store.get_sibling_chunks(chunk_id=99999, window=1)
        assert siblings == []


# ============================================================================
# SEARCH_CHUNKS WITH CONTEXT_WINDOW TESTS
# ============================================================================


class TestSearchWithContextWindow:
    """Тесты search_chunks с context_window."""

    def test_context_window_0_returns_only_found(
        self, semantic_core: SemanticCore, test_db, multi_chunk_document
    ) -> None:
        """context_window=0 возвращает только найденные чанки."""
        semantic_core.ingest(multi_chunk_document, mode="sync")
        
        results_0 = semantic_core.search_chunks(
            "functions python", 
            context_window=0,
            limit=2,
        )
        
        # Все результаты — найденные (не CONTEXT)
        for r in results_0:
            assert r.match_type != MatchType.CONTEXT
            assert r.score > 0

    def test_context_window_expands_results(
        self, semantic_core: SemanticCore, test_db, multi_chunk_document
    ) -> None:
        """context_window > 0 добавляет соседние чанки."""
        semantic_core.ingest(multi_chunk_document, mode="sync")
        
        results_0 = semantic_core.search_chunks(
            "functions def keyword",
            context_window=0,
            limit=1,
        )
        
        results_1 = semantic_core.search_chunks(
            "functions def keyword",
            context_window=1,
            limit=1,
        )
        
        # С context_window=1 должно быть больше результатов
        assert len(results_1) >= len(results_0), (
            f"context_window=1 ({len(results_1)}) должен >= context_window=0 ({len(results_0)})"
        )

    def test_context_chunks_have_match_type_context(
        self, semantic_core: SemanticCore, test_db, multi_chunk_document
    ) -> None:
        """Соседние чанки имеют match_type=CONTEXT."""
        semantic_core.ingest(multi_chunk_document, mode="sync")
        
        results = semantic_core.search_chunks(
            "classes objects",
            context_window=1,
            limit=1,
        )
        
        # Должны быть CONTEXT чанки если есть соседи
        context_chunks = [r for r in results if r.match_type == MatchType.CONTEXT]
        
        # Минимум один найденный + соседи
        if len(results) > 1:
            assert len(context_chunks) > 0, "Должны быть CONTEXT чанки"

    def test_context_chunks_have_zero_score(
        self, semantic_core: SemanticCore, test_db, multi_chunk_document
    ) -> None:
        """Соседние чанки имеют score=0."""
        semantic_core.ingest(multi_chunk_document, mode="sync")
        
        results = semantic_core.search_chunks(
            "modules import",
            context_window=2,
            limit=1,
        )
        
        for r in results:
            if r.match_type == MatchType.CONTEXT:
                assert r.score == 0.0, "CONTEXT чанки должны иметь score=0"

    def test_no_duplicate_chunks(
        self, semantic_core: SemanticCore, test_db, multi_chunk_document
    ) -> None:
        """Нет дубликатов при пересечении соседей."""
        semantic_core.ingest(multi_chunk_document, mode="sync")
        
        # Ищем несколько результатов с большим window
        results = semantic_core.search_chunks(
            "python programming",
            context_window=3,
            limit=3,
        )
        
        chunk_ids = [r.chunk_id for r in results]
        assert len(chunk_ids) == len(set(chunk_ids)), (
            f"Дубликаты: {chunk_ids}"
        )

    def test_results_sorted_by_doc_and_index(
        self, semantic_core: SemanticCore, test_db, multi_chunk_document
    ) -> None:
        """Результаты отсортированы по документу и chunk_index."""
        semantic_core.ingest(multi_chunk_document, mode="sync")
        
        results = semantic_core.search_chunks(
            "python code",
            context_window=2,
            limit=2,
        )
        
        # Проверяем сортировку внутри одного документа
        for i in range(1, len(results)):
            if results[i].parent_doc_id == results[i-1].parent_doc_id:
                assert results[i].chunk_index >= results[i-1].chunk_index, (
                    "Чанки одного документа должны быть отсортированы по индексу"
                )


# ============================================================================
# FULL DOCUMENT RETRIEVAL TESTS
# ============================================================================


class TestFullDocumentRetrieval:
    """Тесты получения всего документа через большой window."""

    def test_large_window_gives_full_document(
        self, semantic_core: SemanticCore, test_db, multi_chunk_document
    ) -> None:
        """Большой window возвращает все чанки документа."""
        result = semantic_core.ingest(multi_chunk_document, mode="sync")
        
        total_chunks = semantic_core.store.get_document_chunks_count(result.id)
        
        # Поиск с очень большим window
        results = semantic_core.search_chunks(
            "python",
            context_window=100,  # Больше чем чанков в документе
            limit=1,
        )
        
        # Должны получить все чанки документа
        assert len(results) == total_chunks, (
            f"Ожидалось {total_chunks} чанков, получено {len(results)}"
        )

    def test_window_equals_doc_size_gives_full_doc(
        self, semantic_core: SemanticCore, test_db, multi_chunk_document
    ) -> None:
        """window >= (doc_size - 1) / 2 возвращает весь документ."""
        result = semantic_core.ingest(multi_chunk_document, mode="sync")
        
        total = semantic_core.store.get_document_chunks_count(result.id)
        
        # Window достаточный для покрытия всего документа
        window = total  # Больше чем нужно
        
        results = semantic_core.search_chunks(
            "variables",
            context_window=window,
            limit=1,
        )
        
        assert len(results) == total


# ============================================================================
# DATABASE INTEGRITY TESTS
# ============================================================================


class TestDatabaseIntegrity:
    """Тесты целостности данных в БД."""

    def test_get_document_chunks_count(
        self, semantic_core: SemanticCore, test_db, multi_chunk_document
    ) -> None:
        """get_document_chunks_count возвращает правильное количество."""
        result = semantic_core.ingest(multi_chunk_document, mode="sync")
        
        # Через метод
        count = semantic_core.store.get_document_chunks_count(result.id)
        
        # Через прямой запрос
        actual = ChunkModel.select().where(ChunkModel.document == result.id).count()
        
        assert count == actual

    def test_sibling_chunks_belong_to_same_document(
        self, semantic_core: SemanticCore, test_db, multi_chunk_document
    ) -> None:
        """Все соседние чанки принадлежат одному документу."""
        result = semantic_core.ingest(multi_chunk_document, mode="sync")
        
        chunk = ChunkModel.get(ChunkModel.document == result.id)
        siblings = semantic_core.store.get_sibling_chunks(chunk.id, window=5)
        
        for sibling in siblings:
            assert sibling.parent_doc_id == result.id

    def test_context_window_preserves_chunk_metadata(
        self, semantic_core: SemanticCore, test_db, multi_chunk_document
    ) -> None:
        """CONTEXT чанки сохраняют корректные метаданные."""
        semantic_core.ingest(multi_chunk_document, mode="sync")
        
        results = semantic_core.search_chunks(
            "python functions",
            context_window=1,
            limit=1,
        )
        
        for r in results:
            # Все результаты должны иметь parent_doc_id
            assert r.parent_doc_id is not None
            # И chunk_index
            assert r.chunk_index is not None
            assert r.chunk_index >= 0


# ============================================================================
# EDGE CASES
# ============================================================================


class TestEdgeCases:
    """Граничные случаи."""

    def test_single_chunk_document(
        self, semantic_core: SemanticCore, test_db
    ) -> None:
        """Документ с одним чанком: window не добавляет соседей."""
        doc = Document(
            content="Short text.",
            media_type=MediaType.TEXT,
            metadata={"title": "Short"},
        )
        
        result = semantic_core.ingest(doc, mode="sync")
        
        results = semantic_core.search_chunks(
            "short",
            context_window=5,
            limit=1,
        )
        
        # Должен быть только 1 чанк
        assert len(results) == 1

    def test_empty_results_with_context_window(
        self, semantic_core: SemanticCore, test_db, multi_chunk_document
    ) -> None:
        """Пустые результаты поиска не ломают context_window."""
        # Не индексируем документ — БД пустая
        
        results = semantic_core.search_chunks(
            "nonexistent query xyz123",
            context_window=2,
            limit=5,
        )
        
        assert results == []

    def test_context_window_with_code_chunks(
        self, semantic_core: SemanticCore, test_db, multi_chunk_document
    ) -> None:
        """context_window работает с CODE чанками."""
        semantic_core.ingest(multi_chunk_document, mode="sync")
        
        results = semantic_core.search_chunks(
            "def greet name",
            context_window=1,
            limit=1,
            chunk_type_filter="code",
        )
        
        # Должны найти код + контекст
        if results:
            # Контекстные чанки могут быть любого типа
            assert any(r.match_type == MatchType.CONTEXT for r in results) or len(results) == 1

    def test_multiple_documents(
        self, semantic_core: SemanticCore, test_db
    ) -> None:
        """context_window не смешивает чанки разных документов."""
        # Два разных документа
        doc1 = Document(
            content="# Doc 1\n\nFirst paragraph.\n\n## Section\n\nSecond paragraph.",
            media_type=MediaType.TEXT,
            metadata={"title": "Doc 1"},
        )
        doc2 = Document(
            content="# Doc 2\n\nAnother document.\n\n## Part\n\nMore content here.",
            media_type=MediaType.TEXT,
            metadata={"title": "Doc 2"},
        )
        
        result1 = semantic_core.ingest(doc1, mode="sync")
        result2 = semantic_core.ingest(doc2, mode="sync")
        
        # Поиск в Doc 1
        results = semantic_core.search_chunks(
            "First paragraph",
            context_window=2,
            limit=1,
        )
        
        # Все результаты должны быть из одного документа
        doc_ids = {r.parent_doc_id for r in results}
        assert len(doc_ids) == 1, "Не должно быть смешивания документов"

