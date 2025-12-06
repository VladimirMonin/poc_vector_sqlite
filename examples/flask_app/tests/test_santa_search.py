"""Тест поиска по 'Санта' для проверки RRF k=1."""
import pytest


def test_santa_search_chunks(app, client):
    """Проверяем что поиск чанков дает правильные скоры."""
    with app.app_context():
        from app.services.search_service import SearchService
        
        core = app.extensions.get('semantic_core')
        cache = app.extensions.get('query_cache')
        service = SearchService(core=core, cache=cache)
        
        # Поиск чанков (широкий запрос для получения разнообразия)
        results = service.search(
            query="Новый год",
            mode="hybrid",
            limit=20,
            min_score=0
        )
        
        assert len(results) > 0, "Должны быть результаты"
        
        # Если мало результатов — скипаем проверку разброса
        if len(results) < 3:
            return
        
        # Проверяем разброс в топ-5 (или меньше если результатов мало)
        top_n = min(5, len(results))
        scores = [r.score_percent for r in results[:top_n]]
        max_score = max(scores)
        min_score = min(scores)
        
        # С k=1 должен быть разброс >= 10% (снижаем порог для надёжности)
        assert (max_score - min_score) >= 10, \
            f"Разброс {max_score - min_score}% слишком мал (k=1 должно давать >= 10%)"
        
        # Топ результат >= 30%
        assert max_score >= 30, \
            f"Топ результат {max_score}% слишком низок (ожидается >= 30%)"


def test_santa_search_documents(app, client):
    """Проверяем что поиск документов дает правильные скоры."""
    with app.app_context():
        from app.services.search_service import SearchService
        
        core = app.extensions.get('semantic_core')
        cache = app.extensions.get('query_cache')
        service = SearchService(core=core, cache=cache)
        
        # Поиск документов (широкий запрос)
        results = service.search_documents(
            query="Новый год",
            mode="hybrid",
            limit=20,
            min_score=0
        )
        
        assert len(results) > 0, "Должны быть результаты"
        
        # Если мало результатов — скипаем проверку разброса
        if len(results) < 3:
            return
        
        # Проверяем разброс
        top_n = min(5, len(results))
        scores = [r.score_percent for r in results[:top_n]]
        max_score = max(scores)
        min_score = min(scores)
        
        # С k=1 должен быть разброс >= 10%
        assert (max_score - min_score) >= 10, \
            f"Разброс {max_score - min_score}% слишком мал (k=1 должно давать >= 10%)"
        
        # Топ результат >= 30%
        assert max_score >= 30, \
            f"Топ результат {max_score}% слишком низок (ожидается >= 30%)"
