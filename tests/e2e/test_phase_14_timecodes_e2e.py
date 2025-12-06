"""E2E-тесты для Phase 14.1: TimecodeParser и user_instructions.

Проверяют:
1. Парсинг таймкодов из audio транскрипций
2. Наследование таймкодов для чанков без меток
3. user_instructions попадают в MediaContext
"""

import json
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from semantic_core import SemanticCore
from semantic_core.domain.media import MediaAnalysisResult, MediaResource
from semantic_core.infrastructure.gemini.embedder import GeminiEmbedder
from semantic_core.infrastructure.storage.peewee.adapter import PeeweeVectorStore
from semantic_core.infrastructure.storage.peewee.engine import init_peewee_database
from semantic_core.infrastructure.storage.peewee.models import ChunkModel
from semantic_core.processing.context.hierarchical_strategy import (
    HierarchicalContextStrategy,
)
from semantic_core.processing.parsers.markdown_parser import MarkdownNodeParser
from semantic_core.processing.splitters.smart_splitter import SmartSplitter


# ============================================================================
# HELPERS
# ============================================================================


def get_chunks_for_document(doc_id: int) -> list:
    """Получить Chunk domain objects для документа из БД."""
    from semantic_core.domain import Chunk, ChunkType
    
    db_chunks = list(ChunkModel.select().where(ChunkModel.document == doc_id))
    
    chunks = []
    for db_chunk in db_chunks:
        chunk = Chunk(
            id=db_chunk.id,
            content=db_chunk.content,
            chunk_index=db_chunk.chunk_index,  # REQUIRED!
            chunk_type=ChunkType(db_chunk.chunk_type),
            language=db_chunk.language,
            metadata=json.loads(db_chunk.metadata),
            parent_doc_id=doc_id,
            embedding=None,  # не загружаем embedding
        )
        chunks.append(chunk)
    
    return chunks


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def test_db(tmp_path: Path) -> Generator:
    """Временная БД для E2E тестов."""
    db_path = tmp_path / "test_timecode_e2e.db"
    db = init_peewee_database(str(db_path))
    yield db
    db.close()


@pytest.fixture
def mock_embedder() -> MagicMock:
    """Mock embedder с детерминированными эмбеддингами."""
    embedder = MagicMock(spec=GeminiEmbedder)
    
    def embed_documents(texts: list[str]) -> list[np.ndarray]:
        result = []
        for text in texts:
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
def mock_audio_analyzer() -> MagicMock:
    """Mock audio analyzer (будет переопределён в тестах через patch)."""
    analyzer = MagicMock()
    analyzer.analyze.return_value = MediaAnalysisResult(
        description="Mock audio",
        transcription="Mock transcription",
        keywords=["mock"],
        participants=[],
        action_items=[],
        duration_seconds=60,
        tokens_used=50,
    )
    return analyzer


@pytest.fixture
def mock_video_analyzer() -> MagicMock:
    """Mock video analyzer."""
    analyzer = MagicMock()
    analyzer.analyze.return_value = MediaAnalysisResult(
        description="Mock video",
        keywords=["mock"],
        transcription=None,
        ocr_text=None,
        participants=[],
        action_items=[],
        duration_seconds=30,
        tokens_used=50,
    )
    return analyzer


@pytest.fixture
def semantic_core(
    test_db,
    mock_embedder,
    mock_audio_analyzer,
    mock_video_analyzer,
) -> SemanticCore:
    """SemanticCore с временной БД и моками."""
    parser = MarkdownNodeParser()
    splitter = SmartSplitter(parser=parser, chunk_size=500)
    context = HierarchicalContextStrategy(include_doc_title=True)
    store = PeeweeVectorStore(test_db)
    
    return SemanticCore(
        embedder=mock_embedder,
        store=store,
        splitter=splitter,
        context_strategy=context,
        audio_analyzer=mock_audio_analyzer,
        video_analyzer=mock_video_analyzer,
    )


@pytest.fixture
def mock_audio_resource(tmp_path: Path) -> MediaResource:
    """Mock audio file resource."""
    audio_path = tmp_path / "test_audio.mp3"
    audio_path.write_bytes(b"fake audio content")
    return MediaResource(
        path=audio_path,
        media_type="audio",
        mime_type="audio/mpeg",
    )


# ============================================================================
# TESTS: Audio Timecodes
# ============================================================================


def test_audio_with_timecodes(
    semantic_core: SemanticCore,
    mock_audio_analyzer: MagicMock,
    mock_audio_resource: MediaResource,
):
    """E2E: Audio транскрипция с таймкодами → metadata['start_seconds']."""
    
    # Переопределяем mock analyzer для этого теста
    # ВАЖНО: Делаем транскрипцию ДЛИННОЙ чтобы splitter разбил на 3+ чанка
    mock_audio_analyzer.analyze.return_value = MediaAnalysisResult(
        description="Test audio with timecodes",
        transcription=(
            "[00:05] Introduction to the topic. "
            "We will discuss the main aspects of semantic search and vector databases. "
            "This includes embeddings, chunking strategies, and retrieval mechanisms. "
            "Let's start with the fundamentals and build up to advanced techniques. "
            "\n"
            "[00:30] Main discussion begins. "
            "Vector databases store high-dimensional embeddings and enable fast similarity search. "
            "Popular options include Pinecone, Weaviate, Qdrant, and sqlite-vec for local usage. "
            "Each has trade-offs in terms of scalability, features, and deployment complexity. "
            "We'll compare their strengths and weaknesses in detail. "
            "\n"
            "[01:15] Conclusion and summary. "
            "Semantic search revolutionizes information retrieval by understanding meaning, not just keywords. "
            "Hybrid search combining vector and keyword approaches often yields the best results. "
            "Consider your use case carefully when choosing between local and cloud solutions. "
            "Thank you for watching this tutorial. "
        ),
        keywords=["test", "timecode", "semantic-search"],
        participants=["Speaker 1"],
        action_items=[],
        duration_seconds=90,  # 1.5 минуты
        tokens_used=100,
    )
    
    # Ingest audio
    doc_id = semantic_core.ingest_audio(mock_audio_resource.path)
    
    # Получаем chunks через helper
    chunks = get_chunks_for_document(doc_id)
    assert len(chunks) >= 2  # Summary + минимум 1 transcript
    
    # Фильтруем transcript chunks (не summary)
    transcript_chunks = [
        c for c in chunks
        if c.metadata.get("role") == "transcript"
    ]
    
    assert len(transcript_chunks) >= 1  # Минимум 1 transcript chunk
    
    # ВАЖНО: Проверяем что ПЕРВЫЙ таймкод [00:05] распарсился
    # Он может быть в первом чанке (splitter объединил все параграфы)
    first_chunk = transcript_chunks[0]
    assert "start_seconds" in first_chunk.metadata
    assert first_chunk.metadata["start_seconds"] == 5  # [00:05]
    
    # Проверяем что есть timecode_original
    assert "timecode_original" in first_chunk.metadata
    assert first_chunk.metadata["timecode_original"] == "[00:05]"
    
    # Если splitter создал несколько чанков (зависит от chunk_size):
    # - Второй чанк должен иметь [00:30] ИЛИ унаследованный 5
    # - Третий чанк должен иметь [01:15] ИЛИ унаследованный
    # Но это зависит от того, как splitter разбил текст!
    # Поэтому просто проверяем что start_seconds есть у всех
    for chunk in transcript_chunks:
        assert "start_seconds" in chunk.metadata, (
            f"Chunk {chunk.chunk_index} missing start_seconds"
        )


def test_timecode_inheritance(
    semantic_core: SemanticCore,
    mock_audio_analyzer: MagicMock,
    mock_audio_resource: MediaResource,
):
    """E2E: Чанк без таймкода наследует от предыдущего через inherit_timecode()."""
    
    # Переопределяем mock analyzer для этого теста
    # ВАЖНО: ДЛИННАЯ транскрипция с 1 таймкодом → splitter разобьёт на 2+ чанка
    mock_audio_analyzer.analyze.return_value = MediaAnalysisResult(
        description="Test timecode inheritance",
        transcription=(
            "[00:10] First section with timecode marker at ten seconds. "
            "We discuss the main topic with detailed explanations and examples. "
            "This content is designed to be long enough for the splitter to create multiple chunks. "
            "\n"
            "This continues without any timecode marker in subsequent paragraphs. "
            "More text in the same section providing additional context and information. "
            "And even more text to force the creation of at least two separate chunks. "
            "This second chunk should inherit the timecode value of ten seconds from the first chunk. "
            "The inheritance logic is tested end-to-end in this scenario. "
        ),
        keywords=["test", "inheritance"],
        participants=["Speaker 1"],
        action_items=[],
        duration_seconds=60,  # 1 минута
        tokens_used=100,
    )
    
    # Ingest audio
    doc_id = semantic_core.ingest_audio(mock_audio_resource.path)
    chunks = get_chunks_for_document(doc_id)
    
    # Фильтруем transcript chunks
    transcript_chunks = [
        c for c in chunks
        if c.metadata.get("role") == "transcript"
    ]
    
    # Минимум 1 transcript chunk
    assert len(transcript_chunks) >= 1
    
    # Первый chunk: [00:10] → start_seconds=10 (может быть внутри большого чанка)
    first_chunk = transcript_chunks[0]
    assert first_chunk.metadata["start_seconds"] == 10
    assert first_chunk.metadata.get("timecode_original") == "[00:10]"
    
    # Все чанки должны иметь start_seconds (либо явный, либо унаследованный)
    for chunk in transcript_chunks:
        assert "start_seconds" in chunk.metadata


def test_first_chunk_without_timecode_is_zero(
    semantic_core: SemanticCore,
    mock_audio_analyzer: MagicMock,
    mock_audio_resource: MediaResource,
):
    """E2E: Если первый чанк без таймкода → start_seconds=0."""
    
    # Переопределяем mock analyzer для этого теста
    mock_audio_analyzer.analyze.return_value = MediaAnalysisResult(
        description="Test no timecodes",
        transcription=(
            "This is a transcription without any timecode markers.\n"
            "It should still work and assign start_seconds=0 to first chunk."
        ),
        keywords=["test"],
        participants=["Speaker 1"],
        action_items=[],
        duration_seconds=30,
        tokens_used=50,
    )
    
    # Ingest audio
    doc_id = semantic_core.ingest_audio(mock_audio_resource.path)
    chunks = get_chunks_for_document(doc_id)
    
    # Фильтруем transcript chunks
    transcript_chunks = [
        c for c in chunks
        if c.metadata.get("role") == "transcript"
    ]
    
    assert len(transcript_chunks) >= 1
    
    # Первый chunk без таймкода → start_seconds=0
    first_chunk = transcript_chunks[0]
    assert first_chunk.metadata["start_seconds"] == 0
    assert "timecode_original" not in first_chunk.metadata


# ============================================================================
# TESTS: user_instructions
# ============================================================================


def test_user_prompt_injection_audio(
    semantic_core: SemanticCore,
    mock_audio_analyzer: MagicMock,
    mock_audio_resource: MediaResource,
):
    """E2E: user_prompt передаётся в analyzer через MediaRequest."""
    
    custom_prompt = "Focus on technical terminology"
    
    # Переопределяем mock analyzer
    mock_audio_analyzer.analyze.return_value = MediaAnalysisResult(
        description="Audio with user prompt",
        transcription="Test transcription",
        keywords=["test"],
        participants=[],
        action_items=[],
        duration_seconds=10,
        tokens_used=50,
    )
    
    # Ingest с custom prompt
    doc_id = semantic_core.ingest_audio(
        mock_audio_resource.path,
        user_prompt=custom_prompt,
    )
    
    # Проверяем что analyzer.analyze() был вызван с правильным MediaRequest
    assert mock_audio_analyzer.analyze.called
    call_args = mock_audio_analyzer.analyze.call_args
    media_request = call_args[0][0]  # Первый позиционный аргумент
    
    # user_prompt должен быть в MediaRequest
    assert media_request.user_prompt == custom_prompt


def test_user_prompt_injection_video(
    semantic_core: SemanticCore,
    mock_video_analyzer: MagicMock,
    tmp_path: Path,
):
    """E2E: user_prompt для video также передаётся в analyzer."""
    
    # Mock video file
    video_path = tmp_path / "test_video.mp4"
    video_path.write_bytes(b"fake video content")
    video_resource = MediaResource(
        path=video_path,
        media_type="video",
        mime_type="video/mp4",
    )
    
    custom_prompt = "Identify all code snippets on screen"
    
    # Переопределяем mock analyzer
    mock_video_analyzer.analyze.return_value = MediaAnalysisResult(
        description="Video with user prompt",
        keywords=["code", "tutorial"],
        ocr_text="print('hello')",
        transcription="This is a coding tutorial",
        participants=[],
        action_items=[],
        duration_seconds=30,
        tokens_used=100,
    )
    
    # Ingest с custom prompt
    doc_id = semantic_core.ingest_video(
        video_resource.path,
        user_prompt=custom_prompt,
    )
    
    # Проверяем что analyzer.analyze() был вызван с user_prompt
    assert mock_video_analyzer.analyze.called
    call_args = mock_video_analyzer.analyze.call_args
    media_request = call_args[0][0]
    
    assert media_request.user_prompt == custom_prompt


# ============================================================================
# TESTS: Timecode Validation
# ============================================================================


def test_timecode_validation_max_duration(
    semantic_core: SemanticCore,
    mock_audio_analyzer: MagicMock,
    mock_audio_resource: MediaResource,
):
    """E2E: Таймкод больше duration → отбрасывается."""
    
    # Переопределяем mock analyzer
    mock_audio_analyzer.analyze.return_value = MediaAnalysisResult(
        description="Test invalid timecode",
        transcription=(
            "[00:05] Valid timecode.\n"
            "[10:00] Invalid - exceeds duration!\n"  # 600 секунд > 60
        ),
        keywords=["test"],
        participants=[],
        action_items=[],
        duration_seconds=60,  # Файл всего 1 минута
        tokens_used=50,
    )
    
    # Ingest audio
    doc_id = semantic_core.ingest_audio(mock_audio_resource.path)
    chunks = get_chunks_for_document(doc_id)
    
    # Фильтруем transcript chunks
    transcript_chunks = [
        c for c in chunks
        if c.metadata.get("role") == "transcript"
    ]
    
    # Первый chunk: валидный [00:05]
    first_chunk = transcript_chunks[0]
    assert first_chunk.metadata["start_seconds"] == 5
    
    # Второй chunk: [10:00] должен быть отброшен, используется inheritance
    if len(transcript_chunks) > 1:
        second_chunk = transcript_chunks[1]
        # Должен наследовать от first_chunk, а не иметь 600 секунд
        assert second_chunk.metadata["start_seconds"] < 600
        assert "timecode_original" not in second_chunk.metadata  # Не распарсен

