"""Unit-тесты для SentenceTransformerEmbedder.

Тестирует SentenceTransformerEmbedder согласно требованиям Phase 15.2.
Использует mock для sentence_transformers чтобы избежать загрузки реальных моделей.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from semantic_core.infrastructure.local import SentenceTransformerEmbedder
from semantic_core.interfaces.embedder import BaseEmbedder

pytestmark = [pytest.mark.cuda, pytest.mark.requires_sentence_transformers]


class TestSentenceTransformerEmbedderInit:
    """Тесты инициализации SentenceTransformerEmbedder."""

    def test_embedder_initialization(self):
        """Проверка инициализации с разными параметрами."""
        embedder = SentenceTransformerEmbedder(
            model_name="all-MiniLM-L6-v2", device="cpu"
        )
        assert embedder.model_name == "all-MiniLM-L6-v2"
        assert embedder.device == "cpu"
        assert embedder.normalize is True  # Default

    def test_embedder_initialization_with_normalize_false(self):
        """Проверка инициализации с normalize=False."""
        embedder = SentenceTransformerEmbedder(normalize=False)
        assert embedder.normalize is False

    def test_embedder_initialization_with_cache_folder(self):
        """Проверка инициализации с кастомной папкой кеша."""
        embedder = SentenceTransformerEmbedder(cache_folder="/tmp/models")
        assert embedder.cache_folder == "/tmp/models"


class TestSentenceTransformerEmbedderLazyLoading:
    """Тесты ленивой загрузки модели."""

    @patch(
        "semantic_core.infrastructure.local.sentence_transformer_embedder.SentenceTransformer"
    )
    def test_model_not_loaded_on_init(self, mock_st):
        """Проверка что модель НЕ загружается при инициализации."""
        embedder = SentenceTransformerEmbedder()
        assert embedder._model is None
        mock_st.assert_not_called()

    @patch(
        "semantic_core.infrastructure.local.sentence_transformer_embedder.SentenceTransformer"
    )
    def test_model_loaded_on_first_use(self, mock_st):
        """Проверка что модель загружается при первом использовании."""
        # Mock модели
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.max_seq_length = 256
        mock_model.encode.return_value = np.random.rand(384)
        mock_st.return_value = mock_model

        embedder = SentenceTransformerEmbedder("all-MiniLM-L6-v2")
        embedder.embed("test")

        mock_st.assert_called_once_with(
            "all-MiniLM-L6-v2", device="cpu", cache_folder=None
        )

    @patch(
        "semantic_core.infrastructure.local.sentence_transformer_embedder.SentenceTransformer"
    )
    def test_model_loading_caching(self, mock_st):
        """Проверка что модель загружается один раз."""
        # Mock модели
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.max_seq_length = 256
        mock_model.encode.return_value = np.random.rand(384)
        mock_st.return_value = mock_model

        embedder = SentenceTransformerEmbedder()

        # Несколько вызовов
        embedder.embed("First text")
        embedder.embed("Second text")

        # Модель загружается только один раз
        assert mock_st.call_count == 1


class TestSentenceTransformerEmbedderEmbed:
    """Тесты метода embed (одиночный текст)."""

    @patch(
        "semantic_core.infrastructure.local.sentence_transformer_embedder.SentenceTransformer"
    )
    def test_embed_single_text(self, mock_st):
        """Проверка эмбеддинга одного текста."""
        # Mock модели
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.max_seq_length = 256
        expected_vector = np.random.rand(384)
        mock_model.encode.return_value = expected_vector
        mock_st.return_value = mock_model

        embedder = SentenceTransformerEmbedder(model_name="all-MiniLM-L6-v2")
        embedding = embedder.embed("Semantic search example")

        assert isinstance(embedding, list)
        assert len(embedding) == 384
        assert all(isinstance(x, float) for x in embedding)

    @patch(
        "semantic_core.infrastructure.local.sentence_transformer_embedder.SentenceTransformer"
    )
    def test_empty_text_handling(self, mock_st):
        """Проверка обработки пустого текста."""
        # Mock модели
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.max_seq_length = 256
        mock_model.encode.return_value = np.random.rand(384)
        mock_st.return_value = mock_model

        embedder = SentenceTransformerEmbedder()

        # Пустая строка должна вернуть валидный эмбеддинг
        embedding = embedder.embed("")
        assert len(embedding) == embedder.dimension


class TestSentenceTransformerEmbedderEmbedBatch:
    """Тесты метода embed_batch."""

    @patch(
        "semantic_core.infrastructure.local.sentence_transformer_embedder.SentenceTransformer"
    )
    def test_embed_batch_texts(self, mock_st):
        """Проверка батчинга."""
        # Mock модели
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.max_seq_length = 256
        mock_model.encode.return_value = np.random.rand(3, 384)
        mock_st.return_value = mock_model

        embedder = SentenceTransformerEmbedder(model_name="all-MiniLM-L6-v2")
        texts = ["First document", "Second document", "Third document"]
        embeddings = embedder.embed_batch(texts)

        assert len(embeddings) == 3
        assert all(len(emb) == embedder.dimension for emb in embeddings)

    @patch(
        "semantic_core.infrastructure.local.sentence_transformer_embedder.SentenceTransformer"
    )
    def test_batch_vs_single_consistency(self, mock_st):
        """Проверка что batch даёт те же результаты что и single."""
        # Mock модели
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.max_seq_length = 256

        # Фиксированные векторы для консистентности
        single_vectors = [np.random.rand(384) for _ in range(3)]
        batch_vectors = np.array(single_vectors)

        def encode_side_effect(texts, **kwargs):
            if isinstance(texts, str):
                # Одиночный текст
                idx = ["First", "Second", "Third"].index(texts)
                return single_vectors[idx]
            else:
                # Батч
                return batch_vectors

        mock_model.encode.side_effect = encode_side_effect
        mock_st.return_value = mock_model

        embedder = SentenceTransformerEmbedder()
        texts = ["First", "Second", "Third"]

        # Батчем
        batch_embeddings = embedder.embed_batch(texts)

        # По одному
        single_embeddings = [embedder.embed(text) for text in texts]

        # Должны совпадать
        for batch_emb, single_emb in zip(batch_embeddings, single_embeddings):
            assert np.allclose(batch_emb, single_emb, rtol=1e-5)


class TestSentenceTransformerEmbedderProperties:
    """Тесты свойств dimension и max_tokens."""

    @patch(
        "semantic_core.infrastructure.local.sentence_transformer_embedder.SentenceTransformer"
    )
    def test_dimension_property_matches_model(self, mock_st):
        """Проверка что dimension совпадает с реальной размерностью."""
        # Mock модели
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.max_seq_length = 256
        mock_model.encode.return_value = np.random.rand(384)
        mock_st.return_value = mock_model

        embedder = SentenceTransformerEmbedder(model_name="all-MiniLM-L6-v2")

        # Dimension через property
        assert embedder.dimension == 384

        # Проверка через реальный эмбеддинг
        embedding = embedder.embed("test")
        assert len(embedding) == embedder.dimension

    @patch(
        "semantic_core.infrastructure.local.sentence_transformer_embedder.SentenceTransformer"
    )
    def test_max_tokens_property(self, mock_st):
        """Проверка свойства max_tokens."""
        # Mock модели
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.max_seq_length = 256
        mock_st.return_value = mock_model

        embedder = SentenceTransformerEmbedder(model_name="all-MiniLM-L6-v2")

        assert embedder.max_tokens == 256
        assert isinstance(embedder.max_tokens, int)

    @patch(
        "semantic_core.infrastructure.local.sentence_transformer_embedder.SentenceTransformer"
    )
    def test_different_models(self, mock_st):
        """Проверка загрузки разных моделей."""
        models_config = [
            ("all-MiniLM-L6-v2", 384, 256),
            ("all-mpnet-base-v2", 768, 384),
        ]

        for model_name, expected_dim, expected_max_tokens in models_config:
            # Mock модели
            mock_model = MagicMock()
            mock_model.get_sentence_embedding_dimension.return_value = expected_dim
            mock_model.max_seq_length = expected_max_tokens
            mock_st.return_value = mock_model

            embedder = SentenceTransformerEmbedder(model_name=model_name)
            assert embedder.dimension == expected_dim
            assert embedder.max_tokens == expected_max_tokens


class TestSentenceTransformerEmbedderNormalization:
    """Тесты нормализации векторов."""

    @patch(
        "semantic_core.infrastructure.local.sentence_transformer_embedder.SentenceTransformer"
    )
    def test_normalize_embeddings(self, mock_st):
        """Проверка нормализации векторов."""
        # Mock модели
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.max_seq_length = 256

        # Ненормализованный вектор
        unnormalized = np.random.rand(384) * 10
        # Нормализованный вектор
        normalized = unnormalized / np.linalg.norm(unnormalized)

        def encode_side_effect(text, normalize_embeddings=False, **kwargs):
            if normalize_embeddings:
                return normalized
            return unnormalized

        mock_model.encode.side_effect = encode_side_effect
        mock_st.return_value = mock_model

        embedder = SentenceTransformerEmbedder(normalize=True)
        embedding = embedder.embed("Normalize test")

        # Проверка L2 нормы (должна быть ~1.0)
        norm = np.linalg.norm(embedding)
        assert abs(norm - 1.0) < 0.01  # Допуск на погрешность

    @patch(
        "semantic_core.infrastructure.local.sentence_transformer_embedder.SentenceTransformer"
    )
    def test_no_normalize(self, mock_st):
        """Проверка что без нормализации векторы не нормализованы."""
        # Mock модели
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.max_seq_length = 256

        # Ненормализованный вектор (норма != 1)
        unnormalized = np.random.rand(384) * 10
        mock_model.encode.return_value = unnormalized
        mock_st.return_value = mock_model

        embedder = SentenceTransformerEmbedder(normalize=False)
        embedding = embedder.embed("No normalize test")

        norm = np.linalg.norm(embedding)
        assert abs(norm - 1.0) > 0.1  # Не нормализован


class TestSentenceTransformerEmbedderDeviceSelection:
    """Тесты выбора устройства."""

    @patch(
        "semantic_core.infrastructure.local.sentence_transformer_embedder.SentenceTransformer"
    )
    def test_device_selection_cpu(self, mock_st):
        """Проверка работы на CPU."""
        # Mock модели
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.max_seq_length = 256
        mock_model.encode.return_value = np.random.rand(384)
        mock_st.return_value = mock_model

        embedder = SentenceTransformerEmbedder(device="cpu")
        embedding = embedder.embed("CPU test")

        assert len(embedding) == embedder.dimension
        mock_st.assert_called_with("all-MiniLM-L6-v2", device="cpu", cache_folder=None)

    @patch(
        "semantic_core.infrastructure.local.sentence_transformer_embedder.SentenceTransformer"
    )
    def test_device_selection_cuda(self, mock_st):
        """Проверка инициализации с device='cuda'."""
        # Mock модели
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.max_seq_length = 256
        mock_model.encode.return_value = np.random.rand(384)
        mock_st.return_value = mock_model

        embedder = SentenceTransformerEmbedder(device="cuda")
        embedder.embed("GPU test")

        mock_st.assert_called_with("all-MiniLM-L6-v2", device="cuda", cache_folder=None)


class TestSentenceTransformerEmbedderInterfaceCompliance:
    """Тесты соответствия интерфейсу BaseEmbedder."""

    def test_interface_compliance(self):
        """Проверка соответствия интерфейсу BaseEmbedder."""
        embedder = SentenceTransformerEmbedder()
        assert isinstance(embedder, BaseEmbedder)
        assert hasattr(embedder, "dimension")
        assert hasattr(embedder, "max_tokens")
        assert hasattr(embedder, "embed")
        assert hasattr(embedder, "embed_batch")
        assert hasattr(embedder, "embed_documents")
        assert hasattr(embedder, "embed_query")


class TestSentenceTransformerEmbedderBaseEmbedderMethods:
    """Тесты методов из BaseEmbedder (embed_documents, embed_query)."""

    @patch(
        "semantic_core.infrastructure.local.sentence_transformer_embedder.SentenceTransformer"
    )
    def test_embed_documents_returns_numpy_arrays(self, mock_st):
        """Тест что embed_documents возвращает numpy arrays."""
        # Mock модели
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.max_seq_length = 256
        mock_model.encode.return_value = np.random.rand(3, 384)
        mock_st.return_value = mock_model

        embedder = SentenceTransformerEmbedder()
        texts = ["doc1", "doc2", "doc3"]
        result = embedder.embed_documents(texts)

        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(v, np.ndarray) for v in result)
        assert all(v.shape == (384,) for v in result)

    @patch(
        "semantic_core.infrastructure.local.sentence_transformer_embedder.SentenceTransformer"
    )
    def test_embed_documents_empty_list_raises_error(self, mock_st):
        """Тест ошибки при пустом списке."""
        embedder = SentenceTransformerEmbedder()

        with pytest.raises(ValueError, match="texts list cannot be empty"):
            embedder.embed_documents([])

    @patch(
        "semantic_core.infrastructure.local.sentence_transformer_embedder.SentenceTransformer"
    )
    def test_embed_query_returns_numpy_array(self, mock_st):
        """Тест что embed_query возвращает numpy array."""
        # Mock модели
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.max_seq_length = 256
        mock_model.encode.return_value = np.random.rand(384)
        mock_st.return_value = mock_model

        embedder = SentenceTransformerEmbedder()
        result = embedder.embed_query("test query")

        assert isinstance(result, np.ndarray)
        assert result.shape == (384,)

    @patch(
        "semantic_core.infrastructure.local.sentence_transformer_embedder.SentenceTransformer"
    )
    def test_embed_query_empty_text_raises_error(self, mock_st):
        """Тест ошибки при пустом тексте."""
        embedder = SentenceTransformerEmbedder()

        with pytest.raises(ValueError, match="text cannot be empty"):
            embedder.embed_query("")


class TestSentenceTransformerEmbedderErrorHandling:
    """Тесты обработки ошибок."""

    @patch(
        "semantic_core.infrastructure.local.sentence_transformer_embedder.SentenceTransformer"
    )
    def test_import_error_on_missing_library(self, mock_st):
        """Тест ImportError при отсутствии sentence-transformers."""
        # Симулируем отсутствие библиотеки
        with patch(
            "semantic_core.infrastructure.local.sentence_transformer_embedder.SentenceTransformer",
            side_effect=ImportError("No module named 'sentence_transformers'"),
        ):
            embedder = SentenceTransformerEmbedder()

            with pytest.raises(
                ImportError, match="sentence-transformers not installed"
            ):
                embedder.embed("test")

    @patch(
        "semantic_core.infrastructure.local.sentence_transformer_embedder.SentenceTransformer"
    )
    def test_runtime_error_on_model_load_failure(self, mock_st):
        """Тест RuntimeError при ошибке загрузки модели."""
        mock_st.side_effect = RuntimeError("Failed to load model")

        embedder = SentenceTransformerEmbedder()

        with pytest.raises(RuntimeError, match="Failed to load model"):
            embedder.embed("test")

    @patch(
        "semantic_core.infrastructure.local.sentence_transformer_embedder.SentenceTransformer"
    )
    def test_runtime_error_on_encoding_failure(self, mock_st):
        """Тест RuntimeError при ошибке encoding."""
        # Mock модели
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.max_seq_length = 256
        mock_model.encode.side_effect = RuntimeError("Encoding failed")
        mock_st.return_value = mock_model

        embedder = SentenceTransformerEmbedder()

        with pytest.raises(RuntimeError, match="Failed to generate embedding"):
            embedder.embed("test")


class TestSentenceTransformerEmbedderConsistency:
    """Тесты консистентности embeddings."""

    @patch(
        "semantic_core.infrastructure.local.sentence_transformer_embedder.SentenceTransformer"
    )
    def test_embedding_consistency(self, mock_st):
        """Проверка что одинаковый текст даёт одинаковый эмбеддинг."""
        # Mock модели
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.max_seq_length = 256

        # Фиксированный вектор
        fixed_vector = np.random.rand(384)
        mock_model.encode.return_value = fixed_vector
        mock_st.return_value = mock_model

        embedder = SentenceTransformerEmbedder()

        emb1 = embedder.embed("Consistency test")
        emb2 = embedder.embed("Consistency test")

        # Должны быть идентичны
        assert np.allclose(emb1, emb2, rtol=1e-5)

    @patch(
        "semantic_core.infrastructure.local.sentence_transformer_embedder.SentenceTransformer"
    )
    def test_long_text_truncation(self, mock_st):
        """Проверка что длинный текст обрезается до max_tokens."""
        # Mock модели
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.max_seq_length = 256
        mock_model.encode.return_value = np.random.rand(384)
        mock_st.return_value = mock_model

        embedder = SentenceTransformerEmbedder()

        # Создаём очень длинный текст
        long_text = "word " * 1000  # Гораздо больше max_tokens

        # Не должно быть ошибки, текст обрезается
        embedding = embedder.embed(long_text)
        assert len(embedding) == embedder.dimension
