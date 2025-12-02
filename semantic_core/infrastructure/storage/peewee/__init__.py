"""Реализация хранилища для Peewee + SQLite.

Модули:
    engine
        Инициализация SQLite с расширениями.
    models
        Внутренние ORM модели.
    adapter
        Реализация BaseVectorStore.
"""

from semantic_core.infrastructure.storage.peewee.adapter import PeeweeVectorStore
from semantic_core.infrastructure.storage.peewee.engine import init_peewee_database

__all__ = [
    "PeeweeVectorStore",
    "init_peewee_database",
]
