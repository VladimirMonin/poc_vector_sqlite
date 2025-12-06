"""Тесты для OCRStep — разбивка OCR текста на чанки.

Тестируются:
- should_run() логика (есть/нет ocr_text)
- Разбивка через mock splitter
- Режимы парсинга (markdown/plain)
- Мониторинг code_ratio (false positives)
- Обогащение metadata (role='ocr', parent_media_path)
- base_index корректно увеличивается
- Immutability контекста
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from semantic_core.core.media_context import MediaContext
from semantic_core.domain import Chunk, ChunkType, Document, MediaType
from semantic_core.processing.steps.ocr import OCRStep


class TestOCRStepShouldRun:
    """Тесты для should_run() логики."""
    
    def test_should_run_with_ocr_text(self):
        """Шаг должен выполняться при наличии ocr_text."""
        splitter = MagicMock()
        step = OCRStep(splitter=splitter)
        
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
        splitter = MagicMock()
        step = OCRStep(splitter=splitter)
        
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
        splitter = MagicMock()
        step = OCRStep(splitter=splitter)
        
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
        splitter = MagicMock()
        step = OCRStep(splitter=splitter)
        assert step.step_name == "ocr"
    
    def test_is_optional_false(self):
        """OCRStep критичен по умолчанию."""
        splitter = MagicMock()
        step = OCRStep(splitter=splitter)
        assert step.is_optional is False
    
    def test_default_parser_mode_markdown(self):
        """По умолчанию parser_mode='markdown'."""
        splitter = MagicMock()
        step = OCRStep(splitter=splitter)
        assert step.parser_mode == "markdown"
    
    def test_custom_parser_mode_plain(self):
        """Можно установить parser_mode='plain'."""
        splitter = MagicMock()
        step = OCRStep(splitter=splitter, parser_mode="plain")
        assert step.parser_mode == "plain"


class TestOCRStepProcessing:
    """Тесты обработки OCR текста."""
    
    def test_single_chunk_ocr(self):
        """OCR текст режется на 1 чанк."""
        # Mock splitter возвращает 1 chunk
        mock_chunk = Chunk(
            content="Recognized text from video",
            chunk_index=0,  # Будет перезаписан
            chunk_type=ChunkType.TEXT,
            metadata={},
        )
        
        mock_splitter = MagicMock()
        mock_splitter.split.return_value = [mock_chunk]
        
        step = OCRStep(splitter=mock_splitter, parser_mode="markdown")
        
        context = MediaContext(
            media_path=Path("screencast.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": "Recognized text from video"},
            chunks=[],
            base_index=3,  # После summary + transcript chunks
        )
        
        new_context = step.process(context)
        
        # Проверяем что splitter вызван
        mock_splitter.split.assert_called_once()
        
        # Проверяем временный Document
        temp_doc = mock_splitter.split.call_args[0][0]
        assert temp_doc.content == "Recognized text from video"
        assert temp_doc.media_type == MediaType.TEXT  # Всегда TEXT, parser_mode влияет на логику splitter
        assert temp_doc.metadata["source"] == "screencast.mp4"
        
        # Проверяем результат
        assert len(new_context.chunks) == 1
        chunk = new_context.chunks[0]
        
        # chunk_index должен быть base_index
        assert chunk.chunk_index == 3
        
        # Metadata обогащена
        assert chunk.metadata["role"] == "ocr"
        assert chunk.metadata["parent_media_path"] == "screencast.mp4"
        assert chunk.metadata["_original_path"] == "screencast.mp4"
        
        # base_index увеличился
        assert new_context.base_index == 4
    
    def test_multi_chunk_ocr(self):
        """Длинный OCR текст режется на несколько чанков."""
        # Mock splitter возвращает 4 chunks
        mock_chunks = [
            Chunk(
                content=f"OCR chunk {i}",
                chunk_index=0,  # Будет перезаписан
                chunk_type=ChunkType.TEXT,
                metadata={},
            )
            for i in range(4)
        ]
        
        mock_splitter = MagicMock()
        mock_splitter.split.return_value = mock_chunks
        
        step = OCRStep(splitter=mock_splitter)
        
        context = MediaContext(
            media_path=Path("tutorial.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": "Very long OCR text from video..."},
            chunks=[],
            base_index=10,
        )
        
        new_context = step.process(context)
        
        # 4 чанка созданы
        assert len(new_context.chunks) == 4
        
        # chunk_index правильно проставлены (10, 11, 12, 13)
        assert new_context.chunks[0].chunk_index == 10
        assert new_context.chunks[1].chunk_index == 11
        assert new_context.chunks[2].chunk_index == 12
        assert new_context.chunks[3].chunk_index == 13
        
        # Все имеют role='ocr'
        for chunk in new_context.chunks:
            assert chunk.metadata["role"] == "ocr"
            assert chunk.metadata["parent_media_path"] == "tutorial.mp4"
        
        # base_index увеличился на 4
        assert new_context.base_index == 14
    
    def test_parser_mode_plain_sets_media_type_text(self):
        """parser_mode='plain' устанавливает MediaType.TEXT."""
        mock_chunk = Chunk(
            content="OCR text",
            chunk_index=0,
            chunk_type=ChunkType.TEXT,
            metadata={},
        )
        
        mock_splitter = MagicMock()
        mock_splitter.split.return_value = [mock_chunk]
        
        step = OCRStep(splitter=mock_splitter, parser_mode="plain")
        
        context = MediaContext(
            media_path=Path("video.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": "OCR text"},
            chunks=[],
            base_index=0,
        )
        
        new_context = step.process(context)
        
        # Проверяем временный Document
        temp_doc = mock_splitter.split.call_args[0][0]
        assert temp_doc.media_type == MediaType.TEXT  # parser_mode='plain'
    
    def test_metadata_enrichment(self):
        """Проверяем обогащение metadata."""
        # Chunk со своими metadata
        mock_chunk = Chunk(
            content="OCR text",
            chunk_index=0,
            chunk_type=ChunkType.TEXT,
            metadata={"custom_field": "value"},
        )
        
        mock_splitter = MagicMock()
        mock_splitter.split.return_value = [mock_chunk]
        
        step = OCRStep(splitter=mock_splitter)
        
        context = MediaContext(
            media_path=Path("/data/screencast.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": "OCR text"},
            chunks=[],
            base_index=0,
        )
        
        new_context = step.process(context)
        chunk = new_context.chunks[0]
        
        # Исходные metadata сохранены
        assert chunk.metadata["custom_field"] == "value"
        
        # Добавлены новые
        assert chunk.metadata["role"] == "ocr"
        assert chunk.metadata["parent_media_path"] == str(Path("/data/screencast.mp4"))
        assert chunk.metadata["_original_path"] == str(Path("/data/screencast.mp4"))


class TestOCRStepCodeRatioMonitoring:
    """Тесты мониторинга code_ratio для false positives."""
    
    @patch("semantic_core.processing.steps.ocr.logger")
    def test_low_code_ratio_no_warning(self, mock_logger):
        """code_ratio < 50% — warning не выдаётся."""
        # 2 text chunks, 1 code chunk → code_ratio = 33%
        mock_chunks = [
            Chunk(content="Text 1", chunk_index=0, chunk_type=ChunkType.TEXT, metadata={}),
            Chunk(content="Text 2", chunk_index=1, chunk_type=ChunkType.TEXT, metadata={}),
            Chunk(content="Code 1", chunk_index=2, chunk_type=ChunkType.CODE, metadata={}),
        ]
        
        mock_splitter = MagicMock()
        mock_splitter.split.return_value = mock_chunks
        
        step = OCRStep(splitter=mock_splitter)
        
        context = MediaContext(
            media_path=Path("video.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": "Mixed text and code"},
            chunks=[],
            base_index=0,
        )
        
        new_context = step.process(context)
        
        # Warning НЕ вызван
        mock_logger.warning.assert_not_called()
    
    @patch("semantic_core.processing.steps.ocr.logger")
    def test_high_code_ratio_triggers_warning(self, mock_logger):
        """code_ratio > 50% — выдаётся warning о false positives."""
        # 1 text chunk, 3 code chunks → code_ratio = 75%
        mock_chunks = [
            Chunk(content="Text", chunk_index=0, chunk_type=ChunkType.TEXT, metadata={}),
            Chunk(content="Code 1", chunk_index=1, chunk_type=ChunkType.CODE, metadata={}),
            Chunk(content="Code 2", chunk_index=2, chunk_type=ChunkType.CODE, metadata={}),
            Chunk(content="Code 3", chunk_index=3, chunk_type=ChunkType.CODE, metadata={}),
        ]
        
        mock_splitter = MagicMock()
        mock_splitter.split.return_value = mock_chunks
        
        step = OCRStep(splitter=mock_splitter)
        
        context = MediaContext(
            media_path=Path("ui_video.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"ocr_text": "UI buttons and text"},
            chunks=[],
            base_index=0,
        )
        
        new_context = step.process(context)
        
        # Warning вызван
        mock_logger.warning.assert_called_once()
        
        # Проверяем содержимое warning
        call_args = mock_logger.warning.call_args
        assert "High code ratio detected" in call_args[0][0]
        assert call_args[1]["code_ratio"] == "75.00%"
        assert call_args[1]["code_chunks"] == 3
        assert call_args[1]["total_chunks"] == 4


class TestOCRStepEdgeCases:
    """Edge cases и граничные условия."""
    
    def test_context_immutability(self):
        """Исходный контекст не изменяется."""
        mock_chunk = Chunk(
            content="OCR text",
            chunk_index=0,
            chunk_type=ChunkType.TEXT,
            metadata={},
        )
        
        mock_splitter = MagicMock()
        mock_splitter.split.return_value = [mock_chunk]
        
        step = OCRStep(splitter=mock_splitter)
        
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
        assert len(new_context.chunks) == 1
        assert new_context.base_index == 1
    
    def test_metadata_no_overwrite_original_path(self):
        """Если _original_path уже есть, не перезаписываем."""
        mock_chunk = Chunk(
            content="OCR text",
            chunk_index=0,
            chunk_type=ChunkType.TEXT,
            metadata={"_original_path": "/custom/path.mp4"},
        )
        
        mock_splitter = MagicMock()
        mock_splitter.split.return_value = [mock_chunk]
        
        step = OCRStep(splitter=mock_splitter)
        
        context = MediaContext(
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
        
        new_context = step.process(context)
        chunk = new_context.chunks[0]
        
        # _original_path не перезаписан
        assert chunk.metadata["_original_path"] == "/custom/path.mp4"
