"""Обработчик slash-команд.

Классы:
    ChatContext
        Контекст чата для передачи в команды.
    SlashCommandHandler
        Регистрирует и роутит slash-команды.
"""

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

from rich.console import Console

from semantic_core.cli.chat.slash.base import BaseSlashCommand, SlashResult, SlashAction
from semantic_core.utils.logger import get_logger

if TYPE_CHECKING:
    from semantic_core.core.rag import RAGEngine, RAGResult
    from semantic_core.core.context import ChatHistoryManager
    from semantic_core.pipeline import SemanticCore
    from semantic_core.interfaces.llm import BaseLLMProvider

logger = get_logger(__name__)


@dataclass
class ChatContext:
    """Контекст чата для slash-команд.

    Предоставляет доступ ко всем компонентам чата.

    Attributes:
        console: Rich console для вывода.
        core: SemanticCore для поиска и индексации.
        rag: RAGEngine для вопрос-ответа.
        llm: LLM провайдер.
        history_manager: Менеджер истории чата.
        last_result: Результат последнего RAG запроса.
        search_mode: Текущий режим поиска.
        context_chunks: Количество чанков контекста.
        temperature: Температура генерации.
        extra_context: Дополнительный контекст для LLM.
    """

    console: Console
    core: "SemanticCore"
    rag: "RAGEngine"
    llm: "BaseLLMProvider"
    history_manager: Optional["ChatHistoryManager"] = None
    last_result: Optional["RAGResult"] = None
    search_mode: str = "hybrid"
    context_chunks: int = 5
    temperature: float = 0.7
    extra_context: dict[str, str] = field(default_factory=dict)

    def add_extra_context(self, key: str, content: str) -> None:
        """Добавить дополнительный контекст для следующего запроса."""
        self.extra_context[key] = content
        logger.debug("Extra context added", key=key, length=len(content))

    def clear_extra_context(self) -> None:
        """Очистить дополнительный контекст."""
        self.extra_context.clear()

    def get_extra_context_text(self) -> Optional[str]:
        """Получить объединённый дополнительный контекст."""
        if not self.extra_context:
            return None
        return "\n\n".join(
            f"[{key}]\n{content}" for key, content in self.extra_context.items()
        )


class SlashCommandHandler:
    """Регистрирует и обрабатывает slash-команды.

    Маршрутизирует команды по имени или алиасу,
    парсит аргументы и вызывает execute().

    Example:
        >>> handler = SlashCommandHandler()
        >>> handler.register(HelpCommand())
        >>> handler.register(SearchCommand())
        >>>
        >>> result = handler.handle("/help", ctx)
        >>> if result:
        ...     # Команда обработана
    """

    def __init__(self):
        """Инициализация обработчика."""
        self._commands: dict[str, BaseSlashCommand] = {}
        logger.debug("SlashCommandHandler initialized")

    def register(self, command: BaseSlashCommand) -> None:
        """Зарегистрировать команду.

        Args:
            command: Экземпляр команды.
        """
        self._commands[command.name] = command
        for alias in command.aliases:
            self._commands[alias] = command

        logger.debug(
            "Command registered",
            name=command.name,
            aliases=command.aliases,
        )

    def get_command(self, name: str) -> Optional[BaseSlashCommand]:
        """Получить команду по имени или алиасу."""
        return self._commands.get(name.lower())

    def list_commands(self) -> list[BaseSlashCommand]:
        """Получить список уникальных команд (без дублей по алиасам)."""
        seen = set()
        result = []
        for cmd in self._commands.values():
            if cmd.name not in seen:
                seen.add(cmd.name)
                result.append(cmd)
        return sorted(result, key=lambda c: c.name)

    def is_slash_command(self, input_text: str) -> bool:
        """Проверить, является ли ввод slash-командой."""
        return input_text.strip().startswith("/")

    def handle(self, input_text: str, ctx: ChatContext) -> Optional[SlashResult]:
        """Обработать slash-команду.

        Args:
            input_text: Ввод пользователя (начинается с /).
            ctx: Контекст чата.

        Returns:
            SlashResult если команда обработана, None если не slash-команда.
        """
        if not self.is_slash_command(input_text):
            return None

        # Парсим команду и аргументы
        text = input_text.strip()[1:]  # Убираем /
        parts = text.split(maxsplit=1)
        cmd_name = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""

        # Ищем команду
        command = self.get_command(cmd_name)
        if not command:
            ctx.console.print(f"[yellow]Unknown command: /{cmd_name}[/yellow]")
            ctx.console.print("[dim]Type /help for available commands[/dim]")
            return SlashResult(action=SlashAction.CONTINUE)

        logger.debug("Executing slash command", command=cmd_name, args=args)

        try:
            result = command.execute(ctx, args)
            return result
        except Exception as e:
            logger.error("Slash command failed", command=cmd_name, error=str(e))
            ctx.console.print(f"[red]Command error: {e}[/red]")
            return SlashResult(action=SlashAction.CONTINUE)


__all__ = ["ChatContext", "SlashCommandHandler"]
