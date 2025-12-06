"""Команда reanalyze для CLI.

Повторный анализ медиа-файлов с новыми промптами или настройками.

Usage:
    semantic reanalyze doc-123                       # С текущими настройками
    semantic reanalyze doc-123 --prompt "..."       # С кастомным промптом
    semantic reanalyze doc-123 --show-details       # Показать детали
"""

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


console = Console()


def reanalyze(
    document_id: str = typer.Argument(
        ...,
        help="ID документа для повторного анализа (например: doc-123)",
    ),
    prompt: Optional[str] = typer.Option(
        None,
        "--prompt",
        "-p",
        help="Кастомный промпт для анализа (переопределяет config)",
    ),
    show_details: bool = typer.Option(
        False,
        "--show-details",
        "-d",
        help="Показать детали после реанализа (summary, transcript, OCR)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Пропустить подтверждение (удалит старые chunks без запроса)",
    ),
) -> None:
    """Повторный анализ медиа-файла с новыми промптами.

    Удаляет старые chunks (summary, transcript, OCR) и создаёт новые
    с использованием актуальных настроек из semantic.toml или
    кастомного промпта.

    Примеры:
        # С текущими настройками из semantic.toml
        semantic reanalyze doc-abc123

        # С кастомным промптом
        semantic reanalyze doc-abc123 --prompt "Extract medical terminology"

        # Показать детали после реанализа
        semantic reanalyze doc-abc123 --show-details

        # Без подтверждения (для скриптов)
        semantic reanalyze doc-abc123 --force
    """
    from semantic_core.cli.app import get_cli_context
    from semantic_core.services.media_service import MediaService
    from peewee import DoesNotExist

    cli_ctx = get_cli_context()
    core = cli_ctx.get_core()

    # Подтверждение (если не --force)
    if not force:
        console.print(
            Panel(
                f"[yellow]⚠️  Внимание[/yellow]\n\n"
                f"Документ: [cyan]{document_id}[/cyan]\n"
                f"Будут удалены: [red]старые chunks (summary, transcript, OCR)[/red]\n"
                f"Будут созданы: [green]новые chunks с актуальными настройками[/green]\n\n"
                f"Продолжить?",
                title="🔄 Повторный анализ",
            )
        )
        confirmed = typer.confirm("Выполнить reanalyze?")
        if not confirmed:
            console.print("[yellow]Операция отменена[/yellow]")
            raise typer.Exit(0)

    # Выполняем reanalyze
    try:
        console.print(f"[cyan]🔄 Запуск повторного анализа: {document_id}[/cyan]")

        with console.status("[bold cyan]Анализирую медиа-файл...", spinner="dots"):
            document = core.reanalyze(document_id, custom_instructions=prompt)

        # Успех
        console.print(
            Panel(
                f"[green]✅ Успешно обновлён![/green]\n\n"
                f"Document ID: [cyan]{document.id}[/cyan]\n"
                f"Тип: [yellow]{document.media_type}[/yellow]\n"
                f"Chunks: [green]{len(document.chunks)}[/green]",
                title="✅ Готово",
            )
        )

        # Показать детали (если --show-details)
        if show_details:
            _show_document_details(document_id, core)

    except DoesNotExist:
        console.print(
            Panel(
                f"[red]❌ Документ не найден: {document_id}[/red]\n\n"
                f"Проверьте ID или используйте:\n"
                f"  semantic search \"...\" --verbose",
                title="❌ Ошибка",
            )
        )
        raise typer.Exit(1)

    except ValueError as e:
        console.print(
            Panel(
                f"[red]❌ Ошибка валидации: {e}[/red]\n\n"
                f"Возможные причины:\n"
                f"  • Документ не является медиа-файлом (только IMAGE/AUDIO/VIDEO)\n"
                f"  • Отсутствует metadata['source']\n"
                f"  • Файл был удалён из файловой системы",
                title="❌ Ошибка",
            )
        )
        raise typer.Exit(1)

    except FileNotFoundError as e:
        console.print(
            Panel(
                f"[red]❌ Файл не найден: {e}[/red]\n\n"
                f"Медиа-файл был удалён из файловой системы.\n"
                f"Восстановите файл или удалите документ:\n"
                f"  semantic delete {document_id}",
                title="❌ Ошибка",
            )
        )
        raise typer.Exit(1)

    except Exception as e:
        console.print(
            Panel(
                f"[red]❌ Неожиданная ошибка: {e}[/red]",
                title="❌ Ошибка",
            )
        )
        raise typer.Exit(1)


def _show_document_details(document_id: str, core) -> None:
    """Показать детали документа после реанализа.

    Args:
        document_id: ID документа.
        core: SemanticCore instance.
    """
    from semantic_core.services.media_service import MediaService

    media_service = MediaService(
        image_analyzer=core.image_analyzer,
        audio_analyzer=core.audio_analyzer,
        video_analyzer=core.video_analyzer,
        splitter=core.splitter,
        store=core.store,
        config=core.config,
    )

    try:
        details = media_service.get_media_details(document_id)
    except Exception as e:
        console.print(f"[yellow]⚠️  Не удалось загрузить детали: {e}[/yellow]")
        return

    console.print("\n[bold cyan]📊 Детали документа[/bold cyan]\n")

    # Summary
    if details.summary:
        console.print(
            Panel(
                details.summary,
                title="📝 Summary",
                border_style="green",
            )
        )

    # Transcript
    if details.has_transcript:
        transcript_preview = (
            details.full_transcript[:300] + "..."
            if len(details.full_transcript) > 300
            else details.full_transcript
        )
        console.print(
            Panel(
                transcript_preview,
                title=f"🎙️ Transcript ({len(details.full_transcript)} chars)",
                border_style="blue",
            )
        )

    # OCR Text
    if details.has_ocr:
        ocr_preview = (
            details.full_ocr_text[:300] + "..."
            if len(details.full_ocr_text) > 300
            else details.full_ocr_text
        )
        console.print(
            Panel(
                ocr_preview,
                title=f"🔍 OCR Text ({len(details.full_ocr_text)} chars)",
                border_style="yellow",
            )
        )

    # Timeline
    if details.has_timeline:
        table = Table(title="⏱️ Timeline", show_header=True)
        table.add_column("Время", style="cyan", width=10)
        table.add_column("Превью", style="white")

        for item in details.timeline[:10]:  # Показываем первые 10
            table.add_row(item.formatted_time, item.content_preview)

        if len(details.timeline) > 10:
            table.add_row("...", f"[dim](ещё {len(details.timeline) - 10} записей)[/dim]")

        console.print(table)

    # Stats
    console.print(
        f"\n[dim]Chunks: {details.total_chunks} | "
        f"Timeline: {len(details.timeline)} | "
        f"Keywords: {len(details.keywords or [])}[/dim]"
    )
