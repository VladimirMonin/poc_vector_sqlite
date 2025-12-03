"""Команды поиска.

Команды:
    SearchCommand — /search <query>
    SearchModeCommand — /search-mode <mode>
    SourcesCommand — /sources, /src
    SourceCommand — /source <N>
"""

from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from semantic_core.cli.chat.slash.base import BaseSlashCommand, SlashResult, SlashAction
from semantic_core.cli.chat.slash.handler import ChatContext


class SearchCommand(BaseSlashCommand):
    """Поиск в базе знаний."""

    name = "search"
    description = "Поиск в базе знаний"
    aliases = ["s"]
    usage = "/search <запрос>"

    def execute(self, ctx: ChatContext, args: str) -> SlashResult:
        """Выполнить поиск и показать результаты."""
        if not args.strip():
            ctx.console.print("[yellow]Использование: /search <запрос>[/yellow]")
            return SlashResult()

        query = args.strip()

        with ctx.console.status("[bold green]Ищу...[/bold green]"):
            results = ctx.core.search(
                query=query,
                limit=5,
                search_type=ctx.search_mode,  # type: ignore
            )

        if not results:
            ctx.console.print("[yellow]Ничего не найдено[/yellow]")
            return SlashResult()

        # Показываем результаты
        table = Table(title=f"🔍 Результаты поиска: {query}", show_header=True)
        table.add_column("#", width=3)
        table.add_column("Источник")
        table.add_column("Score", justify="right", width=8)

        for i, result in enumerate(results, 1):
            source = result.document.metadata.get("source", "—")
            if len(source) > 50:
                source = "..." + source[-47:]
            table.add_row(str(i), source, f"{result.score:.3f}")

        ctx.console.print(table)

        # Добавляем в extra_context
        context_text = "\n\n---\n\n".join(
            f"[Source: {r.document.metadata.get('source', 'unknown')}]\n{r.document.content}"
            for r in results[:3]  # Только топ-3
        )
        ctx.add_extra_context("search_results", context_text)

        ctx.console.print(
            f"\n[green]✓ Топ-3 результата добавлены в контекст следующего вопроса[/green]"
        )
        return SlashResult()


class SearchModeCommand(BaseSlashCommand):
    """Сменить режим поиска."""

    name = "search-mode"
    description = "Сменить режим поиска (vector/fts/hybrid)"
    aliases = ["mode"]
    usage = "/search-mode <mode>"

    VALID_MODES = ("vector", "fts", "hybrid")

    def execute(self, ctx: ChatContext, args: str) -> SlashResult:
        """Показать или сменить режим поиска."""
        if not args.strip():
            # Показываем текущий режим
            mode_icons = {
                "vector": "🎯 vector (семантический)",
                "fts": "📝 fts (полнотекстовый)",
                "hybrid": "🔀 hybrid (гибридный)",
            }
            current = mode_icons.get(ctx.search_mode, ctx.search_mode)
            ctx.console.print(f"Текущий режим поиска: [cyan]{current}[/cyan]")
            ctx.console.print(
                f"[dim]Доступные: {', '.join(self.VALID_MODES)}[/dim]"
            )
            return SlashResult()

        mode = args.strip().lower()
        if mode not in self.VALID_MODES:
            ctx.console.print(
                f"[red]Неверный режим: {mode}[/red]\n"
                f"[dim]Доступные: {', '.join(self.VALID_MODES)}[/dim]"
            )
            return SlashResult()

        ctx.search_mode = mode
        ctx.console.print(f"[green]✓ Режим поиска изменён на: {mode}[/green]")
        return SlashResult()


class SourcesCommand(BaseSlashCommand):
    """Показать источники последнего ответа."""

    name = "sources"
    description = "Показать источники последнего ответа"
    aliases = ["src"]

    def execute(self, ctx: ChatContext, args: str) -> SlashResult:
        """Показать таблицу источников."""
        if not ctx.last_result:
            ctx.console.print("[yellow]Нет предыдущего ответа[/yellow]")
            return SlashResult()

        if not ctx.last_result.has_sources:
            ctx.console.print("[yellow]В последнем ответе нет источников[/yellow]")
            return SlashResult()

        sources = ctx.last_result.sources
        full_docs = ctx.last_result.full_docs

        table = Table(title="📚 Источники последнего ответа", show_header=True)
        table.add_column("#", width=3)
        table.add_column("Источник")
        table.add_column("Score", justify="right", width=8)

        for i, source in enumerate(sources, 1):
            if full_docs:
                # SearchResult
                path = source.document.metadata.get("source", "—")
            else:
                # ChunkResult
                path = source.parent_doc_title or f"Doc#{source.parent_doc_id}"

            if len(path) > 60:
                path = "..." + path[-57:]

            table.add_row(str(i), path, f"{source.score:.3f}")

        ctx.console.print(table)
        ctx.console.print("[dim]Используйте /source <N> для полного текста[/dim]")
        return SlashResult()


class SourceCommand(BaseSlashCommand):
    """Показать полный текст источника."""

    name = "source"
    description = "Показать полный текст источника N"
    aliases = []
    usage = "/source <номер>"

    def execute(self, ctx: ChatContext, args: str) -> SlashResult:
        """Показать полный текст конкретного источника."""
        if not ctx.last_result:
            ctx.console.print("[yellow]Нет предыдущего ответа[/yellow]")
            return SlashResult()

        if not ctx.last_result.has_sources:
            ctx.console.print("[yellow]В последнем ответе нет источников[/yellow]")
            return SlashResult()

        # Парсим номер
        if not args.strip():
            ctx.console.print("[yellow]Использование: /source <номер>[/yellow]")
            return SlashResult()

        try:
            num = int(args.strip())
        except ValueError:
            ctx.console.print(f"[red]Неверный номер: {args}[/red]")
            return SlashResult()

        sources = ctx.last_result.sources
        if num < 1 or num > len(sources):
            ctx.console.print(
                f"[red]Номер должен быть от 1 до {len(sources)}[/red]"
            )
            return SlashResult()

        source = sources[num - 1]
        full_docs = ctx.last_result.full_docs

        # Получаем текст и метаданные
        if full_docs:
            content = source.document.content
            title = source.document.metadata.get("source", "Источник")
        else:
            content = source.content
            title = source.parent_doc_title or f"Chunk #{source.chunk_id}"

        # Показываем
        ctx.console.print(Panel(
            Markdown(content) if content.startswith("#") else content,
            title=f"📄 {title}",
            subtitle=f"Score: {source.score:.3f}",
            border_style="blue",
        ))
        return SlashResult()


__all__ = [
    "SearchCommand",
    "SearchModeCommand",
    "SourcesCommand",
    "SourceCommand",
]
