"""Модель чанка (дочерний объект).

Классы:
    Chunk
        DTO для фрагмента документа с векторным представлением.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import numpy as np


@dataclass
class Chunk:
    """Фрагмент документа (дочерний объект) для векторного поиска.
    
    Представляет нарезанный кусок документа с эмбеддингом.
    Не привязан к ORM — чистый DTO.
    
    Attributes:
        content: Текст фрагмента.
        chunk_index: Порядковый номер в документе (начиная с 0).
        embedding: Векторное представление (numpy array).
        parent_doc_id: ID родительского документа.
        metadata: Словарь метаданных (заголовки, таймкоды, позиции).
        id: Идентификатор чанка (заполняется после сохранения).
        created_at: Дата создания.
    """
    
    content: str
    chunk_index: int
    embedding: Optional[np.ndarray] = None
    parent_doc_id: Optional[int] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    def __repr__(self) -> str:
        preview = self.content[:40] + "..." if len(self.content) > 40 else self.content
        has_vec = "✓" if self.embedding is not None else "✗"
        return (
            f"Chunk(id={self.id}, idx={self.chunk_index}, "
            f"parent={self.parent_doc_id}, vec={has_vec})"
        )
