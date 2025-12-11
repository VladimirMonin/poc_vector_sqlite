"""Локальные embeddings через MLX."""

from semantic_core.infrastructure.local.embeddings.embedder import LocalEmbedder
from semantic_core.infrastructure.local.embeddings.models import MODELS, ModelConfig

__all__ = ["LocalEmbedder", "MODELS", "ModelConfig"]
