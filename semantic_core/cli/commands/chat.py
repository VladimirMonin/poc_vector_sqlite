"""Команда chat для интерактивного RAG-чата.

Запускает REPL-режим с Retrieval-Augmented Generation.
Поддерживает разные режимы поиска, настройки LLM и slash-команды.

Usage:
    semantic chat                     # Гибридный поиск, gemini-2.5-flash-lite
    semantic chat --model gemini-1.5-pro  # Другая модель
    semantic chat --search vector     # Только векторный поиск
    semantic chat --context 10        # Больше контекста
    semantic chat --history-limit 20  # Хранить 20 сообщений
    semantic chat --token-budget 10000  # Лимит по токенам

Slash-команды в чате:
    /help           Справка по командам
    /search <query> Поиск в базе знаний
    /sources        Источники последнего ответа
    /model          Показать/сменить модель
    /tokens         Статистика токенов
    /quit           Выход
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
        "gemini-2.5-flash-lite",
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
    history_limit: int = typer.Option(
        10,
        "--history-limit",
        "-H",
        help="Максимальное количество сообщений в истории",
        min=1,
        max=100,
    ),
    token_budget: Optional[int] = typer.Option(
        None,
        "--token-budget",
        help="Лимит токенов для истории (переопределяет --history-limit)",
    ),
    compress_at: Optional[int] = typer.Option(
        None,
        "--compress-at",
        help="Порог токенов для автоматического сжатия истории через LLM",
    ),
    compress_target: int = typer.Option(
        10000,
        "--compress-target",
        help="Целевое количество токенов после сжатия (используется с --compress-at)",
    ),
    no_history: bool = typer.Option(
        False,
        "--no-history",
        help="Отключить историю (без контекста предыдущих сообщений)",
    ),
) -> None:
    """Запустить интерактивный RAG-чат.

    Примеры:
        semantic chat
        semantic chat --model gemini-1.5-pro --context 10
        semantic chat --search vector --no-sources
        semantic chat --full-docs  # Использовать полные документы
        semantic chat --history-limit 20  # Хранить 20 сообщений
        semantic chat --token-budget 10000  # Лимит по токенам
        semantic chat --compress-at 30000  # Сжимать при 30k токенов
        semantic chat --no-history  # Без истории
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

    # Инициализируем менеджер истории
    from semantic_core.core.context import (
        ChatHistoryManager,
        LastNMessages,
        TokenBudget,
        Unlimited,
        AdaptiveWithCompression,
        ContextCompressor,
    )

    if no_history:
        # Без истории — Unlimited, но не будем передавать в RAG
        history_manager = None
        history_label = "отключена"
    elif compress_at:
        # Адаптивное сжатие через LLM
        compressor = ContextCompressor(llm)
        strategy = AdaptiveWithCompression(
            compressor=compressor,
            threshold_tokens=compress_at,
            target_tokens=compress_target,
        )
        history_manager = ChatHistoryManager(strategy)
        history_label = f"сжатие при {compress_at} токенов"
    elif token_budget:
        # По токенам
        history_manager = ChatHistoryManager(TokenBudget(max_tokens=token_budget))
        history_label = f"до {token_budget} токенов"
    else:
        # По количеству сообщений
        history_manager = ChatHistoryManager(LastNMessages(n=history_limit))
        history_label = f"до {history_limit} сообщений"

    # Инициализируем систему slash-команд
    from semantic_core.cli.chat.slash import (
        SlashCommandHandler,
        ChatContext,
        SlashAction,
        # Basic commands
        HelpCommand,
        ClearCommand,
        QuitCommand,
        TokensCommand,
        HistoryCommand,
        CompressCommand,
        # Search commands
        SearchCommand,
        SearchModeCommand,
        SourcesCommand,
        SourceCommand,
        # Settings commands
        ModelCommand,
        ContextCommand,
    )

    # Создаем контекст чата
    chat_context = ChatContext(
        console=console,
        core=core,
        rag=rag,
        llm=llm,
        history_manager=history_manager,
        last_result=None,
        search_mode=search_mode,
        context_chunks=context_chunks,
        temperature=temperature,
    )
    # Сохраняем дополнительные настройки в extra_context
    chat_context.extra_context["_show_sources"] = str(show_sources)
    chat_context.extra_context["_full_docs"] = str(full_docs)
    chat_context.extra_context["_max_tokens"] = str(max_tokens) if max_tokens else ""
    chat_context.extra_context["_model"] = model

    # Создаем обработчик slash-команд
    slash_handler = SlashCommandHandler()

    # Регистрируем команды (HelpCommand требует handler)
    slash_handler.register(HelpCommand(slash_handler))
    slash_handler.register(ClearCommand())
    slash_handler.register(QuitCommand())
    slash_handler.register(TokensCommand())
    slash_handler.register(HistoryCommand())
    slash_handler.register(CompressCommand())
    slash_handler.register(SearchCommand())
    slash_handler.register(SearchModeCommand())
    slash_handler.register(SourcesCommand())
    slash_handler.register(SourceCommand())
    slash_handler.register(ModelCommand())
    slash_handler.register(ContextCommand())

    # Приветствие
    _show_welcome(console, model, search_mode, context_chunks, full_docs, history_label)

    # REPL цикл
    while True:
        try:
            # Получаем ввод
            query = Prompt.ask("\n[bold blue]You[/bold blue]")

            # Пустой ввод
            if not query.strip():
                continue

            # Обработка slash-команд
            if query.startswith("/"):
                result = slash_handler.handle(query, chat_context)

                # Выводим сообщение если есть
                if result.message:
                    console.print(result.message)

                # Обрабатываем действие
                if result.action == SlashAction.EXIT:
                    console.print("[dim]До свидания! 👋[/dim]")
                    break
                elif result.action == SlashAction.CLEAR:
                    console.clear()
                    current_model = chat_context.extra_context.get("_model", model)
                    current_full_docs = (
                        chat_context.extra_context.get("_full_docs", "False") == "True"
                    )
                    _show_welcome(
                        console,
                        current_model,
                        chat_context.search_mode,
                        chat_context.context_chunks,
                        current_full_docs,
                        history_label,
                    )
                    console.print("[green]✓ Экран очищен[/green]")
                continue

            # Проверка на устаревшие команды выхода (без слеша)
            if query.lower() in ("exit", "quit", "q"):
                console.print("[dim]До свидания! 👋[/dim]")
                break

            # Выполняем RAG запрос
            with console.status("[bold green]Думаю...[/bold green]", spinner="dots"):
                try:
                    # Получаем историю для RAG (если есть)
                    history = history_manager.get_history() if history_manager else None

                    # Читаем настройки из контекста
                    current_max_tokens_str = chat_context.extra_context.get(
                        "_max_tokens", ""
                    )
                    current_max_tokens = (
                        int(current_max_tokens_str)
                        if current_max_tokens_str
                        else max_tokens
                    )
                    current_full_docs = (
                        chat_context.extra_context.get("_full_docs", "False") == "True"
                    )

                    result = rag.ask(
                        query=query,
                        search_mode=chat_context.search_mode,
                        temperature=chat_context.temperature,
                        max_tokens=current_max_tokens,
                        full_docs=current_full_docs,
                        history=history,
                    )

                    # Сохраняем результат в контекст
                    chat_context.last_result = result

                    # Сохраняем в историю
                    if history_manager:
                        input_tokens = result.generation.input_tokens or 0
                        output_tokens = result.generation.output_tokens or 0
                        # Примерное распределение токенов
                        history_manager.add_user(query, tokens=input_tokens // 2)
                        history_manager.add_assistant(
                            result.answer, tokens=output_tokens
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
            current_show_sources = (
                chat_context.extra_context.get("_show_sources", "True") == "True"
            )
            current_full_docs = (
                chat_context.extra_context.get("_full_docs", "False") == "True"
            )
            if current_show_sources and result.has_sources:
                _show_sources(console, result.sources, current_full_docs)

            # Показываем токены
            if result.total_tokens:
                history_info = ""
                if history_manager:
                    msg_count = len(history_manager)
                    total_history_tokens = history_manager.total_tokens()
                    history_info = f" | история: {msg_count} сообщ., {total_history_tokens} токенов"

                    # Показываем информацию о сжатии
                    if history_manager.has_summary:
                        history_info += " (сжато)"

                console.print(
                    f"\n[dim]Токены: {result.total_tokens} "
                    f"(input: {result.generation.input_tokens}, "
                    f"output: {result.generation.output_tokens}){history_info}[/dim]"
                )

        except KeyboardInterrupt:
            console.print("\n[dim]Прервано. Введите '/quit' для выхода.[/dim]")
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
    history_label: str = "до 10 сообщений",
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
        f"История: [cyan]{history_label}[/cyan]\n"
    )

    if full_docs:
        welcome_text += f"Режим: [yellow]полные документы[/yellow]\n"

    welcome_text += f"\n[dim]Введите вопрос или /help для списка команд.[/dim]"

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
