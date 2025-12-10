"""Тесты конфигурации Flask приложения.

Проверяет Pydantic Settings интеграцию.
"""

import pytest


class TestFlaskAppConfig:
    """Тесты FlaskAppConfig."""

    def test_default_values(self):
        """Дефолтные значения загружаются."""
        from app.config import FlaskAppConfig

        config = FlaskAppConfig()

        assert config.debug is True
        assert config.host == "127.0.0.1"
        assert config.port == 5000
        assert config.max_content_length == 50 * 1024 * 1024

    def test_to_flask_config(self):
        """to_flask_config() возвращает словарь для Flask."""
        from app.config import FlaskAppConfig

        config = FlaskAppConfig(secret_key="test-key", debug=False)
        flask_dict = config.to_flask_config()

        assert flask_dict["SECRET_KEY"] == "test-key"
        assert flask_dict["DEBUG"] is False
        assert "UPLOAD_FOLDER" in flask_dict
        assert "MAX_CONTENT_LENGTH" in flask_dict

    def test_env_override(self, monkeypatch):
        """Environment variables переопределяют дефолты."""
        from app.config import FlaskAppConfig

        monkeypatch.setenv("FLASK_PORT", "8080")
        monkeypatch.setenv("FLASK_DEBUG", "false")

        config = FlaskAppConfig()

        assert config.port == 8080
        assert config.debug is False

    def test_get_flask_config_singleton(self):
        """get_flask_config() возвращает singleton."""
        from app.config import get_flask_config, reset_flask_config

        reset_flask_config()

        config1 = get_flask_config()
        config2 = get_flask_config()

        assert config1 is config2

    def test_get_flask_config_with_overrides(self):
        """get_flask_config() с overrides создаёт новый экземпляр."""
        from app.config import get_flask_config, reset_flask_config

        reset_flask_config()

        config1 = get_flask_config()
        config2 = get_flask_config(port=9000)

        assert config1 is not config2
        assert config2.port == 9000


class TestAppConfigIntegration:
    """Тесты интеграции конфигурации с Flask app."""

    def test_app_uses_flask_config(self, app):
        """Flask app использует FlaskAppConfig."""
        # Проверяем, что конфиг применён
        assert "SECRET_KEY" in app.config
        assert "UPLOAD_FOLDER" in app.config

    def test_app_config_override_for_testing(self, app):
        """TESTING=True применяется для тестов."""
        assert app.config["TESTING"] is True
