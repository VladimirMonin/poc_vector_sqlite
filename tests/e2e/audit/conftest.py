"""Конфигурация pytest для e2e audit тестов.

ПОЛНАЯ интеграция с реальным Gemini API.
Отчёты содержат ВСЕ данные: чанки, эмбеддинги, запросы к LLM, ответы.
"""

import json
import os
import time
import pytest
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv
import numpy as np

# Загружаем .env
load_dotenv()

from semantic_core import (
    SemanticCore,
    PeeweeVectorStore,
    init_peewee_database,
)
from semantic_core.domain import Document, Chunk, ChunkType
from semantic_core.domain.media import MediaAnalysisResult
from semantic_core.processing.parsers import MarkdownNodeParser
from semantic_core.processing.splitters import SmartSplitter
from semantic_core.processing.context import HierarchicalContextStrategy
from semantic_core.infrastructure.gemini.embedder import GeminiEmbedder


# ============================================================================
# Пути
# ============================================================================


@pytest.fixture(scope="session")
def test_assets_path() -> Path:
    """Путь к папке с тестовыми ассетами."""
    return Path(__file__).parent.parent.parent / "asests"


@pytest.fixture(scope="session")
def audit_reports_root() -> Path:
    """Корневая папка для отчётов."""
    return Path(__file__).parent.parent.parent / "audit_reports"


@pytest.fixture(scope="session")
def audit_session(audit_reports_root: Path) -> Path:
    """Создаёт папку отчётов для текущего запуска."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    session_path = audit_reports_root / timestamp
    session_path.mkdir(parents=True, exist_ok=True)
    return session_path


# ============================================================================
# Data Classes для отчётов
# ============================================================================


@dataclass
class ChunkInspection:
    """Информация о чанке."""

    chunk_id: int
    chunk_type: str
    content: str
    headers: list[str]
    language: Optional[str]
    size: int
    context_text: str
    embedding_preview: Optional[list[float]] = None
    embedding_dimension: int = 0


@dataclass
class MediaInspection:
    """Полная информация об обработке медиа."""

    asset_path: str
    asset_absolute_path: str
    media_type: str
    file_size_bytes: int
    surrounding_text_before: str
    surrounding_text_after: str
    system_prompt: str
    user_prompt: str
    model_name: str
    response_raw: Optional[dict]
    response_parsed: Optional[MediaAnalysisResult]
    final_chunk_content: str
    processing_time_ms: float


@dataclass
class SearchInspection:
    """Полная информация о поисковом запросе."""

    query: str
    search_mode: str
    limit: int
    query_vector_preview: list[float]
    query_vector_dimension: int
    results: list[dict]
    results_count: int
    search_time_ms: float


@dataclass
class InspectionReport:
    """Полный отчёт инспекции."""

    file_path: str
    file_content_preview: str
    chunks: list[ChunkInspection] = field(default_factory=list)
    media: list[MediaInspection] = field(default_factory=list)
    searches: list[SearchInspection] = field(default_factory=list)


# ============================================================================
# Глобальный коллектор отчётов (session-scoped)
# ============================================================================


class AuditCollector:
    """Глобальный коллектор всех отчётов за сессию."""

    def __init__(self, session_path: Path):
        self.session_path = session_path
        self.reports: list[InspectionReport] = []
        self.media_inspections: list[MediaInspection] = []
        self.search_inspections: list[SearchInspection] = []

    def add_report(self, report: InspectionReport):
        self.reports.append(report)

    def add_media(self, inspection: MediaInspection):
        self.media_inspections.append(inspection)

    def add_search(self, inspection: SearchInspection):
        self.search_inspections.append(inspection)

    def generate_chunking_report(self) -> str:
        """Генерирует ПОЛНЫЙ отчёт о чанкинге."""
        lines = [
            "# 📋 Chunking Audit Report",
            "",
            f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            "",
            "## Summary",
            "",
            f"- **Total Files Processed:** {len(self.reports)}",
            f"- **Total Chunks Created:** {sum(len(r.chunks) for r in self.reports)}",
            "",
            "---",
            "",
        ]

        for report in self.reports:
            lines.append(f"# 📄 File: `{report.file_path}`")
            lines.append("")
            lines.append("## Source Content (Preview)")
            lines.append("```")
            lines.append(report.file_content_preview)
            lines.append("```")
            lines.append("")
            lines.append(f"**Chunks Generated:** {len(report.chunks)}")
            lines.append("")

            for chunk in report.chunks:
                type_emoji = {
                    "text": "📝",
                    "code": "💻",
                    "table": "📊",
                    "image_ref": "🖼️",
                    "audio_ref": "🎵",
                    "video_ref": "🎬",
                }.get(str(chunk.chunk_type).lower(), "📄")

                lines.append("---")
                lines.append(
                    f"### Chunk #{chunk.chunk_id} [{chunk.chunk_type}] {type_emoji}"
                )
                lines.append("")

                if chunk.headers:
                    breadcrumbs = " > ".join(chunk.headers)
                    lines.append(f"**Headers:** `{breadcrumbs}`")

                if chunk.language:
                    lines.append(f"**Language:** `{chunk.language}`")

                lines.append(f"**Size:** {chunk.size} chars")
                lines.append("")

                # Контент
                lines.append("#### Content")
                if "code" in str(chunk.chunk_type).lower():
                    lang = chunk.language or ""
                    lines.append(f"```{lang}")
                    lines.append(chunk.content)
                    lines.append("```")
                else:
                    lines.append("```")
                    lines.append(chunk.content)
                    lines.append("```")
                lines.append("")

                # Векторный контекст
                lines.append("#### Vector Context (sent to embedder)")
                lines.append("```")
                lines.append(chunk.context_text)
                lines.append("```")
                lines.append("")

                # Эмбеддинг
                if chunk.embedding_preview:
                    preview = ", ".join(
                        f"{v:.6f}" for v in chunk.embedding_preview[:10]
                    )
                    lines.append(f"**Embedding:** `[{preview}, ...]`")
                    lines.append(f"**Dimension:** {chunk.embedding_dimension}")
                lines.append("")

        return "\n".join(lines)

    def generate_media_report(self) -> str:
        """Генерирует ПОЛНЫЙ отчёт о медиа-обработке."""
        lines = [
            "# 🎬 Media Processing Audit Report",
            "",
            f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            "",
            f"**Total Media Files Analyzed:** {len(self.media_inspections)}",
            "",
            "---",
            "",
        ]

        if not self.media_inspections:
            lines.append("*No media files were processed in this session.*")
            lines.append("")
            lines.append("To run media tests with real API:")
            lines.append("```bash")
            lines.append("poetry run pytest tests/e2e/audit/test_media_audit.py -v -s")
            lines.append("```")
            return "\n".join(lines)

        for idx, media in enumerate(self.media_inspections, 1):
            emoji = {"image": "🖼️", "audio": "🎵", "video": "🎬"}.get(
                media.media_type, "📁"
            )

            lines.append(f"# {emoji} Media #{idx}: `{media.asset_path}`")
            lines.append("")
            lines.append(f"| Property | Value |")
            lines.append(f"|----------|-------|")
            lines.append(f"| **Type** | {media.media_type.upper()} |")
            lines.append(f"| **Path** | `{media.asset_absolute_path}` |")
            lines.append(f"| **Size** | {media.file_size_bytes:,} bytes |")
            lines.append(f"| **Processing Time** | {media.processing_time_ms:.2f} ms |")
            lines.append(f"| **Model** | `{media.model_name}` |")
            lines.append("")

            # Контекст
            lines.append("## 1. Surrounding Context")
            lines.append("")
            if media.surrounding_text_before:
                lines.append("**Text Before:**")
                lines.append(f"> {media.surrounding_text_before}")
                lines.append("")
            if media.surrounding_text_after:
                lines.append("**Text After:**")
                lines.append(f"> {media.surrounding_text_after}")
                lines.append("")
            if not media.surrounding_text_before and not media.surrounding_text_after:
                lines.append("*(No surrounding context)*")
                lines.append("")

            # Запрос в модель
            lines.append("## 2. LLM Request")
            lines.append("")
            lines.append("### System Prompt")
            lines.append("```")
            lines.append(media.system_prompt or "(default)")
            lines.append("```")
            lines.append("")
            lines.append("### User Prompt")
            lines.append("```")
            lines.append(media.user_prompt or "(none)")
            lines.append("```")
            lines.append("")

            # Сырой ответ
            lines.append("## 3. Raw API Response")
            lines.append("")
            if media.response_raw:
                lines.append("```json")
                lines.append(
                    json.dumps(media.response_raw, ensure_ascii=False, indent=2)
                )
                lines.append("```")
            else:
                lines.append("*(No raw response captured)*")
            lines.append("")

            # Распарсенный ответ
            lines.append("## 4. Parsed Response (MediaAnalysisResult)")
            lines.append("")
            if media.response_parsed:
                r = media.response_parsed
                lines.append(f"- **Description:** {r.description}")
                if r.alt_text:
                    lines.append(f"- **Alt Text:** {r.alt_text}")
                if r.keywords:
                    lines.append(f"- **Keywords:** `{r.keywords}`")
                if r.ocr_text:
                    lines.append(f"- **OCR Text:** {r.ocr_text[:500]}...")
                if r.transcription:
                    lines.append(f"- **Transcription:** {r.transcription[:500]}...")
                if r.participants:
                    lines.append(f"- **Participants:** {r.participants}")
                if r.duration_seconds:
                    lines.append(f"- **Duration:** {r.duration_seconds} seconds")
            else:
                lines.append("*(Parse failed or no response)*")
            lines.append("")

            # Финальный контент
            lines.append("## 5. Final Chunk Content")
            lines.append("```")
            lines.append(media.final_chunk_content)
            lines.append("```")
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def generate_search_report(self) -> str:
        """Генерирует ПОЛНЫЙ отчёт о поиске."""
        # Собираем все поиски из reports и отдельные
        all_searches = list(self.search_inspections)
        for report in self.reports:
            all_searches.extend(report.searches)

        lines = [
            "# 🔍 Search Audit Report",
            "",
            f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            "",
            f"**Total Searches Executed:** {len(all_searches)}",
            "",
            "---",
            "",
        ]

        if not all_searches:
            lines.append("*No searches were executed in this session.*")
            return "\n".join(lines)

        for idx, search in enumerate(all_searches, 1):
            lines.append(f"# Search #{idx}")
            lines.append("")
            lines.append(f"| Property | Value |")
            lines.append(f"|----------|-------|")
            lines.append(f"| **Query** | `{search.query}` |")
            lines.append(f"| **Mode** | `{search.search_mode}` |")
            lines.append(f"| **Limit** | {search.limit} |")
            lines.append(f"| **Time** | {search.search_time_ms:.2f} ms |")
            lines.append(f"| **Results Found** | {search.results_count} |")
            lines.append("")

            # Вектор запроса
            if search.query_vector_preview:
                preview = ", ".join(
                    f"{v:.6f}" for v in search.query_vector_preview[:10]
                )
                lines.append(f"**Query Vector:** `[{preview}, ...]`")
                lines.append(f"**Dimension:** {search.query_vector_dimension}")
                lines.append("")

            # Результаты
            lines.append("## Results")
            lines.append("")

            if search.results:
                for r in search.results:
                    lines.append(f"### #{r.get('rank', '?')}")
                    lines.append("")
                    lines.append(f"- **Score:** {r.get('score', 0):.6f}")
                    lines.append(f"- **Match Type:** {r.get('match_type', 'unknown')}")
                    lines.append(f"- **Document ID:** {r.get('document_id')}")
                    lines.append(f"- **Chunk ID:** {r.get('chunk_id')}")

                    metadata = r.get("metadata", {})
                    if metadata:
                        lines.append(
                            f"- **Metadata:** `{json.dumps(metadata, ensure_ascii=False)}`"
                        )

                    lines.append("")
                    lines.append("**Content:**")
                    lines.append("```")
                    content = r.get("content_full", r.get("content_preview", ""))
                    lines.append(content[:1000] if len(content) > 1000 else content)
                    lines.append("```")
                    lines.append("")
            else:
                lines.append("*No results found*")
                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def save_all_reports(self):
        """Сохраняет ВСЕ отчёты."""
        # Chunking
        path = self.session_path / "01_chunking_audit.md"
        path.write_text(self.generate_chunking_report(), encoding="utf-8")

        # Media
        path = self.session_path / "02_media_audit.md"
        path.write_text(self.generate_media_report(), encoding="utf-8")

        # Search
        path = self.session_path / "03_search_audit.md"
        path.write_text(self.generate_search_report(), encoding="utf-8")


# ============================================================================
# Session-scoped collector
# ============================================================================


@pytest.fixture(scope="session")
def audit_collector(audit_session: Path) -> AuditCollector:
    """Глобальный коллектор отчётов на всю сессию."""
    collector = AuditCollector(session_path=audit_session)
    yield collector
    # Сохраняем отчёты в конце сессии
    collector.save_all_reports()


# ============================================================================
# PipelineInspector
# ============================================================================


class PipelineInspector:
    """Обёртка над SemanticCore для перехвата данных."""

    def __init__(
        self,
        core: SemanticCore,
        collector: AuditCollector,
    ):
        self.core = core
        self.collector = collector

    @property
    def reports(self) -> list[InspectionReport]:
        """Доступ к отчётам через collector."""
        return self.collector.reports

    def ingest_with_inspection(
        self,
        document: Document,
        mode: str = "sync",
    ) -> Document:
        """Индексирует документ с записью данных."""
        source = document.metadata.get("source", "unknown")
        content_preview = document.content[:500] if document.content else ""

        report = InspectionReport(
            file_path=source,
            file_content_preview=content_preview,
        )

        # 1. Сплиттинг
        chunks = self.core.splitter.split(document)

        # 2. Контекст и инспекция
        vector_texts = []
        for i, chunk in enumerate(chunks):
            context_text = self.core.context_strategy.form_vector_text(chunk, document)
            vector_texts.append(context_text)

            headers = chunk.metadata.get("headers", [])
            chunk_type = (
                chunk.chunk_type.value
                if hasattr(chunk.chunk_type, "value")
                else str(chunk.chunk_type)
            )

            inspection = ChunkInspection(
                chunk_id=i + 1,
                chunk_type=chunk_type,
                content=chunk.content,
                headers=headers,
                language=chunk.language,
                size=len(chunk.content),
                context_text=context_text,
            )
            report.chunks.append(inspection)

        # 3. Эмбеддинги
        if mode == "sync":
            embeddings = self.core.embedder.embed_documents(vector_texts)
            for embedding, inspection in zip(embeddings, report.chunks):
                if hasattr(embedding, "tolist"):
                    vec = embedding.tolist()
                else:
                    vec = list(embedding)
                inspection.embedding_preview = vec[:20]
                inspection.embedding_dimension = len(vec)

            # Присваиваем эмбеддинги чанкам
            for chunk, embedding in zip(chunks, embeddings):
                chunk.embedding = embedding

        # 4. Сохраняем
        saved = self.core.store.save(document, chunks)

        self.collector.add_report(report)
        return saved

    def search_with_inspection(
        self,
        query: str,
        limit: int = 10,
        mode: str = "hybrid",
    ) -> list:
        """Выполняет поиск с записью данных."""
        start_time = time.perf_counter()

        # Вектор запроса
        query_vector = self.core.embedder.embed_query(query)

        # Поиск
        results = self.core.search(query=query, limit=limit, mode=mode)

        search_time = (time.perf_counter() - start_time) * 1000

        # Вектор
        if hasattr(query_vector, "tolist"):
            vec = query_vector.tolist()
        else:
            vec = list(query_vector)

        inspection = SearchInspection(
            query=query,
            search_mode=mode,
            limit=limit,
            query_vector_preview=vec[:20],
            query_vector_dimension=len(vec),
            results=[
                {
                    "rank": i + 1,
                    "score": r.score,
                    "match_type": r.match_type.value if r.match_type else "unknown",
                    "document_id": r.document.id if r.document else None,
                    "chunk_id": r.chunk_id,
                    "content_full": r.document.content if r.document else "",
                    "metadata": r.document.metadata if r.document else {},
                }
                for i, r in enumerate(results)
            ],
            results_count=len(results),
            search_time_ms=search_time,
        )

        self.collector.add_search(inspection)
        return results


# ============================================================================
# Фикстуры
# ============================================================================


@pytest.fixture(scope="session")
def real_embedder():
    """Реальный Gemini Embedder."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY not set in environment")
    return GeminiEmbedder(api_key=api_key)


@pytest.fixture(scope="session")
def audit_db(tmp_path_factory):
    """Изолированная БД для сессии."""
    tmp_path = tmp_path_factory.mktemp("audit")
    db_path = tmp_path / "audit.db"
    db = init_peewee_database(str(db_path))
    yield db
    db.close()


@pytest.fixture(scope="session")
def pipeline_inspector(
    audit_db,
    real_embedder,
    audit_collector: AuditCollector,
) -> PipelineInspector:
    """PipelineInspector с реальным embedder."""
    parser = MarkdownNodeParser()
    splitter = SmartSplitter(parser=parser, chunk_size=500, code_chunk_size=1000)
    context = HierarchicalContextStrategy(include_doc_title=True)
    store = PeeweeVectorStore(audit_db)

    core = SemanticCore(
        embedder=real_embedder,
        store=store,
        splitter=splitter,
        context_strategy=context,
    )

    return PipelineInspector(core=core, collector=audit_collector)
