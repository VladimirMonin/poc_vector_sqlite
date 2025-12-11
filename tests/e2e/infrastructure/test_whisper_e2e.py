"""E2E тесты для Whisper транскрипции на реальном аудио.

ВАЖНО:
    Эти тесты требуют установки зависимостей:
    pip install semantic-core[local-whisper]

    На Apple Silicon установится MLX, на других платформах - PyTorch.

Запуск:
    pytest tests/e2e/infrastructure/test_whisper_e2e.py -v -s

Пропуск если зависимости не установлены:
    pytest tests/e2e/infrastructure/test_whisper_e2e.py -v --co
"""

from pathlib import Path

import pytest

from semantic_core.interfaces.transcriber import TranscriptionResult

# Попытка импорта WhisperTranscriber
try:
    from semantic_core.infrastructure.local.whisper import WhisperTranscriber

    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False


# Skip все тесты если Whisper не установлен
pytestmark = pytest.mark.skipif(
    not WHISPER_AVAILABLE,
    reason="Whisper dependencies not installed. Install with: pip install semantic-core[local-whisper]",
)


@pytest.fixture
def test_audio_path() -> Path:
    """Путь к тестовому аудиофайлу."""
    return Path(__file__).parent.parent.parent / "asests" / "slides_ideas_audio.ogg"


@pytest.fixture
def whisper_transcriber() -> WhisperTranscriber:
    """Whisper транскрайбер с auto-detection устройства.

    Note:
        На Apple Silicon будет использоваться MLX (если установлен).
        На других платформах - PyTorch CUDA/MPS/CPU.
    """
    # Используем small модель для быстрых тестов (вместо large-v3-turbo)
    return WhisperTranscriber(model_size="small", batch_size=16)


class TestWhisperTranscriberE2E:
    """E2E тесты для WhisperTranscriber на реальном аудио."""

    def test_transcribe_real_audio(
        self, whisper_transcriber: WhisperTranscriber, test_audio_path: Path
    ):
        """Тест: транскрипция реального аудиофайла.

        Проверяем:
        - Файл успешно обрабатывается
        - Возвращается непустой текст
        - Присутствуют сегменты с таймкодами
        - Определён язык
        """
        assert test_audio_path.exists(), f"Test audio not found: {test_audio_path}"

        # Транскрипция (может занять 10-30 секунд)
        result = whisper_transcriber.transcribe(test_audio_path, language="ru")

        # Assertions
        assert isinstance(result, TranscriptionResult)
        assert len(result.full_text) > 0, "Transcription text is empty"
        assert result.language is not None, "Language not detected"

        # Проверка сегментов с таймкодами
        assert len(result.segments) > 0, "No segments returned"
        assert result.has_timestamps, "Timestamps not present"

        # Проверка первого сегмента
        first_segment = result.segments[0]
        assert first_segment.start_seconds >= 0.0
        assert first_segment.end_seconds > first_segment.start_seconds
        assert len(first_segment.text) > 0

        # Проверка длительности
        if result.duration_seconds:
            assert result.duration_seconds > 0

        # Вывод для визуального контроля
        print("\n=== Transcription Result ===")
        print(f"Language: {result.language}")
        print(f"Duration: {result.duration_seconds:.1f}s")
        print(f"Full text: {result.full_text[:100]}...")
        print(f"\nSegments ({len(result.segments)}):")
        for i, seg in enumerate(result.segments[:3]):  # Первые 3 сегмента
            print(
                f"  [{i}] {seg.start_seconds:.1f}s - {seg.end_seconds:.1f}s: {seg.text}"
            )

    def test_transcribe_auto_language_detection(
        self, whisper_transcriber: WhisperTranscriber, test_audio_path: Path
    ):
        """Тест: автоопределение языка (language=None)."""
        result = whisper_transcriber.transcribe(test_audio_path, language=None)

        assert result.language is not None
        assert len(result.full_text) > 0

        print(f"\n=== Auto-detected language: {result.language} ===")

    def test_transcribe_unsupported_format_raises(
        self, whisper_transcriber: WhisperTranscriber
    ):
        """Тест: ValueError при неподдерживаемом формате."""
        fake_path = Path("/tmp/test.avi")

        # Mock файл существует
        from unittest.mock import MagicMock

        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.suffix = ".avi"

        with pytest.raises(ValueError, match="Unsupported audio format"):
            whisper_transcriber.transcribe(mock_path)

    def test_supported_formats(self, whisper_transcriber: WhisperTranscriber):
        """Тест: список поддерживаемых форматов."""
        formats = whisper_transcriber.supported_formats

        assert "mp3" in formats
        assert "wav" in formats
        assert "flac" in formats
        assert "ogg" in formats
        assert "m4a" in formats
        assert "webm" in formats


class TestWhisperDeviceDetection:
    """Тесты для device detection в e2e сценариях."""

    def test_auto_device_detection(self):
        """Тест: автоопределение устройства работает."""
        transcriber = WhisperTranscriber(model_size="tiny")

        assert transcriber._device_type in ["mlx", "cuda", "mps", "cpu"]
        print(f"\n=== Detected device: {transcriber._device_type} ===")

    @pytest.mark.parametrize(
        "device",
        [
            "cpu",  # Всегда доступен
            # "mlx",  # Только на Apple Silicon
            # "cuda",  # Только с NVIDIA GPU
        ],
    )
    def test_forced_device(self, device: str):
        """Тест: принудительный выбор устройства."""
        transcriber = WhisperTranscriber(model_size="tiny", device=device)
        assert transcriber._device_type == device
