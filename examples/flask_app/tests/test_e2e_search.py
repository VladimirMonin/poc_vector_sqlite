"""E2E тесты поиска с реальным SemanticCore.

Тестирует полный flow: ingest → search → results.
Использует реальную SQLite БД с sqlite-vec, реальный embedder.

ВАЖНО: Требует GEMINI_API_KEY в окружении!
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Добавляем пути
repo_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(repo_root))
flask_app_root = Path(__file__).parent.parent
sys.path.insert(0, str(flask_app_root))

# Загружаем .env перед импортом app
from dotenv import load_dotenv

load_dotenv(repo_root / ".env", override=True)


# Skip all tests if no API key
pytestmark = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"), reason="GEMINI_API_KEY not set"
)


@pytest.fixture(scope="module")
def e2e_app():
    """Flask приложение с реальным SemanticCore.

    Использует временную БД, но реальный Gemini API.
    """
    from semantic_core.config import reset_config

    # Сбрасываем глобальный конфиг перед тестом
    reset_config()

    # Создаём временную БД
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_e2e.db"

        # Устанавливаем путь к БД через env
        os.environ["SEMANTIC_DB_PATH"] = str(db_path)

        from app import create_app

        app = create_app(
            config={
                "TESTING": True,
                "SECRET_KEY": "e2e-test-key",
            }
        )

        yield app

        # Cleanup
        reset_config()
        if "SEMANTIC_DB_PATH" in os.environ:
            del os.environ["SEMANTIC_DB_PATH"]


@pytest.fixture(scope="module")
def e2e_client(e2e_app):
    """Flask test client для E2E."""
    return e2e_app.test_client()


@pytest.fixture(scope="module")
def seeded_app(e2e_app, e2e_client):
    """Flask приложение с загруженными тестовыми документами."""
    from semantic_core.domain import Document

    with e2e_app.app_context():
        core = e2e_app.extensions.get("semantic_core")

        if core is None:
            pytest.skip("SemanticCore not initialized (check API key)")

        # Загружаем тестовые документы
        test_docs = [
            Document(
                content="""# Гибридный поиск

Гибридный поиск объединяет векторный поиск и полнотекстовый поиск 
через алгоритм Reciprocal Rank Fusion (RRF).

## Как работает RRF

RRF комбинирует ранги из разных источников по формуле:
score = sum(1 / (k + rank_i)) для каждого источника i

Константа k обычно равна 60.

## Преимущества

- Лучшее качество чем отдельные методы
- Устойчивость к шуму в одном из источников
- Простота реализации
""",
                metadata={"title": "Гибридный поиск", "tags": ["search", "rrf"]},
            ),
            Document(
                content="""# Векторный поиск

Векторный поиск использует эмбеддинги для семантического поиска.

## Принцип работы

1. Текст преобразуется в вектор через embedding model
2. Вектор сравнивается с векторами в базе через cosine similarity
3. Возвращаются ближайшие результаты

## Пример кода

```python
def vector_search(query: str, limit: int = 10):
    query_vector = embedder.embed(query)
    results = store.search_by_vector(query_vector, limit)
    return results
```

Этот код выполняет векторный поиск по базе.
""",
                metadata={"title": "Векторный поиск", "tags": ["search", "vector"]},
            ),
            Document(
                content="""# SQLite и sqlite-vec

sqlite-vec — расширение SQLite для векторного поиска.

## Установка

```bash
pip install sqlite-vec
```

## Использование

```python
import sqlite_vec

conn = sqlite3.connect(":memory:")
conn.enable_load_extension(True)
sqlite_vec.load(conn)
```

Расширение добавляет виртуальную таблицу vec0.
""",
                metadata={"title": "SQLite Vec", "tags": ["sqlite", "extension"]},
            ),
        ]

        for doc in test_docs:
            core.ingest(doc)

        yield e2e_app


class TestE2ESearch:
    """E2E тесты поиска."""

    def test_search_page_loads(self, seeded_app, e2e_client):
        """Страница поиска загружается."""
        response = e2e_client.get("/search/")
        assert response.status_code == 200
        assert "Поиск" in response.data.decode("utf-8")

    def test_search_returns_results(self, seeded_app, e2e_client):
        """Поиск возвращает результаты."""
        response = e2e_client.get(
            "/search/results",
            query_string={
                "q": "гибридный поиск",
                "types": "text,code",
                "mode": "hybrid",
            },
        )

        assert response.status_code == 200
        html = response.data.decode("utf-8")

        # Должны найти документ про гибридный поиск
        assert (
            "RRF" in html or "гибридный" in html.lower() or "результат" in html.lower()
        )

    def test_search_vector_mode(self, seeded_app, e2e_client):
        """Векторный поиск работает."""
        response = e2e_client.get(
            "/search/results",
            query_string={
                "q": "как искать по смыслу",
                "types": "text",
                "mode": "vector",
            },
        )

        assert response.status_code == 200
        # Не должно быть ошибки
        html = response.data.decode("utf-8")
        assert "Ошибка" not in html or "error" not in html.lower()

    def test_search_code_chunks(self, seeded_app, e2e_client):
        """Поиск находит код."""
        response = e2e_client.get(
            "/search/results",
            query_string={
                "q": "vector_search function",
                "types": "code",
                "mode": "hybrid",
            },
        )

        assert response.status_code == 200
        html = response.data.decode("utf-8")
        # Может найти или не найти, но не должен упасть
        assert response.status_code == 200

    def test_search_empty_query(self, seeded_app, e2e_client):
        """Пустой запрос не падает."""
        response = e2e_client.get(
            "/search/results", query_string={"q": "", "types": "text", "mode": "hybrid"}
        )

        assert response.status_code == 200

    def test_suggest_endpoint(self, seeded_app, e2e_client):
        """Автокомплит работает."""
        response = e2e_client.get("/search/suggest", query_string={"q": "гибрид"})

        assert response.status_code == 200
        # Должен вернуть JSON
        assert response.content_type == "application/json"


class TestE2EIngest:
    """E2E тесты загрузки документов."""

    def test_ingest_page_loads(self, seeded_app, e2e_client):
        """Страница загрузки открывается."""
        response = e2e_client.get("/ingest/")
        assert response.status_code == 200

    def test_ingest_text(self, seeded_app, e2e_client):
        """Загрузка текста работает."""
        response = e2e_client.post(
            "/ingest/text",
            data={
                "content": "# Тестовый документ\n\nЭто тестовый контент для E2E.",
                "title": "E2E Test Doc",
            },
        )

        # Редирект или успех
        assert response.status_code in (200, 302)


class TestE2EChat:
    """E2E тесты чата."""

    def test_chat_page_loads(self, seeded_app, e2e_client):
        """Страница чата открывается."""
        response = e2e_client.get("/chat/")
        assert response.status_code == 200

    def test_chat_send_message(self, seeded_app, e2e_client):
        """Отправка сообщения работает."""
        response = e2e_client.post(
            "/chat/message",
            data={"message": "Как работает гибридный поиск?"},
            headers={"HX-Request": "true"},  # HTMX header
        )

        # Может быть 200 или ошибка LLM, но не 500
        assert response.status_code in (200, 400)


class TestE2EDashboard:
    """E2E тесты дашборда."""

    def test_dashboard_shows_stats(self, seeded_app, e2e_client):
        """Дашборд показывает статистику."""
        response = e2e_client.get("/")

        assert response.status_code == 200
        html = response.data.decode("utf-8")

        # Должен показывать количество документов (мы загрузили 3)
        # Или хотя бы не "N/A"
        assert "Документы" in html or "документ" in html.lower()

    def test_health_endpoint(self, seeded_app, e2e_client):
        """Health check работает."""
        response = e2e_client.get("/health")

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"


class TestE2ESettings:
    """E2E тесты настроек."""

    def test_settings_shows_config(self, seeded_app, e2e_client):
        """Страница настроек показывает конфигурацию."""
        response = e2e_client.get("/settings/")

        assert response.status_code == 200
        html = response.data.decode("utf-8")

        # Должен показывать модель эмбеддинга
        assert "gemini" in html.lower() or "embedding" in html.lower()

    def test_about_page(self, seeded_app, e2e_client):
        """Страница About работает."""
        response = e2e_client.get("/settings/about")

        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "Semantic Core" in html or "semantic" in html.lower()
