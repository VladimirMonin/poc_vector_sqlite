"""Интеграционные тесты для LocalEmbedder с реальными моделями.

⚠️ ВНИМАНИЕ: Эти тесты требуют:
1. Apple Silicon (M1/M2/M3)
2. Установленные MLX зависимости: pip install semantic-core[local-embeddings]
3. ~500MB свободного места для моделей (загружаются автоматически)

Тесты маркированы @pytest.mark.integration и @pytest.mark.skipif для условного запуска.
"""

import sys

import numpy as np
import pytest

# Проверка доступности MLX
try:
    import mlx.core as mx

    MLX_AVAILABLE = True
except ImportError:
    MLX_AVAILABLE = False

# Проверка Apple Silicon
IS_APPLE_SILICON = (
    sys.platform == "darwin"
    and "arm" in str(getattr(sys, "implementation", "")).lower()
)

from semantic_core.infrastructure.local.embeddings import LocalEmbedder


@pytest.mark.integration
@pytest.mark.skipif(
    not MLX_AVAILABLE or not IS_APPLE_SILICON,
    reason="Requires MLX on Apple Silicon",
)
class TestLocalEmbedderIntegration:
    """Интеграционные тесты с реальными MLX моделями."""

    def test_all_minilm_real_embedding(self):
        """Тест реальной генерации embedding с all-MiniLM."""
        embedder = LocalEmbedder("all-minilm")

        # Генерация embedding
        vector = embedder.embed_query("Hello world")

        # Проверки
        assert isinstance(vector, np.ndarray)
        assert vector.shape == (384,)
        assert not np.all(vector == 0)  # Не нулевой вектор
        assert np.isfinite(vector).all()  # Все значения конечные

    def test_all_minilm_similarity(self):
        """Тест семантической близости с all-MiniLM."""
        embedder = LocalEmbedder("all-minilm")

        # Похожие тексты
        vec1 = embedder.embed_query("cat")
        vec2 = embedder.embed_query("kitten")
        vec3 = embedder.embed_query("database")

        # Косинусная близость
        def cosine_similarity(a, b):
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

        sim_cat_kitten = cosine_similarity(vec1, vec2)
        sim_cat_database = cosine_similarity(vec1, vec3)

        # cat и kitten должны быть ближе, чем cat и database
        assert sim_cat_kitten > sim_cat_database
        assert sim_cat_kitten > 0.5  # Достаточно высокая близость

    def test_all_minilm_batch_processing(self):
        """Тест батчевой обработки с all-MiniLM."""
        embedder = LocalEmbedder("all-minilm")

        texts = [
            "First document",
            "Second document",
            "Third document",
        ]

        vectors = embedder.embed_documents(texts)

        # Проверки
        assert len(vectors) == 3
        assert all(isinstance(v, np.ndarray) for v in vectors)
        assert all(v.shape == (384,) for v in vectors)
        assert all(np.isfinite(v).all() for v in vectors)

        # Векторы должны отличаться
        assert not np.array_equal(vectors[0], vectors[1])

    def test_all_minilm_lazy_loading(self):
        """Тест ленивой загрузки модели all-MiniLM."""
        embedder = LocalEmbedder("all-minilm")

        # До первого использования модель не загружена
        assert embedder._model is None

        # Первый вызов загружает модель
        embedder.embed_query("test")
        assert embedder._model is not None

        # Второй вызов использует уже загруженную модель
        model_ref = embedder._model
        embedder.embed_query("test2")
        assert embedder._model is model_ref  # Та же модель

    def test_all_minilm_multilingual(self):
        """Тест работы с разными языками (all-MiniLM)."""
        embedder = LocalEmbedder("all-minilm")

        # Разные языки
        vec_en = embedder.embed_query("Hello world")
        vec_ru = embedder.embed_query("Привет мир")
        vec_zh = embedder.embed_query("你好世界")

        # Все векторы валидные
        for vec in [vec_en, vec_ru, vec_zh]:
            assert isinstance(vec, np.ndarray)
            assert vec.shape == (384,)
            assert np.isfinite(vec).all()

    def test_dimension_and_max_tokens_properties(self):
        """Тест свойств dimension и max_tokens."""
        embedder = LocalEmbedder("all-minilm")

        assert embedder.dimension == 384
        assert embedder.max_tokens == 512


@pytest.mark.integration
@pytest.mark.skipif(
    not MLX_AVAILABLE or not IS_APPLE_SILICON,
    reason="Requires MLX on Apple Silicon",
)
@pytest.mark.slow
class TestLocalEmbedderQwen3Integration:
    """Интеграционные тесты с Qwen3-Embedding (тяжёлая модель ~335MB)."""

    def test_qwen3_real_embedding(self):
        """Тест реальной генерации embedding с Qwen3."""
        embedder = LocalEmbedder("qwen3-embedding")

        # Генерация embedding
        vector = embedder.embed_query("Hello world")

        # Проверки
        assert isinstance(vector, np.ndarray)
        assert vector.shape == (1024,)  # Qwen3 имеет 1024 измерения
        assert not np.all(vector == 0)
        assert np.isfinite(vector).all()

    def test_qwen3_long_context(self):
        """Тест длинного контекста с Qwen3 (8192 токена)."""
        embedder = LocalEmbedder("qwen3-embedding")

        # Длинный текст (больше 512 токенов all-MiniLM)
        long_text = " ".join(["word"] * 1000)

        vector = embedder.embed_query(long_text)

        # Должно работать без ошибок
        assert isinstance(vector, np.ndarray)
        assert vector.shape == (1024,)
        assert np.isfinite(vector).all()

    def test_qwen3_multilingual_similarity(self):
        """Тест кросс-языковой близости с Qwen3."""
        embedder = LocalEmbedder("qwen3-embedding")

        # Одинаковое слово на разных языках
        vec_en = embedder.embed_query("cat")
        vec_ru = embedder.embed_query("кошка")
        vec_zh = embedder.embed_query("猫")

        def cosine_similarity(a, b):
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

        # Проверяем кросс-языковую близость
        sim_en_ru = cosine_similarity(vec_en, vec_ru)
        sim_en_zh = cosine_similarity(vec_en, vec_zh)

        # Должна быть некоторая близость (Qwen3 мультиязычная)
        # Примечание: точные значения зависят от модели
        assert sim_en_ru > 0.0
        assert sim_en_zh > 0.0


@pytest.mark.integration
@pytest.mark.skipif(
    not MLX_AVAILABLE or not IS_APPLE_SILICON,
    reason="Requires MLX on Apple Silicon",
)
class TestLocalEmbedderModelsComparison:
    """Сравнительные тесты разных моделей."""

    def test_different_dimensions(self):
        """Тест что разные модели имеют разные размерности."""
        embedder_minilm = LocalEmbedder("all-minilm")
        embedder_qwen3 = LocalEmbedder("qwen3-embedding")

        vec_minilm = embedder_minilm.embed_query("test")
        vec_qwen3 = embedder_qwen3.embed_query("test")

        # Разные размерности
        assert vec_minilm.shape == (384,)
        assert vec_qwen3.shape == (1024,)

    def test_different_max_tokens(self):
        """Тест что разные модели имеют разные max_tokens."""
        embedder_minilm = LocalEmbedder("all-minilm")
        embedder_qwen3 = LocalEmbedder("qwen3-embedding")

        assert embedder_minilm.max_tokens == 512
        assert embedder_qwen3.max_tokens == 8192

    def test_model_isolation(self):
        """Тест изоляции моделей (каждый embedder загружает свою модель)."""
        embedder1 = LocalEmbedder("all-minilm")
        embedder2 = LocalEmbedder("all-minilm")

        # Генерация embeddings
        embedder1.embed_query("test1")
        embedder2.embed_query("test2")

        # Разные инстансы моделей
        assert embedder1._model is not embedder2._model
