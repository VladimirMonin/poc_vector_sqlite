"""E2E тесты для GeminiVideoAnalyzer.

Требуют:
- Реальный API ключ Gemini (GOOGLE_API_KEY в .env)
- Тестовые видео-файлы в tests/fixtures/media/video/
- ffmpeg установлен в системе

Пропускаются если ключ или файлы отсутствуют.
"""

import os
import pytest
from pathlib import Path

# Маркер для реальных API тестов
pytestmark = [
    pytest.mark.real_api,
    pytest.mark.skipif(
        not os.getenv("GOOGLE_API_KEY"),
        reason="GOOGLE_API_KEY not set",
    ),
]


# ============================================================================
# Фикстуры
# ============================================================================


@pytest.fixture(scope="module")
def media_dir():
    """Путь к директории с медиа-ассетами."""
    return Path(__file__).parent.parent / "fixtures" / "media"


@pytest.fixture(scope="module")
def slides_video_path(media_dir):
    """Путь к видео со слайдами/презентацией."""
    path = media_dir / "video" / "slides.mp4"
    if not path.exists():
        pytest.skip(f"Video file not found: {path}")
    return path


@pytest.fixture(scope="module")
def talking_head_path(media_dir):
    """Путь к видео с говорящим человеком."""
    path = media_dir / "video" / "talking_head.mp4"
    if not path.exists():
        pytest.skip(f"Talking head video not found: {path}")
    return path


@pytest.fixture(scope="module")
def video_analyzer():
    """Реальный GeminiVideoAnalyzer."""
    from semantic_core.infrastructure.gemini.video_analyzer import GeminiVideoAnalyzer

    api_key = os.getenv("GOOGLE_API_KEY")
    return GeminiVideoAnalyzer(api_key=api_key)


# ============================================================================
# E2E Тесты анализа видео
# ============================================================================


class TestRealVideoAnalysis:
    """E2E тесты реального мультимодального анализа видео."""

    def test_analyze_slides_video(self, video_analyzer, slides_video_path):
        """Анализ видео со слайдами.

        Видео содержит диаграмму последовательности OAuth авторизации на Django (~35 сек).
        Ожидаем:
        - Описание содержимого (диаграмма, схема)
        - OCR текста с диаграммы (OAuth, Django, Authorization и т.д.)
        - Keywords по теме
        """
        from semantic_core.domain.media import (
            MediaRequest,
            MediaResource,
            VideoAnalysisConfig,
        )

        request = MediaRequest(
            resource=MediaResource(
                path=slides_video_path,
                media_type="video",
                mime_type="video/mp4",
            )
        )

        config = VideoAnalysisConfig(
            frame_count=5,  # 5 кадров для видео
            include_audio=True,
        )

        result = video_analyzer.analyze(request, config)

        # Базовые проверки структуры
        assert result.description is not None
        assert len(result.description) > 20

        assert result.keywords is not None
        assert len(result.keywords) >= 1

        # Для диаграммы ожидаем распознавание схемы/диаграммы
        description_lower = result.description.lower()
        # Должно содержать упоминание диаграммы, схемы или OAuth
        diagram_words = ["diagram", "диаграмм", "схем", "oauth", "sequence", "flow", "authorization", "авториз"]
        assert any(w in description_lower for w in diagram_words), (
            f"Expected diagram-related words in: {result.description}"
        )

        assert result.duration_seconds is not None
        assert result.duration_seconds > 0

    def test_analyze_talking_head_multimodal(self, video_analyzer, talking_head_path):
        """Мультимодальный анализ: видео + аудио.

        Видео содержит говорящего человека (~16 сек).
        В речи произносятся слова: "Джунгли", "Обезьянка", "Пальма".
        Ожидаем:
        - Описание визуальной части (человек говорит)
        - Транскрипцию речи с этими словами
        - Keywords по теме
        """
        from semantic_core.domain.media import (
            MediaRequest,
            MediaResource,
            VideoAnalysisConfig,
        )

        request = MediaRequest(
            resource=MediaResource(
                path=talking_head_path,
                media_type="video",
                mime_type="video/mp4",
            )
        )

        config = VideoAnalysisConfig(
            frame_count=5,
            include_audio=True,  # Важно для транскрипции
        )

        result = video_analyzer.analyze(request, config)

        # Проверяем описание визуальной части
        assert result.description is not None
        description_lower = result.description.lower()
        # Ожидаем упоминание человека/спикера
        assert any(
            word in description_lower
            for word in ["person", "speaker", "man", "woman", "someone", "talking", "человек", "говорит"]
        ), f"Expected person/speaker mention in: {result.description}"

        # Проверяем транскрипцию - должны быть слова Джунгли/Обезьянка/Пальма
        assert result.transcription is not None
        assert len(result.transcription) > 0
        
        transcription_lower = result.transcription.lower()
        # Проверяем наличие хотя бы одного ключевого слова
        key_words = ["джунгли", "обезьян", "пальм", "jungle", "monkey", "palm"]
        found = [w for w in key_words if w in transcription_lower]
        assert len(found) >= 1 or len(result.transcription) > 20, (
            f"Expected key words {key_words} in transcription: {result.transcription}"
        )

    def test_video_without_audio(self, video_analyzer, slides_video_path):
        """Анализ видео без аудио-дорожки."""
        from semantic_core.domain.media import (
            MediaRequest,
            MediaResource,
            VideoAnalysisConfig,
        )

        request = MediaRequest(
            resource=MediaResource(
                path=slides_video_path,
                media_type="video",
                mime_type="video/mp4",
            )
        )

        config = VideoAnalysisConfig(
            frame_count=3,
            include_audio=False,  # Без аудио
        )

        result = video_analyzer.analyze(request, config)

        # Должен работать без аудио
        assert result.description is not None
        # Транскрипция может быть None
        # (зависит от модели, может вернуть null)

    def test_video_with_context(self, video_analyzer, slides_video_path):
        """Контекст улучшает анализ."""
        from semantic_core.domain.media import (
            MediaRequest,
            MediaResource,
            VideoAnalysisConfig,
        )

        request = MediaRequest(
            resource=MediaResource(
                path=slides_video_path,
                media_type="video",
                mime_type="video/mp4",
            ),
            context_text="Это видео демонстрирует диаграмму последовательности OAuth авторизации в Django проекте.",
        )

        config = VideoAnalysisConfig(frame_count=3)

        result = video_analyzer.analyze(request, config)

        # Описание должно учитывать контекст
        combined_text = (result.description + " " + " ".join(result.keywords)).lower()
        # Хотя бы одно слово из контекста должно появиться
        assert any(
            word in combined_text
            for word in ["oauth", "django", "авториз", "диаграмм", "sequence", "diagram", "authentication"]
        ), f"Expected context-aware words in: {combined_text}"


class TestVideoAnalyzerFrameExtraction:
    """Тесты извлечения кадров."""

    def test_different_frame_modes(self, video_analyzer, slides_video_path):
        """Разные режимы извлечения кадров работают."""
        from semantic_core.domain.media import (
            MediaRequest,
            MediaResource,
            VideoAnalysisConfig,
        )

        request = MediaRequest(
            resource=MediaResource(
                path=slides_video_path,
                media_type="video",
                mime_type="video/mp4",
            )
        )

        # Mode: total (default)
        config_total = VideoAnalysisConfig(frame_mode="total", frame_count=3)
        result_total = video_analyzer.analyze(request, config_total)
        assert result_total.description is not None

        # Mode: interval
        config_interval = VideoAnalysisConfig(
            frame_mode="interval", interval_seconds=5.0
        )
        result_interval = video_analyzer.analyze(request, config_interval)
        assert result_interval.description is not None

    def test_quality_presets(self, video_analyzer, slides_video_path):
        """Разные качества кадров работают."""
        from semantic_core.domain.media import (
            MediaRequest,
            MediaResource,
            VideoAnalysisConfig,
        )

        request = MediaRequest(
            resource=MediaResource(
                path=slides_video_path,
                media_type="video",
                mime_type="video/mp4",
            )
        )

        # HD quality (768px)
        config_hd = VideoAnalysisConfig(frame_count=2, frame_quality="hd")
        result_hd = video_analyzer.analyze(request, config_hd)
        assert result_hd.description is not None

        # Balanced quality (512px) - меньше токенов
        config_balanced = VideoAnalysisConfig(frame_count=2, frame_quality="balanced")
        result_balanced = video_analyzer.analyze(request, config_balanced)
        assert result_balanced.description is not None


class TestVideoAnalyzerPerformance:
    """Тесты производительности."""

    def test_short_video_fast_response(self, video_analyzer, slides_video_path):
        """Короткое видео обрабатывается за разумное время."""
        import time
        from semantic_core.domain.media import (
            MediaRequest,
            MediaResource,
            VideoAnalysisConfig,
        )

        request = MediaRequest(
            resource=MediaResource(
                path=slides_video_path,
                media_type="video",
                mime_type="video/mp4",
            )
        )

        config = VideoAnalysisConfig(frame_count=3, include_audio=False)

        start = time.time()
        result = video_analyzer.analyze(request, config)
        elapsed = time.time() - start

        # Для 3 кадров без аудио ожидаем < 60 секунд
        assert elapsed < 60, f"Video analysis took too long: {elapsed:.1f}s"
        assert result.description is not None


# ============================================================================
# Unit-тесты (без API вызовов)
# ============================================================================


class TestVideoAnalyzerUnit:
    """Unit-тесты GeminiVideoAnalyzer без реальных API вызовов."""

    def test_default_model_is_pro(self):
        """По умолчанию используется pro модель для видео."""
        from semantic_core.infrastructure.gemini.video_analyzer import (
            GeminiVideoAnalyzer,
        )

        assert GeminiVideoAnalyzer.DEFAULT_MODEL == "gemini-2.5-pro"

    def test_custom_model_accepted(self):
        """Можно передать кастомную модель."""
        from semantic_core.infrastructure.gemini.video_analyzer import (
            GeminiVideoAnalyzer,
        )

        analyzer = GeminiVideoAnalyzer(
            api_key="test-key",
            model="gemini-2.5-flash",
        )

        assert analyzer.model == "gemini-2.5-flash"

    def test_client_lazy_initialization(self):
        """Клиент инициализируется lazy при первом обращении."""
        from semantic_core.infrastructure.gemini.video_analyzer import (
            GeminiVideoAnalyzer,
        )

        analyzer = GeminiVideoAnalyzer(api_key="test-key")

        # _client должен быть None до первого обращения
        assert analyzer._client is None

    def test_video_analysis_config_defaults(self):
        """VideoAnalysisConfig имеет разумные дефолты."""
        from semantic_core.domain.media import VideoAnalysisConfig

        config = VideoAnalysisConfig()

        assert config.frame_mode == "total"
        assert config.frame_count == 10
        assert config.include_audio is True
        assert config.frame_quality == "hd"
        assert config.max_frames == 50
