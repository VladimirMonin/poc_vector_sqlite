"""Unit-тесты для HierarchicalContextStrategy.

Проверяют корректность формирования контекста для эмбеддингов:
- Формирование промптов для TEXT и CODE
- Корректность breadcrumbs (иерархия заголовков)
- Обработка пустых headers и None значений
- Различные шаблоны для разных типов контента
"""

import pytest

from semantic_core.domain import Document, Chunk, ChunkType


def test_text_context_formatting(hierarchical_context):
    """Тест формирования контекста для обычного текста."""
    doc = Document(
        content="Full doc content",
        metadata={"title": "Test Document"},
    )
    
    chunk = Chunk(
        content="This is a test paragraph.",
        chunk_index=0,
        chunk_type=ChunkType.TEXT,
        metadata={"headers": ["Chapter 1", "Section A"]},
    )
    
    context_text = hierarchical_context.form_vector_text(chunk, doc)
    
    # Проверяем что контекст содержит ключевые элементы
    assert "Document: Test Document" in context_text
    assert "Section: Chapter 1 > Section A" in context_text
    assert "Content:" in context_text
    assert "This is a test paragraph." in context_text


def test_code_context_formatting(hierarchical_context):
    """Тест формирования контекста для блоков кода."""
    doc = Document(
        content="Doc with code",
        metadata={"title": "Code Example"},
    )
    
    chunk = Chunk(
        content='def hello():\n    print("world")',
        chunk_index=0,
        chunk_type=ChunkType.CODE,
        language="python",
        metadata={"headers": ["Tutorial", "Functions"]},
    )
    
    context_text = hierarchical_context.form_vector_text(chunk, doc)
    
    # Проверяем специфичный для кода формат
    assert "Document: Code Example" in context_text
    assert "Context: Tutorial > Functions" in context_text
    assert "Type: Python Code" in context_text
    assert "Code:" in context_text
    assert 'def hello():' in context_text


def test_code_without_language(hierarchical_context):
    """Тест кода без указания языка."""
    doc = Document(content="Doc", metadata={"title": "Test"})
    
    chunk = Chunk(
        content="some code",
        chunk_index=0,
        chunk_type=ChunkType.CODE,
        language=None,
        metadata={"headers": ["Section"]},
    )
    
    context_text = hierarchical_context.form_vector_text(chunk, doc)
    
    # Должно быть просто "Type: Code"
    assert "Type: Code" in context_text
    assert "Type: Python Code" not in context_text


def test_empty_headers_handling(hierarchical_context):
    """Тест обработки пустых заголовков."""
    doc = Document(content="Doc", metadata={"title": "Test"})
    
    chunk = Chunk(
        content="Text without headers",
        chunk_index=0,
        chunk_type=ChunkType.TEXT,
        metadata={},  # Нет headers
    )
    
    context_text = hierarchical_context.form_vector_text(chunk, doc)
    
    # Не должно быть секции Section
    assert "Section:" not in context_text
    # Но должны быть Document и Content
    assert "Document: Test" in context_text
    assert "Content:" in context_text


def test_no_doc_title(hierarchical_context):
    """Тест обработки документа без заголовка."""
    doc = Document(content="Doc", metadata={})  # Нет title
    
    chunk = Chunk(
        content="Text",
        chunk_index=0,
        chunk_type=ChunkType.TEXT,
        metadata={"headers": ["H1"]},
    )
    
    context_text = hierarchical_context.form_vector_text(chunk, doc)
    
    # Document секция может отсутствовать или быть без значения
    assert "Section: H1" in context_text
    assert "Content:" in context_text


def test_include_doc_title_flag():
    """Тест флага include_doc_title."""
    from semantic_core.processing.context.hierarchical_strategy import (
        HierarchicalContextStrategy,
    )
    
    # Без заголовка документа
    strategy_no_title = HierarchicalContextStrategy(include_doc_title=False)
    
    doc = Document(content="Doc", metadata={"title": "Test Document"})
    chunk = Chunk(
        content="Text",
        chunk_index=0,
        chunk_type=ChunkType.TEXT,
        metadata={"headers": ["H1"]},
    )
    
    context_text = strategy_no_title.form_vector_text(chunk, doc)
    
    # Не должно быть Document секции
    assert "Document:" not in context_text
    assert "Section: H1" in context_text


def test_image_ref_context(hierarchical_context):
    """Тест формирования контекста для IMAGE_REF."""
    doc = Document(content="Doc", metadata={"title": "Gallery"})
    
    chunk = Chunk(
        content="images/photo.jpg",
        chunk_index=0,
        chunk_type=ChunkType.IMAGE_REF,
        metadata={
            "headers": ["Gallery", "Nature"],
            "alt": "Beautiful sunset",
            "title": "Sunset Photo",
        },
    )
    
    context_text = hierarchical_context.form_vector_text(chunk, doc)
    
    # Проверяем формат для изображений
    assert "Type: Image Reference" in context_text
    assert "Description: Beautiful sunset" in context_text
    assert "Title: Sunset Photo" in context_text
    assert "Source: images/photo.jpg" in context_text


def test_quote_metadata(hierarchical_context):
    """Тест обработки цитат (quote metadata)."""
    doc = Document(content="Doc", metadata={"title": "Quotes"})
    
    chunk = Chunk(
        content="This is a famous quote.",
        chunk_index=0,
        chunk_type=ChunkType.TEXT,
        metadata={
            "headers": ["Chapter 1"],
            "quote": True,
        },
    )
    
    context_text = hierarchical_context.form_vector_text(chunk, doc)
    
    # Должен быть маркер Type: Quote
    assert "Type: Quote" in context_text
    assert "This is a famous quote." in context_text


def test_deep_hierarchy(hierarchical_context):
    """Тест глубокой иерархии заголовков."""
    doc = Document(content="Doc", metadata={"title": "Manual"})
    
    chunk = Chunk(
        content="Detailed instructions",
        chunk_index=0,
        chunk_type=ChunkType.TEXT,
        metadata={
            "headers": ["Part 1", "Chapter 2", "Section 3", "Subsection 4"],
        },
    )
    
    context_text = hierarchical_context.form_vector_text(chunk, doc)
    
    # Проверяем полный путь через >
    assert "Part 1 > Chapter 2 > Section 3 > Subsection 4" in context_text


def test_context_consistency():
    """Тест консистентности формата для разных типов."""
    from semantic_core.processing.context.hierarchical_strategy import (
        HierarchicalContextStrategy,
    )
    
    strategy = HierarchicalContextStrategy()
    doc = Document(content="Doc", metadata={"title": "Test"})
    
    # Создаём чанки разных типов
    text_chunk = Chunk(
        content="Text",
        chunk_index=0,
        chunk_type=ChunkType.TEXT,
        metadata={"headers": ["H1"]},
    )
    
    code_chunk = Chunk(
        content="code()",
        chunk_index=1,
        chunk_type=ChunkType.CODE,
        language="python",
        metadata={"headers": ["H1"]},
    )
    
    # Оба должны начинаться с Document
    text_context = strategy.form_vector_text(text_chunk, doc)
    code_context = strategy.form_vector_text(code_chunk, doc)
    
    assert text_context.startswith("Document: Test")
    assert code_context.startswith("Document: Test")
    
    # У кода должно быть "Context:", у текста "Section:"
    assert "Section: H1" in text_context
    assert "Context: H1" in code_context


def test_special_characters_in_headers(hierarchical_context):
    """Тест обработки спецсимволов в заголовках."""
    doc = Document(content="Doc", metadata={"title": "Test"})
    
    chunk = Chunk(
        content="Content",
        chunk_index=0,
        chunk_type=ChunkType.TEXT,
        metadata={
            "headers": ["Chapter: Introduction", "Section > Basics"],
        },
    )
    
    context_text = hierarchical_context.form_vector_text(chunk, doc)
    
    # Спецсимволы должны сохраняться
    assert "Chapter: Introduction > Section > Basics" in context_text
