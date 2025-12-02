"""Стратегии формирования контекста для эмбеддингов.

Классы:
    HierarchicalContextStrategy
        Стратегия с учетом иерархии заголовков и типа контента.
"""

from semantic_core.processing.context.hierarchical_strategy import (
    HierarchicalContextStrategy,
)

__all__ = ["HierarchicalContextStrategy"]
