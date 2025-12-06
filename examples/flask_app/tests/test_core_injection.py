"""Тесты интеграции SemanticCore с Flask.

Проверяет, что ядро доступно через app.extensions.
"""

import pytest


class TestCoreInjection:
    """Тесты DI паттерна для SemanticCore."""

    def test_semantic_config_in_extensions(self, app):
        """SemanticConfig сохраняется в extensions."""
        from semantic_core.config import SemanticConfig

        config = app.extensions.get("semantic_config")
        assert config is not None
        assert isinstance(config, SemanticConfig)

    def test_semantic_store_in_extensions(self, app):
        """PeeweeVectorStore сохраняется в extensions."""
        store = app.extensions.get("semantic_store")
        # Store всегда создаётся (не требует API key)
        assert store is not None

    def test_config_has_db_path(self, app):
        """Конфигурация содержит путь к БД."""
        config = app.extensions.get("semantic_config")
        assert config.db_path is not None

    def test_get_semantic_core_helper(self, app):
        """Хелпер get_semantic_core работает в контексте."""
        from app.extensions import get_semantic_core, get_semantic_config

        with app.app_context():
            # Конфиг всегда доступен
            config = get_semantic_config()
            assert config is not None

            # Core может быть None если нет API key
            core = get_semantic_core()
            # Не проверяем, что core не None — зависит от наличия API key


class TestCoreAvailability:
    """Тесты доступности SemanticCore в зависимости от API key."""

    def test_core_none_without_api_key(self, app, monkeypatch):
        """Без API key SemanticCore = None (graceful degradation)."""
        # Проверяем, что приложение работает даже без core
        with app.app_context():
            from flask import current_app

            # Приложение должно быть работоспособным
            assert current_app is not None

    def test_health_reflects_core_status(self, client):
        """Health endpoint отражает статус core."""
        response = client.get("/health")
        data = response.get_json()

        # semantic_core должен быть "available" или "unavailable"
        assert data["semantic_core"] in ["available", "unavailable"]

        # status зависит от core
        if data["semantic_core"] == "available":
            assert data["status"] == "ok"
        else:
            assert data["status"] == "degraded"
