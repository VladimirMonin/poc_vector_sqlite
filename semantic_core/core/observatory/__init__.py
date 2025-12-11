"""Debug Observatory - инструменты для отладки и инспекции SemanticCore.

Phase 16: Multi-Provider Inspection & Debug Observatory

Компоненты:
- ProviderInspector: Перехват и запись данных pipeline
- SnapshotManager: Сохранение и загрузка артефактов
- Reporters: Экспорт данных (Console/Markdown/JSON/Diff)

Использование:
    >>> from semantic_core.core.observatory import ProviderInspector
    >>> inspector = ProviderInspector(core=semantic_core)
    >>> doc = inspector.ingest_with_inspection(document)
"""

from .inspector import ProviderInspector
from .snapshot import SnapshotManager, InspectionSnapshot
from .reporters import (
    ConsoleReporter,
    MarkdownReporter,
    JsonReporter,
    DiffReporter,
)

__all__ = [
    "ProviderInspector",
    "SnapshotManager",
    "InspectionSnapshot",
    "ConsoleReporter",
    "MarkdownReporter",
    "JsonReporter",
    "DiffReporter",
]
