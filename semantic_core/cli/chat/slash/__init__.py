"""Slash-команды для интерактивного чата.

Классы:
    BaseSlashCommand
        Абстрактный базовый класс для slash-команд.
    SlashCommandHandler
        Обработчик и роутер slash-команд.
    ChatContext
        Контекст чата для передачи в команды.

Команды:
    Basic: HelpCommand, ClearCommand, QuitCommand, TokensCommand,
           HistoryCommand, CompressCommand
    Search: SearchCommand, SearchModeCommand, SourcesCommand, SourceCommand
    Settings: ModelCommand, ContextCommand
"""

from semantic_core.cli.chat.slash.base import (
    BaseSlashCommand,
    SlashResult,
    SlashAction,
)
from semantic_core.cli.chat.slash.handler import SlashCommandHandler, ChatContext

# Basic commands
from semantic_core.cli.chat.slash.basic import (
    HelpCommand,
    ClearCommand,
    QuitCommand,
    TokensCommand,
    HistoryCommand,
    CompressCommand,
)

# Search commands
from semantic_core.cli.chat.slash.search import (
    SearchCommand,
    SearchModeCommand,
    SourcesCommand,
    SourceCommand,
)

# Settings commands
from semantic_core.cli.chat.slash.settings import (
    ModelCommand,
    ContextCommand,
)

__all__ = [
    # Base
    "BaseSlashCommand",
    "SlashResult",
    "SlashAction",
    "SlashCommandHandler",
    "ChatContext",
    # Basic commands
    "HelpCommand",
    "ClearCommand",
    "QuitCommand",
    "TokensCommand",
    "HistoryCommand",
    "CompressCommand",
    # Search commands
    "SearchCommand",
    "SearchModeCommand",
    "SourcesCommand",
    "SourceCommand",
    # Settings commands
    "ModelCommand",
    "ContextCommand",
]
