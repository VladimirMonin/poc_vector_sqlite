"""DiffReporter - сравнение snapshot'ов.

Сравнивает два snapshot и показывает:
- Изменения в chunking
- Drift в embeddings
- Изменения в провайдерах
- Изменения в производительности
"""

from typing import Optional
import numpy as np

from semantic_core.utils.logger import get_logger
from ..models import InspectionSnapshot

logger = get_logger(__name__)


class DiffReporter:
    """Reporter для сравнения двух snapshot'ов."""

    def compare(
        self,
        baseline: InspectionSnapshot,
        current: InspectionSnapshot,
    ) -> dict:
        """
        Сравнивает два snapshot.

        Args:
            baseline: Базовый snapshot
            current: Текущий snapshot

        Returns:
            Dict с результатами сравнения
        """
        diff = {
            "chunks_diff": self._compare_chunks(baseline, current),
            "embeddings_diff": self._compare_embeddings(baseline, current),
            "providers_diff": self._compare_providers(baseline, current),
            "performance_diff": self._compare_performance(baseline, current),
        }

        logger.debug("snapshots_compared")
        return diff

    def _compare_chunks(
        self, baseline: InspectionSnapshot, current: InspectionSnapshot
    ) -> dict:
        """Сравнивает chunking между snapshot'ами."""
        return {
            "baseline_count": len(baseline.chunks),
            "current_count": len(current.chunks),
            "count_changed": len(baseline.chunks) != len(current.chunks),
            "size_diffs": self._compute_size_diffs(baseline.chunks, current.chunks),
        }

    def _compare_embeddings(
        self, baseline: InspectionSnapshot, current: InspectionSnapshot
    ) -> dict:
        """Сравнивает embeddings между snapshot'ами."""
        if not baseline.chunks or not current.chunks:
            return {"error": "No chunks to compare"}

        # Проверяем размерности
        baseline_dim = baseline.chunks[0].embedding_dimension
        current_dim = current.chunks[0].embedding_dimension

        if baseline_dim != current_dim:
            return {
                "error": "Dimension mismatch",
                "baseline_dim": baseline_dim,
                "current_dim": current_dim,
            }

        # Вычисляем drift (если есть embeddings preview)
        drifts = []
        for b_chunk, c_chunk in zip(baseline.chunks, current.chunks):
            if b_chunk.embedding_preview and c_chunk.embedding_preview:
                # Берём только preview (первые 20 значений)
                b_vec = np.array(b_chunk.embedding_preview)
                c_vec = np.array(c_chunk.embedding_preview)

                # Косинусное сходство
                similarity = np.dot(b_vec, c_vec) / (
                    np.linalg.norm(b_vec) * np.linalg.norm(c_vec)
                )
                drift = 1 - similarity
                drifts.append(float(drift))

        if not drifts:
            return {"error": "No embeddings to compare"}

        return {
            "avg_drift": float(np.mean(drifts)),
            "max_drift": float(np.max(drifts)),
            "min_drift": float(np.min(drifts)),
            "high_drift_count": sum(1 for d in drifts if d > 0.3),
        }

    def _compare_providers(
        self, baseline: InspectionSnapshot, current: InspectionSnapshot
    ) -> dict:
        """Сравнивает провайдеры между snapshot'ами."""
        return {
            "embedder_changed": (
                baseline.embedder_metadata.provider_type
                != current.embedder_metadata.provider_type
                if baseline.embedder_metadata and current.embedder_metadata
                else False
            ),
            "model_changed": (
                baseline.embedder_metadata.model_name
                != current.embedder_metadata.model_name
                if baseline.embedder_metadata and current.embedder_metadata
                else False
            ),
        }

    def _compare_performance(
        self, baseline: InspectionSnapshot, current: InspectionSnapshot
    ) -> dict:
        """Сравнивает производительность между snapshot'ами."""
        return {
            "baseline_total_ms": baseline.total_duration_ms,
            "current_total_ms": current.total_duration_ms,
            "diff_ms": current.total_duration_ms - baseline.total_duration_ms,
            "diff_percent": (
                (current.total_duration_ms - baseline.total_duration_ms)
                / baseline.total_duration_ms
                * 100
                if baseline.total_duration_ms > 0
                else 0
            ),
        }

    def _compute_size_diffs(self, baseline_chunks, current_chunks) -> list[dict]:
        """Вычисляет различия в размерах чанков."""
        diffs = []
        max_len = max(len(baseline_chunks), len(current_chunks))

        for i in range(max_len):
            b_size = baseline_chunks[i].size if i < len(baseline_chunks) else 0
            c_size = current_chunks[i].size if i < len(current_chunks) else 0

            if b_size != c_size:
                diffs.append(
                    {
                        "chunk_id": i + 1,
                        "baseline_size": b_size,
                        "current_size": c_size,
                        "diff": c_size - b_size,
                    }
                )

        return diffs
