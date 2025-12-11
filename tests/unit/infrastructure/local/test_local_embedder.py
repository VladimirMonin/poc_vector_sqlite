"""Unit-тесты для LocalEmbedder.

Тестирует LocalEmbedder с mock моделями для проверки:
- Инициализации и конфигурации
- Ленивой загрузки
- Генерации embeddings
- Обработки ошибок
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from semantic_core.infrastructure.local.embeddings import MODELS, LocalEmbedder

pytestmark = pytest.mark.mlx


class TestLocalEmbedderInit:
    """Тесты инициализации LocalEmbedder."""

    def test_init_with_valid_model(self):
        """Тест инициализации с валидной моделью."""
        embedder = LocalEmbedder("all-minilm")

        assert embedder._config == MODELS["all-minilm"]
        assert embedder._model is None  # Lazy loading
        assert embedder._tokenizer is None

    def test_init_with_all_models(self):
        """Тест инициализации со всеми предустановленными моделями."""
        for model_name in MODELS.keys():
            embedder = LocalEmbedder(model_name)
            assert embedder._config == MODELS[model_name]

    def test_init_with_unknown_model_raises_error(self):
        """Тест ошибки при неизвестной модели."""
        with pytest.raises(ValueError, match="Unknown model"):
            LocalEmbedder("non-existent-model")

    def test_init_with_device_parameter(self):
        """Тест инициализации с параметром device."""
        embedder = LocalEmbedder("all-minilm", device="mps")
        assert embedder._device == "mps"


class TestLocalEmbedderProperties:
    """Тесты properties (dimension, max_tokens)."""

    def test_dimension_all_minilm(self):
        """Тест dimension для all-minilm."""
        embedder = LocalEmbedder("all-minilm")
        assert embedder.dimension == 384

    def test_dimension_qwen3_embedding(self):
        """Тест dimension для qwen3-embedding."""
        embedder = LocalEmbedder("qwen3-embedding")
        assert embedder.dimension == 1024

    def test_max_tokens_all_minilm(self):
        """Тест max_tokens для all-minilm."""
        embedder = LocalEmbedder("all-minilm")
        assert embedder.max_tokens == 512

    def test_max_tokens_qwen3_embedding(self):
        """Тест max_tokens для qwen3-embedding."""
        embedder = LocalEmbedder("qwen3-embedding")
        assert embedder.max_tokens == 8192


class TestLocalEmbedderLazyLoading:
    """Тесты ленивой загрузки модели."""

    @patch("semantic_core.infrastructure.local.embeddings.embedder.load_model")
    def test_model_not_loaded_on_init(self, mock_load_model):
        """Тест что модель не загружается при инициализации."""
        embedder = LocalEmbedder("all-minilm")

        assert embedder._model is None
        mock_load_model.assert_not_called()

    @patch("semantic_core.infrastructure.local.embeddings.embedder.load_model")
    def test_model_loaded_on_first_use(self, mock_load_model):
        """Тест что модель загружается при первом использовании."""
        # Mock модели
        mock_model = MagicMock()
        mock_tokenizer = MagicMock()
        mock_load_model.return_value = (mock_model, mock_tokenizer)

        # Mock embedding generation
        mock_model.return_value.text_embeds = [np.zeros(384)]
        mock_tokenizer.batch_encode_plus.return_value = {
            "input_ids": MagicMock(),
            "attention_mask": MagicMock(),
        }

        embedder = LocalEmbedder("all-minilm")
        embedder.embed_query("test")

        mock_load_model.assert_called_once_with(MODELS["all-minilm"])
        assert embedder._model is mock_model
        assert embedder._tokenizer is mock_tokenizer

    @patch("semantic_core.infrastructure.local.embeddings.embedder.load_model")
    def test_model_loaded_only_once(self, mock_load_model):
        """Тест что модель загружается только один раз."""
        # Mock модели
        mock_model = MagicMock()
        mock_tokenizer = MagicMock()
        mock_load_model.return_value = (mock_model, mock_tokenizer)

        # Mock embedding generation
        mock_model.return_value.text_embeds = [np.zeros(384)]
        mock_tokenizer.batch_encode_plus.return_value = {
            "input_ids": MagicMock(),
            "attention_mask": MagicMock(),
        }

        embedder = LocalEmbedder("all-minilm")

        # Несколько вызовов
        embedder.embed_query("test1")
        embedder.embed_query("test2")

        # Загрузка должна быть только один раз
        mock_load_model.assert_called_once()


class TestLocalEmbedderEmbedQuery:
    """Тесты метода embed_query."""

    @patch("semantic_core.infrastructure.local.embeddings.embedder.load_model")
    def test_embed_query_returns_numpy_array(self, mock_load_model):
        """Тест что embed_query возвращает numpy array."""
        # Mock модели
        mock_model = MagicMock()
        mock_tokenizer = MagicMock()
        mock_load_model.return_value = (mock_model, mock_tokenizer)

        # Mock embedding
        expected_vector = np.random.rand(384)
        mock_model.return_value.text_embeds = [expected_vector]
        mock_tokenizer.batch_encode_plus.return_value = {
            "input_ids": MagicMock(),
            "attention_mask": MagicMock(),
        }

        embedder = LocalEmbedder("all-minilm")
        result = embedder.embed_query("test query")

        assert isinstance(result, np.ndarray)
        assert result.shape == (384,)
        np.testing.assert_array_equal(result, expected_vector)

    @patch("semantic_core.infrastructure.local.embeddings.embedder.load_model")
    def test_embed_query_with_empty_text_raises_error(self, mock_load_model):
        """Тест ошибки при пустом тексте."""
        embedder = LocalEmbedder("all-minilm")

        with pytest.raises(ValueError, match="text cannot be empty"):
            embedder.embed_query("")

    @patch("semantic_core.infrastructure.local.embeddings.embedder.load_model")
    def test_embed_query_adds_prefix_when_needed(self, mock_load_model):
        """Тест добавления префикса 'query:' для моделей, которым это нужно."""
        # Mock модели
        mock_model = MagicMock()
        mock_tokenizer = MagicMock()
        mock_load_model.return_value = (mock_model, mock_tokenizer)

        # Mock embedding
        mock_model.return_value.text_embeds = [np.zeros(384)]
        mock_tokenizer.batch_encode_plus.return_value = {
            "input_ids": MagicMock(),
            "attention_mask": MagicMock(),
        }

        # Для all-minilm не нужен префикс
        embedder = LocalEmbedder("all-minilm")
        embedder.embed_query("test")

        # Проверяем что токенизатор вызывается с оригинальным текстом
        mock_tokenizer.batch_encode_plus.assert_called_once()
        call_args = mock_tokenizer.batch_encode_plus.call_args[0]
        assert call_args[0] == ["test"]


class TestLocalEmbedderEmbedDocuments:
    """Тесты метода embed_documents."""

    @patch("semantic_core.infrastructure.local.embeddings.embedder.load_model")
    def test_embed_documents_returns_list_of_arrays(self, mock_load_model):
        """Тест что embed_documents возвращает список numpy arrays."""
        # Mock модели
        mock_model = MagicMock()
        mock_tokenizer = MagicMock()
        mock_load_model.return_value = (mock_model, mock_tokenizer)

        # Mock embeddings
        def mock_embed_side_effect(*args, **kwargs):
            result = MagicMock()
            result.text_embeds = [np.random.rand(384)]
            return result

        mock_model.side_effect = mock_embed_side_effect
        mock_tokenizer.batch_encode_plus.return_value = {
            "input_ids": MagicMock(),
            "attention_mask": MagicMock(),
        }

        embedder = LocalEmbedder("all-minilm")
        texts = ["doc1", "doc2", "doc3"]
        result = embedder.embed_documents(texts)

        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(v, np.ndarray) for v in result)
        assert all(v.shape == (384,) for v in result)

    @patch("semantic_core.infrastructure.local.embeddings.embedder.load_model")
    def test_embed_documents_with_empty_list_raises_error(self, mock_load_model):
        """Тест ошибки при пустом списке."""
        embedder = LocalEmbedder("all-minilm")

        with pytest.raises(ValueError, match="texts list cannot be empty"):
            embedder.embed_documents([])

    @patch("semantic_core.infrastructure.local.embeddings.embedder.load_model")
    def test_embed_documents_processes_each_text(self, mock_load_model):
        """Тест что каждый текст обрабатывается отдельно."""
        # Mock модели
        mock_model = MagicMock()
        mock_tokenizer = MagicMock()
        mock_load_model.return_value = (mock_model, mock_tokenizer)

        # Mock embeddings
        call_count = 0

        def mock_embed_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            result.text_embeds = [np.random.rand(384)]
            return result

        mock_model.side_effect = mock_embed_side_effect
        mock_tokenizer.batch_encode_plus.return_value = {
            "input_ids": MagicMock(),
            "attention_mask": MagicMock(),
        }

        embedder = LocalEmbedder("all-minilm")
        texts = ["doc1", "doc2"]
        embedder.embed_documents(texts)

        # Проверяем что модель вызвана для каждого документа
        assert call_count == 2


class TestLocalEmbedderErrorHandling:
    """Тесты обработки ошибок."""

    @patch("semantic_core.infrastructure.local.embeddings.embedder.load_model")
    def test_import_error_on_missing_mlx(self, mock_load_model):
        """Тест ImportError при отсутствии MLX."""
        mock_load_model.side_effect = ImportError("No module named 'mlx_embeddings'")

        embedder = LocalEmbedder("all-minilm")

        with pytest.raises(ImportError, match="MLX dependencies not installed"):
            embedder.embed_query("test")

    @patch("semantic_core.infrastructure.local.embeddings.embedder.load_model")
    def test_runtime_error_on_model_load_failure(self, mock_load_model):
        """Тест RuntimeError при ошибке загрузки модели."""
        mock_load_model.side_effect = RuntimeError("Failed to load model")

        embedder = LocalEmbedder("all-minilm")

        with pytest.raises(RuntimeError, match="Failed to load model"):
            embedder.embed_query("test")

    @patch("semantic_core.infrastructure.local.embeddings.embedder.load_model")
    def test_runtime_error_on_embedding_generation_failure(self, mock_load_model):
        """Тест RuntimeError при ошибке генерации embedding."""
        # Mock модели
        mock_model = MagicMock()
        mock_tokenizer = MagicMock()
        mock_load_model.return_value = (mock_model, mock_tokenizer)

        # Mock ошибки при генерации
        mock_tokenizer.batch_encode_plus.side_effect = RuntimeError("Tokenization failed")

        embedder = LocalEmbedder("all-minilm")

        with pytest.raises(RuntimeError, match="Failed to generate embedding"):
            embedder.embed_query("test")


class TestLocalEmbedderDifferentModels:
    """Тесты для разных моделей."""

    @pytest.mark.parametrize(
        "model_name,expected_dim,expected_max_tokens",
        [
            ("all-minilm", 384, 512),
            ("qwen3-embedding", 1024, 8192),
            ("bge-small", 384, 512),
        ],
    )
    def test_model_configs(self, model_name, expected_dim, expected_max_tokens):
        """Тест конфигураций разных моделей."""
        embedder = LocalEmbedder(model_name)

        assert embedder.dimension == expected_dim
        assert embedder.max_tokens == expected_max_tokens

    @patch("semantic_core.infrastructure.local.embeddings.embedder.load_model")
    def test_qwen3_uses_mlx_lm_backend(self, mock_load_model):
        """Тест что Qwen3 использует mlx-lm backend."""
        # Mock модели
        mock_model = MagicMock()
        mock_tokenizer = MagicMock()
        mock_load_model.return_value = (mock_model, mock_tokenizer)

        # Mock embedding
        mock_model.return_value.text_embeds = [np.zeros(1024)]
        mock_tokenizer.batch_encode_plus.return_value = {
            "input_ids": MagicMock(),
            "attention_mask": MagicMock(),
        }

        embedder = LocalEmbedder("qwen3-embedding")
        embedder.embed_query("test")

        # Проверяем что load_model вызван с правильным config
        mock_load_model.assert_called_once()
        config = mock_load_model.call_args[0][0]
        assert config.backend == "mlx-lm"
