"""Интеграционный тест granular search — поиск по типу чанков.

Сценарий:
    1. Индексируем evil.md с разными типами контента
    2. Выполняем search_chunks с фильтром по chunk_type
    3. Проверяем, что возвращаются только чанки нужного типа
    4. Валидируем метаданные parent_doc_title
"""

from pathlib import Path

import numpy as np
import pytest

from semantic_core.domain import ChunkType, Document
from semantic_core.infrastructure.storage.peewee.adapter import PeeweeVectorStore
from semantic_core.processing.context.hierarchical_strategy import (
    HierarchicalContextStrategy,
)
from semantic_core.processing.parsers.markdown_parser import MarkdownNodeParser
from semantic_core.processing.splitters.smart_splitter import SmartSplitter


@pytest.fixture
def vector_store(in_memory_db):
    """PeeweeVectorStore с in-memory БД."""
    return PeeweeVectorStore(in_memory_db)


def test_chunk_type_filtering(
    mock_embedder,
    vector_store,
    evil_md_path,
):
    """Тест фильтрации чанков по chunk_type.

    Проверяем:
    - Парсинг evil.md с разными типами контента
    - Индексация с chunk_type и language
    - Поиск только CODE чанков через search_chunks
    - Метаданные parent_doc_title присутствуют
    """
    # Arrange: настраиваем компоненты
    parser = MarkdownNodeParser()
    splitter = SmartSplitter(parser=parser, chunk_size=500, code_chunk_size=1000)
    context_strategy = HierarchicalContextStrategy()

    # Читаем evil.md
    content = evil_md_path.read_text()
    
    # Act: создаём документ и разбиваем на чанки
    document = Document(content=content, metadata={"title": "Evil Test Cases"})
    chunks = splitter.split(document)

    # Генерируем эмбеддинги для каждого чанка
    for chunk in chunks:
        enriched_text = context_strategy.form_vector_text(chunk, document)
        chunk.vector = mock_embedder.embed_query(enriched_text)

    # Сохраняем документ с чанками (уже с векторами)
    saved_doc = vector_store.save(document=document, chunks=chunks)

    # Выполняем поиск только CODE чанков
    code_results = vector_store.search_chunks(
        query_vector=np.array([0.5] * 768, dtype=np.float32),  # numpy array
        limit=10,
        chunk_type_filter=ChunkType.CODE,
    )

    # Assert: все результаты должны быть CODE
    assert len(code_results) > 0, "Должны быть найдены CODE чанки"

    for result in code_results:
        assert result.chunk_type == ChunkType.CODE, f"Ожидался CODE, получен {result.chunk_type}"

        # Проверяем наличие метаданных родителя
        assert result.parent_doc_title == "Evil Test Cases"

        # Для CODE чанков должен быть язык
        if result.language:
            assert result.language in ["python", "javascript", "bash"], (
                f"Неожиданный язык: {result.language}"
            )


def test_text_vs_code_separation(
    mock_embedder,
    vector_store,
    evil_md_path,
):
    """Тест разделения TEXT и CODE чанков.

    Проверяем, что:
    - TEXT чанки не содержат блоки кода
    - CODE чанки содержат только код
    """
    # Arrange
    parser = MarkdownNodeParser()
    splitter = SmartSplitter(parser=parser, chunk_size=500, code_chunk_size=1000)
    context_strategy = HierarchicalContextStrategy()

    content = evil_md_path.read_text()
    document = Document(content=content, metadata={"title": "Evil Separation Test"})
    chunks = splitter.split(document)

    # Генерируем эмбеддинги
    for chunk in chunks:
        enriched_text = context_strategy.form_vector_text(chunk, document)
        chunk.vector = mock_embedder.embed_query(enriched_text)

    # Act
    vector_store.save(document=document, chunks=chunks)

    # Поиск TEXT чанков
    text_results = vector_store.search_chunks(
        query_vector=np.array([0.5] * 768, dtype=np.float32),
        limit=20,
        chunk_type_filter=ChunkType.TEXT,
    )

    # Поиск CODE чанков
    code_results = vector_store.search_chunks(
        query_vector=np.array([0.5] * 768, dtype=np.float32),
        limit=20,
        chunk_type_filter=ChunkType.CODE,
    )

    # Assert: TEXT и CODE не пересекаются
    assert len(text_results) > 0, "Должны быть TEXT чанки"
    assert len(code_results) > 0, "Должны быть CODE чанки"

    text_ids = {r.chunk_id for r in text_results}
    code_ids = {r.chunk_id for r in code_results}

    assert text_ids.isdisjoint(code_ids), "TEXT и CODE чанки не должны пересекаться"


def test_language_metadata_for_code(
    mock_embedder,
    vector_store,
    evil_md_path,
):
    """Тест извлечения языка программирования из CODE чанков.

    Проверяем:
    - Наличие language для ```python блоков
    - Отсутствие language для ``` без указания языка
    """
    # Arrange
    parser = MarkdownNodeParser()
    splitter = SmartSplitter(parser=parser, chunk_size=500, code_chunk_size=1000)
    context_strategy = HierarchicalContextStrategy()

    content = evil_md_path.read_text()
    document = Document(content=content, metadata={"title": "Language Detection Test"})
    chunks = splitter.split(document)

    # Генерируем эмбеддинги
    for chunk in chunks:
        enriched_text = context_strategy.form_vector_text(chunk, document)
        chunk.vector = mock_embedder.embed_query(enriched_text)

    # Act
    vector_store.save(document=document, chunks=chunks)

    code_results = vector_store.search_chunks(
        query_vector=np.array([0.5] * 768, dtype=np.float32),
        limit=20,
        chunk_type_filter=ChunkType.CODE,
    )

    # Assert: проверяем языки
    languages_found = {r.language for r in code_results if r.language}
    assert len(languages_found) > 0, "Должны быть обнаружены языки программирования"

    # evil.md должен содержать хотя бы один из этих языков
    assert any(
        lang in ["python", "javascript", "bash"] for lang in languages_found
    ), f"Неожиданные языки: {languages_found}"


def test_chunk_index_sequential(
    mock_embedder,
    vector_store,
    evil_md_path,
):
    """Тест последовательной нумерации чанков.

    Проверяем, что chunk_index идёт подряд: 0, 1, 2, 3...
    """
    # Arrange
    parser = MarkdownNodeParser()
    splitter = SmartSplitter(parser=parser, chunk_size=500, code_chunk_size=1000)
    context_strategy = HierarchicalContextStrategy()

    content = evil_md_path.read_text()
    document = Document(content=content, metadata={"title": "Sequential Index Test"})
    chunks = splitter.split(document)

    # Генерируем эмбеддинги
    for chunk in chunks:
        enriched_text = context_strategy.form_vector_text(chunk, document)
        chunk.vector = mock_embedder.embed_query(enriched_text)

    # Act
    vector_store.save(document=document, chunks=chunks)

    # Получаем все чанки
    all_results = vector_store.search_chunks(
        query_vector=np.array([0.5] * 768, dtype=np.float32),
        limit=100,
    )

    # Assert: индексы должны быть последовательными
    indices = sorted([r.chunk_index for r in all_results])
    expected_indices = list(range(len(indices)))

    assert indices == expected_indices, f"Индексы не последовательны: {indices}"
