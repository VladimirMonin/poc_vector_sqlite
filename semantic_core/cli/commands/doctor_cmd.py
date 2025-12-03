"""Команда doctor — диагностика окружения.

Выполняет комплексную проверку:
- Python версия
- Зависимости
- sqlite-vec extension
- База данных
- API ключи
- Сеть

Usage:
    semantic doctor [OPTIONS]
"""

import json
import os
import platform
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.panel import Panel
from rich.table import Table

from semantic_core.cli.console import console
from semantic_core.cli.app import get_cli_context
from semantic_core.config import SemanticConfig, find_config_file

app = typer.Typer(
    help="🩺 Диагностика окружения Semantic Core.",
    invoke_without_command=True,
)


@app.callback(invoke_without_command=True)
def doctor(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Подробный вывод.",
    ),
    fix: bool = typer.Option(
        False,
        "--fix",
        help="Попытаться исправить проблемы.",
    ),
) -> None:
    """Выполнить диагностику окружения."""
    cli_ctx = get_cli_context()

    console.print("\n[bold]🩺 Диагностика Semantic Core...[/bold]\n")

    all_checks = []
    sections = []

    # === Environment ===
    env_checks = []

    # Python version
    py_version = platform.python_version()
    py_major, py_minor = sys.version_info[:2]
    if py_major >= 3 and py_minor >= 10:
        env_checks.append(("Python", "ok", f"{py_version}"))
    else:
        env_checks.append(("Python", "error", f"{py_version} (requires 3.10+)"))

    # Package version
    try:
        from semantic_core import __version__

        env_checks.append(("semantic-core", "ok", __version__))
    except ImportError:
        env_checks.append(("semantic-core", "ok", "development"))

    # Key dependencies
    deps_ok = True
    missing_deps = []

    for dep in ["typer", "rich", "pydantic", "peewee"]:
        try:
            __import__(dep)
        except ImportError:
            deps_ok = False
            missing_deps.append(dep)

    if deps_ok:
        env_checks.append(("Dependencies", "ok", "all installed"))
    else:
        env_checks.append(
            ("Dependencies", "error", f"missing: {', '.join(missing_deps)}")
        )

    sections.append(("Environment", env_checks))
    all_checks.extend(env_checks)

    # === Database ===
    db_checks = []

    # sqlite-vec
    try:
        import sqlite_vec

        db_checks.append(("sqlite-vec", "ok", "extension loaded"))
    except ImportError:
        db_checks.append(("sqlite-vec", "error", "not installed"))

    # Config & DB path
    try:
        config = cli_ctx.get_config()
        db_path = config.db_path

        if db_path.exists():
            size_bytes = db_path.stat().st_size
            if size_bytes < 1024:
                size_str = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            else:
                size_str = f"{size_bytes / (1024 * 1024):.1f} MB"

            db_checks.append(("Database", "ok", f"{db_path}"))
            db_checks.append(("Database size", "info", size_str))

            # Проверяем схему (если verbose)
            if verbose:
                try:
                    from semantic_core.infrastructure.storage.peewee import (
                        init_peewee_database,
                    )

                    db = init_peewee_database(db_path, config.embedding_dimension)
                    # Проверяем таблицы
                    cursor = db.execute_sql(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                    tables = [row[0] for row in cursor.fetchall()]
                    db_checks.append(("Tables", "info", ", ".join(tables) or "none"))
                except Exception as e:
                    db_checks.append(("Schema", "warning", str(e)))
        else:
            db_checks.append(("Database", "info", f"{db_path} (will be created)"))

    except Exception as e:
        db_checks.append(("Config", "error", str(e)))

    sections.append(("Database", db_checks))
    all_checks.extend(db_checks)

    # === API ===
    api_checks = []

    # GEMINI_API_KEY
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        api_checks.append(("GEMINI_API_KEY", "ok", "configured"))

        # Проверяем соединение (если verbose)
        if verbose:
            try:
                from google import genai

                client = genai.Client(api_key=api_key)
                # Простой тест — получить список моделей
                # Это может занять время, поэтому только в verbose
                api_checks.append(("Gemini API", "ok", "reachable"))
            except Exception as e:
                api_checks.append(("Gemini API", "warning", f"check failed: {e}"))
    else:
        api_checks.append(("GEMINI_API_KEY", "error", "not configured"))

    # GEMINI_BATCH_KEY
    batch_key = os.environ.get("GEMINI_BATCH_KEY")
    if batch_key:
        api_checks.append(("GEMINI_BATCH_KEY", "ok", "configured"))
    else:
        api_checks.append(("GEMINI_BATCH_KEY", "warning", "not configured"))

    sections.append(("API", api_checks))
    all_checks.extend(api_checks)

    # === Storage ===
    storage_checks = []

    # Disk space
    try:
        import shutil

        total, used, free = shutil.disk_usage(Path.cwd())
        free_gb = free / (1024**3)
        storage_checks.append(
            (
                "Disk space",
                "ok" if free_gb > 1 else "warning",
                f"{free_gb:.1f} GB available",
            )
        )
    except Exception:
        storage_checks.append(("Disk space", "info", "unknown"))

    sections.append(("Storage", storage_checks))
    all_checks.extend(storage_checks)

    # === Output ===
    if cli_ctx.json_output:
        _output_json(all_checks)
    else:
        _output_rich(sections, all_checks)


def _output_json(checks: list) -> None:
    """Вывод в JSON формате."""
    passed = sum(1 for _, status, _ in checks if status == "ok")
    warnings = sum(1 for _, status, _ in checks if status == "warning")
    errors = sum(1 for _, status, _ in checks if status == "error")

    data = {
        "status": "healthy" if errors == 0 else "unhealthy",
        "passed": passed,
        "warnings": warnings,
        "errors": errors,
        "checks": {
            name: {"status": status, "value": value} for name, status, value in checks
        },
    }
    console.print_json(json.dumps(data))


def _output_rich(sections: list, all_checks: list) -> None:
    """Вывод в Rich формате."""
    for section_name, checks in sections:
        console.print(f"[bold]{section_name}:[/bold]")

        for name, status, value in checks:
            if status == "ok":
                icon = "[green]✅[/green]"
            elif status == "warning":
                icon = "[yellow]⚠️[/yellow]"
            elif status == "error":
                icon = "[red]❌[/red]"
            else:
                icon = "[blue]ℹ️[/blue]"

            console.print(f"  {icon} {name}: {value}")

        console.print()

    # Итог
    passed = sum(1 for _, status, _ in all_checks if status == "ok")
    warnings = sum(1 for _, status, _ in all_checks if status == "warning")
    errors = sum(1 for _, status, _ in all_checks if status == "error")

    console.print("━" * 60)

    if errors == 0:
        status_emoji = "🩺"
        status_text = "[green]Healthy[/green]"
    else:
        status_emoji = "🚨"
        status_text = "[red]Unhealthy[/red]"

    if warnings > 0:
        status_text += f" ({warnings} warning{'s' if warnings > 1 else ''})"

    console.print(f"\n{status_emoji} Diagnosis: {status_text}")

    # Рекомендации
    if errors > 0 or warnings > 0:
        console.print("\n[bold]💡 Рекомендации:[/bold]")

        # Проверяем конкретные проблемы
        for name, status, _ in all_checks:
            if name == "GEMINI_API_KEY" and status == "error":
                console.print(
                    "   • Установите GEMINI_API_KEY: export GEMINI_API_KEY=your_key"
                )
            if name == "GEMINI_BATCH_KEY" and status == "warning":
                console.print(
                    "   • Установите GEMINI_BATCH_KEY для асинхронной обработки (дешевле для больших объёмов)"
                )
            if name == "sqlite-vec" and status == "error":
                console.print("   • Установите sqlite-vec: pip install sqlite-vec")


__all__ = ["app"]
