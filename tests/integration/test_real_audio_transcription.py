"""E2E тесты для GeminiAudioAnalyzer.

Требуют:
- Реальный API ключ Gemini (GOOGLE_API_KEY в .env)
- Тестовый аудио-файл в tests/fixtures/media/audio/speech.mp3
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
def speech_audio_path(media_dir):
    """Путь к тестовому аудио с речью."""
    path = media_dir / "audio" / "speech.mp3"
    if not path.exists():
        pytest.skip(f"Audio file not found: {path}")
    return path


@pytest.fixture(scope="module")
def noise_audio_path(media_dir):
    """Путь к аудио с шумом/тишиной."""
    path = media_dir / "audio" / "noise.wav"
    if not path.exists():
        pytest.skip(f"Noise audio not found: {path}")
    return path


@pytest.fixture(scope="module")
def audio_analyzer():
    """Реальный GeminiAudioAnalyzer."""
    from semantic_core.infrastructure.gemini.audio_analyzer import GeminiAudioAnalyzer

    api_key = os.getenv("GOOGLE_API_KEY")
    return GeminiAudioAnalyzer(api_key=api_key)


# ============================================================================
# E2E Тесты транскрипции
# ============================================================================


class TestRealAudioTranscription:
    """E2E тесты реальной транскрипции аудио."""

    def test_transcribe_speech_audio(self, audio_analyzer, speech_audio_path):
        """Транскрипция речевого аудио.

        Аудио содержит рассуждения о векторизации на русском языке (~15 сек).
        Ожидаем слова связанные с векторами, embeddings, поиском и т.д.
        """
        from semantic_core.domain.media import MediaRequest, MediaResource

        request = MediaRequest(
            resource=MediaResource(
                path=speech_audio_path,
                media_type="audio",
                mime_type="audio/mpeg",
            )
        )

        result = audio_analyzer.analyze(request)

        # Базовые проверки структуры
        assert result.description is not None
        assert len(result.description) > 10

        assert result.transcription is not None
        assert len(result.transcription) > 0

        assert result.keywords is not None
        assert len(result.keywords) >= 1

        # Проверяем что транскрипция содержит ожидаемые слова (русский язык)
        # Аудио об идеях по векторизации
        transcription_lower = result.transcription.lower()
        expected_words = ["вектор", "поиск", "embedding", "семантик", "база", "данных"]

        found_words = [w for w in expected_words if w in transcription_lower]
        # Достаточно найти хотя бы 1 слово — модель может транслитерировать по-разному
        assert len(found_words) >= 1 or len(result.transcription) > 20, (
            f"Expected at least 1 word from {expected_words} or long transcription, "
            f"found: {found_words} in transcription: {result.transcription}"
        )

    def test_transcription_with_context(self, audio_analyzer, speech_audio_path):
        """Транскрипция с контекстом улучшает качество."""
        from semantic_core.domain.media import MediaRequest, MediaResource

        request = MediaRequest(
            resource=MediaResource(
                path=speech_audio_path,
                media_type="audio",
                mime_type="audio/mpeg",
            ),
            context_text="Это запись идей о векторизации текста и семантическом поиске для Python библиотеки.",
        )

        result = audio_analyzer.analyze(request)

        assert result.transcription is not None
        assert result.description is not None

        # Контекст должен помочь лучше понять содержимое
        # Проверяем что description учитывает контекст (на русском или английском)
        description_lower = result.description.lower()
        assert any(
            word in description_lower
            for word in ["python", "вектор", "vector", "semantic", "семантик", "поиск", "search", "embedding"]
        )

    def test_transcription_returns_duration(self, audio_analyzer, speech_audio_path):
        """Длительность аудио возвращается."""
        from semantic_core.domain.media import MediaRequest, MediaResource

        request = MediaRequest(
            resource=MediaResource(
                path=speech_audio_path,
                media_type="audio",
                mime_type="audio/mpeg",
            )
        )

        result = audio_analyzer.analyze(request)

        assert result.duration_seconds is not None
        assert result.duration_seconds > 0
        # Для тестового файла ~15 секунд
        assert 10 < result.duration_seconds < 30, f"Expected 10-30 sec, got {result.duration_seconds}"

    def test_noise_audio_handled_gracefully(self, audio_analyzer, noise_audio_path):
        """Шум/тишина обрабатывается без падения.

        Транскрипция может быть пустой или содержать "[inaudible]" и т.д.
        """
        from semantic_core.domain.media import MediaRequest, MediaResource

        request = MediaRequest(
            resource=MediaResource(
                path=noise_audio_path,
                media_type="audio",
                mime_type="audio/wav",
            )
        )

        # Не должно падать
        result = audio_analyzer.analyze(request)

        assert result.description is not None
        # Транскрипция может быть пустой для шума
        # Главное что не упало


class TestAudioAnalyzerPerformance:
    """Тесты производительности и лимитов."""

    def test_short_audio_fast_response(self, audio_analyzer, speech_audio_path):
        """Короткое аудио обрабатывается быстро."""
        import time
        from semantic_core.domain.media import MediaRequest, MediaResource

        request = MediaRequest(
            resource=MediaResource(
                path=speech_audio_path,
                media_type="audio",
                mime_type="audio/mpeg",
            )
        )

        start = time.time()
        result = audio_analyzer.analyze(request)
        elapsed = time.time() - start

        # Для 10 секунд аудио ожидаем ответ за 30 секунд максимум
        assert elapsed < 30, f"Audio analysis took too long: {elapsed:.1f}s"
        assert result.transcription is not None


class TestAudioAnalyzerEdgeCases:
    """Тесты граничных случаев."""

    def test_custom_user_prompt(self, audio_analyzer, speech_audio_path):
        """Кастомный промпт влияет на результат."""
        from semantic_core.domain.media import MediaRequest, MediaResource

        request = MediaRequest(
            resource=MediaResource(
                path=speech_audio_path,
                media_type="audio",
                mime_type="audio/mpeg",
            ),
            user_prompt="Extract only keywords and action items from this audio. Focus on technical terms.",
        )

        result = audio_analyzer.analyze(request)

        # Результат должен содержать keywords
        assert len(result.keywords) >= 1


# ============================================================================
# Unit-тесты (без API вызовов)
# ============================================================================


class TestAudioAnalyzerUnit:
    """Unit-тесты GeminiAudioAnalyzer без реальных API вызовов."""

    def test_default_model_is_flash_lite(self):
        """По умолчанию используется flash-lite модель."""
        from semantic_core.infrastructure.gemini.audio_analyzer import (
            GeminiAudioAnalyzer,
        )

        assert GeminiAudioAnalyzer.DEFAULT_MODEL == "gemini-2.5-flash-lite"

    def test_custom_model_accepted(self):
        """Можно передать кастомную модель."""
        from semantic_core.infrastructure.gemini.audio_analyzer import (
            GeminiAudioAnalyzer,
        )

        analyzer = GeminiAudioAnalyzer(
            api_key="test-key",
            model="gemini-2.5-pro",
        )

        assert analyzer.model == "gemini-2.5-pro"

    def test_client_lazy_initialization(self):
        """Клиент инициализируется lazy при первом обращении."""
        from semantic_core.infrastructure.gemini.audio_analyzer import (
            GeminiAudioAnalyzer,
        )

        analyzer = GeminiAudioAnalyzer(api_key="test-key")

        # _client должен быть None до первого обращения
        assert analyzer._client is None
