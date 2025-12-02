"""DTO для мультимодального контента.

Классы:
    TaskStatus
        Статусы задачи на обработку медиа.
    MediaResource
        Контейнер для медиа-файла.
    MediaRequest
        Запрос на анализ медиа.
    MediaAnalysisResult
        Результат анализа.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class TaskStatus(str, Enum):
    """Статусы задачи на обработку медиа.

    Attributes:
        PENDING: Задача в очереди.
        PROCESSING: Задача обрабатывается.
        COMPLETED: Задача завершена успешно.
        FAILED: Задача завершилась с ошибкой.
    """

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class MediaResource:
    """Контейнер для медиа-файла.

    Attributes:
        path: Путь к файлу.
        media_type: Тип медиа (image/audio/video).
        mime_type: MIME-тип файла.
        metadata: Дополнительные метаданные.
    """

    path: Path
    media_type: str  # "image", "audio", "video"
    mime_type: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Преобразует строку в Path при необходимости."""
        if isinstance(self.path, str):
            self.path = Path(self.path)


@dataclass
class MediaRequest:
    """Запрос на анализ медиа.

    Attributes:
        resource: Медиа-ресурс для анализа.
        user_prompt: Пользовательский промпт (опционально).
        context_text: Контекст из метаданных чанка (заголовки).
    """

    resource: MediaResource
    user_prompt: Optional[str] = None
    context_text: Optional[str] = None


@dataclass
class MediaAnalysisResult:
    """Результат анализа медиа.

    Attributes:
        description: Полное описание контента.
        alt_text: Краткий alt-текст для доступности.
        keywords: Ключевые слова для поиска.
        ocr_text: Распознанный текст (если есть).
        tokens_used: Количество использованных токенов.
    """

    description: str
    alt_text: Optional[str] = None
    keywords: list[str] = field(default_factory=list)
    ocr_text: Optional[str] = None
    tokens_used: Optional[int] = None
