"""Адаптер для интеграции с Peewee ORM.

Классы:
    PeeweeAdapter
        Адаптер для подписки на события Peewee и управления схемой.

Функции:
    fetch_objects_ordered(model: type[Model], ids: list[str]) -> list[Model]
        Получает объекты модели по ID с сохранением порядка.
"""

from semantic_core.integrations.peewee.adapter import PeeweeAdapter
from semantic_core.integrations.peewee.utils import fetch_objects_ordered

__all__ = [
    "PeeweeAdapter",
    "fetch_objects_ordered",
]
