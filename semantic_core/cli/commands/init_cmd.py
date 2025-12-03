"""Команда init — инициализация проекта.

Создаёт semantic.toml в текущей директории.

Usage:
    semantic init [OPTIONS]
"""

from pathlib import Path
from typing import Optional

import typer
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from semantic_core.cli.console import console
from semantic_core.cli.app import get_cli_context
from semantic_core.config import SemanticConfig

app = typer.Typer(
    help="⚙️ Инициализация проекта Semantic Core.",
    invoke_without_command=True,
)


@app.callback(invoke_without_command=True)
def init(
    ctx: typer.Context,
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Перезаписать существующий конфиг.",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        "-y",
        help="Использовать значения по умолчанию без вопросов.",
    ),
    output_path: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Путь для сохранения конфига (по умолчанию: ./semantic.toml).",
    ),
) -> None:
    """Создать semantic.toml в текущей директории."""
    cli_ctx = get_cli_context()
    config_path = output_path or Path.cwd() / "semantic.toml"

    # Проверяем существующий файл
    if config_path.exists() and not force:
        console.print(f"[yellow]⚠️  Файл {config_path} уже существует.[/yellow]")
        if non_interactive:
            console.print("Используйте --force для перезаписи.")
            raise typer.Exit(1)

        if not Confirm.ask("Перезаписать?", default=False):
            raise typer.Exit(0)

    console.print("\n[bold]⚙️  Инициализация Semantic Core проекта...[/bold]\n")

    # Собираем настройки
    if non_interactive:
        # Дефолтные значения
        db_path = "semantic.db"
        log_level = "INFO"
        splitter = "smart"
        media_enabled = True
    else:
        # Интерактивный режим
        db_path = Prompt.ask(
            "📁 Путь к базе данных",
            default="semantic.db",
        )
        log_level = Prompt.ask(
            "📊 Уровень логирования",
            default="INFO",
            choices=["TRACE", "DEBUG", "INFO", "WARNING", "ERROR"],
        )
        splitter = Prompt.ask(
            "✂️  Тип сплиттера",
            default="smart",
            choices=["simple", "smart"],
        )
        media_enabled = Confirm.ask(
            "🖼️  Включить анализ медиа (изображения/аудио/видео)?",
            default=True,
        )

    # Проверяем API ключ
    import os

    has_api_key = bool(os.environ.get("GEMINI_API_KEY"))
    has_batch_key = bool(os.environ.get("GEMINI_BATCH_KEY"))

    if has_api_key:
        console.print("[green]✅ GEMINI_API_KEY найден в окружении[/green]")
    else:
        console.print(
            "[yellow]⚠️  GEMINI_API_KEY не найден. "
            "Установите его перед использованием.[/yellow]"
        )

    if has_batch_key:
        console.print("[green]✅ GEMINI_BATCH_KEY найден в окружении[/green]")

    # Генерируем TOML
    toml_content = _generate_toml(
        db_path=db_path,
        log_level=log_level,
        splitter=splitter,
        media_enabled=media_enabled,
    )

    # Записываем файл
    config_path.write_text(toml_content, encoding="utf-8")

    console.print(f"\n[green]✅ Создан: {config_path}[/green]\n")

    # Показываем структуру проекта
    console.print(
        Panel(
            f"""[bold]📁 Структура проекта:[/bold]

   ./semantic.toml     # Конфигурация
   ./{db_path}    # База данных (создастся при первом запуске)

[bold]💡 Следующие шаги:[/bold]

   1. Установите API ключ: export GEMINI_API_KEY=your_key
   2. Проверьте настройки: semantic config show
   3. Диагностика: semantic doctor""",
            title="[bold green]Semantic Core[/bold green]",
            border_style="green",
        )
    )


def _generate_toml(
    db_path: str,
    log_level: str,
    splitter: str,
    media_enabled: bool,
) -> str:
    """Генерирует содержимое semantic.toml.

    Args:
        db_path: Путь к базе данных.
        log_level: Уровень логирования.
        splitter: Тип сплиттера.
        media_enabled: Включена ли обработка медиа.

    Returns:
        Строка с содержимым TOML файла.
    """
    return f'''# Semantic Core Configuration
# Generated by: semantic init

[database]
path = "{db_path}"

[logging]
level = "{log_level}"
# file = "semantic.log"  # Раскомментируйте для записи в файл

[gemini]
# API ключ читается из переменной окружения GEMINI_API_KEY
model = "text-embedding-004"
embedding_dimension = 768

[processing]
splitter = "{splitter}"           # simple | smart
context_strategy = "hierarchical"  # basic | hierarchical

[media]
enabled = {str(media_enabled).lower()}
rpm_limit = 15  # Запросов в минуту для Vision/Audio API

[search]
limit = 10      # Результатов по умолчанию
type = "hybrid"  # vector | fts | hybrid
'''


__all__ = ["app"]
