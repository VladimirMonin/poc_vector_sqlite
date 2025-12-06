"""Unit-тесты для MediaContext — immutable контейнер для media processing.

Архитектурный контекст:
-----------------------
Phase 14.1.0: Core Architecture — тесты для MediaContext frozen dataclass.

Покрытие:
---------
- ✅ Immutability (frozen dataclass)
- ✅ with_chunks() создаёт новый объект
- ✅ base_index автоматически инкрементируется
- ✅ Service Locator pattern
- ✅ user_instructions опциональное поле
"""

from pathlib import Path

import pytest

from semantic_core.core.media_context import MediaContext
from semantic_core.domain import Chunk, Document, MediaType


class TestMediaContextImmutability:
    """Тесты для immutability frozen dataclass."""
    
    def test_cannot_modify_fields_directly(self):
        """Проверяет, что нельзя изменить поля frozen dataclass."""
        context = MediaContext(
            media_path=Path("test.mp3"),
            document=Document(content="Test", media_type=MediaType.TEXT),
            analysis={"type": "audio"},
            chunks=[],
            base_index=0,
        )
        
        # Попытка изменить поле должна выбросить FrozenInstanceError
        with pytest.raises(Exception):  # dataclasses.FrozenInstanceError
            context.base_index = 10
    
    def test_with_chunks_creates_new_object(self):
        """Проверяет, что with_chunks() возвращает новый объект."""
        original = MediaContext(
            media_path=Path("test.mp3"),
            document=Document(content="Test", media_type=MediaType.TEXT),
            analysis={"type": "audio"},
            chunks=[],
            base_index=0,
        )
        
        chunk = Chunk(content="New chunk", chunk_index=0)
        updated = original.with_chunks([chunk])
        
        # Должны быть разные объекты
        assert updated is not original
        
        # Оригинал не изменился
        assert len(original.chunks) == 0
        assert original.base_index == 0
        
        # Новый объект обновлён
        assert len(updated.chunks) == 1
        assert updated.base_index == 1


class TestWithChunks:
    """Тесты для метода with_chunks()."""
    
    def test_adds_chunks_to_list(self):
        """Проверяет добавление чанков."""
        context = MediaContext(
            media_path=Path("test.mp3"),
            document=Document(content="Test", media_type=MediaType.TEXT),
            analysis={"type": "audio"},
            chunks=[],
            base_index=0,
        )
        
        chunk1 = Chunk(content="First", chunk_index=0)
        chunk2 = Chunk(content="Second", chunk_index=1)
        
        updated = context.with_chunks([chunk1, chunk2])
        
        assert len(updated.chunks) == 2
        assert updated.chunks[0].content == "First"
        assert updated.chunks[1].content == "Second"
    
    def test_increments_base_index_by_default(self):
        """Проверяет автоматический инкремент base_index."""
        context = MediaContext(
            media_path=Path("test.mp3"),
            document=Document(content="Test", media_type=MediaType.TEXT),
            analysis={"type": "audio"},
            chunks=[],
            base_index=0,
        )
        
        # Добавляем 3 чанка
        chunks = [Chunk(content=f"Chunk {i}", chunk_index=i) for i in range(3)]
        updated = context.with_chunks(chunks)
        
        # base_index должен увеличиться на 3
        assert updated.base_index == 3
    
    def test_increment_index_false_preserves_base_index(self):
        """Проверяет, что increment_index=False не меняет base_index."""
        context = MediaContext(
            media_path=Path("test.mp3"),
            document=Document(content="Test", media_type=MediaType.TEXT),
            analysis={"type": "audio"},
            chunks=[],
            base_index=5,
        )
        
        chunk = Chunk(content="Test", chunk_index=5)
        updated = context.with_chunks([chunk], increment_index=False)
        
        # base_index не изменился
        assert updated.base_index == 5
        assert len(updated.chunks) == 1
    
    def test_preserves_existing_chunks(self):
        """Проверяет, что старые чанки сохраняются."""
        chunk1 = Chunk(content="First", chunk_index=0)
        context = MediaContext(
            media_path=Path("test.mp3"),
            document=Document(content="Test", media_type=MediaType.TEXT),
            analysis={"type": "audio"},
            chunks=[chunk1],
            base_index=1,
        )
        
        chunk2 = Chunk(content="Second", chunk_index=1)
        updated = context.with_chunks([chunk2])
        
        # Оба чанка должны быть в списке
        assert len(updated.chunks) == 2
        assert updated.chunks[0].content == "First"
        assert updated.chunks[1].content == "Second"


class TestServiceLocator:
    """Тесты для Service Locator pattern."""
    
    def test_get_service_returns_value(self):
        """Проверяет получение сервиса."""
        splitter_mock = object()
        context = MediaContext(
            media_path=Path("test.mp3"),
            document=Document(content="Test", media_type=MediaType.TEXT),
            analysis={"type": "audio"},
            chunks=[],
            base_index=0,
            services={"splitter": splitter_mock},
        )
        
        assert context.get_service("splitter") is splitter_mock
    
    def test_get_service_returns_default_if_not_found(self):
        """Проверяет возврат default значения."""
        context = MediaContext(
            media_path=Path("test.mp3"),
            document=Document(content="Test", media_type=MediaType.TEXT),
            analysis={"type": "audio"},
            chunks=[],
            base_index=0,
            services={},
        )
        
        assert context.get_service("missing", default="default_value") == "default_value"
    
    def test_get_service_returns_none_if_not_found_and_no_default(self):
        """Проверяет возврат None если нет default."""
        context = MediaContext(
            media_path=Path("test.mp3"),
            document=Document(content="Test", media_type=MediaType.TEXT),
            analysis={"type": "audio"},
            chunks=[],
            base_index=0,
            services={},
        )
        
        assert context.get_service("missing") is None


class TestUserInstructions:
    """Тесты для user_instructions поля."""
    
    def test_user_instructions_optional(self):
        """Проверяет, что user_instructions опциональное."""
        context = MediaContext(
            media_path=Path("test.mp3"),
            document=Document(content="Test", media_type=MediaType.TEXT),
            analysis={"type": "audio"},
            chunks=[],
            base_index=0,
        )
        
        assert context.user_instructions is None
    
    def test_user_instructions_can_be_set(self):
        """Проверяет установку user_instructions."""
        context = MediaContext(
            media_path=Path("test.mp3"),
            document=Document(content="Test", media_type=MediaType.TEXT),
            analysis={"type": "audio"},
            chunks=[],
            base_index=0,
            user_instructions="Focus on technical terms",
        )
        
        assert context.user_instructions == "Focus on technical terms"
    
    def test_user_instructions_preserved_in_with_chunks(self):
        """Проверяет, что user_instructions сохраняется в with_chunks()."""
        context = MediaContext(
            media_path=Path("test.mp3"),
            document=Document(content="Test", media_type=MediaType.TEXT),
            analysis={"type": "audio"},
            chunks=[],
            base_index=0,
            user_instructions="Focus on technical terms",
        )
        
        chunk = Chunk(content="Test", chunk_index=0)
        updated = context.with_chunks([chunk])
        
        assert updated.user_instructions == "Focus on technical terms"


class TestMediaContextIntegration:
    """Интеграционные тесты для реальных сценариев."""
    
    def test_sequential_chunk_addition(self):
        """Проверяет последовательное добавление чанков (как в pipeline)."""
        context = MediaContext(
            media_path=Path("video.mp4"),
            document=Document(content="Video doc", media_type=MediaType.VIDEO),
            analysis={"type": "video", "description": "Test video"},
            chunks=[],
            base_index=0,
        )
        
        # Step 1: Summary
        summary_chunk = Chunk(content="Summary", chunk_index=0)
        context = context.with_chunks([summary_chunk])
        
        assert len(context.chunks) == 1
        assert context.base_index == 1
        
        # Step 2: Transcription (3 chunks)
        transcript_chunks = [
            Chunk(content=f"Transcript {i}", chunk_index=i + 1) for i in range(3)
        ]
        context = context.with_chunks(transcript_chunks)
        
        assert len(context.chunks) == 4
        assert context.base_index == 4
        
        # Step 3: OCR (2 chunks)
        ocr_chunks = [Chunk(content=f"OCR {i}", chunk_index=i + 4) for i in range(2)]
        context = context.with_chunks(ocr_chunks)
        
        assert len(context.chunks) == 6
        assert context.base_index == 6
        
        # Проверяем финальное состояние
        assert context.chunks[0].content == "Summary"
        assert context.chunks[1].content == "Transcript 0"
        assert context.chunks[5].content == "OCR 1"
