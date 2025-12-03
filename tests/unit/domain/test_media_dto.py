"""Тесты domain/media.py - DTO для мультимодального контента."""

import pytest
from pathlib import Path

from semantic_core.domain.media import (
    TaskStatus,
    MediaResource,
    MediaRequest,
    MediaAnalysisResult,
)


class TestTaskStatus:
    """Тесты для TaskStatus enum."""

    def test_values(self):
        """Проверяем значения статусов."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.PROCESSING.value == "processing"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"

    def test_string_comparison(self):
        """Статус сравнивается со строкой."""
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.COMPLETED == "completed"


class TestMediaResource:
    """Тесты для MediaResource dataclass."""

    def test_create_with_path(self, tmp_path):
        """Создание с Path объектом."""
        path = tmp_path / "test.jpg"
        path.touch()

        resource = MediaResource(
            path=path,
            media_type="image",
            mime_type="image/jpeg",
        )

        assert resource.path == path
        assert resource.media_type == "image"
        assert resource.mime_type == "image/jpeg"
        assert resource.metadata == {}

    def test_create_with_string_path(self, tmp_path):
        """Строка автоматически конвертируется в Path."""
        path_str = str(tmp_path / "test.png")

        resource = MediaResource(
            path=path_str,
            media_type="image",
            mime_type="image/png",
        )

        assert isinstance(resource.path, Path)
        assert str(resource.path) == path_str

    def test_metadata(self, tmp_path):
        """Метаданные хранятся корректно."""
        resource = MediaResource(
            path=tmp_path / "test.jpg",
            media_type="image",
            mime_type="image/jpeg",
            metadata={"width": 800, "height": 600},
        )

        assert resource.metadata["width"] == 800
        assert resource.metadata["height"] == 600


class TestMediaRequest:
    """Тесты для MediaRequest dataclass."""

    def test_minimal_request(self, tmp_path):
        """Минимальный запрос только с ресурсом."""
        resource = MediaResource(
            path=tmp_path / "test.jpg",
            media_type="image",
            mime_type="image/jpeg",
        )

        request = MediaRequest(resource=resource)

        assert request.resource == resource
        assert request.user_prompt is None
        assert request.context_text is None

    def test_full_request(self, tmp_path):
        """Полный запрос с промптом и контекстом."""
        resource = MediaResource(
            path=tmp_path / "photo.jpg",
            media_type="image",
            mime_type="image/jpeg",
        )

        request = MediaRequest(
            resource=resource,
            user_prompt="Describe this photo",
            context_text="Section: Paris Travel",
        )

        assert request.user_prompt == "Describe this photo"
        assert request.context_text == "Section: Paris Travel"


class TestMediaAnalysisResult:
    """Тесты для MediaAnalysisResult dataclass."""

    def test_minimal_result(self):
        """Минимальный результат только с описанием."""
        result = MediaAnalysisResult(description="A cat sitting on a chair")

        assert result.description == "A cat sitting on a chair"
        assert result.alt_text is None
        assert result.keywords == []
        assert result.ocr_text is None
        assert result.tokens_used is None

    def test_full_result(self):
        """Полный результат со всеми полями."""
        result = MediaAnalysisResult(
            description="A fluffy orange cat lounging on a vintage chair",
            alt_text="Orange cat on chair",
            keywords=["cat", "orange", "fluffy", "chair", "pet"],
            ocr_text="ADOPT ME",
            tokens_used=258,
        )

        assert "fluffy" in result.description
        assert result.alt_text == "Orange cat on chair"
        assert len(result.keywords) == 5
        assert "cat" in result.keywords
        assert result.ocr_text == "ADOPT ME"
        assert result.tokens_used == 258

    def test_keywords_are_list(self):
        """Keywords всегда список, даже если не указан."""
        result = MediaAnalysisResult(description="Test")

        assert isinstance(result.keywords, list)
        assert len(result.keywords) == 0
