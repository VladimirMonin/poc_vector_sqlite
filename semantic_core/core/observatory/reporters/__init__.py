"""Reporters для Observatory - экспорт данных инспекции.

Компоненты:
- ConsoleReporter: Rich TUI для терминала
- MarkdownReporter: Markdown отчёты
- JsonReporter: JSON дампы
- DiffReporter: Сравнение снимков
"""

from .console import ConsoleReporter
from .markdown import MarkdownReporter
from .json import JsonReporter
from .diff import DiffReporter

__all__ = [
    "ConsoleReporter",
    "MarkdownReporter",
    "JsonReporter",
    "DiffReporter",
]
