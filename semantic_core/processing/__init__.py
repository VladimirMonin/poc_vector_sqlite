"""Модуль обработки документов.

Содержит парсеры, сплиттеры и стратегии контекста.
"""

from semantic_core.processing.parsers import MarkdownNodeParser
from semantic_core.processing.splitters import SmartSplitter
from semantic_core.processing.context import HierarchicalContextStrategy

__all__ = [
    "MarkdownNodeParser",
    "SmartSplitter",
    "HierarchicalContextStrategy",
]
