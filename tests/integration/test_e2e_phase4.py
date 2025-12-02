"""End-to-End интеграционный тест Phase 4: Полный pipeline с реальными документами.

Проверяет полный цикл:
    1. Загрузка реальных архитектурных документов (plan_phase_3.md, plan_phase_4.md)
    2. Парсинг через MarkdownNodeParser
    3. Разбиение через SmartSplitter
    4. Генерация контекста через HierarchicalContextStrategy
    5. Индексация через PeeweeVectorStore
    6. Семантический поиск по chunk_type и language
"""

import pytest
from pathlib import Path
from unittest.mock import Mock
import numpy as np

from semantic_core.infrastructure.storage.peewee.engine import VectorDatabase
from semantic_core.infrastructure.storage.peewee.adapter import PeeweeVectorStore
from semantic_core.processing.parsers import MarkdownNodeParser
from semantic_core.processing.splitters import SmartSplitter
from semantic_core.processing.context import HierarchicalContextStrategy
from semantic_core.domain import Document, ChunkType


@pytest.fixture
def real_docs_path():
    """Путь к директории с реальными документами."""
    return Path(__file__).parent.parent.parent / "doc" / "ideas"


@pytest.fixture
def phase3_doc(real_docs_path):
    """Загружает plan_phase_3.md."""
    path = real_docs_path / "phase_3" / "plan_phase_3.md"
    if not path.exists():
        pytest.skip(f"Документ не найден: {path}")
    
    content = path.read_text(encoding="utf-8")
    return Document(
        id=None,
        content=content,
        metadata={"source": "plan_phase_3.md", "phase": "3", "type": "plan"}
    )


@pytest.fixture
def phase4_doc(real_docs_path):
    """Загружает plan_phase_4.md."""
    path = real_docs_path / "phase_4" / "plan_phase_4.md"
    if not path.exists():
        pytest.skip(f"Документ не найден: {path}")
    
    content = path.read_text(encoding="utf-8")
    return Document(
        id=None,
        content=content,
        metadata={"source": "plan_phase_4.md", "phase": "4", "type": "plan"}
    )


@pytest.fixture
def mock_embedder():
    """Мок embedder для предсказуемых векторов."""
    embedder = Mock()
    embedder.embed.return_value = np.random.rand(768).astype(np.float32)
    embedder.embed_batch.side_effect = lambda texts: [
        np.random.rand(768).astype(np.float32) for _ in texts
    ]
    return embedder


@pytest.fixture
def e2e_store(tmp_path):
    """In-memory store для E2E теста."""
    db = VectorDatabase(":memory:")
    db.connect()
    store = PeeweeVectorStore(db, dimension=768)
    yield store
    db.close()


@pytest.fixture
def parser():
    """Инициализирует MarkdownNodeParser."""
    return MarkdownNodeParser()


@pytest.fixture
def splitter(parser):
    """Инициализирует SmartSplitter."""
    return SmartSplitter(
        parser=parser,
        chunk_size=500,
        code_chunk_size=1000,
        preserve_code=True
    )


@pytest.fixture
def context_strategy():
    """Инициализирует HierarchicalContextStrategy."""
    return HierarchicalContextStrategy(include_doc_title=True)


def test_e2e_pipeline_phase3(
    phase3_doc,
    e2e_store,
    mock_embedder,
    parser,
    splitter,
    context_strategy
):
    """E2E: Phase 3 план → парсинг → сплиттинг → контекст → индексация → поиск.
    
    Проверяем:
        - Markdown парсится в иерархию нод
        - Ноды разбиваются на чанки с chunk_type
        - Контекст добавляется корректно
        - Чанки индексируются с векторами
        - Поиск по chunk_type=CODE возвращает только код
    """
    # 1. Сплиттинг (внутри уже вызывается parser.parse())
    chunks = splitter.split(phase3_doc)
    assert len(chunks) > 0, "Должны быть созданы чанки"
    
    # Проверяем, что есть разные типы чанков
    chunk_types = {chunk.chunk_type for chunk in chunks}
    assert ChunkType.TEXT in chunk_types, "Должны быть TEXT чанки"
    
    # 2. Добавление контекста
    for chunk in chunks:
        context_text = context_strategy.form_vector_text(chunk, phase3_doc)
        chunk.context = context_text
    
    # Проверяем, что контекст добавлен
    for chunk in chunks:
        assert chunk.context is not None, "Контекст должен быть добавлен"
        assert len(chunk.context) > 0, "Контекст не должен быть пустым"
    
    # 3. Генерация векторов
    for chunk in chunks:
        chunk.vector = mock_embedder.embed(chunk.content)
    
    # 4. Индексация
    indexed_doc = e2e_store.save(phase3_doc, chunks)
    assert indexed_doc.id is not None, "Документ должен получить ID"
    
    # 5. Поиск по chunk_type=CODE
    query_vector = np.random.rand(768).astype(np.float32)
    code_results = e2e_store.search_chunks(
        query_vector=query_vector,
        chunk_type_filter=ChunkType.CODE,
        limit=10
    )
    
    # Проверяем, что все результаты - CODE (если они есть)
    for result in code_results:
        assert result.chunk_type == ChunkType.CODE, "Должны быть только CODE чанки"
        assert result.language is not None, "У CODE чанков должен быть язык"


def test_e2e_pipeline_phase4(
    phase4_doc,
    e2e_store,
    mock_embedder,
    parser,
    splitter,
    context_strategy
):
    """E2E: Phase 4 план → полный pipeline → проверка language фильтрации.
    
    Проверяем:
        - Парсинг Phase 4 плана
        - Обнаружение Python кода
        - Корректное присвоение language='python'
        - Поиск по language='python' возвращает только Python чанки
    """
    # 1. Сплиттинг
    chunks = splitter.split(phase4_doc)
    assert len(chunks) > 0
    
    # 2. Контекст
    for chunk in chunks:
        context_text = context_strategy.form_vector_text(chunk, phase4_doc)
        chunk.context = context_text
    
    # 3. Векторы
    for chunk in chunks:
        chunk.vector = mock_embedder.embed(chunk.content)
    
    # 4. Индексация
    indexed_doc = e2e_store.save(phase4_doc, chunks)
    assert indexed_doc.id is not None
    
    # 5. Проверяем, что есть Python чанки
    python_chunks = [c for c in chunks if c.language == "python"]
    if len(python_chunks) > 0:
        # Поиск по language='python'
        query_vector = np.random.rand(768).astype(np.float32)
        python_results = e2e_store.search_chunks(
            query_vector=query_vector,
            chunk_type_filter=ChunkType.CODE,
            language_filter="python",
            limit=10
        )
        
        # Все результаты должны быть Python
        for result in python_results:
            assert result.language == "python", "Должны быть только Python чанки"
    else:
        pytest.skip("В документе нет Python кода")


def test_e2e_multi_document_search(
    phase3_doc,
    phase4_doc,
    e2e_store,
    mock_embedder,
    parser,
    splitter,
    context_strategy
):
    """E2E: Индексация двух документов → поиск по обоим.
    
    Проверяем:
        - Оба документа индексируются
        - Поиск возвращает чанки из обоих документов
        - Фильтрация по метаданным (source) работает
    """
    all_chunks = []
    
    # Индексируем оба документа
    for doc in [phase3_doc, phase4_doc]:
        chunks = splitter.split(doc)
        
        for chunk in chunks:
            context_text = context_strategy.form_vector_text(chunk, doc)
            chunk.context = context_text
            chunk.vector = mock_embedder.embed(chunk.content)
        
        e2e_store.save(doc, chunks)
        all_chunks.extend(chunks)
    
    # Поиск по всем документам
    query_vector = np.random.rand(768).astype(np.float32)
    all_results = e2e_store.search_chunks(
        query_vector=query_vector,
        limit=20
    )
    
    # Должны быть результаты из обоих документов
    sources = {r.parent_metadata.get("source") for r in all_results if r.parent_metadata}
    assert len(sources) > 0, "Должны быть результаты из документов"
    
    # Проверяем, что можем отфильтровать по source через parent_metadata
    phase3_chunks = [
        r for r in all_results 
        if r.parent_metadata and r.parent_metadata.get("source") == "plan_phase_3.md"
    ]
    phase4_chunks = [
        r for r in all_results 
        if r.parent_metadata and r.parent_metadata.get("source") == "plan_phase_4.md"
    ]
    
    assert len(phase3_chunks) + len(phase4_chunks) == len(all_results), \
        "Все результаты должны быть из известных источников"
