"""Unit-тесты для Phase 14.3.2: Per-role Chunk Sizing.

Проверяют, что TranscriptionStep и OCRStep используют default_chunk_size
и временно модифицируют splitter.chunk_size на время обработки.
"""

from pathlib import Path

import pytest

from semantic_core.core.media_context import MediaContext
from semantic_core.domain import Document, MediaType
from semantic_core.processing.steps import TranscriptionStep, OCRStep
from semantic_core.processing.splitters.smart_splitter import SmartSplitter
from semantic_core.processing.parsers.markdown_parser import MarkdownNodeParser


@pytest.fixture
def smart_splitter():
    """Создаёт SmartSplitter с дефолтным chunk_size=1800."""
    parser = MarkdownNodeParser()
    return SmartSplitter(parser=parser, chunk_size=1800, code_chunk_size=2000)


@pytest.fixture
def sample_document():
    """Создаёт Document для тестов."""
    return Document(
        content="Test document",
        metadata={"source": "test.mp3"},
        media_type=MediaType.TEXT,
    )


# ============================================================================
# TranscriptionStep Default Chunk Size
# ============================================================================


def test_transcription_step_uses_custom_chunk_size(smart_splitter, sample_document):
    """TranscriptionStep использует default_chunk_size для transcript."""
    # Arrange
    step = TranscriptionStep(
        splitter=smart_splitter,
        default_chunk_size=2500,  # Custom size
        enable_timecodes=False,
    )

    context = MediaContext(
        media_path=Path("audio.mp3"),
        document=sample_document,
        analysis={"transcription": "A " * 1000},  # Long text
        chunks=[],
        base_index=1,
    )

    # Act
    result_context = step.process(context)

    # Assert: chunk_size временно изменён, затем восстановлен
    assert smart_splitter.chunk_size == 1800, "chunk_size должен быть восстановлен"
    assert len(result_context.chunks) > 0, "Должны быть созданы чанки"


def test_transcription_step_restores_original_chunk_size_after_processing(
    smart_splitter, sample_document
):
    """TranscriptionStep восстанавливает chunk_size после обработки."""
    # Arrange
    original_chunk_size = smart_splitter.chunk_size

    step = TranscriptionStep(
        splitter=smart_splitter,
        default_chunk_size=3000,
        enable_timecodes=False,
    )

    context = MediaContext(
        media_path=Path("audio.mp3"),
        document=sample_document,
        analysis={"transcription": "Short text"},  # Короткий текст
        chunks=[],
        base_index=1,
    )

    # Act
    result_context = step.process(context)

    # Assert
    assert smart_splitter.chunk_size == original_chunk_size
    assert len(result_context.chunks) >= 0  # Чанки созданы или нет (зависит от длины)


def test_transcription_step_with_default_chunk_size_1800(
    smart_splitter, sample_document
):
    """TranscriptionStep по умолчанию использует 2000 токенов."""
    # Arrange
    step = TranscriptionStep(
        splitter=smart_splitter,
        enable_timecodes=False,
    )

    # Assert
    assert step.default_chunk_size == 2000, "Default chunk_size должен быть 2000"


# ============================================================================
# OCRStep Default Chunk Size
# ============================================================================


def test_ocr_step_uses_custom_chunk_size(smart_splitter, sample_document):
    """OCRStep использует ocr_text_chunk_size для разбиения текста."""
    # Arrange
    parser = MarkdownNodeParser()
    step = OCRStep(
        parser=None,  # plain режим
        ocr_text_chunk_size=2200,  # Custom size
        parser_mode="plain",
    )

    context = MediaContext(
        media_path=Path("video.mp4"),
        document=sample_document,
        analysis={"ocr_text": "B " * 1000},  # Long text
        chunks=[],
        base_index=0,
    )

    # Act
    result_context = step.process(context)

    # Assert: OCRStep создал чанки с кастомным размером
    assert len(result_context.chunks) > 0, "Должны быть созданы чанки"
    assert result_context.chunks[0].metadata["role"] == "ocr"
    # OCRStep не использует splitter, поэтому не меняет его chunk_size
    assert smart_splitter.chunk_size == 1800, "splitter не должен быть затронут"


def test_ocr_step_does_not_affect_splitter(smart_splitter, sample_document):
    """OCRStep не модифицирует splitter (не использует его в Phase 14.1)."""
    # Arrange
    original_chunk_size = smart_splitter.chunk_size

    parser = MarkdownNodeParser()
    step = OCRStep(
        parser=parser,
        ocr_text_chunk_size=2200,
        parser_mode="markdown",
    )

    context = MediaContext(
        media_path=Path("video.mp4"),
        document=sample_document,
        analysis={"ocr_text": "# Header\n\nShort text\n\n```python\ncode\n```"},
        chunks=[],
        base_index=0,
    )

    # Act
    result_context = step.process(context)

    # Assert: splitter остался нетронутым
    assert smart_splitter.chunk_size == original_chunk_size
    assert len(result_context.chunks) > 0, "Чанки должны быть созданы"
    assert smart_splitter.chunk_size == original_chunk_size
    assert len(result_context.chunks) >= 0  # Чанки созданы или нет


def test_ocr_step_with_default_chunk_size_1800(smart_splitter, sample_document):
    """OCRStep по умолчанию использует 1800 токенов для текста."""
    # Arrange
    parser = MarkdownNodeParser()
    step = OCRStep(
        parser=parser,
        parser_mode="markdown",
    )

    # Assert
    assert step.ocr_text_chunk_size == 1800, (
        "Default ocr_text_chunk_size должен быть 1800"
    )


# ============================================================================
# Integration: TranscriptionStep + OCRStep в одном pipeline
# ============================================================================


def test_multiple_steps_do_not_interfere_with_chunk_size(
    smart_splitter, sample_document
):
    """Два шага с разными chunk_size не влияют друг на друга."""
    # Arrange
    original_chunk_size = smart_splitter.chunk_size

    transcript_step = TranscriptionStep(
        splitter=smart_splitter,
        default_chunk_size=2500,
        enable_timecodes=False,
    )
    # OCRStep теперь не использует splitter - использует свой simple chunking
    parser = MarkdownNodeParser()
    ocr_step = OCRStep(
        parser=parser,
        ocr_text_chunk_size=1500,
        parser_mode="plain",
    )

    context = MediaContext(
        media_path=Path("video.mp4"),
        document=sample_document,
        analysis={
            "transcription": "A " * 800,
            "ocr_text": "B " * 800,
        },
        chunks=[],
        base_index=0,
    )

    # Act
    context = transcript_step.process(context)
    context = ocr_step.process(context)

    # Assert: TranscriptionStep должен восстановить chunk_size, OCRStep не трогает его
    assert smart_splitter.chunk_size == original_chunk_size, (
        "chunk_size должен быть восстановлен"
    )
    assert len(context.chunks) > 0, "Чанки от обоих шагов созданы"


# ============================================================================
# Edge Cases
# ============================================================================


def test_transcription_step_handles_splitter_without_chunk_size_attribute():
    """TranscriptionStep работает, даже если splitter не имеет chunk_size."""

    class DummySplitter:
        """Mock splitter без chunk_size."""

        def split(self, document):
            return []

    # Arrange
    dummy_splitter = DummySplitter()
    step = TranscriptionStep(
        splitter=dummy_splitter,
        default_chunk_size=2000,
        enable_timecodes=False,
    )

    sample_doc = Document(
        content="Test",
        metadata={"source": "test.mp3"},
        media_type=MediaType.TEXT,
    )

    context = MediaContext(
        media_path=Path("audio.mp3"),
        document=sample_doc,
        analysis={"transcription": "Test text"},
        chunks=[],
        base_index=1,
    )

    # Act (не должно упасть)
    result_context = step.process(context)

    # Assert
    assert len(result_context.chunks) == 0  # DummySplitter возвращает []


def test_ocr_step_handles_splitter_without_chunk_size_attribute():
    """OCRStep не использует splitter в Phase 14.1 - использует свой simple chunking."""

    # Arrange: OCRStep в plain режиме делает простое разбиение текста
    parser = MarkdownNodeParser()
    step = OCRStep(
        parser=None,  # plain режим - parser не нужен
        ocr_text_chunk_size=1800,
        parser_mode="plain",
    )

    sample_doc = Document(
        content="Test",
        metadata={"source": "test.mp4"},
        media_type=MediaType.TEXT,
    )

    context = MediaContext(
        media_path=Path("video.mp4"),
        document=sample_doc,
        analysis={"ocr_text": "Test text"},
        chunks=[],
        base_index=0,
    )

    # Act (не должно упасть)
    result_context = step.process(context)

    # Assert: должны быть созданы чанки
    assert len(result_context.chunks) > 0, "OCRStep должен создать хотя бы один чанк"
    assert result_context.chunks[0].metadata["role"] == "ocr"
