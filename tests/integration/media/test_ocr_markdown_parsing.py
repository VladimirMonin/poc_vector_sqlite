"""Интеграционные тесты для OCR Markdown parsing с реальным MarkdownNodeParser.

Эти тесты проверяют полную интеграцию OCRStep с MarkdownNodeParser
для детекции code blocks в OCR тексте из видео.

Phase 14.5: OCR Code Isolation
"""

from pathlib import Path

import pytest

from semantic_core.core.media_context import MediaContext
from semantic_core.domain import ChunkType, Document, MediaType
from semantic_core.processing.parsers.markdown_parser import MarkdownNodeParser
from semantic_core.processing.steps.ocr import OCRStep


class TestOCRMarkdownParsing:
    """Интеграционные тесты с реальным MarkdownNodeParser."""

    def test_simple_code_block_detection(self):
        """Простой code block детектится как CODE chunk."""
        parser = MarkdownNodeParser()
        step = OCRStep(
            parser=parser,
            parser_mode="markdown",
            ocr_text_chunk_size=1800,
            ocr_code_chunk_size=2000,
        )

        ocr_text = """
# Python Tutorial

Here's a simple function:

```python
def greet(name):
    return f"Hello, {name}!"
```

That's it!
"""

        context = MediaContext(
            media_path=Path("tutorial.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": ocr_text},
            chunks=[],
            base_index=0,
        )

        new_context = step.process(context)

        # Должно быть 3 чанка: TEXT + CODE + TEXT
        assert len(new_context.chunks) == 3

        # Chunk 0: TEXT (заголовок + текст)
        assert new_context.chunks[0].chunk_type == ChunkType.TEXT
        assert "Here's a simple function" in new_context.chunks[0].content

        # Chunk 1: CODE
        assert new_context.chunks[1].chunk_type == ChunkType.CODE
        assert "def greet(name)" in new_context.chunks[1].content
        assert new_context.chunks[1].metadata["language"] == "python"
        assert (
            new_context.chunks[1].metadata["hierarchical_context"] == "Python Tutorial"
        )

        # Chunk 2: TEXT
        assert new_context.chunks[2].chunk_type == ChunkType.TEXT
        assert "That's it!" in new_context.chunks[2].content

    def test_multiple_code_blocks_with_different_languages(self):
        """Несколько code blocks с разными языками."""
        parser = MarkdownNodeParser()
        step = OCRStep(parser=parser, parser_mode="markdown")

        ocr_text = """
## JavaScript Example

```javascript
const hello = () => console.log('Hi');
```

## Python Example

```python
def hello():
    print('Hi')
```
"""

        context = MediaContext(
            media_path=Path("polyglot.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": ocr_text},
            chunks=[],
            base_index=0,
        )

        new_context = step.process(context)

        # Ищем CODE чанки
        code_chunks = [c for c in new_context.chunks if c.chunk_type == ChunkType.CODE]
        assert len(code_chunks) == 2

        # JavaScript chunk
        js_chunk = next(c for c in code_chunks if "const hello" in c.content)
        assert js_chunk.metadata["language"] == "javascript"
        assert "JavaScript Example" in js_chunk.metadata["hierarchical_context"]

        # Python chunk
        py_chunk = next(c for c in code_chunks if "def hello" in c.content)
        assert py_chunk.metadata["language"] == "python"
        assert "Python Example" in py_chunk.metadata["hierarchical_context"]

    def test_code_without_language_tag(self):
        """Code block без указания языка."""
        parser = MarkdownNodeParser()
        step = OCRStep(parser=parser, parser_mode="markdown")

        ocr_text = """
Generic code:

```
some code here
without language
```
"""

        context = MediaContext(
            media_path=Path("video.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": ocr_text},
            chunks=[],
            base_index=0,
        )

        new_context = step.process(context)

        # CODE chunk есть
        code_chunks = [c for c in new_context.chunks if c.chunk_type == ChunkType.CODE]
        assert len(code_chunks) == 1

        # language может быть None
        assert (
            "language" not in code_chunks[0].metadata
            or code_chunks[0].metadata["language"] is None
        )

    def test_long_code_block_splitting(self):
        """Длинный code block разбивается на несколько чанков."""
        parser = MarkdownNodeParser()
        step = OCRStep(
            parser=parser,
            parser_mode="markdown",
            ocr_code_chunk_size=100,  # Маленький размер для теста
        )

        # Генерируем длинный код
        long_code = "\n".join([f"line_{i} = {i}" for i in range(50)])  # ~500+ символов
        ocr_text = f"```python\n{long_code}\n```"

        context = MediaContext(
            media_path=Path("long_code.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": ocr_text},
            chunks=[],
            base_index=0,
        )

        new_context = step.process(context)

        # Несколько CODE чанков
        assert len(new_context.chunks) > 1

        # Все CODE типа
        for chunk in new_context.chunks:
            assert chunk.chunk_type == ChunkType.CODE
            assert chunk.metadata["language"] == "python"
            # Размер примерно ocr_code_chunk_size
            assert len(chunk.content) <= 150  # С запасом

    def test_nested_headers_context(self):
        """Вложенные заголовки в hierarchical_context."""
        parser = MarkdownNodeParser()
        step = OCRStep(parser=parser, parser_mode="markdown")

        ocr_text = """
# Main Topic

## Subtopic A

### Details

Some text under deep nesting.

```python
code_here = True
```
"""

        context = MediaContext(
            media_path=Path("nested.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": ocr_text},
            chunks=[],
            base_index=0,
        )

        new_context = step.process(context)

        # Проверяем hierarchical_context
        text_chunks = [c for c in new_context.chunks if c.chunk_type == ChunkType.TEXT]
        assert any(
            "Main Topic > Subtopic A > Details"
            in c.metadata.get("hierarchical_context", "")
            for c in text_chunks
        )

        code_chunks = [c for c in new_context.chunks if c.chunk_type == ChunkType.CODE]
        assert len(code_chunks) == 1
        assert (
            "Main Topic > Subtopic A > Details"
            in code_chunks[0].metadata["hierarchical_context"]
        )

    def test_mixed_content_complex(self):
        """Сложный случай: текст + код + текст + код."""
        parser = MarkdownNodeParser()
        step = OCRStep(parser=parser, parser_mode="markdown")

        ocr_text = """
# Tutorial

Introduction paragraph.

## Step 1: Setup

```bash
npm install package
```

Explanation text here.

## Step 2: Code

```javascript
const app = require('express')();
app.listen(3000);
```

Final notes.
"""

        context = MediaContext(
            media_path=Path("complex.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": ocr_text},
            chunks=[],
            base_index=0,
        )

        new_context = step.process(context)

        # Проверяем чередование TEXT/CODE
        types = [c.chunk_type for c in new_context.chunks]

        # Должны быть и TEXT, и CODE
        assert ChunkType.TEXT in types
        assert ChunkType.CODE in types

        # CODE чанки имеют правильные языки
        bash_chunk = next(c for c in new_context.chunks if "npm install" in c.content)
        assert bash_chunk.chunk_type == ChunkType.CODE
        assert bash_chunk.metadata["language"] == "bash"

        js_chunk = next(
            c for c in new_context.chunks if "require('express')" in c.content
        )
        assert js_chunk.chunk_type == ChunkType.CODE
        assert js_chunk.metadata["language"] == "javascript"

    def test_plain_mode_vs_markdown_mode(self):
        """Сравнение plain и markdown режимов."""
        ocr_text = """
```python
def test():
    pass
```
"""

        context_base = MediaContext(
            media_path=Path("test.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": ocr_text},
            chunks=[],
            base_index=0,
        )

        # Plain режим — всё TEXT
        step_plain = OCRStep(parser=None, parser_mode="plain")
        context_plain = step_plain.process(context_base)

        assert all(c.chunk_type == ChunkType.TEXT for c in context_plain.chunks)
        assert len(context_plain.chunks) == 1
        assert "```python" in context_plain.chunks[0].content  # Fence не обработан

        # Markdown режим — CODE детектится
        parser = MarkdownNodeParser()
        step_markdown = OCRStep(parser=parser, parser_mode="markdown")
        context_markdown = step_markdown.process(context_base)

        code_chunks = [
            c for c in context_markdown.chunks if c.chunk_type == ChunkType.CODE
        ]
        assert len(code_chunks) >= 1
        assert "def test():" in code_chunks[0].content
        assert "```python" not in code_chunks[0].content  # Fence удалён

    def test_chunk_metadata_role_and_paths(self):
        """Проверка metadata: role, parent_media_path, _original_path."""
        parser = MarkdownNodeParser()
        step = OCRStep(parser=parser, parser_mode="markdown")

        media_path = Path("/absolute/path/to/screencast.mp4")

        context = MediaContext(
            media_path=media_path,
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": "```python\ncode\n```"},
            chunks=[],
            base_index=0,
        )

        new_context = step.process(context)

        for chunk in new_context.chunks:
            assert chunk.metadata["role"] == "ocr"
            assert chunk.metadata["parent_media_path"] == str(media_path)
            assert chunk.metadata["_original_path"] == str(media_path)

    def test_base_index_increments_correctly(self):
        """base_index правильно увеличивается для каждого чанка."""
        parser = MarkdownNodeParser()
        step = OCRStep(parser=parser, parser_mode="markdown")

        ocr_text = """
Text 1

```python
code 1
```

Text 2

```python
code 2
```
"""

        context = MediaContext(
            media_path=Path("multi.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": ocr_text},
            chunks=[],
            base_index=10,  # Начальный индекс
        )

        new_context = step.process(context)

        # chunk_index должны быть последовательными: 10, 11, 12, 13...
        for i, chunk in enumerate(new_context.chunks):
            assert chunk.chunk_index == 10 + i

        # base_index обновлён
        assert new_context.base_index == 10 + len(new_context.chunks)


class TestOCRStepEdgeCases:
    """Edge cases для OCR Markdown parsing."""

    def test_empty_code_block(self):
        """Пустой code block."""
        parser = MarkdownNodeParser()
        step = OCRStep(parser=parser, parser_mode="markdown")

        ocr_text = "```python\n\n```"

        context = MediaContext(
            media_path=Path("empty.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": ocr_text},
            chunks=[],
            base_index=0,
        )

        new_context = step.process(context)

        # Может создать пустой CODE chunk или пропустить — зависит от parser
        # Главное — не упасть
        assert isinstance(new_context.chunks, list)

    def test_malformed_markdown(self):
        """Некорректный Markdown (незакрытые code fences)."""
        parser = MarkdownNodeParser()
        step = OCRStep(parser=parser, parser_mode="markdown")

        ocr_text = """
```python
def test():
    # Незакрытый fence
"""

        context = MediaContext(
            media_path=Path("malformed.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": ocr_text},
            chunks=[],
            base_index=0,
        )

        # Не должно упасть
        new_context = step.process(context)
        assert isinstance(new_context.chunks, list)

    def test_only_code_no_text(self):
        """OCR содержит только code, без текста."""
        parser = MarkdownNodeParser()
        step = OCRStep(parser=parser, parser_mode="markdown")

        ocr_text = "```python\nprint('hello')\n```"

        context = MediaContext(
            media_path=Path("only_code.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": ocr_text},
            chunks=[],
            base_index=0,
        )

        new_context = step.process(context)

        # Только CODE чанки
        assert all(c.chunk_type == ChunkType.CODE for c in new_context.chunks)
        assert len(new_context.chunks) >= 1

    def test_only_text_no_code(self):
        """OCR содержит только текст, без кода."""
        parser = MarkdownNodeParser()
        step = OCRStep(parser=parser, parser_mode="markdown")

        ocr_text = "# Header\n\nJust plain text without any code blocks."

        context = MediaContext(
            media_path=Path("no_code.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": ocr_text},
            chunks=[],
            base_index=0,
        )

        new_context = step.process(context)

        # Только TEXT чанки
        assert all(c.chunk_type == ChunkType.TEXT for c in new_context.chunks)
        assert len(new_context.chunks) >= 1
