"""Утилиты для оптимизации изображений.

Функции:
    resize_image(image: Image.Image, max_dimension: int) -> Image.Image
        Ресайз с сохранением пропорций.
    optimize_for_api(path: str, config: MediaConfig) -> tuple[bytes, str]
        Оптимизирует изображение для API.
"""

from io import BytesIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image
    from semantic_core.domain.config import MediaConfig


def resize_image(image: "Image.Image", max_dimension: int) -> "Image.Image":
    """Ресайз изображения с сохранением пропорций.

    Args:
        image: PIL Image объект.
        max_dimension: Максимальный размер большей стороны.

    Returns:
        Ресайзнутое изображение (или оригинал если меньше max_dimension).
    """
    width, height = image.size

    # Не нужен ресайз
    if max(width, height) <= max_dimension:
        return image

    # Вычисляем новые размеры с сохранением пропорций
    if width > height:
        new_width = max_dimension
        new_height = int(height * (max_dimension / width))
    else:
        new_height = max_dimension
        new_width = int(width * (max_dimension / height))

    # LANCZOS — лучшее качество для downscaling
    from PIL import Image as PILImage

    return image.resize((new_width, new_height), PILImage.Resampling.LANCZOS)


def optimize_for_api(
    path: str,
    max_dimension: int = 1920,
    image_format: str = "webp",
    quality: int = 80,
) -> tuple[bytes, str]:
    """Оптимизирует изображение для API.

    Ресайзит, конвертирует в оптимальный формат и сжимает.

    Args:
        path: Путь к файлу изображения.
        max_dimension: Максимальный размер стороны.
        image_format: Целевой формат (webp/jpeg).
        quality: Качество сжатия (1-100).

    Returns:
        Tuple (bytes, mime_type): Оптимизированные байты и MIME-тип.
    """
    from PIL import Image as PILImage

    image = PILImage.open(path)

    # Конвертируем RGBA в RGB для JPEG
    if image.mode == "RGBA" and image_format.lower() == "jpeg":
        background = PILImage.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        image = background
    elif image.mode != "RGB":
        image = image.convert("RGB")

    # Ресайз
    image = resize_image(image, max_dimension)

    # Конвертируем в байты
    buffer = BytesIO()
    save_format = image_format.upper()
    if save_format == "WEBP":
        image.save(buffer, format="WEBP", quality=quality)
        mime_type = "image/webp"
    else:
        image.save(buffer, format="JPEG", quality=quality)
        mime_type = "image/jpeg"

    return buffer.getvalue(), mime_type
