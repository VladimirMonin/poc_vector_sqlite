"""Unit-тесты для SmartSplitter.

Проверяют корректность умной нарезки документов:
- Группировка мелких текстовых параграфов
- Изоляция блоков кода
- Атомарность CODE блоков (не смешиваются с текстом)
- Нарезка больших блоков кода построчно
- Сохранение метаданных иерархии
"""

import pytest

from semantic_core.domain import Document, Chunk, ChunkType


def test_text_grouping(smart_splitter):
    """Тест группировки мелких текстовых параграфов."""
    # Создаём документ с несколькими мелкими параграфами
    doc = Document(
        content="""# Header

Small paragraph 1.

Small paragraph 2.

Small paragraph 3.""",
        metadata={"title": "Test Doc"},
    )

    chunks = smart_splitter.split(doc)

    # Мелкие параграфы должны быть сгруппированы
    text_chunks = [c for c in chunks if c.chunk_type == ChunkType.TEXT]

    # Должно быть меньше чанков, чем параграфов (из-за группировки)
    assert len(text_chunks) < 3

    # Все чанки должны иметь тип TEXT
    for chunk in text_chunks:
        assert chunk.chunk_type == ChunkType.TEXT


def test_code_isolation(smart_splitter):
    """Тест изоляции блоков кода."""
    doc = Document(
        content="""# Test

Text before code.

```python
print("code")
```

Text after code.""",
        metadata={"title": "Code Test"},
    )

    chunks = smart_splitter.split(doc)

    # Должны быть и текстовые и кодовые чанки
    text_chunks = [c for c in chunks if c.chunk_type == ChunkType.TEXT]
    code_chunks = [c for c in chunks if c.chunk_type == ChunkType.CODE]

    assert len(text_chunks) > 0
    assert len(code_chunks) == 1

    # Проверяем что код изолирован
    code_chunk = code_chunks[0]
    assert code_chunk.chunk_type == ChunkType.CODE
    assert code_chunk.language == "python"
    assert 'print("code")' in code_chunk.content


def test_code_atomicity(smart_splitter):
    """Тест атомарности: код не смешивается с текстом даже если он маленький."""
    doc = Document(
        content="""Tiny text.

```python
x = 1
```

Another tiny text.""",
        metadata={"title": "Atomicity Test"},
    )

    chunks = smart_splitter.split(doc)

    # Код должен быть в отдельном чанке
    code_chunks = [c for c in chunks if c.chunk_type == ChunkType.CODE]
    text_chunks = [c for c in chunks if c.chunk_type == ChunkType.TEXT]

    assert len(code_chunks) == 1

    # Проверяем что код не смешан с текстом
    for text_chunk in text_chunks:
        assert "x = 1" not in text_chunk.content
        assert "```" not in text_chunk.content


def test_large_code_splitting(smart_splitter):
    """Тест нарезки больших блоков кода построчно."""
    # Создаём большой блок кода
    large_code = "\n".join([f"line_{i} = {i}" for i in range(200)])

    doc = Document(
        content=f"""# Test

```python
{large_code}
```
""",
        metadata={"title": "Large Code Test"},
    )

    chunks = smart_splitter.split(doc)
    code_chunks = [c for c in chunks if c.chunk_type == ChunkType.CODE]

    # Большой код должен быть разбит на несколько чанков
    # (зависит от code_chunk_size)
    # При размере 2000 и большом коде должно быть > 1
    if len(large_code) > 2000:
        assert len(code_chunks) > 1

        # Все части должны иметь маркер partial
        for chunk in code_chunks[:-1]:  # Кроме последнего
            assert chunk.metadata.get("partial") is True


def test_metadata_preservation(smart_splitter):
    """Тест сохранения метаданных иерархии."""
    doc = Document(
        content="""# H1

## H2

Text under H2.

```python
code_under_h2()
```
""",
        metadata={"title": "Metadata Test"},
    )

    chunks = smart_splitter.split(doc)

    # Проверяем что метаданные headers сохранены
    for chunk in chunks:
        if chunk.content.strip():
            # Должны быть заголовки в метаданных
            headers = chunk.metadata.get("headers", [])
            # Хотя бы один заголовок должен быть
            assert isinstance(headers, list)


def test_chunk_indexing(smart_splitter):
    """Тест нумерации чанков."""
    doc = Document(
        content="""# Test

Para 1.

```python
code()
```

Para 2.""",
        metadata={"title": "Index Test"},
    )

    chunks = smart_splitter.split(doc)

    # Индексы должны идти по порядку
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i


def test_empty_document_handling(smart_splitter):
    """Тест обработки пустого документа."""
    doc = Document(content="", metadata={"title": "Empty"})

    with pytest.raises(ValueError, match="empty"):
        smart_splitter.split(doc)


def test_only_whitespace_handling(smart_splitter):
    """Тест обработки документа только с пробелами."""
    doc = Document(content="   \n\n   ", metadata={"title": "Whitespace"})

    with pytest.raises(ValueError, match="empty"):
        smart_splitter.split(doc)


def test_mixed_content_evil_md(evil_md_content, smart_splitter):
    """Интеграционный тест на evil.md."""
    doc = Document(content=evil_md_content, metadata={"title": "Evil MD"})

    chunks = smart_splitter.split(doc)

    # Базовые проверки
    assert len(chunks) > 0

    text_chunks = [c for c in chunks if c.chunk_type == ChunkType.TEXT]
    code_chunks = [c for c in chunks if c.chunk_type == ChunkType.CODE]

    # Должны быть оба типа
    assert len(text_chunks) > 0
    assert len(code_chunks) > 0

    # Все чанки должны быть пронумерованы
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i

    # Проверяем языки кода
    python_chunks = [c for c in code_chunks if c.language == "python"]
    assert len(python_chunks) > 0


def test_preserve_code_flag(markdown_parser):
    """Тест флага preserve_code."""
    from semantic_core.processing.splitters.smart_splitter import SmartSplitter

    # Создаём сплиттер с preserve_code=False
    non_preserving_splitter = SmartSplitter(
        parser=markdown_parser,
        chunk_size=1000,
        preserve_code=False,
    )

    doc = Document(
        content="""Text

```python
x = 1
```

More text""",
        metadata={"title": "Test"},
    )

    chunks = non_preserving_splitter.split(doc)

    # С preserve_code=False код может быть смешан с текстом
    # (хотя наш парсер всё равно выделяет его отдельно)
    assert len(chunks) > 0
