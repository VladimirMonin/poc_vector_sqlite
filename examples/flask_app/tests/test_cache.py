"""Тесты кэширования поисковых запросов.

Проверяет cache hit/miss, автокомплит и статистику.
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch


class TestSearchQueryModel:
    """Тесты модели SearchQueryModel."""

    def test_compute_hash_consistent(self):
        """Хэш для одного запроса всегда одинаковый."""
        from app.models.cache import SearchQueryModel

        hash1 = SearchQueryModel.compute_hash("python tutorial")
        hash2 = SearchQueryModel.compute_hash("python tutorial")

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex

    def test_compute_hash_case_insensitive(self):
        """Хэш нормализуется по регистру."""
        from app.models.cache import SearchQueryModel

        hash_lower = SearchQueryModel.compute_hash("python tutorial")
        hash_upper = SearchQueryModel.compute_hash("PYTHON TUTORIAL")
        hash_mixed = SearchQueryModel.compute_hash("Python Tutorial")

        assert hash_lower == hash_upper == hash_mixed

    def test_compute_hash_strips_whitespace(self):
        """Хэш нормализуется по пробелам."""
        from app.models.cache import SearchQueryModel

        hash1 = SearchQueryModel.compute_hash("python tutorial")
        hash2 = SearchQueryModel.compute_hash("  python tutorial  ")

        assert hash1 == hash2

    def test_compute_hash_different_queries(self):
        """Разные запросы дают разные хэши."""
        from app.models.cache import SearchQueryModel

        hash1 = SearchQueryModel.compute_hash("python tutorial")
        hash2 = SearchQueryModel.compute_hash("java tutorial")

        assert hash1 != hash2


class TestQueryCacheService:
    """Тесты сервиса кэширования."""

    @pytest.fixture
    def mock_embedder(self):
        """Мок embedder с фиксированным вектором."""
        embedder = MagicMock()
        embedder.embed_query.return_value = np.random.rand(768).astype(np.float32)
        return embedder

    @pytest.fixture
    def mock_database(self, tmp_path):
        """In-memory SQLite database для тестов."""
        from peewee import SqliteDatabase

        db = SqliteDatabase(":memory:")
        return db

    @pytest.fixture
    def cache_service(self, mock_embedder, mock_database):
        """QueryCacheService с моками."""
        from app.services.cache_service import QueryCacheService

        return QueryCacheService(embedder=mock_embedder, database=mock_database)

    def test_cache_miss_calls_embedder(self, cache_service, mock_embedder):
        """При cache miss вызывается embedder."""
        result = cache_service.get_or_embed("python tutorial")

        mock_embedder.embed_query.assert_called_once_with("python tutorial")
        assert result.from_cache is False
        assert result.frequency == 1
        assert isinstance(result.embedding, np.ndarray)

    def test_cache_hit_does_not_call_embedder(self, cache_service, mock_embedder):
        """При cache hit embedder не вызывается."""
        # Первый запрос — cache miss
        cache_service.get_or_embed("python tutorial")
        mock_embedder.embed_query.reset_mock()

        # Второй запрос — cache hit
        result = cache_service.get_or_embed("python tutorial")

        mock_embedder.embed_query.assert_not_called()
        assert result.from_cache is True
        assert result.frequency == 2

    def test_cache_hit_increments_frequency(self, cache_service):
        """При cache hit frequency увеличивается."""
        cache_service.get_or_embed("python tutorial")
        cache_service.get_or_embed("python tutorial")
        result = cache_service.get_or_embed("python tutorial")

        assert result.frequency == 3

    def test_case_insensitive_cache_hit(self, cache_service, mock_embedder):
        """Cache hit работает независимо от регистра."""
        cache_service.get_or_embed("Python Tutorial")
        mock_embedder.embed_query.reset_mock()

        result = cache_service.get_or_embed("PYTHON TUTORIAL")

        mock_embedder.embed_query.assert_not_called()
        assert result.from_cache is True

    def test_suggest_empty_for_short_query(self, cache_service):
        """Автокомплит пустой для коротких запросов."""
        cache_service.get_or_embed("python tutorial")

        suggestions = cache_service.suggest("p")
        assert suggestions == []

        suggestions = cache_service.suggest("")
        assert suggestions == []

    def test_suggest_returns_matching_queries(self, cache_service):
        """Автокомплит возвращает подходящие запросы."""
        cache_service.get_or_embed("python tutorial")
        cache_service.get_or_embed("python basics")
        cache_service.get_or_embed("java tutorial")

        suggestions = cache_service.suggest("python")

        assert len(suggestions) == 2
        assert "java tutorial" not in suggestions

    def test_suggest_ordered_by_frequency(self, cache_service):
        """Автокомплит сортируется по частоте."""
        cache_service.get_or_embed("python basics")
        cache_service.get_or_embed("python tutorial")
        # Повышаем частоту python tutorial
        cache_service.get_or_embed("python tutorial")
        cache_service.get_or_embed("python tutorial")

        suggestions = cache_service.suggest("python")

        # python tutorial должен быть первым (frequency=3)
        assert suggestions[0] == "python tutorial"

    def test_suggest_respects_limit(self, cache_service):
        """Автокомплит ограничен лимитом."""
        for i in range(10):
            cache_service.get_or_embed(f"python topic {i}")

        suggestions = cache_service.suggest("python", limit=3)

        assert len(suggestions) == 3

    def test_get_stats_empty_cache(self, cache_service):
        """Статистика пустого кэша."""
        stats = cache_service.get_stats()

        assert stats["unique_queries"] == 0
        assert stats["total_hits"] == 0
        assert stats["cache_savings"] == 0

    def test_get_stats_with_data(self, cache_service):
        """Статистика с данными."""
        cache_service.get_or_embed("python tutorial")
        cache_service.get_or_embed("python tutorial")
        cache_service.get_or_embed("java tutorial")

        stats = cache_service.get_stats()

        assert stats["unique_queries"] == 2
        assert stats["total_hits"] == 3
        assert stats["cache_savings"] == 1  # 3 hits - 2 unique = 1 saved API call

    def test_clear_removes_all_entries(self, cache_service):
        """clear() удаляет все записи."""
        cache_service.get_or_embed("python tutorial")
        cache_service.get_or_embed("java tutorial")

        deleted = cache_service.clear()

        assert deleted == 2
        stats = cache_service.get_stats()
        assert stats["unique_queries"] == 0


class TestCacheIntegration:
    """Интеграционные тесты с Flask app."""

    def test_query_cache_in_extensions(self, app):
        """QueryCacheService доступен через extensions."""
        # Может быть None если нет API key
        query_cache = app.extensions.get("query_cache")
        # Проверяем, что ключ существует
        assert "query_cache" in app.extensions

    def test_get_query_cache_helper(self, app):
        """Хелпер get_query_cache работает."""
        from app.extensions import get_query_cache

        with app.app_context():
            cache = get_query_cache()
            # Может быть None без API key
            assert cache is None or hasattr(cache, "get_or_embed")
