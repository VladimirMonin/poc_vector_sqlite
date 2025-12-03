"""Тесты для базовых slash-команд.

Проверяет:
- HelpCommand
- ClearCommand
- QuitCommand
- TokensCommand
- HistoryCommand
- CompressCommand
"""

import pytest
from unittest.mock import MagicMock, create_autospec, PropertyMock
from rich.console import Console

from semantic_core.cli.chat.slash import (
    SlashCommandHandler,
    ChatContext,
    SlashResult,
    SlashAction,
    HelpCommand,
    ClearCommand,
    QuitCommand,
    TokensCommand,
    HistoryCommand,
    CompressCommand,
)


@pytest.fixture
def mock_console() -> MagicMock:
    """Мок консоли Rich."""
    return MagicMock(spec=Console)


@pytest.fixture
def mock_history_manager():
    """Мок менеджера истории."""
    mock = MagicMock()
    mock.__len__ = MagicMock(return_value=5)
    mock.total_tokens.return_value = 1500
    mock.has_summary = False
    mock.get_history.return_value = [
        MagicMock(role="user", content="Hello"),
        MagicMock(role="assistant", content="Hi there!"),
    ]
    return mock


@pytest.fixture
def mock_context(mock_console, mock_history_manager) -> ChatContext:
    """Создает мок контекста чата."""
    return ChatContext(
        console=mock_console,
        core=MagicMock(),
        rag=MagicMock(),
        llm=MagicMock(),
        history_manager=mock_history_manager,
        last_result=None,
        search_mode="hybrid",
        context_chunks=5,
        temperature=0.7,
    )


class TestHelpCommand:
    """Тесты для /help."""

    def test_name_and_aliases(self):
        """Проверяет имя и алиасы."""
        handler = SlashCommandHandler()
        cmd = HelpCommand(handler)

        assert cmd.name == "help"
        assert "h" in cmd.aliases
        assert "?" in cmd.aliases

    def test_execute_prints_table(self, mock_context):
        """execute() выводит таблицу команд."""
        handler = SlashCommandHandler()
        handler.register(HelpCommand(handler))
        handler.register(QuitCommand())

        cmd = HelpCommand(handler)
        result = cmd.execute(mock_context, "")

        # Должен вызвать console.print с таблицей
        mock_context.console.print.assert_called()
        assert result.action == SlashAction.CONTINUE

    def test_lists_all_registered_commands(self, mock_context):
        """Показывает все зарегистрированные команды."""
        handler = SlashCommandHandler()
        handler.register(HelpCommand(handler))
        handler.register(QuitCommand())
        handler.register(ClearCommand())

        cmd = HelpCommand(handler)
        cmd.execute(mock_context, "")

        # Проверяем что print был вызван (таблица была выведена)
        assert mock_context.console.print.called


class TestClearCommand:
    """Тесты для /clear."""

    def test_name_and_aliases(self):
        """Проверяет имя и алиасы."""
        cmd = ClearCommand()

        assert cmd.name == "clear"
        assert "cls" in cmd.aliases

    def test_returns_clear_action(self, mock_context):
        """Возвращает действие CLEAR."""
        cmd = ClearCommand()
        result = cmd.execute(mock_context, "")

        assert result.action == SlashAction.CLEAR


class TestQuitCommand:
    """Тесты для /quit."""

    def test_name_and_aliases(self):
        """Проверяет имя и алиасы."""
        cmd = QuitCommand()

        assert cmd.name == "quit"
        assert "q" in cmd.aliases
        assert "exit" in cmd.aliases

    def test_returns_exit_action(self, mock_context):
        """Возвращает действие EXIT."""
        cmd = QuitCommand()
        result = cmd.execute(mock_context, "")

        assert result.action == SlashAction.EXIT


class TestTokensCommand:
    """Тесты для /tokens."""

    def test_name(self):
        """Проверяет имя."""
        cmd = TokensCommand()
        assert cmd.name == "tokens"

    def test_shows_token_stats(self, mock_context):
        """Показывает статистику токенов."""
        cmd = TokensCommand()
        result = cmd.execute(mock_context, "")

        # Должен вызвать print с таблицей
        mock_context.console.print.assert_called()
        assert result.action == SlashAction.CONTINUE

    def test_handles_no_history_manager(self, mock_console):
        """Обрабатывает случай без менеджера истории."""
        ctx = ChatContext(
            console=mock_console,
            core=MagicMock(),
            rag=MagicMock(),
            llm=MagicMock(),
            history_manager=None,
            last_result=None,
        )

        cmd = TokensCommand()
        result = cmd.execute(ctx, "")

        # Не должен упасть
        assert result.action == SlashAction.CONTINUE


class TestHistoryCommand:
    """Тесты для /history."""

    def test_name(self):
        """Проверяет имя."""
        cmd = HistoryCommand()
        assert cmd.name == "history"

    def test_shows_history(self, mock_context):
        """Показывает историю."""
        cmd = HistoryCommand()
        result = cmd.execute(mock_context, "")

        mock_context.console.print.assert_called()
        assert result.action == SlashAction.CONTINUE

    def test_handles_no_history_manager(self, mock_console):
        """Обрабатывает случай без истории."""
        ctx = ChatContext(
            console=mock_console,
            core=MagicMock(),
            rag=MagicMock(),
            llm=MagicMock(),
            history_manager=None,
            last_result=None,
        )

        cmd = HistoryCommand()
        result = cmd.execute(ctx, "")

        # Не должен упасть
        assert result.action == SlashAction.CONTINUE

    def test_handles_empty_history(self, mock_console):
        """Обрабатывает пустую историю."""
        mock_history = MagicMock()
        mock_history.get_history.return_value = []

        ctx = ChatContext(
            console=mock_console,
            core=MagicMock(),
            rag=MagicMock(),
            llm=MagicMock(),
            history_manager=mock_history,
            last_result=None,
        )

        cmd = HistoryCommand()
        result = cmd.execute(ctx, "")

        assert result.action == SlashAction.CONTINUE


class TestCompressCommand:
    """Тесты для /compress."""

    def test_name(self):
        """Проверяет имя."""
        cmd = CompressCommand()
        assert cmd.name == "compress"

    def test_handles_no_history_manager(self, mock_console):
        """Обрабатывает случай без менеджера истории."""
        ctx = ChatContext(
            console=mock_console,
            core=MagicMock(),
            rag=MagicMock(),
            llm=MagicMock(),
            history_manager=None,
            last_result=None,
        )

        cmd = CompressCommand()
        result = cmd.execute(ctx, "")

        # Должен вывести сообщение об ошибке или вернуть message
        # Не должен упасть
        assert result.action == SlashAction.CONTINUE

    def test_compress_requires_compress_method(self, mock_context):
        """Сжатие требует метод compress."""
        # Если history_manager не имеет compress — сообщаем об этом
        mock_context.history_manager.compress = MagicMock()

        cmd = CompressCommand()
        result = cmd.execute(mock_context, "")

        # Либо вызовет compress, либо сообщит что недоступно
        assert result.action == SlashAction.CONTINUE
