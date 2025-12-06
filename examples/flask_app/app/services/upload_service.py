"""Сервис загрузки и управления файлами.

Обеспечивает сохранение загруженных файлов в uploads/,
UUID-именование и обновление путей в Markdown.

Classes:
    UploadService: Сохранение и управление загруженными файлами.
    UploadResult: Результат загрузки файла.

Usage:
    service = UploadService(upload_dir=Path("uploads"))
    result = service.save_file(file, original_name="doc.md")
    service.process_markdown_paths(result.path, uploaded_files)
"""

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from semantic_core.utils.logger import get_logger

logger = get_logger("flask_app.upload")

# Поддерживаемые расширения
ALLOWED_EXTENSIONS = {
    # Документы
    ".md",
    ".markdown",
    ".txt",
    # Изображения
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    # Аудио
    ".mp3",
    ".wav",
    ".ogg",
    ".m4a",
    ".flac",
    # Видео
    ".mp4",
    ".webm",
    ".mov",
    ".avi",
}


@dataclass
class UploadResult:
    """Результат загрузки файла.

    Attributes:
        success: Успешно ли загружен файл.
        path: Путь к сохранённому файлу (если успешно).
        original_name: Оригинальное имя файла.
        uuid_name: UUID-имя файла.
        error: Сообщение об ошибке (если неудача).
    """

    success: bool
    path: Path | None
    original_name: str
    uuid_name: str | None
    error: str | None = None


class UploadService:
    """Сервис для загрузки и управления файлами.

    Сохраняет файлы с UUID-префиксом для избежания коллизий.
    Обновляет относительные пути в Markdown-файлах.

    Attributes:
        upload_dir: Директория для загрузки файлов.
    """

    def __init__(self, upload_dir: Path) -> None:
        """Инициализировать сервис загрузки.

        Args:
            upload_dir: Путь к директории uploads/.
        """
        self.upload_dir = upload_dir
        self._ensure_upload_dir()

    def _ensure_upload_dir(self) -> None:
        """Создать директорию uploads если не существует."""
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"📁 Upload directory: {self.upload_dir}")

    def _is_allowed_extension(self, filename: str) -> bool:
        """Проверить, разрешено ли расширение файла.

        Args:
            filename: Имя файла.

        Returns:
            True если расширение разрешено.
        """
        ext = Path(filename).suffix.lower()
        return ext in ALLOWED_EXTENSIONS

    def _generate_uuid_name(self, original_name: str) -> str:
        """Сгенерировать UUID-имя для файла.

        Формат: {uuid}_{original_name}

        Args:
            original_name: Оригинальное имя файла.

        Returns:
            UUID-имя файла.
        """
        file_uuid = uuid.uuid4().hex[:8]
        safe_name = Path(original_name).name  # Убираем путь
        return f"{file_uuid}_{safe_name}"

    def save_file(
        self,
        file_data: BinaryIO,
        original_name: str,
    ) -> UploadResult:
        """Сохранить загруженный файл.

        Args:
            file_data: Бинарные данные файла.
            original_name: Оригинальное имя файла.

        Returns:
            UploadResult с информацией о сохранении.
        """
        # Валидация расширения
        if not self._is_allowed_extension(original_name):
            ext = Path(original_name).suffix
            return UploadResult(
                success=False,
                path=None,
                original_name=original_name,
                uuid_name=None,
                error=f"Расширение {ext} не поддерживается",
            )

        # Генерация UUID-имени
        uuid_name = self._generate_uuid_name(original_name)
        file_path = self.upload_dir / uuid_name

        try:
            # Сохранение файла
            with open(file_path, "wb") as f:
                f.write(file_data.read())

            logger.info(f"📥 Файл сохранён: {uuid_name}")

            return UploadResult(
                success=True,
                path=file_path,
                original_name=original_name,
                uuid_name=uuid_name,
            )

        except Exception as e:
            logger.error(f"🔥 Ошибка сохранения {original_name}: {e}")
            return UploadResult(
                success=False,
                path=None,
                original_name=original_name,
                uuid_name=None,
                error=str(e),
            )

    def process_markdown_paths(
        self,
        markdown_path: Path,
        uploaded_files: dict[str, Path],
    ) -> str:
        """Обновить относительные пути в Markdown-файле.

        Заменяет ссылки на медиа-файлы на абсолютные пути к uploads/.

        Args:
            markdown_path: Путь к Markdown-файлу.
            uploaded_files: Маппинг original_name → uuid_path.

        Returns:
            Обновлённое содержимое Markdown.
        """
        content = markdown_path.read_text(encoding="utf-8")

        # Паттерн для Markdown изображений и ссылок
        # ![alt](path) или [text](path)
        pattern = r"(!?\[.*?\])\(((?!http)[^)]+)\)"

        def replace_path(match: re.Match) -> str:
            prefix = match.group(1)
            original_path = match.group(2)

            # Извлекаем имя файла
            filename = Path(original_path).name

            # Ищем в загруженных файлах
            if filename in uploaded_files:
                new_path = uploaded_files[filename]
                logger.debug(f"📝 Заменён путь: {original_path} → {new_path}")
                return f"{prefix}({new_path})"

            return match.group(0)

        updated_content = re.sub(pattern, replace_path, content)
        return updated_content

    def delete_file(self, uuid_name: str) -> bool:
        """Удалить файл из uploads/.

        Args:
            uuid_name: UUID-имя файла.

        Returns:
            True если файл удалён успешно.
        """
        file_path = self.upload_dir / uuid_name

        if not file_path.exists():
            logger.warning(f"⚠️ Файл не найден: {uuid_name}")
            return False

        try:
            file_path.unlink()
            logger.info(f"🗑️ Файл удалён: {uuid_name}")
            return True
        except Exception as e:
            logger.error(f"🔥 Ошибка удаления {uuid_name}: {e}")
            return False

    def list_files(self) -> list[dict]:
        """Получить список загруженных файлов.

        Returns:
            Список словарей с информацией о файлах.
        """
        files = []
        for file_path in self.upload_dir.iterdir():
            if file_path.is_file():
                files.append(
                    {
                        "name": file_path.name,
                        "size": file_path.stat().st_size,
                        "modified": file_path.stat().st_mtime,
                    }
                )
        return sorted(files, key=lambda f: f["modified"], reverse=True)
