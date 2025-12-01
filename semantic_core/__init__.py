"""
Semantic Core - переносимое ядро для семантического поиска.

Этот пакет обеспечивает:
- Инициализацию SQLite с расширением sqlite-vec
- Генерацию эмбеддингов через Google Gemini API
- Нарезку текста на чанки с перекрытием
- Сервисный слой для работы с Parent-Child документами
- Миксин для добавления hybrid search в любую Peewee модель
"""

from semantic_core.database import (
    db,
    init_database,
    create_vector_table,
    create_fts_table,
)
from semantic_core.embeddings import EmbeddingGenerator
from semantic_core.search_mixin import HybridSearchMixin
from semantic_core.text_processing import (
    TextSplitter,
    Chunk,
    SimpleTextSplitter,
)
from semantic_core.services import (
    save_note_with_chunks,
    delete_note_with_chunks,
)

__all__ = [
    # Database
    "db",
    "init_database",
    "create_vector_table",
    "create_fts_table",
    
    # Embeddings
    "EmbeddingGenerator",
    
    # Search
    "HybridSearchMixin",
    
    # Text processing
    "TextSplitter",
    "Chunk",
    "SimpleTextSplitter",
    
    # Services
    "save_note_with_chunks",
    "delete_note_with_chunks",
]
