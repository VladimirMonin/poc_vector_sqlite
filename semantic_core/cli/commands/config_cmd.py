"""Команда config — управление конфигурацией.

Подкоманды:
    show: Показать текущую конфигурацию.
    check: Валидировать настройки.

Usage:
    semantic config show
    semantic config check
"""

import json
import os
from pathlib import Path
from typing import Optional

import typer
from rich.panel import Panel
from rich.table import Table

from semantic_core.cli.console import console
from semantic_core.cli.app import get_cli_context
from semantic_core.config import SemanticConfig, find_config_file

app = typer.Typer(
    help="🔧 Просмотр и проверка конфигурации.",
)


def _mask_secret(value: Optional[str]) -> str:
    """Маскирует секретное значение для вывода.

    Args:
        value: Секретное значение.

    Returns:
        Маскированная строка или 'not set'.
    """
    if not value:
        return "[dim]not set[/dim]"
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}***{value[-4:]}"


@app.command("show")
def show(
    ctx: typer.Context,
    reveal_secrets: bool = typer.Option(
        False,
        "--reveal",
        "-r",
        help="Показать API ключи без маскировки.",
    ),
) -> None:
    """Показать текущую конфигурацию."""
    cli_ctx = get_cli_context()

    try:
        config = cli_ctx.get_config()
    except Exception as e:
        console.print(f"[red]❌ Ошибка загрузки конфигурации: {e}[/red]")
        raise typer.Exit(1)

    # Определяем источник конфига
    toml_path = find_config_file()
    source = f"{toml_path}" if toml_path else "[dim]defaults + environment[/dim]"

    console.print(f"\n[bold]⚙️  Текущая конфигурация[/bold]")
    console.print(f"[dim]Источник: {source}[/dim]\n")

    # JSON режим
    if cli_ctx.json_output:
        data = {
            "source": str(toml_path) if toml_path else None,
            "config": {
                "database": {"path": str(config.db_path)},
                "gemini": {
                    "api_key": config.gemini_api_key if reveal_secrets else "***",
                    "batch_key": config.gemini_batch_key if reveal_secrets else "***",
                    "model": config.embedding_model,
                    "dimension": config.embedding_dimension,
                },
                "processing": {
                    "splitter": config.splitter,
                    "context_strategy": config.context_strategy,
                },
                "media": {
                    "enabled": config.media_enabled,
                    "rpm_limit": config.media_rpm_limit,
                },
                "search": {
                    "limit": config.search_limit,
                    "type": config.search_type,
                },
                "logging": {
                    "level": config.log_level,
                    "file": str(config.log_file) if config.log_file else None,
                },
            },
        }
        console.print_json(json.dumps(data))
        return

    # Rich таблица
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Настройка", style="cyan")
    table.add_column("Значение")

    # Database
    table.add_row("database.path", str(config.db_path))

    # Gemini
    api_key_display = (
        config.gemini_api_key if reveal_secrets else _mask_secret(config.gemini_api_key)
    )
    batch_key_display = (
        config.gemini_batch_key
        if reveal_secrets
        else _mask_secret(config.gemini_batch_key)
    )
    table.add_row("gemini.api_key", api_key_display)
    table.add_row("gemini.batch_key", batch_key_display)
    table.add_row("gemini.model", config.embedding_model)
    table.add_row("gemini.dimension", str(config.embedding_dimension))

    # Processing
    table.add_row("processing.splitter", config.splitter)
    table.add_row("processing.context_strategy", config.context_strategy)

    # Media
    table.add_row("media.enabled", str(config.media_enabled))
    table.add_row("media.rpm_limit", str(config.media_rpm_limit))

    # Search
    table.add_row("search.limit", str(config.search_limit))
    table.add_row("search.type", config.search_type)

    # Logging
    table.add_row("logging.level", config.log_level)
    table.add_row(
        "logging.file",
        str(config.log_file) if config.log_file else "[dim]not set[/dim]",
    )

    console.print(table)


@app.command("check")
def check(
    ctx: typer.Context,
) -> None:
    """Валидировать конфигурацию и проверить соединения."""
    cli_ctx = get_cli_context()

    console.print("\n[bold]🔍 Проверка конфигурации...[/bold]\n")

    checks_passed = 0
    checks_warnings = 0
    checks_failed = 0
    results = []

    # 1. Проверка TOML файла
    toml_path = find_config_file()
    if toml_path:
        results.append(("Config file", "ok", str(toml_path)))
        checks_passed += 1
    else:
        results.append(("Config file", "info", "using defaults + environment"))
        checks_passed += 1

    # 2. Загрузка конфига
    try:
        config = cli_ctx.get_config()
        results.append(("Config parsing", "ok", "valid"))
        checks_passed += 1
    except Exception as e:
        results.append(("Config parsing", "error", str(e)))
        checks_failed += 1
        _print_results(results, checks_passed, checks_warnings, checks_failed, cli_ctx)
        raise typer.Exit(1)

    # 3. Проверка БД
    db_path = config.db_path
    if db_path.exists():
        size_mb = db_path.stat().st_size / (1024 * 1024)
        results.append(("Database", "ok", f"{db_path} ({size_mb:.1f} MB)"))
        checks_passed += 1
    else:
        results.append(("Database", "info", f"{db_path} (will be created)"))
        checks_passed += 1

    # 4. Проверка API ключа
    if config.gemini_api_key:
        results.append(("GEMINI_API_KEY", "ok", "configured"))
        checks_passed += 1
    else:
        results.append(("GEMINI_API_KEY", "error", "not set"))
        checks_failed += 1

    # 5. Проверка Batch ключа
    if config.gemini_batch_key:
        results.append(("GEMINI_BATCH_KEY", "ok", "configured"))
        checks_passed += 1
    else:
        results.append(("GEMINI_BATCH_KEY", "warning", "not set (batch mode disabled)"))
        checks_warnings += 1

    # 6. Проверка sqlite-vec
    try:
        import sqlite_vec

        results.append(("sqlite-vec", "ok", "extension available"))
        checks_passed += 1
    except ImportError:
        results.append(("sqlite-vec", "error", "extension not installed"))
        checks_failed += 1

    # Вывод результатов
    _print_results(results, checks_passed, checks_warnings, checks_failed, cli_ctx)

    if checks_failed > 0:
        raise typer.Exit(1)


def _print_results(
    results: list,
    passed: int,
    warnings: int,
    failed: int,
    cli_ctx,
) -> None:
    """Выводит результаты проверок."""
    # JSON режим
    if cli_ctx.json_output:
        data = {
            "status": "healthy" if failed == 0 else "unhealthy",
            "passed": passed,
            "warnings": warnings,
            "failed": failed,
            "checks": {
                name: {"status": status, "message": msg}
                for name, status, msg in results
            },
        }
        console.print_json(json.dumps(data))
        return

    # Rich вывод
    for name, status, msg in results:
        if status == "ok":
            icon = "[green]✅[/green]"
        elif status == "warning":
            icon = "[yellow]⚠️[/yellow]"
        elif status == "error":
            icon = "[red]❌[/red]"
        else:
            icon = "[blue]ℹ️[/blue]"

        console.print(f"{icon} {name}: {msg}")

    console.print()

    # Итог
    if failed == 0:
        status_text = "[green]Healthy[/green]"
    else:
        status_text = "[red]Unhealthy[/red]"

    summary = f"Summary: {passed} passed"
    if warnings > 0:
        summary += f", {warnings} warnings"
    if failed > 0:
        summary += f", {failed} errors"

    console.print(f"🩺 Status: {status_text}")
    console.print(f"   {summary}")


__all__ = ["app"]
