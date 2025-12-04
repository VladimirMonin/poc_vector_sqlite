"""E2E тесты для chat команды с реальным Gemini API.

Эти тесты используют реальный API и реальную базу данных.
Требуют переменную окружения SEMANTIC_GEMINI_API_KEY.
"""

import os
import pytest
from typer.testing import CliRunner

from semantic_core.cli.app import app


# Пропускаем если нет API ключа
pytestmark = pytest.mark.skipif(
    not os.environ.get("SEMANTIC_GEMINI_API_KEY"),
    reason="SEMANTIC_GEMINI_API_KEY not set"
)


@pytest.fixture
def runner():
    """CLI runner."""
    return CliRunner()


@pytest.fixture
def api_key():
    """API ключ из окружения."""
    return os.environ.get("SEMANTIC_GEMINI_API_KEY")


class TestChatE2E:
    """E2E тесты команды chat."""

    def test_chat_starts_and_shows_welcome(self, runner):
        """Чат запускается и показывает приветствие."""
        result = runner.invoke(app, ["chat"], input="/quit\n")
        
        assert result.exit_code == 0
        assert "Semantic Chat" in result.output
        assert "Модель:" in result.output
        assert "Поиск:" in result.output
        assert "История:" in result.output

    def test_chat_history_enabled_by_default(self, runner):
        """История включена по умолчанию."""
        result = runner.invoke(app, ["chat"], input="/quit\n")
        
        assert result.exit_code == 0
        # Welcome должен показывать "до 10 сообщений"
        assert "до 10 сообщений" in result.output
        # НЕ должно быть "отключена"
        assert "История: отключена" not in result.output

    def test_tokens_command_works(self, runner):
        """Команда /tokens работает и не говорит 'История отключена'."""
        result = runner.invoke(app, ["chat"], input="/tokens\n/quit\n")
        
        assert result.exit_code == 0
        # Должна показать статистику, НЕ "История отключена"
        # Если история работает, будет "Сообщений в истории" или подобное
        output_lower = result.output.lower()
        
        # Это ГЛАВНЫЙ тест - история НЕ должна быть отключена
        assert "история отключена" not in output_lower, \
            f"BUG: /tokens говорит 'История отключена'!\nOutput:\n{result.output}"

    def test_history_command_works(self, runner):
        """Команда /history работает."""
        result = runner.invoke(app, ["chat"], input="/history\n/quit\n")
        
        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert "история отключена" not in output_lower, \
            f"BUG: /history говорит 'История отключена'!\nOutput:\n{result.output}"

    def test_compress_command_works(self, runner):
        """Команда /compress работает."""
        result = runner.invoke(app, ["chat"], input="/compress\n/quit\n")
        
        assert result.exit_code == 0
        output_lower = result.output.lower()
        # Может сказать "недостаточно сообщений" - это ок
        # Но НЕ должна говорить "история отключена"
        assert "история отключена" not in output_lower, \
            f"BUG: /compress говорит 'История отключена'!\nOutput:\n{result.output}"

    def test_quit_shows_single_goodbye(self, runner):
        """Команда /quit показывает одно сообщение прощания."""
        result = runner.invoke(app, ["chat"], input="/quit\n")
        
        assert result.exit_code == 0
        # Считаем сколько раз появляется "До свидания"
        goodbye_count = result.output.count("До свидания")
        assert goodbye_count == 1, \
            f"BUG: 'До свидания' появляется {goodbye_count} раз!\nOutput:\n{result.output}"

    def test_chat_with_real_query(self, runner):
        """Чат отвечает на реальный вопрос."""
        result = runner.invoke(
            app, 
            ["chat"], 
            input="Привет\n/quit\n"
        )
        
        assert result.exit_code == 0
        # Должен быть ответ от Assistant
        assert "Assistant" in result.output or "Привет" in result.output

    def test_history_accumulates_messages(self, runner):
        """История накапливает сообщения."""
        # Задаём 2 вопроса, потом проверяем /tokens
        result = runner.invoke(
            app, 
            ["chat"], 
            input="Привет\nКак дела?\n/tokens\n/quit\n"
        )
        
        assert result.exit_code == 0
        # После 2 вопросов должно быть минимум 4 сообщения (2 user + 2 assistant)
        # /tokens должна показать статистику
        assert "история отключена" not in result.output.lower()
        # Должно быть "Сообщений в истории: 4" (2 вопроса + 2 ответа)
        assert "Сообщений в истории: 4" in result.output, \
            f"Ожидалось 4 сообщения в истории!\nOutput:\n{result.output}"


class TestChatHistoryFlags:
    """Тесты флагов истории."""

    def test_no_history_flag_disables_history(self, runner):
        """Флаг --no-history отключает историю."""
        result = runner.invoke(
            app, 
            ["chat", "--no-history"], 
            input="/tokens\n/quit\n"
        )
        
        assert result.exit_code == 0
        # С --no-history ДОЛЖНА быть "История отключена"
        assert "история отключена" in result.output.lower()

    def test_history_limit_changes_limit(self, runner):
        """Флаг --history-limit меняет лимит."""
        result = runner.invoke(
            app, 
            ["chat", "--history-limit", "5"], 
            input="/quit\n"
        )
        
        assert result.exit_code == 0
        assert "до 5 сообщений" in result.output

    def test_compress_at_enables_compression(self, runner):
        """Флаг --compress-at включает сжатие."""
        result = runner.invoke(
            app, 
            ["chat", "--compress-at", "5000"], 
            input="/quit\n"
        )
        
        assert result.exit_code == 0
        # Должно показать "сжатие при X → Y токенов"
        assert "сжатие при" in result.output


class TestChatSlashCommands:
    """Тесты slash-команд."""

    def test_help_shows_all_commands(self, runner):
        """Команда /help показывает все команды."""
        result = runner.invoke(app, ["chat"], input="/help\n/quit\n")
        
        assert result.exit_code == 0
        assert "/tokens" in result.output
        assert "/history" in result.output
        assert "/compress" in result.output
        assert "/search" in result.output
        assert "/quit" in result.output

    def test_model_command_shows_model(self, runner):
        """Команда /model показывает текущую модель."""
        result = runner.invoke(app, ["chat"], input="/model\n/quit\n")
        
        assert result.exit_code == 0
        assert "gemini" in result.output.lower()

    def test_context_command_shows_chunks(self, runner):
        """Команда /context показывает количество чанков."""
        result = runner.invoke(app, ["chat"], input="/context\n/quit\n")
        
        assert result.exit_code == 0
        assert "чанков" in result.output.lower() or "контекст" in result.output.lower()
