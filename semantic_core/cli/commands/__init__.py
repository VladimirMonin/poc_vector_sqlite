"""CLI команды.

Модули:
    init_cmd: semantic init — инициализация проекта.
    config_cmd: semantic config — управление конфигурацией.
    doctor_cmd: semantic doctor — диагностика.
    ingest_cmd: semantic ingest — индексация документов.
    search_cmd: semantic search — семантический поиск.
    docs_cmd: semantic docs — встроенная документация.
    queue_cmd: semantic queue — управление очередями.
    worker_cmd: semantic worker — воркеры обработки.
    chat_cmd: semantic chat — интерактивный RAG-чат.
"""

from semantic_core.cli.commands import init_cmd
from semantic_core.cli.commands import config_cmd
from semantic_core.cli.commands import doctor_cmd
from semantic_core.cli.commands.ingest import ingest as ingest_cmd
from semantic_core.cli.commands.search import search as search_cmd
from semantic_core.cli.commands.docs import docs_cmd
from semantic_core.cli.commands.queue import queue_cmd
from semantic_core.cli.commands.worker import worker_cmd
from semantic_core.cli.commands.chat import chat_cmd
from semantic_core.cli.commands.reanalyze import reanalyze as reanalyze_cmd

__all__ = [
    "init_cmd",
    "config_cmd",
    "doctor_cmd",
    "ingest_cmd",
    "search_cmd",
    "docs_cmd",
    "queue_cmd",
    "worker_cmd",
    "chat_cmd",
    "reanalyze_cmd",
]
