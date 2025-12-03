"""Slash-команды для интерактивного чата.

Классы:
    BaseSlashCommand
        Абстрактный базовый класс для slash-команд.
    SlashCommandHandler
        Обработчик и роутер slash-команд.
    ChatContext
        Контекст чата для передачи в команды.
"""

from semantic_core.cli.chat.slash.base import (
    BaseSlashCommand,
    SlashResult,
    SlashAction,
)
from semantic_core.cli.chat.slash.handler import SlashCommandHandler, ChatContext

__all__ = [
    "BaseSlashCommand",
    "SlashResult",
    "SlashAction",
    "SlashCommandHandler",
    "ChatContext",
]
