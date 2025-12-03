"""Тесты для команд Phase 8.1 — queue, worker.

Тестирует:
- Команду queue status/flush/retry
- Команду worker run-once/start
- Graceful shutdown (signal handling)
"""

from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
import json
import signal

import pytest
from typer.testing import CliRunner

from semantic_core.cli.app import app


runner = CliRunner()


# ============================================================================
#  Тесты queue команды
# ============================================================================


class TestQueueStatusCommand:
    """Тесты команды semantic queue status."""

    def test_queue_status_help(self):
        """--help отображает корректную справку."""
        result = runner.invoke(app, ["queue", "status", "--help"])
        assert result.exit_code == 0
        assert "status" in result.stdout.lower() or "Показать" in result.stdout

    @patch("semantic_core.cli.commands.queue._get_text_stats")
    @patch("semantic_core.cli.commands.queue._get_media_stats")
    @patch("semantic_core.cli.context.CLIContext.get_core")
    def test_queue_status_displays_stats(
        self, mock_core, mock_media_stats, mock_text_stats
    ):
        """status показывает статистику очередей."""
        mock_core.return_value = MagicMock()
        mock_text_stats.return_value = {
            "pending": 5,
            "processing": 2,
            "ready": 100,
            "failed": 1,
        }
        mock_media_stats.return_value = {
            "pending": 3,
            "processing": 1,
            "completed": 50,
            "failed": 0,
        }

        result = runner.invoke(app, ["queue", "status"])
        assert result.exit_code == 0
        assert "Queue Status" in result.stdout
        # Проверяем что отображаются обе таблицы
        assert "Text Embeddings" in result.stdout
        assert "Media Analysis" in result.stdout

    @patch("semantic_core.cli.commands.queue._get_text_stats")
    @patch("semantic_core.cli.commands.queue._get_media_stats")
    @patch("semantic_core.cli.context.CLIContext.get_core")
    def test_queue_status_json_output(
        self, mock_core, mock_media_stats, mock_text_stats
    ):
        """--json выводит JSON формат."""
        mock_core.return_value = MagicMock()
        mock_text_stats.return_value = {
            "pending": 10,
            "processing": 0,
            "ready": 50,
            "failed": 0,
        }
        mock_media_stats.return_value = {
            "pending": 0,
            "processing": 0,
            "completed": 20,
            "failed": 0,
        }

        result = runner.invoke(app, ["--json", "queue", "status"])
        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert "text_embeddings" in data
        assert "media" in data
        assert data["text_embeddings"]["pending"] == 10
        assert data["media"]["completed"] == 20

    @patch("semantic_core.cli.commands.queue._get_text_stats")
    @patch("semantic_core.cli.commands.queue._get_media_stats")
    @patch("semantic_core.cli.context.CLIContext.get_core")
    def test_queue_status_shows_tip_when_pending(
        self, mock_core, mock_media_stats, mock_text_stats
    ):
        """Показывает подсказку если есть pending задачи."""
        mock_core.return_value = MagicMock()
        mock_text_stats.return_value = {
            "pending": 5,
            "processing": 0,
            "ready": 0,
            "failed": 0,
        }
        mock_media_stats.return_value = {
            "pending": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
        }

        result = runner.invoke(app, ["queue", "status"])
        assert result.exit_code == 0
        assert "worker run-once" in result.stdout


class TestQueueFlushCommand:
    """Тесты команды semantic queue flush."""

    def test_queue_flush_help(self):
        """--help отображает корректную справку."""
        result = runner.invoke(app, ["queue", "flush", "--help"])
        assert result.exit_code == 0
        assert "--min-size" in result.stdout or "--force" in result.stdout

    @patch("semantic_core.cli.context.CLIContext.get_core")
    def test_queue_flush_without_batch_manager(self, mock_core):
        """Ошибка если BatchManager не настроен."""
        core = MagicMock()
        core.batch_manager = None
        mock_core.return_value = core

        result = runner.invoke(app, ["queue", "flush"])
        assert result.exit_code == 1
        assert "BatchManager" in result.stdout

    @patch("semantic_core.cli.commands.queue._get_text_stats")
    @patch("semantic_core.cli.context.CLIContext.get_core")
    def test_queue_flush_creates_batch(self, mock_core, mock_text_stats):
        """flush создаёт batch и показывает результат."""
        core = MagicMock()
        core.batch_manager.flush_queue.return_value = "abc12345-6789-uuid"
        mock_core.return_value = core
        mock_text_stats.return_value = {"pending": 0, "processing": 0}

        result = runner.invoke(app, ["queue", "flush"])
        assert result.exit_code == 0
        assert "Created batch" in result.stdout
        assert "abc12345" in result.stdout

    @patch("semantic_core.cli.context.CLIContext.get_core")
    def test_queue_flush_no_pending_chunks(self, mock_core):
        """Сообщение если нет pending чанков."""
        core = MagicMock()
        core.batch_manager.flush_queue.return_value = None
        mock_core.return_value = core

        result = runner.invoke(app, ["queue", "flush"])
        assert result.exit_code == 0
        assert "No pending chunks" in result.stdout


class TestQueueRetryCommand:
    """Тесты команды semantic queue retry."""

    def test_queue_retry_help(self):
        """--help отображает корректную справку."""
        result = runner.invoke(app, ["queue", "retry", "--help"])
        assert result.exit_code == 0
        assert "--type" in result.stdout

    @patch("semantic_core.cli.context.CLIContext.get_core")
    def test_queue_retry_invalid_type(self, mock_core):
        """Ошибка для неверного типа."""
        mock_core.return_value = MagicMock()

        result = runner.invoke(app, ["queue", "retry", "--type", "invalid"])
        assert result.exit_code == 1
        assert "invalid" in result.stdout.lower()

    @patch("semantic_core.infrastructure.storage.peewee.models.ChunkModel")
    @patch("semantic_core.infrastructure.storage.peewee.models.MediaTaskModel")
    @patch("semantic_core.cli.context.CLIContext.get_core")
    def test_queue_retry_resets_failed_tasks(
        self, mock_core, mock_media_model, mock_chunk_model
    ):
        """retry сбрасывает failed задачи."""
        mock_core.return_value = MagicMock()
        mock_chunk_model.update.return_value.where.return_value.execute.return_value = 2
        mock_media_model.update.return_value.where.return_value.execute.return_value = 1

        result = runner.invoke(app, ["queue", "retry"])
        assert result.exit_code == 0
        assert "PENDING" in result.stdout

    @patch("semantic_core.infrastructure.storage.peewee.models.ChunkModel")
    @patch("semantic_core.infrastructure.storage.peewee.models.MediaTaskModel")
    @patch("semantic_core.cli.context.CLIContext.get_core")
    def test_queue_retry_text_only(self, mock_core, mock_media_model, mock_chunk_model):
        """--type text ретраит только text chunks."""
        mock_core.return_value = MagicMock()
        mock_chunk_model.update.return_value.where.return_value.execute.return_value = 3
        mock_media_model.update.return_value.where.return_value.execute.return_value = 0

        result = runner.invoke(app, ["queue", "retry", "--type", "text"])
        assert result.exit_code == 0
        # Media update не должен вызываться
        mock_media_model.update.assert_not_called()


# ============================================================================
#  Тесты worker команды
# ============================================================================


class TestWorkerRunOnceCommand:
    """Тесты команды semantic worker run-once."""

    def test_worker_run_once_help(self):
        """--help отображает корректную справку."""
        result = runner.invoke(app, ["worker", "run-once", "--help"])
        assert result.exit_code == 0
        assert "--max-tasks" in result.stdout

    @patch("semantic_core.cli.commands.worker._process_media_queue")
    @patch("semantic_core.cli.commands.worker._sync_batch_statuses")
    @patch("semantic_core.infrastructure.storage.peewee.models.MediaTaskModel")
    @patch("semantic_core.cli.context.CLIContext.get_core")
    def test_worker_run_once_processes_queue(
        self, mock_core, mock_media_model, mock_sync, mock_process
    ):
        """run-once обрабатывает очередь."""
        mock_core.return_value = MagicMock()
        mock_sync.return_value = {"batch1": "COMPLETED"}
        mock_process.return_value = 5
        mock_media_model.select.return_value.where.return_value.count.return_value = 0

        result = runner.invoke(app, ["worker", "run-once"])
        assert result.exit_code == 0
        assert "one-time processing" in result.stdout.lower()

    @patch("semantic_core.cli.commands.worker._process_media_queue")
    @patch("semantic_core.cli.commands.worker._sync_batch_statuses")
    @patch("semantic_core.infrastructure.storage.peewee.models.MediaTaskModel")
    @patch("semantic_core.cli.context.CLIContext.get_core")
    def test_worker_run_once_json_output(
        self, mock_core, mock_media_model, mock_sync, mock_process
    ):
        """--json выводит JSON формат."""
        mock_core.return_value = MagicMock()
        mock_sync.return_value = {}
        mock_process.return_value = 3
        mock_media_model.select.return_value.where.return_value.count.return_value = 2

        result = runner.invoke(app, ["--json", "worker", "run-once"])
        assert result.exit_code == 0

        # Извлекаем JSON из вывода (может быть другой текст)
        import re

        json_match = re.search(r"\{.*\}", result.stdout, re.DOTALL)
        assert json_match is not None, f"No JSON found in output: {result.stdout}"
        data = json.loads(json_match.group())
        assert data["success"] is True
        assert data["media_processed"] == 3
        assert data["remaining"] == 2

    @patch("semantic_core.cli.commands.worker._process_media_queue")
    @patch("semantic_core.cli.commands.worker._sync_batch_statuses")
    @patch("semantic_core.infrastructure.storage.peewee.models.MediaTaskModel")
    @patch("semantic_core.cli.context.CLIContext.get_core")
    def test_worker_run_once_respects_max_tasks(
        self, mock_core, mock_media_model, mock_sync, mock_process
    ):
        """--max-tasks передаётся в process_media_queue."""
        mock_core.return_value = MagicMock()
        mock_sync.return_value = {}
        mock_process.return_value = 10
        mock_media_model.select.return_value.where.return_value.count.return_value = 0

        result = runner.invoke(app, ["worker", "run-once", "--max-tasks", "25"])
        assert result.exit_code == 0
        mock_process.assert_called_once()
        # Проверяем что max_tasks=25 передан
        args, kwargs = mock_process.call_args
        assert kwargs.get("max_tasks") == 25 or (len(args) >= 2 and args[1] == 25)


class TestWorkerStartCommand:
    """Тесты команды semantic worker start."""

    def test_worker_start_help(self):
        """--help отображает корректную справку."""
        result = runner.invoke(app, ["worker", "start", "--help"])
        assert result.exit_code == 0
        assert "--batch-size" in result.stdout
        assert "--poll-interval" in result.stdout

    def test_worker_start_rejects_json_output(self):
        """--json не поддерживается для start."""
        result = runner.invoke(app, ["--json", "worker", "start"])
        assert result.exit_code == 1
        assert "not supported" in result.stdout.lower()

    @patch("semantic_core.cli.commands.worker._process_media_queue")
    @patch("semantic_core.cli.commands.worker._sync_batch_statuses")
    @patch("semantic_core.infrastructure.storage.peewee.models.MediaTaskModel")
    @patch("semantic_core.cli.context.CLIContext.get_core")
    @patch("time.sleep")
    @patch("signal.signal")
    def test_worker_start_registers_signal_handler(
        self,
        mock_signal,
        mock_sleep,
        mock_core,
        mock_media_model,
        mock_sync,
        mock_process,
    ):
        """start регистрирует SIGINT handler."""
        mock_core.return_value = MagicMock()
        mock_sync.return_value = {}
        mock_process.return_value = 0
        mock_media_model.select.return_value.where.return_value.count.return_value = 0

        # Симулируем остановку после первой итерации
        call_count = [0]

        def stop_after_one(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] >= 1:
                # Симулируем получение SIGINT
                raise KeyboardInterrupt()

        mock_sleep.side_effect = stop_after_one

        result = runner.invoke(app, ["worker", "start"])
        # Ожидаем что signal.signal был вызван
        assert mock_signal.called


# ============================================================================
#  Тесты EMOJI_MAP
# ============================================================================


class TestEmojiMapUpdates:
    """Тесты обновлений EMOJI_MAP для Phase 8.1."""

    def test_cli_emoji_exists(self):
        """cli паттерн имеет эмодзи."""
        from semantic_core.utils.logger.formatters import EMOJI_MAP

        assert "cli" in EMOJI_MAP
        assert EMOJI_MAP["cli"] == "🖥️"

    def test_worker_emoji_exists(self):
        """worker паттерн имеет эмодзи."""
        from semantic_core.utils.logger.formatters import EMOJI_MAP

        assert "worker" in EMOJI_MAP
        assert EMOJI_MAP["worker"] == "👷"

    def test_commands_emoji_exists(self):
        """commands паттерн имеет эмодзи."""
        from semantic_core.utils.logger.formatters import EMOJI_MAP

        assert "commands" in EMOJI_MAP
        assert EMOJI_MAP["commands"] == "🖥️"

    def test_get_module_emoji_for_cli(self):
        """get_module_emoji возвращает правильные эмодзи для CLI модулей."""
        from semantic_core.utils.logger.formatters import get_module_emoji

        # queue модуль использует 📦 (очередь более специфична чем CLI)
        assert get_module_emoji("semantic_core.cli.commands.queue") == "📦"
        # worker модуль использует 👷
        assert get_module_emoji("semantic_core.cli.commands.worker") == "👷"
        # commands использует 🖥️ для общих CLI команд
        assert get_module_emoji("semantic_core.cli.commands.docs") == "🖥️"


# ============================================================================
#  Интеграционные тесты с изолированной БД
# ============================================================================


class TestQueueIntegration:
    """Интеграционные тесты queue с изолированной БД."""

    @pytest.fixture
    def setup_db(self, tmp_path: Path):
        """Создаёт изолированную БД для тестов."""
        db_path = tmp_path / "test.db"

        # Создаём минимальный semantic.toml
        config_path = tmp_path / "semantic.toml"
        config_path.write_text(f"""
[database]
path = "{db_path}"
""")

        return tmp_path, db_path

    @pytest.mark.skip(reason="Requires full DB initialization")
    def test_queue_status_empty_db(self, tmp_path: Path):
        """queue status работает с пустой БД."""
        pass


# ============================================================================
#  Тесты вспомогательных функций
# ============================================================================


class TestQueueHelpers:
    """Тесты вспомогательных функций queue.py."""

    @patch("semantic_core.infrastructure.storage.peewee.models.ChunkModel")
    def test_get_text_stats(self, mock_chunk_model):
        """_get_text_stats возвращает корректную статистику."""
        from semantic_core.cli.commands.queue import _get_text_stats

        # Настраиваем мок для возврата разных значений
        mock_chunk_model.select.return_value.where.return_value.count.side_effect = [
            10,
            5,
            100,
            2,
        ]

        stats = _get_text_stats()

        assert "pending" in stats
        assert "processing" in stats
        assert "ready" in stats
        assert "failed" in stats

    @patch("semantic_core.infrastructure.storage.peewee.models.MediaTaskModel")
    def test_get_media_stats(self, mock_media_model):
        """_get_media_stats возвращает корректную статистику."""
        from semantic_core.cli.commands.queue import _get_media_stats

        mock_media_model.select.return_value.where.return_value.count.side_effect = [
            3,
            1,
            50,
            0,
        ]

        stats = _get_media_stats()

        assert "pending" in stats
        assert "processing" in stats
        assert "completed" in stats
        assert "failed" in stats


class TestWorkerHelpers:
    """Тесты вспомогательных функций worker.py."""

    def test_sync_batch_statuses_without_batch_manager(self):
        """_sync_batch_statuses возвращает {} если BatchManager отсутствует."""
        from semantic_core.cli.commands.worker import _sync_batch_statuses

        core = MagicMock()
        core.batch_manager = None

        result = _sync_batch_statuses(core)
        assert result == {}

    def test_sync_batch_statuses_with_batch_manager(self):
        """_sync_batch_statuses вызывает sync_status."""
        from semantic_core.cli.commands.worker import _sync_batch_statuses

        core = MagicMock()
        core.batch_manager.sync_status.return_value = {"batch1": "COMPLETED"}

        result = _sync_batch_statuses(core)
        assert result == {"batch1": "COMPLETED"}
        core.batch_manager.sync_status.assert_called_once()

    def test_process_media_queue_calls_core(self):
        """_process_media_queue вызывает core.process_media_queue."""
        from semantic_core.cli.commands.worker import _process_media_queue

        core = MagicMock()
        core.process_media_queue.return_value = 5

        result = _process_media_queue(core, max_tasks=10)
        assert result == 5
        core.process_media_queue.assert_called_once_with(max_tasks=10)

    def test_process_media_queue_handles_errors(self):
        """_process_media_queue возвращает 0 при ошибке."""
        from semantic_core.cli.commands.worker import _process_media_queue

        core = MagicMock()
        core.process_media_queue.side_effect = Exception("API Error")

        result = _process_media_queue(core, max_tasks=10)
        assert result == 0
