"""Утилиты расчёта токенов для обработки медиа Gemini API.

Функции:
    calculate_image_tokens(image: Image.Image) -> int
        Рассчитывает количество токенов для изображения.
    calculate_images_tokens(images: List[Image.Image]) -> dict
        Рассчитывает общее количество токенов для списка изображений.
    estimate_cost(tokens: int, model: str) -> dict
        Оценивает стоимость API на основе количества токенов.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image

# Токены на один тайл изображения (фиксированное значение Gemini)
TOKENS_PER_TILE = 258


def calculate_image_tokens(image: "Image.Image") -> int:
    """Рассчитывает количество токенов для изображения.

    Алгоритм Gemini:
    - Изображения <= 384x384: 258 токенов
    - Большие изображения: тайлинг (crop_unit = min_dim / 1.5)

    Args:
        image: PIL Image объект.

    Returns:
        Ожидаемое количество токенов.
    """
    width, height = image.size

    # Small images (both dimensions ≤ 384px)
    if width <= 384 and height <= 384:
        return TOKENS_PER_TILE

    # Large images - tiled processing
    min_dim = min(width, height)
    crop_unit = int(min_dim / 1.5)

    tiles_w = (width + crop_unit - 1) // crop_unit  # ceiling division
    tiles_h = (height + crop_unit - 1) // crop_unit
    total_tiles = tiles_w * tiles_h

    return total_tiles * TOKENS_PER_TILE


def calculate_images_tokens(images: list["Image.Image"]) -> dict:
    """Рассчитывает общее количество токенов для списка изображений.

    Args:
        images: Список PIL Image объектов.

    Returns:
        Словарь с разбивкой по изображениям:
        - total_tokens: Общее количество токенов.
        - image_count: Количество изображений.
        - per_image: Список токенов по каждому изображению.
        - breakdown: Текстовый отчёт.
    """
    per_image_tokens = [calculate_image_tokens(img) for img in images]
    total = sum(per_image_tokens)

    # Create detailed breakdown
    breakdown_lines = []
    for i, (img, tokens) in enumerate(zip(images, per_image_tokens), 1):
        w, h = img.size
        breakdown_lines.append(f"Frame {i} ({w}×{h}): {tokens:,} tokens")

    breakdown_lines.append(f"Total: {total:,} tokens")
    breakdown = "\n".join(breakdown_lines)

    return {
        "total_tokens": total,
        "image_count": len(images),
        "per_image": per_image_tokens,
        "breakdown": breakdown,
    }


# Ценовые тарифы Gemini (USD per 1K tokens)
GEMINI_PRICING = {
    "gemini-2.5-flash-lite": {
        "input": 0.00001875,
        "output": 0.000075,
    },
    "gemini-2.5-flash": {
        "input": 0.00001875,
        "output": 0.000075,
    },
    "gemini-2.5-pro": {
        "input": 0.00125,
        "output": 0.005,
    },
    "gemini-2.0-flash": {
        "input": 0.00001875,
        "output": 0.000075,
    },
}


def estimate_cost(tokens: int, model: str = "gemini-2.5-flash") -> dict:
    """Оценивает стоимость API на основе количества токенов.

    Args:
        tokens: Общее количество токенов.
        model: Название модели.

    Returns:
        Словарь с оценкой стоимости:
        - tokens: Количество токенов.
        - model: Использованная модель.
        - estimated_input_cost_usd: Оценка стоимости в USD.
        - note: Примечание.
    """
    rates = GEMINI_PRICING.get(model, GEMINI_PRICING["gemini-2.5-flash"])
    input_cost = (tokens / 1000) * rates["input"]

    return {
        "tokens": tokens,
        "model": model,
        "estimated_input_cost_usd": round(input_cost, 6),
        "note": "Output tokens charged separately based on response length",
    }
