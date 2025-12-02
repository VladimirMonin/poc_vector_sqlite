"""Тесты infrastructure/media/utils/tokens.py - расчёт токенов для изображений."""

import pytest

try:
    from PIL import Image

    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

from semantic_core.infrastructure.media.utils.tokens import (
    calculate_image_tokens,
    calculate_images_tokens,
    estimate_cost,
    TOKENS_PER_TILE,
)


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not installed")
class TestCalculateImageTokens:
    """Тесты для calculate_image_tokens."""

    def test_small_image_258_tokens(self):
        """Маленькое изображение (<=384x384) = 258 токенов."""
        img = Image.new("RGB", (300, 300))
        tokens = calculate_image_tokens(img)
        assert tokens == TOKENS_PER_TILE  # 258

    def test_tiny_image(self):
        """Очень маленькое изображение."""
        img = Image.new("RGB", (100, 100))
        assert calculate_image_tokens(img) == 258

    def test_edge_case_384x384(self):
        """Граничный случай 384x384."""
        img = Image.new("RGB", (384, 384))
        assert calculate_image_tokens(img) == 258

    def test_medium_image_tiling(self):
        """Среднее изображение 800x600 - тайлинг."""
        img = Image.new("RGB", (800, 600))
        tokens = calculate_image_tokens(img)

        # min_dim=600, crop_unit=400, tiles=2x2=4, tokens=4*258=1032
        assert tokens == 1032

    def test_large_image_1080p(self):
        """Большое изображение 1920x1080."""
        img = Image.new("RGB", (1920, 1080))
        tokens = calculate_image_tokens(img)

        # min_dim=1080, crop_unit=720, tiles=3x2=6
        # tokens = 6 * 258 = 1548
        assert tokens > 1000
        assert tokens == 1548

    def test_very_large_4k(self):
        """4K изображение - большой crop_unit."""
        img = Image.new("RGB", (3840, 2160))
        tokens = calculate_image_tokens(img)

        # min_dim=2160, crop_unit=1440, tiles=3x2=6
        # tokens = 6 * 258 = 1548
        assert tokens == 1548

    def test_portrait_orientation(self):
        """Портретная ориентация (высота > ширины)."""
        img = Image.new("RGB", (600, 800))
        tokens = calculate_image_tokens(img)

        # Такое же как 800x600
        assert tokens == 1032


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not installed")
class TestCalculateImagesTokens:
    """Тесты для calculate_images_tokens (для списка)."""

    def test_single_image(self):
        """Один элемент в списке."""
        images = [Image.new("RGB", (200, 200))]
        result = calculate_images_tokens(images)

        assert result["total_tokens"] == 258
        assert result["image_count"] == 1
        assert len(result["per_image"]) == 1

    def test_multiple_images(self):
        """Несколько изображений."""
        images = [
            Image.new("RGB", (200, 200)),  # 258
            Image.new("RGB", (800, 600)),  # 1032
        ]
        result = calculate_images_tokens(images)

        assert result["total_tokens"] == 258 + 1032
        assert result["image_count"] == 2
        assert result["per_image"] == [258, 1032]

    def test_breakdown_format(self):
        """Проверка формата breakdown."""
        images = [Image.new("RGB", (100, 100))]
        result = calculate_images_tokens(images)

        assert "breakdown" in result
        assert "Total:" in result["breakdown"]
        assert "Frame 1" in result["breakdown"]


class TestEstimateCost:
    """Тесты для estimate_cost."""

    def test_flash_model(self):
        """Оценка для gemini-2.5-flash."""
        result = estimate_cost(1000, "gemini-2.5-flash")

        assert result["tokens"] == 1000
        assert result["model"] == "gemini-2.5-flash"
        assert "estimated_input_cost_usd" in result
        assert result["estimated_input_cost_usd"] >= 0

    def test_pro_model_more_expensive(self):
        """Pro модель дороже Flash."""
        flash_cost = estimate_cost(1000, "gemini-2.5-flash")
        pro_cost = estimate_cost(1000, "gemini-2.5-pro")

        assert (
            pro_cost["estimated_input_cost_usd"]
            > flash_cost["estimated_input_cost_usd"]
        )

    def test_unknown_model_uses_flash(self):
        """Неизвестная модель использует цены flash."""
        result = estimate_cost(1000, "unknown-model")
        flash = estimate_cost(1000, "gemini-2.5-flash")

        assert result["estimated_input_cost_usd"] == flash["estimated_input_cost_usd"]

    def test_cost_scales_with_tokens(self):
        """Стоимость растёт линейно с токенами."""
        cost_1k = estimate_cost(1000, "gemini-2.5-flash")
        cost_2k = estimate_cost(2000, "gemini-2.5-flash")

        # Используем rel tolerance из-за floating point precision
        assert cost_2k["estimated_input_cost_usd"] == pytest.approx(
            cost_1k["estimated_input_cost_usd"] * 2, rel=0.1
        )

    def test_note_present(self):
        """Результат содержит примечание."""
        result = estimate_cost(1000, "gemini-2.5-flash")
        assert "note" in result
