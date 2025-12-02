"""Утилиты для работы с файлами и валидации изображений.

Функции:
    get_file_mime_type(file_path: str) -> str | None
        Определяет MIME-тип файла.
    read_file_as_bytes(file_path: str) -> bytes
        Читает файл как байты.
    is_image_valid(file_path: str) -> bool
        Проверяет, является ли файл поддерживаемым изображением.
"""

import mimetypes
import os
from pathlib import Path
from typing import List

SUPPORTED_IMAGE_MIME_TYPES: List[str] = [
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/heic",
    "image/heif",
]


def get_file_mime_type(file_path: str) -> str | None:
    """Определяет MIME-тип файла.

    Args:
        file_path: Путь к файлу.

    Returns:
        MIME-тип или 'application/octet-stream' для неизвестных типов.
    """
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type:
        return mime_type

    file_extension = Path(file_path).suffix.lower()
    extension_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".heic": "image/heic",
        ".heif": "image/heif",
    }

    return extension_map.get(file_extension, "application/octet-stream")


def read_file_as_bytes(file_path: str) -> bytes:
    """Читает содержимое файла как байты.

    Args:
        file_path: Путь к файлу.

    Returns:
        Содержимое файла как байты.

    Raises:
        FileNotFoundError: Если файл не найден.
        IOError: Ошибка чтения файла.
    """
    try:
        with open(file_path, "rb") as f:
            return f.read()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"File not found: {file_path}") from exc
    except IOError as e:
        raise IOError(f"Error reading file {file_path}: {e}") from e


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
