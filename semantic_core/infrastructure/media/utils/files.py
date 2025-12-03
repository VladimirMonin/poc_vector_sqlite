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

from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)

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
        logger.trace(
            "MIME type detected (mimetypes)",
            path=file_path,
            mime_type=mime_type,
        )
        return mime_type

    file_extension = Path(file_path).suffix.lower()
    mime_type = EXTENSION_MIME_MAP.get(file_extension, "application/octet-stream")
    
    logger.trace(
        "MIME type detected (extension fallback)",
        path=file_path,
        extension=file_extension,
        mime_type=mime_type,
    )
    
    return mime_type


def is_image_valid(file_path: str) -> bool:
    """Проверяет, является ли файл поддерживаемым изображением.

    Args:
        file_path: Путь к файлу.

    Returns:
        True если файл существует и является поддерживаемым изображением.
    """
    if not os.path.exists(file_path):
        logger.trace(
            "File not found",
            path=file_path,
        )
        return False
    if not os.path.isfile(file_path):
        logger.trace(
            "Path is not a file",
            path=file_path,
        )
        return False
    mime_type = get_file_mime_type(file_path)
    is_valid = mime_type in SUPPORTED_IMAGE_MIME_TYPES
    
    logger.trace(
        "Image validation",
        path=file_path,
        mime_type=mime_type,
        is_valid=is_valid,
    )
    
    return is_valid


def get_media_type(file_path: str) -> str:
    """Определяет тип медиа по MIME-типу.

    Args:
        file_path: Путь к файлу.

    Returns:
        Тип медиа: 'image', 'audio', 'video' или 'unknown'.
    """
    mime_type = get_file_mime_type(file_path)

    if mime_type.startswith("image/"):
        media_type = "image"
    elif mime_type.startswith("audio/"):
        media_type = "audio"
    elif mime_type.startswith("video/"):
        media_type = "video"
    else:
        media_type = "unknown"
    
    logger.trace(
        "Media type detected",
        path=file_path,
        mime_type=mime_type,
        media_type=media_type,
    )
    
    return media_type
