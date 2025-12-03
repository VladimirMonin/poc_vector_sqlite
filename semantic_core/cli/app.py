"""Typer приложение — главный CLI.

Определяет глобальные опции и монтирует команды.

Attributes:
    app: Главное Typer приложение.
"""

from pathlib import Path
from typing import Optional

import typer

from semantic_core.cli.context import CLIContext

# Главное приложение
app = typer.Typer(
    name="semantic",
    help="🧠 Semantic Core CLI — Ваш второй мозг в терминале.",
    add_completion=True,
    no_args_is_help=True,
    rich_markup_mode="rich",
)


# Хранение контекста между callback и командами
_cli_context: Optional[CLIContext] = None


def get_cli_context() -> CLIContext:
    """Получить текущий CLI контекст.

    Returns:
        CLIContext с настройками из глобальных опций.

    Raises:
        RuntimeError: Если контекст не инициализирован.
    """
    if _cli_context is None:
        # Создаём дефолтный контекст если команда вызвана напрямую
        return CLIContext()
    return _cli_context


def version_callback(value: bool) -> None:
    """Показать версию и выйти."""
    if value:
        from semantic_core import __version__

        typer.echo(f"Semantic Core CLI v{__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    ctx: typer.Context,
    db_path: Optional[Path] = typer.Option(
        None,
        "--db-path",
        "-d",
        help="Путь к SQLite базе данных.",
        envvar="SEMANTIC_DB_PATH",
    ),
    log_level: Optional[str] = typer.Option(
        None,
        "--log-level",
        "-l",
        help="Уровень логирования: TRACE, DEBUG, INFO, WARNING, ERROR.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Вывод в формате JSON (для скриптов).",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Подробный вывод (эквивалент --log-level INFO).",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Показать версию и выйти.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """🧠 Semantic Core CLI — Ваш второй мозг в терминале."""
    global _cli_context

    _cli_context = CLIContext(
        db_path=db_path,
        log_level=log_level,
        json_output=json_output,
        verbose=verbose,
    )

    # Сохраняем в typer context для доступа из команд
    ctx.obj = _cli_context


# === Монтирование команд ===

# Phase 8.3: Config & Init
from semantic_core.cli.commands import init_cmd, config_cmd, doctor_cmd

app.add_typer(init_cmd.app, name="init")
app.add_typer(config_cmd.app, name="config")
app.add_typer(doctor_cmd.app, name="doctor")

# Phase 8.0: Core commands
from semantic_core.cli.commands import ingest_cmd, search_cmd, docs_cmd

app.add_typer(ingest_cmd, name="ingest")
app.add_typer(search_cmd, name="search")
app.add_typer(docs_cmd, name="docs")

# Phase 8.1: Operations commands
from semantic_core.cli.commands import queue_cmd, worker_cmd

app.add_typer(queue_cmd, name="queue")
app.add_typer(worker_cmd, name="worker")

# Phase 9.0: RAG Chat
from semantic_core.cli.commands import chat_cmd

app.add_typer(chat_cmd, name="chat")


__all__ = ["app", "get_cli_context"]
