"""Search routes — поиск по базе знаний.

Blueprints:
    search_bp: Поиск, результаты, автокомплит.

HTMX endpoints:
    GET /search — Страница поиска
    GET /search/results — Результаты поиска (partial)
    GET /search/suggest — Автокомплит (JSON)
"""

from flask import (
    Blueprint,
    current_app,
    render_template,
    request,
    jsonify,
)

from app.services.search_service import SearchService
from app.utils.markdown import render_markdown, render_code, truncate_content
from semantic_core.utils.logger import get_logger

logger = get_logger("flask_app.routes.search")

search_bp = Blueprint("search", __name__, url_prefix="/search")


def _get_search_service() -> SearchService | None:
    """Получить SearchService из контекста приложения.

    Returns:
        SearchService или None если core недоступен.
    """
    core = current_app.extensions.get("semantic_core")
    if not core:
        return None

    cache = current_app.extensions.get("query_cache")
    return SearchService(core=core, cache=cache)


@search_bp.route("/")
def index():
    """Страница поиска.

    Отображает форму поиска с фильтрами.
    """
    service = _get_search_service()
    available_types = service.get_available_types() if service else []

    return render_template(
        "search.html",
        core_available=service is not None,
        available_types=available_types,
    )


@search_bp.route("/results")
def results():
    """HTMX endpoint: результаты поиска.

    Query params:
        q: Поисковый запрос
        types: Типы контента (text,code,image,audio)
        mode: Режим поиска (hybrid, vector, fts)
        limit: Максимум результатов

    Returns:
        HTML partial с карточками результатов.
    """
    service = _get_search_service()
    if not service:
        return render_template(
            "partials/search_error.html",
            error="SemanticCore недоступен. Проверьте API ключ.",
        )

    # Параметры запроса
    query = request.args.get("q", "").strip()
    types_param = request.args.get("types", "")
    mode = request.args.get("mode", "hybrid")
    limit = request.args.get("limit", "20", type=int)

    # Пустой запрос — пустые результаты
    if not query:
        return render_template("partials/search_results.html", results=[], query="")

    # Парсим типы контента
    chunk_types = None
    if types_param:
        chunk_types = [t.strip() for t in types_param.split(",") if t.strip()]

    logger.info(f"🔍 Search request: q='{query}', types={chunk_types}, mode={mode}")

    try:
        results = service.search(
            query=query,
            chunk_types=chunk_types,
            mode=mode,
            limit=limit,
        )

        return render_template(
            "partials/search_results.html",
            results=results,
            query=query,
            render_markdown=render_markdown,
            render_code=render_code,
            truncate_content=truncate_content,
        )

    except Exception as e:
        logger.error(f"🔥 Search error: {e}")
        return render_template(
            "partials/search_error.html",
            error=f"Ошибка поиска: {str(e)}",
        )


@search_bp.route("/suggest")
def suggest():
    """HTMX/JSON endpoint: автокомплит запросов.

    Query params:
        q: Частичный запрос

    Returns:
        JSON список предложений.
    """
    cache = current_app.extensions.get("query_cache")
    if not cache:
        return jsonify([])

    partial = request.args.get("q", "").strip()
    if len(partial) < 2:
        return jsonify([])

    try:
        suggestions = cache.suggest(partial, limit=5)
        return jsonify(suggestions)
    except Exception as e:
        logger.warning(f"⚠️ Suggest error: {e}")
        return jsonify([])
