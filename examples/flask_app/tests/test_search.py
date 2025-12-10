"""Тесты поиска: роуты, сервис, markdown.

Проверяет:
- Search routes (HTMX endpoints)
- SearchService с mock core
- Markdown rendering
- Фильтрация по chunk_type
"""

import pytest
import numpy as np
from dataclasses import dataclass
from unittest.mock import MagicMock, patch
from typing import Optional


# ============================================================================
# Markdown Utils Tests
# ============================================================================


class TestMarkdownUtils:
    """Тесты утилит рендеринга Markdown."""

    def test_render_markdown_basic(self):
        """Базовый Markdown рендерится в HTML."""
        from app.utils.markdown import render_markdown

        html = render_markdown("# Hello\n\nWorld")

        assert "<h1>" in html
        assert "Hello" in html
        assert "<p>" in html
        assert "World" in html

    def test_render_markdown_code_block(self):
        """Блок кода рендерится правильно."""
        from app.utils.markdown import render_markdown

        md = "```python\nprint('hello')\n```"
        html = render_markdown(md)

        assert "<code" in html
        assert "print" in html

    def test_render_markdown_escapes_html(self):
        """Сырой HTML экранируется."""
        from app.utils.markdown import render_markdown

        html = render_markdown("<script>alert('xss')</script>")

        assert "<script>" not in html
        # markdown-it преобразует < в &lt;
        assert "&lt;script&gt;" in html or "script" in html

    def test_render_markdown_empty_string(self):
        """Пустая строка возвращает пустую строку."""
        from app.utils.markdown import render_markdown

        assert render_markdown("") == ""
        assert render_markdown(None) == ""

    def test_render_code_with_language(self):
        """Код рендерится с классом языка."""
        from app.utils.markdown import render_code

        html = render_code("print('hello')", "python")

        assert 'class="language-python"' in html
        assert "<pre>" in html
        assert "<code" in html
        assert "print" in html

    def test_render_code_escapes_html(self):
        """HTML в коде экранируется."""
        from app.utils.markdown import render_code

        html = render_code("<div>test</div>")

        assert "<div>" not in html
        assert "&lt;div&gt;" in html

    def test_truncate_content_short(self):
        """Короткий текст не обрезается."""
        from app.utils.markdown import truncate_content

        text = "Short text"
        result = truncate_content(text, max_length=100)

        assert result == text
        assert "..." not in result

    def test_truncate_content_long(self):
        """Длинный текст обрезается с многоточием."""
        from app.utils.markdown import truncate_content

        text = "This is a very long text that should be truncated at some point"
        result = truncate_content(text, max_length=30)

        assert len(result) <= 33  # 30 + "..."
        assert result.endswith("...")

    def test_truncate_content_at_word_boundary(self):
        """Текст обрезается по границе слова."""
        from app.utils.markdown import truncate_content

        text = "Word1 Word2 Word3 Word4 Word5 Word6"
        result = truncate_content(text, max_length=20)

        # Должен обрезаться по пробелу, не разрывая слово
        assert not result.rstrip(".").endswith("Word")


# ============================================================================
# SearchResultItem Tests
# ============================================================================


class TestSearchResultItem:
    """Тесты SearchResultItem dataclass."""

    def test_score_to_class_high(self):
        """Score >= 0.02 → score-high."""
        from app.services.search_service import _score_to_class

        assert _score_to_class(0.05) == "score-high"
        assert _score_to_class(0.02) == "score-high"

    def test_score_to_class_medium(self):
        """Score 0.01-0.02 → score-medium."""
        from app.services.search_service import _score_to_class

        assert _score_to_class(0.015) == "score-medium"
        assert _score_to_class(0.01) == "score-medium"

    def test_score_to_class_low(self):
        """Score < 0.01 → score-low."""
        from app.services.search_service import _score_to_class

        assert _score_to_class(0.005) == "score-low"
        assert _score_to_class(0.0) == "score-low"


# ============================================================================
# SearchService Tests
# ============================================================================


class TestSearchService:
    """Тесты SearchService."""

    @pytest.fixture
    def mock_chunk(self):
        """Фабрика для создания mock chunk."""

        def _create_chunk(
            content="Test content",
            chunk_type="text",
            language=None,
            chunk_id=1,
        ):
            chunk = MagicMock()
            chunk.id = chunk_id
            chunk.content = content
            chunk.chunk_type = MagicMock(value=chunk_type)
            chunk.language = language
            chunk.metadata = {"heading_hierarchy": "H1 > H2"}
            return chunk

        return _create_chunk

    @pytest.fixture
    def mock_chunk_result(self, mock_chunk):
        """Фабрика для создания mock ChunkResult."""

        def _create_result(
            content="Test content",
            chunk_type="text",
            language=None,
            score=0.05,
            match_type="hybrid",
        ):
            result = MagicMock()
            result.chunk = mock_chunk(content, chunk_type, language)
            result.chunk_id = 1
            result.content = content
            result.chunk_type = MagicMock(value=chunk_type)
            result.language = language
            result.score = score
            result.match_type = MagicMock(value=match_type)
            result.parent_doc_id = 1
            result.parent_doc_title = "Test Document"
            result.parent_metadata = {"tags": ["python", "tutorial"]}
            result.highlight = None
            return result

        return _create_result

    @pytest.fixture
    def mock_core(self, mock_chunk_result):
        """Mock SemanticCore."""
        core = MagicMock()
        core.search_chunks.return_value = [
            mock_chunk_result(content="Result 1", score=0.05),
            mock_chunk_result(content="Result 2", score=0.03),
        ]
        return core

    @pytest.fixture
    def mock_cache(self):
        """Mock QueryCacheService."""
        cache = MagicMock()
        cache.get_or_embed.return_value = MagicMock(
            embedding=np.random.rand(768).astype(np.float32),
            from_cache=False,
            frequency=1,
        )
        return cache

    @pytest.fixture
    def search_service(self, mock_core, mock_cache):
        """SearchService с моками."""
        from app.services.search_service import SearchService

        return SearchService(core=mock_core, cache=mock_cache)

    def test_search_returns_results(self, search_service):
        """Поиск возвращает результаты."""
        results = search_service.search("python tutorial")

        assert len(results) == 2
        assert results[0].content == "Result 1"
        assert results[0].score == 0.05

    def test_search_empty_query_returns_empty(self, search_service):
        """Пустой запрос возвращает пустой список."""
        assert search_service.search("") == []
        assert search_service.search("   ") == []

    def test_search_uses_cache(self, search_service, mock_cache):
        """Поиск использует кэш для эмбеддинга."""
        search_service.search("python tutorial")

        mock_cache.get_or_embed.assert_called_once_with("python tutorial")

    def test_search_with_chunk_type_filter(self, search_service, mock_core, mock_cache):
        """Поиск с фильтром по типу чанка."""
        search_service.search("python", chunk_types=["code"])

        # Проверяем что вызов был с правильными параметрами (включая query_vector)
        call_kwargs = mock_core.search_chunks.call_args[1]
        assert call_kwargs["query"] == "python"
        assert call_kwargs["mode"] == "hybrid"
        assert call_kwargs["limit"] == 20
        assert call_kwargs["chunk_type_filter"] == "code"
        assert call_kwargs["query_vector"] is not None

    def test_search_with_multiple_chunk_types(self, search_service, mock_core):
        """Поиск с несколькими типами чанков."""
        search_service.search("python", chunk_types=["text", "code"])

        # Должно быть 2 вызова search_chunks
        assert mock_core.search_chunks.call_count == 2

    def test_search_results_sorted_by_score(self, search_service):
        """Результаты отсортированы по score."""
        results = search_service.search("python")

        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_get_available_types(self, search_service):
        """get_available_types возвращает типы контента."""
        types = search_service.get_available_types()

        assert len(types) == 5
        assert types[0]["id"] == "text"
        assert types[1]["id"] == "code"
        assert "icon" in types[0]
        assert "label" in types[0]

    def test_search_passes_cached_vector_to_core(self, mock_core, mock_cache):
        """Закешированный вектор передаётся в core.search_chunks()."""
        from app.services.search_service import SearchService

        cached_vector = [0.1] * 768
        mock_cache.get_or_embed.return_value = MagicMock(
            embedding=cached_vector,
            from_cache=True,
            frequency=5,
        )

        service = SearchService(core=mock_core, cache=mock_cache)
        service.search("python")

        # Проверяем что вектор был передан
        call_kwargs = mock_core.search_chunks.call_args[1]
        assert call_kwargs["query_vector"] == cached_vector

    def test_search_no_cache_passes_none_vector(self, mock_core):
        """Без кеша query_vector = None."""
        from app.services.search_service import SearchService

        service = SearchService(core=mock_core, cache=None)
        service.search("python")

        call_kwargs = mock_core.search_chunks.call_args[1]
        assert call_kwargs.get("query_vector") is None

    def test_search_documents_returns_document_items(self, mock_core, mock_cache):
        """search_documents возвращает DocumentResultItem."""
        from app.services.search_service import SearchService, DocumentResultItem

        # Mock search result
        mock_doc = MagicMock()
        mock_doc.id = 1
        mock_doc.source = "test.md"
        mock_doc.content = "Test document content"
        mock_doc.metadata = {"title": "Test Doc", "tags": ["test"]}

        mock_result = MagicMock()
        mock_result.document = mock_doc
        mock_result.score = 0.95
        mock_result.match_type = MagicMock(value="hybrid")

        mock_core.search.return_value = [mock_result]

        service = SearchService(core=mock_core, cache=mock_cache)
        results = service.search_documents("test query")

        assert len(results) == 1
        assert isinstance(results[0], DocumentResultItem)
        assert results[0].doc_id == 1
        assert results[0].title == "Test Doc"
        assert results[0].score == 0.95

    def test_search_documents_uses_cached_vector(self, mock_core, mock_cache):
        """search_documents передаёт закешированный вектор."""
        from app.services.search_service import SearchService

        cached_vector = [0.2] * 768
        mock_cache.get_or_embed.return_value = MagicMock(
            embedding=cached_vector,
            from_cache=True,
            frequency=3,
        )
        mock_core.search.return_value = []

        service = SearchService(core=mock_core, cache=mock_cache)
        service.search_documents("test query")

        call_kwargs = mock_core.search.call_args[1]
        assert call_kwargs["query_vector"] == cached_vector


# ============================================================================
# Search Routes Tests
# ============================================================================


class TestSearchRoutes:
    """Тесты маршрутов поиска."""

    def test_search_page_loads(self, client):
        """Страница поиска загружается."""
        response = client.get("/search/")

        assert response.status_code == 200
        assert (
            b"search" in response.data.lower()
            or b"\xd0\xbf\xd0\xbe\xd0\xb8\xd1\x81\xd0\xba" in response.data
        )

    def test_search_page_without_core(self, app, client):
        """Страница показывает предупреждение без core."""
        # Убираем core
        with app.app_context():
            app.extensions["semantic_core"] = None

            response = client.get("/search/")

            assert response.status_code == 200
            # Проверяем наличие предупреждения
            assert b"alert" in response.data or b"warning" in response.data

    def test_search_results_empty_query(self, client):
        """Пустой запрос возвращает пустые результаты."""
        response = client.get("/search/results?q=")

        assert response.status_code == 200
        # Должен вернуть пустой partial
        assert b"results" in response.data.lower() or len(response.data) < 500

    def test_search_results_without_core(self, app, client):
        """Поиск без core возвращает ошибку."""
        with app.app_context():
            app.extensions["semantic_core"] = None

            response = client.get("/search/results?q=test")

            assert response.status_code == 200
            # Должна быть ошибка - проверяем alert-danger класс
            assert b"alert-danger" in response.data

    def test_suggest_returns_json(self, client):
        """Автокомплит возвращает JSON."""
        response = client.get("/search/suggest?q=py")

        assert response.status_code == 200
        assert response.content_type == "application/json"

    def test_suggest_short_query(self, client):
        """Короткий запрос возвращает пустой список."""
        response = client.get("/search/suggest?q=p")

        assert response.status_code == 200
        data = response.get_json()
        assert data == []

    def test_search_results_with_documents_type(self, app, client):
        """Поиск с result_type=documents использует правильный шаблон."""
        with app.app_context():
            # Mock search_documents
            core = app.extensions.get("semantic_core")
            if core:
                # Делаем mock core.search
                original_search = core.search
                core.search = MagicMock(return_value=[])

                response = client.get(
                    "/search/results?q=test&result_type=documents"
                )

                assert response.status_code == 200
                # Шаблон documents должен быть использован
                # Возвращаем сообщение "документы не найдены"
                assert (
                    b"\xd0\x94\xd0\xbe\xd0\xba\xd1\x83\xd0\xbc\xd0\xb5\xd0\xbd\xd1\x82\xd1\x8b"
                    in response.data  # "Документы" в UTF-8
                    or b"document" in response.data.lower()
                )

                core.search = original_search

    def test_search_results_chunks_is_default(self, app, client):
        """По умолчанию result_type=chunks."""
        with app.app_context():
            core = app.extensions.get("semantic_core")
            if core:
                original_search_chunks = core.search_chunks
                core.search_chunks = MagicMock(return_value=[])

                response = client.get("/search/results?q=test")

                assert response.status_code == 200
                # Должен вызваться search_chunks, а не search
                core.search_chunks.assert_called()

                core.search_chunks = original_search_chunks


# ============================================================================
# Integration Tests (with mock data)
# ============================================================================


class TestSearchIntegration:
    """Интеграционные тесты поиска."""

    def test_chunk_result_to_item_conversion(self, mock_chunk_result):
        """ChunkResult правильно конвертируется в SearchResultItem."""
        # Создаём фикстуру вручную для этого теста
        chunk = MagicMock()
        chunk.id = 1
        chunk.content = "Test content"
        chunk.chunk_type = MagicMock(value="code")
        chunk.language = "python"
        chunk.metadata = {"heading_hierarchy": "H1 > H2"}

        result = MagicMock()
        result.chunk = chunk
        result.chunk_id = 1
        result.content = "Test content"
        result.chunk_type = MagicMock(value="code")
        result.language = "python"
        result.score = 0.05
        result.match_type = MagicMock(value="hybrid")
        result.parent_doc_id = 1
        result.parent_doc_title = "Test Document"
        result.parent_metadata = {"tags": ["python"]}
        result.highlight = None

        from app.services.search_service import _chunk_result_to_item

        item = _chunk_result_to_item(result)

        assert item.chunk_id == 1
        assert item.content == "Test content"
        assert item.chunk_type == "code"
        assert item.language == "python"
        assert item.score == 0.05
        assert item.score_class == "score-high"
        assert item.match_type == "hybrid"
        assert item.parent_doc_id == 1
        assert item.parent_doc_title == "Test Document"
        assert item.tags == ["python"]
        assert item.context == "H1 > H2"

    @pytest.fixture
    def mock_chunk_result(self):
        """Mock ChunkResult для интеграционных тестов."""

        def _create():
            chunk = MagicMock()
            chunk.id = 1
            chunk.content = "Test"
            chunk.chunk_type = MagicMock(value="text")
            chunk.language = None
            chunk.metadata = {}

            result = MagicMock()
            result.chunk = chunk
            result.chunk_id = 1
            result.content = "Test"
            result.chunk_type = MagicMock(value="text")
            result.language = None
            result.score = 0.05
            result.match_type = MagicMock(value="hybrid")
            result.parent_doc_id = 1
            result.parent_doc_title = "Doc"
            result.parent_metadata = {}
            result.highlight = None
            return result

        return _create
