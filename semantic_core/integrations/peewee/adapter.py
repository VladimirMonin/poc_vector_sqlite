"""Адаптер для интеграции с Peewee ORM.

Использует паттерн "Explicit Hook Injection" - внедряет хуки в методы
save() и delete_instance() модели через обертки. Это позволяет работать
с обычной peewee.Model без требования наследования от SignalModel.

Классы:
    PeeweeAdapter
        Адаптер для автоматической индексации при изменениях ORM.
"""

from typing import TYPE_CHECKING, Callable, Any
from peewee import Model

if TYPE_CHECKING:
    from semantic_core.integrations.base import SemanticIndex


# Class-level registry для отслеживания множественных дескрипторов
_MODEL_HOOKS: dict[type[Model], list["SemanticIndex"]] = {}


class PeeweeAdapter:
    """Адаптер для интеграции семантического поиска с Peewee.

    Внедряет хуки в методы save() и delete_instance() модели,
    обеспечивая автоматическую синхронизацию с векторным хранилищем.

    Работает с любой peewee.Model - наследование от SignalModel не требуется.

    Attributes:
        descriptor: Дескриптор SemanticIndex.
        model: Класс Peewee модели.
    """

    def __init__(self, model: type[Model], descriptor: "SemanticIndex"):
        self.model = model
        self.descriptor = descriptor

    def _apply_hooks(self) -> None:
        """Внедряет триггеры автоматической индексации в методы модели.

        Оборачивает save() и delete_instance() в декораторы, которые
        вызывают соответствующие обработчики для всех зарегистрированных
        на модели дескрипторов SemanticIndex.

        Патчинг выполняется только один раз для модели, даже если на ней
        несколько дескрипторов. Все дескрипторы регистрируются в реестре
        _MODEL_HOOKS и вызываются из единого wrapper.
        """
        # Регистрируем дескриптор в реестре
        if self.model not in _MODEL_HOOKS:
            _MODEL_HOOKS[self.model] = []
        _MODEL_HOOKS[self.model].append(self.descriptor)

        # Патчим методы только при первом дескрипторе
        if len(_MODEL_HOOKS[self.model]) == 1:
            self._patch_save()
            self._patch_delete()

    def _patch_save(self) -> None:
        """Патчит метод save() модели для автоиндексации."""
        original_save = self.model.save
        model_class = self.model  # Сохраняем ссылку для использования в замыкании

        def save_wrapper(instance: Model, *args: Any, **kwargs: Any) -> int:
            """Обертка над save() - вызывает индексацию после сохранения.

            Args:
                instance: Инстанс модели для сохранения.
                *args: Позиционные аргументы для save().
                **kwargs: Именованные аргументы для save().

            Returns:
                Результат оригинального save() (количество измененных строк).
            """
            # Проверяем, создается или обновляется объект
            is_new = not bool(instance.get_id())

            # 1. Вызываем оригинальный save
            result = original_save(instance, *args, **kwargs)

            # 2. Если успешно - триггерим индексацию для всех дескрипторов
            if result:
                for desc in _MODEL_HOOKS.get(model_class, []):
                    desc._handle_save(instance, created=is_new)

            return result

        # Подменяем метод на классе модели
        self.model.save = save_wrapper

    def _patch_delete(self) -> None:
        """Патчит метод delete_instance() модели для автоудаления из индекса."""
        original_delete = self.model.delete_instance
        model_class = self.model  # Сохраняем ссылку для использования в замыкании

        def delete_wrapper(instance: Model, *args: Any, **kwargs: Any) -> int:
            """Обертка над delete_instance() - удаляет из индекса перед удалением.

            Args:
                instance: Инстанс модели для удаления.
                *args: Позиционные аргументы для delete_instance().
                **kwargs: Именованные аргументы для delete_instance().

            Returns:
                Результат оригинального delete_instance() (количество удаленных строк).
            """
            # 1. Сначала удаляем из индекса (пока есть ID и метаданные)
            for desc in _MODEL_HOOKS.get(model_class, []):
                desc._handle_delete(instance)

            # 2. Вызываем оригинальное удаление
            return original_delete(instance, *args, **kwargs)

        # Подменяем метод на классе модели
        self.model.delete_instance = delete_wrapper


def register_model(model: type[Model], descriptor: "SemanticIndex") -> None:
    """Регистрирует модель Peewee для автоматической индексации.

    Внедряет хуки в методы save() и delete_instance() через method patching.
    Работает с любой peewee.Model - SignalModel не требуется.

    Args:
        model: Класс Peewee модели.
        descriptor: Дескриптор SemanticIndex.
    """
    adapter = PeeweeAdapter(model=model, descriptor=descriptor)
    adapter._apply_hooks()
