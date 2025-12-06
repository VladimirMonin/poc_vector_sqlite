"""Main routes — главная страница и общие маршруты.

Blueprints:
    main_bp: Главная страница, статус, about, queue.
"""

from flask import Blueprint, render_template, current_app, request, redirect, url_for, flash

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


@main_bp.route("/queue")
def queue_monitor():
    """Мониторинг очереди обработки медиа.
    
    Отображает:
    - Статистику по статусам задач
    - Таблицу последних 100 задач
    - Auto-refresh через HTMX каждые 5 сек
    """
    from semantic_core.infrastructure.storage.peewee.models import MediaTaskModel
    
    # Получаем последние 100 задач
    tasks = list(
        MediaTaskModel.select()
        .order_by(MediaTaskModel.created_at.desc())
        .limit(100)
    )
    
    # Статистика по статусам
    stats = {
        "pending": sum(1 for t in tasks if t.status == "pending"),
        "processing": sum(1 for t in tasks if t.status == "processing"),
        "completed": sum(1 for t in tasks if t.status == "completed"),
        "failed": sum(1 for t in tasks if t.status == "failed"),
    }
    
    return render_template(
        "queue.html",
        tasks=tasks,
        stats=stats,
    )


@main_bp.route("/queue/tasks")
def queue_tasks():
    """HTMX partial: обновление таблицы задач."""
    from semantic_core.infrastructure.storage.peewee.models import MediaTaskModel
    
    tasks = list(
        MediaTaskModel.select()
        .order_by(MediaTaskModel.created_at.desc())
        .limit(100)
    )
    
    return render_template("partials/queue_tasks.html", tasks=tasks)


@main_bp.route("/queue/retry/<task_id>", methods=["POST"])
def retry_task(task_id: str):
    """Повторить обработку failed задачи.
    
    Args:
        task_id: UUID задачи
        
    Returns:
        Redirect на страницу очереди
    """
    from semantic_core.infrastructure.storage.peewee.models import MediaTaskModel
    
    try:
        task = MediaTaskModel.get_by_id(task_id)
        
        if task.status != "failed":
            flash(f"Задача {task_id[:8]} не в статусе failed", "warning")
        else:
            # Сбрасываем статус на pending для повторной обработки
            task.status = "pending"
            task.error_message = None
            task.save()
            
            flash(f"Задача {task_id[:8]} возвращена в очередь", "success")
    except Exception as e:
        flash(f"Ошибка при retry: {e}", "danger")
    
    return redirect(url_for("main.queue_monitor"))
