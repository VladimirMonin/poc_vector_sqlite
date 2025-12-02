"""E2E тесты с реальным Gemini API.

⚠️ ВНИМАНИЕ: Эти тесты тратят токены!

Запуск:
    export GEMINI_API_KEY="your-key"
    pytest tests/e2e/gemini/ -m real_api -v

Реальные изображения (tests/asests/):
    - red_car.jpg — красный автомобиль
    - cat_photo.png — кот
    - eiffel_tower.jpg — Эйфелева башня
    - text_sign.jpg — фото с текстом (для OCR)
    - code_screen.jpg — скриншот кода
    - paris_street.jpg — парижская улица
    - seq_django_diagram.png — диаграмма Django
    - small_icon.webp — маленькая иконка (edge case)
    - 8k_japanese_walpaper.jpg — 8K обои (edge case)
"""

import pytest
import os

from semantic_core.domain.media import MediaResource, MediaRequest


# =============================================================================
# Module-level fixtures for real API tests
# =============================================================================


@pytest.fixture
def api_key():
    """API ключ из окружения."""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        pytest.skip("GEMINI_API_KEY not set")
    return key


@pytest.fixture
def analyzer(api_key):
    """Реальный GeminiImageAnalyzer."""
    from semantic_core.infrastructure.gemini.image_analyzer import (
        GeminiImageAnalyzer,
    )

    return GeminiImageAnalyzer(api_key=api_key)


# =============================================================================
# Basic Synthetic Tests (minimal token usage)
# =============================================================================


@pytest.mark.real_api
class TestRealGeminiImageAnalysis:
    """E2E тесты анализа изображений с реальным Gemini API."""

    def test_analyze_synthetic_red_square(self, analyzer, red_square_path):
        """Gemini описывает синтетический красный квадрат."""
        resource = MediaResource(
            path=red_square_path,
            media_type="image",
            mime_type="image/png",
        )
        request = MediaRequest(resource=resource)

        result = analyzer.analyze(request)

        # Проверяем структуру ответа
        assert result.description is not None
        assert len(result.description) > 10

        # Gemini должен упомянуть "red" или "square"
        text = result.description.lower()
        assert "red" in text or "square" in text or "color" in text

        print(f"\n🎨 Gemini says: {result.description}")
        print(f"   Alt-text: {result.alt_text}")
        print(f"   Keywords: {result.keywords}")

    def test_analyze_with_context(self, analyzer, red_square_path):
        """Контекст влияет на описание."""
        resource = MediaResource(
            path=red_square_path,
            media_type="image",
            mime_type="image/png",
        )
        request = MediaRequest(
            resource=resource,
            context_text="This is a logo for a tech company called RedBox",
        )

        result = analyzer.analyze(request)

        assert result.description is not None
        print(f"\n💼 With context: {result.description}")

    def test_analyze_returns_keywords(self, analyzer, red_square_path):
        """Результат содержит ключевые слова."""
        resource = MediaResource(
            path=red_square_path,
            media_type="image",
            mime_type="image/png",
        )
        request = MediaRequest(resource=resource)

        result = analyzer.analyze(request)

        assert isinstance(result.keywords, list)
        assert len(result.keywords) > 0

        print(f"\n🏷️  Keywords: {result.keywords}")


# =============================================================================
# Real Image Tests (use actual photos from tests/asests/)
# =============================================================================


@pytest.mark.real_api
class TestRealGeminiWithRealImages:
    """E2E тесты с реальными изображениями из tests/asests/.

    Каждый тест использует фикстуру из conftest.py.
    """

    def test_analyze_red_car(self, analyzer, red_car_path):
        """Анализ фото красного автомобиля."""
        resource = MediaResource(
            path=red_car_path,
            media_type="image",
            mime_type="image/jpeg",
        )
        request = MediaRequest(resource=resource)

        result = analyzer.analyze(request)

        # Должен распознать автомобиль
        text = result.description.lower()
        assert any(word in text for word in ["car", "vehicle", "auto", "red"])

        print(f"\n🚗 Red car: {result.description}")
        print(f"   Alt-text: {result.alt_text}")
        print(f"   Keywords: {result.keywords}")

    def test_analyze_cat_photo(self, analyzer, cat_photo_path):
        """Анализ фото кота."""
        resource = MediaResource(
            path=cat_photo_path,
            media_type="image",
            mime_type="image/png",
        )
        request = MediaRequest(resource=resource)

        result = analyzer.analyze(request)

        # Должен распознать кота
        text = result.description.lower()
        assert any(word in text for word in ["cat", "kitten", "feline", "pet"])

        print(f"\n🐱 Cat photo: {result.description}")
        print(f"   Keywords: {result.keywords}")

    def test_analyze_eiffel_tower(self, analyzer, eiffel_tower_path):
        """Анализ фото Эйфелевой башни."""
        resource = MediaResource(
            path=eiffel_tower_path,
            media_type="image",
            mime_type="image/jpeg",
        )
        request = MediaRequest(resource=resource)

        result = analyzer.analyze(request)

        # Должен распознать Эйфелеву башню или Париж
        text = result.description.lower()
        assert any(word in text for word in ["eiffel", "paris", "tower", "france"])

        print(f"\n🗼 Eiffel Tower: {result.description}")
        print(f"   Keywords: {result.keywords}")

    def test_analyze_text_sign_ocr(self, analyzer, text_sign_path):
        """Анализ изображения с текстом (OCR)."""
        resource = MediaResource(
            path=text_sign_path,
            media_type="image",
            mime_type="image/jpeg",
        )
        request = MediaRequest(
            resource=resource,
            user_prompt="Please extract any visible text from this image",
        )

        result = analyzer.analyze(request)

        # Должен вернуть OCR текст или описать текст
        has_ocr = result.ocr_text is not None and len(result.ocr_text) > 0
        mentions_text = "text" in result.description.lower()

        assert has_ocr or mentions_text

        print(f"\n📝 OCR result: {result.ocr_text}")
        print(f"   Description: {result.description}")

    def test_analyze_code_screenshot(self, analyzer, code_screenshot_path):
        """Анализ скриншота кода."""
        resource = MediaResource(
            path=code_screenshot_path,
            media_type="image",
            mime_type="image/jpeg",
        )
        request = MediaRequest(
            resource=resource,
            user_prompt="Describe this code screenshot and extract any visible code",
        )

        result = analyzer.analyze(request)

        # Должен распознать код
        text = result.description.lower()
        assert any(
            word in text
            for word in ["code", "programming", "script", "function", "screen"]
        )

        print(f"\n💻 Code screenshot: {result.description}")
        print(f"   OCR: {result.ocr_text[:200] if result.ocr_text else 'None'}...")

    def test_analyze_paris_street(self, analyzer, paris_street_path):
        """Анализ фото парижской улицы."""
        resource = MediaResource(
            path=paris_street_path,
            media_type="image",
            mime_type="image/jpeg",
        )
        request = MediaRequest(resource=resource)

        result = analyzer.analyze(request)

        # Должен распознать городскую сцену
        text = result.description.lower()
        assert any(
            word in text for word in ["paris", "street", "city", "urban", "building"]
        )

        print(f"\n🏙️  Paris street: {result.description}")

    def test_analyze_diagram(self, analyzer, diagram_path):
        """Анализ технической диаграммы."""
        resource = MediaResource(
            path=diagram_path,
            media_type="image",
            mime_type="image/png",
        )
        request = MediaRequest(
            resource=resource,
            user_prompt="Analyze this technical diagram and describe its structure",
        )

        result = analyzer.analyze(request)

        # Должен распознать диаграмму
        text = result.description.lower()
        assert any(
            word in text
            for word in ["diagram", "flow", "sequence", "django", "architecture"]
        )

        print(f"\n📊 Diagram: {result.description}")


# =============================================================================
# Edge Cases with Real Assets
# =============================================================================


@pytest.mark.real_api
class TestRealGeminiEdgeCases:
    """Тесты краевых случаев с реальными файлами."""

    def test_analyze_small_icon(self, analyzer, small_icon_path):
        """Маленькая иконка (WebP) обрабатывается корректно."""
        resource = MediaResource(
            path=small_icon_path,
            media_type="image",
            mime_type="image/webp",
        )
        request = MediaRequest(resource=resource)

        result = analyzer.analyze(request)

        assert result.description is not None
        assert len(result.description) > 5

        print(f"\n🔍 Small icon: {result.description}")

    def test_analyze_large_wallpaper(self, analyzer, large_wallpaper_path):
        """Большие 8K обои обрабатываются без ошибок."""
        resource = MediaResource(
            path=large_wallpaper_path,
            media_type="image",
            mime_type="image/jpeg",
        )
        request = MediaRequest(resource=resource)

        # Не должно упасть на большом изображении
        result = analyzer.analyze(request)

        assert result.description is not None
        print(f"\n📐 8K wallpaper: {result.description[:150]}...")
        print(f"   Keywords: {result.keywords}")


# =============================================================================
# Retry & Error Handling
# =============================================================================


@pytest.mark.real_api
class TestRealGeminiRetryBehavior:
    """Тесты retry поведения с реальным API."""

    def test_real_request_succeeds(self, api_key, red_square_path):
        """Реальный запрос успешен (retry не нужен)."""
        from semantic_core.infrastructure.gemini.image_analyzer import (
            GeminiImageAnalyzer,
        )

        analyzer = GeminiImageAnalyzer(api_key=api_key)

        resource = MediaResource(
            path=red_square_path,
            media_type="image",
            mime_type="image/png",
        )
        request = MediaRequest(resource=resource)

        # Не должен бросить исключение
        result = analyzer.analyze(request)
        assert result.description is not None
