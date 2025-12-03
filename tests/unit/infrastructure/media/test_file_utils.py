"""Тесты infrastructure/media/utils/files.py - работа с файлами и MIME."""

import pytest
from pathlib import Path

from semantic_core.infrastructure.media.utils.files import (
    get_file_mime_type,
    is_image_valid,
    get_media_type,
    SUPPORTED_IMAGE_MIME_TYPES,
)


class TestGetFileMimeType:
    """Тесты для get_file_mime_type."""

    def test_jpeg_extension(self, tmp_path):
        """JPEG по расширению."""
        path = tmp_path / "photo.jpg"
        path.touch()
        assert get_file_mime_type(str(path)) == "image/jpeg"

    def test_jpeg_alt_extension(self, tmp_path):
        """JPEG с расширением .jpeg."""
        path = tmp_path / "photo.jpeg"
        path.touch()
        assert get_file_mime_type(str(path)) == "image/jpeg"

    def test_png_extension(self, tmp_path):
        """PNG по расширению."""
        path = tmp_path / "image.png"
        path.touch()
        assert get_file_mime_type(str(path)) == "image/png"

    def test_gif_extension(self, tmp_path):
        """GIF по расширению."""
        path = tmp_path / "animation.gif"
        path.touch()
        assert get_file_mime_type(str(path)) == "image/gif"

    def test_webp_extension(self, tmp_path):
        """WebP по расширению."""
        path = tmp_path / "modern.webp"
        path.touch()
        assert get_file_mime_type(str(path)) == "image/webp"

    def test_mp4_extension(self, tmp_path):
        """MP4 видео."""
        path = tmp_path / "video.mp4"
        path.touch()
        assert get_file_mime_type(str(path)) == "video/mp4"

    def test_mp3_extension(self, tmp_path):
        """MP3 аудио."""
        path = tmp_path / "music.mp3"
        path.touch()
        assert get_file_mime_type(str(path)) == "audio/mpeg"

    def test_unknown_extension(self, tmp_path):
        """Неизвестное расширение - fallback."""
        # Используем расширение, которое точно не зарегистрировано
        path = tmp_path / "data.qzxvbnm"
        path.touch()
        assert get_file_mime_type(str(path)) == "application/octet-stream"

    def test_case_insensitive(self, tmp_path):
        """Расширение регистронезависимо."""
        path = tmp_path / "PHOTO.JPG"
        path.touch()
        assert get_file_mime_type(str(path)) == "image/jpeg"


class TestIsImageValid:
    """Тесты для is_image_valid."""

    def test_valid_jpeg(self, tmp_path):
        """Валидный JPEG файл."""
        path = tmp_path / "valid.jpg"
        path.touch()
        assert is_image_valid(str(path)) is True

    def test_valid_png(self, tmp_path):
        """Валидный PNG файл."""
        path = tmp_path / "valid.png"
        path.touch()
        assert is_image_valid(str(path)) is True

    def test_valid_webp(self, tmp_path):
        """Валидный WebP файл."""
        path = tmp_path / "valid.webp"
        path.touch()
        assert is_image_valid(str(path)) is True

    def test_invalid_mp4(self, tmp_path):
        """MP4 - не изображение."""
        path = tmp_path / "video.mp4"
        path.touch()
        assert is_image_valid(str(path)) is False

    def test_invalid_txt(self, tmp_path):
        """TXT - не изображение."""
        path = tmp_path / "readme.txt"
        path.touch()
        assert is_image_valid(str(path)) is False

    def test_nonexistent_file(self):
        """Несуществующий файл - False."""
        assert is_image_valid("/nonexistent/path/image.jpg") is False

    def test_directory_not_file(self, tmp_path):
        """Директория - не файл."""
        directory = tmp_path / "images"
        directory.mkdir()
        assert is_image_valid(str(directory)) is False


class TestGetMediaType:
    """Тесты для get_media_type."""

    def test_image_jpeg(self, tmp_path):
        """JPEG = image."""
        path = tmp_path / "photo.jpg"
        path.touch()
        assert get_media_type(str(path)) == "image"

    def test_image_png(self, tmp_path):
        """PNG = image."""
        path = tmp_path / "image.png"
        path.touch()
        assert get_media_type(str(path)) == "image"

    def test_audio_mp3(self, tmp_path):
        """MP3 = audio."""
        path = tmp_path / "song.mp3"
        path.touch()
        assert get_media_type(str(path)) == "audio"

    def test_audio_wav(self, tmp_path):
        """WAV = audio."""
        path = tmp_path / "sound.wav"
        path.touch()
        assert get_media_type(str(path)) == "audio"

    def test_video_mp4(self, tmp_path):
        """MP4 = video."""
        path = tmp_path / "clip.mp4"
        path.touch()
        assert get_media_type(str(path)) == "video"

    def test_video_mov(self, tmp_path):
        """MOV = video."""
        path = tmp_path / "clip.mov"
        path.touch()
        assert get_media_type(str(path)) == "video"

    def test_unknown_type(self, tmp_path):
        """Неизвестный тип = unknown."""
        path = tmp_path / "data.bin"
        path.touch()
        assert get_media_type(str(path)) == "unknown"


class TestSupportedMimeTypes:
    """Тесты константы SUPPORTED_IMAGE_MIME_TYPES."""

    def test_jpeg_supported(self):
        """JPEG поддерживается."""
        assert "image/jpeg" in SUPPORTED_IMAGE_MIME_TYPES

    def test_png_supported(self):
        """PNG поддерживается."""
        assert "image/png" in SUPPORTED_IMAGE_MIME_TYPES

    def test_webp_supported(self):
        """WebP поддерживается."""
        assert "image/webp" in SUPPORTED_IMAGE_MIME_TYPES

    def test_gif_supported(self):
        """GIF поддерживается."""
        assert "image/gif" in SUPPORTED_IMAGE_MIME_TYPES

    def test_heic_supported(self):
        """HEIC поддерживается."""
        assert "image/heic" in SUPPORTED_IMAGE_MIME_TYPES
