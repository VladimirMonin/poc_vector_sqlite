"""Main routes — главная страница и общие маршруты.

Blueprints:
    main_bp: Главная страница, статус, about.
"""

from flask import Blueprint, render_template, current_app

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Главная страница.

    Показывает статус системы и quick links.
    """
    core = current_app.extensions.get("semantic_core")
    config = current_app.extensions.get("semantic_config")

    # Статистика (если core доступен)
    stats = None
    if core:
        try:
            store = current_app.extensions.get("semantic_store")
            if store:
                # Получаем количество документов и чанков
                from semantic_core.infrastructure.storage.peewee.models import (
                    DocumentModel,
                    ChunkModel,
                )

                stats = {
                    "documents": DocumentModel.select().count(),
                    "chunks": ChunkModel.select().count(),
                    "db_path": str(config.db_path) if config else "N/A",
                    "embedding_model": config.embedding_model if config else "N/A",
                }
        except Exception:
            pass  # БД может быть не инициализирована

    return render_template(
        "index.html",
        core_available=core is not None,
        stats=stats,
    )


@main_bp.route("/health")
def health():
    """Health check endpoint для мониторинга."""
    core = current_app.extensions.get("semantic_core")

    return {
        "status": "ok" if core else "degraded",
        "semantic_core": "available" if core else "unavailable",
    }
