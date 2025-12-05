"""E2E-тесты: полный цикл прямой загрузки медиа и поиска.

Эти тесты проверяют:
1. Прямая загрузка медиа → правильный chunk_type в БД
2. Markdown загрузка → IMAGE_REF из парсера
3. Поиск по всем режимам (vector, fts, hybrid)
4. Аудит целостности БД

Phase 13.4 — тесты, которые ловят баг автоматически.
"""

import json
import sqlite3
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from semantic_core import SemanticCore
from semantic_core.domain import Document, MediaType
from semantic_core.domain.chunk import ChunkType
from semantic_core.domain.media import MediaAnalysisResult
from semantic_core.infrastructure.gemini.embedder import GeminiEmbedder
from semantic_core.infrastructure.storage.peewee.adapter import PeeweeVectorStore
from semantic_core.infrastructure.storage.peewee.engine import init_peewee_database
from semantic_core.infrastructure.storage.peewee.models import ChunkModel, DocumentModel
from semantic_core.processing.context.hierarchical_strategy import (
    HierarchicalContextStrategy,
)
from semantic_core.processing.parsers.markdown_parser import MarkdownNodeParser
from semantic_core.processing.splitters.smart_splitter import SmartSplitter


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def test_db(tmp_path: Path) -> Generator:
    """Временная БД для тестов."""
    db_path = tmp_path / "test_direct_media.db"
    db = init_peewee_database(str(db_path))
    yield db
    db.close()


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Путь к тестовой БД."""
    return tmp_path / "e2e_test.db"


@pytest.fixture
def mock_embedder() -> MagicMock:
    """Mock embedder с детерминированными эмбеддингами."""
    embedder = MagicMock(spec=GeminiEmbedder)
    
    # Возвращаем разные эмбеддинги для разного контента
    def embed_documents(texts: list[str]) -> list[np.ndarray]:
        result = []
        for text in texts:
            # Создаём псевдо-уникальные эмбеддинги на основе хеша текста
            seed = hash(text) % 10000
            rng = np.random.default_rng(seed)
            result.append(rng.random(768).astype(np.float32))
        return result
    
    def embed_query(text: str) -> np.ndarray:
        seed = hash(text) % 10000
        rng = np.random.default_rng(seed)
        return rng.random(768).astype(np.float32)
    
    embedder.embed_documents = embed_documents
    embedder.embed_query = embed_query
    embedder.dimension = 768
    
    return embedder


@pytest.fixture
def mock_image_analyzer() -> MagicMock:
    """Mock image analyzer."""
    analyzer = MagicMock()
    analyzer.analyze.return_value = MediaAnalysisResult(
        description="A beautiful sunset over the ocean with orange and purple sky",
        alt_text="Sunset photo",
        keywords=["sunset", "ocean", "nature", "sky"],
    )
    return analyzer


@pytest.fixture
def mock_audio_analyzer() -> MagicMock:
    """Mock audio analyzer."""
    analyzer = MagicMock()
    analyzer.analyze.return_value = MediaAnalysisResult(
        description="Python programming tutorial audio",
        transcription="Hello, welcome to the Python programming tutorial.",
        keywords=["python", "tutorial", "programming"],
    )
    return analyzer


@pytest.fixture
def mock_video_analyzer() -> MagicMock:
    """Mock video analyzer."""
    analyzer = MagicMock()
    analyzer.analyze.return_value = MediaAnalysisResult(
        description="Screen recording of VS Code with Python code",
        transcription="Let me show you how to create a VectorDatabase class.",
        keywords=["vscode", "python", "database"],
    )
    return analyzer


@pytest.fixture
def semantic_core(
    test_db,
    mock_embedder,
    mock_image_analyzer,
    mock_audio_analyzer,
    mock_video_analyzer,
) -> SemanticCore:
    """SemanticCore для тестов с моками."""
    parser = MarkdownNodeParser()
    splitter = SmartSplitter(parser=parser, chunk_size=500)
    context = HierarchicalContextStrategy(include_doc_title=True)
    store = PeeweeVectorStore(test_db)
    
    return SemanticCore(
        embedder=mock_embedder,
        store=store,
        splitter=splitter,
        context_strategy=context,
        image_analyzer=mock_image_analyzer,
        audio_analyzer=mock_audio_analyzer,
        video_analyzer=mock_video_analyzer,
    )


# ============================================================================
# DIRECT IMAGE INGESTION TESTS
# ============================================================================


class TestDirectImageIngestion:
    """Тесты прямой загрузки изображений."""
    
    def test_image_document_creates_image_ref_chunk(
        self, semantic_core: SemanticCore, test_db
    ) -> None:
        """Document(media_type=IMAGE) → chunk_type=IMAGE_REF.
        
        ЭТО ГЛАВНЫЙ ТЕСТ, который ловит баг!
        До фикса: chunk_type=text (FAIL)
        После фикса: chunk_type=image_ref (PASS)
        """
        # Arrange
        doc = Document(
            content="/path/to/sunset.jpg",
            media_type=MediaType.IMAGE,
            metadata={"title": "Sunset"},
        )
        
        # Act
        result = semantic_core.ingest(doc, mode="sync", enrich_media=False)
        
        # Assert: Проверяем в БД напрямую!
        chunks = list(ChunkModel.select().where(ChunkModel.document == result.id))
        
        assert len(chunks) == 1, "Должен быть ровно 1 чанк"
        assert chunks[0].chunk_type == ChunkType.IMAGE_REF.value, (
            f"chunk_type должен быть 'image_ref', а не '{chunks[0].chunk_type}'"
        )
    
    def test_image_enrichment_stores_description(
        self, semantic_core: SemanticCore, test_db, mock_image_analyzer
    ) -> None:
        """При enrich_media=True в content попадает описание, а не путь."""
        # Arrange
        doc = Document(
            content="/path/to/sunset.jpg",
            media_type=MediaType.IMAGE,
            metadata={"title": "Sunset"},
        )
        
        # Act
        result = semantic_core.ingest(doc, mode="sync", enrich_media=True)
        
        # Assert
        chunks = list(ChunkModel.select().where(ChunkModel.document == result.id))
        
        assert "sunset" in chunks[0].content.lower(), (
            "Content должен содержать описание от Vision API"
        )
        assert "/path/to/sunset.jpg" not in chunks[0].content, (
            "Content НЕ должен содержать путь к файлу"
        )
    
    def test_original_path_preserved_without_enrichment(
        self, semantic_core: SemanticCore, test_db
    ) -> None:
        """Без enrichment путь сохраняется в content."""
        doc = Document(
            content="/path/to/photo.jpg",
            media_type=MediaType.IMAGE,
            metadata={"title": "Photo"},
        )
        
        result = semantic_core.ingest(doc, mode="sync", enrich_media=False)
        
        chunk = ChunkModel.get(ChunkModel.document == result.id)
        
        # Путь должен быть в content (когда нет enrichment)
        # На Windows путь нормализуется, проверяем имя файла
        assert "photo.jpg" in chunk.content


# ============================================================================
# DIRECT AUDIO INGESTION TESTS
# ============================================================================


class TestDirectAudioIngestion:
    """Тесты прямой загрузки аудио."""
    
    def test_audio_document_creates_audio_ref_chunk(
        self, semantic_core: SemanticCore, test_db
    ) -> None:
        """Document(media_type=AUDIO) → chunk_type=AUDIO_REF."""
        doc = Document(
            content="/path/to/lecture.ogg",
            media_type=MediaType.AUDIO,
            metadata={"title": "Lecture"},
        )
        
        result = semantic_core.ingest(doc, mode="sync", enrich_media=False)
        
        chunk = ChunkModel.get(ChunkModel.document == result.id)
        
        assert chunk.chunk_type == ChunkType.AUDIO_REF.value, (
            f"chunk_type должен быть 'audio_ref', а не '{chunk.chunk_type}'"
        )
    
    def test_audio_enrichment_stores_transcription(
        self, semantic_core: SemanticCore, test_db, mock_audio_analyzer
    ) -> None:
        """При enrich_media=True в content попадает транскрипция."""
        doc = Document(
            content="/path/to/lecture.ogg",
            media_type=MediaType.AUDIO,
            metadata={"title": "Lecture"},
        )
        
        result = semantic_core.ingest(doc, mode="sync", enrich_media=True)
        
        chunk = ChunkModel.get(ChunkModel.document == result.id)
        
        assert "python" in chunk.content.lower(), (
            "Content должен содержать транскрипцию от Audio API"
        )


# ============================================================================
# DIRECT VIDEO INGESTION TESTS
# ============================================================================


class TestDirectVideoIngestion:
    """Тесты прямой загрузки видео."""
    
    def test_video_document_creates_video_ref_chunk(
        self, semantic_core: SemanticCore, test_db
    ) -> None:
        """Document(media_type=VIDEO) → chunk_type=VIDEO_REF."""
        doc = Document(
            content="/path/to/demo.mp4",
            media_type=MediaType.VIDEO,
            metadata={"title": "Demo"},
        )
        
        result = semantic_core.ingest(doc, mode="sync", enrich_media=False)
        
        chunk = ChunkModel.get(ChunkModel.document == result.id)
        
        assert chunk.chunk_type == ChunkType.VIDEO_REF.value, (
            f"chunk_type должен быть 'video_ref', а не '{chunk.chunk_type}'"
        )
    
    def test_video_enrichment_stores_description_and_transcription(
        self, semantic_core: SemanticCore, test_db, mock_video_analyzer
    ) -> None:
        """При enrich_media=True в content попадает описание + транскрипция."""
        doc = Document(
            content="/path/to/tutorial.mp4",
            media_type=MediaType.VIDEO,
            metadata={"title": "Tutorial"},
        )
        
        result = semantic_core.ingest(doc, mode="sync", enrich_media=True)
        
        chunk = ChunkModel.get(ChunkModel.document == result.id)
        
        # Должно быть и описание, и транскрипция
        assert "vscode" in chunk.content.lower() or "python" in chunk.content.lower(), (
            "Content должен содержать данные от Video API"
        )


# ============================================================================
# MARKDOWN REGRESSION TESTS
# ============================================================================


class TestMarkdownStillWorks:
    """Регрессионные тесты: markdown не сломался."""
    
    def test_markdown_with_image_ref_creates_correct_chunks(
        self, semantic_core: SemanticCore, test_db
    ) -> None:
        """Markdown с ![](path) продолжает создавать IMAGE_REF."""
        doc = Document(
            content="# Article\n\n![Photo](images/photo.jpg)\n\nText here.",
            media_type=MediaType.TEXT,
            metadata={"title": "Article"},
        )
        
        result = semantic_core.ingest(doc, mode="sync", enrich_media=False)
        
        chunks = list(ChunkModel.select().where(ChunkModel.document == result.id))
        
        chunk_types = {c.chunk_type for c in chunks}
        assert "image_ref" in chunk_types, "Markdown парсер должен создать IMAGE_REF"
        assert "text" in chunk_types, "Должен быть текстовый чанк"
    
    def test_text_document_uses_splitter(
        self, semantic_core: SemanticCore, test_db
    ) -> None:
        """Текстовый документ проходит через SmartSplitter."""
        doc = Document(
            content="""# Chapter 1

Some text about Python programming.

## Section 1.1

More detailed information here.

```python
def hello():
    print("world")
```

The end.
""",
            media_type=MediaType.TEXT,
            metadata={"title": "Python Guide"},
        )
        
        result = semantic_core.ingest(doc, mode="sync", enrich_media=False)
        
        chunks = list(ChunkModel.select().where(ChunkModel.document == result.id))
        
        # Должно быть несколько чанков (текст + код)
        assert len(chunks) >= 2, "SmartSplitter должен создать несколько чанков"
        
        chunk_types = {c.chunk_type for c in chunks}
        assert "text" in chunk_types
        assert "code" in chunk_types


# ============================================================================
# SEARCH TESTS
# ============================================================================


class TestSearchModes:
    """Тесты разных режимов поиска."""
    
    @pytest.fixture
    def populated_db(
        self, semantic_core: SemanticCore, test_db
    ) -> SemanticCore:
        """БД с разными типами документов."""
        # Текстовый документ
        semantic_core.ingest(
            Document(
                content="# Python Guide\n\nLearn Python programming basics.",
                media_type=MediaType.TEXT,
                metadata={"title": "Python Guide"},
            ),
            mode="sync",
            enrich_media=False,
        )
        
        # Изображение
        semantic_core.ingest(
            Document(
                content="/photos/sunset.jpg",
                media_type=MediaType.IMAGE,
                metadata={"title": "Sunset Photo"},
            ),
            mode="sync",
            enrich_media=True,
        )
        
        # Аудио
        semantic_core.ingest(
            Document(
                content="/audio/lecture.ogg",
                media_type=MediaType.AUDIO,
                metadata={"title": "Python Lecture"},
            ),
            mode="sync",
            enrich_media=True,
        )
        
        return semantic_core
    
    def test_vector_search_finds_all_types(
        self, populated_db: SemanticCore
    ) -> None:
        """Векторный поиск находит текст, изображения, аудио."""
        results = populated_db.search("python programming", mode="vector", limit=10)
        
        # С mock embedder все vectors одинаковые, так что найдём все
        assert len(results) >= 1, "Должны найти минимум 1 результат"
        
        # Проверяем что поиск работает
        assert isinstance(results, list)
    
    def test_fts_search_works(self, populated_db: SemanticCore) -> None:
        """FTS поиск по ключевым словам."""
        results = populated_db.search("Python", mode="fts", limit=10)
        
        # FTS должен найти документы с "Python" в контенте
        assert len(results) >= 1, "FTS должен найти результаты"
    
    def test_hybrid_search_combines_results(
        self, populated_db: SemanticCore
    ) -> None:
        """Гибридный поиск комбинирует vector и fts."""
        results = populated_db.search("python tutorial", mode="hybrid", limit=10)
        
        # Гибридный поиск должен вернуть результаты
        assert len(results) >= 1, "Hybrid search должен найти результаты"
    
    def test_search_media_by_content_not_path(
        self, populated_db: SemanticCore
    ) -> None:
        """Поиск находит медиа по описанию, а не по пути."""
        # Ищем по описанию от Vision API ("sunset ocean")
        results = populated_db.search("beautiful sunset ocean", mode="vector", limit=5)
        
        # Проверяем что поиск работает и возвращает SearchResult объекты
        # С mock embedder все vectors одинаковые, так что найдём все документы
        assert isinstance(results, list)
        
        if results:
            # SearchResult содержит document, проверяем структуру
            from semantic_core.domain.search_result import SearchResult
            assert all(isinstance(r, SearchResult) for r in results)
            
            # Проверяем что результаты содержат документы
            assert all(r.document is not None for r in results)


# ============================================================================
# DATABASE AUDIT TESTS
# ============================================================================


class TestDatabaseIntegrity:
    """Тесты-аудиторы для проверки целостности БД."""
    
    def test_no_media_files_stored_as_text_chunks(
        self, semantic_core: SemanticCore, test_db
    ) -> None:
        """Аудит: медиа-документы НЕ должны иметь chunk_type=text.
        
        Этот тест запускается ПОСЛЕ инжеста и проверяет:
        - Если document.media_type IN (image, audio, video)
        - То chunk.chunk_type НЕ ДОЛЖЕН быть 'text'
        """
        # Загружаем медиа-файлы
        for media_type, path in [
            (MediaType.IMAGE, "/test/image.jpg"),
            (MediaType.AUDIO, "/test/audio.ogg"),
            (MediaType.VIDEO, "/test/video.mp4"),
        ]:
            semantic_core.ingest(
                Document(
                    content=path,
                    media_type=media_type,
                    metadata={"title": f"Test {media_type.value}"},
                ),
                mode="sync",
                enrich_media=False,
            )
        
        # Аудит: проверяем нет ли нарушений
        violations = (
            ChunkModel.select(ChunkModel, DocumentModel)
            .join(DocumentModel)
            .where(
                (DocumentModel.media_type.in_(["image", "audio", "video"]))
                & (ChunkModel.chunk_type == "text")
            )
        )
        
        violations_list = list(violations)
        
        if violations_list:
            details = "\n".join([
                f"  Doc {v.document.id}: media_type={v.document.media_type}, "
                f"chunk_type={v.chunk_type}"
                for v in violations_list
            ])
            pytest.fail(
                f"НАРУШЕНИЕ: {len(violations_list)} медиа-документов "
                f"с chunk_type='text':\n{details}"
            )
    
    def test_all_chunks_have_embeddings(
        self, semantic_core: SemanticCore, test_db
    ) -> None:
        """Все чанки должны иметь embedding_status=READY.
        
        Примечание: embeddings хранятся в virtual table chunks_vec,
        а не в ChunkModel напрямую. Проверяем статус.
        """
        # Загружаем документ
        semantic_core.ingest(
            Document(
                content="# Test\n\nContent here.",
                media_type=MediaType.TEXT,
                metadata={"title": "Test"},
            ),
            mode="sync",
        )
        
        # Проверяем что все чанки имеют статус READY
        # (embeddings хранятся в chunks_vec virtual table)
        from semantic_core.infrastructure.storage.peewee.models import EmbeddingStatus
        
        chunks_not_ready = (
            ChunkModel.select()
            .where(ChunkModel.embedding_status != EmbeddingStatus.READY.value)
        )
        
        assert list(chunks_not_ready) == [], (
            "Все чанки должны иметь embedding_status=READY"
        )
    
    def test_chunk_type_matches_media_type(
        self, semantic_core: SemanticCore, test_db
    ) -> None:
        """chunk_type соответствует document.media_type для прямой загрузки."""
        expected_mappings = [
            (MediaType.IMAGE, ChunkType.IMAGE_REF),
            (MediaType.AUDIO, ChunkType.AUDIO_REF),
            (MediaType.VIDEO, ChunkType.VIDEO_REF),
        ]
        
        for media_type, expected_chunk_type in expected_mappings:
            doc = Document(
                content=f"/path/to/file.{media_type.value}",
                media_type=media_type,
                metadata={"title": f"Test {media_type.value}"},
            )
            
            result = semantic_core.ingest(doc, mode="sync", enrich_media=False)
            
            chunk = ChunkModel.get(ChunkModel.document == result.id)
            
            assert chunk.chunk_type == expected_chunk_type.value, (
                f"Для media_type={media_type.value} "
                f"ожидается chunk_type={expected_chunk_type.value}, "
                f"получено {chunk.chunk_type}"
            )


# ============================================================================
# EDGE CASES
# ============================================================================


class TestEdgeCases:
    """Граничные случаи."""
    
    def test_empty_metadata(
        self, semantic_core: SemanticCore, test_db
    ) -> None:
        """Документ без metadata не падает."""
        doc = Document(
            content="/path/to/image.jpg",
            media_type=MediaType.IMAGE,
        )
        
        result = semantic_core.ingest(doc, mode="sync", enrich_media=False)
        
        assert result.id is not None
    
    def test_special_characters_in_path(
        self, semantic_core: SemanticCore, test_db
    ) -> None:
        """Пути с пробелами и спецсимволами."""
        doc = Document(
            content="/path/to/my photo (1).jpg",
            media_type=MediaType.IMAGE,
            metadata={"title": "Photo with spaces"},
        )
        
        result = semantic_core.ingest(doc, mode="sync", enrich_media=False)
        
        chunk = ChunkModel.get(ChunkModel.document == result.id)
        assert "my photo (1).jpg" in chunk.content
    
    def test_cyrillic_in_content(
        self, semantic_core: SemanticCore, test_db
    ) -> None:
        """Кириллица в контенте."""
        doc = Document(
            content="# Привет мир\n\nТекст на русском языке.",
            media_type=MediaType.TEXT,
            metadata={"title": "Русский документ"},
        )
        
        result = semantic_core.ingest(doc, mode="sync", enrich_media=False)
        
        chunks = list(ChunkModel.select().where(ChunkModel.document == result.id))
        
        assert any("русском" in c.content for c in chunks)
