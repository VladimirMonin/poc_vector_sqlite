"""Тесты для секции Providers в команде doctor (Phase 15.5).

Проверяет:
- Отображение доступных/недоступных провайдеров
- Install hints в verbose-режиме
- JSON вывод
"""

import pytest
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner

from semantic_core.cli.app import app


runner = CliRunner()


class TestDoctorProviders:
    """Тесты для секции Providers в doctor."""

    @patch("semantic_core.cli.commands.doctor_cmd.get_available_providers")
    @patch("semantic_core.cli.commands.doctor_cmd.get_cli_context")
    def test_shows_available_providers(
        self, mock_get_cli_context, mock_get_available_providers
    ):
        """Doctor показывает доступные провайдеры."""
        # Arrange
        mock_ctx = MagicMock()
        mock_ctx.get_config.return_value = MagicMock(
            db_path=MagicMock(exists=lambda: False)
        )
        mock_ctx.json_output = False
        mock_get_cli_context.return_value = mock_ctx

        mock_get_available_providers.return_value = {
            "google": True,
            "openai": False,
            "local_embeddings": False,
            "local_whisper": False,
            "media": True,
        }

        # Act
        result = runner.invoke(app, ["doctor"])

        # Assert
        assert result.exit_code == 0
        assert "Providers:" in result.stdout
        assert "Google: installed" in result.stdout
        assert "Openai: not installed" in result.stdout
        assert "Media: installed" in result.stdout

    @patch("semantic_core.cli.commands.doctor_cmd.get_available_providers")
    @patch("semantic_core.cli.commands.doctor_cmd.get_install_hint")
    @patch("semantic_core.cli.commands.doctor_cmd.get_cli_context")
    def test_shows_install_hints_in_verbose_mode(
        self,
        mock_get_cli_context,
        mock_get_install_hint,
        mock_get_available_providers,
    ):
        """Doctor показывает install hints в verbose-режиме."""
        # Arrange
        mock_ctx = MagicMock()
        mock_ctx.get_config.return_value = MagicMock(
            db_path=MagicMock(exists=lambda: False)
        )
        mock_ctx.json_output = False
        mock_get_cli_context.return_value = mock_ctx

        mock_get_available_providers.return_value = {
            "google": True,
            "openai": False,
            "local_embeddings": False,
            "local_whisper": False,
            "media": True,
        }

        mock_get_install_hint.return_value = "pip install poc-vector-sqlite[openai]"

        # Act
        result = runner.invoke(app, ["doctor", "--verbose"])

        # Assert
        assert result.exit_code == 0
        assert "📦 Установка дополнительных провайдеров:" in result.stdout
        assert "pip install" in result.stdout

    @patch("semantic_core.cli.commands.doctor_cmd.get_available_providers")
    @patch("semantic_core.cli.commands.doctor_cmd.get_cli_context")
    def test_all_providers_installed_no_warnings(
        self, mock_get_cli_context, mock_get_available_providers
    ):
        """Когда все провайдеры установлены — нет warnings."""
        # Arrange
        mock_ctx = MagicMock()
        mock_ctx.get_config.return_value = MagicMock(
            db_path=MagicMock(exists=lambda: False)
        )
        mock_ctx.json_output = False
        mock_get_cli_context.return_value = mock_ctx

        # Все провайдеры доступны
        mock_get_available_providers.return_value = {
            "google": True,
            "openai": True,
            "local_embeddings": True,
            "local_whisper": True,
            "media": True,
        }

        # Act
        result = runner.invoke(app, ["doctor"])

        # Assert
        assert result.exit_code == 0
        assert "✅ Google: installed" in result.stdout
        assert "✅ Openai: installed" in result.stdout
        assert "✅ Media: installed" in result.stdout
        # Не должно быть install hints
        assert "📦 Установка дополнительных провайдеров:" not in result.stdout
