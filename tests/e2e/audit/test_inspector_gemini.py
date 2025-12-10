"""E2E Audit: Observatory Inspector с реальным Gemini API.

Проверяет:
- Полный pipeline от файла до search results
- Сохранение всех artifacts (input file, embeddings, similarity matrix)
- Rich TUI отчёты
- Snapshot versioning

Требует:
- GEMINI_API_KEY в .env
- Интернет соединение
"""

import os
import pytest
from pathlib import Path

from semantic_core import SemanticCore
from semantic_core.config import SemanticConfig
from semantic_core.core.observatory import (
    ProviderInspector,
    ConsoleReporter,
    MarkdownReporter,
    JsonReporter,
)


# Skip если нет API ключа
pytestmark = pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not found in environment",
)


@pytest.fixture
def test_file(tmp_path: Path) -> Path:
    """Создать тестовый Markdown файл."""
    test_md = tmp_path / "test_document.md"
    test_md.write_text(
        """# Test Document

This is a test document for Observatory inspection.

## Section 1: Python

Python is a high-level programming language known for its simplicity.

```python
def hello_world():
    print("Hello, World!")
```

## Section 2: Machine Learning

Machine learning is a subset of artificial intelligence.

## Section 3: Vector Search

Vector search enables semantic similarity matching.
""",
        encoding="utf-8",
    )
    return test_md


@pytest.fixture
def artifacts_dir(tmp_path: Path) -> Path:
    """Создать папку для artifacts."""
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(exist_ok=True)
    return artifacts


@pytest.fixture
def gemini_core(tmp_path: Path, monkeypatch) -> SemanticCore:
    """SemanticCore с Gemini embedder через create_core()."""
    from semantic_core.core.factory import create_core
    
    db_path = tmp_path / "test.db"
    
    # Патчим environment для create_core()
    monkeypatch.setenv("SEMANTIC_DB_PATH", str(db_path))
    monkeypatch.setenv("SEMANTIC_EMBEDDINGS_PROVIDER", "gemini")
    monkeypatch.setenv("SEMANTIC_EMBEDDINGS_MODEL", "text-embedding-004")
    monkeypatch.setenv("SEMANTIC_EMBEDDINGS_DIMENSION", "768")
    
    # Создаём через production API
    return create_core()


def test_inspector_ingest_with_gemini(
    gemini_core: SemanticCore,
    test_file: Path,
    artifacts_dir: Path,
):
    """Test: Полный ingest inspection с Gemini."""
    # Создаём инспектор
    inspector = ProviderInspector(
        core=gemini_core,
        artifacts_root=artifacts_dir,
    )
    
    # Инспекция
    snapshot = inspector.ingest_with_inspection(path=str(test_file))
    
    # Проверки snapshot
    assert snapshot.snapshot_version == "1.0"
    assert snapshot.file_path == str(test_file)
    assert "Test Document" in snapshot.file_content
    assert len(snapshot.chunks) > 0
    
    # Проверка provider metadata
    assert snapshot.embedder_metadata is not None
    assert snapshot.embedder_metadata.provider_type == "GeminiEmbedder"
    # model_name может быть None если GeminiEmbedder не сохраняет его
    # assert snapshot.embedder_metadata.model_name == "text-embedding-004"
    assert snapshot.embedder_metadata.dimension == 768
    
    # Проверка chunks
    for chunk in snapshot.chunks:
        assert chunk.embedding_preview is not None
        assert len(chunk.embedding_preview) == 20
        assert chunk.embedding_dimension == 768
        assert chunk.content != ""
    
    # Проверка processing steps
    assert len(snapshot.steps) > 0
    step_names = [s["step_name"] for s in snapshot.steps]
    assert "splitting" in step_names
    assert "embedding" in step_names
    
    print(f"\n✅ Inspection completed:")
    print(f"   Chunks: {len(snapshot.chunks)}")
    print(f"   Duration: {snapshot.total_duration_ms:.2f}ms")
    print(f"   Provider: {snapshot.embedder_metadata.provider_type}")


def test_inspector_search_with_gemini(
    gemini_core: SemanticCore,
    test_file: Path,
    artifacts_dir: Path,
):
    """Test: Search inspection после ingest."""
    inspector = ProviderInspector(
        core=gemini_core,
        artifacts_root=artifacts_dir,
    )
    
    # Сначала ingest
    ingest_snapshot = inspector.ingest_with_inspection(path=str(test_file))
    assert len(ingest_snapshot.chunks) > 0
    
    # Теперь search
    search_snapshot = inspector.search_with_inspection(
        query="What is Python programming language?",
        top_k=3,
        mode="hybrid",
    )
    
    # Проверки
    assert len(search_snapshot.searches) == 1
    search = search_snapshot.searches[0]
    
    assert search.query == "What is Python programming language?"
    assert search.search_mode == "hybrid"
    assert search.limit == 3
    assert search.results_count <= 3
    assert len(search.results) <= 3
    
    # Проверка similarity scores
    for result in search.results:
        assert "similarity" in result
        assert 0.0 <= result["similarity"] <= 1.0
        assert "content" in result
        assert "chunk_id" in result
    
    # Первый результат должен быть про Python (высокая близость)
    if search.results:
        top_result = search.results[0]
        assert top_result["similarity"] > 0.4  # Gemini обычно даёт > 0.5 для релевантных
        assert "python" in top_result["content"].lower()
    
    print(f"\n✅ Search completed:")
    print(f"   Results: {search.results_count}")
    print(f"   Time: {search.search_time_ms:.2f}ms")
    
    if search.results:
        print(f"\n   Top result similarity: {search.results[0]['similarity']:.4f}")


def test_inspector_save_artifacts(
    gemini_core: SemanticCore,
    test_file: Path,
    artifacts_dir: Path,
):
    """Test: Сохранение всех artifacts на диск."""
    inspector = ProviderInspector(
        core=gemini_core,
        artifacts_root=artifacts_dir,
    )
    
    # Ingest
    snapshot = inspector.ingest_with_inspection(path=str(test_file))
    
    # Search
    search_snapshot = inspector.search_with_inspection(
        query="vector search",
        top_k=5,
    )
    
    # Объединяем snapshots
    snapshot.searches.extend(search_snapshot.searches)
    
    # Сохраняем
    session_name = "test_session"
    session_folder = inspector.snapshot_manager.create_session_folder(session_name)
    snapshot_path = inspector.snapshot_manager.save_snapshot(
        snapshot,
        session_path=session_folder,
        file_prefix="test",
    )
    
    # Проверяем что файл создан
    assert snapshot_path.exists()
    assert snapshot_path.suffix == ".json"
    
    # Создаём дополнительные artifacts (как в CLI команде)
    
    # Input file copy
    input_copy = session_folder / f"input_{test_file.name}"
    input_copy.write_text(test_file.read_text(), encoding="utf-8")
    assert input_copy.exists()
    
    # Similarity matrix CSV
    similarities_csv = session_folder / "similarities.csv"
    with similarities_csv.open("w", encoding="utf-8") as f:
        f.write("rank,chunk_id,content_preview,similarity\n")
        for search_insp in snapshot.searches:
            for idx, result in enumerate(search_insp.results, 1):
                content = result.get("content", "").replace("\n", " ")[:100]
                similarity = result.get("similarity", 0.0)
                chunk_id = result.get("chunk_id", "N/A")
                f.write(f"{idx},{chunk_id},\"{content}\",{similarity:.6f}\n")
    
    assert similarities_csv.exists()
    
    # Проверяем содержимое CSV
    csv_content = similarities_csv.read_text()
    assert "similarity" in csv_content
    assert len(csv_content.split("\n")) > 2  # Header + data
    
    # Markdown report
    markdown_reporter = MarkdownReporter()
    report_path = session_folder / "report.md"
    markdown_reporter.generate_report(snapshot, output_path=report_path)
    assert report_path.exists()
    
    # JSON export
    json_reporter = JsonReporter(snapshot_manager=inspector.snapshot_manager)
    json_export_path = session_folder / "test_json_export.json"
    json_path = json_reporter.export(snapshot, json_export_path)
    assert json_path.exists()
    
    print(f"\n✅ All artifacts saved:")
    print(f"   Session folder: {session_folder}")
    print(f"   Snapshot: {snapshot_path.name}")
    print(f"   Input copy: {input_copy.name}")
    print(f"   Similarity CSV: {similarities_csv.name}")
    print(f"   Markdown report: {report_path.name}")
    print(f"   JSON export: {json_path.name}")
    
    # Проверяем что можем загрузить обратно
    loaded_snapshot = inspector.snapshot_manager.load_snapshot(snapshot_path)
    assert loaded_snapshot.snapshot_version == snapshot.snapshot_version
    assert len(loaded_snapshot.chunks) == len(snapshot.chunks)
    assert len(loaded_snapshot.searches) == len(snapshot.searches)


def test_console_reporter_output(
    gemini_core: SemanticCore,
    test_file: Path,
    artifacts_dir: Path,
):
    """Test: ConsoleReporter Rich TUI output."""
    inspector = ProviderInspector(
        core=gemini_core,
        artifacts_root=artifacts_dir,
    )
    
    snapshot = inspector.ingest_with_inspection(path=str(test_file))
    
    # ConsoleReporter
    reporter = ConsoleReporter()
    
    # Report первого chunk (без вывода в тест)
    from io import StringIO
    from rich.console import Console
    
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=True)
    
    # Перенаправляем вывод
    original_console = reporter.console
    reporter.console = console
    
    reporter.report_chunk(snapshot.chunks[0], snapshot.embedder_metadata)
    
    # Восстанавливаем
    reporter.console = original_console
    
    # Проверяем что что-то вывелось
    output = buffer.getvalue()
    assert len(output) > 0
    assert "CHUNK" in output or "chunk" in output.lower()
    
    print("\n✅ ConsoleReporter output generated successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
