"""Базовый класс для slash-команд.

Классы:
    SlashAction
        Enum действий после выполнения команды.
    SlashResult
        Результат выполнения команды.
    BaseSlashCommand
        Абстрактный базовый класс для slash-команд.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from semantic_core.cli.chat.slash.handler import ChatContext


class SlashAction(Enum):
    """Действие после выполнения команды."""

    CONTINUE = auto()  # Продолжить REPL
    EXIT = auto()  # Выход из чата
    CLEAR = auto()  # Очистить экран и продолжить


@dataclass
class SlashResult:
    """Результат выполнения slash-команды.

    Attributes:
        action: Действие после выполнения.
        message: Сообщение для вывода (опционально).
        add_to_context: Текст для добавления в контекст LLM.
    """

    action: SlashAction = SlashAction.CONTINUE
    message: Optional[str] = None
    add_to_context: Optional[str] = None


class BaseSlashCommand(ABC):
    """Абстрактный базовый класс для slash-команд.

    Каждая команда должна определить:
    - name: имя команды (без /)
    - description: краткое описание
    - execute(): логика выполнения

    Опционально:
    - aliases: альтернативные имена
    - usage: примеры использования

    Example:
        >>> class HelpCommand(BaseSlashCommand):
        ...     name = "help"
        ...     description = "Show available commands"
        ...     aliases = ["h", "?"]
        ...
        ...     def execute(self, ctx, args):
        ...         # Показать справку
        ...         return SlashResult()
    """

    name: str
    description: str
    aliases: list[str] = []
    usage: Optional[str] = None

    @abstractmethod
    def execute(self, ctx: "ChatContext", args: str) -> SlashResult:
        """Выполнить команду.

        Args:
            ctx: Контекст чата (доступ к core, rag, history и т.д.).
            args: Аргументы команды (строка после имени).

        Returns:
            SlashResult с действием и опциональным сообщением.
        """
        pass

    @property
    def help_text(self) -> str:
        """Полный текст справки для команды."""
        text = f"/{self.name}"
        if self.aliases:
            text += f" ({', '.join('/' + a for a in self.aliases)})"
        text += f" — {self.description}"
        if self.usage:
            text += f"\n    {self.usage}"
        return text


__all__ = ["SlashAction", "SlashResult", "BaseSlashCommand"]
