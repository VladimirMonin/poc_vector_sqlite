"""Реализация BaseEmbedder для Google Gemini API.

Классы:
    GeminiEmbedder
        Адаптер для генерации эмбеддингов через Gemini.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Literal

import google.generativeai as genai
import numpy as np

from semantic_core.interfaces import BaseEmbedder
from semantic_core.utils.logger import get_logger

if TYPE_CHECKING:
    from semantic_core.config import SemanticConfig

logger = get_logger(__name__)


TaskType = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]


class GeminiEmbedder(BaseEmbedder):
    """Адаптер для Google Gemini Embedding API.

    Реализует BaseEmbedder с поддержкой:
    - Асимметричного поиска (разные task_type).
    - MRL (Matryoshka Representation Learning).
    - Автоматической нормализации векторов.

    Attributes:
        model_name: Название модели (по умолчанию 'models/gemini-embedding-001').
        dimension: Размерность векторов (768 для MRL).
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "models/gemini-embedding-001",
        dimension: int = 768,
    ):
        """Инициализация адаптера Gemini.

        Args:
            api_key: API ключ Google Gemini.
            model_name: Модель для генерации.
            dimension: Размерность векторов (MRL).
        """
        self.api_key = api_key
        self.model_name = model_name
        self.dimension = dimension

        # Конфигурируем API
        genai.configure(api_key=self.api_key)
        logger.debug(
            "Embedder initialized",
            model=model_name,
            dimension=dimension,
        )

    @classmethod
    def from_config(cls, config: SemanticConfig) -> GeminiEmbedder:
        """Создаёт embedder из конфигурации.

        Factory-метод для создания экземпляра с параметрами из SemanticConfig.

        Args:
            config: Конфигурация Semantic Core.

        Returns:
            Инициализированный GeminiEmbedder.

        Raises:
            ValueError: Если API ключ не настроен.

        Example:
            >>> from semantic_core.config import get_config
            >>> config = get_config()
            >>> embedder = GeminiEmbedder.from_config(config)
        """
        return cls(
            api_key=config.require_api_key(),
            model_name=config.embedding_model,
            dimension=config.embedding_dimension,
        )

    def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        """Генерирует эмбеддинги для списка документов.

        Args:
            texts: Список текстов для векторизации.

        Returns:
            Список numpy массивов (векторов).

        Raises:
            ValueError: Если texts пустой.
            RuntimeError: Если API вернул ошибку.
        """
        if not texts:
            logger.warning("Empty texts list provided")
            raise ValueError("Список текстов не может быть пустым")

        logger.debug(
            "Embedding documents",
            count=len(texts),
            model=self.model_name,
        )

        start_time = time.perf_counter()
        vectors = []
        for text in texts:
            vector = self._generate_embedding(text, task_type="RETRIEVAL_DOCUMENT")
            vectors.append(vector)

        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Documents embedded",
            count=len(texts),
            latency_ms=round(latency_ms, 2),
        )

        return vectors

    def embed_query(self, text: str) -> np.ndarray:
        """Генерирует эмбеддинг для поискового запроса.

        Args:
            text: Текст запроса.

        Returns:
            Numpy массив (вектор).

        Raises:
            ValueError: Если text пустой.
            RuntimeError: Если API вернул ошибку.
        """
        if not text or not text.strip():
            logger.warning("Empty query text provided")
            raise ValueError("Текст запроса не может быть пустым")

        logger.debug(
            "Embedding query",
            text_length=len(text),
        )

        start_time = time.perf_counter()
        vector = self._generate_embedding(text, task_type="RETRIEVAL_QUERY")
        latency_ms = (time.perf_counter() - start_time) * 1000

        logger.debug(
            "Query embedded",
            latency_ms=round(latency_ms, 2),
        )

        return vector

    def _generate_embedding(self, text: str, task_type: TaskType) -> np.ndarray:
        """Внутренний метод генерации эмбеддинга.

        Args:
            text: Текст для векторизации.
            task_type: Тип задачи (DOCUMENT или QUERY).

        Returns:
            Нормализованный numpy вектор.

        Raises:
            RuntimeError: Если API вернул ошибку.
        """
        logger.trace(
            "Generating embedding",
            task_type=task_type,
            text_length=len(text),
        )

        try:
            result = genai.embed_content(
                model=self.model_name,
                content=text,
                task_type=task_type,
                output_dimensionality=self.dimension,
            )

            embedding = np.array(result["embedding"], dtype=np.float32)
            embedding = self._normalize_vector(embedding)

            # Логируем AI вызов
            prompt_preview = text[:100] + "..." if len(text) > 100 else text
            logger.trace_ai(
                prompt=prompt_preview,
                model=self.model_name,
                operation="embedding",
                task_type=task_type,
                dimension=self.dimension,
            )

            logger.trace(
                "Embedding generated",
                dimension=len(embedding),
            )

            return embedding

        except Exception as e:
            logger.error(
                "Embedding generation failed",
                error_type=type(e).__name__,
                task_type=task_type,
            )
            raise RuntimeError(f"Ошибка при генерации эмбеддинга: {e}")

    @staticmethod
    def _normalize_vector(vector: np.ndarray) -> np.ndarray:
        """Нормализует вектор для косинусного расстояния.

        Args:
            vector: Исходный вектор.

        Returns:
            Нормализованный вектор (длина = 1).
        """
        norm = np.linalg.norm(vector)
        if norm == 0:
            return vector
        return vector / norm

    @staticmethod
    def vector_to_blob(vector: np.ndarray) -> bytes:
        """Конвертирует numpy вектор в BLOB для SQLite.

        Args:
            vector: Numpy массив float32.

        Returns:
            Сериализованные данные.
        """
        return vector.tobytes()

    @staticmethod
    def blob_to_vector(blob: bytes) -> np.ndarray:
        """Конвертирует BLOB обратно в numpy вектор.

        Args:
            blob: Бинарные данные из БД.

        Returns:
            Восстановленный вектор float32.
        """
        return np.frombuffer(blob, dtype=np.float32)
