"""Команда search для CLI.

Семантический поиск по проиндексированным документам.

Usage:
    semantic search "запрос"                  # Гибридный поиск
    semantic search "запрос" --type vector    # Только векторный
    semantic search "запрос" -l 20            # Больше результатов
"""

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


search_cmd = typer.Typer(
    name="search",
    help="Семантический поиск по документам",
    no_args_is_help=True,
)

console = Console()


@search_cmd.callback(invoke_without_command=True)
def search(
    ctx: typer.Context,
    query: str = typer.Argument(
        ...,
        help="Поисковый запрос",
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        "-l",
        help="Максимальное количество результатов",
        min=1,
        max=100,
    ),
    search_type: str = typer.Option(
        "hybrid",
        "--type",
        "-t",
        help="Тип поиска: vector, fts, hybrid",
    ),
    threshold: Optional[float] = typer.Option(
        None,
        "--threshold",
        "-T",
        help="Минимальный порог релевантности (0.0-1.0)",
        min=0.0,
        max=1.0,
    ),
    k: int = typer.Option(
        60,
        "--k",
        "-k",
        help="Параметр k для RRF (Reciprocal Rank Fusion)",
        min=1,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Показывать детальную информацию",
    ),
) -> None:
    """Выполнить семантический поиск.

    Примеры:
        semantic search "как работает эмбеддинг"
        semantic search "rate limiting" --type vector --limit 5
        semantic search "обработка ошибок" -T 0.5
    """
    # Late import to avoid circular dependency
    from semantic_core.cli.app import get_cli_context
    
    cli_ctx = get_cli_context()

    # Валидация типа поиска
    valid_types = ("vector", "fts", "hybrid")
    if search_type not in valid_types:
        raise typer.BadParameter(
            f"Неверный тип поиска: {search_type}. "
            f"Допустимые значения: {', '.join(valid_types)}"
        )

    core = cli_ctx.get_core()

    # Выполняем поиск
    try:
        results = core.search(
            query=query,
            limit=limit,
            mode=search_type,
            k=k,
        )
    except Exception as e:
        console.print(Panel(
            f"[red]Ошибка поиска: {e}[/red]",
            title="❌ Ошибка",
        ))
        raise typer.Exit(1)

    # Фильтрация по порогу
    if threshold is not None:
        results = [r for r in results if r.score >= threshold]

    # Вывод результатов
    if cli_ctx.json_output:
        _render_json(query, results, search_type)
    else:
        _render_rich(query, results, search_type, verbose)


def _render_rich(
    query: str,
    results: list,
    search_type: str,
    verbose: bool,
) -> None:
    """Отображает результаты в Rich формате."""
    if not results:
        console.print(Panel(
            "[yellow]Ничего не найдено[/yellow]",
            title=f"🔍 Поиск: {query}",
        ))
        return

    # Заголовок
    type_label = {
        "vector": "🎯 Векторный",
        "fts": "📝 Полнотекстовый",
        "hybrid": "🔀 Гибридный",
    }.get(search_type, search_type)

    console.print(Panel(
        f"[cyan]Найдено результатов: {len(results)}[/cyan]",
        title=f"🔍 {type_label} поиск: [bold]{query}[/bold]",
    ))

    # Таблица результатов
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=3)
    table.add_column("Score", justify="right", width=8)
    table.add_column("Источник", width=30)
    table.add_column("Контент", overflow="fold")

    for i, result in enumerate(results, 1):
        # Score с цветовой индикацией
        score = result.score
        if score >= 0.8:
            score_text = Text(f"{score:.3f}", style="green")
        elif score >= 0.5:
            score_text = Text(f"{score:.3f}", style="yellow")
        else:
            score_text = Text(f"{score:.3f}", style="red")

        # Источник
        source = result.metadata.get("source", "—")
        if len(source) > 28:
            source = "..." + source[-25:]

        # Контент (превью)
        content = result.content
        if not verbose and len(content) > 100:
            content = content[:100] + "..."

        table.add_row(str(i), score_text, source, content)

    console.print(table)

    # Детальная информация (verbose)
    if verbose and results:
        console.print("\n[dim]Детали первого результата:[/dim]")
        first = results[0]
        console.print(f"  Chunk ID: {getattr(first, 'chunk_id', '—')}")
        console.print(f"  Doc ID: {getattr(first, 'document_id', '—')}")
        console.print(f"  Match Type: {getattr(first, 'match_type', '—')}")
        if first.metadata:
            console.print("  Metadata:")
            for key, value in list(first.metadata.items())[:5]:
                console.print(f"    {key}: {value}")


def _render_json(query: str, results: list, search_type: str) -> None:
    """Отображает результаты в JSON формате."""
    import json

    output = {
        "query": query,
        "search_type": search_type,
        "count": len(results),
        "results": [
            {
                "rank": i,
                "score": r.score,
                "content": r.content,
                "metadata": r.metadata,
                "chunk_id": getattr(r, "chunk_id", None),
                "document_id": getattr(r, "document_id", None),
                "match_type": str(getattr(r, "match_type", None)),
            }
            for i, r in enumerate(results, 1)
        ],
    }

    console.print_json(json.dumps(output, ensure_ascii=False, default=str))
