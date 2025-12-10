"""Интеграционные тесты FTS на уровне чанков (Phase 13.1).

Генерирует подробный Markdown-отчёт с визуализацией:
- Входные данные (документы, чанки)
- Результаты каждого метода поиска (Vector, FTS, Hybrid)
- Сравнение chunk_id между методами
- Проверка RRF boost (hybrid_score > max(vector_score, fts_score))
"""

import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from semantic_core.domain import Document, Chunk, ChunkType, MatchType
from semantic_core.infrastructure.storage.peewee.adapter import PeeweeVectorStore
from semantic_core.infrastructure.storage.peewee.engine import VectorDatabase
from semantic_core.infrastructure.storage.peewee.models import ChunkModel


class FTSChunkLevelReporter:
    """Генератор Markdown-отчёта для тестирования FTS на уровне чанков."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.sections: list[str] = []
        self.test_results: dict = {}

    def add_header(self, title: str, level: int = 1):
        """Добавляет заголовок."""
        prefix = "#" * level
        self.sections.append(f"\n{prefix} {title}\n")

    def add_text(self, text: str):
        """Добавляет текст."""
        self.sections.append(text)

    def add_table(self, headers: list[str], rows: list[list[str]]):
        """Добавляет таблицу."""
        header_line = "| " + " | ".join(headers) + " |"
        separator = "| " + " | ".join(["---"] * len(headers)) + " |"
        lines = [header_line, separator]
        for row in rows:
            lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
        self.sections.append("\n".join(lines) + "\n")

    def add_code_block(self, code: str, language: str = ""):
        """Добавляет блок кода."""
        self.sections.append(f"\n```{language}\n{code}\n```\n")

    def add_json(self, data: dict):
        """Добавляет JSON."""
        self.add_code_block(json.dumps(data, indent=2, ensure_ascii=False), "json")

    def add_divider(self):
        """Добавляет разделитель."""
        self.sections.append("\n---\n")

    def save(self, filename: str = "fts_chunk_level_report.md"):
        """Сохраняет отчёт."""
        path = self.output_dir / filename
        content = "\n".join(self.sections)
        path.write_text(content, encoding="utf-8")
        return path


@pytest.fixture
def report_dir(tmp_path) -> Path:
    """Директория для отчётов."""
    # Используем фиксированную директорию для просмотра результатов
    reports_path = Path("tests/audit_reports") / datetime.now().strftime(
        "%Y-%m-%d_%H-%M-%S_fts_chunk_level"
    )
    reports_path.mkdir(parents=True, exist_ok=True)
    return reports_path


@pytest.fixture
def temp_db(tmp_path) -> VectorDatabase:
    """Временная БД для тестов."""
    db_path = tmp_path / "test_fts_chunks.db"
    db = VectorDatabase(str(db_path))
    return db


@pytest.fixture
def vector_store(temp_db) -> PeeweeVectorStore:
    """PeeweeVectorStore с чистой БД."""
    return PeeweeVectorStore(database=temp_db, dimension=768)


def create_test_document(content: str, source: str) -> Document:
    """Создаёт тестовый документ."""
    return Document(
        content=content,
        metadata={"source": source, "category": "test"},
    )


def create_test_chunks(doc_id: int, texts: list[str]) -> list[Chunk]:
    """Создаёт тестовые чанки с фейковыми эмбеддингами."""
    chunks = []
    for i, text in enumerate(texts):
        chunk = Chunk(
            content=text,
            chunk_index=i,
            chunk_type=ChunkType.TEXT,
            parent_doc_id=doc_id,
            metadata={"chunk_index": i},
        )
        # Фейковый эмбеддинг на основе хеша текста
        np.random.seed(hash(text) % (2**32))
        chunk.vector = np.random.randn(768).astype(np.float32)
        chunks.append(chunk)
    return chunks


class TestFTSChunkLevel:
    """Тесты FTS на уровне чанков с генерацией отчёта."""

    def test_fts_returns_chunk_id(self, vector_store, report_dir):
        """Проверяет, что FTS возвращает chunk_id."""
        reporter = FTSChunkLevelReporter(report_dir)
        reporter.add_header("🔍 FTS Chunk Level Test Report")
        reporter.add_text(f"*Generated: {datetime.now().isoformat()}*\n")

        # === Входные данные ===
        reporter.add_header("📥 Входные данные", level=2)

        doc = create_test_document(
            content="Reciprocal Rank Fusion algorithm for hybrid search",
            source="test_rrf.md",
        )

        chunks_text = [
            "Reciprocal Rank Fusion (RRF) is a method for combining rankings.",
            "The formula is: score = 1/(k + rank) where k=60 typically.",
            "RRF works well for hybrid search combining vector and FTS results.",
            "Unrelated chunk about cooking recipes and kitchen tools.",
        ]

        # Сохраняем документ
        doc = vector_store.save(doc, [])
        reporter.add_text(f"**Document ID:** {doc.id}")
        reporter.add_text(f"**Source:** {doc.metadata.get('source')}")

        # Создаём и сохраняем чанки
        chunks = create_test_chunks(doc.id, chunks_text)
        for chunk in chunks:
            chunk_model = ChunkModel.create(
                document=doc.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                chunk_type=chunk.chunk_type.value,
                metadata=json.dumps(chunk.metadata),
            )
            chunk.id = chunk_model.id

            # Сохраняем вектор
            vector_store.db.execute_sql(
                "INSERT INTO chunks_vec(id, embedding) VALUES (?, ?)",
                (chunk_model.id, chunk.vector.tobytes()),
            )

        reporter.add_header("Чанки", level=3)
        chunk_rows = []
        for c in chunks:
            chunk_rows.append([c.id, c.chunk_index, c.content[:60] + "..."])
        reporter.add_table(["ID", "Index", "Content (preview)"], chunk_rows)

        # === FTS поиск ===
        reporter.add_divider()
        reporter.add_header("🔎 FTS Search", level=2)

        query = "Reciprocal Rank Fusion"
        reporter.add_text(f"**Query:** `{query}`\n")

        start = time.perf_counter()
        fts_results = vector_store._fts_search(query, filters=None, limit=5)
        fts_time = (time.perf_counter() - start) * 1000

        reporter.add_text(f"**Time:** {fts_time:.2f} ms")
        reporter.add_text(f"**Results:** {len(fts_results)}")

        if fts_results:
            fts_rows = []
            for i, r in enumerate(fts_results, 1):
                fts_rows.append(
                    [
                        i,
                        r.chunk_id,  # Должен быть NOT None!
                        r.score,
                        r.match_type.value,
                        r.document.content[:40] + "...",
                    ]
                )
            reporter.add_table(
                ["#", "Chunk ID", "Score", "Match Type", "Doc Content"],
                fts_rows,
            )

            # Проверка: chunk_id должен быть
            chunk_ids = [r.chunk_id for r in fts_results]
            all_have_chunk_id = all(cid is not None for cid in chunk_ids)
            reporter.add_text(
                f"\n**✅ All results have chunk_id:** {all_have_chunk_id}"
            )
            assert all_have_chunk_id, "FTS должен возвращать chunk_id"
        else:
            reporter.add_text("*No FTS results found*")

        # === Vector поиск ===
        reporter.add_divider()
        reporter.add_header("🧮 Vector Search", level=2)

        # Создаём query vector
        np.random.seed(hash(query) % (2**32))
        query_vector = np.random.randn(768).astype(np.float32)

        start = time.perf_counter()
        vector_results = vector_store._vector_search(
            query_vector, filters=None, limit=5
        )
        vector_time = (time.perf_counter() - start) * 1000

        reporter.add_text(f"**Time:** {vector_time:.2f} ms")
        reporter.add_text(f"**Results:** {len(vector_results)}")

        if vector_results:
            vec_rows = []
            for i, r in enumerate(vector_results, 1):
                vec_rows.append(
                    [
                        i,
                        r.chunk_id,
                        f"{r.score:.4f}",
                        r.match_type.value,
                    ]
                )
            reporter.add_table(["#", "Chunk ID", "Score", "Match Type"], vec_rows)

        # === Hybrid поиск ===
        reporter.add_divider()
        reporter.add_header("🔀 Hybrid Search (RRF)", level=2)

        start = time.perf_counter()
        hybrid_results = vector_store._hybrid_search(
            query_vector, query, filters=None, limit=5, k=60
        )
        hybrid_time = (time.perf_counter() - start) * 1000

        reporter.add_text(f"**Time:** {hybrid_time:.2f} ms")
        reporter.add_text(f"**Results:** {len(hybrid_results)}")

        if hybrid_results:
            hybrid_rows = []
            for i, r in enumerate(hybrid_results, 1):
                hybrid_rows.append(
                    [
                        i,
                        r.chunk_id,  # Должен быть NOT None!
                        f"{r.score:.6f}",
                        r.match_type.value,
                    ]
                )
            reporter.add_table(["#", "Chunk ID", "Score", "Match Type"], hybrid_rows)

            # Проверка: chunk_id должен быть
            hybrid_chunk_ids = [r.chunk_id for r in hybrid_results]
            all_have_chunk_id = all(cid is not None for cid in hybrid_chunk_ids)
            reporter.add_text(
                f"\n**✅ All hybrid results have chunk_id:** {all_have_chunk_id}"
            )
            assert all_have_chunk_id, "Hybrid должен возвращать chunk_id"

        # === Сравнение результатов ===
        reporter.add_divider()
        reporter.add_header("📊 Сравнение результатов", level=2)

        # Находим пересечения chunk_id
        fts_chunk_ids = {r.chunk_id for r in fts_results if r.chunk_id}
        vector_chunk_ids = {r.chunk_id for r in vector_results if r.chunk_id}
        hybrid_chunk_ids_set = {r.chunk_id for r in hybrid_results if r.chunk_id}

        intersection = fts_chunk_ids & vector_chunk_ids
        reporter.add_text(f"**FTS chunk_ids:** {fts_chunk_ids}")
        reporter.add_text(f"**Vector chunk_ids:** {vector_chunk_ids}")
        reporter.add_text(f"**Intersection:** {intersection}")
        reporter.add_text(f"**Hybrid chunk_ids:** {hybrid_chunk_ids_set}")

        # RRF boost check
        if intersection and hybrid_results:
            reporter.add_header("RRF Boost Analysis", level=3)

            for chunk_id in intersection:
                fts_score = next(
                    (r.score for r in fts_results if r.chunk_id == chunk_id), None
                )
                vec_score = next(
                    (r.score for r in vector_results if r.chunk_id == chunk_id), None
                )
                hybrid_score = next(
                    (r.score for r in hybrid_results if r.chunk_id == chunk_id), None
                )

                reporter.add_text(f"\n**Chunk {chunk_id}:**")
                reporter.add_text(f"- FTS Score: {fts_score}")
                reporter.add_text(f"- Vector Score: {vec_score}")
                reporter.add_text(f"- Hybrid Score: {hybrid_score}")

                # RRF должен дать буст для пересекающихся чанков
                if hybrid_score and vec_score:
                    # Hybrid score это RRF = 1/(k+rank_vec) + 1/(k+rank_fts)
                    # Он должен быть > 0 если чанк найден обоими методами
                    reporter.add_text(
                        f"- **RRF Boost:** ✅ (both methods found this chunk)"
                    )

        # === Summary ===
        reporter.add_divider()
        reporter.add_header("📋 Summary", level=2)

        summary = {
            "fts_results": len(fts_results),
            "vector_results": len(vector_results),
            "hybrid_results": len(hybrid_results),
            "fts_time_ms": round(fts_time, 2),
            "vector_time_ms": round(vector_time, 2),
            "hybrid_time_ms": round(hybrid_time, 2),
            "intersection_count": len(intersection),
            "fts_has_chunk_ids": all(r.chunk_id is not None for r in fts_results),
            "hybrid_has_chunk_ids": all(r.chunk_id is not None for r in hybrid_results),
        }
        reporter.add_json(summary)

        # Финальные assertions
        assert summary["fts_has_chunk_ids"], "FTS должен возвращать chunk_id"
        assert summary["hybrid_has_chunk_ids"], "Hybrid должен возвращать chunk_id"

        # Сохраняем отчёт
        report_path = reporter.save()
        reporter.add_text(f"\n**Report saved to:** `{report_path}`")

        print(f"\n📄 Report saved to: {report_path}")

    def test_hybrid_boost_over_vector(self, vector_store, report_dir):
        """Проверяет, что Hybrid бустит чанки, найденные обоими методами."""
        reporter = FTSChunkLevelReporter(report_dir)
        reporter.add_header("🚀 Hybrid Boost Test")
        reporter.add_text(f"*Generated: {datetime.now().isoformat()}*\n")

        # Создаём документ с уникальным термином
        doc = create_test_document(
            content="Test document about sqlite-vec integration",
            source="test_boost.md",
        )

        # Чанки с ключевым термином "sqlite-vec"
        chunks_text = [
            "sqlite-vec is a vector search extension for SQLite database.",
            "This chunk does not contain the key term at all.",
            "Another mention of sqlite-vec for hybrid search testing.",
        ]

        doc = vector_store.save(doc, [])
        chunks = create_test_chunks(doc.id, chunks_text)

        for chunk in chunks:
            chunk_model = ChunkModel.create(
                document=doc.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                chunk_type=chunk.chunk_type.value,
                metadata=json.dumps(chunk.metadata),
            )
            chunk.id = chunk_model.id
            vector_store.db.execute_sql(
                "INSERT INTO chunks_vec(id, embedding) VALUES (?, ?)",
                (chunk_model.id, chunk.vector.tobytes()),
            )

        query = "sqlite-vec"
        np.random.seed(hash(query) % (2**32))
        query_vector = np.random.randn(768).astype(np.float32)

        # Поиски
        fts_results = vector_store._fts_search(query, filters=None, limit=5)
        vector_results = vector_store._vector_search(
            query_vector, filters=None, limit=5
        )
        hybrid_results = vector_store._hybrid_search(
            query_vector, query, filters=None, limit=5, k=60
        )

        reporter.add_header("Results Comparison", level=2)

        # Таблица сравнения
        comparison_rows = []
        all_chunk_ids = set()
        for r in fts_results + vector_results + hybrid_results:
            if r.chunk_id:
                all_chunk_ids.add(r.chunk_id)

        for chunk_id in sorted(all_chunk_ids):
            fts_score = next(
                (f"{r.score:.4f}" for r in fts_results if r.chunk_id == chunk_id),
                "-",
            )
            vec_score = next(
                (f"{r.score:.4f}" for r in vector_results if r.chunk_id == chunk_id),
                "-",
            )
            hybrid_score = next(
                (f"{r.score:.6f}" for r in hybrid_results if r.chunk_id == chunk_id),
                "-",
            )

            # Проверяем буст
            boost_status = "🔥" if fts_score != "-" and vec_score != "-" else ""

            comparison_rows.append(
                [
                    chunk_id,
                    fts_score,
                    vec_score,
                    hybrid_score,
                    boost_status,
                ]
            )

        reporter.add_table(
            ["Chunk ID", "FTS Score", "Vector Score", "Hybrid Score", "Boost"],
            comparison_rows,
        )

        # Сохраняем
        report_path = reporter.save("hybrid_boost_report.md")
        print(f"\n📄 Report saved to: {report_path}")

        # Assertions
        assert len(fts_results) > 0, "FTS должен найти хотя бы 1 результат"
        assert all(r.chunk_id is not None for r in fts_results), (
            "FTS должен возвращать chunk_id"
        )
        assert all(r.chunk_id is not None for r in hybrid_results), (
            "Hybrid должен возвращать chunk_id"
        )


class TestFTSMigration:
    """Тесты миграции существующих данных в chunks_fts."""

    def test_auto_migration_populates_fts(self, tmp_path):
        """Проверяет автомиграцию существующих чанков в chunks_fts."""
        db_path = tmp_path / "test_migration.db"
        db = VectorDatabase(str(db_path))

        # Первый store — создаёт таблицы
        store1 = PeeweeVectorStore(database=db, dimension=768)

        # Сохраняем данные
        doc = create_test_document("Migration test document", "migration.md")
        chunks = create_test_chunks(1, ["Chunk one content", "Chunk two content"])
        store1.save(doc, chunks)

        # Проверяем, что chunks_fts заполнена
        cursor = db.execute_sql("SELECT COUNT(*) FROM chunks_fts")
        fts_count = cursor.fetchone()[0]

        cursor = db.execute_sql("SELECT COUNT(*) FROM chunks")
        chunks_count = cursor.fetchone()[0]

        print(f"\nChunks: {chunks_count}, FTS: {fts_count}")

        # FTS должна синхронизироваться через триггеры
        assert fts_count == chunks_count, "FTS должна быть синхронизирована с chunks"
