"""Конфигурация для обработки медиа.

Классы:
    MediaConfig
        Dataclass с настройками моделей и rate limiting.
"""

from dataclasses import dataclass


@dataclass
class MediaConfig:
    """Конфигурация для обработки медиа-контента.

    Attributes:
        image_model: Модель Gemini для анализа изображений.
        audio_model: Модель Gemini для анализа аудио (Phase 6.2).
        video_model: Модель Gemini для анализа видео (Phase 6.2).
        rpm_limit: Requests Per Minute (консервативно для Free Tier).
        max_image_dimension: Максимальный размер стороны изображения.
        image_format: Формат для оптимизации (webp/jpeg).
        image_quality: Качество сжатия (1-100).
    """

    # Модели Gemini
    image_model: str = "gemini-2.5-flash"
    audio_model: str = "gemini-2.5-flash-lite"  # Phase 6.2
    video_model: str = "gemini-2.5-pro"  # Phase 6.2

    # Rate Limiting
    rpm_limit: int = 15  # Консервативно для Free Tier

    # Оптимизация изображений
    max_image_dimension: int = 1920
    image_format: str = "webp"
    image_quality: int = 80
