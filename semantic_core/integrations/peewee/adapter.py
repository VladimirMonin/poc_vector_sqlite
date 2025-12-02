"""Адаптер для интеграции с Peewee ORM.

Классы:
    PeeweeAdapter
        Адаптер для подписки на события Peewee и управления схемой.
"""

from typing import TYPE_CHECKING, Any
from peewee import Model

try:
    from playhouse.signals import post_save, pre_delete

    SIGNALS_AVAILABLE = True
except ImportError:
    SIGNALS_AVAILABLE = False

if TYPE_CHECKING:
    from semantic_core.integrations.base import SemanticIndex


class PeeweeAdapter:
    """Адаптер для интеграции семантического поиска с Peewee.

    Подписывается на события Peewee (post_save, pre_delete) и
    автоматически синхронизирует изменения с векторным хранилищем.

    Attributes:
        descriptor: Дескриптор SemanticIndex.
        model: Класс Peewee модели.
    """

    def __init__(self, model: type[Model], descriptor: "SemanticIndex"):
        self.model = model
        self.descriptor = descriptor

        if not SIGNALS_AVAILABLE:
            raise ImportError(
                "playhouse.signals не установлен. "
                "Установите: pip install peewee[signals]"
            )

    def register_hooks(self) -> None:
        """Регистрирует хуки на события Peewee.

        Подписывается на post_save и pre_delete для автоматической
        синхронизации данных с векторным хранилищем.
        """
        # Генерируем уникальные имена для обработчиков на основе дескриптора
        descriptor_id = id(self.descriptor)
        save_handler_name = f"on_save_{descriptor_id}"
        delete_handler_name = f"on_delete_{descriptor_id}"

        @post_save(sender=self.model, name=save_handler_name)
        def on_save(model_class: type[Model], instance: Model, created: bool) -> None:
            """Обработчик события сохранения.

            Args:
                model_class: Класс модели.
                instance: Сохраненный инстанс.
                created: True если объект создан, False если обновлен.
            """
            # Строим документ
            doc = self.descriptor.builder.build(instance)

            # Если это обновление, удаляем старые чанки
            if not created and hasattr(instance, "id"):
                source_id = str(getattr(instance, "id"))
                # Используем метод delete из store
                # Фильтруем по source_id в метаданных
                # Пока используем простое удаление и пересоздание
                # TODO: добавить delete_by_metadata в VectorStore
                pass

            # Индексируем
            self.descriptor.core.ingest(doc)

        @pre_delete(sender=self.model, name=delete_handler_name)
        def on_delete(model_class: type[Model], instance: Model) -> None:
            """Обработчик события удаления.

            Args:
                model_class: Класс модели.
                instance: Удаляемый инстанс.
            """
            if hasattr(instance, "id"):
                source_id = str(getattr(instance, "id"))
                # TODO: добавить delete_by_metadata в VectorStore
                pass


def register_model(model: type[Model], descriptor: "SemanticIndex") -> None:
    """Регистрирует модель Peewee для автоматической индексации.

    Args:
        model: Класс Peewee модели.
        descriptor: Дескриптор SemanticIndex.

    Raises:
        ImportError: Если playhouse.signals не установлен.
    """
    adapter = PeeweeAdapter(model=model, descriptor=descriptor)
    adapter.register_hooks()
