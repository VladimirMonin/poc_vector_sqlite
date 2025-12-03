"""Unit-тесты для audio_utils.

Тестируем утилиты обработки аудио без реальных API вызовов.
Проверяем:
- Валидацию параметров
- Ошибки зависимостей (DependencyError)
- Корректность MIME-типов
- Логику конвертации (с моками)
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import BytesIO

from semantic_core.infrastructure.media.utils.audio import (
    DependencyError,
    ensure_ffmpeg,
    extract_audio_from_video,
    optimize_audio,
    optimize_audio_to_bytes,
    get_audio_duration,
    is_audio_supported,
    SUPPORTED_AUDIO_TYPES,
    DEFAULT_BITRATE,
    DEFAULT_CODEC,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_MONO,
)


# ============================================================================
# Тесты ensure_ffmpeg
# ============================================================================


class TestEnsureFfmpeg:
    """Тесты проверки наличия ffmpeg."""

    def test_ffmpeg_found(self):
        """Если ffmpeg есть в PATH — не кидаем исключение."""
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            # Не должно кидать исключение
            ensure_ffmpeg()

    def test_ffmpeg_missing_raises_dependency_error(self):
        """Если ffmpeg нет — кидаем DependencyError."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(DependencyError) as exc_info:
                ensure_ffmpeg()

            assert "ffmpeg" in str(exc_info.value).lower()
            assert "brew install" in str(exc_info.value) or "apt install" in str(
                exc_info.value
            )

    def test_dependency_error_has_install_instructions(self):
        """DependencyError содержит инструкции по установке."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(DependencyError) as exc_info:
                ensure_ffmpeg()

            error_msg = str(exc_info.value)
            # Должны быть инструкции для macOS и Linux
            assert "brew" in error_msg or "apt" in error_msg


# ============================================================================
# Тесты is_audio_supported
# ============================================================================


class TestIsAudioSupported:
    """Тесты проверки MIME-типов аудио."""

    @pytest.mark.parametrize(
        "mime_type",
        [
            "audio/mpeg",
            "audio/mp3",
            "audio/wav",
            "audio/ogg",
            "audio/flac",
            "audio/aac",
            "audio/x-m4a",
        ],
    )
    def test_supported_audio_types(self, mime_type):
        """Все стандартные аудио-форматы поддерживаются."""
        assert is_audio_supported(mime_type) is True

    @pytest.mark.parametrize(
        "mime_type",
        [
            "video/mp4",
            "image/jpeg",
            "text/plain",
            "application/json",
            "audio/unknown",
        ],
    )
    def test_unsupported_types(self, mime_type):
        """Неподдерживаемые типы возвращают False."""
        assert is_audio_supported(mime_type) is False

    def test_supported_types_constant_not_empty(self):
        """SUPPORTED_AUDIO_TYPES не пустой."""
        assert len(SUPPORTED_AUDIO_TYPES) >= 5


# ============================================================================
# Тесты default констант
# ============================================================================


class TestDefaults:
    """Тесты дефолтных значений."""

    def test_default_bitrate_is_32(self):
        """Агрессивный битрейт 32kbps для максимальной вместимости."""
        assert DEFAULT_BITRATE == 32

    def test_default_codec_is_libvorbis(self):
        """Кодек libvorbis для OGG."""
        assert DEFAULT_CODEC == "libvorbis"

    def test_default_sample_rate_is_16000(self):
        """Sample rate 16000 достаточен для речи."""
        assert DEFAULT_SAMPLE_RATE == 16000

    def test_default_mono_is_true(self):
        """Моно по умолчанию — Gemini не различает стерео."""
        assert DEFAULT_MONO is True


# ============================================================================
# Тесты extract_audio_from_video (с моками)
# ============================================================================


class TestExtractAudioFromVideo:
    """Тесты извлечения аудио из видео."""

    def test_file_not_found_raises(self, tmp_path):
        """Если видео-файл не существует — FileNotFoundError."""
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            fake_path = tmp_path / "nonexistent.mp4"
            with pytest.raises(FileNotFoundError) as exc_info:
                extract_audio_from_video(fake_path)

            assert "not found" in str(exc_info.value).lower()

    def test_ffmpeg_missing_raises(self, tmp_path):
        """Если ffmpeg нет — DependencyError."""
        video_file = tmp_path / "test.mp4"
        video_file.touch()  # Создаём пустой файл

        with patch("shutil.which", return_value=None):
            with pytest.raises(DependencyError):
                extract_audio_from_video(video_file)

    def test_output_path_auto_generated(self, tmp_path):
        """Если output_path не указан — генерируется автоматически."""
        video_file = tmp_path / "video.mp4"

        # Мокаем всё
        mock_audio = MagicMock()
        mock_audio.set_channels.return_value = mock_audio
        mock_audio.set_frame_rate.return_value = mock_audio

        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch(
                "pydub.AudioSegment.from_file", return_value=mock_audio
            ) as mock_from_file:
                with patch.object(Path, "exists", return_value=True):
                    result = extract_audio_from_video(video_file)

                    # output_path должен быть video.ogg (по умолчанию)
                    assert result.suffix == ".ogg"
                    assert result.stem == "video"

    def test_custom_output_path(self, tmp_path):
        """Можно указать свой output_path."""
        video_file = tmp_path / "video.mp4"
        output_file = tmp_path / "custom_audio.mp3"

        mock_audio = MagicMock()
        mock_audio.set_channels.return_value = mock_audio
        mock_audio.set_frame_rate.return_value = mock_audio

        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("pydub.AudioSegment.from_file", return_value=mock_audio):
                with patch.object(Path, "exists", return_value=True):
                    result = extract_audio_from_video(
                        video_file, output_path=output_file
                    )
                    assert result == output_file

    def test_mono_conversion_applied(self, tmp_path):
        """При mono=True вызывается set_channels(1)."""
        video_file = tmp_path / "video.mp4"

        mock_audio = MagicMock()
        mock_audio.set_channels.return_value = mock_audio
        mock_audio.set_frame_rate.return_value = mock_audio

        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("pydub.AudioSegment.from_file", return_value=mock_audio):
                with patch.object(Path, "exists", return_value=True):
                    extract_audio_from_video(video_file, mono=True)

                    mock_audio.set_channels.assert_called_once_with(1)

    def test_stereo_preserved_when_mono_false(self, tmp_path):
        """При mono=False не конвертируем в моно."""
        video_file = tmp_path / "video.mp4"

        mock_audio = MagicMock()
        mock_audio.set_channels.return_value = mock_audio
        mock_audio.set_frame_rate.return_value = mock_audio

        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("pydub.AudioSegment.from_file", return_value=mock_audio):
                with patch.object(Path, "exists", return_value=True):
                    extract_audio_from_video(video_file, mono=False)

                    mock_audio.set_channels.assert_not_called()


# ============================================================================
# Тесты optimize_audio (с моками)
# ============================================================================


class TestOptimizeAudio:
    """Тесты оптимизации аудио."""

    def test_file_not_found_raises(self, tmp_path):
        """Если аудио-файл не существует — FileNotFoundError."""
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            fake_path = tmp_path / "nonexistent.mp3"
            with pytest.raises(FileNotFoundError) as exc_info:
                optimize_audio(fake_path)

            assert "not found" in str(exc_info.value).lower()

    def test_output_path_auto_generated_with_suffix(self, tmp_path):
        """Автогенерация output_path с суффиксом _optimized."""
        audio_file = tmp_path / "speech.mp3"

        mock_audio = MagicMock()
        mock_audio.set_channels.return_value = mock_audio
        mock_audio.set_frame_rate.return_value = mock_audio

        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("pydub.AudioSegment.from_file", return_value=mock_audio):
                with patch.object(Path, "exists", return_value=True):
                    result = optimize_audio(audio_file)

                    assert "optimized" in result.stem
                    assert result.suffix == ".ogg"

    def test_export_called_with_correct_params(self, tmp_path):
        """Export вызывается с правильными параметрами."""
        audio_file = tmp_path / "speech.mp3"

        mock_audio = MagicMock()
        mock_audio.set_channels.return_value = mock_audio
        mock_audio.set_frame_rate.return_value = mock_audio

        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("pydub.AudioSegment.from_file", return_value=mock_audio):
                with patch.object(Path, "exists", return_value=True):
                    optimize_audio(
                        audio_file,
                        format="ogg",
                        codec="libvorbis",
                        bitrate=32,
                    )

                    # Проверяем вызов export
                    mock_audio.export.assert_called_once()
                    call_kwargs = mock_audio.export.call_args[1]
                    assert call_kwargs["format"] == "ogg"
                    assert call_kwargs["codec"] == "libvorbis"
                    assert call_kwargs["bitrate"] == "32k"


# ============================================================================
# Тесты optimize_audio_to_bytes (с моками)
# ============================================================================


class TestOptimizeAudioToBytes:
    """Тесты оптимизации аудио в bytes."""

    def test_returns_bytes_and_mime_type(self, tmp_path):
        """Возвращает tuple (bytes, mime_type)."""
        audio_file = tmp_path / "speech.mp3"
        audio_file.touch()

        mock_audio = MagicMock()
        mock_audio.set_channels.return_value = mock_audio
        mock_audio.set_frame_rate.return_value = mock_audio
        # Мокаем export для записи в buffer
        mock_audio.export.side_effect = lambda buf, **kwargs: buf.write(b"fake_audio")

        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("pydub.AudioSegment.from_file", return_value=mock_audio):
                result = optimize_audio_to_bytes(audio_file, format="ogg")

                assert isinstance(result, tuple)
                assert len(result) == 2
                audio_bytes, mime_type = result
                assert isinstance(audio_bytes, bytes)
                assert mime_type == "audio/ogg"

    def test_different_formats(self, tmp_path):
        """Разные форматы → разные MIME-типы."""
        audio_file = tmp_path / "speech.mp3"
        audio_file.touch()

        mock_audio = MagicMock()
        mock_audio.set_channels.return_value = mock_audio
        mock_audio.set_frame_rate.return_value = mock_audio
        mock_audio.export.side_effect = lambda buf, **kwargs: buf.write(b"data")

        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("pydub.AudioSegment.from_file", return_value=mock_audio):
                _, mime_ogg = optimize_audio_to_bytes(audio_file, format="ogg")
                assert mime_ogg == "audio/ogg"

                _, mime_mp3 = optimize_audio_to_bytes(audio_file, format="mp3")
                assert mime_mp3 == "audio/mp3"


# ============================================================================
# Тесты get_audio_duration (с моками)
# ============================================================================


class TestGetAudioDuration:
    """Тесты получения длительности аудио."""

    def test_returns_seconds(self, tmp_path):
        """Возвращает длительность в секундах."""
        audio_file = tmp_path / "speech.mp3"
        audio_file.touch()

        # AudioSegment.__len__ возвращает миллисекунды
        mock_audio = MagicMock()
        mock_audio.__len__ = lambda self: 5000  # 5 секунд

        with patch("pydub.AudioSegment.from_file", return_value=mock_audio):
            duration = get_audio_duration(audio_file)
            assert duration == 5.0

    def test_handles_long_audio(self, tmp_path):
        """Корректно обрабатывает длинное аудио."""
        audio_file = tmp_path / "podcast.mp3"
        audio_file.touch()

        # 1 час = 3600000 мс
        mock_audio = MagicMock()
        mock_audio.__len__ = lambda self: 3600000

        with patch("pydub.AudioSegment.from_file", return_value=mock_audio):
            duration = get_audio_duration(audio_file)
            assert duration == 3600.0  # 1 час в секундах
