"""Тесты для MarkdownAssetEnricher.

Проверяем извлечение контекста для IMAGE_REF чанков:
- Breadcrumbs из headers
- Surrounding text из соседних чанков
- Alt и title из metadata
"""

import pytest

from semantic_core.domain.chunk import Chunk, ChunkType
from semantic_core.processing.enrichers.markdown_assets import (
    MediaContext,
    MarkdownAssetEnricher,
)


class TestMediaContext:
    """Тесты для MediaContext DTO."""

    def test_format_for_vision_full(self):
        """Полный контекст форматируется корректно."""
        ctx = MediaContext(
            breadcrumbs="Setup > Nginx > Configuration",
            surrounding_text="[Before]: ...install nginx...\n[After]: ...restart service...",
            alt_text="Nginx config diagram",
            title="Figure 1",
        )

        result = ctx.format_for_vision()

        assert "Document section: Setup > Nginx > Configuration" in result
        assert "Image caption: Nginx config diagram" in result
        assert "Title: Figure 1" in result
        assert "[Before]: ...install nginx..." in result
        assert "Role: Illustration embedded in document" in result

    def test_format_for_vision_minimal(self):
        """Минимальный контекст (только role)."""
        ctx = MediaContext()

        result = ctx.format_for_vision()

        assert result == "Role: Illustration embedded in document"

    def test_format_for_vision_partial(self):
        """Частичный контекст — пропускает пустые поля."""
        ctx = MediaContext(
            breadcrumbs="API Docs",
            alt_text="Diagram",
        )

        result = ctx.format_for_vision()

        assert "Document section: API Docs" in result
        assert "Image caption: Diagram" in result
        assert "Title:" not in result  # title пустой
        assert "Surrounding text:" not in result  # surrounding_text пустой


class TestMarkdownAssetEnricher:
    """Тесты для MarkdownAssetEnricher."""

    @pytest.fixture
    def enricher(self):
        """Стандартный enricher."""
        return MarkdownAssetEnricher(context_window=50)

    @pytest.fixture
    def sample_chunks(self):
        """Набор чанков: TEXT, IMAGE_REF, TEXT."""
        return [
            Chunk(
                content="This is introduction text about nginx configuration.",
                chunk_index=0,
                chunk_type=ChunkType.TEXT,
                metadata={"headers": ["Setup"]},
            ),
            Chunk(
                content="images/nginx_diagram.png",
                chunk_index=1,
                chunk_type=ChunkType.IMAGE_REF,
                metadata={
                    "headers": ["Setup", "Nginx"],
                    "alt": "Nginx architecture",
                    "title": "Figure 1",
                },
            ),
            Chunk(
                content="After seeing the diagram, you can configure the server.",
                chunk_index=2,
                chunk_type=ChunkType.TEXT,
                metadata={"headers": ["Setup", "Nginx"]},
            ),
        ]

    def test_get_context_with_neighbors(self, enricher, sample_chunks):
        """Контекст включает текст ДО и ПОСЛЕ."""
        image_chunk = sample_chunks[1]

        ctx = enricher.get_context(image_chunk, sample_chunks)

        # Breadcrumbs из headers
        assert ctx.breadcrumbs == "Setup > Nginx"

        # Alt и title
        assert ctx.alt_text == "Nginx architecture"
        assert ctx.title == "Figure 1"

        # Surrounding text
        assert "[Before]:" in ctx.surrounding_text
        assert "[After]:" in ctx.surrounding_text
        assert "nginx configuration" in ctx.surrounding_text
        assert "diagram" in ctx.surrounding_text

    def test_get_context_first_chunk_no_before(self, enricher):
        """Первый чанк — нет текста ДО."""
        chunks = [
            Chunk(
                content="images/intro.png",
                chunk_index=0,
                chunk_type=ChunkType.IMAGE_REF,
                metadata={"headers": ["Intro"], "alt": "Intro image"},
            ),
            Chunk(
                content="Welcome to our documentation.",
                chunk_index=1,
                chunk_type=ChunkType.TEXT,
            ),
        ]

        ctx = enricher.get_context(chunks[0], chunks)

        assert "[Before]:" not in ctx.surrounding_text
        assert "[After]:" in ctx.surrounding_text
        assert "Welcome" in ctx.surrounding_text

    def test_get_context_last_chunk_no_after(self, enricher):
        """Последний чанк — нет текста ПОСЛЕ."""
        chunks = [
            Chunk(
                content="That concludes our guide.",
                chunk_index=0,
                chunk_type=ChunkType.TEXT,
            ),
            Chunk(
                content="images/end.png",
                chunk_index=1,
                chunk_type=ChunkType.IMAGE_REF,
                metadata={"alt": "End image"},
            ),
        ]

        ctx = enricher.get_context(chunks[1], chunks)

        assert "[Before]:" in ctx.surrounding_text
        assert "[After]:" not in ctx.surrounding_text
        assert "concludes" in ctx.surrounding_text

    def test_get_context_code_neighbor_skipped(self, enricher):
        """CODE чанки пропускаются при поиске соседей."""
        chunks = [
            Chunk(
                content="Here is some code:",
                chunk_index=0,
                chunk_type=ChunkType.TEXT,
            ),
            Chunk(
                content="def foo(): pass",
                chunk_index=1,
                chunk_type=ChunkType.CODE,
                language="python",
            ),
            Chunk(
                content="images/code_diagram.png",
                chunk_index=2,
                chunk_type=ChunkType.IMAGE_REF,
                metadata={"alt": "Code diagram"},
            ),
        ]

        ctx = enricher.get_context(chunks[2], chunks)

        # Должен найти TEXT чанк через CODE
        assert "[Before]:" in ctx.surrounding_text
        assert "some code" in ctx.surrounding_text
        assert "def foo" not in ctx.surrounding_text  # CODE пропущен

    def test_breadcrumbs_from_headers(self, enricher):
        """Breadcrumbs формируются из headers."""
        chunk = Chunk(
            content="images/test.png",
            chunk_index=0,
            chunk_type=ChunkType.IMAGE_REF,
            metadata={"headers": ["Chapter 1", "Section A", "Subsection"]},
        )

        ctx = enricher.get_context(chunk, [chunk])

        assert ctx.breadcrumbs == "Chapter 1 > Section A > Subsection"

    def test_alt_included_in_context(self, enricher):
        """Alt-текст извлекается из metadata."""
        chunk = Chunk(
            content="images/test.png",
            chunk_index=0,
            chunk_type=ChunkType.IMAGE_REF,
            metadata={"alt": "Test image alt text"},
        )

        ctx = enricher.get_context(chunk, [chunk])

        assert ctx.alt_text == "Test image alt text"

    def test_no_headers_empty_breadcrumbs(self, enricher):
        """Без headers — пустые breadcrumbs."""
        chunk = Chunk(
            content="images/test.png",
            chunk_index=0,
            chunk_type=ChunkType.IMAGE_REF,
            metadata={},
        )

        ctx = enricher.get_context(chunk, [chunk])

        assert ctx.breadcrumbs == ""

    def test_context_window_limits_text(self):
        """context_window ограничивает длину текста."""
        enricher = MarkdownAssetEnricher(context_window=10)

        chunks = [
            Chunk(
                content="This is a very long text that should be truncated.",
                chunk_index=0,
                chunk_type=ChunkType.TEXT,
            ),
            Chunk(
                content="images/test.png",
                chunk_index=1,
                chunk_type=ChunkType.IMAGE_REF,
            ),
        ]

        ctx = enricher.get_context(chunks[1], chunks)

        # Берём последние 10 символов
        assert "truncated." in ctx.surrounding_text
        assert len(ctx.surrounding_text) < 50  # Не весь текст

    def test_empty_chunks_list(self, enricher):
        """Пустой список чанков — нет соседей."""
        chunk = Chunk(
            content="images/lonely.png",
            chunk_index=0,
            chunk_type=ChunkType.IMAGE_REF,
            metadata={"alt": "Lonely image"},
        )

        ctx = enricher.get_context(chunk, [chunk])

        assert ctx.surrounding_text == ""
        assert ctx.alt_text == "Lonely image"

    def test_multiple_images_in_sequence(self, enricher):
        """Несколько картинок подряд — пропускаем IMAGE_REF соседей."""
        chunks = [
            Chunk(
                content="Introduction text.",
                chunk_index=0,
                chunk_type=ChunkType.TEXT,
            ),
            Chunk(
                content="images/first.png",
                chunk_index=1,
                chunk_type=ChunkType.IMAGE_REF,
            ),
            Chunk(
                content="images/second.png",
                chunk_index=2,
                chunk_type=ChunkType.IMAGE_REF,
            ),
            Chunk(
                content="Conclusion text.",
                chunk_index=3,
                chunk_type=ChunkType.TEXT,
            ),
        ]

        # Контекст для второй картинки
        ctx = enricher.get_context(chunks[2], chunks)

        # Должен найти TEXT, а не IMAGE_REF
        assert "Introduction" in ctx.surrounding_text
        assert "Conclusion" in ctx.surrounding_text
        assert "first.png" not in ctx.surrounding_text
