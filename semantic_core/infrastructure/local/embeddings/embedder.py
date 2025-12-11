"""Локальный embedder через MLX.

Реализация BaseEmbedder для локальных моделей на Apple Silicon.
Поддерживает all-MiniLM, Qwen3-Embedding и другие MLX модели.
"""

from typing import Any, Optional

import numpy as np

from semantic_core.infrastructure.local.embeddings.models import (
    MODELS,
    ModelConfig,
    embed_with_model,
    load_model,
)
from semantic_core.interfaces.embedder import BaseEmbedder


class LocalEmbedder(BaseEmbedder):
    """Локальные embeddings через MLX.

    Поддерживает предустановленные модели (all-minilm, qwen3-embedding, bge-small)
    с ленивой загрузкой для экономии памяти.

    Attributes:
        config: Конфигурация модели (размерность, max_tokens, backend).

    Examples:
        >>> # Использование предустановленной модели
        >>> embedder = LocalEmbedder("all-minilm")
        >>> vector = embedder.embed_query("Hello world")
        >>> vector.shape
        (384,)

        >>> # Batch обработка
        >>> embedder = LocalEmbedder("qwen3-embedding")
        >>> vectors = embedder.embed_documents(["doc1", "doc2"])
        >>> len(vectors)
        2

    Note:
        Требует установки `pip install semantic-core[local-embeddings]`.
        Работает только на Apple Silicon (M1/M2/M3).
    """

    def __init__(
        self,
        model: str = "all-minilm",
        device: Optional[str] = None,
    ):
        """Инициализация LocalEmbedder.

        Args:
            model: Ключ из MODELS или кастомный путь HuggingFace.
            device: Устройство для вычислений (не используется в MLX).

        Raises:
            ValueError: Если модель неизвестна.
            ImportError: Если MLX библиотеки не установлены.

        Examples:
            >>> embedder = LocalEmbedder("all-minilm")
            >>> embedder.dimension
            384
        """
        if model not in MODELS:
            raise ValueError(
                f"Unknown model: {model}. "
                f"Available models: {list(MODELS.keys())}"
            )

        self._config: ModelConfig = MODELS[model]
        self._model: Optional[Any] = None
        self._tokenizer: Optional[Any] = None
        self._device = device  # Для совместимости, MLX не требует явного device

    def _ensure_loaded(self) -> None:
        """Ленивая загрузка модели при первом использовании.

        Raises:
            ImportError: Если MLX библиотеки не установлены.
            RuntimeError: Если загрузка модели не удалась.
        """
        if self._model is None:
            self._model, self._tokenizer = load_model(self._config)

    def _embed_single(self, text: str) -> np.ndarray:
        """Генерация embedding для одного текста.

        Args:
            text: Текст для векторизации.

        Returns:
            Numpy массив с эмбеддингом.

        Raises:
            RuntimeError: Если embedding generation не удался.
        """
        return embed_with_model(
            self._model,
            self._tokenizer,
            text,
            max_length=self._config.max_tokens,
            backend=self._config.backend,
        )

    def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        """Генерирует эмбеддинги для списка документов.

        Args:
            texts: Список текстов для векторизации.

        Returns:
            Список numpy массивов (векторов).

        Raises:
            ValueError: Если texts пустой.
            RuntimeError: Если embedding generation не удался.

        Examples:
            >>> embedder = LocalEmbedder("all-minilm")
            >>> vectors = embedder.embed_documents(["doc1", "doc2"])
            >>> len(vectors)
            2
            >>> vectors[0].shape
            (384,)
        """
        if not texts:
            raise ValueError("texts list cannot be empty")

        self._ensure_loaded()

        embeddings = []
        for text in texts:
            emb = self._embed_single(text)
            embeddings.append(emb)

        return embeddings

    def embed_query(self, text: str) -> np.ndarray:
        """Генерирует эмбеддинг для поискового запроса.

        Args:
            text: Текст запроса.

        Returns:
            Numpy массив (вектор).

        Raises:
            ValueError: Если text пустой.
            RuntimeError: Если embedding generation не удался.

        Examples:
            >>> embedder = LocalEmbedder("qwen3-embedding")
            >>> vector = embedder.embed_query("search query")
            >>> vector.shape
            (1024,)

        Note:
            Для некоторых моделей добавляет префикс "query:" согласно config.
        """
        if not text:
            raise ValueError("text cannot be empty")

        self._ensure_loaded()

        # Некоторые модели требуют префикс для query
        if self._config.needs_query_prefix:
            text = f"query: {text}"

        return self._embed_single(text)

    @property
    def dimension(self) -> int:
        """Размерность выходного вектора.

        Returns:
            Размерность (384 для all-minilm, 1024 для qwen3-embedding).

        Examples:
            >>> LocalEmbedder("all-minilm").dimension
            384
            >>> LocalEmbedder("qwen3-embedding").dimension
            1024
        """
        return self._config.dimension

    @property
    def max_tokens(self) -> int:
        """Максимальное количество токенов на вход.

        Returns:
            Лимит токенов (512 для all-minilm, 8192 для qwen3-embedding).

        Examples:
            >>> LocalEmbedder("all-minilm").max_tokens
            512
            >>> LocalEmbedder("qwen3-embedding").max_tokens
            8192
        """
        return self._config.max_tokens
