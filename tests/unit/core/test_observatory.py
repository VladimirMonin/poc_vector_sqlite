"""Unit-тесты для Observatory компонентов.

Тестируем:
- SnapshotManager: сохранение/загрузка
- ProviderInspector: инспекция pipeline
- Reporters: форматирование вывода
"""

import pytest
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, MagicMock

from semantic_core.core.observatory import (
    SnapshotManager,
    ProviderInspector,
    InspectionSnapshot,
    ConsoleReporter,
    MarkdownReporter,
    JsonReporter,
    DiffReporter,
)
from semantic_core.core.observatory.models import (
    ProviderMetadata,
    ChunkInspection,
)
from semantic_core.domain import Document, Chunk, ChunkType


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_artifacts_dir(tmp_path):
    """Временная папка для артефактов."""
    return tmp_path / "artifacts"


@pytest.fixture
def snapshot_manager(temp_artifacts_dir):
    """SnapshotManager с временной папкой."""
    return SnapshotManager(artifacts_root=temp_artifacts_dir)


@pytest.fixture
def sample_provider_metadata():
    """Тестовые метаданные провайдера."""
    return ProviderMetadata(
        provider_type="GeminiEmbedder",
        model_name="gemini-embedding-001",
        dimension=768,
        max_tokens=2048,
        device="cloud",
    )


@pytest.fixture
def sample_chunk_inspection():
    """Тестовая инспекция чанка."""
    return ChunkInspection(
        chunk_id=1,
        chunk_type="text",
        content="Machine learning is a subset of AI.",
        headers=["Introduction", "Overview"],
        language=None,
        size=37,
        context_text="Document: test.md\nMachine learning...",
        embedding_preview=[0.123, -0.456, 0.789],
        embedding_dimension=768,
    )


@pytest.fixture
def sample_snapshot(sample_provider_metadata, sample_chunk_inspection):
    """Тестовый snapshot."""
    return InspectionSnapshot(
        file_path="test.md",
        file_content_preview="# Test\n\nMachine learning...",
        processing_timestamp=datetime.now(),
        total_duration_ms=123.45,
        embedder_metadata=sample_provider_metadata,
        config_hash="abc123",
        chunks=[sample_chunk_inspection],
        steps=[
            {"step_name": "splitting", "duration_ms": 10.0, "chunks_count": 1},
            {"step_name": "embedding", "duration_ms": 100.0, "vectors_count": 1},
        ],
    )


# ============================================================================
# SnapshotManager Tests
# ============================================================================


def test_snapshot_manager_creates_root(temp_artifacts_dir):
    """Тест: SnapshotManager создаёт корневую папку."""
    manager = SnapshotManager(artifacts_root=temp_artifacts_dir)
    assert temp_artifacts_dir.exists()
    assert temp_artifacts_dir.is_dir()


def test_create_session_folder(snapshot_manager):
    """Тест: создание папки сессии."""
    session_path = snapshot_manager.create_session_folder("test_session")
    assert session_path.exists()
    assert session_path.name == "test_session"


def test_create_session_folder_with_timestamp(snapshot_manager):
    """Тест: создание папки с автоматическим timestamp."""
    session_path = snapshot_manager.create_session_folder()
    assert session_path.exists()
    # Проверяем формат: YYYY-MM-DD_HH-MM-SS
    assert len(session_path.name) == 19


def test_save_and_load_snapshot(snapshot_manager, sample_snapshot, tmp_path):
    """Тест: сохранение и загрузка snapshot."""
    session_path = tmp_path / "session"
    session_path.mkdir()

    # Сохраняем
    saved_path = snapshot_manager.save_snapshot(
        sample_snapshot, session_path, "test", compress=False
    )

    assert saved_path.exists()
    assert saved_path.name == "test_inspection.json"

    # Загружаем
    loaded = snapshot_manager.load_snapshot(saved_path)

    assert loaded.file_path == sample_snapshot.file_path
    assert loaded.config_hash == sample_snapshot.config_hash
    assert len(loaded.chunks) == 1
    assert len(loaded.steps) == 2


def test_save_snapshot_compressed(snapshot_manager, sample_snapshot, tmp_path):
    """Тест: сохранение с gzip сжатием."""
    session_path = tmp_path / "session"
    session_path.mkdir()

    saved_path = snapshot_manager.save_snapshot(
        sample_snapshot, session_path, "test", compress=True
    )

    assert saved_path.exists()
    assert saved_path.name == "test_inspection.json.gz"

    # Загружаем
    loaded = snapshot_manager.load_snapshot(saved_path)
    assert loaded.file_path == sample_snapshot.file_path


def test_list_sessions(snapshot_manager):
    """Тест: получение списка сессий."""
    # Создаём несколько сессий
    snapshot_manager.create_session_folder("session1")
    snapshot_manager.create_session_folder("session2")

    sessions = snapshot_manager.list_sessions()
    assert len(sessions) >= 2
    assert all(s.is_dir() for s in sessions)


def test_list_snapshots(snapshot_manager, sample_snapshot, tmp_path):
    """Тест: получение списка snapshot'ов в сессии."""
    session_path = tmp_path / "session"
    session_path.mkdir()

    # Создаём несколько snapshot'ов
    snapshot_manager.save_snapshot(sample_snapshot, session_path, "file1")
    snapshot_manager.save_snapshot(sample_snapshot, session_path, "file2")

    snapshots = snapshot_manager.list_snapshots(session_path)
    assert len(snapshots) == 2
    assert all(s.suffix == ".json" for s in snapshots)


# ============================================================================
# ProviderInspector Tests
# ============================================================================


def test_provider_inspector_initialization():
    """Тест: инициализация ProviderInspector."""
    mock_core = Mock()
    inspector = ProviderInspector(core=mock_core)

    assert inspector.core == mock_core
    assert inspector.snapshot_manager is not None


def test_provider_inspector_extract_metadata():
    """Тест: извлечение метаданных провайдера."""
    mock_core = Mock()
    inspector = ProviderInspector(core=mock_core)

    # Mock embedder
    mock_embedder = Mock()
    mock_embedder.model = "gemini-embedding-001"
    mock_embedder.dimension = 768
    mock_embedder.max_tokens = 2048

    metadata = inspector._extract_provider_metadata(mock_embedder)

    assert metadata.provider_type == "Mock"
    assert metadata.model_name == "gemini-embedding-001"
    assert metadata.dimension == 768
    assert metadata.max_tokens == 2048


def test_provider_inspector_compute_config_hash():
    """Тест: вычисление хеша конфигурации."""
    mock_core = Mock()
    mock_core.embedder.model = "gemini-001"
    mock_core.splitter.chunk_size = 512

    inspector = ProviderInspector(core=mock_core)
    hash1 = inspector._compute_config_hash()

    # Hash должен быть 8 символов (MD5[:8])
    assert len(hash1) == 8

    # Изменяем конфиг
    mock_core.embedder.model = "gemini-002"
    hash2 = inspector._compute_config_hash()

    # Хеши должны отличаться
    assert hash1 != hash2


def test_provider_inspector_ingest(tmp_path):
    """Тест: инспекция индексации документа."""
    # Mock SemanticCore
    mock_core = Mock()
    mock_core.embedder = Mock()
    mock_core.embedder.model = "test-model"
    mock_core.embedder.dimension = 768
    mock_core.embedder.embed_documents = Mock(return_value=[[0.1, 0.2, 0.3]])

    mock_core.splitter = Mock()
    mock_chunk = Chunk(
        content="Test content",
        chunk_type=ChunkType.TEXT,
        chunk_index=0,
        metadata={"headers": ["Test"]},
    )
    mock_core.splitter.split = Mock(return_value=[mock_chunk])
    mock_core.splitter.chunk_size = 512

    mock_core.context_strategy = Mock()
    mock_core.context_strategy.form_vector_text = Mock(
        return_value="Document: test\nTest content"
    )

    mock_core.store = Mock()
    mock_saved_doc = Document(content="Test", metadata={"source": "test.txt"})
    mock_saved_doc.id = 1
    mock_core.store.save = Mock(return_value=mock_saved_doc)

    # Inspector
    inspector = ProviderInspector(core=mock_core)

    # Документ
    doc = Document(content="Test content", metadata={"source": "test.txt"})

    # Инспектируем
    saved, snapshot = inspector.ingest_with_inspection(doc, mode="sync")

    # Проверки
    assert saved.id == 1
    assert snapshot.file_path == "test.txt"
    assert len(snapshot.chunks) == 1
    assert len(snapshot.steps) >= 3  # splitting, context, embedding, save
    assert snapshot.embedder_metadata.model_name == "test-model"


# ============================================================================
# ConsoleReporter Tests
# ============================================================================


def test_console_reporter_initialization():
    """Тест: инициализация ConsoleReporter."""
    from rich.console import Console

    console = Console()
    reporter = ConsoleReporter(console=console)

    assert reporter.console == console


def test_console_reporter_report_chunk(sample_chunk_inspection, capsys):
    """Тест: вывод чанка (захватываем stdout)."""
    reporter = ConsoleReporter()

    # Используем io.StringIO для захвата вывода
    from io import StringIO
    from rich.console import Console

    output = StringIO()
    console = Console(file=output, force_terminal=True)
    reporter.console = console

    reporter.report_chunk(sample_chunk_inspection, index=1)

    result = output.getvalue()
    assert "Chunk #1" in result
    assert "TEXT" in result  # Rich uppercase title


# ============================================================================
# MarkdownReporter Tests
# ============================================================================


def test_markdown_reporter_generate_report(sample_snapshot):
    """Тест: генерация Markdown отчёта."""
    reporter = MarkdownReporter()
    markdown = reporter.generate_report(sample_snapshot)

    assert "# 🔍 Inspection Report" in markdown
    assert "test.md" in markdown
    assert "GeminiEmbedder" in markdown
    assert "Chunk #1" in markdown


def test_markdown_reporter_save_to_file(sample_snapshot, tmp_path):
    """Тест: сохранение отчёта в файл."""
    reporter = MarkdownReporter()
    output_path = tmp_path / "report.md"

    markdown = reporter.generate_report(sample_snapshot, output_path=output_path)

    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert content == markdown


# ============================================================================
# JsonReporter Tests
# ============================================================================


def test_json_reporter_export(sample_snapshot, tmp_path):
    """Тест: экспорт в JSON."""
    reporter = JsonReporter()
    output_path = tmp_path / "snapshot.json"

    saved_path = reporter.export(sample_snapshot, output_path)

    assert saved_path.exists()

    # Проверяем валидность JSON
    with open(saved_path) as f:
        data = json.load(f)

    assert data["file_path"] == "test.md"
    assert data["config_hash"] == "abc123"


# ============================================================================
# DiffReporter Tests
# ============================================================================


def test_diff_reporter_compare_same_snapshots(sample_snapshot):
    """Тест: сравнение идентичных snapshot'ов."""
    reporter = DiffReporter()
    diff = reporter.compare(sample_snapshot, sample_snapshot)

    assert diff["chunks_diff"]["count_changed"] is False
    assert diff["providers_diff"]["embedder_changed"] is False


def test_diff_reporter_compare_different_chunks(sample_snapshot):
    """Тест: сравнение с разным количеством чанков."""
    # Создаём второй snapshot с доп чанком
    snapshot2 = InspectionSnapshot(
        file_path="test.md",
        chunks=[
            sample_snapshot.chunks[0],
            ChunkInspection(
                chunk_id=2,
                chunk_type="text",
                content="Extra chunk",
                headers=[],
                language=None,
                size=11,
                context_text="Extra",
            ),
        ],
    )

    reporter = DiffReporter()
    diff = reporter.compare(sample_snapshot, snapshot2)

    assert diff["chunks_diff"]["baseline_count"] == 1
    assert diff["chunks_diff"]["current_count"] == 2
    assert diff["chunks_diff"]["count_changed"] is True


def test_diff_reporter_compare_different_providers(sample_snapshot):
    """Тест: сравнение с разными провайдерами."""
    snapshot2 = InspectionSnapshot(
        file_path="test.md",
        embedder_metadata=ProviderMetadata(
            provider_type="OpenAIEmbedder",
            model_name="text-embedding-3-small",
        ),
    )

    reporter = DiffReporter()
    diff = reporter.compare(sample_snapshot, snapshot2)

    assert diff["providers_diff"]["embedder_changed"] is True
    assert diff["providers_diff"]["model_changed"] is True
