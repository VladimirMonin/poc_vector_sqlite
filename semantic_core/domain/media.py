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
    VideoAnalysisConfig
        Конфигурация анализа видео.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Optional


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
    """Результат анализа медиа (изображения, аудио, видео).

    Attributes:
        description: Полное описание контента.
        alt_text: Краткий alt-текст для доступности.
        keywords: Ключевые слова для поиска.
        ocr_text: Распознанный текст из изображений (если есть).
        transcription: Транскрипция аудио/видео (Phase 6.2).
        participants: Спикеры/участники (Phase 6.2).
        action_items: Выделенные задачи из контента (Phase 6.2).
        duration_seconds: Длительность медиа в секундах (Phase 6.2).
        tokens_used: Количество использованных токенов.
    """

    description: str
    alt_text: Optional[str] = None
    keywords: list[str] = field(default_factory=list)
    ocr_text: Optional[str] = None
    # Audio/Video fields (Phase 6.2)
    transcription: Optional[str] = None
    participants: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    duration_seconds: Optional[float] = None
    tokens_used: Optional[int] = None


@dataclass
class VideoAnalysisConfig:
    """Конфигурация анализа видео.

    Поддерживает три режима извлечения кадров:
    - fps: N кадров в секунду
    - total: Ровно N равномерно распределённых кадров
    - interval: Кадр каждые N секунд

    Attributes:
        frame_mode: Режим извлечения кадров.
        fps: Кадров в секунду (для mode="fps").
        frame_count: Количество кадров (для mode="total").
        interval_seconds: Интервал в секундах (для mode="interval").
        frame_quality: Пресет качества кадров (fhd/hd/balanced).
        max_frames: Максимальное количество кадров.
        include_audio: Включать ли аудио-дорожку в анализ.
    """

    frame_mode: Literal["fps", "total", "interval"] = "total"
    fps: float = 1.0
    frame_count: int = 10
    interval_seconds: float = 5.0
    frame_quality: Literal["fhd", "hd", "balanced"] = "hd"
    max_frames: int = 50
    include_audio: bool = True
