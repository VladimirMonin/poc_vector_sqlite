"""Тесты для SlashCommandHandler.

Проверяет:
- Регистрацию команд
- Парсинг ввода
- Роутинг команд
- Обработку неизвестных команд
"""

import pytest
from unittest.mock import MagicMock, create_autospec

from semantic_core.cli.chat.slash import (
    SlashCommandHandler,
    ChatContext,
    SlashResult,
    SlashAction,
    BaseSlashCommand,
)


class DummyCommand(BaseSlashCommand):
    """Тестовая команда."""

    name = "dummy"
    description = "Тестовая команда"
    aliases = ["d", "test"]

    def execute(self, ctx: ChatContext, args: str) -> SlashResult:
        return SlashResult(message=f"Dummy executed with args: {args}")


class ExitCommand(BaseSlashCommand):
    """Команда выхода."""

    name = "exit"
    description = "Выход"

    def execute(self, ctx: ChatContext, args: str) -> SlashResult:
        return SlashResult(action=SlashAction.EXIT, message="Goodbye")


@pytest.fixture
def handler() -> SlashCommandHandler:
    """Создает обработчик с тестовыми командами."""
    h = SlashCommandHandler()
    h.register(DummyCommand())
    h.register(ExitCommand())
    return h


@pytest.fixture
def mock_context() -> ChatContext:
    """Создает мок контекста чата."""
    return ChatContext(
        console=MagicMock(),
        core=MagicMock(),
        rag=MagicMock(),
        llm=MagicMock(),
        history_manager=MagicMock(),
        last_result=None,
        search_mode="hybrid",
        context_chunks=5,
        temperature=0.7,
    )


class TestSlashCommandHandlerRegistration:
    """Тесты регистрации команд."""

    def test_register_command(self):
        """Команда регистрируется по имени."""
        handler = SlashCommandHandler()
        cmd = DummyCommand()
        handler.register(cmd)

        assert handler.get_command("dummy") is cmd

    def test_register_with_aliases(self):
        """Команда доступна по алиасам."""
        handler = SlashCommandHandler()
        cmd = DummyCommand()
        handler.register(cmd)

        assert handler.get_command("d") is cmd
        assert handler.get_command("test") is cmd

    def test_list_commands_unique(self):
        """list_commands возвращает уникальные команды без дублей."""
        handler = SlashCommandHandler()
        handler.register(DummyCommand())
        handler.register(ExitCommand())

        commands = handler.list_commands()
        names = [c.name for c in commands]

        assert len(names) == 2
        assert "dummy" in names
        assert "exit" in names

    def test_list_commands_sorted(self):
        """Команды отсортированы по имени."""
        handler = SlashCommandHandler()
        handler.register(ExitCommand())  # exit идёт раньше
        handler.register(DummyCommand())  # dummy

        commands = handler.list_commands()
        names = [c.name for c in commands]

        assert names == ["dummy", "exit"]


class TestSlashCommandHandlerParsing:
    """Тесты парсинга ввода."""

    def test_is_slash_command_true(self, handler):
        """Распознает slash-команды."""
        assert handler.is_slash_command("/help") is True
        assert handler.is_slash_command("/search query") is True
        assert handler.is_slash_command("  /help  ") is True

    def test_is_slash_command_false(self, handler):
        """Отвергает обычный текст."""
        assert handler.is_slash_command("hello") is False
        assert handler.is_slash_command("help") is False
        assert handler.is_slash_command("") is False

    def test_handle_parses_command_and_args(self, handler, mock_context):
        """handle() корректно парсит команду и аргументы."""
        result = handler.handle("/dummy arg1 arg2", mock_context)

        assert result is not None
        assert "arg1 arg2" in result.message

    def test_handle_command_without_args(self, handler, mock_context):
        """Команда без аргументов получает пустую строку."""
        result = handler.handle("/dummy", mock_context)

        assert result is not None
        assert "args:" in result.message  # "Dummy executed with args: "

    def test_handle_via_alias(self, handler, mock_context):
        """Команда вызывается по алиасу."""
        result = handler.handle("/d some args", mock_context)

        assert result is not None
        assert "some args" in result.message


class TestSlashCommandHandlerRouting:
    """Тесты роутинга команд."""

    def test_handle_unknown_command(self, handler, mock_context):
        """Неизвестная команда возвращает результат без message."""
        result = handler.handle("/unknown", mock_context)

        # Результат должен быть (сообщение выводится в console.print)
        assert result is not None
        assert result.action == SlashAction.CONTINUE
        # Консоль должна была получить сообщение
        mock_context.console.print.assert_called()

    def test_handle_exit_action(self, handler, mock_context):
        """Команда может вернуть действие EXIT."""
        result = handler.handle("/exit", mock_context)

        assert result is not None
        assert result.action == SlashAction.EXIT
        assert result.message == "Goodbye"

    def test_handle_non_slash_returns_none(self, handler, mock_context):
        """Обычный текст не обрабатывается как команда."""
        result = handler.handle("hello world", mock_context)

        # Может вернуть None или результат с message о том что это не команда
        # В нашей реализации handle() не вызывается для не-slash ввода
        # Но если вызвали — вернёт None
        assert result is None or result.action == SlashAction.CONTINUE

    def test_handle_empty_slash(self, handler, mock_context):
        """Пустой слеш обрабатывается как неизвестная команда."""
        result = handler.handle("/", mock_context)

        # Должен вернуть ошибку или пустой результат
        assert result is not None


class TestSlashResult:
    """Тесты SlashResult."""

    def test_default_values(self):
        """По умолчанию — CONTINUE, без сообщения."""
        result = SlashResult()

        assert result.action == SlashAction.CONTINUE
        assert result.message is None
        assert result.add_to_context is None

    def test_with_message(self):
        """Сообщение сохраняется."""
        result = SlashResult(message="Hello")

        assert result.message == "Hello"

    def test_with_action_and_add_to_context(self):
        """action и add_to_context сохраняются."""
        result = SlashResult(
            action=SlashAction.EXIT,
            add_to_context="some context",
        )

        assert result.action == SlashAction.EXIT
        assert result.add_to_context == "some context"


class TestSlashAction:
    """Тесты SlashAction enum."""

    def test_all_actions_exist(self):
        """Все ожидаемые действия существуют."""
        assert SlashAction.CONTINUE is not None
        assert SlashAction.EXIT is not None
        assert SlashAction.CLEAR is not None

    def test_actions_are_distinct(self):
        """Все действия различны."""
        actions = [
            SlashAction.CONTINUE,
            SlashAction.EXIT,
            SlashAction.CLEAR,
        ]
        assert len(set(actions)) == 3
