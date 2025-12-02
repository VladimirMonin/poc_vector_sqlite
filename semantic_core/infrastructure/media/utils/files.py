"""Утилиты для работы с файлами и валидации медиа.

Функции:
    get_file_mime_type(file_path: str) -> str
        Определяет MIME-тип файла.
    is_image_valid(file_path: str) -> bool
        Проверяет, является ли файл поддерживаемым изображением.
    get_media_type(file_path: str) -> str
        Определяет тип медиа по MIME-типу.
"""

import mimetypes
import os
from pathlib import Path

# Поддерживаемые MIME-типы изображений
SUPPORTED_IMAGE_MIME_TYPES: list[str] = [
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/heic",
    "image/heif",
]

# Маппинг расширений на MIME-типы
EXTENSION_MIME_MAP: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
    # Audio (для Phase 6.2)
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    # Video (для Phase 6.2)
    ".mp4": "video/mp4",
    ".avi": "video/x-msvideo",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
}


def get_file_mime_type(file_path: str) -> str:
    """Определяет MIME-тип файла.

    Сначала пытается использовать mimetypes, затем fallback на расширение.

    Args:
        file_path: Путь к файлу.

    Returns:
        MIME-тип или 'application/octet-stream' для неизвестных типов.
    """
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type:
        return mime_type

    file_extension = Path(file_path).suffix.lower()
    return EXTENSION_MIME_MAP.get(file_extension, "application/octet-stream")


def is_image_valid(file_path: str) -> bool:
    """Проверяет, является ли файл поддерживаемым изображением.

    Args:
        file_path: Путь к файлу.

    Returns:
        True если файл существует и является поддерживаемым изображением.
    """
    if not os.path.exists(file_path):
        return False
    if not os.path.isfile(file_path):
        return False
    mime_type = get_file_mime_type(file_path)
    return mime_type in SUPPORTED_IMAGE_MIME_TYPES


def get_media_type(file_path: str) -> str:
    """Определяет тип медиа по MIME-типу.

    Args:
        file_path: Путь к файлу.

    Returns:
        Тип медиа: 'image', 'audio', 'video' или 'unknown'.
    """
    mime_type = get_file_mime_type(file_path)

    if mime_type.startswith("image/"):
        return "image"
    elif mime_type.startswith("audio/"):
        return "audio"
    elif mime_type.startswith("video/"):
        return "video"
    else:
        return "unknown"
