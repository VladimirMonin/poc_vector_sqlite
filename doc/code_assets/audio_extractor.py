"""Утилиты извлечения и конвертации аудио из видео.

Функции:
    estimate_audio_size(duration_sec: float, bitrate: int) -> float
        Оценивает размер аудиофайла без обработки.
    extract_audio_from_video(video_path: str, ...) -> dict
        Извлекает и конвертирует аудиодорожку из видео.
    get_audio_metadata(video_path: str) -> dict
        Получает метаданные аудио без полного извлечения.
"""

import base64
import io
import os
from typing import Optional, Literal
from pydub import AudioSegment
from utils.logger import get_logger

logger = get_logger(__name__)


def estimate_audio_size(duration_sec: float, bitrate: int = 64) -> float:
    """Оценивает размер аудиофайла без обработки.

    Args:
        duration_sec: Длительность аудио в секундах.
        bitrate: Битрейт в kbps.

    Returns:
        Ожидаемый размер в МБ.
    """
    # Formula: (duration_sec * bitrate_kbps * 1000 bits/kbit) / 8 bits/byte
    size_bytes = (duration_sec * bitrate * 1000) / 8
    size_mb = size_bytes / (1024 * 1024)
    return round(size_mb, 2)


def extract_audio_from_video(
    video_path: str,
    bitrate: Literal[64, 32, 24] = 64,
    max_duration_sec: Optional[int] = None,
    dry_run: bool = False,
) -> dict:
    """Извлекает и конвертирует аудиодорожку из видео.

    Args:
        video_path: Путь к видеофайлу.
        bitrate: Битрейт в kbps (64/32/24).
        max_duration_sec: Максимальная длительность для извлечения.
        dry_run: Если True, только оценивает размер.

    Returns:
        Словарь с данными аудио.

    Raises:
        FileNotFoundError: Если видеофайл не найден.
        RuntimeError: Ошибка извлечения аудио.
    """
    if not os.path.exists(video_path):
        logger.error(f"Video file not found: {video_path}")
        raise FileNotFoundError(f"Video file not found: {video_path}")

    logger.info(f"Extracting audio from video: {video_path}")
    logger.info(f"Settings: bitrate={bitrate} kbps, mono, Vorbis (OGG)")

    try:
        # Load audio from video using pydub
        # pydub will use ffmpeg under the hood (from imageio-ffmpeg)
        logger.info("Loading audio track from video...")
        audio = AudioSegment.from_file(video_path)

        # Get original duration
        duration_ms = len(audio)
        duration_sec = duration_ms / 1000.0
        logger.info(f"Original audio: {duration_sec:.1f}s, {audio.channels} channels")

        # Trim if needed
        if max_duration_sec and duration_sec > max_duration_sec:
            logger.info(f"Trimming audio to {max_duration_sec}s")
            audio = audio[: max_duration_sec * 1000]
            duration_sec = max_duration_sec

        # If dry run, just estimate size
        if dry_run:
            estimated_size = estimate_audio_size(duration_sec, bitrate)
            logger.info(f"🔍 Dry run: estimated size {estimated_size:.2f} MB")

            return {
                "mime_type": "audio/ogg",
                "duration_sec": round(duration_sec, 1),
                "size_mb": estimated_size,
                "bitrate": bitrate,
                "channels": 1,
            }

        # Convert to mono
        if audio.channels > 1:
            logger.info("Converting stereo to mono...")
            audio = audio.set_channels(1)

        # Export to Vorbis (OGG) format in-memory
        logger.info(f"Converting to Vorbis mono {bitrate} kbps...")
        buffer = io.BytesIO()

        audio.export(
            buffer,
            format="ogg",
            codec="libvorbis",
            bitrate=f"{bitrate}k",
            parameters=["-ac", "1"],  # Force mono
        )

        # Get size and base64
        buffer.seek(0)
        audio_bytes = buffer.getvalue()
        actual_size_mb = len(audio_bytes) / (1024 * 1024)
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

        logger.info(
            f"✅ Audio extracted: {duration_sec:.1f}s, "
            f"{actual_size_mb:.2f} MB, "
            f"{bitrate} kbps mono"
        )

        return {
            "base64": audio_b64,
            "mime_type": "audio/ogg",
            "duration_sec": round(duration_sec, 1),
            "size_mb": round(actual_size_mb, 3),
            "bitrate": bitrate,
            "channels": 1,
        }

    except FileNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to extract audio: {e}")
        raise RuntimeError(f"Audio extraction failed: {e}")


def get_audio_metadata(video_path: str) -> dict:
    """Получает метаданные аудио без полного извлечения.

    Args:
        video_path: Путь к видеофайлу.

    Returns:
        Словарь с метаданными.

    Raises:
        FileNotFoundError: Если видеофайл не найден.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    try:
        # Load just the first second to get metadata
        audio = AudioSegment.from_file(video_path, duration=1.0)

        # Get full file duration by loading without limit
        full_audio = AudioSegment.from_file(video_path)
        duration_sec = len(full_audio) / 1000.0

        return {
            "duration_sec": round(duration_sec, 1),
            "channels": audio.channels,
            "sample_rate": audio.frame_rate,
            "has_audio": True,
        }

    except Exception as e:
        logger.warning(f"Could not extract audio metadata: {e}")
        return {
            "duration_sec": 0.0,
            "channels": 0,
            "sample_rate": 0,
            "has_audio": False,
        }
