"""
Модуль обработки текста для нарезки на чанки.

Предоставляет абстрактный интерфейс и конкретные реализации
сплиттеров для подготовки текста к векторизации.
"""

from .base import TextSplitter, Chunk
from .simple_splitter import SimpleTextSplitter

__all__ = [
    "TextSplitter",
    "Chunk",
    "SimpleTextSplitter",
]
