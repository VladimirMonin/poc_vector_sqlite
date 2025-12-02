"""Утилиты для работы с Peewee ORM.

Функции:
    fetch_objects_ordered(model: type[Model], ids: list) -> list[Model]
        Получает объекты модели по ID с сохранением порядка.
"""

from typing import Any
from peewee import Model


def fetch_objects_ordered(model: type[Model], ids: list[Any]) -> list[Model]:
    """Получает объекты модели по ID с сохранением порядка.

    Args:
        model: Класс Peewee модели.
        ids: Список ID для выборки.

    Returns:
        Список объектов модели в том же порядке, что и ids.

    Raises:
        ValueError: Если ids пустой.
    """
    if not ids:
        return []

    # Выполняем запрос
    query = model.select().where(model.id.in_(ids))
    objects = list(query)

    # Создаем словарь для быстрого доступа
    objects_dict = {obj.id: obj for obj in objects}

    # Возвращаем объекты в исходном порядке
    ordered_objects = []
    for obj_id in ids:
        if obj_id in objects_dict:
            ordered_objects.append(objects_dict[obj_id])

    return ordered_objects
