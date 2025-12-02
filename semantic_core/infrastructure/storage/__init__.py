"""Адаптеры для хранилища данных.

Модули:
    peewee
        Реализация BaseVectorStore для SQLite + Peewee.
"""

from semantic_core.infrastructure.storage.peewee.adapter import PeeweeVectorStore
from semantic_core.infrastructure.storage.peewee.engine import init_peewee_database

__all__ = [
    "PeeweeVectorStore",
    "init_peewee_database",
]
