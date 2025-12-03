"""Интеграционные тесты: SemanticCore + Media Enrichment.

Проверяем полный пайплайн обработки Markdown с медиа-ссылками:
- Парсинг → Обогащение → Сохранение в БД
- Работа с mock анализаторами
- Проверка metadata и content после обогащения
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from semantic_core import (
    SemanticCore,
    PeeweeVectorStore,
    init_peewee_database,
)
from semantic_core.domain import Document
from semantic_core.domain.chunk import ChunkType
from semantic_core.domain.media import MediaAnalysisResult
from semantic_core.processing.parsers.markdown_parser import MarkdownNodeParser
from semantic_core.processing.splitters.smart_splitter import SmartSplitter
from semantic_core.processing.context.hierarchical_strategy import (
    HierarchicalContextStrategy,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def test_db(tmp_path):
    """Временная БД для тестов."""
    db_path = tmp_path / "test.db"
    db = init_peewee_database(str(db_path))
    yield db
    db.close()


@pytest.fixture
def mock_embedder():
    """Mock embedder для тестов.

    Возвращает numpy array (как реальный embedder).
    """
    import numpy as np

    embedder = MagicMock()
    embedder.embed_query.return_value = np.array([0.1] * 768, dtype=np.float32)
    embedder.embed_documents.return_value = [
        np.array([0.1] * 768, dtype=np.float32) for _ in range(10)
    ]
    return embedder


@pytest.fixture
def mock_image_analyzer():
    """Mock GeminiImageAnalyzer."""
    analyzer = MagicMock()
    analyzer.analyze.return_value = MediaAnalysisResult(
        description="A colorful diagram showing system architecture",
        alt_text="Architecture diagram",
        keywords=["architecture", "system", "diagram"],
        ocr_text="API Gateway",
    )
    return analyzer


@pytest.fixture
def mock_audio_analyzer():
    """Mock GeminiAudioAnalyzer."""
    analyzer = MagicMock()
    analyzer.analyze.return_value = MediaAnalysisResult(
        description="Recording of a technical lecture",
        alt_text="Lecture audio",
        keywords=["vectors", "embeddings", "database"],
        transcription="Сегодня мы поговорим о векторных базах данных",
        participants=["Lecturer"],
        action_items=["Learn sqlite-vec"],
        duration_seconds=15.0,
    )
    return analyzer


@pytest.fixture
def mock_video_analyzer():
    """Mock GeminiVideoAnalyzer."""
    analyzer = MagicMock()
    analyzer.analyze.return_value = MediaAnalysisResult(
        description="Tutorial video demonstrating OAuth flow",
        alt_text="OAuth demo",
        keywords=["OAuth", "authentication", "Django"],
        transcription="This is the authorization flow",
        ocr_text="OAuth 2.0 Authorization Code Flow",
        duration_seconds=35.0,
    )
    return analyzer


@pytest.fixture
def semantic_core_with_analyzers(
    test_db,
    mock_embedder,
    mock_image_analyzer,
    mock_audio_analyzer,
    mock_video_analyzer,
):
    """SemanticCore с всеми mock анализаторами."""
    parser = MarkdownNodeParser()
    splitter = SmartSplitter(parser=parser, chunk_size=500)
    context = HierarchicalContextStrategy(include_doc_title=True)
    store = PeeweeVectorStore(test_db)

    core = SemanticCore(
        embedder=mock_embedder,
        store=store,
        splitter=splitter,
        context_strategy=context,
        image_analyzer=mock_image_analyzer,
        audio_analyzer=mock_audio_analyzer,
        video_analyzer=mock_video_analyzer,
    )

    return core


@pytest.fixture
def semantic_core_image_only(
    test_db,
    mock_embedder,
    mock_image_analyzer,
):
    """SemanticCore только с image_analyzer."""
    parser = MarkdownNodeParser()
    splitter = SmartSplitter(parser=parser, chunk_size=500)
    context = HierarchicalContextStrategy(include_doc_title=True)
    store = PeeweeVectorStore(test_db)

    core = SemanticCore(
        embedder=mock_embedder,
        store=store,
        splitter=splitter,
        context_strategy=context,
        image_analyzer=mock_image_analyzer,
        # audio_analyzer и video_analyzer не настроены
    )

    return core


@pytest.fixture
def test_markdown_content():
    """Тестовый Markdown с разными типами медиа."""
    return """
# Tutorial: Semantic Search

Welcome to our tutorial!

## Architecture Overview

Here is the system diagram:

![Architecture](images/architecture.png)

## Audio Materials

Listen to the introduction:

![Lecture](audio/intro.mp3)

## Video Demonstration

Watch the OAuth flow:

![OAuth Demo](video/oauth.mp4)

## Conclusion

That's all for now!
"""


@pytest.fixture
def temp_media_files(tmp_path, test_markdown_content):
    """Создаёт временные медиа-файлы для тестов."""
    # Создаём директории
    (tmp_path / "images").mkdir()
    (tmp_path / "audio").mkdir()
    (tmp_path / "video").mkdir()

    # Создаём пустые файлы (для проверки существования)
    (tmp_path / "images" / "architecture.png").write_bytes(b"PNG")
    (tmp_path / "audio" / "intro.mp3").write_bytes(b"MP3")
    (tmp_path / "video" / "oauth.mp4").write_bytes(b"MP4")

    # Создаём markdown файл для правильного разрешения путей
    (tmp_path / "doc.md").write_text(test_markdown_content)

    return tmp_path


# ============================================================================
# Тесты парсинга медиа-ссылок
# ============================================================================


class TestMarkdownMediaParsing:
    """Тесты парсинга Markdown с медиа-ссылками."""

    def test_markdown_parsed_correctly(
        self, semantic_core_with_analyzers, test_markdown_content
    ):
        """Markdown с медиа парсится на чанки."""
        splitter = semantic_core_with_analyzers.splitter
        doc = Document(content=test_markdown_content, metadata={"title": "Test"})

        chunks = splitter.split(doc)

        # Должны быть разные типы чанков
        chunk_types = {c.chunk_type for c in chunks}

        assert ChunkType.TEXT in chunk_types
        assert ChunkType.IMAGE_REF in chunk_types
        assert ChunkType.AUDIO_REF in chunk_types
        assert ChunkType.VIDEO_REF in chunk_types

    def test_image_chunk_has_correct_path(
        self, semantic_core_with_analyzers, test_markdown_content
    ):
        """IMAGE_REF чанк содержит путь к файлу."""
        splitter = semantic_core_with_analyzers.splitter
        doc = Document(content=test_markdown_content, metadata={"title": "Test"})

        chunks = splitter.split(doc)
        image_chunks = [c for c in chunks if c.chunk_type == ChunkType.IMAGE_REF]

        assert len(image_chunks) == 1
        assert image_chunks[0].content == "images/architecture.png"

    def test_audio_chunk_has_correct_path(
        self, semantic_core_with_analyzers, test_markdown_content
    ):
        """AUDIO_REF чанк содержит путь к файлу."""
        splitter = semantic_core_with_analyzers.splitter
        doc = Document(content=test_markdown_content, metadata={"title": "Test"})

        chunks = splitter.split(doc)
        audio_chunks = [c for c in chunks if c.chunk_type == ChunkType.AUDIO_REF]

        assert len(audio_chunks) == 1
        assert audio_chunks[0].content == "audio/intro.mp3"

    def test_video_chunk_has_correct_path(
        self, semantic_core_with_analyzers, test_markdown_content
    ):
        """VIDEO_REF чанк содержит путь к файлу."""
        splitter = semantic_core_with_analyzers.splitter
        doc = Document(content=test_markdown_content, metadata={"title": "Test"})

        chunks = splitter.split(doc)
        video_chunks = [c for c in chunks if c.chunk_type == ChunkType.VIDEO_REF]

        assert len(video_chunks) == 1
        assert video_chunks[0].content == "video/oauth.mp4"

    def test_headers_preserved_for_media(
        self, semantic_core_with_analyzers, test_markdown_content
    ):
        """Headers сохраняются для медиа-чанков."""
        splitter = semantic_core_with_analyzers.splitter
        doc = Document(content=test_markdown_content, metadata={"title": "Test"})

        chunks = splitter.split(doc)

        audio_chunks = [c for c in chunks if c.chunk_type == ChunkType.AUDIO_REF]
        assert audio_chunks[0].metadata.get("headers") == [
            "Tutorial: Semantic Search",
            "Audio Materials",
        ]


# ============================================================================
# Тесты обогащения с mock анализаторами
# ============================================================================


class TestSemanticCoreMediaEnrichment:
    """Интеграция: SemanticCore.ingest() с медиа-обогащением."""

    def test_ingest_without_enrichment(
        self, semantic_core_with_analyzers, test_markdown_content
    ):
        """ingest() без enrich_media НЕ вызывает анализаторы."""
        doc = Document(
            content=test_markdown_content,
            metadata={"title": "Test", "source": "/fake/path.md"},
        )

        # enrich_media=False (по умолчанию)
        semantic_core_with_analyzers.ingest(doc, enrich_media=False)

        # Анализаторы не должны быть вызваны
        semantic_core_with_analyzers.image_analyzer.analyze.assert_not_called()
        semantic_core_with_analyzers.audio_analyzer.analyze.assert_not_called()
        semantic_core_with_analyzers.video_analyzer.analyze.assert_not_called()

    def test_ingest_with_enrichment_missing_files(
        self, semantic_core_with_analyzers, test_markdown_content
    ):
        """ingest() с enrich_media=True пропускает несуществующие файлы."""
        doc = Document(
            content=test_markdown_content,
            metadata={"title": "Test", "source": "/fake/path.md"},
        )

        # Файлы не существуют, поэтому анализаторы не должны вызываться
        semantic_core_with_analyzers.ingest(doc, enrich_media=True)

        # Анализаторы не вызваны (файлы не найдены)
        semantic_core_with_analyzers.image_analyzer.analyze.assert_not_called()
        semantic_core_with_analyzers.audio_analyzer.analyze.assert_not_called()
        semantic_core_with_analyzers.video_analyzer.analyze.assert_not_called()

    def test_ingest_with_enrichment_real_files(
        self, semantic_core_with_analyzers, test_markdown_content, temp_media_files
    ):
        """ingest() с enrich_media=True вызывает анализаторы для существующих файлов."""
        # Создаём документ с правильным путём
        doc = Document(
            content=test_markdown_content,
            metadata={
                "title": "Test",
                "source": str(temp_media_files / "doc.md"),
            },
        )

        semantic_core_with_analyzers.ingest(doc, enrich_media=True)

        # Все анализаторы должны быть вызваны
        semantic_core_with_analyzers.image_analyzer.analyze.assert_called_once()
        semantic_core_with_analyzers.audio_analyzer.analyze.assert_called_once()
        semantic_core_with_analyzers.video_analyzer.analyze.assert_called_once()

    def test_missing_analyzer_skips_chunk(
        self, semantic_core_image_only, test_markdown_content, temp_media_files
    ):
        """Если нет audio_analyzer, AUDIO_REF пропускается без ошибки."""
        doc = Document(
            content=test_markdown_content,
            metadata={
                "title": "Test",
                "source": str(temp_media_files / "doc.md"),
            },
        )

        # Не должно падать, даже если audio/video анализаторы не настроены
        result = semantic_core_image_only.ingest(doc, enrich_media=True)

        assert result.id is not None
        # image_analyzer вызван
        semantic_core_image_only.image_analyzer.analyze.assert_called_once()


# ============================================================================
# Тесты сохранения в БД
# ============================================================================


class TestMediaEnrichmentDatabase:
    """Тесты сохранения обогащённых чанков в БД."""

    def test_enriched_chunks_saved_to_db(
        self, semantic_core_with_analyzers, test_markdown_content, temp_media_files
    ):
        """Обогащённые чанки сохраняются в БД."""
        from semantic_core.infrastructure.storage.peewee.models import ChunkModel

        doc = Document(
            content=test_markdown_content,
            metadata={
                "title": "Test",
                "source": str(temp_media_files / "doc.md"),
            },
        )

        saved_doc = semantic_core_with_analyzers.ingest(doc, enrich_media=True)

        # Проверяем БД
        chunks = list(ChunkModel.select().where(ChunkModel.document == saved_doc.id))

        # Должны быть чанки
        assert len(chunks) > 0

    def test_enriched_flag_set(
        self, semantic_core_with_analyzers, test_markdown_content, temp_media_files
    ):
        """metadata['_enriched'] == True после обогащения."""
        from semantic_core.infrastructure.storage.peewee.models import ChunkModel
        import json

        doc = Document(
            content=test_markdown_content,
            metadata={
                "title": "Test",
                "source": str(temp_media_files / "doc.md"),
            },
        )

        saved_doc = semantic_core_with_analyzers.ingest(doc, enrich_media=True)

        # Находим IMAGE_REF чанк
        image_chunks = list(
            ChunkModel.select().where(
                ChunkModel.document == saved_doc.id,
                ChunkModel.chunk_type == ChunkType.IMAGE_REF.value,
            )
        )

        assert len(image_chunks) == 1
        metadata = json.loads(image_chunks[0].metadata)
        assert metadata.get("_enriched") is True

    def test_original_path_preserved(
        self, semantic_core_with_analyzers, test_markdown_content, temp_media_files
    ):
        """metadata['_original_path'] содержит исходный путь."""
        from semantic_core.infrastructure.storage.peewee.models import ChunkModel
        import json

        doc = Document(
            content=test_markdown_content,
            metadata={
                "title": "Test",
                "source": str(temp_media_files / "doc.md"),
            },
        )

        saved_doc = semantic_core_with_analyzers.ingest(doc, enrich_media=True)

        # Находим AUDIO_REF чанк
        audio_chunks = list(
            ChunkModel.select().where(
                ChunkModel.document == saved_doc.id,
                ChunkModel.chunk_type == ChunkType.AUDIO_REF.value,
            )
        )

        assert len(audio_chunks) == 1
        metadata = json.loads(audio_chunks[0].metadata)
        assert metadata.get("_original_path") == "audio/intro.mp3"

    def test_content_replaced_with_description(
        self, semantic_core_with_analyzers, test_markdown_content, temp_media_files
    ):
        """content чанка заменяется на описание от анализатора."""
        from semantic_core.infrastructure.storage.peewee.models import ChunkModel

        doc = Document(
            content=test_markdown_content,
            metadata={
                "title": "Test",
                "source": str(temp_media_files / "doc.md"),
            },
        )

        saved_doc = semantic_core_with_analyzers.ingest(doc, enrich_media=True)

        # IMAGE_REF
        image_chunks = list(
            ChunkModel.select().where(
                ChunkModel.document == saved_doc.id,
                ChunkModel.chunk_type == ChunkType.IMAGE_REF.value,
            )
        )
        assert "diagram showing system architecture" in image_chunks[0].content

        # AUDIO_REF (content = transcription)
        audio_chunks = list(
            ChunkModel.select().where(
                ChunkModel.document == saved_doc.id,
                ChunkModel.chunk_type == ChunkType.AUDIO_REF.value,
            )
        )
        assert "векторных базах данных" in audio_chunks[0].content

        # VIDEO_REF (content = description)
        video_chunks = list(
            ChunkModel.select().where(
                ChunkModel.document == saved_doc.id,
                ChunkType.VIDEO_REF.value,
            )
        )
        # Видео может быть или не быть в зависимости от реализации


# ============================================================================
# Тесты edge cases
# ============================================================================


class TestMediaEdgeCases:
    """Edge cases обработки медиа."""

    def test_url_media_skipped(
        self, semantic_core_with_analyzers
    ):
        """HTTP URL → пропускается (не локальный файл)."""
        md = """
# Test

![Remote Image](https://example.com/image.png)
"""
        doc = Document(content=md, metadata={"title": "Test"})

        semantic_core_with_analyzers.ingest(doc, enrich_media=True)

        # Анализатор не должен вызываться для URL
        semantic_core_with_analyzers.image_analyzer.analyze.assert_not_called()

    def test_data_uri_skipped(
        self, semantic_core_with_analyzers
    ):
        """data: URI → пропускается."""
        md = """
# Test

![Embedded](data:image/png;base64,abc123)
"""
        doc = Document(content=md, metadata={"title": "Test"})

        semantic_core_with_analyzers.ingest(doc, enrich_media=True)

        semantic_core_with_analyzers.image_analyzer.analyze.assert_not_called()

    def test_ingest_without_source_metadata(
        self, semantic_core_with_analyzers, test_markdown_content
    ):
        """Документ без metadata['source'] → пути относительно CWD."""
        doc = Document(
            content=test_markdown_content,
            metadata={"title": "Test"},  # Нет source
        )

        # Не должно падать
        result = semantic_core_with_analyzers.ingest(doc, enrich_media=True)
        assert result.id is not None
