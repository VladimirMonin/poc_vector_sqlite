"""Интеграционные тесты SemanticCore для аудио и видео."""

import pytest
from unittest.mock import patch, MagicMock

from semantic_core.pipeline import SemanticCore
from semantic_core.domain import MediaConfig, MediaAnalysisResult
from semantic_core.infrastructure.storage.peewee.models import MediaTaskModel


class TestSemanticCoreAudioIngestion:
    """Тесты ingest_audio() в SemanticCore."""

    @pytest.fixture
    def mock_audio_analyzer(self):
        """Mock для GeminiAudioAnalyzer."""
        long_transcript = " ".join(
            [
                "This is a long audio transcript fragment that repeats to force splitting"
                for _ in range(80)
            ]
        )
        analyzer = MagicMock()
        analyzer.analyze.return_value = MediaAnalysisResult(
            description="Test audio summary about document review.",
            transcription=long_transcript,
            participants=["Speaker 1"],
            action_items=["Review the document"],
            duration_seconds=30.0,
        )
        return analyzer

    @pytest.fixture
    def core_with_audio_analyzer(self, mock_embedder, media_db, mock_audio_analyzer):
        """SemanticCore с настроенным audio analyzer."""
        from semantic_core import (
            PeeweeVectorStore,
            SimpleSplitter,
            BasicContextStrategy,
        )

        store = PeeweeVectorStore(media_db)
        splitter = SimpleSplitter(chunk_size=500)
        context_strategy = BasicContextStrategy()
        media_config = MediaConfig(rpm_limit=60)

        core = SemanticCore(
            embedder=mock_embedder,
            store=store,
            splitter=splitter,
            context_strategy=context_strategy,
            audio_analyzer=mock_audio_analyzer,
            media_config=media_config,
        )

        return core

    @pytest.fixture
    def test_audio_path(self, tmp_path):
        """Создаёт тестовый аудиофайл."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"dummy audio content")
        return audio_file

    @patch(
        "semantic_core.infrastructure.media.utils.files.get_file_mime_type",
        return_value="audio/mpeg",
    )
    @patch(
        "semantic_core.infrastructure.media.utils.audio.is_audio_supported",
        return_value=True,
    )
    def test_ingest_audio_sync_success(
        self, mock_is_supported, mock_mime, core_with_audio_analyzer, test_audio_path
    ):
        """Sync mode: успешная индексация аудио создаёт searchable документ."""
        from semantic_core.infrastructure.storage.peewee.models import (
            DocumentModel,
            ChunkModel,
        )

        document_id = core_with_audio_analyzer.ingest_audio(
            path=str(test_audio_path),
            mode="sync",
        )

        assert document_id is not None
        assert isinstance(document_id, str)

        # Документ создан с media_type=audio
        doc = DocumentModel.get_by_id(int(document_id))
        assert doc is not None
        assert doc.media_type == "audio"

        # Есть summary + несколько чанков транскрипции
        chunks = list(
            ChunkModel.select()
            .where(ChunkModel.document_id == int(document_id))
            .order_by(ChunkModel.chunk_index)
        )
        assert len(chunks) >= 2

        import json

        summary_chunk = chunks[0]
        summary_meta = json.loads(summary_chunk.metadata)
        assert summary_chunk.chunk_type == "audio_ref"
        assert summary_chunk.embedding_status == "READY"
        assert summary_meta.get("role") == "summary"

        transcript_chunks = [
            chunk
            for chunk in chunks
            if json.loads(chunk.metadata).get("role") == "transcript"
        ]
        assert transcript_chunks
        assert all(chunk.chunk_type == "text" for chunk in transcript_chunks)
        assert all(chunk.embedding_status == "READY" for chunk in chunks)

    @patch(
        "semantic_core.infrastructure.media.utils.files.get_file_mime_type",
        return_value="audio/mpeg",
    )
    @patch(
        "semantic_core.infrastructure.media.utils.audio.is_audio_supported",
        return_value=True,
    )
    def test_ingest_audio_async_returns_task_id(
        self, mock_is_supported, mock_mime, core_with_audio_analyzer, test_audio_path
    ):
        """Async mode: возвращает task_id."""
        task_id = core_with_audio_analyzer.ingest_audio(
            path=str(test_audio_path),
            mode="async",
        )

        assert task_id is not None

        # Задача в БД со статусом pending
        task = MediaTaskModel.get_by_id(task_id)
        assert task.status == "pending"

    def test_ingest_audio_without_analyzer_raises(self, mock_embedder, media_db):
        """Без audio_analyzer выбрасывает RuntimeError."""
        from semantic_core import (
            PeeweeVectorStore,
            SimpleSplitter,
            BasicContextStrategy,
        )

        store = PeeweeVectorStore(media_db)
        core = SemanticCore(
            embedder=mock_embedder,
            store=store,
            splitter=SimpleSplitter(),
            context_strategy=BasicContextStrategy(),
            audio_analyzer=None,  # Явно None
        )

        with pytest.raises(RuntimeError, match="audio_analyzer not configured"):
            core.ingest_audio(path="test.mp3", mode="sync")


class TestSemanticCoreVideoIngestion:
    """Тесты ingest_video() в SemanticCore."""

    @pytest.fixture
    def mock_video_analyzer(self):
        """Mock для GeminiVideoAnalyzer."""
        long_transcript = " ".join(
            [
                "Video narration continues with detailed description of scenes and actions"
                for _ in range(80)
            ]
        )
        analyzer = MagicMock()
        analyzer.analyze.return_value = MediaAnalysisResult(
            description="A video showing a person walking in the park.",
            transcription=long_transcript,
            keywords=["park", "walking", "nature"],
            duration_seconds=120.0,
        )
        return analyzer

    @pytest.fixture
    def core_with_video_analyzer(self, mock_embedder, media_db, mock_video_analyzer):
        """SemanticCore с настроенным video analyzer."""
        from semantic_core import (
            PeeweeVectorStore,
            SimpleSplitter,
            BasicContextStrategy,
        )

        store = PeeweeVectorStore(media_db)
        splitter = SimpleSplitter(chunk_size=500)
        context_strategy = BasicContextStrategy()
        media_config = MediaConfig(rpm_limit=60)

        core = SemanticCore(
            embedder=mock_embedder,
            store=store,
            splitter=splitter,
            context_strategy=context_strategy,
            video_analyzer=mock_video_analyzer,
            media_config=media_config,
        )

        return core

    @pytest.fixture
    def test_video_path(self, tmp_path):
        """Создаёт тестовый видеофайл."""
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"dummy video content")
        return video_file

    @patch(
        "semantic_core.infrastructure.media.utils.files.get_file_mime_type",
        return_value="video/mp4",
    )
    @patch(
        "semantic_core.infrastructure.media.utils.video.is_video_supported",
        return_value=True,
    )
    def test_ingest_video_sync_success(
        self, mock_is_supported, mock_mime, core_with_video_analyzer, test_video_path
    ):
        """Sync mode: успешная индексация видео создаёт searchable документ."""
        from semantic_core.infrastructure.storage.peewee.models import (
            DocumentModel,
            ChunkModel,
        )

        document_id = core_with_video_analyzer.ingest_video(
            path=str(test_video_path),
            mode="sync",
        )

        assert document_id is not None
        assert isinstance(document_id, str)

        # Документ создан с media_type=video
        doc = DocumentModel.get_by_id(int(document_id))
        assert doc is not None
        assert doc.media_type == "video"

        # Есть summary + транскрипция, разбитая на несколько чанков
        chunks = list(
            ChunkModel.select()
            .where(ChunkModel.document_id == int(document_id))
            .order_by(ChunkModel.chunk_index)
        )
        assert len(chunks) >= 2

        summary_chunk = chunks[0]
        assert summary_chunk.chunk_type == "video_ref"
        assert summary_chunk.metadata.get("role") == "summary"
        assert summary_chunk.embedding_status == "READY"

        transcript_chunks = [
            chunk for chunk in chunks if chunk.metadata.get("role") == "transcript"
        ]
        assert transcript_chunks
        assert all(chunk.chunk_type == "text" for chunk in transcript_chunks)
        assert all(chunk.embedding_status == "READY" for chunk in chunks)

    @patch(
        "semantic_core.infrastructure.media.utils.files.get_file_mime_type",
        return_value="video/mp4",
    )
    @patch(
        "semantic_core.infrastructure.media.utils.video.is_video_supported",
        return_value=True,
    )
    def test_ingest_video_async_returns_task_id(
        self, mock_is_supported, mock_mime, core_with_video_analyzer, test_video_path
    ):
        """Async mode: возвращает task_id."""
        task_id = core_with_video_analyzer.ingest_video(
            path=str(test_video_path),
            mode="async",
        )

        assert task_id is not None

        # Задача в БД со статусом pending
        task = MediaTaskModel.get_by_id(task_id)
        assert task.status == "pending"

    def test_ingest_video_without_analyzer_raises(self, mock_embedder, media_db):
        """Без video_analyzer выбрасывает RuntimeError."""
        from semantic_core import (
            PeeweeVectorStore,
            SimpleSplitter,
            BasicContextStrategy,
        )

        store = PeeweeVectorStore(media_db)
        core = SemanticCore(
            embedder=mock_embedder,
            store=store,
            splitter=SimpleSplitter(),
            context_strategy=BasicContextStrategy(),
            video_analyzer=None,
        )

        with pytest.raises(RuntimeError, match="video_analyzer not configured"):
            core.ingest_video(path="test.mp4", mode="sync")
