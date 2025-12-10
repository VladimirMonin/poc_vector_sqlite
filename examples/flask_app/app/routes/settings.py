"""Settings routes — настройки приложения.

Blueprints:
    settings_bp: Просмотр конфигурации системы.
"""

from flask import Blueprint, render_template, current_app
import sys

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


@settings_bp.route("/")
def index():
    """Страница настроек.

    Показывает текущую конфигурацию системы (read-only).
    """
    config = current_app.extensions.get("semantic_config")
    flask_config = current_app.extensions.get("flask_config")

    # Semantic Core конфигурация — всегда загружаем из get_config()
    semantic_settings = {}
    try:
        from semantic_core.config import get_config

        cfg = get_config()
        semantic_settings = {
            "db_path": str(cfg.db_path),
            "embedding_model": cfg.embedding_model,
            "embedding_dimension": cfg.embedding_dimension,
            "log_level": cfg.log_level,
            "splitter": getattr(cfg, "splitter", "smart"),
            "media_enabled": getattr(cfg, "media_enabled", False),
        }
    except Exception:
        pass

    # Flask конфигурация (безопасные поля)
    flask_settings = {}
    if flask_config:
        flask_settings = {
            "host": flask_config.host,
            "port": flask_config.port,
            "debug": flask_config.debug,
            "upload_folder": str(flask_config.upload_folder),
            "max_content_length_mb": flask_config.max_content_length // (1024 * 1024),
        }

    # Системная информация
    system_info = {
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "flask_version": current_app.import_name,
    }

    # Попытка получить версии пакетов
    try:
        from importlib.metadata import version

        system_info["flask_version"] = version("flask")
    except Exception:
        pass

    try:
        from semantic_core import __version__ as sc_version

        system_info["semantic_core_version"] = sc_version
    except Exception:
        system_info["semantic_core_version"] = "N/A"

    return render_template(
        "settings.html",
        semantic_settings=semantic_settings,
        flask_settings=flask_settings,
        system_info=system_info,
    )


@settings_bp.route("/about")
def about():
    """Страница О приложении.

    Показывает информацию о проекте и лицензию.
    """
    return render_template("about.html")
