"""Реализации для обработки текста.

Модули:
    simple_splitter
        Простой сплиттер с фиксированным размером чанков.
    basic_context
        Базовая стратегия формирования контекста.
"""

from semantic_core.infrastructure.text_processing.simple_splitter import (
    SimpleSplitter,
)
from semantic_core.infrastructure.text_processing.basic_context import (
    BasicContextStrategy,
)

__all__ = [
    "SimpleSplitter",
    "BasicContextStrategy",
]
