"""Unit-тесты для команды reanalyze CLI."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typer.testing import CliRunner
from peewee import DoesNotExist

from semantic_core.cli.app import app
from semantic_core.domain import MediaType


runner = CliRunner()


@pytest.fixture
def mock_document():
    """Mock документ после reanalyze."""
    doc = Mock()
    doc.id = "doc-abc123"
    doc.media_type = MediaType.AUDIO
    doc.chunks = [Mock(), Mock(), Mock()]  # 3 chunks
    return doc


@pytest.fixture
def mock_media_details():
    """Mock MediaDetails."""
    details = Mock()
    details.summary = "Test summary"
    details.full_transcript = "Test transcript " * 50  # > 300 chars
    details.full_ocr_text = ""
    details.has_transcript = True
    details.has_ocr = False
    details.has_timeline = False
    details.timeline = []
    details.total_chunks = 3
    details.keywords = ["test", "audio"]
    return details


class TestReanalyzeCommand:
    """Тесты команды semantic reanalyze."""

    def test_reanalyze_help(self):
        """Справка команды отображается."""
        result = runner.invoke(app, ["reanalyze", "--help"])
        assert result.exit_code == 0
        assert "Повторный анализ медиа-файлов" in result.stdout
        assert "--prompt" in result.stdout
        assert "--show-details" in result.stdout
        assert "--force" in result.stdout

    @patch("semantic_core.cli.app.get_cli_context")
    def test_reanalyze_requires_confirmation_by_default(self, mock_get_context):
        """По умолчанию требуется подтверждение."""
        mock_core = Mock()
        mock_ctx = Mock()
        mock_ctx.get_core.return_value = mock_core
        mock_get_context.return_value = mock_ctx

        # Пользователь отказывается
        result = runner.invoke(
            app, ["reanalyze", "doc-123"], input="n\n"
        )

        assert result.exit_code == 0
        assert "Операция отменена" in result.stdout
        mock_core.reanalyze.assert_not_called()

    @patch("semantic_core.cli.app.get_cli_context")
    def test_reanalyze_success_with_force(self, mock_get_context, mock_document):
        """Успешный reanalyze с флагом --force."""
        mock_core = Mock()
        mock_core.reanalyze.return_value = mock_document
        mock_ctx = Mock()
        mock_ctx.get_core.return_value = mock_core
        mock_get_context.return_value = mock_ctx

        result = runner.invoke(app, ["reanalyze", "doc-abc123", "--force"])

        assert result.exit_code == 0
        assert "✅ Успешно обновлён!" in result.stdout
        assert "doc-abc123" in result.stdout
        assert "Chunks: 3" in result.stdout
        mock_core.reanalyze.assert_called_once_with("doc-abc123", custom_instructions=None)

    @patch("semantic_core.cli.app.get_cli_context")
    def test_reanalyze_success_with_confirmation(self, mock_get_context, mock_document):
        """Успешный reanalyze после подтверждения."""
        mock_core = Mock()
        mock_core.reanalyze.return_value = mock_document
        mock_ctx = Mock()
        mock_ctx.get_core.return_value = mock_core
        mock_get_context.return_value = mock_ctx

        # Пользователь подтверждает
        result = runner.invoke(
            app, ["reanalyze", "doc-abc123"], input="y\n"
        )

        assert result.exit_code == 0
        assert "✅ Успешно обновлён!" in result.stdout
        mock_core.reanalyze.assert_called_once()

    @patch("semantic_core.cli.app.get_cli_context")
    def test_reanalyze_with_custom_prompt(self, mock_get_context, mock_document):
        """Reanalyze с кастомным промптом."""
        mock_core = Mock()
        mock_core.reanalyze.return_value = mock_document
        mock_ctx = Mock()
        mock_ctx.get_core.return_value = mock_core
        mock_get_context.return_value = mock_ctx

        result = runner.invoke(
            app,
            ["reanalyze", "doc-abc123", "--prompt", "Extract medical terms", "--force"],
        )

        assert result.exit_code == 0
        mock_core.reanalyze.assert_called_once_with(
            "doc-abc123", custom_instructions="Extract medical terms"
        )

    @patch("semantic_core.cli.app.get_cli_context")
    def test_reanalyze_document_not_found(self, mock_get_context):
        """Документ не найден (DoesNotExist)."""
        mock_core = Mock()
        mock_core.reanalyze.side_effect = DoesNotExist("Document not found")
        mock_ctx = Mock()
        mock_ctx.get_core.return_value = mock_core
        mock_get_context.return_value = mock_ctx

        result = runner.invoke(app, ["reanalyze", "invalid-id", "--force"])

        assert result.exit_code == 1
        assert "❌ Документ не найден" in result.stdout

    @patch("semantic_core.cli.app.get_cli_context")
    def test_reanalyze_validation_error(self, mock_get_context):
        """Ошибка валидации (не медиа-файл)."""
        mock_core = Mock()
        mock_core.reanalyze.side_effect = ValueError("Document is not a media file")
        mock_ctx = Mock()
        mock_ctx.get_core.return_value = mock_core
        mock_get_context.return_value = mock_ctx

        result = runner.invoke(app, ["reanalyze", "doc-text", "--force"])

        assert result.exit_code == 1
        assert "❌ Ошибка валидации" in result.stdout

    @patch("semantic_core.cli.app.get_cli_context")
    def test_reanalyze_file_not_found(self, mock_get_context):
        """Файл не найден (FileNotFoundError)."""
        mock_core = Mock()
        mock_core.reanalyze.side_effect = FileNotFoundError("/path/to/audio.mp3")
        mock_ctx = Mock()
        mock_ctx.get_core.return_value = mock_core
        mock_get_context.return_value = mock_ctx

        result = runner.invoke(app, ["reanalyze", "doc-deleted", "--force"])

        assert result.exit_code == 1
        assert "❌ Файл не найден" in result.stdout

    @patch("semantic_core.services.media_service.MediaService")
    @patch("semantic_core.cli.app.get_cli_context")
    def test_reanalyze_show_details(
        self, mock_get_context, mock_media_service_cls, mock_document, mock_media_details
    ):
        """Показать детали после reanalyze (--show-details)."""
        mock_core = Mock()
        mock_core.reanalyze.return_value = mock_document
        mock_core.image_analyzer = Mock()
        mock_core.audio_analyzer = Mock()
        mock_core.video_analyzer = Mock()
        mock_core.splitter = Mock()
        mock_core.store = Mock()
        mock_core.config = Mock()
        mock_ctx = Mock()
        mock_ctx.get_core.return_value = mock_core
        mock_get_context.return_value = mock_ctx

        mock_media_service = Mock()
        mock_media_service.get_media_details.return_value = mock_media_details
        mock_media_service_cls.return_value = mock_media_service

        result = runner.invoke(
            app, ["reanalyze", "doc-abc123", "--force", "--show-details"]
        )

        assert result.exit_code == 0
        assert "✅ Успешно обновлён!" in result.stdout
        assert "📊 Детали документа" in result.stdout
        assert "📝 Summary" in result.stdout
        assert "Test summary" in result.stdout
        mock_media_service.get_media_details.assert_called_once_with("doc-abc123")

    @patch("semantic_core.cli.app.get_cli_context")
    def test_reanalyze_unexpected_error(self, mock_get_context):
        """Неожиданная ошибка."""
        mock_core = Mock()
        mock_core.reanalyze.side_effect = RuntimeError("Unexpected error")
        mock_ctx = Mock()
        mock_ctx.get_core.return_value = mock_core
        mock_get_context.return_value = mock_ctx

        result = runner.invoke(app, ["reanalyze", "doc-abc123", "--force"])

        assert result.exit_code == 1
        assert "❌ Неожиданная ошибка" in result.stdout

    @patch("semantic_core.services.media_service.MediaService")
    @patch("semantic_core.cli.app.get_cli_context")
    def test_show_details_handles_errors(
        self, mock_get_context, mock_media_service_cls, mock_document
    ):
        """_show_document_details обрабатывает ошибки."""
        mock_core = Mock()
        mock_core.reanalyze.return_value = mock_document
        mock_core.image_analyzer = Mock()
        mock_core.audio_analyzer = Mock()
        mock_core.video_analyzer = Mock()
        mock_core.splitter = Mock()
        mock_core.store = Mock()
        mock_core.config = Mock()
        mock_ctx = Mock()
        mock_ctx.get_core.return_value = mock_core
        mock_get_context.return_value = mock_ctx

        mock_media_service = Mock()
        mock_media_service.get_media_details.side_effect = Exception("Service error")
        mock_media_service_cls.return_value = mock_media_service

        result = runner.invoke(
            app, ["reanalyze", "doc-abc123", "--force", "--show-details"]
        )

        assert result.exit_code == 0  # Команда не падает
        assert "⚠️  Не удалось загрузить детали" in result.stdout
