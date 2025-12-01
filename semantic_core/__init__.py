"""
Semantic Core - переносимое ядро для семантического поиска.

Этот пакет обеспечивает:
- Инициализацию SQLite с расширением sqlite-vec
- Генерацию эмбеддингов через Google Gemini API
- Миксин для добавления hybrid search в любую Peewee модель
"""

from semantic_core.database import db, init_database
from semantic_core.embeddings import EmbeddingGenerator
from semantic_core.search_mixin import HybridSearchMixin

__all__ = [
    "db",
    "init_database",
    "EmbeddingGenerator",
    "HybridSearchMixin",
]
