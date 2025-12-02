"""Универсальное извлечение кадров из GIF и видеофайлов.

Функции:
    extract_frames(source: Union[str, Image.Image], mode: str, ...) -> tuple[list[str], dict]
        Извлекает и оптимизирует кадры из видео или GIF.
"""

import base64
import io
from typing import Optional, Literal, Union
from PIL import Image
import imageio.v3 as iio
from utils.logger import get_logger
from utils.gif_processor import (
    _get_fps_indices,
    _get_total_indices,
    _get_interval_indices,
    _convert_frame,
    resize_image,
)

logger = get_logger(__name__)


def extract_frames(
    source: Union[str, Image.Image],
    mode: Literal["fps", "total", "interval"] = "total",
    frame_count: Optional[int] = 10,
    fps: Optional[float] = None,
    interval_sec: Optional[float] = None,
    max_dimension: int = 1920,
    output_format: Literal["webp", "jpeg", "png"] = "webp",
    quality: int = 80,
) -> tuple[list[str], dict]:
    """Извлекает и оптимизирует кадры из видео или GIF.

    Args:
        source: Путь к видео или PIL Image для GIF.
        mode: Режим извлечения ('fps', 'total', 'interval').
        frame_count: Количество кадров для режима 'total'.
        fps: Кадров в секунду для режима 'fps'.
        interval_sec: Интервал в секундах для режима 'interval'.
        max_dimension: Максимальное измерение для ресайза.
        output_format: Формат вывода ('webp', 'jpeg', 'png').
        quality: Качество сжатия (1-100).

    Returns:
        Кортеж (frames_base64, metadata).

    Raises:
        ValueError: Неверные параметры или формат файла.
        FileNotFoundError: Видеофайл не найден.
        RuntimeError: Ошибка извлечения кадров.
    """
    # Determine if source is GIF or video
    is_gif = isinstance(source, Image.Image)

    if is_gif:
        logger.info("Extracting frames from GIF")
        pil_frames = _extract_gif_frames(source, mode, fps, frame_count, interval_sec)
    else:
        logger.info(f"Extracting frames from video: {source}")
        pil_frames = _extract_video_frames(source, mode, fps, frame_count, interval_sec)

    if not pil_frames:
        raise RuntimeError("No frames extracted from source")

    logger.info(f"Extracted {len(pil_frames)} frames, converting to {output_format}...")

    # Resize and convert frames to base64
    frames_base64 = []
    total_size_bytes = 0

    for i, frame in enumerate(pil_frames, 1):
        # Resize if needed
        resized_frame = resize_image(frame, max_dimension)

        # Convert to base64
        frame_b64, frame_size = _convert_to_base64(
            resized_frame, output_format, quality
        )
        frames_base64.append(frame_b64)
        total_size_bytes += frame_size

        if i == 1:
            # Log first frame info
            w, h = resized_frame.size
            logger.info(
                f"Frame 1: {w}×{h}, {frame_size / 1024:.1f} KB ({output_format} q={quality})"
            )

    # Calculate metadata
    total_size_mb = total_size_bytes / (1024 * 1024)
    avg_frame_size_kb = (total_size_bytes / len(pil_frames)) / 1024
    w, h = pil_frames[0].size
    resolution = f"{w}×{h}"

    metadata = {
        "frame_count": len(pil_frames),
        "total_size_mb": round(total_size_mb, 3),
        "avg_frame_size_kb": round(avg_frame_size_kb, 1),
        "resolution": resolution,
        "format": output_format,
        "quality": quality,
    }

    logger.info(
        f"✅ Extracted {metadata['frame_count']} frames, "
        f"total size: {metadata['total_size_mb']:.2f} MB, "
        f"avg: {metadata['avg_frame_size_kb']:.1f} KB/frame"
    )

    return frames_base64, metadata


def _extract_gif_frames(
    image: Image.Image,
    mode: Literal["fps", "total", "interval"],
    fps: Optional[float],
    frame_count: Optional[int],
    interval_sec: Optional[float],
) -> list[Image.Image]:
    """Извлекает кадры из анимированного GIF."""
    if not getattr(image, "is_animated", False):
        logger.info("GIF is not animated, returning single frame")
        return [_convert_frame(image)]

    # Get GIF metadata
    gif_duration_ms = image.info.get("duration", 100)
    total_frames = getattr(image, "n_frames", 1)
    total_duration_sec = (gif_duration_ms * total_frames) / 1000.0
    native_fps = 1000.0 / gif_duration_ms

    logger.info(
        f"GIF: {total_frames} frames, {total_duration_sec:.1f}s, {native_fps:.1f} native fps"
    )

    # Calculate frame indices using gif_processor logic
    if mode == "fps":
        if fps is None:
            raise ValueError("Parameter 'fps' required for mode 'fps'")
        frame_indices = _get_fps_indices(total_frames, native_fps, fps)

    elif mode == "total":
        if frame_count is None:
            raise ValueError("Parameter 'frame_count' required for mode 'total'")
        frame_indices = _get_total_indices(total_frames, frame_count)

    elif mode == "interval":
        if interval_sec is None:
            raise ValueError("Parameter 'interval_sec' required for mode 'interval'")
        frame_indices = _get_interval_indices(
            total_frames, total_duration_sec, interval_sec
        )
    else:
        raise ValueError(f"Unknown mode: {mode}")

    logger.info(f"Selected {len(frame_indices)} frame indices using mode '{mode}'")

    # Extract frames at calculated indices
    frames = []
    for idx in frame_indices:
        image.seek(idx)
        frame = image.copy()
        frames.append(_convert_frame(frame))

    return frames


def _extract_video_frames(
    video_path: str,
    mode: Literal["fps", "total", "interval"],
    fps: Optional[float],
    frame_count: Optional[int],
    interval_sec: Optional[float],
) -> list[Image.Image]:
    """Извлекает кадры из видеофайла через imageio-ffmpeg."""
    # Get video metadata
    try:
        import math

        video_meta = iio.immeta(video_path)
        total_frames = video_meta.get("nframes", 0)
        native_fps = video_meta.get("fps", 30.0)
        duration = video_meta.get("duration", 0.0)

        # Handle inf/NaN values from metadata
        if isinstance(total_frames, (int, float)):
            if (
                total_frames == 0
                or math.isinf(total_frames)
                or math.isnan(total_frames)
            ):
                logger.warning(
                    f"Invalid frame count from metadata: {total_frames}, will read dynamically"
                )
                total_frames = None
            else:
                total_frames = int(total_frames)  # Convert to int if valid
        else:
            logger.warning(
                f"Unexpected frame count type: {type(total_frames)}, will read dynamically"
            )
            total_frames = None

        if duration == 0.0 or math.isinf(duration) or math.isnan(duration):
            if total_frames and total_frames > 0:
                duration = total_frames / native_fps
            else:
                duration = None

        if total_frames:
            logger.info(
                f"Video: {total_frames} frames, {duration:.1f}s, {native_fps:.1f} native fps"
            )
        else:
            logger.info(
                f"Video metadata incomplete, will read all frames (estimated {native_fps:.1f} fps)"
            )

    except Exception as e:
        logger.warning(f"Could not read video metadata: {e}")
        logger.info("Will extract frames and determine count dynamically")
        total_frames = None
        native_fps = 30.0  # fallback
        duration = None

    # Calculate frame indices
    if mode == "fps":
        if fps is None:
            raise ValueError("Parameter 'fps' required for mode 'fps'")

        # For FPS mode, we'll read every Nth frame
        if total_frames:
            frame_indices = _get_fps_indices(total_frames, native_fps, fps)
        else:
            # Read all frames and subsample
            frame_indices = None  # Will handle during reading

    elif mode == "total":
        if frame_count is None:
            raise ValueError("Parameter 'frame_count' required for mode 'total'")

        if total_frames:
            frame_indices = _get_total_indices(total_frames, frame_count)
        else:
            # Will need to read all frames first
            frame_indices = None

    elif mode == "interval":
        if interval_sec is None:
            raise ValueError("Parameter 'interval_sec' required for mode 'interval'")

        if total_frames and duration:
            frame_indices = _get_interval_indices(total_frames, duration, interval_sec)
        else:
            # Calculate based on assumed duration
            frame_indices = None

    else:
        raise ValueError(f"Unknown mode: {mode}")

    # Extract frames
    frames = []

    if frame_indices is not None:
        # We know exact indices to extract
        logger.info(f"Extracting {len(frame_indices)} frames at specific indices...")

        try:
            # Read video and extract specific frames
            for frame_idx, frame_array in enumerate(iio.imiter(video_path)):
                if frame_idx in frame_indices:
                    # Convert numpy array to PIL Image
                    pil_frame = Image.fromarray(frame_array)
                    pil_frame = _convert_frame(pil_frame)
                    frames.append(pil_frame)

                    # Stop if we have all needed frames
                    if len(frames) == len(frame_indices):
                        break

        except Exception as e:
            logger.error(f"Error reading video frames: {e}")
            raise RuntimeError(f"Failed to extract frames from video: {e}")

    else:
        # Need to read all frames first, then subsample
        logger.info("Reading all video frames for dynamic extraction...")

        try:
            all_frames = []
            for frame_array in iio.imiter(video_path):
                pil_frame = Image.fromarray(frame_array)
                pil_frame = _convert_frame(pil_frame)
                all_frames.append(pil_frame)

            total_frames = len(all_frames)
            logger.info(f"Read {total_frames} total frames")

            # Now calculate indices
            if mode == "fps":
                # Assume 30 fps if not known
                if fps is None:
                    raise ValueError("Parameter 'fps' required for mode 'fps'")
                frame_indices = _get_fps_indices(total_frames, native_fps, fps)
            elif mode == "total":
                if frame_count is None:
                    raise ValueError(
                        "Parameter 'frame_count' required for mode 'total'"
                    )
                frame_indices = _get_total_indices(total_frames, frame_count)
            elif mode == "interval":
                if interval_sec is None:
                    raise ValueError(
                        "Parameter 'interval_sec' required for mode 'interval'"
                    )
                # Calculate duration from frame count
                calc_duration = total_frames / native_fps
                frame_indices = _get_interval_indices(
                    total_frames, calc_duration, interval_sec
                )

            # Extract selected frames
            frames = [all_frames[i] for i in frame_indices if i < len(all_frames)]

        except Exception as e:
            logger.error(f"Error reading video frames: {e}")
            raise RuntimeError(f"Failed to extract frames from video: {e}")

    if not frames:
        raise RuntimeError("No frames were extracted from video")

    logger.info(f"Successfully extracted {len(frames)} frames from video")
    return frames


def _convert_to_base64(
    image: Image.Image, output_format: str, quality: int
) -> tuple[str, int]:
    """Конвертирует PIL Image в base64-строку."""
    buffer = io.BytesIO()

    # Convert format name to PIL format
    if output_format == "webp":
        image.save(buffer, format="WEBP", quality=quality, method=6)
    elif output_format == "jpeg":
        # Convert RGBA to RGB for JPEG
        if image.mode == "RGBA":
            rgb_image = Image.new("RGB", image.size, (255, 255, 255))
            rgb_image.paste(image, mask=image.split()[3])
            image = rgb_image
        image.save(buffer, format="JPEG", quality=quality, optimize=True)
    elif output_format == "png":
        image.save(buffer, format="PNG", optimize=True)
    else:
        raise ValueError(f"Unsupported output format: {output_format}")

    # Get size and base64
    buffer.seek(0)
    image_bytes = buffer.getvalue()
    size = len(image_bytes)
    b64_string = base64.b64encode(image_bytes).decode("utf-8")

    return b64_string, size
