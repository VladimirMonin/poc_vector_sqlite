"""Утилиты обработки GIF-анимаций.

Функции:
    extract_gif_frames(image: Image.Image, mode: str, ...) -> list[Image.Image]
        Извлекает кадры из анимированного GIF.
    resize_image(image: Image.Image, max_dimension: int) -> Image.Image
        Изменяет размер изображения с сохранением пропорций.
    create_animation_prompt(user_prompt: str, ...) -> str
        Создаёт контекстно-зависимый промпт для анализа анимации.
"""

from typing import Optional, Literal
from PIL import Image
from utils.logger import get_logger

logger = get_logger(__name__)


def extract_gif_frames(
    image: Image.Image,
    mode: Literal["fps", "total", "interval"] = "total",
    gif_fps: Optional[float] = None,
    frame_count: Optional[int] = None,
    interval_sec: Optional[float] = None,
) -> list[Image.Image]:
    """Извлекает кадры из анимированного GIF.

    Args:
        image: PIL Image объект (анимированный GIF).
        mode: Режим извлечения ('fps', 'total', 'interval').
        gif_fps: Кадров в секунду для режима 'fps'.
        frame_count: Количество кадров для режима 'total'.
        interval_sec: Интервал в секундах для режима 'interval'.

    Returns:
        Список извлечённых кадров как PIL Images.

    Raises:
        ValueError: Если требуемые параметры для режима отсутствуют.
    """
    if not getattr(image, "is_animated", False):
        logger.info("Image is not animated, returning single frame")
        return [_convert_frame(image)]

    # Get GIF metadata
    gif_duration_ms = image.info.get("duration", 100)  # milliseconds per frame
    total_frames = getattr(image, "n_frames", 1)
    total_duration_sec = (gif_duration_ms * total_frames) / 1000.0
    native_fps = 1000.0 / gif_duration_ms

    logger.info(
        f"GIF info: {total_frames} frames, {total_duration_sec:.1f}s, {native_fps:.1f} fps"
    )

    # Determine frame indices based on mode
    if mode == "fps":
        if gif_fps is None:
            raise ValueError("Parameter 'gif_fps' required for mode 'fps'")
        frame_indices = _get_fps_indices(total_frames, native_fps, gif_fps)

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

    logger.info(f"Extracting {len(frame_indices)} frames using mode '{mode}'")

    # Extract frames at calculated indices
    frames = []
    for idx in frame_indices:
        image.seek(idx)
        frame = image.copy()
        frames.append(_convert_frame(frame))

    return frames


def _get_fps_indices(
    total_frames: int, native_fps: float, target_fps: float
) -> list[int]:
    """Рассчитывает индексы кадров для режима FPS."""
    frame_step = max(1, int(native_fps / target_fps))
    return list(range(0, total_frames, frame_step))


def _get_total_indices(total_frames: int, frame_count: int) -> list[int]:
    """Рассчитывает равномерно распределённые индексы кадров для режима TOTAL."""
    if frame_count >= total_frames:
        return list(range(total_frames))

    # Evenly distribute frames
    step = total_frames / frame_count
    indices = [int(i * step) for i in range(frame_count)]

    return indices


def _get_interval_indices(
    total_frames: int, total_duration_sec: float, interval_sec: float
) -> list[int]:
    """Рассчитывает индексы кадров для режима INTERVAL."""
    if total_duration_sec <= 0:
        return [0]

    frames_per_sec = total_frames / total_duration_sec
    frame_step = max(1, int(interval_sec * frames_per_sec))

    return list(range(0, total_frames, frame_step))


def _convert_frame(frame: Image.Image) -> Image.Image:
    """Конвертирует кадр в совместимый режим для Gemini API."""
    # Convert palette mode (P) and other incompatible modes to RGB
    if frame.mode in ("P", "LA", "PA"):
        return frame.convert("RGB")
    elif frame.mode == "RGBA":
        return frame  # Keep RGBA - it's supported
    elif frame.mode not in ("RGB", "L"):
        return frame.convert("RGB")
    return frame


def resize_image(image: Image.Image, max_dimension: Optional[int]) -> Image.Image:
    """Изменяет размер изображения с сохранением пропорций.

    Args:
        image: PIL Image объект.
        max_dimension: Максимальный размер длинной стороны.

    Returns:
        Изображение с изменённым размером.
    """
    if max_dimension is None:
        return image

    width, height = image.size
    max_current = max(width, height)

    if max_current <= max_dimension:
        return image

    scale = max_dimension / max_current
    new_width = int(width * scale)
    new_height = int(height * scale)

    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)


def create_animation_prompt(
    user_prompt: str, frame_count: int, extraction_info: str, system_prompt: str
) -> str:
    """Создаёт контекстно-зависимый промпт для анализа анимации.

    Args:
        user_prompt: Оригинальный промпт пользователя.
        frame_count: Количество извлечённых кадров.
        extraction_info: Описание метода извлечения.
        system_prompt: Системный промпт.

    Returns:
        Расширенный промпт с контекстом анимации.
    """
    context_prompt = f"""{system_prompt}

**Animation Details:**
- Total frames analyzed: {frame_count}
- Extraction method: {extraction_info}

**User's Specific Request:**
{user_prompt}

Please provide your analysis based on the frames and the user's request above."""

    return context_prompt
