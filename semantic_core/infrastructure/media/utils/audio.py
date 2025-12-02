"""Утилиты для работы с аудио.

Агрессивная оптимизация для максимальной вместимости в Gemini 20MB лимит:
- 32 kbps mono OGG = ~83 минуты аудио в одном запросе
- Любой подкаст/лекция до 1.5 часов без нарезки

Functions:
    ensure_ffmpeg: Проверяет наличие ffmpeg в системе.
    extract_audio_from_video: Извлекает аудио-дорожку из видео.
    optimize_audio: Оптимизирует аудио для Gemini API.
    get_audio_duration: Возвращает длительность аудио.
"""

import shutil
from io import BytesIO
from pathlib import Path
from typing import Optional

from pydub import AudioSegment

# Поддерживаемые MIME-типы аудио
SUPPORTED_AUDIO_TYPES = [
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/ogg",
    "audio/flac",
    "audio/aac",
    "audio/x-m4a",
]

# Агрессивные дефолты для максимальной вместимости
DEFAULT_BITRATE = 32  # kbps — 20MB / (32k/8) = ~83 минуты!
DEFAULT_CODEC = "libvorbis"  # Совместим с pydub/ffmpeg
DEFAULT_SAMPLE_RATE = 16000  # Достаточно для speech
DEFAULT_MONO = True  # Gemini не различает стерео


class DependencyError(Exception):
    """Отсутствует системная зависимость (ffmpeg)."""

    pass


def ensure_ffmpeg() -> None:
    """Проверяет наличие ffmpeg в системе.

    Raises:
        DependencyError: Если ffmpeg не найден в PATH.
    """
    if shutil.which("ffmpeg") is None:
        raise DependencyError(
            "System ffmpeg is required for audio/video processing.\n"
            "Install: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)"
        )


def extract_audio_from_video(
    video_path: str | Path,
    output_path: Optional[str | Path] = None,
    format: str = "ogg",
    codec: str = DEFAULT_CODEC,
    bitrate: int = DEFAULT_BITRATE,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    mono: bool = DEFAULT_MONO,
) -> Path:
    """Извлекает аудио-дорожку из видео с агрессивной оптимизацией.

    При дефолтных настройках (32kbps mono OGG) позволяет уместить
    до 83 минут аудио в 20MB лимит Gemini API.

    Args:
        video_path: Путь к видео-файлу.
        output_path: Путь для сохранения (auto если None).
        format: Формат контейнера (ogg, mp3, wav).
        codec: Кодек ffmpeg (libvorbis, libmp3lame).
        bitrate: Битрейт в kbps (32 = ~83 мин в 20MB).
        sample_rate: Частота дискретизации.
        mono: Конвертировать в моно.

    Returns:
        Path к извлечённому аудио-файлу.

    Raises:
        DependencyError: Если ffmpeg не установлен.
        FileNotFoundError: Если видео-файл не найден.
    """
    ensure_ffmpeg()

    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    audio = AudioSegment.from_file(str(video_path))

    if mono:
        audio = audio.set_channels(1)

    audio = audio.set_frame_rate(sample_rate)

    if output_path is None:
        output_path = video_path.with_suffix(f".{format}")
    else:
        output_path = Path(output_path)

    # Экспортируем с указанным кодеком и битрейтом
    audio.export(
        str(output_path),
        format=format,
        codec=codec,
        bitrate=f"{bitrate}k",
    )

    return output_path


def optimize_audio(
    audio_path: str | Path,
    output_path: Optional[str | Path] = None,
    format: str = "ogg",
    codec: str = DEFAULT_CODEC,
    bitrate: int = DEFAULT_BITRATE,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    mono: bool = DEFAULT_MONO,
) -> Path:
    """Оптимизирует аудио-файл для Gemini API.

    Применяет агрессивное сжатие: 32kbps mono OGG.
    Результат: 83 минуты аудио в 20MB.

    Args:
        audio_path: Путь к исходному аудио.
        output_path: Путь для сохранения (auto если None).
        format: Формат контейнера.
        codec: Кодек ffmpeg.
        bitrate: Битрейт в kbps.
        sample_rate: Частота дискретизации.
        mono: Конвертировать в моно.

    Returns:
        Path к оптимизированному аудио.
    """
    ensure_ffmpeg()

    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    audio = AudioSegment.from_file(str(audio_path))

    if mono:
        audio = audio.set_channels(1)

    audio = audio.set_frame_rate(sample_rate)

    if output_path is None:
        stem = audio_path.stem
        output_path = audio_path.parent / f"{stem}_optimized.{format}"
    else:
        output_path = Path(output_path)

    audio.export(
        str(output_path),
        format=format,
        codec=codec,
        bitrate=f"{bitrate}k",
    )

    return output_path


def optimize_audio_to_bytes(
    audio_path: str | Path,
    format: str = "ogg",
    codec: str = DEFAULT_CODEC,
    bitrate: int = DEFAULT_BITRATE,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    mono: bool = DEFAULT_MONO,
) -> tuple[bytes, str]:
    """Оптимизирует аудио и возвращает bytes для inline upload.

    Args:
        audio_path: Путь к исходному аудио.
        format: Формат контейнера.
        codec: Кодек ffmpeg.
        bitrate: Битрейт в kbps.
        sample_rate: Частота дискретизации.
        mono: Конвертировать в моно.

    Returns:
        Tuple (audio_bytes, mime_type).
    """
    ensure_ffmpeg()

    audio_path = Path(audio_path)
    audio = AudioSegment.from_file(str(audio_path))

    if mono:
        audio = audio.set_channels(1)

    audio = audio.set_frame_rate(sample_rate)

    buffer = BytesIO()
    audio.export(
        buffer,
        format=format,
        codec=codec,
        bitrate=f"{bitrate}k",
    )

    mime_type = f"audio/{format}"
    return buffer.getvalue(), mime_type


def get_audio_duration(path: str | Path) -> float:
    """Возвращает длительность аудио в секундах.

    Args:
        path: Путь к аудио-файлу.

    Returns:
        Длительность в секундах.
    """
    audio = AudioSegment.from_file(str(path))
    return len(audio) / 1000.0


def is_audio_supported(mime_type: str) -> bool:
    """Проверяет, поддерживается ли MIME-тип аудио.

    Args:
        mime_type: MIME-тип для проверки.

    Returns:
        True если тип поддерживается.
    """
    return mime_type in SUPPORTED_AUDIO_TYPES
