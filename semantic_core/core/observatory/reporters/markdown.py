"""MarkdownReporter - генерация Markdown отчётов.

Аналогичен отчётам из Phase 13, но с поддержкой:
- Multi-provider метаданных
- Сравнения конфигураций
- Snapshot версионирования
"""

from pathlib import Path
from typing import Optional

from semantic_core.utils.logger import get_logger
from ..models import InspectionSnapshot, ChunkInspection

logger = get_logger(__name__)


class MarkdownReporter:
    """Генератор Markdown отчётов для инспекции."""

    def generate_report(
        self, snapshot: InspectionSnapshot, output_path: Optional[Path] = None
    ) -> str:
        """
        Генерирует Markdown отчёт из snapshot.

        Args:
            snapshot: Снимок для отчёта
            output_path: Путь для сохранения (опционально)

        Returns:
            Markdown текст отчёта
        """
        lines = [
            "# 🔍 Inspection Report",
            "",
            f"**File:** `{snapshot.file_path}`",
            f"**Timestamp:** {snapshot.processing_timestamp}",
            f"**Duration:** {snapshot.total_duration_ms:.2f}ms",
            "",
            "---",
            "",
        ]

        # Provider metadata
        if snapshot.embedder_metadata:
            lines.extend(
                self._format_provider_metadata("Embedder", snapshot.embedder_metadata)
            )

        # Processing steps
        lines.extend(self._format_processing_steps(snapshot))

        # Chunks
        lines.extend(self._format_chunks(snapshot.chunks))

        markdown = "\n".join(lines)

        # Сохраняем если указан путь
        if output_path:
            output_path.write_text(markdown, encoding="utf-8")
            logger.info("markdown_report_saved", path=str(output_path))

        return markdown

    def _format_provider_metadata(self, name: str, metadata) -> list[str]:
        """Форматирует метаданные провайдера."""
        lines = [
            f"## 🔧 {name}",
            "",
            f"- **Type:** `{metadata.provider_type}`",
        ]

        if metadata.model_name:
            lines.append(f"- **Model:** `{metadata.model_name}`")

        if metadata.dimension:
            lines.append(f"- **Dimension:** {metadata.dimension}")

        lines.extend(["", "---", ""])
        return lines

    def _format_processing_steps(self, snapshot: InspectionSnapshot) -> list[str]:
        """Форматирует шаги обработки."""
        if not snapshot.steps:
            return []

        lines = [
            "## ⚡ Processing Steps",
            "",
            "| Step | Duration | Details |",
            "|------|----------|---------|",
        ]

        for step in snapshot.steps:
            step_name = step["step_name"].replace("_", " ").title()
            duration = f"{step['duration_ms']:.2f}ms"
            details = ", ".join(
                f"{k}={v}"
                for k, v in step.items()
                if k not in ["step_name", "duration_ms"]
            )
            lines.append(f"| {step_name} | {duration} | {details} |")

        lines.extend(["", "---", ""])
        return lines

    def _format_chunks(self, chunks: list[ChunkInspection]) -> list[str]:
        """Форматирует чанки."""
        lines = [f"## 📦 Chunks ({len(chunks)})", ""]

        for chunk in chunks:
            type_emoji = {
                "text": "📝",
                "code": "💻",
                "image_ref": "🖼️",
            }.get(chunk.chunk_type.lower(), "📄")

            lines.append(
                f"### {type_emoji} Chunk #{chunk.chunk_id} [{chunk.chunk_type}]"
            )
            lines.append("")
            lines.append(f"**Size:** {chunk.size} chars")

            if chunk.headers:
                lines.append(f"**Headers:** `{' > '.join(chunk.headers)}`")

            lines.append("")
            lines.append("#### Content")
            lines.append("```")
            lines.append(chunk.content[:500])
            lines.append("```")
            lines.append("")

        return lines
