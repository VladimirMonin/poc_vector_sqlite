"""Модель чанка (дочерний объект).

Классы:
    ChunkType
        Enum типов контента в чанке.
    Chunk
        DTO для фрагмента документа с векторным представлением.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import numpy as np


class ChunkType(str, Enum):
    """Типы контента в чанке.

    Attributes:
        TEXT: Обычный текстовый контент.
        CODE: Блок кода.
        TABLE: Таблица (Markdown/HTML).
        IMAGE_REF: Ссылка на изображение.
        AUDIO_REF: Ссылка на аудиофайл.
        VIDEO_REF: Ссылка на видеофайл.
    """

    TEXT = "text"
    CODE = "code"
    TABLE = "table"
    IMAGE_REF = "image_ref"
    AUDIO_REF = "audio_ref"
    VIDEO_REF = "video_ref"


# Множество медиа-типов для удобной проверки
MEDIA_CHUNK_TYPES = frozenset({
    ChunkType.IMAGE_REF,
    ChunkType.AUDIO_REF,
    ChunkType.VIDEO_REF,
})


@dataclass
class Chunk:
    """Фрагмент документа (дочерний объект) для векторного поиска.

    Представляет нарезанный кусок документа с эмбеддингом.
    Не привязан к ORM — чистый DTO.

    Attributes:
        content: Текст фрагмента.
        chunk_index: Порядковый номер в документе (начиная с 0).
        chunk_type: Тип контента (TEXT/CODE/TABLE/IMAGE_REF/AUDIO_REF/VIDEO_REF).
        language: Язык программирования для блоков кода (например, "python").
        embedding: Векторное представление (numpy array).
        parent_doc_id: ID родительского документа.
        metadata: Словарь метаданных. Рекомендуемые ключи:
            - headers (list[str]): Иерархия заголовков ["H1", "H2"].
            - start_line (int): Номер начальной строки в исходном файле.
            - end_line (int): Номер конечной строки в исходном файле.
        id: Идентификатор чанка (заполняется после сохранения).
        created_at: Дата создания.
    """

    content: str
    chunk_index: int
    chunk_type: ChunkType = ChunkType.TEXT
    language: Optional[str] = None
    embedding: Optional[np.ndarray] = None
    parent_doc_id: Optional[int] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)

    def __repr__(self) -> str:
        preview = self.content[:40] + "..." if len(self.content) > 40 else self.content
        has_vec = "✓" if self.embedding is not None else "✗"
        lang_info = f"[{self.language}]" if self.language else ""
        return (
            f"Chunk(id={self.id}, idx={self.chunk_index}, "
            f"type={self.chunk_type.value}{lang_info}, "
            f"parent={self.parent_doc_id}, vec={has_vec})"
        )
