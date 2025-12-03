"""Unit-тесты для HierarchicalContextStrategy с медиа-чанками.

Проверяем формирование vector_text для AUDIO_REF и VIDEO_REF чанков:
- Обогащённые чанки (с транскрипцией/описанием от API)
- Необогащённые чанки (только путь и alt-текст)
- Breadcrumbs и заголовок документа
"""

import pytest

from semantic_core.domain import Document
from semantic_core.domain.chunk import Chunk, ChunkType
from semantic_core.processing.context.hierarchical_strategy import (
    HierarchicalContextStrategy,
)


class TestHierarchicalContextAudioEnriched:
    """Тесты vector_text для обогащённого AUDIO_REF."""

    @pytest.fixture
    def strategy(self):
        return HierarchicalContextStrategy(include_doc_title=True)

    @pytest.fixture
    def document(self):
        return Document(
            content="",
            metadata={"title": "Курс Python"},
        )

    @pytest.fixture
    def enriched_audio_chunk(self):
        """Обогащённый аудио-чанк с транскрипцией от API."""
        return Chunk(
            content="Сегодня мы поговорим о векторных базах данных и эмбеддингах.",
            chunk_index=0,
            chunk_type=ChunkType.AUDIO_REF,
            metadata={
                "headers": ["Лекция 1", "Введение"],
                "_enriched": True,
                "_original_path": "audio/lecture1.mp3",
                "_audio_description": "Лекция о векторных базах данных",
                "_audio_keywords": ["векторы", "эмбеддинги", "база данных"],
                "_audio_participants": ["Преподаватель"],
                "_audio_action_items": ["Изучить sqlite-vec"],
                "_audio_duration": 15.5,
            },
        )

    def test_audio_enriched_includes_transcription(
        self, strategy, document, enriched_audio_chunk
    ):
        """Обогащённый AUDIO_REF: vector_text содержит 'Transcription:'."""
        result = strategy.form_vector_text(enriched_audio_chunk, document)

        assert "Transcription:" in result
        assert "векторных базах данных" in result

    def test_audio_enriched_includes_speakers(
        self, strategy, document, enriched_audio_chunk
    ):
        """Обогащённый AUDIO_REF: vector_text содержит 'Speakers:'."""
        result = strategy.form_vector_text(enriched_audio_chunk, document)

        assert "Speakers:" in result
        assert "Преподаватель" in result

    def test_audio_enriched_includes_keywords(
        self, strategy, document, enriched_audio_chunk
    ):
        """Обогащённый AUDIO_REF: vector_text содержит 'Keywords:'."""
        result = strategy.form_vector_text(enriched_audio_chunk, document)

        assert "Keywords:" in result
        assert "векторы" in result

    def test_audio_enriched_includes_action_items(
        self, strategy, document, enriched_audio_chunk
    ):
        """Обогащённый AUDIO_REF: vector_text содержит 'Action items:'."""
        result = strategy.form_vector_text(enriched_audio_chunk, document)

        assert "Action items:" in result
        assert "sqlite-vec" in result

    def test_audio_enriched_includes_duration(
        self, strategy, document, enriched_audio_chunk
    ):
        """Обогащённый AUDIO_REF: vector_text содержит 'Duration:'."""
        result = strategy.form_vector_text(enriched_audio_chunk, document)

        assert "Duration:" in result
        assert "15.5s" in result

    def test_audio_enriched_includes_source_path(
        self, strategy, document, enriched_audio_chunk
    ):
        """Обогащённый AUDIO_REF: vector_text содержит 'Source:' с путём."""
        result = strategy.form_vector_text(enriched_audio_chunk, document)

        assert "Source:" in result
        assert "audio/lecture1.mp3" in result

    def test_audio_enriched_includes_section(
        self, strategy, document, enriched_audio_chunk
    ):
        """Обогащённый AUDIO_REF: vector_text содержит 'Section:' с breadcrumbs."""
        result = strategy.form_vector_text(enriched_audio_chunk, document)

        assert "Section:" in result
        assert "Лекция 1 > Введение" in result

    def test_audio_enriched_includes_document_title(
        self, strategy, document, enriched_audio_chunk
    ):
        """Обогащённый AUDIO_REF: vector_text содержит 'Document:'."""
        result = strategy.form_vector_text(enriched_audio_chunk, document)

        assert "Document:" in result
        assert "Курс Python" in result

    def test_audio_enriched_type_is_audio(
        self, strategy, document, enriched_audio_chunk
    ):
        """Обогащённый AUDIO_REF: vector_text содержит 'Type: Audio'."""
        result = strategy.form_vector_text(enriched_audio_chunk, document)

        assert "Type: Audio" in result


class TestHierarchicalContextAudioRaw:
    """Тесты vector_text для НЕобогащённого AUDIO_REF."""

    @pytest.fixture
    def strategy(self):
        return HierarchicalContextStrategy(include_doc_title=True)

    @pytest.fixture
    def document(self):
        return Document(
            content="",
            metadata={"title": "Podcast Archive"},
        )

    @pytest.fixture
    def raw_audio_chunk(self):
        """Необогащённый аудио-чанк (только путь)."""
        return Chunk(
            content="podcasts/episode42.mp3",
            chunk_index=0,
            chunk_type=ChunkType.AUDIO_REF,
            metadata={
                "headers": ["Season 2", "Episode 42"],
                "alt": "Interview with expert",
            },
        )

    def test_audio_raw_includes_source_path(self, strategy, document, raw_audio_chunk):
        """Необогащённый AUDIO_REF: vector_text содержит 'Source:' с путём."""
        result = strategy.form_vector_text(raw_audio_chunk, document)

        assert "Source:" in result
        assert "podcasts/episode42.mp3" in result

    def test_audio_raw_includes_alt_description(
        self, strategy, document, raw_audio_chunk
    ):
        """Необогащённый AUDIO_REF: vector_text содержит alt-текст."""
        result = strategy.form_vector_text(raw_audio_chunk, document)

        assert "Description:" in result
        assert "Interview with expert" in result

    def test_audio_raw_type_is_audio_reference(
        self, strategy, document, raw_audio_chunk
    ):
        """Необогащённый AUDIO_REF: vector_text содержит 'Type: Audio Reference'."""
        result = strategy.form_vector_text(raw_audio_chunk, document)

        assert "Type: Audio Reference" in result

    def test_audio_raw_includes_section(self, strategy, document, raw_audio_chunk):
        """Необогащённый AUDIO_REF: vector_text содержит breadcrumbs."""
        result = strategy.form_vector_text(raw_audio_chunk, document)

        assert "Section:" in result
        assert "Season 2 > Episode 42" in result

    def test_audio_raw_no_transcription(self, strategy, document, raw_audio_chunk):
        """Необогащённый AUDIO_REF: НЕ содержит 'Transcription:'."""
        result = strategy.form_vector_text(raw_audio_chunk, document)

        assert "Transcription:" not in result


class TestHierarchicalContextVideoEnriched:
    """Тесты vector_text для обогащённого VIDEO_REF."""

    @pytest.fixture
    def strategy(self):
        return HierarchicalContextStrategy(include_doc_title=True)

    @pytest.fixture
    def document(self):
        return Document(
            content="",
            metadata={"title": "Django Tutorial"},
        )

    @pytest.fixture
    def enriched_video_chunk(self):
        """Обогащённый видео-чанк с описанием от API."""
        return Chunk(
            content="Диаграмма показывает последовательность OAuth авторизации в Django приложении.",
            chunk_index=0,
            chunk_type=ChunkType.VIDEO_REF,
            metadata={
                "headers": ["Authentication", "OAuth Flow"],
                "_enriched": True,
                "_original_path": "video/oauth_demo.mp4",
                "_video_transcription": "Здесь мы видим sequence diagram авторизации",
                "_video_keywords": ["OAuth", "Django", "авторизация", "sequence diagram"],
                "_video_ocr": "OAuth 2.0 Authorization Code Flow",
                "_video_duration": 35.0,
            },
        )

    def test_video_enriched_includes_description(
        self, strategy, document, enriched_video_chunk
    ):
        """Обогащённый VIDEO_REF: vector_text содержит 'Description:'."""
        result = strategy.form_vector_text(enriched_video_chunk, document)

        assert "Description:" in result
        assert "OAuth авторизации" in result

    def test_video_enriched_includes_audio_transcription(
        self, strategy, document, enriched_video_chunk
    ):
        """Обогащённый VIDEO_REF: vector_text содержит 'Audio transcription:'."""
        result = strategy.form_vector_text(enriched_video_chunk, document)

        assert "Audio transcription:" in result
        assert "sequence diagram" in result

    def test_video_enriched_includes_visible_text(
        self, strategy, document, enriched_video_chunk
    ):
        """Обогащённый VIDEO_REF: vector_text содержит 'Visible text:' (OCR)."""
        result = strategy.form_vector_text(enriched_video_chunk, document)

        assert "Visible text:" in result
        assert "OAuth 2.0" in result

    def test_video_enriched_includes_keywords(
        self, strategy, document, enriched_video_chunk
    ):
        """Обогащённый VIDEO_REF: vector_text содержит 'Keywords:'."""
        result = strategy.form_vector_text(enriched_video_chunk, document)

        assert "Keywords:" in result
        assert "OAuth" in result
        assert "Django" in result

    def test_video_enriched_includes_duration(
        self, strategy, document, enriched_video_chunk
    ):
        """Обогащённый VIDEO_REF: vector_text содержит 'Duration:'."""
        result = strategy.form_vector_text(enriched_video_chunk, document)

        assert "Duration:" in result
        assert "35.0s" in result

    def test_video_enriched_includes_source(
        self, strategy, document, enriched_video_chunk
    ):
        """Обогащённый VIDEO_REF: vector_text содержит 'Source:'."""
        result = strategy.form_vector_text(enriched_video_chunk, document)

        assert "Source:" in result
        assert "video/oauth_demo.mp4" in result

    def test_video_enriched_type_is_video(
        self, strategy, document, enriched_video_chunk
    ):
        """Обогащённый VIDEO_REF: vector_text содержит 'Type: Video'."""
        result = strategy.form_vector_text(enriched_video_chunk, document)

        assert "Type: Video" in result


class TestHierarchicalContextVideoRaw:
    """Тесты vector_text для НЕобогащённого VIDEO_REF."""

    @pytest.fixture
    def strategy(self):
        return HierarchicalContextStrategy(include_doc_title=True)

    @pytest.fixture
    def document(self):
        return Document(
            content="",
            metadata={"title": "Video Library"},
        )

    @pytest.fixture
    def raw_video_chunk(self):
        """Необогащённый видео-чанк (только путь)."""
        return Chunk(
            content="videos/demo.mp4",
            chunk_index=0,
            chunk_type=ChunkType.VIDEO_REF,
            metadata={
                "headers": ["Demos", "Product Demo"],
                "alt": "Product demonstration video",
            },
        )

    def test_video_raw_includes_source_path(self, strategy, document, raw_video_chunk):
        """Необогащённый VIDEO_REF: vector_text содержит 'Source:'."""
        result = strategy.form_vector_text(raw_video_chunk, document)

        assert "Source:" in result
        assert "videos/demo.mp4" in result

    def test_video_raw_includes_alt_description(
        self, strategy, document, raw_video_chunk
    ):
        """Необогащённый VIDEO_REF: vector_text содержит alt-текст."""
        result = strategy.form_vector_text(raw_video_chunk, document)

        assert "Description:" in result
        assert "Product demonstration video" in result

    def test_video_raw_type_is_video_reference(
        self, strategy, document, raw_video_chunk
    ):
        """Необогащённый VIDEO_REF: vector_text содержит 'Type: Video Reference'."""
        result = strategy.form_vector_text(raw_video_chunk, document)

        assert "Type: Video Reference" in result

    def test_video_raw_no_transcription(self, strategy, document, raw_video_chunk):
        """Необогащённый VIDEO_REF: НЕ содержит 'Audio transcription:'."""
        result = strategy.form_vector_text(raw_video_chunk, document)

        assert "Audio transcription:" not in result


class TestHierarchicalContextMediaCommon:
    """Общие тесты для всех типов медиа."""

    @pytest.fixture
    def strategy(self):
        return HierarchicalContextStrategy(include_doc_title=True)

    @pytest.fixture
    def document(self):
        return Document(
            content="",
            metadata={"title": "Test Document"},
        )

    def test_all_media_types_include_section(self, strategy, document):
        """Все медиа-типы содержат 'Section:' с breadcrumbs."""
        headers = ["Chapter 1", "Section A"]

        for chunk_type in [ChunkType.IMAGE_REF, ChunkType.AUDIO_REF, ChunkType.VIDEO_REF]:
            chunk = Chunk(
                content="path/to/media.ext",
                chunk_index=0,
                chunk_type=chunk_type,
                metadata={"headers": headers},
            )
            result = strategy.form_vector_text(chunk, document)

            assert "Section:" in result, f"Failed for {chunk_type}"
            assert "Chapter 1 > Section A" in result, f"Failed for {chunk_type}"

    def test_all_media_types_include_document_title(self, strategy, document):
        """Все медиа-типы содержат 'Document:' заголовок."""
        for chunk_type in [ChunkType.IMAGE_REF, ChunkType.AUDIO_REF, ChunkType.VIDEO_REF]:
            chunk = Chunk(
                content="path/to/media.ext",
                chunk_index=0,
                chunk_type=chunk_type,
                metadata={},
            )
            result = strategy.form_vector_text(chunk, document)

            assert "Document: Test Document" in result, f"Failed for {chunk_type}"

    def test_no_doc_title_when_disabled(self, document):
        """include_doc_title=False убирает заголовок документа."""
        strategy = HierarchicalContextStrategy(include_doc_title=False)

        chunk = Chunk(
            content="audio/test.mp3",
            chunk_index=0,
            chunk_type=ChunkType.AUDIO_REF,
            metadata={},
        )
        result = strategy.form_vector_text(chunk, document)

        assert "Document:" not in result

    def test_empty_headers_no_section(self, strategy, document):
        """Без headers нет строки 'Section:'."""
        chunk = Chunk(
            content="audio/orphan.mp3",
            chunk_index=0,
            chunk_type=ChunkType.AUDIO_REF,
            metadata={},  # Нет headers
        )
        result = strategy.form_vector_text(chunk, document)

        assert "Section:" not in result

    def test_image_ref_still_works(self, strategy, document):
        """IMAGE_REF по-прежнему работает корректно."""
        enriched_image = Chunk(
            content="A detailed architecture diagram showing microservices",
            chunk_index=0,
            chunk_type=ChunkType.IMAGE_REF,
            metadata={
                "headers": ["Architecture"],
                "_enriched": True,
                "_original_path": "images/arch.png",
                "_vision_keywords": ["microservices", "architecture"],
                "_vision_ocr": "API Gateway",
            },
        )

        result = strategy.form_vector_text(enriched_image, document)

        assert "Type: Image" in result
        assert "Description:" in result
        assert "architecture diagram" in result
        assert "Keywords:" in result
        assert "Visible text:" in result


class TestHierarchicalContextEdgeCases:
    """Edge cases для медиа-чанков."""

    @pytest.fixture
    def strategy(self):
        return HierarchicalContextStrategy(include_doc_title=True)

    @pytest.fixture
    def document(self):
        return Document(content="", metadata={})  # Без title

    def test_no_document_title(self, strategy, document):
        """Документ без title — строка 'Document:' отсутствует."""
        chunk = Chunk(
            content="audio/test.mp3",
            chunk_index=0,
            chunk_type=ChunkType.AUDIO_REF,
            metadata={},
        )
        result = strategy.form_vector_text(chunk, document)

        assert "Document:" not in result

    def test_enriched_without_optional_fields(self, strategy, document):
        """Обогащённый чанк без опциональных полей."""
        chunk = Chunk(
            content="Basic transcription only",
            chunk_index=0,
            chunk_type=ChunkType.AUDIO_REF,
            metadata={
                "_enriched": True,
                "_original_path": "audio/minimal.mp3",
                # Нет participants, action_items, keywords, duration
            },
        )
        result = strategy.form_vector_text(chunk, document)

        # Обязательные поля
        assert "Transcription:" in result
        assert "Source:" in result

        # Опциональные поля отсутствуют
        assert "Speakers:" not in result
        assert "Action items:" not in result
        assert "Duration:" not in result

    def test_video_without_transcription(self, strategy, document):
        """Видео без транскрипции (только визуальный анализ)."""
        chunk = Chunk(
            content="A diagram showing the system architecture",
            chunk_index=0,
            chunk_type=ChunkType.VIDEO_REF,
            metadata={
                "_enriched": True,
                "_original_path": "video/diagram.mp4",
                "_video_ocr": "System Architecture v2.0",
                # Нет transcription
            },
        )
        result = strategy.form_vector_text(chunk, document)

        assert "Description:" in result
        assert "Visible text:" in result
        assert "Audio transcription:" not in result
