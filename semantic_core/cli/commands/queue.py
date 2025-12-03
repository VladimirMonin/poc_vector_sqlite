"""CLI команды для управления очередями.

Команды:
    status: Показывает состояние очередей (text/media).
    flush: Отправляет pending чанки в Batch API.
    retry: Перезапускает failed задачи.
"""

import json
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()

queue_cmd = typer.Typer(
    name="queue",
    help="📦 Управление очередями обработки.",
    no_args_is_help=True,
)


def _get_text_stats() -> dict:
    """Получить статистику очереди текстовых чанков.

    Returns:
        Словарь со счётчиками по статусам.
    """
    from semantic_core.infrastructure.storage.peewee.models import (
        ChunkModel,
        EmbeddingStatus,
    )

    return {
        "pending": ChunkModel.select()
        .where(ChunkModel.embedding_status == EmbeddingStatus.PENDING.value)
        .count(),
        "processing": ChunkModel.select()
        .where(
            (ChunkModel.embedding_status == EmbeddingStatus.PENDING.value)
            & (ChunkModel.batch_job.is_null(False))
        )
        .count(),
        "ready": ChunkModel.select()
        .where(ChunkModel.embedding_status == EmbeddingStatus.READY.value)
        .count(),
        "failed": ChunkModel.select()
        .where(ChunkModel.embedding_status == EmbeddingStatus.FAILED.value)
        .count(),
    }


def _get_media_stats() -> dict:
    """Получить статистику очереди медиа задач.

    Returns:
        Словарь со счётчиками по статусам.
    """
    from semantic_core.infrastructure.storage.peewee.models import MediaTaskModel
    from semantic_core.domain.media import TaskStatus

    return {
        "pending": MediaTaskModel.select()
        .where(MediaTaskModel.status == TaskStatus.PENDING.value)
        .count(),
        "processing": MediaTaskModel.select()
        .where(MediaTaskModel.status == TaskStatus.PROCESSING.value)
        .count(),
        "completed": MediaTaskModel.select()
        .where(MediaTaskModel.status == TaskStatus.COMPLETED.value)
        .count(),
        "failed": MediaTaskModel.select()
        .where(MediaTaskModel.status == TaskStatus.FAILED.value)
        .count(),
    }


def _render_stats_table(title: str, stats: dict, status_map: dict) -> Table:
    """Создать Rich таблицу со статистикой.

    Args:
        title: Заголовок таблицы.
        stats: Словарь статистики.
        status_map: Маппинг статус → (emoji, название).

    Returns:
        Rich Table для вывода.
    """
    table = Table(title=title, show_header=True, header_style="bold")
    table.add_column("Status", style="cyan")
    table.add_column("Count", justify="right")

    for key, (emoji, label) in status_map.items():
        count = stats.get(key, 0)
        table.add_row(f"{emoji} {label}", str(count))

    return table


@queue_cmd.command("status")
def queue_status() -> None:
    """📊 Показать состояние очередей.

    Отображает статистику по очередям:
    - Text Embeddings (Batch API)
    - Media Analysis (Local Queue)
    """
    from semantic_core.cli.app import get_cli_context

    ctx = get_cli_context()

    # Инициализируем БД
    try:
        core = ctx.get_core()
    except Exception as e:
        if ctx.json_output:
            console.print_json(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]❌ Ошибка:[/red] {e}")
        raise typer.Exit(1)

    logger.debug("Getting queue stats")

    try:
        text_stats = _get_text_stats()
        media_stats = _get_media_stats()
    except Exception as e:
        if ctx.json_output:
            console.print_json(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]❌ Ошибка при получении статистики:[/red] {e}")
        raise typer.Exit(1)

    if ctx.json_output:
        output = {
            "text_embeddings": text_stats,
            "media": media_stats,
        }
        console.print_json(json.dumps(output))
        return

    # Rich output
    console.print()
    console.print("[bold]📦 Queue Status[/bold]")
    console.print()

    # Text embeddings table
    text_map = {
        "pending": ("🔵", "Pending"),
        "processing": ("🟡", "Processing"),
        "ready": ("🟢", "Ready"),
        "failed": ("🔴", "Failed"),
    }
    text_table = _render_stats_table(
        "Text Embeddings (Batch API)",
        text_stats,
        text_map,
    )
    console.print(text_table)
    console.print()

    # Media table
    media_map = {
        "pending": ("🔵", "Pending"),
        "processing": ("🟡", "Processing"),
        "completed": ("🟢", "Completed"),
        "failed": ("🔴", "Failed"),
    }
    media_table = _render_stats_table(
        "Media Analysis (Local Queue)",
        media_stats,
        media_map,
    )
    console.print(media_table)
    console.print()

    # Tip
    total_pending = text_stats.get("pending", 0) + media_stats.get("pending", 0)
    if total_pending > 0:
        console.print(
            "[dim]💡 Tip: Run 'semantic worker run-once' to process pending tasks[/dim]"
        )


@queue_cmd.command("flush")
def queue_flush(
    min_size: int = typer.Option(
        0,
        "--min-size",
        "-m",
        help="Минимальный размер батча (игнорируется с force).",
    ),
    force: bool = typer.Option(
        True,
        "--force/--no-force",
        "-f",
        help="Принудительно отправить даже маленький батч.",
    ),
) -> None:
    """🚀 Отправить pending чанки в Batch API.

    Создаёт batch job для всех pending text chunks.
    По умолчанию отправляет все доступные чанки (--force).
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
        console.print("[bold]📦 Flushing text embedding queue...[/bold]")

    logger.info("Flushing queue", min_size=min_size, force=force)

    try:
        # Проверяем наличие batch_manager
        if not hasattr(core, "batch_manager") or core.batch_manager is None:
            msg = "BatchManager не настроен. Проверьте API ключи."
            if ctx.json_output:
                console.print_json(json.dumps({"error": msg}))
            else:
                console.print(f"[yellow]⚠️ {msg}[/yellow]")
            raise typer.Exit(1)

        batch_id = core.batch_manager.flush_queue(min_size=min_size, force=force)

        if batch_id:
            text_stats = _get_text_stats()
            pending = text_stats.get("pending", 0) + text_stats.get("processing", 0)

            if ctx.json_output:
                console.print_json(
                    json.dumps(
                        {
                            "success": True,
                            "batch_id": batch_id,
                            "pending_after": pending,
                        }
                    )
                )
            else:
                console.print(f"[green]✅ Created batch:[/green] {batch_id[:8]}...")
                if pending > 0:
                    console.print(f"   Remaining in queue: {pending}")
        else:
            if ctx.json_output:
                console.print_json(
                    json.dumps(
                        {
                            "success": True,
                            "batch_id": None,
                            "message": "No pending chunks to flush",
                        }
                    )
                )
            else:
                console.print("[dim]ℹ️ No pending chunks to flush[/dim]")

    except Exception as e:
        logger.error_with_context("Flush failed", e)
        if ctx.json_output:
            console.print_json(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]❌ Ошибка:[/red] {e}")
        raise typer.Exit(1)


@queue_cmd.command("retry")
def queue_retry(
    task_type: str = typer.Option(
        "all",
        "--type",
        "-t",
        help="Тип задач: text, media, all.",
    ),
) -> None:
    """🔄 Перезапустить failed задачи.

    Сбрасывает статус failed задач на pending для повторной обработки.
    """
    from semantic_core.cli.app import get_cli_context
    from semantic_core.infrastructure.storage.peewee.models import (
        ChunkModel,
        MediaTaskModel,
        EmbeddingStatus,
    )
    from semantic_core.domain.media import TaskStatus

    ctx = get_cli_context()

    try:
        core = ctx.get_core()
    except Exception as e:
        if ctx.json_output:
            console.print_json(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]❌ Ошибка:[/red] {e}")
        raise typer.Exit(1)

    if task_type not in ("all", "text", "media"):
        if ctx.json_output:
            console.print_json(
                json.dumps(
                    {"error": f"Invalid type: {task_type}. Use: all, text, media"}
                )
            )
        else:
            console.print(
                f"[red]❌ Неверный тип:[/red] {task_type}. "
                "Используйте: all, text, media"
            )
        raise typer.Exit(1)

    if not ctx.json_output:
        console.print("[bold]🔄 Retrying failed tasks...[/bold]")

    logger.info("Retrying failed tasks", task_type=task_type)

    text_retried = 0
    media_retried = 0

    try:
        # Retry text chunks
        if task_type in ("all", "text"):
            text_retried = (
                ChunkModel.update(
                    embedding_status=EmbeddingStatus.PENDING.value,
                    batch_job=None,
                    error_message=None,
                )
                .where(ChunkModel.embedding_status == EmbeddingStatus.FAILED.value)
                .execute()
            )

            logger.info("Text chunks retried", count=text_retried)

        # Retry media tasks
        if task_type in ("all", "media"):
            media_retried = (
                MediaTaskModel.update(
                    status=TaskStatus.PENDING.value,
                    error_message=None,
                )
                .where(MediaTaskModel.status == TaskStatus.FAILED.value)
                .execute()
            )

            logger.info("Media tasks retried", count=media_retried)

        if ctx.json_output:
            console.print_json(
                json.dumps(
                    {
                        "success": True,
                        "text_retried": text_retried,
                        "media_retried": media_retried,
                    }
                )
            )
        else:
            console.print(f"   Text chunks: {text_retried} → PENDING")
            console.print(f"   Media tasks: {media_retried} → PENDING")

            total = text_retried + media_retried
            if total > 0:
                console.print("[green]✅ Ready for reprocessing[/green]")
            else:
                console.print("[dim]ℹ️ No failed tasks to retry[/dim]")

    except Exception as e:
        logger.error_with_context("Retry failed", e)
        if ctx.json_output:
            console.print_json(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]❌ Ошибка:[/red] {e}")
        raise typer.Exit(1)


__all__ = ["queue_cmd"]
