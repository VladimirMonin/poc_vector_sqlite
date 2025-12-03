"""CLI команды для управления воркерами.

Команды:
    run-once: Одноразовая обработка очереди.
    start: Бесконечный цикл обработки с graceful shutdown.
"""

import json
import signal
import time
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()

worker_cmd = typer.Typer(
    name="worker",
    help="👷 Управление воркерами обработки.",
    no_args_is_help=True,
)


def _sync_batch_statuses(core) -> dict:
    """Синхронизирует статусы батчей с Google API.

    Args:
        core: SemanticCore instance.

    Returns:
        Словарь {batch_id: status}.
    """
    if not hasattr(core, "batch_manager") or core.batch_manager is None:
        logger.debug("BatchManager not configured, skipping sync")
        return {}

    try:
        return core.batch_manager.sync_status()
    except Exception as e:
        logger.warning("Batch sync failed", error=str(e))
        return {}


def _process_media_queue(core, max_tasks: int) -> int:
    """Обрабатывает очередь медиа.

    Args:
        core: SemanticCore instance.
        max_tasks: Максимальное количество задач.

    Returns:
        Количество обработанных задач.
    """
    try:
        return core.process_media_queue(max_tasks=max_tasks)
    except Exception as e:
        logger.warning("Media queue processing failed", error=str(e))
        return 0


@worker_cmd.command("run-once")
def worker_run_once(
    max_tasks: int = typer.Option(
        50,
        "--max-tasks",
        "-m",
        help="Максимальное количество задач за проход.",
    ),
) -> None:
    """🔄 Однократная обработка очереди.

    Синхронизирует статусы батчей и обрабатывает pending медиа-задачи.
    """
    from semantic_core.cli.app import get_cli_context

    ctx = get_cli_context()

    try:
        core = ctx.get_core()
    except Exception as e:
        if ctx.json_output:
            console.print_json(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]❌ Ошибка:[/red] {e}")
        raise typer.Exit(1)

    if not ctx.json_output:
        console.print("[bold]👷 Running one-time processing...[/bold]")
        console.print()

    logger.info("Starting one-time processing", max_tasks=max_tasks)

    results = {
        "batch_sync": {},
        "media_processed": 0,
        "remaining": 0,
    }

    try:
        # 1. Sync batch statuses
        if not ctx.json_output:
            console.print("[cyan]Batch Sync:[/cyan]")

        batch_results = _sync_batch_statuses(core)
        results["batch_sync"] = batch_results

        if not ctx.json_output:
            if batch_results:
                for batch_id, status in batch_results.items():
                    emoji = (
                        "🟢"
                        if status == "COMPLETED"
                        else "🟡"
                        if status == "PROCESSING"
                        else "🔴"
                    )
                    console.print(f"   {batch_id[:8]}...: {emoji} {status}")
            else:
                console.print("   [dim]No active batches[/dim]")
            console.print()

        # 2. Process media queue
        if not ctx.json_output:
            console.print("[cyan]Media Queue:[/cyan]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
            disable=ctx.json_output,
        ) as progress:
            progress.add_task("Processing media tasks...", total=None)
            processed = _process_media_queue(core, max_tasks)

        results["media_processed"] = processed

        if not ctx.json_output:
            console.print(f"   Processed: {processed} tasks")
            console.print()

        # 3. Get remaining count
        from semantic_core.infrastructure.storage.peewee.models import MediaTaskModel
        from semantic_core.domain.media import TaskStatus

        remaining = (
            MediaTaskModel.select()
            .where(MediaTaskModel.status == TaskStatus.PENDING.value)
            .count()
        )
        results["remaining"] = remaining

        if ctx.json_output:
            console.print_json(
                json.dumps(
                    {
                        "success": True,
                        **results,
                    }
                )
            )
        else:
            if remaining > 0:
                console.print(
                    f"[yellow]📦 Remaining: {remaining} tasks in queue[/yellow]"
                )
            else:
                console.print("[green]✅ All tasks processed[/green]")

        logger.info(
            "One-time processing completed",
            batches_synced=len(batch_results),
            media_processed=processed,
            remaining=remaining,
        )

    except Exception as e:
        logger.error_with_context("One-time processing failed", e)
        if ctx.json_output:
            console.print_json(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]❌ Ошибка:[/red] {e}")
        raise typer.Exit(1)


@worker_cmd.command("start")
def worker_start(
    batch_size: int = typer.Option(
        10,
        "--batch-size",
        "-b",
        help="Задач за одну итерацию.",
    ),
    poll_interval: float = typer.Option(
        5.0,
        "--poll-interval",
        "-p",
        help="Секунды между проверками очереди.",
    ),
) -> None:
    """♾️ Запустить бесконечный воркер.

    Непрерывно обрабатывает очередь с заданным интервалом.
    Используйте Ctrl+C для graceful shutdown.
    """
    from semantic_core.cli.app import get_cli_context
    from semantic_core.infrastructure.storage.peewee.models import MediaTaskModel
    from semantic_core.domain.media import TaskStatus

    ctx = get_cli_context()

    # Проверяем JSON mode — не поддерживается для start
    if ctx.json_output:
        console.print_json(
            json.dumps(
                {
                    "error": "JSON output not supported for 'worker start'. Use 'worker run-once' instead."
                }
            )
        )
        raise typer.Exit(1)

    try:
        core = ctx.get_core()
    except Exception as e:
        console.print(f"[red]❌ Ошибка:[/red] {e}")
        raise typer.Exit(1)

    console.print(
        f"[bold]👷 Starting worker[/bold] (batch={batch_size}, poll={poll_interval}s)"
    )
    console.print("   Press [bold]Ctrl+C[/bold] for graceful shutdown")
    console.print()

    logger.info(
        "Worker starting",
        batch_size=batch_size,
        poll_interval=poll_interval,
    )

    # Graceful shutdown
    running = True
    total_processed = 0

    def handle_sigint(sig, frame):
        nonlocal running
        console.print()
        console.print("[yellow]⏹️ Graceful shutdown requested...[/yellow]")
        logger.info("Shutdown signal received")
        running = False

    # Регистрируем обработчик сигналов
    original_handler = signal.signal(signal.SIGINT, handle_sigint)

    try:
        while running:
            iteration_start = time.time()

            # 1. Sync batch statuses
            batch_results = _sync_batch_statuses(core)
            if batch_results:
                completed = sum(1 for s in batch_results.values() if s == "COMPLETED")
                processing = sum(1 for s in batch_results.values() if s == "PROCESSING")
                if completed or processing:
                    logger.info(
                        "Batch sync",
                        completed=completed,
                        processing=processing,
                    )

            # 2. Process media queue
            processed = _process_media_queue(core, batch_size)
            total_processed += processed

            if processed > 0:
                logger.info("Processed media tasks", count=processed)

            # 3. Check if queue is empty
            remaining = (
                MediaTaskModel.select()
                .where(MediaTaskModel.status == TaskStatus.PENDING.value)
                .count()
            )

            if remaining == 0 and processed == 0:
                logger.trace("No pending tasks, sleeping", seconds=poll_interval)

            # Sleep до следующей итерации
            elapsed = time.time() - iteration_start
            sleep_time = max(0, poll_interval - elapsed)

            if running and sleep_time > 0:
                time.sleep(sleep_time)

    except Exception as e:
        logger.error_with_context("Worker crashed", e)
        console.print(f"[red]❌ Worker error:[/red] {e}")
        raise typer.Exit(1)

    finally:
        # Восстанавливаем оригинальный обработчик
        signal.signal(signal.SIGINT, original_handler)

    console.print(
        f"[green]✅ Worker stopped.[/green] Processed {total_processed} tasks total."
    )
    logger.info("Worker stopped", total_processed=total_processed)


__all__ = ["worker_cmd"]
