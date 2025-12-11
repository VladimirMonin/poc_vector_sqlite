"""Unit-тесты для Whisper локальной транскрипции.

Тестируемые модули:
    - semantic_core.infrastructure.local.whisper.device
    - semantic_core.infrastructure.local.whisper.models
    - semantic_core.infrastructure.local.whisper.transcriber
    - semantic_core.infrastructure.local.whisper.__init__

Запуск:
    pytest tests/unit/infrastructure/local/test_whisper.py -v
"""

import platform
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from semantic_core.interfaces.transcriber import (
    TranscriptionResult,
    TranscriptionSegment,
)


# Проверяем наличие lightning_whisper_mlx для MLX тестов
try:
    import lightning_whisper_mlx
    HAS_LIGHTNING_MLX = True
except ImportError:
    HAS_LIGHTNING_MLX = False


# ============================================================================
# Tests: device.py
# ============================================================================


class TestDeviceDetection:
    """Тесты для device.py - определение оптимального устройства."""

    def test_is_apple_silicon_m_series(self):
        """Тест: is_apple_silicon() на Apple Silicon M-серии."""
        with patch("platform.system", return_value="Darwin"):
            with patch("platform.machine", return_value="arm64"):
                from semantic_core.infrastructure.local.whisper.device import is_apple_silicon

                assert is_apple_silicon() is True

    def test_is_apple_silicon_intel_mac(self):
        """Тест: is_apple_silicon() на Intel Mac."""
        with patch("platform.system", return_value="Darwin"):
            with patch("platform.machine", return_value="x86_64"):
                from semantic_core.infrastructure.local.whisper.device import is_apple_silicon

                assert is_apple_silicon() is False

    def test_is_apple_silicon_linux(self):
        """Тест: is_apple_silicon() на Linux."""
        with patch("platform.system", return_value="Linux"):
            from semantic_core.infrastructure.local.whisper.device import is_apple_silicon

            assert is_apple_silicon() is False

    def test_is_apple_silicon_windows(self):
        """Тест: is_apple_silicon() на Windows."""
        with patch("platform.system", return_value="Windows"):
            from semantic_core.infrastructure.local.whisper.device import is_apple_silicon

            assert is_apple_silicon() is False

    def test_get_device_info_forced_mlx(self):
        """Тест: get_device_info() с принудительным MLX."""
        with patch.dict("os.environ", {"WHISPER_BACKEND": "mlx"}):
            with patch("platform.system", return_value="Darwin"):
                with patch("platform.machine", return_value="arm64"):
                    from semantic_core.infrastructure.local.whisper.device import get_device_info

                    device_type, device_name = get_device_info()
                    assert device_type == "mlx"
                    assert "FORCED" in device_name

    def test_get_device_info_forced_pytorch_on_apple_silicon(self):
        """Тест: get_device_info() с принудительным PyTorch на Apple Silicon."""
        with patch.dict("os.environ", {"WHISPER_BACKEND": "pytorch"}):
            with patch("platform.system", return_value="Darwin"):
                with patch("platform.machine", return_value="arm64"):
                    from semantic_core.infrastructure.local.whisper.device import get_device_info

                    with patch("torch.cuda.is_available", return_value=False):
                        with patch("torch.backends.mps.is_available", return_value=True):
                            device_type, device_name = get_device_info()
                            assert device_type == "mps"
                            assert "FORCED" in device_name

    def test_get_device_info_auto_mlx(self):
        """Тест: get_device_info() auto-detection MLX."""
        with patch("platform.system", return_value="Darwin"):
            with patch("platform.machine", return_value="arm64"):
                from semantic_core.infrastructure.local.whisper.device import get_device_info

                # Mock lightning_whisper_mlx успешно импортируется
                with patch.dict("sys.modules", {"lightning_whisper_mlx": MagicMock()}):
                    device_type, device_name = get_device_info()
                    assert device_type == "mlx"
                    assert "MLX" in device_name

    @pytest.mark.skipif(HAS_LIGHTNING_MLX, reason="Test requires MLX NOT installed for fallback behavior")
    def test_get_device_info_auto_mps_fallback(self):
        """Тест: get_device_info() fallback на MPS если MLX не установлен."""
        with patch("platform.system", return_value="Darwin"):
            with patch("platform.machine", return_value="arm64"):
                from semantic_core.infrastructure.local.whisper.device import get_device_info

                # MLX not installed, fallback to MPS
                with patch("torch.backends.mps.is_available", return_value=True):
                    device_type, device_name = get_device_info()
                    assert device_type == "mps"
                    assert "speedup" in device_name.lower()

    def test_get_device_info_cuda(self):
        """Тест: get_device_info() на Linux с CUDA."""
        with patch("platform.system", return_value="Linux"):
            from semantic_core.infrastructure.local.whisper.device import get_device_info

            with patch("torch.cuda.is_available", return_value=True):
                with patch("torch.cuda.get_device_name", return_value="NVIDIA RTX 4090"):
                    device_type, device_name = get_device_info()
                    assert device_type == "cuda"
                    assert "4090" in device_name


# ============================================================================
# Tests: models.py
# ============================================================================


@pytest.mark.mlx
@pytest.mark.skipif(not HAS_LIGHTNING_MLX, reason="lightning-whisper-mlx not installed")
class TestWhisperModelMLX:
    """Тесты для WhisperModelMLX."""

    def test_init_valid_model(self):
        """Тест: инициализация с валидной моделью."""
        with patch("platform.system", return_value="Darwin"):
            with patch("platform.machine", return_value="arm64"):
                from semantic_core.infrastructure.local.whisper.models import WhisperModelMLX

                model = WhisperModelMLX(model_size="large-v3", batch_size=12)
                assert model.model_size == "large-v3"
                assert model.batch_size == 12
                assert model.whisper is None  # Lazy load

    def test_init_raises_on_non_apple_silicon(self):
        """Тест: RuntimeError на не-Apple Silicon."""
        with patch("platform.system", return_value="Linux"):
            from semantic_core.infrastructure.local.whisper.models import WhisperModelMLX

            with pytest.raises(RuntimeError, match="requires Apple Silicon"):
                WhisperModelMLX(model_size="large-v3")

    def test_init_invalid_model_raises(self):
        """Тест: ValueError при невалидной модели."""
        with patch("platform.system", return_value="Darwin"):
            with patch("platform.machine", return_value="arm64"):
                from semantic_core.infrastructure.local.whisper.models import WhisperModelMLX

                with pytest.raises(ValueError, match="not available"):
                    WhisperModelMLX(model_size="invalid-model")

    def test_load_model_lightning(self):
        """Тест: загрузка Lightning Whisper MLX модели."""
        with patch("platform.system", return_value="Darwin"):
            with patch("platform.machine", return_value="arm64"):
                from semantic_core.infrastructure.local.whisper.models import WhisperModelMLX

                mock_lightning = MagicMock()
                with patch.dict("sys.modules", {"lightning_whisper_mlx": mock_lightning}):
                    model = WhisperModelMLX(model_size="large-v3")
                    model.load_model()

                    assert model.whisper is not None
                    assert model.is_loaded() is True

    def test_transcribe_returns_segments(self):
        """Тест: transcribe() возвращает segments с таймкодами."""
        with patch("platform.system", return_value="Darwin"):
            with patch("platform.machine", return_value="arm64"):
                from semantic_core.infrastructure.local.whisper.models import WhisperModelMLX

                mock_whisper = MagicMock()
                mock_whisper.transcribe.return_value = {
                    "text": "Hello world",
                    "segments": [
                        {"start": 0.0, "end": 2.5, "text": "Hello"},
                        {"start": 2.5, "end": 5.0, "text": "world"},
                    ],
                    "language": "en",
                }

                model = WhisperModelMLX(model_size="large-v3")
                model.whisper = mock_whisper

                result = model.transcribe("test.mp3", language="en")

                assert result["text"] == "Hello world"
                assert len(result["segments"]) == 2
                assert result["segments"][0]["start"] == 0.0
                assert result["language"] == "en"


class TestWhisperModel:
    """Тесты для WhisperModel (PyTorch)."""

    def test_init(self):
        """Тест: инициализация PyTorch модели."""
        from semantic_core.infrastructure.local.whisper.models import WhisperModel

        with patch("torch.cuda.is_available", return_value=False):
            with patch("torch.backends.mps.is_available", return_value=False):
                model = WhisperModel(model_size="medium")
                assert "whisper-medium" in model.model_id
                assert model.device.type == "cpu"

    def test_load_model_enables_timestamps(self):
        """Тест: load_model() включает таймкоды (ключевое отличие от донора)."""
        from semantic_core.infrastructure.local.whisper.models import WhisperModel

        mock_model = MagicMock()
        mock_processor = MagicMock()
        mock_pipeline = MagicMock()

        with patch("torch.cuda.is_available", return_value=False):
            with patch("torch.backends.mps.is_available", return_value=False):
                with patch(
                    "transformers.AutoModelForSpeechSeq2Seq.from_pretrained",
                    return_value=mock_model,
                ):
                    with patch(
                        "transformers.AutoProcessor.from_pretrained",
                        return_value=mock_processor,
                    ):
                        with patch("transformers.pipeline", return_value=mock_pipeline):
                            model = WhisperModel(model_size="medium")
                            model.load_model()

                            # ✅ Проверяем, что таймкоды включены
                            assert (
                                mock_processor.feature_extractor.return_token_timestamps
                                is True
                            )
                            assert model.is_loaded() is True

    def test_transcribe_returns_chunks(self):
        """Тест: transcribe() возвращает chunks с таймкодами."""
        librosa = pytest.importorskip("librosa")
        
        from semantic_core.infrastructure.local.whisper.models import WhisperModel

        mock_pipe = MagicMock()
        mock_pipe.return_value = {
            "text": "Hello world",
            "chunks": [
                {"timestamp": (0.0, 2.5), "text": "Hello"},
                {"timestamp": (2.5, 5.0), "text": "world"},
            ],
        }

        with patch("torch.cuda.is_available", return_value=False):
            with patch("torch.backends.mps.is_available", return_value=False):
                with patch("librosa.load", return_value=(MagicMock(), 16000)):
                    with patch("soundfile.write"):
                        model = WhisperModel(model_size="medium")
                        model.pipe = mock_pipe

                        result = model.transcribe("test.mp3")

                        assert result["text"] == "Hello world"
                        assert len(result["chunks"]) == 2


# ============================================================================
# Tests: transcriber.py
# ============================================================================


class TestWhisperTranscriber:
    """Тесты для WhisperTranscriber (ITranscriber реализация)."""

    @patch(
        "semantic_core.infrastructure.local.whisper.transcriber.get_device_info",
        return_value=("mlx", "MLX"),
    )
    def test_init_auto_detection(self, mock_device):
        """Тест: auto-detection устройства при инициализации."""
        from semantic_core.infrastructure.local.whisper.transcriber import (
            WhisperTranscriber,
        )

        transcriber = WhisperTranscriber(model_size="large-v3-turbo")
        assert transcriber._device_type == "mlx"
        assert transcriber._model_size == "large-v3-turbo"

    def test_supported_formats(self):
        """Тест: supported_formats property."""
        from semantic_core.infrastructure.local.whisper.transcriber import (
            WhisperTranscriber,
        )

        with patch(
            "semantic_core.infrastructure.local.whisper.transcriber.get_device_info",
            return_value=("cpu", "CPU"),
        ):
            transcriber = WhisperTranscriber()
            formats = transcriber.supported_formats

            assert "mp3" in formats
            assert "wav" in formats
            assert "flac" in formats

    def test_transcribe_file_not_found(self):
        """Тест: FileNotFoundError если файл не существует."""
        from semantic_core.infrastructure.local.whisper.transcriber import (
            WhisperTranscriber,
        )

        with patch(
            "semantic_core.infrastructure.local.whisper.transcriber.get_device_info",
            return_value=("cpu", "CPU"),
        ):
            transcriber = WhisperTranscriber()

            with pytest.raises(FileNotFoundError, match="not found"):
                transcriber.transcribe(Path("/nonexistent/file.mp3"))

    def test_transcribe_unsupported_format(self):
        """Тест: ValueError при неподдерживаемом формате."""
        from semantic_core.infrastructure.local.whisper.transcriber import (
            WhisperTranscriber,
        )

        with patch(
            "semantic_core.infrastructure.local.whisper.transcriber.get_device_info",
            return_value=("cpu", "CPU"),
        ):
            transcriber = WhisperTranscriber()

            # Mock файл существует, но неподдерживаемый формат
            mock_path = MagicMock(spec=Path)
            mock_path.exists.return_value = True
            mock_path.suffix = ".avi"

            with pytest.raises(ValueError, match="Unsupported audio format"):
                transcriber.transcribe(mock_path)

    def test_convert_to_dto_mlx_format(self):
        """Тест: _convert_to_dto() с MLX форматом (segments)."""
        from semantic_core.infrastructure.local.whisper.transcriber import (
            WhisperTranscriber,
        )

        with patch(
            "semantic_core.infrastructure.local.whisper.transcriber.get_device_info",
            return_value=("mlx", "MLX"),
        ):
            transcriber = WhisperTranscriber()

            raw_result = {
                "text": "Hello world",
                "segments": [
                    {"start": 0.0, "end": 2.5, "text": "Hello"},
                    {"start": 2.5, "end": 5.0, "text": "world"},
                ],
                "language": "en",
            }

            result = transcriber._convert_to_dto(raw_result)

            assert isinstance(result, TranscriptionResult)
            assert result.full_text == "Hello world"
            assert len(result.segments) == 2
            assert result.segments[0].start_seconds == 0.0
            assert result.segments[0].end_seconds == 2.5
            assert result.segments[0].text == "Hello"
            assert result.language == "en"
            assert result.has_timestamps is True

    def test_convert_to_dto_pytorch_format(self):
        """Тест: _convert_to_dto() с PyTorch форматом (chunks)."""
        from semantic_core.infrastructure.local.whisper.transcriber import (
            WhisperTranscriber,
        )

        with patch(
            "semantic_core.infrastructure.local.whisper.transcriber.get_device_info",
            return_value=("cpu", "CPU"),
        ):
            transcriber = WhisperTranscriber()

            raw_result = {
                "text": "Test transcription",
                "chunks": [
                    {"timestamp": (0.0, 3.0), "text": "Test"},
                    {"timestamp": (3.0, 6.0), "text": "transcription"},
                ],
            }

            result = transcriber._convert_to_dto(raw_result)

            assert isinstance(result, TranscriptionResult)
            assert result.full_text == "Test transcription"
            assert len(result.segments) == 2
            assert result.segments[1].start_seconds == 3.0
            assert result.segments[1].end_seconds == 6.0

    def test_transcribe_integration(self):
        """Тест: полная интеграция transcribe() с mock моделью."""
        from semantic_core.infrastructure.local.whisper.transcriber import (
            WhisperTranscriber,
        )

        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            "text": "Integration test",
            "segments": [{"start": 0.0, "end": 5.0, "text": "Integration test"}],
            "language": "en",
        }
        mock_model.load_model = MagicMock()

        with patch(
            "semantic_core.infrastructure.local.whisper.transcriber.get_device_info",
            return_value=("cpu", "CPU"),
        ):
            with patch(
                "semantic_core.infrastructure.local.whisper.transcriber.WhisperModel",
                return_value=mock_model,
            ):
                transcriber = WhisperTranscriber()

                # Mock файл существует
                mock_path = MagicMock(spec=Path)
                mock_path.exists.return_value = True
                mock_path.suffix = ".mp3"

                result = transcriber.transcribe(mock_path, language="en")

                assert result.full_text == "Integration test"
                assert len(result.segments) == 1
                mock_model.load_model.assert_called_once()
                mock_model.transcribe.assert_called_once()


# ============================================================================
# Tests: __init__.py (graceful degradation)
# ============================================================================


class TestGracefulDegradation:
    """Тесты для graceful degradation при отсутствии зависимостей."""

    def test_get_whisper_transcriber_raises_without_deps(self):
        """Тест: get_whisper_transcriber() вызывает ImportError без зависимостей."""
        # Mock WhisperTranscriber как None (имитация отсутствия зависимостей)
        with patch(
            "semantic_core.infrastructure.local.whisper.WhisperTranscriber", None
        ):
            with patch(
                "semantic_core.infrastructure.local.whisper._import_error",
                "No module named 'lightning_whisper_mlx'",
            ):
                from semantic_core.infrastructure.local.whisper import (
                    get_whisper_transcriber,
                )

                with pytest.raises(
                    ImportError, match="Whisper dependencies not installed"
                ):
                    get_whisper_transcriber()

    def test_get_whisper_transcriber_success(self):
        """Тест: get_whisper_transcriber() успешно создаёт экземпляр."""
        from semantic_core.infrastructure.local.whisper import (
            WhisperTranscriber,
            get_whisper_transcriber,
        )

        # Если импорт успешен, должны получить инстанс
        if WhisperTranscriber is not None:
            with patch(
                "semantic_core.infrastructure.local.whisper.transcriber.get_device_info",
                return_value=("cpu", "CPU"),
            ):
                transcriber = get_whisper_transcriber(model_size="medium")
                assert transcriber._model_size == "medium"
