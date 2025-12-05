"""Команда ingest для CLI.

Индексация документов в семантическую базу данных.

Usage:
    semantic ingest file.md              # Индексация файла
    semantic ingest ./docs/ --recursive  # Индексация папки
    semantic ingest ./docs/ -p "*.md"    # Только Markdown файлы
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)

from semantic_core.domain import Document, MediaType


# Простая команда вместо Typer-группы
console = Console()


def _detect_media_type(path: Path) -> MediaType:
    """Определяет тип медиа по расширению файла.

    Args:
        path: Путь к файлу.

    Returns:
        MediaType соответствующий расширению.
    """
    suffix = path.suffix.lower()
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
    audio_extensions = {".mp3", ".wav", ".ogg", ".flac", ".m4a"}
    video_extensions = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

    if suffix in image_extensions:
        return MediaType.IMAGE
    elif suffix in audio_extensions:
        return MediaType.AUDIO
    elif suffix in video_extensions:
        return MediaType.VIDEO
    else:
        return MediaType.TEXT


def _create_document(path: Path) -> Document:
    """Создаёт Document из файла.

    Args:
        path: Путь к файлу.

    Returns:
        Объект Document с контентом и метаданными.
    """
    media_type = _detect_media_type(path)

    if media_type == MediaType.TEXT:
        content = path.read_text(encoding="utf-8")
    else:
        # Для медиа-файлов храним путь
        content = str(path.absolute())

    return Document(
        content=content,
        media_type=media_type,
        metadata={
            "title": path.stem,
            "source": str(path),
            "filename": path.name,
            "doc_id": path.stem,  # Для логов SmartSplitter
        },
    )


def _collect_files(
    path: Path,
    pattern: str = "*",
    recursive: bool = False,
) -> list[Path]:
    """Собирает файлы для индексации.

    Args:
        path: Путь к файлу или директории.
        pattern: Glob-паттерн для фильтрации.
        recursive: Рекурсивный обход.

    Returns:
        Список путей к файлам.

    Raises:
        typer.BadParameter: Если путь не существует.
    """
    if not path.exists():
        raise typer.BadParameter(f"Путь не существует: {path}")

    if path.is_file():
        return [path]

    if recursive:
        return sorted(path.rglob(pattern))
    else:
        return sorted(path.glob(pattern))


def ingest(
    path: Path = typer.Argument(
        None,  # Не обязательный, проверяем вручную
        help="Путь к файлу или директории для индексации",
    ),
    mode: str = typer.Option(
        "sync",
        "--mode",
        "-m",
        help="Режим обработки: sync (по умолчанию) или async",
    ),
    pattern: str = typer.Option(
        "*",
        "--pattern",
        "-p",
        help="Glob-паттерн для фильтрации файлов (например, '*.md')",
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive",
        "-r",
        help="Рекурсивный обход директорий",
    ),
    enrich_media: bool = typer.Option(
        False,
        "--enrich-media",
        "-e",
        help="Обогащать чанки анализом медиа-файлов",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Показать файлы без индексации",
    ),
) -> None:
    """Индексировать документы в семантическую базу данных.

    Примеры:
        semantic ingest document.md
        semantic ingest ./docs/ --recursive --pattern "*.md"
        semantic ingest ./media/ -r -e  # С анализом медиа
    """
    # Проверка обязательного аргумента
    if path is None:
        console.print(
            Panel(
                "[red]Укажите путь к файлу или директории[/red]\n\n"
                "Примеры:\n"
                "  semantic ingest document.md\n"
                "  semantic ingest ./docs/ --recursive",
                title="❌ Ошибка",
            )
        )
        raise typer.Exit(1)

    # Проверка существования пути
    if not path.exists():
        console.print(
            Panel(
                f"[red]Путь не существует: {path}[/red]",
                title="❌ Ошибка",
            )
        )
        raise typer.Exit(1)

    # Late import to avoid circular dependency
    from semantic_core.cli.app import get_cli_context

    cli_ctx = get_cli_context()

    # Валидация режима
    if mode not in ("sync", "async"):
        raise typer.BadParameter(
            f"Неверный режим: {mode}. Допустимые значения: sync, async"
        )

    # Собираем файлы
    files = _collect_files(path, pattern, recursive)

    if not files:
        console.print(
            Panel(
                f"[yellow]Файлы не найдены по паттерну '{pattern}'[/yellow]",
                title="⚠️  Предупреждение",
            )
        )
        raise typer.Exit(0)

    # Фильтруем директории (оставляем только файлы)
    files = [f for f in files if f.is_file()]

    if not files:
        console.print("[yellow]Нет файлов для индексации[/yellow]")
        raise typer.Exit(0)

    # Dry run
    if dry_run:
        _show_dry_run(files)
        raise typer.Exit(0)

    # Индексация
    if cli_ctx.json_output:
        _ingest_json(files, mode, enrich_media, cli_ctx)
    else:
        _ingest_rich(files, mode, enrich_media, cli_ctx)


def _show_dry_run(files: list[Path]) -> None:
    """Показывает файлы без индексации (dry-run)."""
    console.print(
        Panel(
            f"[cyan]Найдено файлов: {len(files)}[/cyan]",
            title="🔍 Dry Run",
        )
    )

    for f in files:
        media_type = _detect_media_type(f)
        icon = {
            MediaType.TEXT: "📄",
            MediaType.IMAGE: "🖼️ ",
            MediaType.AUDIO: "🎵",
            MediaType.VIDEO: "🎬",
        }.get(media_type, "📎")
        console.print(f"  {icon} {f}")


def _ingest_rich(
    files: list[Path],
    mode: str,
    enrich_media: bool,
    cli_ctx: "CLIContext",
) -> None:
    """Индексация с Rich progress bar."""
    from semantic_core.cli.context import CLIContext

    core = cli_ctx.get_core()

    results = {
        "success": 0,
        "failed": 0,
        "errors": [],
    }

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            "[cyan]Индексация...",
            total=len(files),
        )

        for file_path in files:
            try:
                doc = _create_document(file_path)
                core.ingest(doc, mode=mode, enrich_media=enrich_media)
                results["success"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"file": str(file_path), "error": str(e)})

            progress.update(task, advance=1)

    # Итоговый отчёт
    _show_summary(results)


def _ingest_json(
    files: list[Path],
    mode: str,
    enrich_media: bool,
    cli_ctx: "CLIContext",
) -> None:
    """Индексация с JSON-выводом."""
    import json
    from semantic_core.cli.context import CLIContext

    core = cli_ctx.get_core()

    results = {
        "total": len(files),
        "success": 0,
        "failed": 0,
        "files": [],
        "errors": [],
    }

    for file_path in files:
        try:
            doc = _create_document(file_path)
            core.ingest(doc, mode=mode, enrich_media=enrich_media)
            results["success"] += 1
            results["files"].append(
                {
                    "path": str(file_path),
                    "status": "ok",
                    "media_type": _detect_media_type(file_path).value,
                }
            )
        except Exception as e:
            results["failed"] += 1
            results["files"].append(
                {
                    "path": str(file_path),
                    "status": "error",
                    "error": str(e),
                }
            )
            results["errors"].append({"file": str(file_path), "error": str(e)})

    console.print_json(json.dumps(results, ensure_ascii=False))


def _show_summary(results: dict) -> None:
    """Показывает итоговую сводку индексации."""
    success = results["success"]
    failed = results["failed"]
    total = success + failed

    if failed == 0:
        console.print(
            Panel(
                f"[green]✓ Успешно проиндексировано: {success} из {total}[/green]",
                title="📚 Индексация завершена",
            )
        )
    else:
        console.print(
            Panel(
                f"[yellow]Проиндексировано: {success} из {total}\n"
                f"[red]Ошибок: {failed}[/red][/yellow]",
                title="⚠️  Индексация с ошибками",
            )
        )

        if results["errors"]:
            console.print("\n[red bold]Ошибки:[/red bold]")
            for err in results["errors"][:5]:  # Показываем первые 5
                console.print(f"  • {err['file']}: {err['error']}")
            if len(results["errors"]) > 5:
                console.print(f"  ... и ещё {len(results['errors']) - 5} ошибок")
