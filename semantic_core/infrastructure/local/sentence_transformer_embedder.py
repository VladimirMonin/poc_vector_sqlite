"""Универсальный embedder через sentence-transformers.

Кросс-платформенная реализация BaseEmbedder для CPU/GPU.
Работает на любой ОС (Linux, Windows, macOS).
"""

from typing import List, Literal, Optional

import numpy as np

from semantic_core.interfaces.embedder import BaseEmbedder
from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)


class SentenceTransformerEmbedder(BaseEmbedder):
    """Локальные embeddings через sentence-transformers.

    Универсальное решение для всех платформ (CPU/GPU).
    Поддерживает сотни предобученных моделей с HuggingFace.

    Attributes:
        model_name: Название модели (all-MiniLM-L6-v2, all-mpnet-base-v2, etc).
        device: Устройство для вычислений (cpu/cuda/mps).
        normalize: Нормализовать векторы для косинусного сходства.

    Examples:
        >>> # Быстрая английская модель
        >>> embedder = SentenceTransformerEmbedder("all-MiniLM-L6-v2")
        >>> vector = embedder.embed("Hello world")
        >>> vector.shape
        (384,)

        >>> # Мультиязычная модель
        >>> embedder = SentenceTransformerEmbedder(
        ...     "paraphrase-multilingual-mpnet-base-v2"
        ... )
        >>> vectors = embedder.embed_batch(["Hello", "Привет", "你好"])
        >>> len(vectors)
        3

    Note:
        Требует установки: pip install sentence-transformers
        Модели загружаются автоматически из HuggingFace при первом использовании.
    """

    # Рекомендуемые модели с характеристиками
    RECOMMENDED_MODELS = {
        "all-MiniLM-L6-v2": {
            "dimension": 384,
            "max_tokens": 256,
            "languages": ["en"],
            "description": "Быстрая английская модель (⭐⭐⭐ качество, 🚀🚀🚀 скорость)",
        },
        "all-mpnet-base-v2": {
            "dimension": 768,
            "max_tokens": 384,
            "languages": ["en"],
            "description": "Качественная английская модель (⭐⭐⭐⭐ качество, 🚀🚀 скорость)",
        },
        "paraphrase-multilingual-mpnet-base-v2": {
            "dimension": 768,
            "max_tokens": 128,
            "languages": ["multilingual"],
            "description": "Мультиязычная модель (⭐⭐⭐⭐ качество, 🚀🚀 скорость)",
        },
        "sentence-transformers/LaBSE": {
            "dimension": 768,
            "max_tokens": 256,
            "languages": ["109 languages"],
            "description": "Максимальная мультиязычность (⭐⭐⭐⭐⭐ качество, 🚀 скорость)",
        },
    }

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: Literal["cpu", "cuda", "mps"] = "cpu",
        normalize: bool = True,
        cache_folder: Optional[str] = None,
    ):
        """Инициализация SentenceTransformerEmbedder.

        Args:
            model_name: Название модели с HuggingFace.
            device: Устройство (cpu/cuda/mps).
            normalize: Нормализовать векторы (L2 norm = 1.0).
            cache_folder: Папка для кеширования моделей.

        Raises:
            ImportError: Если sentence-transformers не установлен.
            RuntimeError: Если модель не найдена или device недоступен.

        Examples:
            >>> embedder = SentenceTransformerEmbedder()  # Дефолт: all-MiniLM-L6-v2
            >>> embedder = SentenceTransformerEmbedder("all-mpnet-base-v2", device="cuda")
        """
        self.model_name = model_name
        self.device = device
        self.normalize = normalize
        self.cache_folder = cache_folder

        self._model = None  # Lazy loading
        self._dimension: Optional[int] = None
        self._max_tokens: Optional[int] = None

        logger.bind(
            model_name=model_name, device=device, normalize=normalize
        ).info("🧠 SentenceTransformerEmbedder initialized")

    def _ensure_loaded(self) -> None:
        """Ленивая загрузка модели при первом использовании.

        Raises:
            ImportError: Если sentence-transformers не установлен.
            RuntimeError: Если загрузка модели не удалась.
        """
        if self._model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            logger.error(
                "❌ sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
            raise ImportError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            ) from e

        try:
            logger.info(f"🧠 Loading model {self.model_name} on {self.device}...")

            self._model = SentenceTransformer(
                self.model_name,
                device=self.device,
                cache_folder=self.cache_folder,
            )

            # Кэшируем dimension и max_tokens
            self._dimension = self._model.get_sentence_embedding_dimension()
            self._max_tokens = self._model.max_seq_length

            logger.bind(
                dimension=self._dimension, max_tokens=self._max_tokens
            ).info(f"✅ Model {self.model_name} loaded successfully")

        except Exception as e:
            logger.bind(error=str(e)).error(
                f"❌ Failed to load model {self.model_name}"
            )
            raise RuntimeError(f"Failed to load model {self.model_name}: {e}") from e

    def embed(self, text: str) -> List[float]:
        """Генерация embedding для одного текста.

        Args:
            text: Текст для векторизации.

        Returns:
            Список float (вектор).

        Raises:
            RuntimeError: Если embedding generation не удался.

        Examples:
            >>> embedder = SentenceTransformerEmbedder()
            >>> vector = embedder.embed("Semantic search example")
            >>> len(vector)
            384
        """
        self._ensure_loaded()

        try:
            embedding = self._model.encode(
                text,
                normalize_embeddings=self.normalize,
                convert_to_numpy=True,
            )

            return embedding.tolist()

        except Exception as e:
            logger.bind(error=str(e)).error("❌ Failed to generate embedding")
            raise RuntimeError(f"Failed to generate embedding: {e}") from e

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Генерация embeddings для батча текстов (эффективнее одиночных).

        Args:
            texts: Список текстов для векторизации.

        Returns:
            Список векторов.

        Raises:
            RuntimeError: Если batch embedding не удался.

        Examples:
            >>> embedder = SentenceTransformerEmbedder()
            >>> vectors = embedder.embed_batch(["doc1", "doc2", "doc3"])
            >>> len(vectors)
            3
        """
        self._ensure_loaded()

        try:
            logger.bind(batch_size=len(texts)).debug(
                f"🧠 Generating embeddings for batch of {len(texts)} texts"
            )

            embeddings = self._model.encode(
                texts,
                normalize_embeddings=self.normalize,
                convert_to_numpy=True,
                show_progress_bar=False,
            )

            return embeddings.tolist()

        except Exception as e:
            logger.bind(error=str(e), batch_size=len(texts)).error(
                "❌ Failed to generate batch embeddings"
            )
            raise RuntimeError(f"Failed to generate batch embeddings: {e}") from e

    def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        """Генерирует эмбеддинги для списка документов.

        Args:
            texts: Список текстов для векторизации.

        Returns:
            Список numpy массивов (векторов).

        Raises:
            ValueError: Если texts пустой.
            RuntimeError: Если embedding generation не удался.
        """
        if not texts:
            raise ValueError("texts list cannot be empty")

        embeddings_list = self.embed_batch(texts)
        return [np.array(emb) for emb in embeddings_list]

    def embed_query(self, text: str) -> np.ndarray:
        """Генерирует эмбеддинг для поискового запроса.

        Args:
            text: Текст запроса.

        Returns:
            Numpy массив (вектор).

        Raises:
            ValueError: Если text пустой.
            RuntimeError: Если embedding generation не удался.
        """
        if not text:
            raise ValueError("text cannot be empty")

        embedding_list = self.embed(text)
        return np.array(embedding_list)

    @property
    def dimension(self) -> int:
        """Размерность выходного вектора.

        Returns:
            Размерность (384 для all-MiniLM, 768 для mpnet/LaBSE).

        Examples:
            >>> SentenceTransformerEmbedder("all-MiniLM-L6-v2").dimension
            384
            >>> SentenceTransformerEmbedder("all-mpnet-base-v2").dimension
            768
        """
        if self._dimension is None:
            self._ensure_loaded()
        return self._dimension

    @property
    def max_tokens(self) -> int:
        """Максимальное количество токенов на вход.

        Returns:
            Лимит токенов (256 для all-MiniLM, 384 для mpnet, etc).

        Examples:
            >>> SentenceTransformerEmbedder("all-MiniLM-L6-v2").max_tokens
            256
        """
        if self._max_tokens is None:
            self._ensure_loaded()
        return self._max_tokens
