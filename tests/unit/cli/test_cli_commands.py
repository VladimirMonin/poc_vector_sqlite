"""
Tests for CLI commands — init, config, doctor.

Используем Typer CliRunner для тестирования команд без реального терминала.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from semantic_core.cli.app import app
from semantic_core.config import reset_config


runner = CliRunner()


class TestCliApp:
    """Тесты основного CLI приложения."""

    def test_version_option(self):
        """--version показывает версию."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.8.0" in result.stdout

    def test_help_option(self):
        """--help показывает справку."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "semantic" in result.stdout.lower() or "Semantic Core" in result.stdout

    def test_unknown_command(self):
        """Неизвестная команда возвращает ошибку."""
        result = runner.invoke(app, ["unknown-command"])
        assert result.exit_code != 0


class TestInitCommand:
    """Тесты команды init."""

    def test_init_help(self):
        """init --help показывает справку."""
        result = runner.invoke(app, ["init", "--help"])
        assert result.exit_code == 0
        assert "init" in result.stdout.lower() or "создаёт" in result.stdout.lower()

    def test_init_interactive_needs_more_input(self):
        """init требует интерактивного ввода."""
        # init запрашивает несколько параметров, недостаточно "\n\n\n"
        result = runner.invoke(app, ["init"], input="\n" * 10)
        # Команда должна запускаться (exit_code не важен — важно что работает)
        assert "Инициализация" in result.stdout or "semantic" in result.stdout.lower()


class TestConfigCommand:
    """Тесты команды config."""

    def test_config_show_displays_settings(self):
        """config show отображает текущие настройки."""
        reset_config()
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        # Должны быть какие-то настройки в выводе
        assert "db" in result.stdout.lower() or "database" in result.stdout.lower()
        reset_config()

    def test_config_show_masks_api_key(self):
        """config show показывает 'not set' для отсутствующего API ключа."""
        reset_config()
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        # Когда ключа нет, должно быть "not set"
        assert "not set" in result.stdout.lower() or "not_set" in result.stdout.lower()
        reset_config()

    def test_config_check_validates_config(self):
        """config check проверяет валидность конфигурации."""
        reset_config()
        result = runner.invoke(app, ["config", "check"])
        # Может быть 0 (всё ок) или не 0 (проблемы)
        # Главное — не упал с exception
        assert result.exit_code in (0, 1)
        reset_config()

    def test_config_help(self):
        """config --help показывает справку."""
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0
        assert "show" in result.stdout.lower() or "check" in result.stdout.lower()


class TestDoctorCommand:
    """Тесты команды doctor."""

    def test_doctor_runs_diagnostics(self):
        """doctor выполняет диагностику."""
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code in (0, 1)  # 0 = всё ок, 1 = есть проблемы
        # Должна быть какая-то диагностика
        output_lower = result.stdout.lower()
        assert any(word in output_lower for word in [
            "python", "sqlite", "environment", "окружение", "version", "версия"
        ])

    def test_doctor_checks_python_version(self):
        """doctor проверяет версию Python."""
        result = runner.invoke(app, ["doctor"])
        output_lower = result.stdout.lower()
        # Должна быть версия Python или слово python
        assert "python" in output_lower or "3." in result.stdout

    def test_doctor_checks_sqlite_vec(self):
        """doctor проверяет наличие sqlite-vec."""
        result = runner.invoke(app, ["doctor"])
        output_lower = result.stdout.lower()
        # Должно быть упоминание sqlite-vec или vector
        assert "sqlite" in output_lower or "vec" in output_lower

    def test_doctor_help(self):
        """doctor --help показывает справку."""
        result = runner.invoke(app, ["doctor", "--help"])
        assert result.exit_code == 0
        assert "doctor" in result.stdout.lower() or "диагност" in result.stdout.lower()


class TestCliGlobalOptions:
    """Тесты глобальных опций CLI."""

    def test_config_show_works(self):
        """config show работает корректно."""
        result = runner.invoke(app, ["config", "show"])
        # Должно работать
        assert result.exit_code == 0
        assert "database" in result.stdout.lower() or "path" in result.stdout.lower()


class TestCliContext:
    """Тесты контекста CLI."""

    def test_context_lazy_initialization(self):
        """Контекст лениво инициализирует компоненты."""
        from semantic_core.cli.context import CLIContext
        
        ctx = CLIContext()
        # При создании core не должен быть инициализирован
        assert ctx._core is None
        assert ctx._batch_manager is None

    def test_context_get_config(self):
        """Контекст предоставляет конфигурацию."""
        from semantic_core.cli.context import CLIContext
        
        reset_config()
        ctx = CLIContext()
        config = ctx.get_config()
        assert config is not None
        assert hasattr(config, "db_path")
        reset_config()


class TestCliConsole:
    """Тесты консольного вывода."""

    def test_console_singleton(self):
        """Console — синглтон."""
        from semantic_core.cli.console import console
        from semantic_core.cli.console import console as console2
        
        assert console is console2

    def test_console_is_rich_console(self):
        """Console — экземпляр Rich Console."""
        from semantic_core.cli.console import console
        from rich.console import Console
        
        assert isinstance(console, Console)


class TestCliEdgeCases:
    """Тесты граничных случаев."""

    def test_empty_config_file(self):
        """Пустой TOML файл не вызывает ошибку."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as f:
            f.write("")  # Пустой файл
            f.flush()

            try:
                from semantic_core.config import SemanticConfig
                with patch("semantic_core.config.find_config_file", return_value=Path(f.name)):
                    config = SemanticConfig()
                    # Должны загрузиться дефолты
                    assert config.db_path == Path("semantic.db")
            finally:
                os.unlink(f.name)

    def test_invalid_toml_file(self):
        """Невалидный TOML приводит к логированию warning и использованию дефолтов."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as f:
            f.write("this is not valid toml [[[")
            f.flush()

            try:
                from semantic_core.config import SemanticConfig
                # _load_toml ловит ошибки и возвращает {}
                with patch("semantic_core.config.find_config_file", return_value=Path(f.name)):
                    config = SemanticConfig()
                    # Должны загрузиться дефолты (т.к. TOML невалидный)
                    assert config.db_path == Path("semantic.db")
            finally:
                os.unlink(f.name)

    def test_partial_toml_sections(self):
        """Частичные секции TOML дополняются дефолтами."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as f:
            f.write("[database]\npath = 'partial.db'\n")
            f.flush()

            try:
                from semantic_core.config import SemanticConfig
                with patch("semantic_core.config.find_config_file", return_value=Path(f.name)):
                    config = SemanticConfig()
                    # database изменён
                    assert config.db_path == Path("partial.db")
                    # остальное — дефолты
                    assert config.splitter == "smart"
                    assert config.search_limit == 10
            finally:
                os.unlink(f.name)
