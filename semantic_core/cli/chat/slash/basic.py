"""Базовые slash-команды.

Команды:
    HelpCommand — /help, /h, /?
    ClearCommand — /clear, /cls
    QuitCommand — /quit, /q, /exit
    TokensCommand — /tokens
    HistoryCommand — /history
    CompressCommand — /compress
"""

from rich.table import Table
from rich.panel import Panel

from semantic_core.cli.chat.slash.base import BaseSlashCommand, SlashResult, SlashAction
from semantic_core.cli.chat.slash.handler import ChatContext


class HelpCommand(BaseSlashCommand):
    """Показать справку по командам."""

    name = "help"
    description = "Показать справку по командам"
    aliases = ["h", "?"]

    def __init__(self, handler: "SlashCommandHandler"):
        """Принимает handler для получения списка команд."""
        self._handler = handler

    def execute(self, ctx: ChatContext, args: str) -> SlashResult:
        """Показать список всех команд."""
        commands = self._handler.list_commands()

        table = Table(title="📚 Доступные команды", show_header=True)
        table.add_column("Команда", style="cyan")
        table.add_column("Описание")

        for cmd in commands:
            name = f"/{cmd.name}"
            if cmd.aliases:
                name += f" ({', '.join('/' + a for a in cmd.aliases)})"
            table.add_row(name, cmd.description)

        ctx.console.print(table)
        return SlashResult()


class ClearCommand(BaseSlashCommand):
    """Очистить экран."""

    name = "clear"
    description = "Очистить экран"
    aliases = ["cls"]

    def execute(self, ctx: ChatContext, args: str) -> SlashResult:
        """Очистить консоль."""
        return SlashResult(action=SlashAction.CLEAR)


class QuitCommand(BaseSlashCommand):
    """Выйти из чата."""

    name = "quit"
    description = "Выйти из чата"
    aliases = ["q", "exit"]

    def execute(self, ctx: ChatContext, args: str) -> SlashResult:
        """Завершить сессию чата."""
        return SlashResult(
            action=SlashAction.EXIT, message="[dim]До свидания! 👋[/dim]"
        )


class TokensCommand(BaseSlashCommand):
    """Показать использование токенов."""

    name = "tokens"
    description = "Показать статистику токенов"
    aliases = ["t"]

    def execute(self, ctx: ChatContext, args: str) -> SlashResult:
        """Показать статистику токенов в истории."""
        if ctx.history_manager is None:
            ctx.console.print("[yellow]История отключена[/yellow]")
            return SlashResult()

        msg_count = len(ctx.history_manager)
        total_tokens = ctx.history_manager.total_tokens()
        has_summary = ctx.history_manager.has_summary

        # Информация о последнем запросе
        last_info = ""
        if ctx.last_result and ctx.last_result.generation:
            gen = ctx.last_result.generation
            last_info = f"\n  Последний запрос: {gen.input_tokens or 0} input, {gen.output_tokens or 0} output"

        summary_info = " (включая summary)" if has_summary else ""

        text = (
            f"📊 Статистика токенов:\n"
            f"  Сообщений в истории: {msg_count}\n"
            f"  Токенов в истории: {total_tokens}{summary_info}"
            f"{last_info}"
        )

        ctx.console.print(Panel(text, title="Токены", border_style="blue"))
        return SlashResult()


class HistoryCommand(BaseSlashCommand):
    """Показать историю чата."""

    name = "history"
    description = "Показать историю сообщений"
    aliases = ["hist"]

    def execute(self, ctx: ChatContext, args: str) -> SlashResult:
        """Показать краткую историю сообщений."""
        if ctx.history_manager is None:
            ctx.console.print("[yellow]История отключена[/yellow]")
            return SlashResult()

        history = ctx.history_manager.get_history()
        if not history:
            ctx.console.print("[dim]История пуста[/dim]")
            return SlashResult()

        # Показываем summary если есть
        if ctx.history_manager.has_summary:
            ctx.console.print("[dim]📝 [Summary сохранён][/dim]\n")

        table = Table(show_header=True, title=f"📜 История ({len(history)} сообщ.)")
        table.add_column("#", width=3)
        table.add_column("Роль", width=10)
        table.add_column("Сообщение")
        table.add_column("Токены", justify="right", width=8)

        for i, msg in enumerate(history, 1):
            # Обрезаем длинные сообщения
            content = msg.content
            if len(content) > 60:
                content = content[:57] + "..."

            role_style = {
                "user": "blue",
                "assistant": "green",
                "system": "yellow",
            }.get(msg.role, "white")

            table.add_row(
                str(i),
                f"[{role_style}]{msg.role}[/{role_style}]",
                content,
                str(msg.tokens),
            )

        ctx.console.print(table)
        return SlashResult()


class CompressCommand(BaseSlashCommand):
    """Принудительно сжать историю."""

    name = "compress"
    description = "Принудительно сжать историю чата"
    aliases = []

    def execute(self, ctx: ChatContext, args: str) -> SlashResult:
        """Запустить сжатие истории."""
        if ctx.history_manager is None:
            ctx.console.print(
                "[yellow]История отключена (используйте чат без --no-history)[/yellow]"
            )
            return SlashResult()

        # Получаем историю
        messages = ctx.history_manager.get_history()
        if len(messages) < 2:
            ctx.console.print(
                "[yellow]Недостаточно сообщений для сжатия (минимум 2)[/yellow]"
            )
            return SlashResult()

        before_tokens = ctx.history_manager.total_tokens()

        # Проверяем, поддерживает ли стратегия сжатие
        strategy = ctx.history_manager.strategy

        with ctx.console.status("[bold green]Сжимаю историю...[/bold green]"):
            from semantic_core.core.context.strategies import AdaptiveWithCompression
            from semantic_core.core.context import ContextCompressor

            if isinstance(strategy, AdaptiveWithCompression):
                # Стратегия поддерживает сжатие — используем её компрессор
                old_threshold = strategy.threshold
                strategy.threshold = 1  # Временно понижаем для триггера
                ctx.history_manager._messages = strategy.trim(messages)
                strategy.threshold = old_threshold
            else:
                # Любая другая стратегия — создаём временный компрессор
                compressor = ContextCompressor(ctx.llm)
                # Сжимаем все сообщения кроме последних 2
                if len(messages) > 2:
                    to_compress = messages[:-2]
                    to_keep = messages[-2:]
                    summary = compressor.compress(to_compress)
                    ctx.history_manager._messages = [summary] + to_keep

        after_tokens = ctx.history_manager.total_tokens()

        ctx.console.print(
            f"[green]✓ История сжата: {before_tokens} → {after_tokens} токенов "
            f"(сэкономлено {before_tokens - after_tokens})[/green]"
        )
        return SlashResult()


# Для удобства импорта
from semantic_core.cli.chat.slash.handler import SlashCommandHandler

__all__ = [
    "HelpCommand",
    "ClearCommand",
    "QuitCommand",
    "TokensCommand",
    "HistoryCommand",
    "CompressCommand",
]
