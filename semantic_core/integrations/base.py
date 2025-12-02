"""Базовые классы для интеграции с ORM.

Классы:
    DocumentBuilder
        Строитель документов из ORM инстансов.
    InstanceManager
        Менеджер для управления индексом конкретного инстанса.
    SemanticIndex
        Дескриптор для добавления семантического поиска к ORM моделям.
"""

from typing import Any, Optional, TYPE_CHECKING

from semantic_core.domain import Document, MediaType

if TYPE_CHECKING:
    from semantic_core.pipeline import SemanticCore
    from semantic_core.integrations.search_proxy import SearchProxy


class DocumentBuilder:
    """Строитель документов из ORM инстансов.

    Преобразует объекты ORM в DTO Document для обработки пайплайном.
    Извлекает данные из указанных полей модели и собирает их в Document.

    Attributes:
        content_field: Имя поля с основным контентом.
        context_fields: Список полей для включения в метаданные.
        media_fields: Список полей с путями к медиа-файлам.
        filter_fields: Список полей для фильтрации.
    """

    def __init__(
        self,
        content_field: str,
        context_fields: Optional[list[str]] = None,
        media_fields: Optional[list[str]] = None,
        filter_fields: Optional[list[str]] = None,
    ):
        self.content_field = content_field
        self.context_fields = context_fields or []
        self.media_fields = media_fields or []
        self.filter_fields = filter_fields or []

    def build(self, instance: Any) -> Document:
        """Строит Document из ORM инстанса.

        Args:
            instance: Объект ORM модели.

        Returns:
            Document с извлеченными данными.

        Raises:
            AttributeError: Если поле не существует в модели.
        """
        # Извлекаем основной контент
        content = getattr(instance, self.content_field, "")

        # Обрабатываем None как пустую строку
        if content is None:
            content = ""

        # Собираем метаданные из context_fields
        metadata: dict[str, Any] = {}
        for field_name in self.context_fields:
            if hasattr(instance, field_name):
                metadata[field_name] = getattr(instance, field_name)

        # Добавляем filter_fields в метаданные
        for field_name in self.filter_fields:
            if hasattr(instance, field_name):
                metadata[field_name] = getattr(instance, field_name)

        # Добавляем ID модели в метаданные
        if hasattr(instance, "id"):
            metadata["source_id"] = getattr(instance, "id")

        # Определяем тип медиа
        media_type = MediaType.TEXT
        if self.media_fields:
            # Если есть медиа-поля, это может быть изображение/видео
            # Пока оставляем TEXT, в Phase 6 добавим логику определения типа
            media_type = MediaType.TEXT

        return Document(
            content=content,
            metadata=metadata,
            media_type=media_type,
        )


class InstanceManager:
    """Менеджер для управления индексом конкретного инстанса.

    Возвращается при обращении к дескриптору через инстанс.
    Позволяет обновлять или удалять индекс для конкретной записи.

    Attributes:
        instance: ORM инстанс.
        descriptor: Родительский дескриптор SemanticIndex.
    """

    def __init__(self, instance: Any, descriptor: "SemanticIndex"):
        self.instance = instance
        self.descriptor = descriptor

    def update(self) -> None:
        """Обновляет индекс для текущего инстанса.

        Принудительно пересоздает Document и обновляет векторы.
        """
        # Строим документ
        doc = self.descriptor.builder.build(self.instance)

        # Удаляем старые чанки если есть source_id
        if hasattr(self.instance, "id") and self.instance.id is not None:
            source_id = self.instance.id  # Используем напрямую, без str()
            self.descriptor.core.delete_by_metadata({"source_id": source_id})

        # Индексируем заново
        self.descriptor.core.ingest(doc)

    def delete(self) -> None:
        """Удаляет индекс для текущего инстанса."""
        if hasattr(self.instance, "id") and self.instance.id is not None:
            source_id = self.instance.id  # Используем напрямую, без str()
            self.descriptor.core.delete_by_metadata({"source_id": source_id})


class SemanticIndex:
    """Дескриптор для добавления семантического поиска к ORM моделям.

    Реализует Descriptor Protocol для интеграции с классами моделей.
    Автоматически индексирует данные при сохранении и предоставляет
    интерфейс поиска через SearchProxy.

    Пример:
        >>> from peewee import Model, CharField, TextField
        >>> from semantic_core import SemanticCore, SemanticIndex
        >>>
        >>> class Article(Model):
        ...     title = CharField()
        ...     content = TextField()
        ...
        ...     search = SemanticIndex(
        ...         core=core,
        ...         content_field="content",
        ...         context_fields=["title"],
        ...     )
        >>>
        >>> # Class access - поиск
        >>> results = Article.search.hybrid("python tutorial")
        >>>
        >>> # Instance access - управление индексом
        >>> article = Article.get_by_id(1)
        >>> article.search.update()

    Attributes:
        core: Экземпляр SemanticCore для обработки.
        builder: DocumentBuilder для преобразования инстансов.
        name: Имя дескриптора (устанавливается автоматически).
        owner: Класс-владелец (устанавливается автоматически).
    """

    def __init__(
        self,
        core: "SemanticCore",
        content_field: str,
        context_fields: Optional[list[str]] = None,
        media_fields: Optional[list[str]] = None,
        filter_fields: Optional[list[str]] = None,
    ):
        self.core = core
        self.builder = DocumentBuilder(
            content_field=content_field,
            context_fields=context_fields,
            media_fields=media_fields,
            filter_fields=filter_fields,
        )
        self.name: Optional[str] = None
        self.owner: Optional[type] = None

    def __set_name__(self, owner: type, name: str) -> None:
        """Регистрирует дескриптор при создании класса.

        Args:
            owner: Класс-владелец дескриптора.
            name: Имя атрибута дескриптора.
        """
        self.name = name
        self.owner = owner

        # Проверяем, является ли owner Peewee моделью
        try:
            from peewee import Model

            if issubclass(owner, Model):
                # Регистрируем хуки через адаптер
                from semantic_core.integrations.peewee.adapter import register_model

                register_model(owner, self)
        except ImportError:
            # Peewee не установлен, пропускаем регистрацию
            pass

    def __get__(self, instance: Any, owner: type) -> "SearchProxy | InstanceManager":
        """Возвращает SearchProxy или InstanceManager.

        Args:
            instance: Инстанс модели (или None при доступе через класс).
            owner: Класс модели.

        Returns:
            SearchProxy при доступе через класс.
            InstanceManager при доступе через инстанс.
        """
        if instance is None:
            # Class access: Model.search -> SearchProxy
            from semantic_core.integrations.search_proxy import SearchProxy

            return SearchProxy(core=self.core, model=owner, descriptor=self)
        else:
            # Instance access: instance.search -> InstanceManager
            return InstanceManager(instance=instance, descriptor=self)

    def __set__(self, instance: Any, value: Any) -> None:
        """Запрещает присваивание дескриптору.

        Raises:
            AttributeError: Всегда.
        """
        raise AttributeError(f"Cannot set attribute '{self.name}'")

    def _handle_save(self, instance: Any, created: bool) -> None:
        """Обработчик сохранения инстанса (вызывается из PeeweeAdapter).

        Args:
            instance: Сохраненный инстанс модели.
            created: True если объект создан, False если обновлен.
        """
        # Строим документ
        doc = self.builder.build(instance)

        # Если это обновление, удаляем старые чанки
        if not created and hasattr(instance, "id") and instance.id is not None:
            source_id = instance.id  # Используем напрямую, без str()
            self.core.delete_by_metadata({"source_id": source_id})

        # Индексируем
        self.core.ingest(doc)

    def _handle_delete(self, instance: Any) -> None:
        """Обработчик удаления инстанса (вызывается из PeeweeAdapter).

        Args:
            instance: Удаляемый инстанс модели.
        """
        if hasattr(instance, "id") and instance.id is not None:
            source_id = instance.id  # Используем напрямую, без str()
            self.core.delete_by_metadata({"source_id": source_id})
