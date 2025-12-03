"""Рендереры для CLI вывода.

Функции для форматирования результатов поиска,
сводок индексации и сообщений об ошибках.
"""

from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


console = Console()


def render_search_results(
    query: str,
    results: list[Any],
    search_type: str = "hybrid",
    verbose: bool = False,
) -> None:
    """Отображает результаты поиска в Rich формате.

    Args:
        query: Поисковый запрос.
        results: Список SearchResult объектов.
        search_type: Тип поиска (vector, fts, hybrid).
        verbose: Показывать детальную информацию.
    """
    if not results:
        console.print(Panel(
            "[yellow]Ничего не найдено[/yellow]",
            title=f"🔍 Поиск: {query}",
        ))
        return

    # Заголовок
    type_icons = {
        "vector": "🎯",
        "fts": "📝",
        "hybrid": "🔀",
    }
    icon = type_icons.get(search_type, "🔍")

    console.print(Panel(
        f"[cyan]Найдено результатов: {len(results)}[/cyan]",
        title=f"{icon} Поиск: [bold]{query}[/bold]",
    ))

    # Таблица
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=3)
    table.add_column("Score", justify="right", width=8)
    table.add_column("Источник", width=30)
    table.add_column("Контент", overflow="fold")

    for i, result in enumerate(results, 1):
        score_text = _format_score(result.score)
        source = _format_source(result.metadata.get("source", "—"))
        content = _format_content(result.content, verbose)
        table.add_row(str(i), score_text, source, content)

    console.print(table)


def render_ingest_summary(
    success: int,
    failed: int,
    errors: Optional[list[dict]] = None,
) -> None:
    """Отображает сводку индексации.

    Args:
        success: Количество успешно обработанных.
        failed: Количество ошибок.
        errors: Список ошибок с деталями.
    """
    total = success + failed

    if failed == 0:
        console.print(Panel(
            f"[green]✓ Успешно проиндексировано: {success} из {total}[/green]",
            title="📚 Индексация завершена",
        ))
    else:
        console.print(Panel(
            f"[yellow]Проиндексировано: {success} из {total}\n"
            f"[red]Ошибок: {failed}[/red][/yellow]",
            title="⚠️  Индексация с ошибками",
        ))

        if errors:
            console.print("\n[red bold]Ошибки:[/red bold]")
            for err in errors[:5]:
                console.print(f"  • {err.get('file', '—')}: {err.get('error', '—')}")
            if len(errors) > 5:
                console.print(f"  ... и ещё {len(errors) - 5} ошибок")


def render_error(message: str, title: str = "Ошибка") -> None:
    """Отображает сообщение об ошибке.

    Args:
        message: Текст ошибки.
        title: Заголовок панели.
    """
    console.print(Panel(
        f"[red]{message}[/red]",
        title=f"❌ {title}",
    ))


def render_success(message: str, title: str = "Успех") -> None:
    """Отображает сообщение об успехе.

    Args:
        message: Текст сообщения.
        title: Заголовок панели.
    """
    console.print(Panel(
        f"[green]{message}[/green]",
        title=f"✓ {title}",
    ))


def render_warning(message: str, title: str = "Предупреждение") -> None:
    """Отображает предупреждение.

    Args:
        message: Текст предупреждения.
        title: Заголовок панели.
    """
    console.print(Panel(
        f"[yellow]{message}[/yellow]",
        title=f"⚠️  {title}",
    ))


def _format_score(score: float) -> Text:
    """Форматирует score с цветовой индикацией."""
    if score >= 0.8:
        return Text(f"{score:.3f}", style="green")
    elif score >= 0.5:
        return Text(f"{score:.3f}", style="yellow")
    else:
        return Text(f"{score:.3f}", style="red")


def _format_source(source: str, max_length: int = 28) -> str:
    """Форматирует путь к источнику с обрезкой."""
    if len(source) > max_length:
        return "..." + source[-(max_length - 3):]
    return source


def _format_content(content: str, verbose: bool, max_length: int = 100) -> str:
    """Форматирует контент с обрезкой."""
    if not verbose and len(content) > max_length:
        return content[:max_length] + "..."
    return content
