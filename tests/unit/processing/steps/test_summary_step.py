"""Тесты для SummaryStep — создание summary chunk из analysis.

Тестируются:
- Базовый сценарий создания summary chunk
- Поддержка разных типов медиа (image, audio, video)
- Флаг include_keywords
- Edge cases (пустой analysis, отсутствующие поля)
"""

from pathlib import Path

import pytest

from semantic_core.core.media_context import MediaContext
from semantic_core.domain import Chunk, ChunkType, Document, MediaType
from semantic_core.processing.steps.summary import SummaryStep


class TestSummaryStepBasic:
    """Базовые тесты SummaryStep."""
    
    def test_step_name(self):
        """Проверяем имя шага."""
        step = SummaryStep()
        assert step.step_name == "summary"
    
    def test_is_optional_false(self):
        """SummaryStep критичен — is_optional должен быть False."""
        step = SummaryStep()
        assert step.is_optional is False
    
    def test_should_run_always_true(self):
        """SummaryStep должен выполняться всегда."""
        step = SummaryStep()
        context = MediaContext(
            media_path=Path("test.jpg"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.IMAGE,
            ),
            analysis={"type": "image"},
            chunks=[],
            base_index=0,
        )
        assert step.should_run(context) is True


class TestSummaryStepImage:
    """Тесты для обработки изображений."""
    
    def test_image_summary_with_keywords(self):
        """Создание summary chunk для изображения с keywords."""
        analysis = {
            "type": "image",
            "description": "A beautiful sunset over mountains",
            "alt_text": "Sunset landscape photo",
            "keywords": ["sunset", "mountains", "nature"],
            "ocr_text": "Welcome to National Park",
        }
        
        context = MediaContext(
            media_path=Path("/data/sunset.jpg"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.IMAGE,
            ),
            analysis=analysis,
            chunks=[],
            base_index=0,
        )
        
        step = SummaryStep(include_keywords=True)
        new_context = step.process(context)
        
        # Проверяем что создан 1 chunk
        assert len(new_context.chunks) == 1
        chunk = new_context.chunks[0]
        
        # Проверяем content
        assert chunk.content == "A beautiful sunset over mountains"
        
        # Проверяем chunk_type
        assert chunk.chunk_type == ChunkType.IMAGE_REF
        
        # Проверяем chunk_index
        assert chunk.chunk_index == 0
        
        # Проверяем metadata
        assert chunk.metadata["role"] == "summary"
        assert chunk.metadata["_original_path"] == str(Path("/data/sunset.jpg"))
        assert chunk.metadata["_vision_alt"] == "Sunset landscape photo"
        assert chunk.metadata["_vision_keywords"] == ["sunset", "mountains", "nature"]
        assert chunk.metadata["_vision_ocr"] == "Welcome to National Park"
        
        # Проверяем что base_index увеличился
        assert new_context.base_index == 1
    
    def test_image_summary_without_keywords(self):
        """Создание summary chunk без keywords."""
        analysis = {
            "type": "image",
            "description": "A cat sitting on a table",
            "alt_text": "Cat photo",
            "keywords": ["cat", "animal"],
        }
        
        context = MediaContext(
            media_path=Path("cat.png"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.IMAGE,
            ),
            analysis=analysis,
            chunks=[],
            base_index=0,
        )
        
        step = SummaryStep(include_keywords=False)
        new_context = step.process(context)
        
        chunk = new_context.chunks[0]
        
        # keywords не должны попасть в metadata
        assert "_vision_keywords" not in chunk.metadata
        assert chunk.metadata["_vision_alt"] == "Cat photo"
    
    def test_image_summary_missing_fields(self):
        """Обработка изображения с отсутствующими полями."""
        analysis = {
            "type": "image",
            "description": "A dog",
            # alt_text, keywords, ocr_text отсутствуют
        }
        
        context = MediaContext(
            media_path=Path("dog.jpg"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.IMAGE,
            ),
            analysis=analysis,
            chunks=[],
            base_index=5,
        )
        
        step = SummaryStep()
        new_context = step.process(context)
        
        chunk = new_context.chunks[0]
        
        # Поля должны быть пустыми, но присутствовать
        assert chunk.content == "A dog"
        assert chunk.metadata["_vision_alt"] == ""
        assert "_vision_keywords" not in chunk.metadata or chunk.metadata["_vision_keywords"] == []
        assert "_vision_ocr" not in chunk.metadata


class TestSummaryStepAudio:
    """Тесты для обработки аудио."""
    
    def test_audio_summary_with_keywords(self):
        """Создание summary chunk для аудио с полными метаданными."""
        analysis = {
            "type": "audio",
            "description": "Podcast episode about AI",
            "keywords": ["AI", "technology", "podcast"],
            "participants": ["Alice", "Bob"],
            "action_items": ["Research GPT-4", "Schedule follow-up"],
            "duration_seconds": 3600,
            "transcription": "This is the full transcript...",  # Не должен попасть в summary
        }
        
        context = MediaContext(
            media_path=Path("podcast.mp3"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.AUDIO,
            ),
            analysis=analysis,
            chunks=[],
            base_index=0,
        )
        
        step = SummaryStep(include_keywords=True)
        new_context = step.process(context)
        
        chunk = new_context.chunks[0]
        
        # Content — только description (без transcription)
        assert chunk.content == "Podcast episode about AI"
        assert "This is the full transcript" not in chunk.content
        
        # ChunkType
        assert chunk.chunk_type == ChunkType.AUDIO_REF
        
        # Metadata
        assert chunk.metadata["role"] == "summary"
        assert chunk.metadata["_audio_description"] == "Podcast episode about AI"
        assert chunk.metadata["_audio_keywords"] == ["AI", "technology", "podcast"]
        assert chunk.metadata["_audio_participants"] == ["Alice", "Bob"]
        assert chunk.metadata["_audio_action_items"] == ["Research GPT-4", "Schedule follow-up"]
        assert chunk.metadata["_audio_duration"] == 3600
    
    def test_audio_summary_without_keywords(self):
        """Аудио без keywords."""
        analysis = {
            "type": "audio",
            "description": "Interview",
            "keywords": ["interview", "business"],
        }
        
        context = MediaContext(
            media_path=Path("interview.wav"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.AUDIO,
            ),
            analysis=analysis,
            chunks=[],
            base_index=0,
        )
        
        step = SummaryStep(include_keywords=False)
        new_context = step.process(context)
        
        chunk = new_context.chunks[0]
        assert "_audio_keywords" not in chunk.metadata


class TestSummaryStepVideo:
    """Тесты для обработки видео."""
    
    def test_video_summary_with_keywords(self):
        """Создание summary chunk для видео."""
        analysis = {
            "type": "video",
            "description": "Tutorial on Python programming",
            "keywords": ["python", "programming", "tutorial"],
            "duration_seconds": 1200,
        }
        
        context = MediaContext(
            media_path=Path("tutorial.mp4"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis=analysis,
            chunks=[],
            base_index=0,
        )
        
        step = SummaryStep(include_keywords=True)
        new_context = step.process(context)
        
        chunk = new_context.chunks[0]
        
        # Content
        assert chunk.content == "Tutorial on Python programming"
        
        # ChunkType
        assert chunk.chunk_type == ChunkType.VIDEO_REF
        
        # Metadata
        assert chunk.metadata["_video_keywords"] == ["python", "programming", "tutorial"]
        assert chunk.metadata["_video_duration"] == 1200
    
    def test_video_summary_without_keywords(self):
        """Видео без keywords."""
        analysis = {
            "type": "video",
            "description": "Conference talk",
            "keywords": ["conference", "talk"],
            "duration_seconds": 2400,
        }
        
        context = MediaContext(
            media_path=Path("talk.webm"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.VIDEO,
            ),
            analysis=analysis,
            chunks=[],
            base_index=0,
        )
        
        step = SummaryStep(include_keywords=False)
        new_context = step.process(context)
        
        chunk = new_context.chunks[0]
        assert "_video_keywords" not in chunk.metadata
        assert chunk.metadata["_video_duration"] == 2400


class TestSummaryStepEdgeCases:
    """Edge cases и граничные условия."""
    
    def test_empty_description(self):
        """Пустое description в analysis."""
        analysis = {
            "type": "image",
            "description": "",
            "alt_text": "Photo",
        }
        
        context = MediaContext(
            media_path=Path("empty.jpg"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.IMAGE,
            ),
            analysis=analysis,
            chunks=[],
            base_index=0,
        )
        
        step = SummaryStep()
        new_context = step.process(context)
        
        chunk = new_context.chunks[0]
        assert chunk.content == ""  # Пустой, но chunk создан
        assert chunk.metadata["_vision_alt"] == "Photo"
    
    def test_unknown_media_type(self):
        """Неизвестный тип медиа."""
        analysis = {
            "type": "pdf",  # Неизвестный тип
            "description": "Some document",
        }
        
        context = MediaContext(
            media_path=Path("doc.pdf"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.TEXT,
            ),
            analysis=analysis,
            chunks=[],
            base_index=0,
        )
        
        step = SummaryStep()
        new_context = step.process(context)
        
        chunk = new_context.chunks[0]
        
        # Content пустой для неизвестного типа
        assert chunk.content == ""
        
        # ChunkType — дефолтный TEXT
        assert chunk.chunk_type == ChunkType.TEXT
    
    def test_base_index_increments_correctly(self):
        """base_index корректно увеличивается."""
        analysis = {
            "type": "image",
            "description": "Test image",
        }
        
        context = MediaContext(
            media_path=Path("test.jpg"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.IMAGE,
            ),
            analysis=analysis,
            chunks=[],
            base_index=42,  # Начальный индекс
        )
        
        step = SummaryStep()
        new_context = step.process(context)
        
        # Chunk index должен быть 42
        assert new_context.chunks[0].chunk_index == 42
        
        # base_index должен увеличиться до 43
        assert new_context.base_index == 43
    
    def test_context_immutability(self):
        """Исходный контекст не изменяется."""
        analysis = {
            "type": "audio",
            "description": "Audio file",
        }
        
        original_context = MediaContext(
            media_path=Path("audio.mp3"),
            document=Document(
                content="Test",
                metadata={},
                media_type=MediaType.AUDIO,
            ),
            analysis=analysis,
            chunks=[],
            base_index=0,
        )
        
        step = SummaryStep()
        new_context = step.process(original_context)
        
        # Исходный контекст не изменился
        assert len(original_context.chunks) == 0
        assert original_context.base_index == 0
        
        # Новый контекст обновлён
        assert len(new_context.chunks) == 1
        assert new_context.base_index == 1
