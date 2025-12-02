"""Модель документа (родительский объект).

Классы:
    MediaType
        Перечисление типов медиа-контента.
    Document
        DTO для хранения исходного документа.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class MediaType(str, Enum):
    """Тип медиа-контента документа.

    Attributes:
        TEXT: Текстовый документ (Markdown, Plain Text).
        IMAGE: Изображение (JPG, PNG, WEBP).
        VIDEO: Видео (MP4, AVI).
        AUDIO: Аудио (MP3, WAV).
    """

    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


@dataclass
class Document:
    """Документ (родительский объект) в системе.

    Представляет исходный контент до нарезки на чанки.
    Не привязан к ORM — чистый DTO.

    Attributes:
        content: Полный текст документа или путь к медиа-файлу.
        metadata: Словарь метаданных (title, url, author, tags и т.д.).
        media_type: Тип контента (TEXT, IMAGE, VIDEO, AUDIO).
        id: Идентификатор документа (заполняется после сохранения).
        created_at: Дата создания.
    """

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    media_type: MediaType = MediaType.TEXT
    id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)

    def __repr__(self) -> str:
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        title = self.metadata.get("title", "Untitled")
        return f"Document(id={self.id}, type={self.media_type.value}, title='{title}')"
