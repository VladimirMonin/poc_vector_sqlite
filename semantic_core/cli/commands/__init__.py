"""CLI команды.

Модули:
    init_cmd: semantic init — инициализация проекта.
    config_cmd: semantic config — управление конфигурацией.
    doctor_cmd: semantic doctor — диагностика.
    ingest_cmd: semantic ingest — индексация документов.
    search_cmd: semantic search — семантический поиск.
    docs_cmd: semantic docs — встроенная документация.
"""

from semantic_core.cli.commands import init_cmd
from semantic_core.cli.commands import config_cmd
from semantic_core.cli.commands import doctor_cmd
from semantic_core.cli.commands.ingest import ingest_cmd
from semantic_core.cli.commands.search import search_cmd
from semantic_core.cli.commands.docs import docs_cmd

__all__ = [
    "init_cmd",
    "config_cmd",
    "doctor_cmd",
    "ingest_cmd",
    "search_cmd",
    "docs_cmd",
]
