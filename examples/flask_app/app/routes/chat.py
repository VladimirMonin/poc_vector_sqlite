"""Chat routes — RAG-чат с базой знаний.

Blueprints:
    chat_bp: Интерфейс чата с историей и источниками.

HTMX endpoints:
    GET  /chat              — Страница чата
    POST /chat/send         — Отправить сообщение
    GET  /chat/messages     — Загрузить историю сессии
    POST /chat/new          — Создать новую сессию
    POST /chat/clear        — Очистить сессию
    GET  /chat/sessions     — Список сессий (sidebar)
"""

from flask import (
    Blueprint,
    current_app,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
)

from app.utils.markdown import render_markdown
from semantic_core.utils.logger import get_logger

logger = get_logger("flask_app.routes.chat")

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")


def _get_chat_service():
    """Получить ChatService из контекста.

    Returns:
        ChatService или None если недоступен.
    """
    return current_app.extensions.get("chat_service")


def _check_service_available():
    """Проверить доступность сервиса.

    Returns:
        tuple: (service, error_response) — service или None + ошибка.
    """
    service = _get_chat_service()
    if not service:
        error = render_template(
            "partials/chat_error.html",
            error="RAG-чат недоступен. Проверьте API ключ.",
        )
        return None, error
    return service, None


@chat_bp.route("/")
def index():
    """Страница чата.

    Query params:
        session: ID сессии для загрузки (опционально).

    Returns:
        HTML страница чата.
    """
    service = _get_chat_service()
    session_id = request.args.get("session")

    # Получаем недавние сессии для сайдбара
    sessions = []
    current_session = None
    messages = []

    if service:
        sessions = service.get_recent_sessions(limit=10)

        if session_id:
            current_session = service.get_session(session_id)
            if current_session:
                messages = service.get_session_messages(session_id)

    return render_template(
        "chat.html",
        service_available=service is not None,
        sessions=sessions,
        current_session=current_session,
        messages=messages,
        render_markdown=render_markdown,
    )


@chat_bp.route("/send", methods=["POST"])
def send():
    """HTMX endpoint: отправить сообщение.

    Form data:
        question: Текст вопроса.
        session_id: ID сессии (опционально).
        mode: Режим поиска (hybrid/vector/fts).

    Returns:
        HTML partial с ответом и источниками.
    """
    service, error = _check_service_available()
    if error:
        return error

    # Получаем параметры
    question = request.form.get("question", "").strip()
    session_id = request.form.get("session_id") or None
    mode = request.form.get("mode", "hybrid")

    if not question:
        return render_template(
            "partials/chat_error.html",
            error="Введите вопрос.",
        )

    logger.info(f"💬 Chat send: q='{question[:50]}...', session={session_id}")

    try:
        response = service.ask(
            question=question,
            session_id=session_id,
            search_mode=mode,
        )

        return render_template(
            "partials/chat_response.html",
            response=response,
            render_markdown=render_markdown,
        )

    except Exception as e:
        logger.error(f"🔥 Chat error: {e}")
        return render_template(
            "partials/chat_error.html",
            error=f"Ошибка: {str(e)}",
        )


@chat_bp.route("/messages")
def messages():
    """HTMX endpoint: загрузить историю сессии.

    Query params:
        session_id: ID сессии.

    Returns:
        HTML partial со списком сообщений.
    """
    service, error = _check_service_available()
    if error:
        return error

    session_id = request.args.get("session_id")
    if not session_id:
        return ""

    messages = service.get_session_messages(session_id)

    return render_template(
        "partials/chat_messages.html",
        messages=messages,
        render_markdown=render_markdown,
    )


@chat_bp.route("/new", methods=["POST"])
def new_session():
    """HTMX endpoint: создать новую сессию.

    Returns:
        Редирект на новую сессию или пустой чат.
    """
    service = _get_chat_service()
    if not service:
        return redirect(url_for("chat.index"))

    # Просто редиректим на пустой чат (сессия создастся при первом сообщении)
    return redirect(url_for("chat.index"))


@chat_bp.route("/clear", methods=["POST"])
def clear():
    """HTMX endpoint: очистить сессию.

    Form data:
        session_id: ID сессии.

    Returns:
        Редирект на новый чат.
    """
    service = _get_chat_service()
    session_id = request.form.get("session_id")

    if service and session_id:
        service.clear_session(session_id)

    return redirect(url_for("chat.index"))


@chat_bp.route("/sessions")
def sessions():
    """HTMX endpoint: список сессий для сайдбара.

    Returns:
        HTML partial со списком сессий.
    """
    service = _get_chat_service()
    if not service:
        return ""

    sessions = service.get_recent_sessions(limit=10)

    return render_template(
        "partials/chat_sessions.html",
        sessions=sessions,
    )


@chat_bp.route("/session/<session_id>/delete", methods=["POST"])
def delete_session(session_id: str):
    """HTMX endpoint: удалить сессию.

    Args:
        session_id: UUID сессии.

    Returns:
        Редирект на новый чат.
    """
    service = _get_chat_service()
    if service:
        service.delete_session(session_id)

    return redirect(url_for("chat.index"))
