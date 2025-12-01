"""
Генератор эмбеддингов через Google Gemini API.

Предоставляет асимметричный поиск с использованием task_type
и поддержку Matryoshka Representation Learning (MRL).
"""

from typing import Literal

import google.generativeai as genai
import numpy as np

from config import settings


TaskType = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]


class EmbeddingGenerator:
    """
    Генератор векторных представлений текста через Google Gemini API.

    Поддерживает:
    - Асимметричный поиск (разные task_type для документов и запросов)
    - MRL (Matryoshka Representation Learning) для уменьшения размерности
    - Автоматическую нормализацию векторов

    Attributes:
        model_name: Имя модели эмбеддингов Gemini
        dimension: Целевая размерность векторов (768 для MRL)
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        dimension: int | None = None,
    ):
        """
        Инициализация генератора эмбеддингов.

        Args:
            api_key: API ключ Google Gemini (по умолчанию из settings)
            model_name: Модель для генерации (по умолчанию из settings)
            dimension: Размерность векторов (по умолчанию из settings)
        """
        self.api_key = api_key or settings.gemini_api_key
        self.model_name = model_name or settings.embedding_model
        self.dimension = dimension or settings.embedding_dimension

        # Конфигурируем API
        genai.configure(api_key=self.api_key)

    def embed_document(self, text: str) -> np.ndarray:
        """
        Генерирует эмбеддинг для документа (индексируемого контента).

        Использует task_type="RETRIEVAL_DOCUMENT" для оптимизации
        векторного представления документов в базе знаний.

        Args:
            text: Текст документа для векторизации

        Returns:
            np.ndarray: Нормализованный вектор размерности self.dimension

        Examples:
            >>> gen = EmbeddingGenerator()
            >>> vec = gen.embed_document("Python - язык программирования")
            >>> vec.shape
            (768,)
        """
        return self._generate_embedding(text, task_type="RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> np.ndarray:
        """
        Генерирует эмбеддинг для поискового запроса.

        Использует task_type="RETRIEVAL_QUERY" для оптимизации
        векторного представления пользовательских запросов.

        Args:
            text: Текст запроса

        Returns:
            np.ndarray: Нормализованный вектор размерности self.dimension

        Examples:
            >>> gen = EmbeddingGenerator()
            >>> vec = gen.embed_query("как написать цикл в питоне?")
            >>> vec.shape
            (768,)
        """
        return self._generate_embedding(text, task_type="RETRIEVAL_QUERY")

    def _generate_embedding(self, text: str, task_type: TaskType) -> np.ndarray:
        """
        Внутренний метод генерации эмбеддинга.

        Args:
            text: Текст для векторизации
            task_type: Тип задачи (DOCUMENT или QUERY)

        Returns:
            np.ndarray: Нормализованный вектор

        Raises:
            ValueError: Если текст пустой
            RuntimeError: Если API вернул ошибку
        """
        if not text or not text.strip():
            raise ValueError("Текст не может быть пустым")

        try:
            # Генерируем эмбеддинг через Gemini API
            result = genai.embed_content(
                model=self.model_name,
                content=text,
                task_type=task_type,
                output_dimensionality=self.dimension,  # MRL - режем до 768
            )

            # Извлекаем вектор
            embedding = np.array(result["embedding"], dtype=np.float32)

            # Нормализуем вектор (для косинусного сходства)
            embedding = self._normalize_vector(embedding)

            return embedding

        except Exception as e:
            raise RuntimeError(f"Ошибка при генерации эмбеддинга: {e}")

    @staticmethod
    def _normalize_vector(vector: np.ndarray) -> np.ndarray:
        """
        Нормализует вектор для использования с косинусным расстоянием.

        Args:
            vector: Исходный вектор

        Returns:
            np.ndarray: Нормализованный вектор (длина = 1)
        """
        norm = np.linalg.norm(vector)
        if norm == 0:
            return vector
        return vector / norm

    @staticmethod
    def vector_to_blob(vector: np.ndarray) -> bytes:
        """
        Конвертирует numpy вектор в бинарный BLOB для SQLite.

        Args:
            vector: Numpy массив float32

        Returns:
            bytes: Сериализованные данные для хранения в SQLite

        Examples:
            >>> vec = np.array([0.1, 0.2, 0.3], dtype=np.float32)
            >>> blob = EmbeddingGenerator.vector_to_blob(vec)
            >>> len(blob)
            12
        """
        return vector.tobytes()

    @staticmethod
    def blob_to_vector(blob: bytes) -> np.ndarray:
        """
        Конвертирует BLOB из SQLite обратно в numpy вектор.

        Args:
            blob: Бинарные данные из базы

        Returns:
            np.ndarray: Восстановленный вектор float32

        Examples:
            >>> blob = b'\\x00\\x00\\x00\\x00'
            >>> vec = EmbeddingGenerator.blob_to_vector(blob)
            >>> vec.dtype
            dtype('float32')
        """
        return np.frombuffer(blob, dtype=np.float32)
