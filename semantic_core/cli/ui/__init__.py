"""UI слой CLI — Rich виджеты и рендереры.

Модули:
    renderers — Форматирование результатов
    spinners — Прогресс-индикаторы
"""

from semantic_core.cli.ui.renderers import (
    render_search_results,
    render_ingest_summary,
    render_error,
    render_success,
)
from semantic_core.cli.ui.spinners import (
    progress_spinner,
    progress_bar,
)

__all__ = [
    "render_search_results",
    "render_ingest_summary",
    "render_error",
    "render_success",
    "progress_spinner",
    "progress_bar",
]
