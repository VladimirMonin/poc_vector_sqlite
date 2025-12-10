"""Конфигурации моделей для локальных embeddings.

Модуль содержит ModelConfig для управления параметрами моделей
и функции загрузки через MLX.
"""

from dataclasses import dataclass
from typing import Any, Literal, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class ModelConfig:
    """Конфигурация embedding модели.

    Attributes:
        name: HuggingFace model ID (mlx-community/...).
        dimension: Размерность выходного вектора.
        max_tokens: Максимальная длина входа в токенах.
        backend: Бэкенд для загрузки (mlx-embeddings или mlx-lm).
        needs_query_prefix: Требуется ли префикс 'query:' для поисковых запросов.
    """

    name: str
    dimension: int
    max_tokens: int
    backend: Literal["mlx-embeddings", "mlx-lm"]
    needs_query_prefix: bool = False


# Предустановленные модели
MODELS = {
    "all-minilm": ModelConfig(
        name="mlx-community/all-MiniLM-L6-v2-4bit",
        dimension=384,
        max_tokens=512,
        backend="mlx-embeddings",
        needs_query_prefix=False,
    ),
    "qwen3-embedding": ModelConfig(
        name="mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ",
        dimension=1024,
        max_tokens=8192,
        backend="mlx-lm",
        needs_query_prefix=False,
    ),
    "bge-small": ModelConfig(
        name="mlx-community/bge-small-en-v1.5-4bit",
        dimension=384,
        max_tokens=512,
        backend="mlx-embeddings",
        needs_query_prefix=False,
    ),
}


def load_model(config: ModelConfig) -> Tuple[Any, Any]:
    """Загрузка модели через соответствующий MLX бэкенд.

    Args:
        config: Конфигурация модели.

    Returns:
        Tuple[model, tokenizer]: Загруженная модель и токенизатор.

    Raises:
        ImportError: Если MLX библиотеки не установлены.
        ValueError: Если бэкенд неизвестен.
        RuntimeError: Если загрузка модели не удалась.

    Examples:
        >>> config = MODELS["all-minilm"]
        >>> model, tokenizer = load_model(config)
    """
    try:
        if config.backend == "mlx-embeddings":
            from mlx_embeddings.utils import load

            return load(config.name)
        elif config.backend == "mlx-lm":
            from mlx_lm import load

            return load(config.name)
        else:
            raise ValueError(f"Unknown backend: {config.backend}")
    except ImportError as e:
        raise ImportError(
            f"MLX dependencies not installed. "
            f"Install with: pip install semantic-core[local-embeddings]\n"
            f"Original error: {e}"
        ) from e
    except Exception as e:
        raise RuntimeError(f"Failed to load model {config.name}: {e}") from e


def embed_with_model(
    model: Any,
    tokenizer: Any,
    text: str,
    max_length: int = 512,
) -> np.ndarray:
    """Генерация embedding через MLX модель.

    Args:
        model: Загруженная MLX модель.
        tokenizer: Токенизатор модели.
        text: Текст для векторизации.
        max_length: Максимальная длина в токенах.

    Returns:
        Numpy массив с эмбеддингом.

    Raises:
        RuntimeError: Если embedding generation не удался.

    Examples:
        >>> model, tokenizer = load_model(MODELS["all-minilm"])
        >>> vector = embed_with_model(model, tokenizer, "Hello world")
        >>> vector.shape
        (384,)
    """
    try:
        # Токенизация
        inputs = tokenizer.batch_encode_plus(
            [text],
            return_tensors="mlx",
            padding=True,
            truncation=True,
            max_length=max_length,
        )

        # Генерация эмбеддинга
        outputs = model(inputs["input_ids"], attention_mask=inputs["attention_mask"])
        embeddings = outputs.text_embeds

        return np.array(embeddings[0])
    except Exception as e:
        raise RuntimeError(f"Failed to generate embedding: {e}") from e
