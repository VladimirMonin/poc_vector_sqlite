"""Утилиты для рендеринга Markdown в безопасный HTML.

Использует markdown-it-py для парсинга и рендеринга.
Sanitizes HTML output to prevent XSS.

Functions:
    render_markdown: Конвертирует Markdown в безопасный HTML.
    render_code: Рендерит код с подсветкой синтаксиса.

Usage:
    html = render_markdown("# Hello\\n\\nWorld")
    code_html = render_code("print('hello')", "python")
"""

import html
from typing import Optional

from markdown_it import MarkdownIt

from semantic_core.utils.logger import get_logger

logger = get_logger("flask_app.markdown")

# Настраиваем markdown-it с безопасными настройками
_md = MarkdownIt(
    "commonmark",
    {
        "html": False,  # Не разрешаем сырой HTML
        "linkify": True,  # Автолинки для URL
        "typographer": True,  # Типографские замены
    },
)
# Включаем расширения
_md.enable(["table", "strikethrough"])


def render_markdown(text: str) -> str:
    """Рендерить Markdown в безопасный HTML.

    Использует markdown-it-py с отключённым raw HTML.
    Безопасен для вывода в браузер.

    Args:
        text: Markdown текст.

    Returns:
        HTML строка.
    """
    if not text:
        return ""

    try:
        return _md.render(text)
    except Exception as e:
        logger.warning(f"⚠️ Ошибка рендеринга markdown: {e}")
        # Fallback: escape и wrap в <p>
        return f"<p>{html.escape(text)}</p>"


def render_code(code: str, language: Optional[str] = None) -> str:
    """Рендерить код в HTML с подсветкой.

    Создаёт <pre><code> блок для highlight.js.

    Args:
        code: Исходный код.
        language: Язык программирования (python, javascript, etc.).

    Returns:
        HTML строка с кодом.
    """
    if not code:
        return ""

    escaped_code = html.escape(code)
    lang_class = f"language-{language}" if language else ""

    return f'<pre><code class="{lang_class}">{escaped_code}</code></pre>'


def truncate_content(content: str, max_length: int = 300) -> str:
    """Обрезать контент до указанной длины.

    Добавляет "..." если текст обрезан.

    Args:
        content: Исходный текст.
        max_length: Максимальная длина.

    Returns:
        Обрезанный текст.
    """
    if not content:
        return ""

    if len(content) <= max_length:
        return content

    # Обрезаем по пробелу, чтобы не ломать слова
    truncated = content[:max_length]
    last_space = truncated.rfind(" ")
    if last_space > max_length // 2:
        truncated = truncated[:last_space]

    return truncated + "..."
