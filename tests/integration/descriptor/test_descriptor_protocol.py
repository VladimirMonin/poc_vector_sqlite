"""Integration-тесты для Descriptor Protocol SemanticIndex.

Проверяет регистрацию, __get__, __set_name__ и взаимодействие с моделями.
"""

import pytest
from peewee import Model, CharField, TextField
from semantic_core import SemanticIndex
from semantic_core.integrations.base import InstanceManager
from semantic_core.integrations.search_proxy import SearchProxy


def test_descriptor_set_name(create_test_model):
    """Проверяет автоматическую установку name и owner при создании класса."""
    TestModel = create_test_model(
        fields={"title": CharField(), "body": TextField()},
        index_config={"content_field": "body", "context_fields": ["title"]},
    )

    # Дескриптор должен знать свое имя и владельца
    assert TestModel.search.name == "search"
    assert TestModel.search.owner == TestModel


def test_descriptor_class_access(create_test_model):
    """Проверяет доступ через класс (Model.search) -> SearchProxy."""
    TestModel = create_test_model(
        fields={"content": TextField()},
        index_config={"content_field": "content"},
    )

    # Class access должен вернуть SearchProxy
    search_proxy = TestModel.search
    assert isinstance(search_proxy, SearchProxy)
    assert search_proxy.model == TestModel


def test_descriptor_instance_access(create_test_model):
    """Проверяет доступ через инстанс (instance.search) -> InstanceManager."""
    TestModel = create_test_model(
        fields={"text": TextField()},
        index_config={"content_field": "text"},
    )

    obj = TestModel.create(text="Hello World")

    # Instance access должен вернуть InstanceManager
    manager = obj.search
    assert isinstance(manager, InstanceManager)
    assert manager.instance == obj
    assert manager.descriptor == TestModel.search


def test_descriptor_cannot_set(create_test_model):
    """Проверяет, что присваивание дескриптору запрещено."""
    TestModel = create_test_model(
        fields={"data": TextField()},
        index_config={"content_field": "data"},
    )

    obj = TestModel.create(data="Test")

    # Попытка присвоить должна вызвать AttributeError
    with pytest.raises(AttributeError, match="Cannot set attribute"):
        obj.search = "something"


def test_multiple_descriptors_on_same_model(create_test_model, semantic_core):
    """Проверяет возможность иметь несколько дескрипторов на одной модели."""
    from peewee import Model, CharField, TextField
    from semantic_core import SemanticIndex

    # Создаем модель с двумя индексами вручную
    class Article(Model):
        title = CharField()
        body_ru = TextField()
        body_en = TextField()

        search_ru = SemanticIndex(
            core=semantic_core, content_field="body_ru", context_fields=["title"]
        )
        search_en = SemanticIndex(
            core=semantic_core, content_field="body_en", context_fields=["title"]
        )

        class Meta:
            database = semantic_core.store.db

    semantic_core.store.db.create_tables([Article])

    # Оба дескриптора должны быть зарегистрированы
    assert Article.search_ru.name == "search_ru"
    assert Article.search_en.name == "search_en"

    # Class access на обоих должен работать
    assert isinstance(Article.search_ru, SearchProxy)
    assert isinstance(Article.search_en, SearchProxy)

    # Cleanup
    semantic_core.store.db.drop_tables([Article])


def test_descriptor_with_empty_config(create_test_model):
    """Проверяет работу дескриптора с минимальной конфигурацией."""
    TestModel = create_test_model(
        fields={"text": TextField()},
        index_config={"content_field": "text"},  # Только обязательное поле
    )

    obj = TestModel.create(text="Simple text")

    # Дескриптор должен работать с минимальной конфигурацией
    assert isinstance(TestModel.search, SearchProxy)
    assert isinstance(obj.search, InstanceManager)


def test_descriptor_builder_configuration(create_test_model):
    """Проверяет, что конфигурация корректно передается в DocumentBuilder."""
    TestModel = create_test_model(
        fields={
            "title": CharField(),
            "body": TextField(),
            "category": CharField(),
        },
        index_config={
            "content_field": "body",
            "context_fields": ["title"],
            "filter_fields": ["category"],
        },
    )

    # Проверяем конфигурацию builder
    builder = TestModel.search.builder
    assert builder.content_field == "body"
    assert builder.context_fields == ["title"]
    assert builder.filter_fields == ["category"]
