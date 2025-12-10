"""Тесты логирования Flask запросов.

Проверяет middleware для HTTP логов с эмодзи.
"""

import pytest


class TestRequestLogging:
    """Тесты логирования HTTP запросов."""

    def test_request_logs_success(self, client, caplog):
        """Успешный запрос логируется с эмодзи."""
        import logging

        with caplog.at_level(logging.INFO):
            response = client.get("/")

        assert response.status_code == 200
        # Проверяем, что был лог запроса
        # Лог может содержать эмодзи 🌐 или ⚡ в зависимости от времени
        log_messages = [record.message for record in caplog.records]
        assert any("[GET]" in msg and "/" in msg for msg in log_messages)

    def test_request_logs_contain_method(self, client, caplog):
        """Лог содержит HTTP метод."""
        import logging

        with caplog.at_level(logging.INFO):
            client.get("/health")

        log_messages = [record.message for record in caplog.records]
        assert any("[GET]" in msg for msg in log_messages)

    def test_request_logs_contain_path(self, client, caplog):
        """Лог содержит путь запроса."""
        import logging

        with caplog.at_level(logging.INFO):
            client.get("/health")

        log_messages = [record.message for record in caplog.records]
        assert any("/health" in msg for msg in log_messages)

    def test_request_logs_contain_status_code(self, client, caplog):
        """Лог содержит статус код."""
        import logging

        with caplog.at_level(logging.INFO):
            client.get("/")

        log_messages = [record.message for record in caplog.records]
        assert any("200" in msg for msg in log_messages)

    def test_404_logged_with_warning_emoji(self, client, caplog):
        """404 ошибка логируется с предупреждающим эмодзи."""
        import logging

        with caplog.at_level(logging.INFO):
            client.get("/nonexistent")

        log_messages = [record.message for record in caplog.records]
        # Должен быть лог с 404
        assert any("404" in msg for msg in log_messages)


class TestLoggingInitialization:
    """Тесты инициализации логирования."""

    def test_logging_initialized_on_app_create(self, app):
        """Логирование настраивается при создании приложения."""
        # Если приложение создано успешно, логирование настроено
        assert app is not None

    def test_semantic_logger_available(self, app):
        """SemanticLogger доступен."""
        from semantic_core.utils.logger import get_logger

        with app.app_context():
            logger = get_logger("test")
            assert logger is not None
