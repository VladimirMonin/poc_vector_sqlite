"""Pytest конфигурация для Flask app тестов.

Fixtures:
    app: Flask приложение с тестовой конфигурацией.
    client: Flask test client.
"""

import sys
from pathlib import Path

import pytest

# Добавляем корень репозитория в PYTHONPATH
repo_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(repo_root))

# Добавляем flask_app в PYTHONPATH
flask_app_root = Path(__file__).parent.parent
sys.path.insert(0, str(flask_app_root))


@pytest.fixture
def app():
    """Создать Flask приложение с тестовой конфигурацией."""
    from app import create_app

    app = create_app(
        config={
            "TESTING": True,
            "SECRET_KEY": "test-secret-key",
        }
    )

    yield app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Flask CLI test runner."""
    return app.test_cli_runner()
