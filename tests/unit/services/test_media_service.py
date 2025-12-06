"""Unit-тесты для MediaService (агрегация медиа-чанков)."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from peewee import DoesNotExist

from semantic_core.services import MediaService
from semantic_core.domain import MediaDetails, TimelineItem, Chunk, ChunkType
from semantic_core.infrastructure.storage.peewee.models import (
    DocumentModel,
    ChunkModel,
)


@pytest.fixture
def mock_document():
    """Мок документа (аудиофайл с транскрипцией)."""
    doc = MagicMock(spec=DocumentModel)
    doc.id = "doc-123"
    doc.source = "/path/to/audio.mp3"
    doc.media_type = "audio"
    doc.created_at = datetime(2025, 12, 6, 10, 0, 0)
    return doc


@pytest.fixture
def mock_summary_chunk():
    """Мок summary chunk."""
    chunk = MagicMock(spec=ChunkModel)
    chunk.id = 1
    chunk.content = "Аудиофайл о Python разработке"
    chunk.chunk_index = 0
    chunk.chunk_type = "audio_ref"
    chunk.language = None
    chunk.created_at = datetime(2025, 12, 6, 10, 0, 0)
    chunk.metadata = json.dumps({
        "role": "summary",
        "keywords": ["python", "development"],
        "duration_seconds": 180,
        "participants": ["Speaker 1"],
    })
    chunk.document.id = "doc-123"
    return chunk


@pytest.fixture
def mock_transcript_chunks():
    """Моки transcript chunks с таймкодами."""
    chunks = []
    
    # Chunk 1: [00:05]
    chunk1 = MagicMock(spec=ChunkModel)
    chunk1.id = 2
    chunk1.content = "Привет! Сегодня поговорим о Python."
    chunk1.chunk_index = 1
    chunk1.chunk_type = "text"
    chunk1.language = None
    chunk1.created_at = datetime(2025, 12, 6, 10, 0, 0)
    chunk1.metadata = json.dumps({
        "role": "transcript",
        "start_seconds": 5,
    })
    chunk1.document.id = "doc-123"
    chunks.append(chunk1)
    
    # Chunk 2: [01:30]
    chunk2 = MagicMock(spec=ChunkModel)
    chunk2.id = 3
    chunk2.content = "Давайте начнем с основ."
    chunk2.chunk_index = 2
    chunk2.chunk_type = "text"
    chunk2.language = None
    chunk2.created_at = datetime(2025, 12, 6, 10, 0, 0)
    chunk2.metadata = json.dumps({
        "role": "transcript",
        "start_seconds": 90,
    })
    chunk2.document.id = "doc-123"
    chunks.append(chunk2)
    
    return chunks


@pytest.fixture
def mock_ocr_chunk():
    """Мок OCR chunk (код)."""
    chunk = MagicMock(spec=ChunkModel)
    chunk.id = 4
    chunk.content = "def hello():\n    print('Hello')"
    chunk.chunk_index = 3
    chunk.chunk_type = "code"
    chunk.language = "python"
    chunk.created_at = datetime(2025, 12, 6, 10, 0, 0)
    chunk.metadata = json.dumps({
        "role": "ocr",
        "start_seconds": 60,
    })
    chunk.document.id = "doc-123"
    return chunk


class TestMediaService:
    """Тесты MediaService."""
    
    @patch("semantic_core.services.media_service.DocumentModel")
    @patch("semantic_core.services.media_service.ChunkModel")
    def test_get_media_details_success(
        self,
        mock_chunk_model,
        mock_doc_model,
        mock_document,
        mock_summary_chunk,
        mock_transcript_chunks,
        mock_ocr_chunk,
    ):
        """Тест успешной агрегации медиа-данных."""
        # Arrange
        mock_doc_model.get_by_id.return_value = mock_document
        
        # Имитируем Peewee QuerySet
        all_chunks = [mock_summary_chunk] + mock_transcript_chunks + [mock_ocr_chunk]
        mock_query = MagicMock()
        mock_query.__iter__ = MagicMock(return_value=iter(all_chunks))
        mock_chunk_model.select.return_value.where.return_value.order_by.return_value = mock_query
        
        service = MediaService()
        
        # Act
        details = service.get_media_details("doc-123")
        
        # Assert
        assert isinstance(details, MediaDetails)
        assert details.document_id == "doc-123"
        assert details.media_path == Path("/path/to/audio.mp3")
        assert details.media_type == "audio"
        assert details.summary == "Аудиофайл о Python разработке"
        assert details.keywords == ["python", "development"]
        assert details.duration_seconds == 180
        assert details.participants == ["Speaker 1"]
        
        # Проверяем transcript
        assert details.has_transcript
        assert len(details.transcript_chunks) == 2
        assert "Привет! Сегодня поговорим о Python." in details.full_transcript
        assert "Давайте начнем с основ." in details.full_transcript
        
        # Проверяем OCR
        assert details.has_ocr
        assert len(details.ocr_chunks) == 1
        assert "def hello():" in details.full_ocr_text
        
        # Проверяем timeline
        assert details.has_timeline
        assert len(details.timeline) == 3  # 2 transcript + 1 OCR
        assert details.timeline[0].start_seconds == 5
        assert details.timeline[1].start_seconds == 60
        assert details.timeline[2].start_seconds == 90
        
        # Проверяем total_chunks
        assert details.total_chunks == 4  # 1 summary + 2 transcript + 1 OCR
    
    @patch("semantic_core.services.media_service.DocumentModel")
    def test_get_media_details_document_not_found(self, mock_doc_model):
        """Тест: документ не найден."""
        # Arrange
        mock_doc_model.get_by_id.side_effect = DoesNotExist
        service = MediaService()
        
        # Act & Assert
        with pytest.raises(ValueError, match="Document doc-999 not found"):
            service.get_media_details("doc-999")
    
    @patch("semantic_core.services.media_service.DocumentModel")
    def test_get_media_details_not_media_file(self, mock_doc_model):
        """Тест: документ не является медиа-файлом."""
        # Arrange
        doc = MagicMock(spec=DocumentModel)
        doc.media_type = "text"  # Не медиа
        mock_doc_model.get_by_id.return_value = doc
        service = MediaService()
        
        # Act & Assert
        with pytest.raises(ValueError, match="is not a media file"):
            service.get_media_details("doc-123")
    
    @patch("semantic_core.services.media_service.DocumentModel")
    @patch("semantic_core.services.media_service.ChunkModel")
    def test_get_media_details_no_summary_chunk(
        self,
        mock_chunk_model,
        mock_doc_model,
        mock_document,
        mock_transcript_chunks,
    ):
        """Тест: нет summary chunk (ошибка)."""
        # Arrange
        mock_doc_model.get_by_id.return_value = mock_document
        
        # Только transcript chunks (нет summary)
        mock_query = MagicMock()
        mock_query.__iter__ = MagicMock(return_value=iter(mock_transcript_chunks))
        mock_chunk_model.select.return_value.where.return_value.order_by.return_value = mock_query
        
        service = MediaService()
        
        # Act & Assert
        with pytest.raises(ValueError, match="has no summary chunk"):
            service.get_media_details("doc-123")
    
    @patch("semantic_core.services.media_service.DocumentModel")
    @patch("semantic_core.services.media_service.ChunkModel")
    def test_get_media_details_include_filters(
        self,
        mock_chunk_model,
        mock_doc_model,
        mock_document,
        mock_summary_chunk,
        mock_transcript_chunks,
        mock_ocr_chunk,
    ):
        """Тест фильтров include_transcript / include_ocr."""
        # Arrange
        mock_doc_model.get_by_id.return_value = mock_document
        all_chunks = [mock_summary_chunk] + mock_transcript_chunks + [mock_ocr_chunk]
        mock_query = MagicMock()
        mock_query.__iter__ = MagicMock(return_value=iter(all_chunks))
        mock_chunk_model.select.return_value.where.return_value.order_by.return_value = mock_query
        
        service = MediaService()
        
        # Act: только summary (без transcript и OCR)
        details = service.get_media_details(
            "doc-123",
            include_transcript=False,
            include_ocr=False,
        )
        
        # Assert
        assert not details.has_transcript
        assert not details.has_ocr
        assert not details.has_timeline
        assert details.total_chunks == 1  # Только summary
    
    @patch("semantic_core.services.media_service.DocumentModel")
    @patch("semantic_core.services.media_service.ChunkModel")
    def test_get_timeline_success(
        self,
        mock_chunk_model,
        mock_doc_model,
        mock_document,
        mock_summary_chunk,
        mock_transcript_chunks,
        mock_ocr_chunk,
    ):
        """Тест получения timeline."""
        # Arrange
        mock_doc_model.get_by_id.return_value = mock_document
        all_chunks = [mock_summary_chunk] + mock_transcript_chunks + [mock_ocr_chunk]
        mock_query = MagicMock()
        mock_query.__iter__ = MagicMock(return_value=iter(all_chunks))
        mock_chunk_model.select.return_value.where.return_value.order_by.return_value = mock_query
        
        service = MediaService()
        
        # Act
        timeline = service.get_timeline("doc-123")
        
        # Assert
        assert len(timeline) == 3  # 2 transcript + 1 OCR
        assert all(isinstance(item, TimelineItem) for item in timeline)
        
        # Проверяем сортировку по времени
        assert timeline[0].start_seconds == 5
        assert timeline[1].start_seconds == 60
        assert timeline[2].start_seconds == 90
        
        # Проверяем formatted_time
        assert timeline[0].formatted_time == "00:05"
        assert timeline[1].formatted_time == "01:00"
        assert timeline[2].formatted_time == "01:30"
    
    @patch("semantic_core.services.media_service.DocumentModel")
    @patch("semantic_core.services.media_service.ChunkModel")
    def test_get_timeline_with_role_filter(
        self,
        mock_chunk_model,
        mock_doc_model,
        mock_document,
        mock_summary_chunk,
        mock_transcript_chunks,
        mock_ocr_chunk,
    ):
        """Тест фильтрации timeline по role."""
        # Arrange
        mock_doc_model.get_by_id.return_value = mock_document
        all_chunks = [mock_summary_chunk] + mock_transcript_chunks + [mock_ocr_chunk]
        mock_query = MagicMock()
        mock_query.__iter__ = MagicMock(return_value=iter(all_chunks))
        mock_chunk_model.select.return_value.where.return_value.order_by.return_value = mock_query
        
        service = MediaService()
        
        # Act: только transcript
        timeline = service.get_timeline("doc-123", role_filter="transcript")
        
        # Assert
        assert len(timeline) == 2  # Только transcript chunks
        assert all(item.role == "transcript" for item in timeline)
    
    @patch("semantic_core.services.media_service.DocumentModel")
    @patch("semantic_core.services.media_service.ChunkModel")
    def test_get_chunks_by_role(
        self,
        mock_chunk_model,
        mock_doc_model,
        mock_document,
        mock_summary_chunk,
        mock_transcript_chunks,
    ):
        """Тест получения чанков по роли."""
        # Arrange
        mock_doc_model.get_by_id.return_value = mock_document
        chunks = [mock_summary_chunk] + mock_transcript_chunks
        mock_query = MagicMock()
        mock_query.__iter__ = MagicMock(return_value=iter(chunks))
        mock_chunk_model.select.return_value.where.return_value.order_by.return_value = mock_query
        
        service = MediaService()
        
        # Act
        transcript_chunks = service.get_chunks_by_role("doc-123", "transcript")
        
        # Assert
        assert len(transcript_chunks) == 2
        assert all(isinstance(c, Chunk) for c in transcript_chunks)
        assert all(c.metadata["role"] == "transcript" for c in transcript_chunks)
    
    def test_timeline_item_formatted_time(self):
        """Тест форматирования времени."""
        # Arrange & Act
        item_short = TimelineItem(
            chunk_id="1",
            start_seconds=65,  # 01:05
            content_preview="Test",
            role="transcript",
            chunk_type="text",
        )
        
        item_long = TimelineItem(
            chunk_id="2",
            start_seconds=3665,  # 1:01:05
            content_preview="Test",
            role="transcript",
            chunk_type="text",
        )
        
        # Assert
        assert item_short.formatted_time == "01:05"
        assert item_long.formatted_time == "1:01:05"
