"""Интерфейс для генераторов эмбеддингов.

Классы:
    BaseEmbedder
        ABC для AI-моделей векторизации.
"""

from abc import ABC, abstractmethod

import numpy as np


class BaseEmbedder(ABC):
    """Абстрактный интерфейс для генераторов эмбеддингов.
    
    Определяет контракт для всех AI-провайдеров (Gemini, OpenAI, Local).
    Поддерживает асимметричный поиск (разные task_type для документов и запросов).
    """
    
    @abstractmethod
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
        raise NotImplementedError
    
    @abstractmethod
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
        raise NotImplementedError
