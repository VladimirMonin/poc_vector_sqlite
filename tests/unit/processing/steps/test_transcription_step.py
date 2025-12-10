"""Тесты для TranscriptionStep — разбивка транскрипции на чанки.

Тестируются:
- should_run() логика (есть/нет transcription)
- Разбивка через mock splitter
- Обогащение metadata (role='transcript', parent_media_path)
- base_index корректно увеличивается
- Immutability контекста
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from semantic_core.core.media_context import MediaContext
from semantic_core.domain import Chunk, ChunkType, Document, MediaType
from semantic_core.processing.steps.transcription import TranscriptionStep


class TestTranscriptionStepShouldRun:
    """Тесты для should_run() логики."""
    
    def test_should_run_with_transcription(self):
        """Шаг должен выполняться при наличии transcription."""
        splitter = MagicMock()
        step = TranscriptionStep(splitter=splitter)
        
        context = MediaContext(
            media_path=Path("audio.mp3"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.AUDIO,
            ),
            analysis={"transcription": "Some text"},
            chunks=[],
            base_index=0,
        )
        
        assert step.should_run(context) is True
    
    def test_should_run_without_transcription(self):
        """Шаг НЕ должен выполняться без transcription."""
        splitter = MagicMock()
        step = TranscriptionStep(splitter=splitter)
        
        context = MediaContext(
            media_path=Path("audio.mp3"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.AUDIO,
            ),
            analysis={"type": "audio"},  # Нет transcription
            chunks=[],
            base_index=0,
        )
        
        assert step.should_run(context) is False
    
    def test_should_run_with_empty_transcription(self):
        """Пустая transcription — не выполняем."""
        splitter = MagicMock()
        step = TranscriptionStep(splitter=splitter)
        
        context = MediaContext(
            media_path=Path("video.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"transcription": ""},  # Пустая строка
            chunks=[],
            base_index=0,
        )
        
        assert step.should_run(context) is False


class TestTranscriptionStepBasic:
    """Базовые тесты TranscriptionStep."""
    
    def test_step_name(self):
        """Проверяем имя шага."""
        splitter = MagicMock()
        step = TranscriptionStep(splitter=splitter)
        assert step.step_name == "transcription"
    
    def test_is_optional_false(self):
        """TranscriptionStep критичен по умолчанию."""
        splitter = MagicMock()
        step = TranscriptionStep(splitter=splitter)
        assert step.is_optional is False


class TestTranscriptionStepProcessing:
    """Тесты обработки транскрипции."""
    
    def test_single_chunk_transcription(self):
        """Транскрипция режется на 1 чанк."""
        # Mock splitter возвращает 1 chunk
        mock_chunk = Chunk(
            content="This is the full transcription.",
            chunk_index=0,  # Будет перезаписан
            chunk_type=ChunkType.TEXT,
            metadata={},
        )
        
        mock_splitter = MagicMock()
        mock_splitter.split.return_value = [mock_chunk]
        
        step = TranscriptionStep(splitter=mock_splitter)
        
        context = MediaContext(
            media_path=Path("podcast.mp3"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.AUDIO,
            ),
            analysis={"transcription": "This is the full transcription."},
            chunks=[],
            base_index=1,  # После summary chunk
        )
        
        new_context = step.process(context)
        
        # Проверяем что splitter вызван
        mock_splitter.split.assert_called_once()
        
        # Проверяем временный Document
        temp_doc = mock_splitter.split.call_args[0][0]
        assert temp_doc.content == "This is the full transcription."
        assert temp_doc.media_type == MediaType.TEXT
        assert temp_doc.metadata["source"] == "podcast.mp3"
        
        # Проверяем результат
        assert len(new_context.chunks) == 1
        chunk = new_context.chunks[0]
        
        # chunk_index должен быть base_index
        assert chunk.chunk_index == 1
        
        # Metadata обогащена
        assert chunk.metadata["role"] == "transcript"
        assert chunk.metadata["parent_media_path"] == "podcast.mp3"
        assert chunk.metadata["_original_path"] == "podcast.mp3"
        
        # base_index увеличился
        assert new_context.base_index == 2
    
    def test_multi_chunk_transcription(self):
        """Длинная транскрипция режется на несколько чанков."""
        # Mock splitter возвращает 3 chunks
        mock_chunks = [
            Chunk(
                content=f"Chunk {i}",
                chunk_index=0,  # Будет перезаписан
                chunk_type=ChunkType.TEXT,
                metadata={},
            )
            for i in range(3)
        ]
        
        mock_splitter = MagicMock()
        mock_splitter.split.return_value = mock_chunks
        
        step = TranscriptionStep(splitter=mock_splitter)
        
        context = MediaContext(
            media_path=Path("interview.wav"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.AUDIO,
            ),
            analysis={"transcription": "Very long transcription text..."},
            chunks=[],
            base_index=5,
        )
        
        new_context = step.process(context)
        
        # 3 чанка созданы
        assert len(new_context.chunks) == 3
        
        # chunk_index правильно проставлены (5, 6, 7)
        assert new_context.chunks[0].chunk_index == 5
        assert new_context.chunks[1].chunk_index == 6
        assert new_context.chunks[2].chunk_index == 7
        
        # Все имеют role='transcript'
        for chunk in new_context.chunks:
            assert chunk.metadata["role"] == "transcript"
            assert chunk.metadata["parent_media_path"] == "interview.wav"
        
        # base_index увеличился на 3
        assert new_context.base_index == 8
    
    def test_metadata_enrichment(self):
        """Проверяем обогащение metadata."""
        # Chunk со своими metadata
        mock_chunk = Chunk(
            content="Transcript",
            chunk_index=0,
            chunk_type=ChunkType.TEXT,
            metadata={"custom_field": "value"},
        )
        
        mock_splitter = MagicMock()
        mock_splitter.split.return_value = [mock_chunk]
        
        step = TranscriptionStep(splitter=mock_splitter)
        
        context = MediaContext(
            media_path=Path("/data/audio.mp3"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.AUDIO,
            ),
            analysis={"transcription": "Transcript"},
            chunks=[],
            base_index=0,
        )
        
        new_context = step.process(context)
        chunk = new_context.chunks[0]
        
        # Исходные metadata сохранены
        assert chunk.metadata["custom_field"] == "value"
        
        # Добавлены новые
        assert chunk.metadata["role"] == "transcript"
        assert chunk.metadata["parent_media_path"] == str(Path("/data/audio.mp3"))
        assert chunk.metadata["_original_path"] == str(Path("/data/audio.mp3"))
    
    def test_metadata_no_overwrite_original_path(self):
        """Если _original_path уже есть, не перезаписываем."""
        mock_chunk = Chunk(
            content="Transcript",
            chunk_index=0,
            chunk_type=ChunkType.TEXT,
            metadata={"_original_path": "/custom/path.mp3"},
        )
        
        mock_splitter = MagicMock()
        mock_splitter.split.return_value = [mock_chunk]
        
        step = TranscriptionStep(splitter=mock_splitter)
        
        context = MediaContext(
            media_path=Path("audio.mp3"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.AUDIO,
            ),
            analysis={"transcription": "Transcript"},
            chunks=[],
            base_index=0,
        )
        
        new_context = step.process(context)
        chunk = new_context.chunks[0]
        
        # _original_path не перезаписан
        assert chunk.metadata["_original_path"] == "/custom/path.mp3"


class TestTranscriptionStepEdgeCases:
    """Edge cases и граничные условия."""
    
    def test_context_immutability(self):
        """Исходный контекст не изменяется."""
        mock_chunk = Chunk(
            content="Transcript",
            chunk_index=0,
            chunk_type=ChunkType.TEXT,
            metadata={},
        )
        
        mock_splitter = MagicMock()
        mock_splitter.split.return_value = [mock_chunk]
        
        step = TranscriptionStep(splitter=mock_splitter)
        
        original_context = MediaContext(
            media_path=Path("audio.mp3"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.AUDIO,
            ),
            analysis={"transcription": "Text"},
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
    
    def test_video_transcription(self):
        """Транскрипция видео обрабатывается так же."""
        mock_chunk = Chunk(
            content="Video transcript",
            chunk_index=0,
            chunk_type=ChunkType.TEXT,
            metadata={},
        )
        
        mock_splitter = MagicMock()
        mock_splitter.split.return_value = [mock_chunk]
        
        step = TranscriptionStep(splitter=mock_splitter)
        
        context = MediaContext(
            media_path=Path("tutorial.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis={"type": "video", "transcription": "Video transcript"},
            chunks=[],
            base_index=10,
        )
        
        new_context = step.process(context)
        
        assert len(new_context.chunks) == 1
        chunk = new_context.chunks[0]
        
        assert chunk.content == "Video transcript"
        assert chunk.chunk_index == 10
        assert chunk.metadata["role"] == "transcript"


class TestTranscriptionStepTimecodes:
    """Тесты для интеграции TimecodeParser."""
    
    def test_timecodes_enabled_by_default(self):
        """enable_timecodes=True по умолчанию."""
        splitter = MagicMock()
        step = TranscriptionStep(splitter=splitter)
        
        assert step.enable_timecodes is True
    
    def test_timecodes_can_be_disabled(self):
        """enable_timecodes можно отключить."""
        splitter = MagicMock()
        step = TranscriptionStep(splitter=splitter, enable_timecodes=False)
        
        assert step.enable_timecodes is False
    
    def test_parses_timecode_from_content(self):
        """Парсит таймкод [MM:SS] из контента чанка."""
        mock_chunk = Chunk(
            content="[05:30] Chapter 1 begins here",
            chunk_index=0,
            chunk_type=ChunkType.TEXT,
            metadata={},
        )
        
        mock_splitter = MagicMock()
        mock_splitter.split.return_value = [mock_chunk]
        
        step = TranscriptionStep(splitter=mock_splitter, enable_timecodes=True)
        
        context = MediaContext(
            media_path=Path("podcast.mp3"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.AUDIO,
            ),
            analysis={
                "transcription": "[05:30] Chapter 1",
                "duration_seconds": 3600,
            },
            chunks=[],
            base_index=1,
        )
        
        new_context = step.process(context)
        
        chunk = new_context.chunks[0]
        assert chunk.metadata["start_seconds"] == 330  # 5*60 + 30
        assert chunk.metadata["timecode_original"] == "[05:30]"
    
    def test_inherits_timecode_when_missing(self):
        """Наследует таймкод от предыдущего чанка."""
        # 2 чанка: первый с таймкодом, второй без
        chunk1 = Chunk(
            content="[01:00] First chunk",
            chunk_index=0,
            chunk_type=ChunkType.TEXT,
            metadata={},
        )
        chunk2 = Chunk(
            content="Second chunk without timecode",
            chunk_index=1,
            chunk_type=ChunkType.TEXT,
            metadata={},
        )
        
        mock_splitter = MagicMock()
        mock_splitter.split.return_value = [chunk1, chunk2]
        
        step = TranscriptionStep(splitter=mock_splitter, enable_timecodes=True)
        
        context = MediaContext(
            media_path=Path("podcast.mp3"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.AUDIO,
            ),
            analysis={
                "transcription": "[01:00] First\nSecond",
                "duration_seconds": 600,  # 10 минут
            },
            chunks=[],
            base_index=1,
        )
        
        new_context = step.process(context)
        
        # Первый чанк: явный таймкод
        assert new_context.chunks[0].metadata["start_seconds"] == 60  # [01:00]
        assert "timecode_original" in new_context.chunks[0].metadata
        
        # Второй чанк: наследует (60 + delta)
        # delta = 600 / 2 = 300
        assert new_context.chunks[1].metadata["start_seconds"] == 360  # 60 + 300
        assert "timecode_original" not in new_context.chunks[1].metadata
    
    def test_first_chunk_without_timecode_is_zero(self):
        """Первый чанк без таймкода начинается с 0."""
        mock_chunk = Chunk(
            content="No timecode at start",
            chunk_index=0,
            chunk_type=ChunkType.TEXT,
            metadata={},
        )
        
        mock_splitter = MagicMock()
        mock_splitter.split.return_value = [mock_chunk]
        
        step = TranscriptionStep(splitter=mock_splitter, enable_timecodes=True)
        
        context = MediaContext(
            media_path=Path("podcast.mp3"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.AUDIO,
            ),
            analysis={
                "transcription": "No timecode",
                "duration_seconds": 1000,
            },
            chunks=[],
            base_index=0,
        )
        
        new_context = step.process(context)
        
        assert new_context.chunks[0].metadata["start_seconds"] == 0
    
    def test_timecodes_disabled_no_parsing(self):
        """При enable_timecodes=False таймкоды не парсятся."""
        mock_chunk = Chunk(
            content="[05:30] Chapter 1",
            chunk_index=0,
            chunk_type=ChunkType.TEXT,
            metadata={},
        )
        
        mock_splitter = MagicMock()
        mock_splitter.split.return_value = [mock_chunk]
        
        step = TranscriptionStep(splitter=mock_splitter, enable_timecodes=False)
        
        context = MediaContext(
            media_path=Path("podcast.mp3"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.AUDIO,
            ),
            analysis={
                "transcription": "[05:30] Chapter 1",
                "duration_seconds": 3600,
            },
            chunks=[],
            base_index=0,
        )
        
        new_context = step.process(context)
        
        chunk = new_context.chunks[0]
        # Таймкоды не добавлены
        assert "start_seconds" not in chunk.metadata
        assert "timecode_original" not in chunk.metadata
    
    def test_timecode_validation_with_max_duration(self):
        """Таймкод больше duration_seconds игнорируется."""
        # Таймкод [20:00] при duration_seconds=600 (10 минут) недопустим
        mock_chunk = Chunk(
            content="[20:00] Invalid timecode",
            chunk_index=0,
            chunk_type=ChunkType.TEXT,
            metadata={},
        )
        
        mock_splitter = MagicMock()
        mock_splitter.split.return_value = [mock_chunk]
        
        step = TranscriptionStep(splitter=mock_splitter, enable_timecodes=True)
        
        context = MediaContext(
            media_path=Path("podcast.mp3"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.AUDIO,
            ),
            analysis={
                "transcription": "[20:00] Invalid",
                "duration_seconds": 600,  # 10 минут
            },
            chunks=[],
            base_index=0,
        )
        
        new_context = step.process(context)
        
        chunk = new_context.chunks[0]
        # Таймкод отклонён, наследован от position=0
        assert chunk.metadata["start_seconds"] == 0
        assert "timecode_original" not in chunk.metadata
