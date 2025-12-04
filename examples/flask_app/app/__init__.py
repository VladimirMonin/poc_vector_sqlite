"""Flask Application Factory.

Создаёт и настраивает Flask приложение с интеграцией semantic_core.

Usage:
    from app import create_app
    app = create_app()
"""

from flask import Flask

from app.config import get_flask_config, FlaskAppConfig
from app.extensions import init_semantic_core
from app.logging import init_logging


def create_app(config: dict | FlaskAppConfig | None = None) -> Flask:
    """Создать Flask приложение.

    Args:
        config: Опциональные настройки:
            - dict: переопределения для Flask config
            - FlaskAppConfig: полная конфигурация
            - None: загрузить из env/.env

    Returns:
        Настроенное Flask приложение.
    """
    app = Flask(__name__)

    # Загрузка конфигурации
    if isinstance(config, FlaskAppConfig):
        flask_config = config
    elif isinstance(config, dict):
        flask_config = get_flask_config(**config)
    else:
        flask_config = get_flask_config()

    # Применение конфигурации
    app.config.from_mapping(flask_config.to_flask_config())

    # Override из словаря (для тестов с TESTING=True)
    if isinstance(config, dict):
        app.config.from_mapping(config)

    # Инициализация расширений
    init_logging(app)
    init_semantic_core(app)

    # Регистрация blueprints
    from app.routes import main_bp
    from app.routes.search import search_bp
    from app.routes.ingest import ingest_bp
    from app.routes.chat import chat_bp
    from app.routes.settings import settings_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(ingest_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(settings_bp)

    return app
