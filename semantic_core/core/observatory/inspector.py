"""ProviderInspector - Provider-agnostic инспектор pipeline.

Основные отличия от Phase 13 PipelineInspector:
1. Работает с ЛЮБЫМИ провайдерами (не только Gemini)
2. Собирает метаданные провайдеров автоматически
3. Создаёт версионированные снимки (snapshot_version)
4. Поддерживает сравнение между разными конфигурациями

Использование:
    >>> from semantic_core import SemanticCore
    >>> from semantic_core.core.observatory import ProviderInspector
    >>>
    >>> core = SemanticCore(config="gemini_config.toml")
    >>> inspector = ProviderInspector(core=core)
    >>> doc = inspector.ingest_with_inspection(document)
"""

import time
import hashlib
from datetime import datetime
from typing import Optional
from pathlib import Path

from semantic_core.domain import Document
from semantic_core.utils.logger import get_logger
from .models import (
    InspectionSnapshot,
    ChunkInspection,
    SearchInspection,
    ProviderMetadata,
)
from .snapshot import SnapshotManager

logger = get_logger(__name__)


class ProviderInspector:
    """Provider-agnostic инспектор для SemanticCore pipeline."""

    def __init__(
        self,
        core,  # SemanticCore (избегаем circular import)
        artifacts_root: Optional[Path] = None,
    ):
        """
        Инициализация ProviderInspector.

        Args:
            core: Экземпляр SemanticCore
            artifacts_root: Корневая папка для сохранения artifacts (опционально)
        """
        self.core = core
        
        # Создаём SnapshotManager с artifacts_root
        if artifacts_root:
            self.snapshot_manager = SnapshotManager(artifacts_root=Path(artifacts_root))
        else:
            self.snapshot_manager = SnapshotManager()

        logger.trace("provider_inspector_initialized", artifacts_root=str(artifacts_root) if artifacts_root else None)

    def ingest_with_inspection(
        self,
        path: Optional[str] = None,
        document: Optional[Document] = None,
        mode: str = "sync",
    ) -> InspectionSnapshot:
        """
        Индексирует документ с полной инспекцией pipeline.

        Args:
            path: Путь к файлу (для автоматической загрузки)
            document: Документ для индексации (если уже загружен)
            mode: Режим (sync/async)

        Returns:
            InspectionSnapshot с полными данными
        """
        start_time = time.perf_counter()

        # Загружаем документ если передан path
        if path and not document:
            from semantic_core.domain import Document
            
            file_path = Path(path)
            content = file_path.read_text(encoding="utf-8")
            document = Document(
                content=content,
                metadata={"source": str(file_path)},
            )

        if not document:
            raise ValueError("Either path or document must be provided")

        # Создаём snapshot
        source = document.metadata.get("source", "unknown")
        content = document.content or ""
        content_preview = content[:500] if content else ""

        snapshot = InspectionSnapshot(
            file_path=source,
            file_content=content,  # Сохраняем полное содержимое
            file_content_preview=content_preview,
            processing_timestamp=datetime.now(),
            embedder_metadata=self._extract_provider_metadata(self.core.embedder),
            config_hash=self._compute_config_hash(),
        )

        # Шаг 1: Сплиттинг
        step_start = time.perf_counter()
        chunks = self.core.splitter.split(document)
        step_time = (time.perf_counter() - step_start) * 1000

        snapshot.steps.append(
            {
                "step_name": "splitting",
                "duration_ms": step_time,
                "splitter": type(self.core.splitter).__name__,
                "chunks_count": len(chunks),
            }
        )

        logger.trace("splitting_completed", chunks_count=len(chunks), time_ms=step_time)

        # Шаг 2: Контекст
        step_start = time.perf_counter()
        vector_texts = []
        for i, chunk in enumerate(chunks):
            context_text = self.core.context_strategy.form_vector_text(chunk, document)
            vector_texts.append(context_text)

            # Записываем инспекцию чанка
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
            snapshot.chunks.append(inspection)

        step_time = (time.perf_counter() - step_start) * 1000
        snapshot.steps.append(
            {
                "step_name": "context_formation",
                "duration_ms": step_time,
                "strategy": type(self.core.context_strategy).__name__,
            }
        )

        logger.trace("context_formed", time_ms=step_time)

        # Шаг 3: Embeddings
        if mode == "sync":
            step_start = time.perf_counter()
            embeddings = self.core.embedder.embed_documents(vector_texts)
            step_time = (time.perf_counter() - step_start) * 1000

            snapshot.steps.append(
                {
                    "step_name": "embedding",
                    "duration_ms": step_time,
                    "embedder": type(self.core.embedder).__name__,
                    "vectors_count": len(embeddings),
                }
            )

            logger.trace(
                "embeddings_generated", vectors_count=len(embeddings), time_ms=step_time
            )

            # Записываем embeddings preview
            for embedding, inspection in zip(embeddings, snapshot.chunks):
                if hasattr(embedding, "tolist"):
                    vec = embedding.tolist()
                else:
                    vec = list(embedding)
                inspection.embedding_preview = vec[:20]
                inspection.embedding_dimension = len(vec)

            # Присваиваем embeddings чанкам
            for chunk, embedding in zip(chunks, embeddings):
                chunk.embedding = embedding

        # Шаг 4: Сохранение в БД
        step_start = time.perf_counter()
        saved = self.core.store.save(document, chunks)
        step_time = (time.perf_counter() - step_start) * 1000

        snapshot.steps.append(
            {
                "step_name": "database_save",
                "duration_ms": step_time,
                "document_id": saved.id,
            }
        )

        logger.trace("document_saved", document_id=saved.id, time_ms=step_time)

        # Финализация snapshot
        snapshot.total_duration_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "inspection_completed",
            document_id=saved.id,
            total_time_ms=snapshot.total_duration_ms,
            chunks=len(chunks),
        )

        return snapshot

    def search_with_inspection(
        self,
        query: str,
        top_k: int = 10,
        mode: str = "hybrid",
    ) -> InspectionSnapshot:
        """
        Выполняет поиск с инспекцией.

        Args:
            query: Поисковый запрос
            top_k: Количество результатов
            mode: Режим поиска (vector/exact/hybrid)

        Returns:
            InspectionSnapshot с результатами поиска
        """
        start_time = time.perf_counter()

        # Вектор запроса
        query_vector = self.core.embedder.embed_query(query)

        # Поиск
        results = self.core.search(query=query, limit=top_k, mode=mode)

        search_time = (time.perf_counter() - start_time) * 1000

        # Вектор preview
        if hasattr(query_vector, "tolist"):
            vec = query_vector.tolist()
        else:
            vec = list(query_vector)

        inspection = SearchInspection(
            query=query,
            search_mode=mode,
            limit=top_k,
            query_vector_preview=vec[:20],
            query_vector_dimension=len(vec),
            results=[
                {
                    "rank": i + 1,
                    "chunk_id": r.chunk_id,
                    "content": r.document.content if r.document else "",
                    "similarity": r.score,
                    "match_type": r.match_type.value if r.match_type else "unknown",
                    "metadata": r.document.metadata if r.document else {},
                }
                for i, r in enumerate(results)
            ],
            results_count=len(results),
            search_time_ms=search_time,
        )

        logger.info(
            "search_completed",
            query=query,
            mode=mode,
            results_count=len(results),
            time_ms=search_time,
        )

        # Создаём snapshot только с search results
        snapshot = InspectionSnapshot(
            processing_timestamp=datetime.now(),
            embedder_metadata=self._extract_provider_metadata(self.core.embedder),
            searches=[inspection],
            total_duration_ms=search_time,
        )

        return snapshot

        return results, inspection

    def _extract_provider_metadata(self, provider) -> ProviderMetadata:
        """
        Извлекает метаданные провайдера (provider-agnostic).

        Работает с любыми провайдерами через утиные типы.
        """
        provider_type = type(provider).__name__

        # Пытаемся извлечь общие атрибуты
        model_name = getattr(provider, "model", None)
        dimension = getattr(provider, "dimension", None)
        max_tokens = getattr(provider, "max_tokens", None)
        device = getattr(provider, "device", None)

        # Дополнительные атрибуты (provider-specific)
        extra = {}
        if hasattr(provider, "api_key"):
            extra["has_api_key"] = bool(provider.api_key)
        if hasattr(provider, "base_url"):
            extra["base_url"] = provider.base_url

        return ProviderMetadata(
            provider_type=provider_type,
            model_name=model_name,
            dimension=dimension,
            max_tokens=max_tokens,
            device=device,
            extra=extra,
        )

    def _compute_config_hash(self) -> str:
        """
        Вычисляет хеш конфигурации для отслеживания изменений.

        Returns:
            MD5 хеш конфигурации
        """
        # Собираем ключевые параметры конфигурации
        config_str = f"{type(self.core.embedder).__name__}:"
        config_str += f"{getattr(self.core.embedder, 'model', 'unknown')}:"
        config_str += f"{type(self.core.splitter).__name__}:"
        config_str += f"{getattr(self.core.splitter, 'chunk_size', 'unknown')}"

        return hashlib.md5(config_str.encode()).hexdigest()[:8]
