"""Конфигурация для обработки медиа.

Классы:
    MediaConfig
        Dataclass с настройками моделей и rate limiting.
"""

from dataclasses import dataclass


@dataclass
class MediaConfig:
    """Конфигурация для обработки медиа-контента.

    Агрессивные дефолты для максимальной вместимости в лимит 20MB:
    - audio_bitrate=32 kbps → 83 минуты аудио в одном запросе
    - video_max_dimension=1024 → экономия ~40% токенов

    Attributes:
        image_model: Модель Gemini для анализа изображений.
        audio_model: Модель Gemini для анализа аудио (flash-lite — дешевле в 4x).
        video_model: Модель Gemini для анализа видео (pro для сложного контента).
        rpm_limit: Requests Per Minute (консервативно для Free Tier).
        max_image_dimension: Максимальный размер стороны изображения.
        image_format: Формат для оптимизации (webp/jpeg).
        image_quality: Качество сжатия (1-100).
        audio_bitrate: Битрейт аудио в kbps (32 = 83 мин в 20MB).
        audio_codec: Кодек для ffmpeg (libvorbis).
        audio_sample_rate: Частота дискретизации.
        audio_mono: Конвертировать в моно (Gemini не различает стерео).
        max_audio_duration_sec: Макс. длительность аудио (80 мин при 32kbps).
        video_max_dimension: Максимальный размер кадра видео.
        max_video_duration_sec: Макс. длительность видео.
    """

    # Модели Gemini
    image_model: str = "gemini-2.5-flash"
    audio_model: str = "gemini-2.5-flash-lite"  # Дешевле flash в 4x
    video_model: str = "gemini-2.5-pro"  # Для сложного мультимодального контента

    # Rate Limiting
    rpm_limit: int = 15  # Консервативно для Free Tier

    # Оптимизация изображений
    max_image_dimension: int = 1920
    image_format: str = "webp"
    image_quality: int = 80

    # Оптимизация аудио (агрессивные дефолты)
    audio_bitrate: int = 32  # kbps — 20MB / (32k/8) = ~83 минуты!
    audio_codec: str = "libvorbis"  # Совместим с pydub/ffmpeg
    audio_sample_rate: int = 16000  # Достаточно для speech
    audio_mono: bool = True  # Gemini не различает стерео
    max_audio_duration_sec: int = 4800  # 80 минут (влезает в 20MB при 32kbps)

    # Оптимизация видео
    video_max_dimension: int = 1024  # Экономия ~40% токенов
    max_video_duration_sec: int = 300  # 5 минут
