"""Unit-тесты для MediaService.reprocess_document() (Phase 14.3.3).

Проверяют логику повторного анализа медиа-файлов с новыми custom_instructions.
"""

import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

import pytest

from semantic_core.domain import Document, Chunk, ChunkType, MediaType
from semantic_core.services.media_service import MediaService


@pytest.fixture
def mock_store():
    """Mock BaseVectorStore."""
    store = Mock()
    store.save = Mock()
    return store


@pytest.fixture
def mock_splitter():
    """Mock BaseSplitter."""
    splitter = Mock()
    splitter.chunk_size = 1800
    splitter.code_chunk_size = 2000
    
    # Всегда возвращает 1 чанк
    def split_side_effect(document):
        return [
            Chunk(
                content=document.content,
                chunk_index=0,
                chunk_type=ChunkType.TEXT,
            )
        ]
    
    splitter.split = Mock(side_effect=split_side_effect)
    return splitter


@pytest.fixture
def mock_config():
    """Mock SemanticConfig."""
    config = Mock()
    config.media.chunk_sizes.transcript_chunk_size = 2000
    config.media.chunk_sizes.ocr_text_chunk_size = 1800
    config.media.processing.enable_timecodes = True
    config.media.processing.ocr_parser_mode = "markdown"
    return config


@pytest.fixture
def mock_image_analyzer():
    """Mock GeminiImageAnalyzer."""
    analyzer = Mock()
    analyzer.analyze = Mock(return_value={
        "description": "New image description",
        "keywords": ["new", "test"],
    })
    return analyzer


@pytest.fixture
def mock_audio_analyzer():
    """Mock GeminiAudioAnalyzer."""
    analyzer = Mock()
    analyzer.analyze = Mock(return_value={
        "description": "New audio summary",
        "transcription": "New transcript text",
        "keywords": ["audio", "new"],
    })
    return analyzer


@pytest.fixture
def mock_video_analyzer():
    """Mock GeminiVideoAnalyzer."""
    analyzer = Mock()
    analyzer.analyze = Mock(return_value={
        "description": "New video summary",
        "transcription": "New video transcript",
        "ocr_text": "New OCR text",
        "keywords": ["video", "new"],
    })
    return analyzer


# ============================================================================
# MediaService.reprocess_document() Tests
# ============================================================================


def test_reprocess_document_requires_dependencies():
    """reprocess_document() выбрасывает ValueError если нет зависимостей."""
    # Arrange
    service = MediaService()  # Без аргументов
    
    # Act & Assert
    with pytest.raises(ValueError, match="requires splitter, store, and config"):
        service.reprocess_document(document_id="doc-123")


@patch("semantic_core.services.media_service.DocumentModel")
def test_reprocess_document_not_found(
    mock_document_model,
    mock_splitter,
    mock_store,
    mock_config,
):
    """reprocess_document() выбрасывает ValueError если документ не найден."""
    # Arrange
    from peewee import DoesNotExist
    
    mock_document_model.get_by_id = Mock(side_effect=DoesNotExist)
    
    service = MediaService(
        splitter=mock_splitter,
        store=mock_store,
        config=mock_config,
    )
    
    # Act & Assert
    with pytest.raises(ValueError, match="Document doc-123 not found"):
        service.reprocess_document(document_id="doc-123")


@patch("semantic_core.services.media_service.DocumentModel")
def test_reprocess_document_not_media_file(
    mock_document_model,
    mock_splitter,
    mock_store,
    mock_config,
):
    """reprocess_document() выбрасывает ValueError если не медиа-файл."""
    # Arrange
    doc_model = Mock()
    doc_model.id = "doc-123"
    doc_model.media_type = "text"  # NOT media
    
    mock_document_model.get_by_id = Mock(return_value=doc_model)
    
    service = MediaService(
        splitter=mock_splitter,
        store=mock_store,
        config=mock_config,
    )
    
    # Act & Assert
    with pytest.raises(ValueError, match="is not a media file"):
        service.reprocess_document(document_id="doc-123")


@patch("semantic_core.services.media_service.DocumentModel")
def test_reprocess_document_missing_source_metadata(
    mock_document_model,
    mock_splitter,
    mock_store,
    mock_config,
):
    """reprocess_document() выбрасывает ValueError если нет source в metadata."""
    # Arrange
    doc_model = Mock()
    doc_model.id = "doc-123"
    doc_model.media_type = "audio"
    doc_model.metadata = json.dumps({})  # No "source" key
    
    mock_document_model.get_by_id = Mock(return_value=doc_model)
    
    service = MediaService(
        splitter=mock_splitter,
        store=mock_store,
        config=mock_config,
    )
    
    # Act & Assert
    with pytest.raises(ValueError, match="has no 'source' in metadata"):
        service.reprocess_document(document_id="doc-123")


@patch("semantic_core.services.media_service.DocumentModel")
def test_reprocess_document_file_not_found(
    mock_document_model,
    mock_splitter,
    mock_store,
    mock_config,
):
    """reprocess_document() выбрасывает FileNotFoundError если файл не существует."""
    # Arrange
    doc_model = Mock()
    doc_model.id = "doc-123"
    doc_model.media_type = "audio"
    doc_model.metadata = json.dumps({"source": "/nonexistent/file.mp3"})
    
    mock_document_model.get_by_id = Mock(return_value=doc_model)
    
    service = MediaService(
        splitter=mock_splitter,
        store=mock_store,
        config=mock_config,
    )
    
    # Act & Assert
    with pytest.raises(FileNotFoundError, match="Media file not found"):
        service.reprocess_document(document_id="doc-123")


@patch("semantic_core.services.media_service.ChunkModel")
@patch("semantic_core.services.media_service.DocumentModel")
@patch("semantic_core.services.media_service.Path")
def test_reprocess_document_audio_success(
    mock_path_class,
    mock_document_model,
    mock_chunk_model,
    mock_splitter,
    mock_store,
    mock_config,
    mock_audio_analyzer,
):
    """reprocess_document() успешно переобрабатывает аудио."""
    # Arrange
    doc_model = Mock()
    doc_model.id = "doc-123"
    doc_model.media_type = "audio"
    doc_model.metadata = json.dumps({"source": "/test/audio.mp3"})
    
    mock_document_model.get_by_id = Mock(return_value=doc_model)
    
    # Mock Path.exists() → True
    mock_path_instance = Mock()
    mock_path_instance.exists = Mock(return_value=True)
    mock_path_class.return_value = mock_path_instance
    
    # Mock удаление чанков
    mock_chunk_query = Mock()
    mock_chunk_query.where = Mock(return_value=[])  # Return empty list (no old chunks)
    mock_chunk_model.select = Mock(return_value=mock_chunk_query)
    
    service = MediaService(
        audio_analyzer=mock_audio_analyzer,
        splitter=mock_splitter,
        store=mock_store,
        config=mock_config,
    )
    
    # Act
    result = service.reprocess_document(
        document_id="doc-123",
        custom_instructions="Extract medical terms",
    )
    
    # Assert
    assert result.id == "doc-123"
    assert mock_audio_analyzer.analyze.called
    assert mock_store.save.called


@patch("semantic_core.services.media_service.ChunkModel")
@patch("semantic_core.services.media_service.DocumentModel")
@patch("semantic_core.services.media_service.Path")
def test_reprocess_document_deletes_old_chunks(
    mock_path_class,
    mock_document_model,
    mock_chunk_model,
    mock_splitter,
    mock_store,
    mock_config,
    mock_audio_analyzer,
):
    """reprocess_document() удаляет старые медиа-чанки перед созданием новых."""
    # Arrange
    doc_model = Mock()
    doc_model.id = "doc-123"
    doc_model.media_type = "audio"
    doc_model.metadata = json.dumps({"source": "/test/audio.mp3"})
    
    mock_document_model.get_by_id = Mock(return_value=doc_model)
    
    # Mock Path
    mock_path_instance = Mock()
    mock_path_instance.exists = Mock(return_value=True)
    mock_path_class.return_value = mock_path_instance
    
    # Mock старые чанки
    old_chunk1 = Mock()
    old_chunk1.metadata = json.dumps({"role": "summary"})
    old_chunk1.delete_instance = Mock()
    
    old_chunk2 = Mock()
    old_chunk2.metadata = json.dumps({"role": "transcript"})
    old_chunk2.delete_instance = Mock()
    
    mock_chunk_query = Mock()
    mock_chunk_query.where = Mock(return_value=[old_chunk1, old_chunk2])  # Return list of chunks
    mock_chunk_model.select = Mock(return_value=mock_chunk_query)
    
    service = MediaService(
        audio_analyzer=mock_audio_analyzer,
        splitter=mock_splitter,
        store=mock_store,
        config=mock_config,
    )
    
    # Act
    service.reprocess_document(document_id="doc-123")
    
    # Assert
    assert old_chunk1.delete_instance.called
    assert old_chunk2.delete_instance.called


@patch("semantic_core.services.media_service.ChunkModel")
@patch("semantic_core.services.media_service.DocumentModel")
@patch("semantic_core.services.media_service.Path")
def test_reprocess_document_calls_correct_analyzer(
    mock_path_class,
    mock_document_model,
    mock_chunk_model,
    mock_splitter,
    mock_store,
    mock_config,
    mock_image_analyzer,
    mock_audio_analyzer,
    mock_video_analyzer,
):
    """reprocess_document() вызывает правильный analyzer по media_type."""
    # Arrange
    doc_model = Mock()
    doc_model.id = "doc-123"
    doc_model.media_type = "video"  # VIDEO
    doc_model.metadata = json.dumps({"source": "/test/video.mp4"})
    
    mock_document_model.get_by_id = Mock(return_value=doc_model)
    
    # Mock Path
    mock_path_instance = Mock()
    mock_path_instance.exists = Mock(return_value=True)
    mock_path_class.return_value = mock_path_instance
    
    # Mock chunks
    mock_chunk_query = Mock()
    mock_chunk_query.where = Mock(return_value=[])  # Empty list
    mock_chunk_model.select = Mock(return_value=mock_chunk_query)
    
    service = MediaService(
        image_analyzer=mock_image_analyzer,
        audio_analyzer=mock_audio_analyzer,
        video_analyzer=mock_video_analyzer,
        splitter=mock_splitter,
        store=mock_store,
        config=mock_config,
    )
    
    # Act
    service.reprocess_document(document_id="doc-123")
    
    # Assert
    assert mock_video_analyzer.analyze.called
    assert not mock_audio_analyzer.analyze.called
    assert not mock_image_analyzer.analyze.called


@patch("semantic_core.services.media_service.ChunkModel")
@patch("semantic_core.services.media_service.DocumentModel")
@patch("semantic_core.services.media_service.Path")
def test_reprocess_document_no_analyzer_raises_error(
    mock_path_class,
    mock_document_model,
    mock_chunk_model,
    mock_splitter,
    mock_store,
    mock_config,
):
    """reprocess_document() выбрасывает ValueError если нет analyzer."""
    # Arrange
    doc_model = Mock()
    doc_model.id = "doc-123"
    doc_model.media_type = "audio"
    doc_model.metadata = json.dumps({"source": "/test/audio.mp3"})
    
    mock_document_model.get_by_id = Mock(return_value=doc_model)
    
    # Mock Path
    mock_path_instance = Mock()
    mock_path_instance.exists = Mock(return_value=True)
    mock_path_class.return_value = mock_path_instance
    
    # Mock chunks
    mock_chunk_query = Mock()
    mock_chunk_query.where = Mock(return_value=[])  # Empty list
    mock_chunk_model.select = Mock(return_value=mock_chunk_query)
    
    # Service БЕЗ analyzers
    service = MediaService(
        splitter=mock_splitter,
        store=mock_store,
        config=mock_config,
    )
    
    # Act & Assert
    with pytest.raises(ValueError, match="No analyzer available"):
        service.reprocess_document(document_id="doc-123")
