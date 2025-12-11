"""Локальные AI провайдеры (embeddings, LLM через MLX/sentence-transformers)."""

from semantic_core.infrastructure.local.embeddings.embedder import LocalEmbedder
from semantic_core.infrastructure.local.sentence_transformer_embedder import (
    SentenceTransformerEmbedder,
)

__all__ = ["LocalEmbedder", "SentenceTransformerEmbedder"]
