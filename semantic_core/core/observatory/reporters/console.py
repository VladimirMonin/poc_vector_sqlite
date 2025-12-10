"""ConsoleReporter - Rich TUI вывод для инспекции.

Форматирует данные инспекции для вывода в терминал:
- Красивые панели и таблицы (Rich)
- Прогресс обработки в реальном времени
- Превью векторов и контента
- Метрики производительности
"""

from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.text import Text

from semantic_core.utils.logger import get_logger
from ..models import InspectionSnapshot, ChunkInspection, ProviderMetadata

logger = get_logger(__name__)


class ConsoleReporter:
    """Rich TUI reporter для вывода инспекции в терминал."""

    def __init__(self, console: Optional[Console] = None):
        """
        Инициализация ConsoleReporter.

        Args:
            console: Rich Console (опционально)
        """
        self.console = console or Console()

    def report_snapshot(self, snapshot: InspectionSnapshot):
        """
        Выводит полный snapshot в терминал.

        Args:
            snapshot: Снимок для вывода
        """
        # Заголовок
        title = f"📄 Inspection: {snapshot.file_path}"
        self.console.print(Panel(title, style="bold blue"))
        self.console.print()

        # Метаданные провайдеров
        if snapshot.embedder_metadata:
            self._report_provider_metadata("Embedder", snapshot.embedder_metadata)

        if snapshot.llm_metadata:
            self._report_provider_metadata("LLM", snapshot.llm_metadata)

        if snapshot.transcriber_metadata:
            self._report_provider_metadata("Transcriber", snapshot.transcriber_metadata)

        # Шаги обработки
        self._report_processing_steps(snapshot)

        # Чанки
        self._report_chunks(snapshot.chunks)

        # Итоговые метрики
        self._report_summary(snapshot)

    def report_chunk(self, chunk: ChunkInspection, index: Optional[int] = None):
        """
        Выводит информацию о чанке.

        Args:
            chunk: Чанк для вывода
            index: Номер чанка (опционально)
        """
        chunk_num = index if index is not None else chunk.chunk_id

        # Эмодзи для типа
        type_emoji = {
            "text": "📝",
            "code": "💻",
            "table": "📊",
            "image_ref": "🖼️",
            "audio_ref": "🎵",
            "video_ref": "🎬",
        }.get(chunk.chunk_type.lower(), "📄")

        title = f"{type_emoji} Chunk #{chunk_num} [{chunk.chunk_type.upper()}]"

        # Таблица с метаданными
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Property", style="cyan")
        table.add_column("Value")

        if chunk.headers:
            breadcrumbs = " > ".join(chunk.headers)
            table.add_row("Headers", breadcrumbs)

        if chunk.language:
            table.add_row("Language", chunk.language)

        table.add_row("Size", f"{chunk.size} chars")

        if chunk.embedding_dimension:
            table.add_row("Embedding", f"{chunk.embedding_dimension}D")

        self.console.print(Panel(table, title=title, border_style="blue"))

        # Content preview
        if chunk.chunk_type.lower() == "code" and chunk.language:
            syntax = Syntax(
                chunk.content[:500], chunk.language, theme="monokai", line_numbers=True
            )
            self.console.print(Panel(syntax, title="Content", border_style="dim"))
        else:
            content_preview = chunk.content[:500]
            if len(chunk.content) > 500:
                content_preview += "\n... (truncated)"
            self.console.print(
                Panel(content_preview, title="Content", border_style="dim")
            )

        # Vector context
        self.console.print(
            Panel(
                chunk.context_text[:300],
                title="Vector Context",
                border_style="dim",
            )
        )

        # Embedding preview
        if chunk.embedding_preview:
            preview = ", ".join(f"{v:.4f}" for v in chunk.embedding_preview[:10])
            embedding_text = f"[{preview}, ...]"
            self.console.print(
                Panel(embedding_text, title="Embedding Preview", border_style="dim")
            )

        self.console.print()

    def _report_provider_metadata(self, provider_name: str, metadata: ProviderMetadata):
        """Выводит метаданные провайдера."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Property", style="cyan")
        table.add_column("Value")

        table.add_row("Type", metadata.provider_type)

        if metadata.model_name:
            table.add_row("Model", metadata.model_name)

        if metadata.dimension:
            table.add_row("Dimension", str(metadata.dimension))

        if metadata.max_tokens:
            table.add_row("Max Tokens", str(metadata.max_tokens))

        if metadata.device:
            table.add_row("Device", metadata.device)

        for key, value in metadata.extra.items():
            table.add_row(key.replace("_", " ").title(), str(value))

        self.console.print(
            Panel(table, title=f"🔧 {provider_name}", border_style="green")
        )
        self.console.print()

    def _report_processing_steps(self, snapshot: InspectionSnapshot):
        """Выводит шаги обработки."""
        if not snapshot.steps:
            return

        table = Table(title="⚡ Processing Steps", show_header=True)
        table.add_column("Step", style="cyan")
        table.add_column("Duration", justify="right", style="yellow")
        table.add_column("Details", style="dim")

        for step in snapshot.steps:
            step_name = step["step_name"].replace("_", " ").title()
            duration = f"{step['duration_ms']:.2f}ms"

            # Детали (зависит от типа шага)
            details = []
            for key, value in step.items():
                if key not in ["step_name", "duration_ms"]:
                    details.append(f"{key}={value}")

            details_str = ", ".join(details) if details else "-"

            table.add_row(step_name, duration, details_str)

        self.console.print(table)
        self.console.print()

    def _report_chunks(self, chunks: list[ChunkInspection]):
        """Выводит сводку по чанкам."""
        if not chunks:
            return

        self.console.print(Panel(f"📦 Chunks: {len(chunks)}", style="bold magenta"))
        self.console.print()

        # Показываем первые 3 чанка
        for i, chunk in enumerate(chunks[:3], 1):
            self.report_chunk(chunk, index=i)

        if len(chunks) > 3:
            remaining = len(chunks) - 3
            self.console.print(f"[dim]... and {remaining} more chunks[/dim]")
            self.console.print()

    def _report_summary(self, snapshot: InspectionSnapshot):
        """Выводит итоговую сводку."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", style="bold green")

        table.add_row("Total Duration", f"{snapshot.total_duration_ms:.2f}ms")
        table.add_row("Chunks Created", str(len(snapshot.chunks)))

        if snapshot.config_hash:
            table.add_row("Config Hash", snapshot.config_hash)

        if snapshot.processing_timestamp:
            table.add_row("Timestamp", snapshot.processing_timestamp.isoformat())

        self.console.print(Panel(table, title="📊 Summary", border_style="green"))
        self.console.print()

    def report_progress(self, step_name: str, current: int, total: int):
        """
        Выводит прогресс выполнения.

        Args:
            step_name: Название шага
            current: Текущий элемент
            total: Всего элементов
        """
        percentage = (current / total) * 100 if total > 0 else 0
        bar_length = 30
        filled = int(bar_length * current / total) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_length - filled)

        text = Text()
        text.append(f"[{current}/{total}] ", style="cyan")
        text.append(step_name, style="bold")
        text.append(f" {bar} ", style="blue")
        text.append(f"{percentage:.1f}%", style="green")

        self.console.print(text)
