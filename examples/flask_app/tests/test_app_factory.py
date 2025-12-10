"""Тесты Flask application factory.

Проверяет, что приложение запускается и конфигурация загружается.
"""

import pytest


class TestAppFactory:
    """Тесты создания Flask приложения."""

    def test_create_app_returns_flask_instance(self, app):
        """create_app() возвращает Flask приложение."""
        from flask import Flask

        assert isinstance(app, Flask)

    def test_app_has_testing_config(self, app):
        """Тестовая конфигурация применяется."""
        assert app.config["TESTING"] is True
        assert app.config["SECRET_KEY"] == "test-secret-key"

    def test_app_has_default_config(self, app):
        """Дефолтная конфигурация присутствует."""
        assert "UPLOAD_FOLDER" in app.config
        assert app.config["MAX_CONTENT_LENGTH"] == 50 * 1024 * 1024

    def test_app_has_extensions(self, app):
        """Extensions инициализированы."""
        # semantic_config всегда должен быть
        assert "semantic_config" in app.extensions

    def test_main_blueprint_registered(self, app):
        """Main blueprint зарегистрирован."""
        assert "main" in app.blueprints


class TestRoutes:
    """Тесты базовых маршрутов."""

    def test_index_returns_200(self, client):
        """Главная страница доступна."""
        response = client.get("/")
        assert response.status_code == 200

    def test_index_contains_title(self, client):
        """Главная страница содержит заголовок."""
        response = client.get("/")
        assert b"Dashboard" in response.data or b"Semantic" in response.data

    def test_health_endpoint_returns_json(self, client):
        """Health endpoint возвращает JSON."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.content_type == "application/json"

        data = response.get_json()
        assert "status" in data
        assert "semantic_core" in data

    def test_404_for_unknown_route(self, client):
        """Неизвестный маршрут возвращает 404."""
        response = client.get("/unknown-route-that-does-not-exist")
        assert response.status_code == 404
