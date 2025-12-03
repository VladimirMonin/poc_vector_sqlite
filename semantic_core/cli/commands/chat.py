"""Команда chat для интерактивного RAG-чата.

Запускает REPL-режим с Retrieval-Augmented Generation.
Поддерживает разные режимы поиска и настройки LLM.

Usage:
    semantic chat                     # Гибридный поиск, gemini-2.0-flash
    semantic chat --model gemini-1.5-pro  # Другая модель
    semantic chat --search vector     # Только векторный поиск
    semantic chat --context 10        # Больше контекста
"""

from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich.text import Text

from semantic_core.cli.console import console as default_console

chat_cmd = typer.Typer(
    name="chat",
    help="Интерактивный RAG-чат с базой знаний",
    no_args_is_help=False,
)


@chat_cmd.callback(invoke_without_command=True)
def chat(
    ctx: typer.Context,
    model: str = typer.Option(
        "gemini-2.0-flash",
        "--model",
        "-m",
        help="Модель LLM для генерации ответов",
    ),
    context_chunks: int = typer.Option(
        5,
        "--context",
        "-c",
        help="Количество чанков контекста",
        min=1,
        max=20,
    ),
    search_mode: str = typer.Option(
        "hybrid",
        "--search",
        "-s",
        help="Режим поиска: vector, fts, hybrid",
    ),
    temperature: float = typer.Option(
        0.7,
        "--temperature",
        "-t",
        help="Температура генерации (0.0-2.0)",
        min=0.0,
        max=2.0,
    ),
    show_sources: bool = typer.Option(
        True,
        "--sources/--no-sources",
        help="Показывать источники ответа",
    ),
    max_tokens: Optional[int] = typer.Option(
        None,
        "--max-tokens",
        help="Максимальное количество токенов в ответе",
    ),
    full_docs: bool = typer.Option(
        False,
        "--full-docs",
        help="Использовать полные документы вместо чанков для контекста",
    ),
) -> None:
    """Запустить интерактивный RAG-чат.

    Примеры:
        semantic chat
        semantic chat --model gemini-1.5-pro --context 10
        semantic chat --search vector --no-sources
        semantic chat --full-docs  # Использовать полные документы
    """
    from semantic_core.cli.app import get_cli_context

    cli_ctx = get_cli_context()
    console = default_console

    # Валидация режима поиска
    valid_modes = ("vector", "fts", "hybrid")
    if search_mode not in valid_modes:
        raise typer.BadParameter(
            f"Неверный режим поиска: {search_mode}. "
            f"Допустимые значения: {', '.join(valid_modes)}"
        )

    # Получаем компоненты
    try:
        core = cli_ctx.get_core()
        config = cli_ctx.get_config()
    except Exception as e:
        console.print(
            Panel(
                f"[red]Ошибка инициализации: {e}[/red]",
                title="❌ Ошибка",
            )
        )
        raise typer.Exit(1)

    # Инициализируем LLM провайдер
    try:
        from semantic_core.infrastructure.llm import GeminiLLMProvider

        api_key = config.require_api_key()
        llm = GeminiLLMProvider(api_key=api_key, model=model)
    except Exception as e:
        console.print(
            Panel(
                f"[red]Ошибка инициализации LLM: {e}[/red]",
                title="❌ Ошибка",
            )
        )
        raise typer.Exit(1)

    # Инициализируем RAG Engine
    from semantic_core.core.rag import RAGEngine

    rag = RAGEngine(
        core=core,
        llm=llm,
        context_chunks=context_chunks,
    )

    # Приветствие
    _show_welcome(console, model, search_mode, context_chunks, full_docs)

    # REPL цикл
    while True:
        try:
            # Получаем ввод
            query = Prompt.ask("\n[bold blue]You[/bold blue]")

            # Проверка на выход
            if query.lower() in ("exit", "quit", "/exit", "/quit", "q"):
                console.print("[dim]До свидания! 👋[/dim]")
                break

            # Пустой ввод
            if not query.strip():
                continue

            # Выполняем RAG запрос
            with console.status("[bold green]Думаю...[/bold green]", spinner="dots"):
                try:
                    result = rag.ask(
                        query=query,
                        search_mode=search_mode,  # type: ignore
                        temperature=temperature,
                        max_tokens=max_tokens,
                        full_docs=full_docs,
                    )
                except Exception as e:
                    console.print(
                        Panel(
                            f"[red]Ошибка: {e}[/red]",
                            title="❌ Ошибка генерации",
                        )
                    )
                    continue

            # Выводим ответ
            console.print()
            console.print("[bold green]Assistant[/bold green]")
            console.print(Markdown(result.answer))

            # Показываем источники
            if show_sources and result.has_sources:
                _show_sources(console, result.sources, result.full_docs)

            # Показываем токены
            if result.total_tokens:
                console.print(
                    f"\n[dim]Токены: {result.total_tokens} "
                    f"(input: {result.generation.input_tokens}, "
                    f"output: {result.generation.output_tokens})[/dim]"
                )

        except KeyboardInterrupt:
            console.print("\n[dim]Прервано. Введите 'exit' для выхода.[/dim]")
            continue

        except EOFError:
            console.print("\n[dim]До свидания! 👋[/dim]")
            break


def _show_welcome(
    console: Console,
    model: str,
    search_mode: str,
    context_chunks: int,
    full_docs: bool = False,
) -> None:
    """Показывает приветственное сообщение."""
    mode_icons = {
        "vector": "🎯 Векторный",
        "fts": "📝 Полнотекстовый",
        "hybrid": "🔀 Гибридный",
    }
    mode_label = mode_icons.get(search_mode, search_mode)
    context_mode = "документов" if full_docs else "чанков"

    welcome_text = (
        f"[bold]🤖 Semantic Chat[/bold]\n\n"
        f"Модель: [cyan]{model}[/cyan]\n"
        f"Поиск: [cyan]{mode_label}[/cyan]\n"
        f"Контекст: [cyan]{context_chunks} {context_mode}[/cyan]\n"
    )

    if full_docs:
        welcome_text += f"Режим: [yellow]полные документы[/yellow]\n"

    welcome_text += f"\n[dim]Введите вопрос или 'exit' для выхода.[/dim]"

    console.print(
        Panel(
            welcome_text,
            title="💬 RAG Chat",
            border_style="blue",
        )
    )


def _show_sources(console: Console, sources: list, full_docs: bool = False) -> None:
    """Показывает источники ответа."""
    console.print("\n[bold dim]📚 Источники:[/bold dim]")

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("", width=3)
    table.add_column("", style="dim")
    table.add_column("", justify="right", style="dim")

    for i, source in enumerate(sources[:5], 1):
        # Извлекаем путь и score в зависимости от типа источника
        if full_docs:
            # SearchResult — полные документы
            source_path = source.document.metadata.get("source", "—")
        else:
            # ChunkResult — чанки
            source_path = source.parent_doc_title or f"Doc#{source.parent_doc_id}"

        if len(source_path) > 50:
            source_path = "..." + source_path[-47:]

        score_text = f"{source.score:.2f}"
        table.add_row(f"[{i}]", source_path, score_text)

    console.print(table)


__all__ = ["chat_cmd"]
