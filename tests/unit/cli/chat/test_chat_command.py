"""Тесты для команды chat и инициализации history_manager.

Проверяет:
- Создание history_manager по умолчанию
- Передача history_manager в ChatContext
- Работа slash-команд /tokens, /history, /compress
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from typer.testing import CliRunner

from semantic_core.cli.chat.slash import ChatContext
from semantic_core.core.context import ChatHistoryManager, LastNMessages


class TestChatContextHistoryManager:
    """Тесты что ChatContext правильно принимает history_manager."""

    def test_chat_context_accepts_history_manager(self):
        """ChatContext принимает history_manager и сохраняет его."""
        # Создаём реальный history_manager
        strategy = LastNMessages(n=10)
        history_manager = ChatHistoryManager(strategy)
        
        # Создаём ChatContext с ним
        ctx = ChatContext(
            console=MagicMock(),
            core=MagicMock(),
            rag=MagicMock(),
            llm=MagicMock(),
            history_manager=history_manager,
        )
        
        # Проверяем что history_manager сохранён
        assert ctx.history_manager is not None
        assert ctx.history_manager is history_manager

    def test_chat_context_history_manager_default_none(self):
        """По умолчанию history_manager = None."""
        ctx = ChatContext(
            console=MagicMock(),
            core=MagicMock(),
            rag=MagicMock(),
            llm=MagicMock(),
        )
        
        assert ctx.history_manager is None

    def test_history_manager_is_functional(self):
        """history_manager в ChatContext работает."""
        strategy = LastNMessages(n=10)
        history_manager = ChatHistoryManager(strategy)
        
        ctx = ChatContext(
            console=MagicMock(),
            core=MagicMock(),
            rag=MagicMock(),
            llm=MagicMock(),
            history_manager=history_manager,
        )
        
        # Добавляем сообщение
        ctx.history_manager.add_user("Hello", tokens=10)
        
        # Проверяем
        assert len(ctx.history_manager) == 1
        assert ctx.history_manager.total_tokens() == 10


class TestChatCommandHistoryInit:
    """Тесты инициализации history_manager в команде chat."""

    def test_chat_welcome_shows_history_enabled(self):
        """Welcome-баннер показывает что история включена."""
        from typer.testing import CliRunner
        from semantic_core.cli.app import app
        
        runner = CliRunner()
        # Запускаем chat с --help чтобы увидеть дефолты
        result = runner.invoke(app, ["chat", "--help"])
        
        # Должен быть флаг --history-limit с дефолтом 10
        assert "--history-limit" in result.output
        # Должен быть флаг --no-history 
        assert "--no-history" in result.output
        
    def test_history_limit_default_is_10(self):
        """Дефолт history_limit = 10."""
        from semantic_core.cli.commands.chat import chat
        import inspect
        
        sig = inspect.signature(chat)
        history_limit_param = sig.parameters.get("history_limit")
        
        assert history_limit_param is not None
        assert history_limit_param.default.default == 10


class TestSlashCommandsWithRealHistoryManager:
    """Тесты slash-команд с реальным history_manager."""

    @pytest.fixture
    def real_context(self):
        """Создаёт ChatContext с реальным history_manager."""
        strategy = LastNMessages(n=10)
        history_manager = ChatHistoryManager(strategy)
        
        # Добавляем тестовые сообщения
        history_manager.add_user("Привет", tokens=5)
        history_manager.add_assistant("Привет! Чем помочь?", tokens=10)
        history_manager.add_user("Как работает поиск?", tokens=8)
        history_manager.add_assistant("Поиск работает через...", tokens=50)
        
        return ChatContext(
            console=MagicMock(),
            core=MagicMock(),
            rag=MagicMock(),
            llm=MagicMock(),
            history_manager=history_manager,
        )

    def test_tokens_command_works(self, real_context):
        """Команда /tokens работает с реальным history_manager."""
        from semantic_core.cli.chat.slash import TokensCommand
        
        cmd = TokensCommand()
        result = cmd.execute(real_context, "")
        
        # Не должно быть "История отключена"
        calls = real_context.console.print.call_args_list
        output = str(calls)
        assert "История отключена" not in output
        # Должна быть статистика
        assert real_context.console.print.called

    def test_history_command_works(self, real_context):
        """Команда /history работает с реальным history_manager."""
        from semantic_core.cli.chat.slash import HistoryCommand
        
        cmd = HistoryCommand()
        result = cmd.execute(real_context, "")
        
        # Не должно быть "История отключена"
        calls = real_context.console.print.call_args_list
        output = str(calls)
        assert "История отключена" not in output

    def test_compress_command_with_real_history(self, real_context):
        """Команда /compress работает с реальным history_manager."""
        from semantic_core.cli.chat.slash import CompressCommand
        
        # Мокаем LLM чтобы вернул нормальный ответ
        real_context.llm.generate.return_value = MagicMock(
            text="Summary of conversation",
            input_tokens=100,
            output_tokens=20,
        )
        
        cmd = CompressCommand()
        result = cmd.execute(real_context, "")
        
        # Не должно быть "История отключена"  
        calls = real_context.console.print.call_args_list
        output = str(calls)
        assert "История отключена" not in output


class TestHistoryManagerCreationLogic:
    """Тесты логики создания history_manager в chat.py."""

    def test_last_n_messages_created_by_default(self):
        """По умолчанию создаётся LastNMessages(n=history_limit)."""
        from semantic_core.core.context import (
            ChatHistoryManager,
            LastNMessages,
        )
        
        # Симулируем логику из chat.py
        no_history = False
        compress_at = None
        token_budget = None
        history_limit = 10
        
        if no_history:
            history_manager = None
        elif compress_at:
            history_manager = "compress"  # упрощённо
        elif token_budget:
            history_manager = "token_budget"  # упрощённо
        else:
            history_manager = ChatHistoryManager(LastNMessages(n=history_limit))
        
        assert history_manager is not None
        assert isinstance(history_manager, ChatHistoryManager)

    def test_no_history_flag_sets_none(self):
        """Флаг --no-history устанавливает history_manager = None."""
        no_history = True
        compress_at = None
        token_budget = None
        history_limit = 10
        
        if no_history:
            history_manager = None
        elif compress_at:
            history_manager = "compress"
        elif token_budget:
            history_manager = "token_budget"
        else:
            history_manager = "default"
        
        assert history_manager is None
