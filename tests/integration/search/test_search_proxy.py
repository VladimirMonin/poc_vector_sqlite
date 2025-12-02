"""Integration-тесты для SearchProxy.

Проверяет методы поиска hybrid(), vector(), fts() и возврат ORM объектов.
"""

import pytest
from peewee import CharField, TextField
from semantic_core.domain import Document


def test_search_proxy_hybrid_basic(create_test_model, semantic_core):
    """Базовый тест гибридного поиска."""
    TestModel = create_test_model(
        fields={"title": CharField(), "content": TextField()},
        index_config={"content_field": "content", "context_fields": ["title"]},
    )

    # Создаем тестовые данные вручную через core
    doc1 = Document(
        content="Python programming tutorial",
        metadata={"source_id": None, "title": "Python Guide"},
    )
    doc2 = Document(
        content="JavaScript basics for beginners",
        metadata={"source_id": None, "title": "JS Tutorial"},
    )

    semantic_core.ingest(doc1)
    semantic_core.ingest(doc2)

    # Создаем соответствующие записи в модели
    obj1 = TestModel.create(title="Python Guide", content="Python programming tutorial")
    obj2 = TestModel.create(
        title="JS Tutorial", content="JavaScript basics for beginners"
    )

    # Обновляем source_id в документах
    # (в реальности это должно происходить автоматически через signals)
    # TODO: После реализации signals этот шаг не нужен

    # Выполняем поиск
    results = TestModel.search.hybrid("Python programming", limit=5)

    # Проверяем результаты
    assert isinstance(results, list)
    # TODO: После полной реализации проверить содержимое


def test_search_proxy_vector(create_test_model, semantic_core):
    """Тест векторного поиска."""
    TestModel = create_test_model(
        fields={"text": TextField()},
        index_config={"content_field": "text"},
    )

    # Создаем данные
    obj1 = TestModel.create(text="Machine learning algorithms")
    obj2 = TestModel.create(text="Deep neural networks")
    obj3 = TestModel.create(text="Cooking recipes")

    # Вручную индексируем (пока нет signals)
    obj1.search.update()
    obj2.search.update()
    obj3.search.update()

    # Векторный поиск
    results = TestModel.search.vector("artificial intelligence", limit=2)

    assert isinstance(results, list)
    # Ожидаем, что ML и DL ближе к AI, чем рецепты
    # TODO: Проверить после полной реализации


def test_search_proxy_fts(create_test_model, semantic_core):
    """Тест полнотекстового поиска."""
    TestModel = create_test_model(
        fields={"content": TextField()},
        index_config={"content_field": "content"},
    )

    obj1 = TestModel.create(content="Python is a programming language")
    obj2 = TestModel.create(content="Java is also a programming language")
    obj3 = TestModel.create(content="Cooking is an art")

    # Вручную индексируем
    obj1.search.update()
    obj2.search.update()
    obj3.search.update()

    # FTS поиск по точному совпадению
    results = TestModel.search.fts("programming", limit=5)

    assert isinstance(results, list)
    # TODO: Проверить, что найдены Python и Java, но не Cooking


def test_search_proxy_returns_tuples(create_test_model, semantic_core):
    """Проверяет, что результаты возвращаются как (объект, скор)."""
    TestModel = create_test_model(
        fields={"data": TextField()},
        index_config={"content_field": "data"},
    )

    obj = TestModel.create(data="Test data for search")
    obj.search.update()

    results = TestModel.search.vector("search test", limit=1)

    # Результаты должны быть списком кортежей
    assert isinstance(results, list)

    if results:
        obj_result, score = results[0]
        # Проверяем типы
        assert isinstance(obj_result, TestModel)
        assert isinstance(score, (int, float))
        # Скор - это число (может быть отрицательным для cosine distance)
        assert score is not None


def test_search_proxy_with_filters(create_test_model, semantic_core):
    """Проверяет поиск с фильтрами по метаданным."""
    TestModel = create_test_model(
        fields={
            "title": CharField(),
            "content": TextField(),
            "category": CharField(),
        },
        index_config={
            "content_field": "content",
            "context_fields": ["title"],
            "filter_fields": ["category"],
        },
    )

    obj1 = TestModel.create(
        title="Python Tutorial", content="Learn Python", category="tech"
    )
    obj2 = TestModel.create(
        title="Cooking Recipe", content="How to cook", category="food"
    )

    obj1.search.update()
    obj2.search.update()

    # Поиск с фильтром
    results = TestModel.search.hybrid("tutorial", category="tech", limit=5)

    assert isinstance(results, list)
    # TODO: Проверить, что найден только tech объект


def test_search_proxy_empty_results(create_test_model):
    """Проверяет поведение при отсутствии результатов."""
    TestModel = create_test_model(
        fields={"text": TextField()},
        index_config={"content_field": "text"},
    )

    # Не создаем никаких данных

    results = TestModel.search.hybrid("nonexistent query", limit=5)

    assert isinstance(results, list)
    assert len(results) == 0


def test_search_proxy_preserves_order(create_test_model, semantic_core):
    """Проверяет, что порядок результатов сохраняется (RRF сортировка)."""
    TestModel = create_test_model(
        fields={"content": TextField()},
        index_config={"content_field": "content"},
    )

    obj1 = TestModel.create(content="First item very relevant")
    obj2 = TestModel.create(content="Second item somewhat relevant")
    obj3 = TestModel.create(content="Third item barely relevant")

    obj1.search.update()
    obj2.search.update()
    obj3.search.update()

    results = TestModel.search.hybrid("very relevant", limit=3)

    assert isinstance(results, list)
    # TODO: Проверить, что порядок соответствует релевантности


def test_search_proxy_limit_parameter(create_test_model, semantic_core):
    """Проверяет работу параметра limit."""
    TestModel = create_test_model(
        fields={"text": TextField()},
        index_config={"content_field": "text"},
    )

    # Создаем 5 объектов
    for i in range(5):
        obj = TestModel.create(text=f"Document number {i}")
        obj.search.update()

    # Запрашиваем только 2
    results = TestModel.search.hybrid("document", limit=2)

    assert isinstance(results, list)
    # TODO: Проверить, что вернулось не более 2 результатов


def test_search_proxy_different_modes(create_test_model, semantic_core):
    """Проверяет, что разные методы используют разные режимы поиска."""
    TestModel = create_test_model(
        fields={"content": TextField()},
        index_config={"content_field": "content"},
    )

    obj = TestModel.create(content="Test content for search modes")
    obj.search.update()

    # Все три метода должны работать без ошибок
    hybrid_results = TestModel.search.hybrid("search", limit=1)
    vector_results = TestModel.search.vector("search", limit=1)
    fts_results = TestModel.search.fts("search", limit=1)

    assert isinstance(hybrid_results, list)
    assert isinstance(vector_results, list)
    assert isinstance(fts_results, list)

    # TODO: Проверить, что результаты могут отличаться
