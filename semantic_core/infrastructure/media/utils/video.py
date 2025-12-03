"""Утилиты для работы с видео.

Извлечение кадров с тремя режимами:
- fps: N кадров в секунду
- total: Ровно N равномерно распределённых кадров
- interval: Кадр каждые N секунд

Оптимизация для экономии токенов:
- max_dimension=1024 вместо 1920 (экономия ~40%)

Functions:
    extract_frames: Извлекает кадры из видео.
    get_video_duration: Возвращает длительность видео.
    get_video_metadata: Возвращает метаданные видео.
"""

from io import BytesIO
from pathlib import Path
from typing import Literal

import imageio.v3 as iio
from PIL import Image

from semantic_core.utils.logger import get_logger

from .audio import ensure_ffmpeg

logger = get_logger(__name__)

# Поддерживаемые MIME-типы видео
SUPPORTED_VIDEO_TYPES = [
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-matroska",
    "video/mpeg",
]

# Уменьшенные пресеты — экономия ~40% токенов без потери качества
QUALITY_PRESETS = {
    "fhd": 1024,  # Было 1920 → 1024 (достаточно для Gemini Vision)
    "hd": 768,  # Было 1280 → 768
    "balanced": 512,  # Было 960 → 512
}

# Максимум по умолчанию
DEFAULT_MAX_DIMENSION = 1024


def extract_frames(
    video_path: str | Path,
    mode: Literal["fps", "total", "interval"] = "total",
    fps: float = 1.0,
    frame_count: int = 10,
    interval_seconds: float = 5.0,
    quality: Literal["fhd", "hd", "balanced"] = "hd",
    max_frames: int = 50,
) -> list[Image.Image]:
    """Извлекает кадры из видео.

    Три режима извлечения:
    - fps: Извлекать N кадров в секунду
    - total: Извлечь ровно N равномерно распределённых кадров
    - interval: Извлекать кадр каждые N секунд

    Args:
        video_path: Путь к видео-файлу.
        mode: Режим извлечения кадров.
        fps: Кадров в секунду (для mode="fps").
        frame_count: Количество кадров (для mode="total").
        interval_seconds: Интервал в секундах (для mode="interval").
        quality: Пресет качества (fhd/hd/balanced).
        max_frames: Максимальное количество кадров.

    Returns:
        Список PIL.Image кадров.

    Raises:
        DependencyError: Если ffmpeg не установлен.
        FileNotFoundError: Если видео не найдено.
        ValueError: Неизвестный режим.
    """
    ensure_ffmpeg()

    video_path = Path(video_path)
    if not video_path.exists():
        logger.error("Video file not found", path=str(video_path))
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Получаем метаданные
    meta = iio.immeta(str(video_path), plugin="pyav")
    duration = meta.get("duration", 0)
    video_fps = meta.get("fps", 30)
    total_frames_count = int(duration * video_fps)

    logger.debug(
        "Extracting frames from video",
        video_path=str(video_path),
        mode=mode,
        duration_sec=duration,
        video_fps=video_fps,
        total_frames_available=total_frames_count,
    )

    if total_frames_count == 0:
        logger.warning("Video has no frames", video_path=str(video_path))
        return []

    # Вычисляем индексы кадров
    if mode == "fps":
        step = max(1, int(video_fps / fps))
        indices = list(range(0, total_frames_count, step))
    elif mode == "total":
        if frame_count >= total_frames_count:
            indices = list(range(total_frames_count))
        else:
            indices = [
                int(i * total_frames_count / frame_count) for i in range(frame_count)
            ]
    elif mode == "interval":
        step = max(1, int(interval_seconds * video_fps))
        indices = list(range(0, total_frames_count, step))
    else:
        logger.error("Unknown extraction mode", mode=mode)
        raise ValueError(f"Unknown mode: {mode}")

    # Лимитируем количество кадров
    indices = indices[:max_frames]

    # Извлекаем кадры
    frames = []
    max_dim = QUALITY_PRESETS.get(quality, DEFAULT_MAX_DIMENSION)
    skipped_count = 0

    for idx in indices:
        try:
            frame = iio.imread(str(video_path), index=idx, plugin="pyav")
            img = Image.fromarray(frame)
            img = _resize_frame(img, max_dim)
            frames.append(img)
        except Exception as e:
            # Логируем пропущенный кадр и продолжаем
            logger.trace(
                "Skipped corrupted frame",
                video_path=str(video_path),
                frame_index=idx,
                error=str(e),
            )
            skipped_count += 1
            continue

    logger.info(
        "Frames extracted from video",
        video_path=str(video_path),
        mode=mode,
        frames_extracted=len(frames),
        frames_skipped=skipped_count,
        quality=quality,
        max_dimension=max_dim,
    )

    return frames


def frames_to_bytes(
    frames: list[Image.Image],
    format: str = "JPEG",
    quality: int = 85,
) -> list[tuple[bytes, str]]:
    """Конвертирует кадры в bytes для inline upload.

    Args:
        frames: Список PIL.Image кадров.
        format: Формат изображения (JPEG, PNG, WEBP).
        quality: Качество сжатия (1-100).

    Returns:
        Список tuple (image_bytes, mime_type).
    """
    logger.debug(
        "Converting frames to bytes",
        frames_count=len(frames),
        format=format,
        quality=quality,
    )

    result = []
    mime_type = f"image/{format.lower()}"

    for frame in frames:
        buffer = BytesIO()
        frame.save(buffer, format=format, quality=quality)
        result.append((buffer.getvalue(), mime_type))

    total_size = sum(len(item[0]) for item in result)
    logger.info(
        "Frames converted to bytes",
        frames_count=len(result),
        total_size_bytes=total_size,
        mime_type=mime_type,
    )

    return result


def get_video_duration(path: str | Path) -> float:
    """Возвращает длительность видео в секундах.

    Args:
        path: Путь к видео-файлу.

    Returns:
        Длительность в секундах.
    """
    meta = iio.immeta(str(path), plugin="pyav")
    duration = meta.get("duration", 0)
    logger.trace("Got video duration", path=str(path), duration_sec=duration)
    return duration


def get_video_metadata(path: str | Path) -> dict:
    """Возвращает метаданные видео.

    Args:
        path: Путь к видео-файлу.

    Returns:
        Словарь с метаданными (duration, fps, size, codec).
    """
    meta = iio.immeta(str(path), plugin="pyav")
    result = {
        "duration": meta.get("duration", 0),
        "fps": meta.get("fps", 0),
        "size": meta.get("size", (0, 0)),
        "codec": meta.get("codec", "unknown"),
    }
    logger.trace(
        "Got video metadata",
        path=str(path),
        duration=result["duration"],
        fps=result["fps"],
        size=result["size"],
    )
    return result


def is_video_supported(mime_type: str) -> bool:
    """Проверяет, поддерживается ли MIME-тип видео.

    Args:
        mime_type: MIME-тип для проверки.

    Returns:
        True если тип поддерживается.
    """
    return mime_type in SUPPORTED_VIDEO_TYPES


def _resize_frame(img: Image.Image, max_dim: int) -> Image.Image:
    """Ресайз кадра с сохранением пропорций.

    Args:
        img: PIL.Image кадр.
        max_dim: Максимальный размер стороны.

    Returns:
        Отресайзенный кадр.
    """
    width, height = img.size
    if max(width, height) <= max_dim:
        return img

    ratio = max_dim / max(width, height)
    new_size = (int(width * ratio), int(height * ratio))
    return img.resize(new_size, Image.Resampling.LANCZOS)
