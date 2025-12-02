"""Unit-тесты для DocumentBuilder.

Проверяет чистую логику сборки Document из объектов без БД.
"""

import pytest
from semantic_core.integrations.base import DocumentBuilder
from semantic_core.domain import Document, MediaType


class MockObject:
    """Фейковый объект с атрибутами для тестирования."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_document_builder_basic():
    """Базовая сборка Document из content_field."""
    builder = DocumentBuilder(content_field="body")
    obj = MockObject(id=1, body="Test content")

    doc = builder.build(obj)

    assert isinstance(doc, Document)
    assert doc.content == "Test content"
    assert doc.metadata["source_id"] == 1
    assert doc.media_type == MediaType.TEXT


def test_document_builder_with_context_fields():
    """Сборка Document с контекстными полями."""
    builder = DocumentBuilder(content_field="body", context_fields=["title", "author"])
    obj = MockObject(id=1, title="Hello", body="Content", author="John")

    doc = builder.build(obj)

    assert doc.content == "Content"
    assert doc.metadata["title"] == "Hello"
    assert doc.metadata["author"] == "John"
    assert doc.metadata["source_id"] == 1


def test_document_builder_with_filter_fields():
    """Сборка Document с полями для фильтрации."""
    builder = DocumentBuilder(
        content_field="text", filter_fields=["category", "status"]
    )
    obj = MockObject(id=5, text="Data", category="tech", status="published")

    doc = builder.build(obj)

    assert doc.content == "Data"
    assert doc.metadata["category"] == "tech"
    assert doc.metadata["status"] == "published"
    assert doc.metadata["source_id"] == 5


def test_document_builder_combined_fields():
    """Сборка Document с комбинацией context и filter полей."""
    builder = DocumentBuilder(
        content_field="body",
        context_fields=["title"],
        filter_fields=["tags", "priority"],
    )
    obj = MockObject(
        id=10, title="Article", body="Text", tags=["python", "coding"], priority=1
    )

    doc = builder.build(obj)

    assert doc.content == "Text"
    assert doc.metadata["title"] == "Article"
    assert doc.metadata["tags"] == ["python", "coding"]
    assert doc.metadata["priority"] == 1
    assert doc.metadata["source_id"] == 10


def test_document_builder_missing_field():
    """Обработка отсутствующего поля (не падает, использует пустое значение)."""
    builder = DocumentBuilder(content_field="missing_field")
    obj = MockObject(id=1, existing_field="Data")

    doc = builder.build(obj)

    # getattr с дефолтом возвращает пустую строку
    assert doc.content == ""
    assert doc.metadata["source_id"] == 1


def test_document_builder_empty_content():
    """Сборка Document с пустым контентом."""
    builder = DocumentBuilder(content_field="body")
    obj = MockObject(id=1, body="")

    doc = builder.build(obj)

    assert doc.content == ""
    assert doc.metadata["source_id"] == 1


def test_document_builder_no_id():
    """Сборка Document когда у объекта нет ID."""
    builder = DocumentBuilder(content_field="text")
    obj = MockObject(text="Content")  # Нет id

    doc = builder.build(obj)

    assert doc.content == "Content"
    assert "source_id" not in doc.metadata


def test_document_builder_media_fields():
    """Сборка Document с медиа-полями (пока только TEXT)."""
    builder = DocumentBuilder(
        content_field="description", media_fields=["image_path", "video_url"]
    )
    obj = MockObject(
        id=1,
        description="Photo description",
        image_path="/path/to/image.jpg",
        video_url="https://example.com/video.mp4",
    )

    doc = builder.build(obj)

    assert doc.content == "Photo description"
    assert doc.media_type == MediaType.TEXT  # Пока всегда TEXT
    # В Phase 6 здесь будет логика определения типа медиа


def test_document_builder_none_values():
    """Обработка None значений в полях."""
    builder = DocumentBuilder(content_field="body", context_fields=["title"])
    obj = MockObject(id=1, body=None, title=None)

    doc = builder.build(obj)

    # None в контенте преобразуется в пустую строку
    assert doc.content == ""
    # None в метаданных сохраняется как None
    assert doc.metadata["title"] is None
    assert doc.metadata["title"] is None
    assert doc.metadata["source_id"] == 1


def test_document_builder_complex_types():
    """Обработка сложных типов данных в метаданных."""
    builder = DocumentBuilder(content_field="text", context_fields=["metadata_obj"])
    obj = MockObject(
        id=1, text="Content", metadata_obj={"key": "value", "nested": [1, 2, 3]}
    )

    doc = builder.build(obj)

    assert doc.content == "Content"
    assert doc.metadata["metadata_obj"] == {"key": "value", "nested": [1, 2, 3]}
