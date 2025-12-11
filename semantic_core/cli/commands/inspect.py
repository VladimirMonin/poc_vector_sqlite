"""Команда inspect — X-Ray диагностика pipeline.

Выполняет полный рентген обработки документа:
- Разбивка на chunks
- Генерация embeddings
- Тестовый поиск
- Сохранение всех artifacts для анализа

Usage:
    semantic inspect <file_path> [OPTIONS]

Examples:
    # Inspect с Rich TUI выводом
    semantic inspect docs/example.md

    # Inspect с сохранением artifacts
    semantic inspect docs/example.md --save

    # Inspect с кастомным путём artifacts
    semantic inspect docs/example.md --save --output tests/e2e/audit/snapshots/

    # Inspect с тестовым поиском
    semantic inspect docs/example.md --search "test query" --top-k 5

    # Inspect с форматом отчёта
    semantic inspect docs/example.md --save --format markdown
"""

from pathlib import Path
from typing import Optional
import typer
from rich.panel import Panel
from rich.table import Table

from semantic_core.cli.console import console
from semantic_core.cli.app import get_cli_context
from semantic_core.core.observatory import (
    ProviderInspector,
    ConsoleReporter,
    MarkdownReporter,
    JsonReporter,
)
from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)


def inspect(
    file_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        help="Путь к файлу для инспекции.",
    ),
    save: bool = typer.Option(
        False,
        "--save",
        "-s",
        help="Сохранить artifacts в файлы.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Путь для сохранения artifacts (по умолчанию: tests/e2e/audit/snapshots/).",
    ),
    search: Optional[str] = typer.Option(
        None,
        "--search",
        "-q",
        help="Тестовый поисковый запрос для инспекции.",
    ),
    top_k: int = typer.Option(
        5,
        "--top-k",
        "-k",
        help="Количество результатов для тестового поиска.",
    ),
    format: str = typer.Option(
        "console",
        "--format",
        "-f",
        help="Формат вывода: console, markdown, json.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Подробный вывод.",
    ),
) -> None:
    """Выполнить X-Ray инспекцию документа."""
    cli_ctx = get_cli_context()

    console.print(f"\n[bold]🔬 Inspector X-Ray: {file_path.name}[/bold]\n")

    try:
        # Создаём SemanticCore через CLI context
        core = cli_ctx.get_core()

        # Определяем путь для artifacts
        if output:
            artifacts_root = output
        else:
            artifacts_root = Path("tests/e2e/audit/snapshots")

        # Создаём инспектор
        inspector = ProviderInspector(
            core=core,
            artifacts_root=artifacts_root,
        )

        console.print(f"[dim]📁 Artifacts root: {artifacts_root}[/dim]\n")

        # === STEP 1: Ingest Inspection ===
        console.print("[bold cyan]STEP 1:[/bold cyan] Ingest inspection...\n")

        snapshot = inspector.ingest_with_inspection(path=str(file_path))

        console.print(f"[green]✓[/green] Processed {len(snapshot.chunks)} chunks")
        console.print(
            f"[green]✓[/green] Duration: {snapshot.total_duration_ms:.2f}ms\n"
        )

        # === STEP 2: Search Inspection (if requested) ===
        if search:
            console.print(
                f"[bold cyan]STEP 2:[/bold cyan] Search inspection (query: '{search}')...\n"
            )

            search_snapshot = inspector.search_with_inspection(
                query=search,
                top_k=top_k,
            )

            # Добавляем search results в snapshot
            if search_snapshot.searches:
                snapshot.searches.extend(search_snapshot.searches)

            console.print(
                f"[green]✓[/green] Found {search_snapshot.searches[0].results_count if search_snapshot.searches else 0} results"
            )
            console.print(
                f"[green]✓[/green] Search time: {search_snapshot.searches[0].search_time_ms if search_snapshot.searches else 0:.2f}ms\n"
            )

        # === STEP 3: Report Generation ===
        console.print("[bold cyan]STEP 3:[/bold cyan] Generating report...\n")

        if format == "console":
            reporter = ConsoleReporter()

            # Provider metadata panel
            if snapshot.embedder_metadata:
                meta = snapshot.embedder_metadata
                console.print(
                    Panel(
                        f"[bold]{meta.provider_type}[/bold]\n"
                        f"Model: {meta.model_name or 'N/A'}\n"
                        f"Dimension: {meta.dimension or 'N/A'}\n"
                        f"Device: {meta.device or 'N/A'}",
                        title="🤖 Provider Metadata",
                        border_style="cyan",
                    )
                )
                console.print()

            # Chunks table
            for idx, chunk in enumerate(snapshot.chunks, 1):
                reporter.report_chunk(chunk, snapshot.embedder_metadata)
                if verbose or idx < 5:  # Показываем первые 5 или все в verbose
                    console.print()

            if len(snapshot.chunks) > 5 and not verbose:
                console.print(
                    f"[dim]... и ещё {len(snapshot.chunks) - 5} chunks (используйте --verbose для полного вывода)[/dim]\n"
                )

            # Search results table
            if snapshot.searches:
                for search_insp in snapshot.searches:
                    table = Table(title=f"🔍 Search Results: '{search_insp.query}'")
                    table.add_column("Rank", style="cyan")
                    table.add_column("Content Preview", style="white")
                    table.add_column("Similarity", style="green")

                    for idx, result in enumerate(search_insp.results[:top_k], 1):
                        content = (
                            result.get("content", "")[:100] + "..."
                            if len(result.get("content", "")) > 100
                            else result.get("content", "")
                        )
                        similarity = result.get("similarity", 0.0)
                        table.add_row(str(idx), content, f"{similarity:.4f}")

                    console.print(table)
                    console.print()

        elif format == "markdown":
            reporter = MarkdownReporter()
            report = reporter.generate_report(snapshot)

            if save:
                report_path = (
                    artifacts_root
                    / f"report_{snapshot.processing_timestamp.strftime('%Y%m%d_%H%M%S')}.md"
                )
                reporter.save_to_file(snapshot, report_path)
                console.print(
                    f"[green]✓[/green] Markdown report saved: {report_path}\n"
                )
            else:
                console.print(report)

        elif format == "json":
            reporter = JsonReporter(snapshot_manager=inspector.snapshot_manager)

            if save:
                session_name = f"session_{snapshot.processing_timestamp.strftime('%Y-%m-%d_%H-%M-%S')}"
                snapshot_path = reporter.export(snapshot, session_name)
                console.print(
                    f"[green]✓[/green] JSON snapshot saved: {snapshot_path}\n"
                )
            else:
                # Print JSON to console
                import json
                from semantic_core.core.observatory.snapshot import SnapshotManager

                # Convert snapshot to dict
                snapshot_dict = SnapshotManager._snapshot_to_dict(snapshot)
                console.print_json(data=snapshot_dict)

        # === STEP 4: Save Artifacts (if requested) ===
        if save and format != "json":  # JSON already saves in reporter
            console.print("[bold cyan]STEP 4:[/bold cyan] Saving artifacts...\n")

            session_name = (
                f"session_{snapshot.processing_timestamp.strftime('%Y-%m-%d_%H-%M-%S')}"
            )
            session_folder = artifacts_root / session_name
            session_folder.mkdir(parents=True, exist_ok=True)

            file_prefix = file_path.stem  # mixed_content_example
            snapshot_path = inspector.snapshot_manager.save_snapshot(
                snapshot,
                session_path=session_folder,
                file_prefix=file_prefix,
                compress=False,  # Don't compress for easy inspection
            )

            console.print(f"[green]✓[/green] Snapshot saved: {snapshot_path}")

            # Save input file copy
            input_copy_path = session_folder / f"input_{file_path.name}"
            input_copy_path.write_text(file_path.read_text(), encoding="utf-8")
            console.print(f"[green]✓[/green] Input file copy: {input_copy_path}")

            # Save similarity matrix (if search was performed)
            if snapshot.searches:
                similarity_csv_path = session_folder / "similarities.csv"
                with similarity_csv_path.open("w", encoding="utf-8") as f:
                    f.write("rank,chunk_id,content_preview,similarity\n")
                    for search_insp in snapshot.searches:
                        for idx, result in enumerate(search_insp.results, 1):
                            content = result.get("content", "").replace("\n", " ")[:100]
                            similarity = result.get("similarity", 0.0)
                            chunk_id = result.get("chunk_id", "N/A")
                            f.write(f'{idx},{chunk_id},"{content}",{similarity:.6f}\n')

                console.print(
                    f"[green]✓[/green] Similarity matrix: {similarity_csv_path}"
                )

            console.print(
                f"\n[bold green]✅ All artifacts saved to: {session_folder}[/bold green]\n"
            )

        # Summary
        console.print(
            Panel(
                f"[bold]Summary[/bold]\n"
                f"Chunks: {len(snapshot.chunks)}\n"
                f"Embeddings dimension: {snapshot.embedder_metadata.dimension if snapshot.embedder_metadata else 'N/A'}\n"
                f"Processing time: {snapshot.total_duration_ms:.2f}ms\n"
                f"Search results: {snapshot.searches[0].results_count if snapshot.searches else 'N/A'}",
                title="📊 Inspection Summary",
                border_style="green",
            )
        )

    except Exception as e:
        logger.error(f"Inspection failed: {e}", exc_info=True)
        console.print(f"\n[bold red]❌ Inspection failed:[/bold red] {e}\n")
        raise typer.Exit(code=1)
