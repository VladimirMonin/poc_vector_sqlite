"""Unit-тесты для video_utils.

Тестируем утилиты обработки видео без реальных файлов.
Проверяем:
- Режимы извлечения кадров (fps, total, interval)
- Quality presets
- Ресайз кадров
- Валидацию параметров
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image

from semantic_core.infrastructure.media.utils.video import (
    extract_frames,
    frames_to_bytes,
    get_video_duration,
    get_video_metadata,
    is_video_supported,
    SUPPORTED_VIDEO_TYPES,
    QUALITY_PRESETS,
    DEFAULT_MAX_DIMENSION,
    _resize_frame,
)


# ============================================================================
# Тесты is_video_supported
# ============================================================================


class TestIsVideoSupported:
    """Тесты проверки MIME-типов видео."""

    @pytest.mark.parametrize(
        "mime_type",
        [
            "video/mp4",
            "video/webm",
            "video/quicktime",
            "video/x-msvideo",
            "video/x-matroska",
            "video/mpeg",
        ],
    )
    def test_supported_video_types(self, mime_type):
        """Все стандартные видео-форматы поддерживаются."""
        assert is_video_supported(mime_type) is True

    @pytest.mark.parametrize(
        "mime_type",
        [
            "audio/mp3",
            "image/jpeg",
            "text/plain",
            "application/json",
            "video/unknown",
        ],
    )
    def test_unsupported_types(self, mime_type):
        """Неподдерживаемые типы возвращают False."""
        assert is_video_supported(mime_type) is False

    def test_supported_types_constant_not_empty(self):
        """SUPPORTED_VIDEO_TYPES не пустой."""
        assert len(SUPPORTED_VIDEO_TYPES) >= 4


# ============================================================================
# Тесты quality presets
# ============================================================================


class TestQualityPresets:
    """Тесты пресетов качества."""

    def test_fhd_preset_is_1024(self):
        """FHD пресет = 1024px (не 1920 — экономия токенов)."""
        assert QUALITY_PRESETS["fhd"] == 1024

    def test_hd_preset_is_768(self):
        """HD пресет = 768px."""
        assert QUALITY_PRESETS["hd"] == 768

    def test_balanced_preset_is_512(self):
        """Balanced пресет = 512px."""
        assert QUALITY_PRESETS["balanced"] == 512

    def test_default_max_dimension_is_1024(self):
        """Дефолт = 1024px (совпадает с fhd)."""
        assert DEFAULT_MAX_DIMENSION == 1024

    def test_all_presets_below_2000(self):
        """Все пресеты ниже 2000px (оптимизация для Gemini)."""
        for name, value in QUALITY_PRESETS.items():
            assert value < 2000, f"Preset {name} is too large: {value}"


# ============================================================================
# Тесты _resize_frame
# ============================================================================


class TestResizeFrame:
    """Тесты ресайза кадров."""

    def test_small_image_not_resized(self):
        """Маленькие картинки не ресайзятся."""
        img = Image.new("RGB", (500, 300))
        result = _resize_frame(img, max_dim=1024)
        assert result.size == (500, 300)

    def test_large_image_resized(self):
        """Большие картинки ресайзятся до max_dim."""
        img = Image.new("RGB", (2000, 1500))
        result = _resize_frame(img, max_dim=1024)

        # Проверяем что максимальная сторона = 1024
        assert max(result.size) == 1024
        # Проверяем соотношение сторон (примерно)
        original_ratio = 2000 / 1500
        new_ratio = result.size[0] / result.size[1]
        assert abs(original_ratio - new_ratio) < 0.01

    def test_exact_max_dim_not_resized(self):
        """Картинка с точным размером max_dim не ресайзится."""
        img = Image.new("RGB", (1024, 768))
        result = _resize_frame(img, max_dim=1024)
        assert result.size == (1024, 768)

    def test_tall_image_resized_by_height(self):
        """Высокие картинки ресайзятся по высоте."""
        img = Image.new("RGB", (1000, 3000))
        result = _resize_frame(img, max_dim=1024)

        assert result.size[1] == 1024  # Высота = max_dim
        assert result.size[0] < result.size[1]  # Остаётся высокой


# ============================================================================
# Тесты extract_frames (с моками)
# ============================================================================


class TestExtractFrames:
    """Тесты извлечения кадров."""

    def test_file_not_found_raises(self, tmp_path):
        """Если видео-файл не существует — FileNotFoundError."""
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            fake_path = tmp_path / "nonexistent.mp4"
            with pytest.raises(FileNotFoundError) as exc_info:
                extract_frames(fake_path)

            assert "not found" in str(exc_info.value).lower()

    def test_ffmpeg_missing_raises(self, tmp_path):
        """Если ffmpeg нет — DependencyError."""
        from semantic_core.infrastructure.media.utils.audio import DependencyError

        video_file = tmp_path / "test.mp4"
        video_file.touch()

        with patch("shutil.which", return_value=None):
            with pytest.raises(DependencyError):
                extract_frames(video_file)

    def test_unknown_mode_raises(self, tmp_path):
        """Неизвестный режим — ValueError."""
        video_file = tmp_path / "test.mp4"

        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch.object(Path, "exists", return_value=True):
                with patch(
                    "imageio.v3.immeta",
                    return_value={"duration": 10, "fps": 30},
                ):
                    with pytest.raises(ValueError) as exc_info:
                        extract_frames(video_file, mode="unknown")

                    assert "unknown" in str(exc_info.value).lower()

    def test_mode_total_calculates_correct_indices(self, tmp_path):
        """Mode='total' вычисляет правильные индексы кадров."""
        video_file = tmp_path / "test.mp4"

        # Видео 10 сек, 30 fps = 300 кадров
        # Если frame_count=5, индексы: 0, 60, 120, 180, 240
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch.object(Path, "exists", return_value=True):
                with patch(
                    "imageio.v3.immeta",
                    return_value={"duration": 10, "fps": 30},
                ):
                    # Мокаем imread чтобы считать вызовы
                    mock_frame = Image.new("RGB", (640, 480))
                    frame_indices = []

                    def capture_index(path, index=0, plugin=None):
                        frame_indices.append(index)
                        import numpy as np

                        return np.array(mock_frame)

                    with patch("imageio.v3.imread", side_effect=capture_index):
                        frames = extract_frames(video_file, mode="total", frame_count=5)

                        # Проверяем равномерное распределение
                        assert len(frame_indices) == 5
                        # Индексы должны быть 0, 60, 120, 180, 240
                        expected = [0, 60, 120, 180, 240]
                        assert frame_indices == expected

    def test_mode_fps_calculates_correct_step(self, tmp_path):
        """Mode='fps' вычисляет правильный шаг."""
        video_file = tmp_path / "test.mp4"

        # Видео 30 fps, хотим 1 кадр/сек = шаг 30
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch.object(Path, "exists", return_value=True):
                with patch(
                    "imageio.v3.immeta",
                    return_value={"duration": 10, "fps": 30},
                ):
                    mock_frame = Image.new("RGB", (640, 480))
                    frame_indices = []

                    def capture_index(path, index=0, plugin=None):
                        frame_indices.append(index)
                        import numpy as np

                        return np.array(mock_frame)

                    with patch("imageio.v3.imread", side_effect=capture_index):
                        frames = extract_frames(video_file, mode="fps", fps=1.0)

                        # При 30fps видео и 1fps извлечения, шаг = 30
                        # За 10 сек должно быть 10 кадров: 0, 30, 60, ..., 270
                        assert len(frame_indices) == 10
                        # Шаг между индексами = 30
                        for i in range(1, len(frame_indices)):
                            assert frame_indices[i] - frame_indices[i - 1] == 30

    def test_mode_interval_calculates_correct_step(self, tmp_path):
        """Mode='interval' вычисляет правильный шаг."""
        video_file = tmp_path / "test.mp4"

        # Видео 30 fps, интервал 5 сек = шаг 150 кадров
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch.object(Path, "exists", return_value=True):
                with patch(
                    "imageio.v3.immeta",
                    return_value={"duration": 15, "fps": 30},
                ):
                    mock_frame = Image.new("RGB", (640, 480))
                    frame_indices = []

                    def capture_index(path, index=0, plugin=None):
                        frame_indices.append(index)
                        import numpy as np

                        return np.array(mock_frame)

                    with patch("imageio.v3.imread", side_effect=capture_index):
                        frames = extract_frames(
                            video_file, mode="interval", interval_seconds=5.0
                        )

                        # За 15 сек с интервалом 5 сек: 0, 150, 300
                        assert len(frame_indices) == 3
                        expected = [0, 150, 300]
                        assert frame_indices == expected

    def test_max_frames_limit(self, tmp_path):
        """max_frames ограничивает количество кадров."""
        video_file = tmp_path / "test.mp4"

        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch.object(Path, "exists", return_value=True):
                with patch(
                    "imageio.v3.immeta",
                    return_value={"duration": 60, "fps": 30},
                ):
                    mock_frame = Image.new("RGB", (640, 480))
                    frame_count = [0]

                    def count_frames(path, index=0, plugin=None):
                        frame_count[0] += 1
                        import numpy as np

                        return np.array(mock_frame)

                    with patch("imageio.v3.imread", side_effect=count_frames):
                        frames = extract_frames(
                            video_file, mode="total", frame_count=100, max_frames=10
                        )

                        # Должно быть не более 10 кадров
                        assert frame_count[0] <= 10

    def test_frames_are_resized(self, tmp_path):
        """Кадры ресайзятся согласно quality preset."""
        video_file = tmp_path / "test.mp4"

        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch.object(Path, "exists", return_value=True):
                with patch(
                    "imageio.v3.immeta",
                    return_value={"duration": 5, "fps": 30},
                ):
                    # Большой кадр 2000x1500
                    import numpy as np

                    big_frame = np.zeros((1500, 2000, 3), dtype=np.uint8)

                    with patch("imageio.v3.imread", return_value=big_frame):
                        frames = extract_frames(
                            video_file, mode="total", frame_count=1, quality="hd"
                        )

                        # hd = 768px max
                        assert len(frames) == 1
                        assert max(frames[0].size) == 768


# ============================================================================
# Тесты frames_to_bytes
# ============================================================================


class TestFramesToBytes:
    """Тесты конвертации кадров в bytes."""

    def test_returns_list_of_tuples(self):
        """Возвращает список tuple (bytes, mime_type)."""
        frames = [Image.new("RGB", (100, 100)), Image.new("RGB", (100, 100))]

        result = frames_to_bytes(frames)

        assert isinstance(result, list)
        assert len(result) == 2
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert isinstance(item[0], bytes)
            assert isinstance(item[1], str)

    def test_jpeg_format(self):
        """JPEG формат возвращает правильный MIME-тип."""
        frames = [Image.new("RGB", (100, 100))]

        result = frames_to_bytes(frames, format="JPEG")

        _, mime_type = result[0]
        assert mime_type == "image/jpeg"

    def test_png_format(self):
        """PNG формат возвращает правильный MIME-тип."""
        frames = [Image.new("RGB", (100, 100))]

        result = frames_to_bytes(frames, format="PNG")

        _, mime_type = result[0]
        assert mime_type == "image/png"

    def test_webp_format(self):
        """WEBP формат возвращает правильный MIME-тип."""
        frames = [Image.new("RGB", (100, 100))]

        result = frames_to_bytes(frames, format="WEBP")

        _, mime_type = result[0]
        assert mime_type == "image/webp"

    def test_empty_frames_list(self):
        """Пустой список кадров → пустой результат."""
        result = frames_to_bytes([])
        assert result == []


# ============================================================================
# Тесты get_video_duration (с моками)
# ============================================================================


class TestGetVideoDuration:
    """Тесты получения длительности видео."""

    def test_returns_duration_in_seconds(self, tmp_path):
        """Возвращает длительность в секундах."""
        video_file = tmp_path / "test.mp4"
        video_file.touch()

        with patch("imageio.v3.immeta", return_value={"duration": 123.45}):
            duration = get_video_duration(video_file)
            assert duration == 123.45

    def test_missing_duration_returns_zero(self, tmp_path):
        """Если duration отсутствует — возвращает 0."""
        video_file = tmp_path / "test.mp4"
        video_file.touch()

        with patch("imageio.v3.immeta", return_value={}):
            duration = get_video_duration(video_file)
            assert duration == 0


# ============================================================================
# Тесты get_video_metadata (с моками)
# ============================================================================


class TestGetVideoMetadata:
    """Тесты получения метаданных видео."""

    def test_returns_all_fields(self, tmp_path):
        """Возвращает все поля метаданных."""
        video_file = tmp_path / "test.mp4"
        video_file.touch()

        mock_meta = {
            "duration": 60.0,
            "fps": 29.97,
            "size": (1920, 1080),
            "codec": "h264",
        }

        with patch("imageio.v3.immeta", return_value=mock_meta):
            meta = get_video_metadata(video_file)

            assert meta["duration"] == 60.0
            assert meta["fps"] == 29.97
            assert meta["size"] == (1920, 1080)
            assert meta["codec"] == "h264"

    def test_missing_fields_have_defaults(self, tmp_path):
        """Отсутствующие поля имеют дефолтные значения."""
        video_file = tmp_path / "test.mp4"
        video_file.touch()

        with patch("imageio.v3.immeta", return_value={}):
            meta = get_video_metadata(video_file)

            assert meta["duration"] == 0
            assert meta["fps"] == 0
            assert meta["size"] == (0, 0)
            assert meta["codec"] == "unknown"
