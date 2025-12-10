"""Тесты для OCRStep — разбивка OCR текста на чанки с детекцией code blocks.

Тестируются:
- should_run() логика (есть/нет ocr_text)
- Markdown parsing с детекцией code blocks
- Режимы парсинга (markdown/plain)
- Разные chunk_size для TEXT и CODE
- Мониторинг code_ratio (false positives)
- Обогащение metadata (role='ocr', parent_media_path, hierarchical_context)
- base_index корректно увеличивается
- Immutability контекста
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from semantic_core.core.media_context import MediaContext
from semantic_core.domain import Chunk, ChunkType, Document, MediaType
from semantic_core.interfaces.parser import ParsingSegment
from semantic_core.processing.steps.ocr import OCRStep


class TestOCRStepShouldRun:
    """Тесты для should_run() логики."""

    def test_should_run_with_ocr_text(self):
        """Шаг должен выполняться при наличии ocr_text."""
        step = OCRStep(parser=None, parser_mode="plain")

        context = MediaContext(
            media_path=Path("video.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": "Some OCR text"},
            chunks=[],
            base_index=0,
        )

        assert step.should_run(context) is True

    def test_should_run_without_ocr_text(self):
        """Шаг НЕ должен выполняться без ocr_text."""
        step = OCRStep(parser=None, parser_mode="plain")

        context = MediaContext(
            media_path=Path("video.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"type": "video"},  # Нет ocr_text
            chunks=[],
            base_index=0,
        )

        assert step.should_run(context) is False

    def test_should_run_with_empty_ocr_text(self):
        """Пустой ocr_text — не выполняем."""
        step = OCRStep(parser=None, parser_mode="plain")

        context = MediaContext(
            media_path=Path("video.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": ""},  # Пустая строка
            chunks=[],
            base_index=0,
        )

        assert step.should_run(context) is False


class TestOCRStepBasic:
    """Базовые тесты OCRStep."""

    def test_step_name(self):
        """Проверяем имя шага."""
        step = OCRStep(parser=None)
        assert step.step_name == "ocr"

    def test_is_optional_false(self):
        """OCRStep критичен по умолчанию."""
        step = OCRStep(parser=None)
        assert step.is_optional is False

    def test_default_parser_mode_markdown(self):
        """По умолчанию parser_mode='markdown'."""
        mock_parser = MagicMock()
        step = OCRStep(parser=mock_parser)
        assert step.parser_mode == "markdown"

    def test_custom_parser_mode_plain(self):
        """Можно установить parser_mode='plain'."""
        step = OCRStep(parser=None, parser_mode="plain")
        assert step.parser_mode == "plain"

    @patch("semantic_core.processing.steps.ocr.logger")
    def test_markdown_mode_without_parser_switches_to_plain(self, mock_logger):
        """Если parser_mode='markdown', но parser=None, переключаемся на plain с warning."""
        step = OCRStep(parser=None, parser_mode="markdown")

        # Режим переключился на plain
        assert step.parser_mode == "plain"

        # Warning выдан
        mock_logger.warning.assert_called_once()
        assert "requires parser" in mock_logger.warning.call_args[0][0]


class TestOCRStepPlainMode:
    """Тесты plain режима (без Markdown parsing)."""

    def test_plain_mode_single_chunk(self):
        """Plain режим: короткий текст → 1 TEXT чанк."""
        step = OCRStep(
            parser=None,
            parser_mode="plain",
            ocr_text_chunk_size=1800,
        )

        context = MediaContext(
            media_path=Path("screencast.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": "Short OCR text"},
            chunks=[],
            base_index=3,
        )

        new_context = step.process(context)

        # 1 чанк создан
        assert len(new_context.chunks) == 1
        chunk = new_context.chunks[0]

        # Тип TEXT
        assert chunk.chunk_type == ChunkType.TEXT
        assert chunk.content == "Short OCR text"

        # chunk_index = base_index
        assert chunk.chunk_index == 3

        # Metadata обогащена
        assert chunk.metadata["role"] == "ocr"
        assert chunk.metadata["parent_media_path"] == "screencast.mp4"
        assert chunk.metadata["_original_path"] == "screencast.mp4"

        # base_index увеличился
        assert new_context.base_index == 4

    def test_plain_mode_multi_chunk(self):
        """Plain режим: длинный текст → несколько TEXT чанков."""
        step = OCRStep(
            parser=None,
            parser_mode="plain",
            ocr_text_chunk_size=20,  # Маленький размер для теста
        )

        long_text = "A" * 60 + "\n" + "B" * 60  # 121 символ

        context = MediaContext(
            media_path=Path("tutorial.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": long_text},
            chunks=[],
            base_index=10,
        )

        new_context = step.process(context)

        # Несколько чанков созданы
        assert len(new_context.chunks) >= 2

        # Все TEXT типа
        for chunk in new_context.chunks:
            assert chunk.chunk_type == ChunkType.TEXT
            assert chunk.metadata["role"] == "ocr"

        # chunk_index правильно проставлены
        for i, chunk in enumerate(new_context.chunks):
            assert chunk.chunk_index == 10 + i

        # base_index увеличился
        assert new_context.base_index == 10 + len(new_context.chunks)


class TestOCRStepMarkdownMode:
    """Тесты markdown режима (с детекцией code blocks)."""

    def test_markdown_mode_code_detection(self):
        """Markdown режим: code blocks → ChunkType.CODE."""
        # Mock parser возвращает сегменты: TEXT + CODE + TEXT
        mock_parser = MagicMock()
        mock_parser.parse.return_value = [
            ParsingSegment(
                content="Introduction text",
                segment_type=ChunkType.TEXT,
                headers=["Tutorial"],
                start_line=1,
                end_line=1,
            ),
            ParsingSegment(
                content="def hello():\n    print('hi')",
                segment_type=ChunkType.CODE,
                language="python",
                headers=["Tutorial"],
                start_line=3,
                end_line=5,
            ),
            ParsingSegment(
                content="Conclusion text",
                segment_type=ChunkType.TEXT,
                headers=["Tutorial"],
                start_line=7,
                end_line=7,
            ),
        ]

        step = OCRStep(
            parser=mock_parser,
            parser_mode="markdown",
            ocr_text_chunk_size=1800,
            ocr_code_chunk_size=2000,
        )

        context = MediaContext(
            media_path=Path("screencast.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={
                "ocr_text": "# Tutorial\nIntro\n```python\ndef hello():\n    print('hi')\n```\nConclusion"
            },
            chunks=[],
            base_index=0,
        )

        new_context = step.process(context)

        # Parser вызван
        mock_parser.parse.assert_called_once()

        # 3 чанка созданы
        assert len(new_context.chunks) == 3

        # Chunk 0: TEXT
        assert new_context.chunks[0].chunk_type == ChunkType.TEXT
        assert new_context.chunks[0].content == "Introduction text"
        assert new_context.chunks[0].chunk_index == 0
        assert new_context.chunks[0].metadata["hierarchical_context"] == "Tutorial"
        assert new_context.chunks[0].metadata["start_line"] == 1

        # Chunk 1: CODE
        assert new_context.chunks[1].chunk_type == ChunkType.CODE
        assert "def hello()" in new_context.chunks[1].content
        assert new_context.chunks[1].chunk_index == 1
        assert new_context.chunks[1].metadata["language"] == "python"
        assert new_context.chunks[1].metadata["start_line"] == 3

        # Chunk 2: TEXT
        assert new_context.chunks[2].chunk_type == ChunkType.TEXT
        assert new_context.chunks[2].content == "Conclusion text"
        assert new_context.chunks[2].chunk_index == 2

    def test_markdown_mode_long_code_splitting(self):
        """Markdown режим: длинный code block режется на части."""
        # Mock parser возвращает очень длинный CODE сегмент
        long_code = "x = 1\n" * 200  # ~1200 символов
        mock_parser = MagicMock()
        mock_parser.parse.return_value = [
            ParsingSegment(
                content=long_code,
                segment_type=ChunkType.CODE,
                language="python",
                headers=[],
                start_line=1,
                end_line=200,
            ),
        ]

        step = OCRStep(
            parser=mock_parser,
            parser_mode="markdown",
            ocr_code_chunk_size=500,  # Маленький chunk для теста
        )

        context = MediaContext(
            media_path=Path("video.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": long_code},
            chunks=[],
            base_index=0,
        )

        new_context = step.process(context)

        # Несколько CODE чанков созданы
        assert len(new_context.chunks) >= 2

        # Все CODE типа
        for chunk in new_context.chunks:
            assert chunk.chunk_type == ChunkType.CODE
            assert chunk.metadata["language"] == "python"

    def test_markdown_mode_hierarchical_context(self):
        """Markdown режим: hierarchical_context из headers."""
        mock_parser = MagicMock()
        mock_parser.parse.return_value = [
            ParsingSegment(
                content="Content under nested headers",
                segment_type=ChunkType.TEXT,
                headers=["Chapter 1", "Section 1.1", "Subsection 1.1.1"],
                start_line=10,
                end_line=12,
            ),
        ]

        step = OCRStep(parser=mock_parser, parser_mode="markdown")

        context = MediaContext(
            media_path=Path("video.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={
                "ocr_text": "# Chapter 1\n## Section 1.1\n### Subsection 1.1.1\nContent"
            },
            chunks=[],
            base_index=0,
        )

        new_context = step.process(context)

        chunk = new_context.chunks[0]
        assert (
            chunk.metadata["hierarchical_context"]
            == "Chapter 1 > Section 1.1 > Subsection 1.1.1"
        )


class TestOCRStepCodeRatioMonitoring:
    """Тесты мониторинга code_ratio для false positives."""

    @patch("semantic_core.processing.steps.ocr.logger")
    def test_low_code_ratio_no_warning(self, mock_logger):
        """code_ratio < 50% — warning не выдаётся."""
        # 2 text, 1 code → 33%
        mock_parser = MagicMock()
        mock_parser.parse.return_value = [
            ParsingSegment(content="Text 1", segment_type=ChunkType.TEXT, headers=[]),
            ParsingSegment(content="Text 2", segment_type=ChunkType.TEXT, headers=[]),
            ParsingSegment(
                content="code",
                segment_type=ChunkType.CODE,
                language="python",
                headers=[],
            ),
        ]

        step = OCRStep(parser=mock_parser, parser_mode="markdown")

        context = MediaContext(
            media_path=Path("video.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": "Mixed"},
            chunks=[],
            base_index=0,
        )

        new_context = step.process(context)

        # Info вызван, но WARNING нет
        calls = [
            call
            for call in mock_logger.warning.call_args_list
            if "High code ratio" in str(call)
        ]
        assert len(calls) == 0

    @patch("semantic_core.processing.steps.ocr.logger")
    def test_high_code_ratio_triggers_warning(self, mock_logger):
        """code_ratio > 50% — выдаётся warning о false positives."""
        # 1 text, 3 code → 75%
        mock_parser = MagicMock()
        mock_parser.parse.return_value = [
            ParsingSegment(content="Text", segment_type=ChunkType.TEXT, headers=[]),
            ParsingSegment(
                content="code1",
                segment_type=ChunkType.CODE,
                language="python",
                headers=[],
            ),
            ParsingSegment(
                content="code2",
                segment_type=ChunkType.CODE,
                language="python",
                headers=[],
            ),
            ParsingSegment(
                content="code3",
                segment_type=ChunkType.CODE,
                language="python",
                headers=[],
            ),
        ]

        step = OCRStep(parser=mock_parser, parser_mode="markdown")

        context = MediaContext(
            media_path=Path("ui_video.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": "UI text"},
            chunks=[],
            base_index=0,
        )

        new_context = step.process(context)

        # Warning вызван
        warning_calls = [
            call
            for call in mock_logger.warning.call_args_list
            if "High code ratio" in str(call)
        ]
        assert len(warning_calls) == 1

        # Проверяем содержимое
        call_args = warning_calls[0]
        assert call_args[1]["code_ratio"] == "75.00%"
        assert call_args[1]["code_chunks"] == 3
        assert call_args[1]["total_chunks"] == 4


class TestOCRStepEdgeCases:
    """Edge cases и граничные условия."""

    def test_context_immutability(self):
        """Исходный контекст не изменяется."""
        step = OCRStep(parser=None, parser_mode="plain")

        original_context = MediaContext(
            media_path=Path("video.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": "Text"},
            chunks=[],
            base_index=0,
        )

        new_context = step.process(original_context)

        # Исходный контекст не изменился
        assert len(original_context.chunks) == 0
        assert original_context.base_index == 0

        # Новый контекст обновлён
        assert len(new_context.chunks) >= 1
        assert new_context.base_index >= 1

    def test_empty_segments_from_parser(self):
        """Если parser возвращает пустой список, создаём 0 чанков."""
        mock_parser = MagicMock()
        mock_parser.parse.return_value = []

        step = OCRStep(parser=mock_parser, parser_mode="markdown")

        context = MediaContext(
            media_path=Path("video.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": "Empty"},
            chunks=[],
            base_index=5,
        )

        new_context = step.process(context)

        # 0 чанков
        assert len(new_context.chunks) == 0
        # base_index не изменился
        assert new_context.base_index == 5
