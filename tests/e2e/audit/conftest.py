"""Конфигурация pytest для e2e audit тестов.

Фикстуры:
    - audit_session: Создаёт папку отчётов для текущего запуска
    - pipeline_inspector: Обёртка над SemanticCore для перехвата данных
    - test_assets_path: Путь к тестовым ассетам (tests/asests/)
"""

import json
import os
import pytest
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Any
from unittest.mock import MagicMock
import numpy as np

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


# ============================================================================
# Пути — ИСПРАВЛЕНО: используем tests/asests/
# ============================================================================


@pytest.fixture(scope="session")
def test_assets_path() -> Path:
    """Путь к папке с тестовыми ассетами (tests/asests/)."""
    return Path(__file__).parent.parent.parent / "asests"


@pytest.fixture(scope="session")
def audit_reports_root() -> Path:
    """Корневая папка для отчётов (tests/audit_reports/)."""
    return Path(__file__).parent.parent.parent / "audit_reports"


@pytest.fixture(scope="session")
def audit_session(audit_reports_root: Path) -> Path:
    """Создаёт папку отчётов для текущего запуска.
    
    Формат: YYYY-MM-DD_HH-MM
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    session_path = audit_reports_root / timestamp
    session_path.mkdir(parents=True, exist_ok=True)
    return session_path


# ============================================================================
# Inspector: Перехват промежуточных данных
# ============================================================================


@dataclass
class ChunkInspection:
    """Информация о чанке для отчёта."""
    
    chunk_id: int
    chunk_type: ChunkType
    content: str
    headers: list[str]
    language: Optional[str]
    size: int
    context_text: str  # Текст для векторизации (полный!)
    embedding_preview: Optional[list[float]] = None  # Первые 10 значений
    embedding_full: Optional[list[float]] = None  # Полный вектор для отчёта


@dataclass
class MediaInspection:
    """Полная информация об обработке медиа."""
    
    asset_path: str
    asset_absolute_path: str
    media_type: str
    file_size_bytes: int
    
    # Контекст
    surrounding_text_before: str
    surrounding_text_after: str
    
    # Запрос в модель
    system_prompt: str
    user_prompt: str
    model_name: str
    
    # Ответ модели (полный!)
    response_raw: Optional[dict]  # Полный JSON ответ
    response_parsed: Optional[MediaAnalysisResult]
    
    # Финальный результат
    final_chunk_content: str
    processing_time_ms: float


@dataclass
class SearchInspection:
    """Полная информация о поисковом запросе."""
    
    query: str
    search_mode: str
    limit: int
    
    # Вектор запроса
    query_vector_full: list[float]  # Полный вектор!
    query_vector_preview: list[float]  # Первые 10
    
    # SQL запросы (если доступны)
    sql_query: Optional[str]
    sql_params: Optional[list]
    
    # Результаты
    results: list[dict]  # Полная информация о каждом результате
    results_count: int
    search_time_ms: float


@dataclass
class InspectionReport:
    """Полный отчёт инспекции."""
    
    file_path: str
    file_content_preview: str  # Первые 500 символов исходного файла
    chunks: list[ChunkInspection] = field(default_factory=list)
    media: list[MediaInspection] = field(default_factory=list)
    searches: list[SearchInspection] = field(default_factory=list)


class PipelineInspector:
    """Обёртка над SemanticCore для перехвата ВСЕХ промежуточных данных.
    
    Записывает:
    - Все чанки с полным контекстом
    - Все эмбеддинги (полные векторы)
    - Все запросы к LLM
    - Все ответы от LLM
    - Все SQL запросы
    """
    
    def __init__(
        self,
        core: SemanticCore,
        session_path: Path,
    ):
        self.core = core
        self.session_path = session_path
        self.reports: list[InspectionReport] = []
        self._current_report: Optional[InspectionReport] = None
    
    def ingest_with_inspection(
        self,
        document: Document,
        mode: str = "sync",
        enrich_media: bool = False,
    ) -> Document:
        """Индексирует документ с записью ВСЕХ промежуточных данных."""
        source = document.metadata.get("source", "unknown")
        content_preview = document.content[:500] if document.content else ""
        
        self._current_report = InspectionReport(
            file_path=source,
            file_content_preview=content_preview,
        )
        
        # 1. Сплиттинг (перехватываем чанки)
        chunks = self.core.splitter.split(document)
        
        # 2. Формируем контекст и записываем инспекцию
        vector_texts = []
        for i, chunk in enumerate(chunks):
            context_text = self.core.context_strategy.form_vector_text(chunk, document)
            vector_texts.append(context_text)
            
            # headers хранятся в metadata
            headers = chunk.metadata.get("headers", [])
            
            inspection = ChunkInspection(
                chunk_id=i + 1,
                chunk_type=chunk.chunk_type,
                content=chunk.content,
                headers=headers,
                language=chunk.language,
                size=len(chunk.content),
                context_text=context_text,  # Полный текст!
            )
            self._current_report.chunks.append(inspection)
        
        # 3. Генерируем эмбеддинги
        if mode == "sync":
            embeddings = self.core.embedder.embed_documents(vector_texts)
            for chunk, embedding, inspection in zip(
                chunks, embeddings, self._current_report.chunks
            ):
                chunk.embedding = embedding
                # Сохраняем ПОЛНЫЙ вектор и preview
                if hasattr(embedding, 'tolist'):
                    full_vec = embedding.tolist()
                else:
                    full_vec = list(embedding)
                
                inspection.embedding_full = full_vec
                inspection.embedding_preview = full_vec[:10]
        
        # 4. Сохраняем в БД
        saved_document = self.core.store.save(document, chunks)
        
        self.reports.append(self._current_report)
        self._current_report = None
        
        return saved_document
    
    def search_with_inspection(
        self,
        query: str,
        limit: int = 10,
        mode: str = "hybrid",
    ) -> list:
        """Выполняет поиск с записью ВСЕХ промежуточных данных."""
        import time
        start_time = time.perf_counter()
        
        # Генерируем вектор запроса
        query_vector = self.core.embedder.embed_query(query)
        
        # Выполняем поиск
        results = self.core.search(query=query, limit=limit, mode=mode)
        
        search_time_ms = (time.perf_counter() - start_time) * 1000
        
        # Получаем полный вектор
        if hasattr(query_vector, 'tolist'):
            full_vec = query_vector.tolist()
        else:
            full_vec = list(query_vector)
        
        inspection = SearchInspection(
            query=query,
            search_mode=mode,
            limit=limit,
            query_vector_full=full_vec,
            query_vector_preview=full_vec[:10],
            sql_query=None,  # TODO: перехватывать SQL
            sql_params=None,
            results=[
                {
                    "rank": i + 1,
                    "score": r.score,
                    "match_type": r.match_type.value if r.match_type else "unknown",
                    "document_id": r.document.id if r.document else None,
                    "content_full": r.document.content if r.document else "",
                    "content_preview": r.document.content[:200] if r.document and r.document.content else "",
                    "metadata": r.document.metadata if r.document else {},
                    "chunk_id": r.chunk_id,
                }
                for i, r in enumerate(results)
            ],
            results_count=len(results),
            search_time_ms=search_time_ms,
        )
        
        # Добавляем к последнему отчёту или создаём новый
        if self.reports:
            self.reports[-1].searches.append(inspection)
        else:
            report = InspectionReport(
                file_path="search_only",
                file_content_preview="",
            )
            report.searches.append(inspection)
            self.reports.append(report)
        
        return results
    
    def add_media_inspection(self, inspection: MediaInspection):
        """Добавляет инспекцию медиа-обработки."""
        if self._current_report:
            self._current_report.media.append(inspection)
        elif self.reports:
            self.reports[-1].media.append(inspection)
    
    def generate_chunking_report(self) -> str:
        """Генерирует ПОЛНЫЙ Markdown-отчёт о чанкинге."""
        lines = [
            "# 📋 Chunking Audit Report",
            "",
            f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            "",
            "## Summary",
            "",
            f"- **Total Files:** {len(self.reports)}",
            f"- **Total Chunks:** {sum(len(r.chunks) for r in self.reports)}",
            "",
            "---",
            "",
        ]
        
        for report in self.reports:
            lines.append(f"# 📄 File: `{report.file_path}`")
            lines.append("")
            lines.append("## Source Content Preview")
            lines.append("```")
            lines.append(report.file_content_preview)
            lines.append("```")
            lines.append("")
            lines.append(f"**Total Chunks:** {len(report.chunks)}")
            lines.append("")
            
            for chunk in report.chunks:
                type_emoji = {
                    ChunkType.TEXT: "📝",
                    ChunkType.CODE: "💻",
                    ChunkType.TABLE: "📊",
                    ChunkType.IMAGE_REF: "🖼️",
                    ChunkType.AUDIO_REF: "🎵",
                    ChunkType.VIDEO_REF: "🎬",
                }.get(chunk.chunk_type, "📄")
                
                lines.append("---")
                lines.append(
                    f"## Chunk #{chunk.chunk_id} [{chunk.chunk_type.value.upper()}] {type_emoji}"
                )
                lines.append("")
                
                if chunk.headers:
                    breadcrumbs = " > ".join(chunk.headers)
                    lines.append(f"**Headers Breadcrumbs:** `{breadcrumbs}`")
                
                if chunk.language:
                    lines.append(f"**Language:** `{chunk.language}`")
                
                lines.append(f"**Size:** {chunk.size} chars")
                lines.append("")
                
                # Полный контент
                lines.append("### Content (Full)")
                if chunk.chunk_type == ChunkType.CODE:
                    lang = chunk.language or ""
                    lines.append(f"```{lang}")
                    lines.append(chunk.content)
                    lines.append("```")
                else:
                    lines.append("```")
                    lines.append(chunk.content)
                    lines.append("```")
                lines.append("")
                
                # Полный контекст для векторизации
                lines.append("### Vector Context (Full Text Sent to Embedder)")
                lines.append("```")
                lines.append(chunk.context_text)
                lines.append("```")
                lines.append("")
                
                # Эмбеддинг
                if chunk.embedding_preview:
                    preview = ", ".join(f"{v:.6f}" for v in chunk.embedding_preview)
                    lines.append(f"**Embedding Preview (first 10):** `[{preview}]`")
                    lines.append(f"**Embedding Dimension:** {len(chunk.embedding_full) if chunk.embedding_full else 'N/A'}")
                
                lines.append("")
        
        return "\n".join(lines)
    
    def generate_search_report(self) -> str:
        """Генерирует ПОЛНЫЙ Markdown-отчёт о поиске."""
        lines = [
            "# 🔍 Search Audit Report",
            "",
            f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            "",
            "---",
            "",
        ]
        
        all_searches = []
        for report in self.reports:
            all_searches.extend(report.searches)
        
        lines.append(f"**Total Searches:** {len(all_searches)}")
        lines.append("")
        
        for idx, search in enumerate(all_searches, 1):
            lines.append(f"# Search #{idx}")
            lines.append("")
            lines.append(f"**Query:** `{search.query}`")
            lines.append(f"**Mode:** `{search.search_mode}`")
            lines.append(f"**Limit:** {search.limit}")
            lines.append(f"**Time:** {search.search_time_ms:.2f} ms")
            lines.append(f"**Results Found:** {search.results_count}")
            lines.append("")
            
            # Вектор запроса (полный!)
            lines.append("## Query Vector")
            lines.append("")
            preview = ", ".join(f"{v:.6f}" for v in search.query_vector_preview)
            lines.append(f"**Preview (first 10):** `[{preview}]`")
            lines.append(f"**Dimension:** {len(search.query_vector_full)}")
            lines.append("")
            
            # Результаты
            lines.append("## Results")
            lines.append("")
            
            if search.results:
                for r in search.results:
                    lines.append(f"### Result #{r['rank']}")
                    lines.append("")
                    lines.append(f"- **Score:** {r['score']:.6f}")
                    lines.append(f"- **Match Type:** {r['match_type']}")
                    lines.append(f"- **Document ID:** {r['document_id']}")
                    lines.append(f"- **Chunk ID:** {r['chunk_id']}")
                    lines.append(f"- **Metadata:** `{json.dumps(r['metadata'], ensure_ascii=False)}`")
                    lines.append("")
                    lines.append("**Content Preview:**")
                    lines.append("```")
                    lines.append(r['content_preview'])
                    lines.append("```")
                    lines.append("")
            else:
                lines.append("*No results found*")
            
            lines.append("---")
            lines.append("")
        
        return "\n".join(lines)
    
    def generate_media_report(self) -> str:
        """Генерирует ПОЛНЫЙ Markdown-отчёт о медиа-обработке."""
        lines = [
            "# 🎬 Media Processing Audit Report",
            "",
            f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            "",
            "---",
            "",
        ]
        
        all_media = []
        for report in self.reports:
            all_media.extend(report.media)
        
        if not all_media:
            lines.append("*No media files processed*")
            return "\n".join(lines)
        
        lines.append(f"**Total Media Files:** {len(all_media)}")
        lines.append("")
        
        for idx, media in enumerate(all_media, 1):
            emoji = {"image": "🖼️", "audio": "🎵", "video": "🎬"}.get(media.media_type, "📁")
            
            lines.append(f"# {emoji} Media #{idx}: `{media.asset_path}`")
            lines.append("")
            lines.append(f"**Type:** {media.media_type.upper()}")
            lines.append(f"**Absolute Path:** `{media.asset_absolute_path}`")
            lines.append(f"**File Size:** {media.file_size_bytes:,} bytes")
            lines.append(f"**Processing Time:** {media.processing_time_ms:.2f} ms")
            lines.append("")
            
            # Контекст
            lines.append("## 1. Surrounding Context")
            lines.append("")
            lines.append("**Text Before:**")
            lines.append("```")
            lines.append(media.surrounding_text_before or "(none)")
            lines.append("```")
            lines.append("")
            lines.append("**Text After:**")
            lines.append("```")
            lines.append(media.surrounding_text_after or "(none)")
            lines.append("```")
            lines.append("")
            
            # Запрос в модель
            lines.append("## 2. LLM Request")
            lines.append("")
            lines.append(f"**Model:** `{media.model_name}`")
            lines.append("")
            lines.append("**System Prompt:**")
            lines.append("```")
            lines.append(media.system_prompt or "(none)")
            lines.append("```")
            lines.append("")
            lines.append("**User Prompt:**")
            lines.append("```")
            lines.append(media.user_prompt or "(none)")
            lines.append("```")
            lines.append("")
            
            # Ответ модели
            lines.append("## 3. LLM Response (Raw)")
            lines.append("")
            if media.response_raw:
                lines.append("```json")
                lines.append(json.dumps(media.response_raw, ensure_ascii=False, indent=2))
                lines.append("```")
            else:
                lines.append("*(No raw response available)*")
            lines.append("")
            
            # Распарсенный ответ
            lines.append("## 4. Parsed Response")
            lines.append("")
            if media.response_parsed:
                r = media.response_parsed
                lines.append(f"- **Description:** {r.description}")
                if r.alt_text:
                    lines.append(f"- **Alt Text:** {r.alt_text}")
                if r.keywords:
                    lines.append(f"- **Keywords:** {r.keywords}")
                if r.ocr_text:
                    lines.append(f"- **OCR Text:** {r.ocr_text}")
                if r.transcription:
                    lines.append(f"- **Transcription:** {r.transcription}")
                if r.participants:
                    lines.append(f"- **Participants:** {r.participants}")
                if r.duration_seconds:
                    lines.append(f"- **Duration:** {r.duration_seconds} sec")
            else:
                lines.append("*(No parsed response)*")
            lines.append("")
            
            # Финальный контент
            lines.append("## 5. Final Chunk Content")
            lines.append("")
            lines.append("```")
            lines.append(media.final_chunk_content)
            lines.append("```")
            lines.append("")
            lines.append("---")
            lines.append("")
        
        return "\n".join(lines)
    
    def save_reports(self):
        """Сохраняет ВСЕ отчёты в файлы."""
        # Chunking report
        chunking_path = self.session_path / "01_chunking_audit.md"
        chunking_path.write_text(self.generate_chunking_report(), encoding="utf-8")
        
        # Media report
        media_path = self.session_path / "02_media_audit.md"
        media_path.write_text(self.generate_media_report(), encoding="utf-8")
        
        # Search report
        search_path = self.session_path / "03_search_audit.md"
        search_path.write_text(self.generate_search_report(), encoding="utf-8")


# ============================================================================
# Фикстуры для тестов
# ============================================================================


@pytest.fixture
def mock_embedder():
    """Mock embedder для детерминированных векторов."""
    import hashlib
    
    class MockEmbedder:
        def __init__(self, dim: int = 768):
            self.dim = dim
        
        def embed_query(self, text: str) -> np.ndarray:
            # Детерминированный вектор на основе хеша
            hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
            vector = np.array([
                ((hash_val + i) % 1000) / 1000.0 - 0.5
                for i in range(self.dim)
            ], dtype=np.float32)
            return vector
        
        def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
            return [self.embed_query(text) for text in texts]
    
    return MockEmbedder()


@pytest.fixture
def audit_db(tmp_path):
    """Изолированная БД для аудита."""
    db_path = tmp_path / "audit.db"
    db = init_peewee_database(str(db_path))
    yield db
    db.close()


@pytest.fixture
def pipeline_inspector(
    audit_db,
    mock_embedder,
    audit_session: Path,
) -> PipelineInspector:
    """Создаёт PipelineInspector с mock компонентами."""
    parser = MarkdownNodeParser()
    splitter = SmartSplitter(parser=parser, chunk_size=500, code_chunk_size=1000)
    context = HierarchicalContextStrategy(include_doc_title=True)
    store = PeeweeVectorStore(audit_db)
    
    core = SemanticCore(
        embedder=mock_embedder,
        store=store,
        splitter=splitter,
        context_strategy=context,
    )
    
    inspector = PipelineInspector(core=core, session_path=audit_session)
    
    yield inspector
    
    # Сохраняем отчёты после теста
    inspector.save_reports()
