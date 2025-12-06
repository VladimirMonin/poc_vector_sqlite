"""Тесты для страницы настроек и About.

Tests:
    - Settings page загружается
    - About page загружается
    - Отображение конфигурации
"""

import pytest
from flask import Flask


class TestSettingsRoutes:
    """Тесты маршрутов настроек."""

    def test_settings_page_loads(self, client):
        """Страница настроек загружается."""
        response = client.get("/settings/")
        assert response.status_code == 200
        assert "Настройки" in response.data.decode("utf-8")

    def test_settings_page_shows_semantic_config(self, client):
        """Страница показывает Semantic Core конфигурацию."""
        response = client.get("/settings/")
        html = response.data.decode("utf-8")
        assert "Semantic Core" in html

    def test_settings_page_shows_flask_config(self, client):
        """Страница показывает Flask конфигурацию."""
        response = client.get("/settings/")
        html = response.data.decode("utf-8")
        assert "Flask Application" in html

    def test_settings_page_shows_system_info(self, client):
        """Страница показывает информацию о системе."""
        response = client.get("/settings/")
        html = response.data.decode("utf-8")
        assert "Python" in html


class TestAboutRoutes:
    """Тесты страницы О приложении."""

    def test_about_page_loads(self, client):
        """Страница О приложении загружается."""
        response = client.get("/settings/about")
        assert response.status_code == 200
        assert "Semantic Knowledge Base" in response.data.decode("utf-8")

    def test_about_page_shows_features(self, client):
        """Страница показывает возможности."""
        response = client.get("/settings/about")
        html = response.data.decode("utf-8")
        assert "Семантический поиск" in html

    def test_about_page_shows_tech_stack(self, client):
        """Страница показывает технологический стек."""
        response = client.get("/settings/about")
        html = response.data.decode("utf-8")
        assert "Flask" in html
        assert "HTMX" in html
        assert "Bootstrap" in html

    def test_about_page_shows_license(self, client):
        """Страница показывает лицензию."""
        response = client.get("/settings/about")
        html = response.data.decode("utf-8")
        assert "MIT" in html


class TestSettingsBlueprint:
    """Тесты регистрации blueprint."""

    def test_settings_blueprint_registered(self, app: Flask):
        """Blueprint настроек зарегистрирован."""
        assert "settings" in app.blueprints

    def test_settings_blueprint_has_url_prefix(self, app: Flask):
        """Blueprint имеет правильный url_prefix."""
        from app.routes.settings import settings_bp

        assert settings_bp.url_prefix == "/settings"


class TestFlaskConfigExtension:
    """Тесты хранения flask_config в extensions."""

    def test_flask_config_in_extensions(self, app: Flask):
        """Flask config сохранён в extensions."""
        with app.app_context():
            assert "flask_config" in app.extensions

    def test_flask_config_has_attributes(self, app: Flask):
        """Flask config имеет нужные атрибуты."""
        with app.app_context():
            config = app.extensions.get("flask_config")
            if config:
                assert hasattr(config, "host")
                assert hasattr(config, "port")
                assert hasattr(config, "debug")
