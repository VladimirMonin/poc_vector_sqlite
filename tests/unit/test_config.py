"""Unit-тесты для SemanticConfig и вложенных Media* конфигураций.

Проверяет:
- Загрузку MediaConfig из TOML
- Дефолтные значения
- Валидацию Field constraints (ge, le, pattern)
- Template injection placeholders
"""

import tempfile
from pathlib import Path
from typing import Dict, Any

import pytest
from pydantic import ValidationError

from semantic_core.config import (
    SemanticConfig,
    MediaConfig,
    MediaPromptsConfig,
    MediaChunkSizesConfig,
    MediaProcessingConfig,
    reset_config,
)


@pytest.fixture(autouse=True)
def reset_global_config():
    """Сбрасывает глобальный конфиг перед каждым тестом."""
    reset_config()
    yield
    reset_config()


class TestMediaPromptsConfig:
    """Тесты для MediaPromptsConfig."""

    def test_defaults(self):
        """Проверка дефолтных значений."""
        config = MediaPromptsConfig()
        assert config.audio_instructions is None
        assert config.image_instructions is None
        assert config.video_instructions is None

    def test_custom_instructions(self):
        """Проверка кастомных инструкций."""
        config = MediaPromptsConfig(
            audio_instructions="Focus on technical content",
            image_instructions="Detect all diagrams",
            video_instructions="Transcribe speaker names",
        )
        assert config.audio_instructions == "Focus on technical content"
        assert config.image_instructions == "Detect all diagrams"
        assert config.video_instructions == "Transcribe speaker names"

    def test_partial_instructions(self):
        """Проверка частичного заполнения."""
        config = MediaPromptsConfig(audio_instructions="Audio only")
        assert config.audio_instructions == "Audio only"
        assert config.image_instructions is None
        assert config.video_instructions is None


class TestMediaChunkSizesConfig:
    """Тесты для MediaChunkSizesConfig."""

    def test_defaults(self):
        """Проверка дефолтных значений."""
        config = MediaChunkSizesConfig()
        assert config.summary_chunk_size == 1500
        assert config.transcript_chunk_size == 2000
        assert config.ocr_text_chunk_size == 1800
        assert config.ocr_code_chunk_size == 2000

    def test_custom_sizes(self):
        """Проверка кастомных размеров."""
        config = MediaChunkSizesConfig(
            summary_chunk_size=1000,
            transcript_chunk_size=3000,
            ocr_text_chunk_size=1500,
            ocr_code_chunk_size=2500,
        )
        assert config.summary_chunk_size == 1000
        assert config.transcript_chunk_size == 3000
        assert config.ocr_text_chunk_size == 1500
        assert config.ocr_code_chunk_size == 2500

    def test_validation_min_constraint(self):
        """Проверка минимального ограничения (ge=500)."""
        with pytest.raises(ValidationError) as exc_info:
            MediaChunkSizesConfig(summary_chunk_size=400)
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "greater_than_equal"
        assert "summary_chunk_size" in str(errors[0])

    def test_validation_max_constraint(self):
        """Проверка максимального ограничения (le=8000)."""
        with pytest.raises(ValidationError) as exc_info:
            MediaChunkSizesConfig(transcript_chunk_size=9000)
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "less_than_equal"
        assert "transcript_chunk_size" in str(errors[0])


class TestMediaProcessingConfig:
    """Тесты для MediaProcessingConfig."""

    def test_defaults(self):
        """Проверка дефолтных значений."""
        config = MediaProcessingConfig()
        assert config.ocr_parser_mode == "markdown"
        assert config.enable_timecodes is True
        assert config.strict_timecode_ordering is False
        assert config.max_timeline_items == 100

    def test_custom_values(self):
        """Проверка кастомных значений."""
        config = MediaProcessingConfig(
            ocr_parser_mode="plain",
            enable_timecodes=False,
            strict_timecode_ordering=True,
            max_timeline_items=50,
        )
        assert config.ocr_parser_mode == "plain"
        assert config.enable_timecodes is False
        assert config.strict_timecode_ordering is True
        assert config.max_timeline_items == 50

    def test_ocr_parser_mode_validation(self):
        """Проверка pattern validation для ocr_parser_mode."""
        # Valid values
        config1 = MediaProcessingConfig(ocr_parser_mode="markdown")
        assert config1.ocr_parser_mode == "markdown"
        
        config2 = MediaProcessingConfig(ocr_parser_mode="plain")
        assert config2.ocr_parser_mode == "plain"
        
        # Invalid value
        with pytest.raises(ValidationError) as exc_info:
            MediaProcessingConfig(ocr_parser_mode="invalid")
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["type"] == "string_pattern_mismatch"

    def test_max_timeline_items_constraints(self):
        """Проверка ограничений max_timeline_items (ge=10, le=500)."""
        # Min boundary
        config1 = MediaProcessingConfig(max_timeline_items=10)
        assert config1.max_timeline_items == 10
        
        # Max boundary
        config2 = MediaProcessingConfig(max_timeline_items=500)
        assert config2.max_timeline_items == 500
        
        # Below min
        with pytest.raises(ValidationError) as exc_info:
            MediaProcessingConfig(max_timeline_items=5)
        assert exc_info.value.errors()[0]["type"] == "greater_than_equal"
        
        # Above max
        with pytest.raises(ValidationError) as exc_info:
            MediaProcessingConfig(max_timeline_items=600)
        assert exc_info.value.errors()[0]["type"] == "less_than_equal"


class TestMediaConfig:
    """Тесты для MediaConfig (композиция вложенных моделей)."""

    def test_defaults(self):
        """Проверка дефолтных значений."""
        config = MediaConfig()
        assert isinstance(config.prompts, MediaPromptsConfig)
        assert isinstance(config.chunk_sizes, MediaChunkSizesConfig)
        assert isinstance(config.processing, MediaProcessingConfig)
        
        # Check nested defaults
        assert config.prompts.audio_instructions is None
        assert config.chunk_sizes.summary_chunk_size == 1500
        assert config.processing.ocr_parser_mode == "markdown"

    def test_custom_nested_values(self):
        """Проверка кастомных вложенных значений."""
        config = MediaConfig(
            prompts=MediaPromptsConfig(audio_instructions="Custom audio"),
            chunk_sizes=MediaChunkSizesConfig(summary_chunk_size=1000),
            processing=MediaProcessingConfig(ocr_parser_mode="plain"),
        )
        assert config.prompts.audio_instructions == "Custom audio"
        assert config.chunk_sizes.summary_chunk_size == 1000
        assert config.processing.ocr_parser_mode == "plain"

    def test_dict_initialization(self):
        """Проверка инициализации из словарей."""
        config = MediaConfig(
            prompts={"audio_instructions": "Audio only"},
            chunk_sizes={"summary_chunk_size": 1200},
            processing={"enable_timecodes": False},
        )
        assert config.prompts.audio_instructions == "Audio only"
        assert config.chunk_sizes.summary_chunk_size == 1200
        assert config.processing.enable_timecodes is False


class TestSemanticConfigMediaIntegration:
    """Тесты интеграции MediaConfig в SemanticConfig."""

    def test_default_media_config(self):
        """Проверка дефолтного MediaConfig в SemanticConfig."""
        config = SemanticConfig()
        assert isinstance(config.media, MediaConfig)
        assert config.media.prompts.audio_instructions is None
        assert config.media.chunk_sizes.summary_chunk_size == 1500
        assert config.media.processing.ocr_parser_mode == "markdown"

    def test_override_media_config(self):
        """Проверка override MediaConfig через kwargs."""
        media_config = MediaConfig(
            prompts=MediaPromptsConfig(audio_instructions="Focus on keywords"),
            chunk_sizes=MediaChunkSizesConfig(transcript_chunk_size=3000),
        )
        config = SemanticConfig(media=media_config)
        
        assert config.media.prompts.audio_instructions == "Focus on keywords"
        assert config.media.chunk_sizes.transcript_chunk_size == 3000

    def test_toml_media_config_loading(self):
        """Проверка загрузки MediaConfig из TOML файла."""
        toml_content = """
[media.prompts]
audio_instructions = "Detect technical terms"
image_instructions = "Focus on diagrams"

[media.chunk_sizes]
summary_chunk_size = 1200
transcript_chunk_size = 2500

[media.processing]
ocr_parser_mode = "plain"
enable_timecodes = false
max_timeline_items = 75
"""
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".toml",
            delete=False,
            dir=Path.cwd(),
        ) as f:
            f.write(toml_content)
            toml_path = Path(f.name)
        
        # Rename to semantic.toml to be discovered
        semantic_toml = Path.cwd() / "semantic.toml"
        backup_exists = semantic_toml.exists()
        if backup_exists:
            backup_path = semantic_toml.with_suffix(".toml.backup")
            semantic_toml.rename(backup_path)
        
        try:
            toml_path.rename(semantic_toml)
            
            # Load config
            config = SemanticConfig()
            
            # Verify nested media config loaded
            assert config.media.prompts.audio_instructions == "Detect technical terms"
            assert config.media.prompts.image_instructions == "Focus on diagrams"
            assert config.media.chunk_sizes.summary_chunk_size == 1200
            assert config.media.chunk_sizes.transcript_chunk_size == 2500
            assert config.media.processing.ocr_parser_mode == "plain"
            assert config.media.processing.enable_timecodes is False
            assert config.media.processing.max_timeline_items == 75
        finally:
            # Cleanup
            if semantic_toml.exists():
                semantic_toml.unlink()
            if backup_exists:
                backup_path.rename(semantic_toml)

    def test_to_toml_dict_with_media_config(self):
        """Проверка сериализации MediaConfig в TOML dict."""
        config = SemanticConfig(
            media=MediaConfig(
                prompts=MediaPromptsConfig(audio_instructions="Custom"),
                chunk_sizes=MediaChunkSizesConfig(summary_chunk_size=1000),
                processing=MediaProcessingConfig(max_timeline_items=50),
            )
        )
        
        toml_dict = config.to_toml_dict()
        
        # Verify media section
        assert "media" in toml_dict
        assert "prompts" in toml_dict["media"]
        assert "chunk_sizes" in toml_dict["media"]
        assert "processing" in toml_dict["media"]
        
        # Verify values
        assert toml_dict["media"]["prompts"]["audio_instructions"] == "Custom"
        assert toml_dict["media"]["chunk_sizes"]["summary_chunk_size"] == 1000
        assert toml_dict["media"]["processing"]["max_timeline_items"] == 50

    def test_partial_toml_media_config(self):
        """Проверка частичной загрузки MediaConfig из TOML."""
        toml_content = """
[media.prompts]
audio_instructions = "Audio only"

[media.chunk_sizes]
summary_chunk_size = 1100
"""
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".toml",
            delete=False,
            dir=Path.cwd(),
        ) as f:
            f.write(toml_content)
            toml_path = Path(f.name)
        
        semantic_toml = Path.cwd() / "semantic.toml"
        backup_exists = semantic_toml.exists()
        if backup_exists:
            backup_path = semantic_toml.with_suffix(".toml.backup")
            semantic_toml.rename(backup_path)
        
        try:
            toml_path.rename(semantic_toml)
            config = SemanticConfig()
            
            # Partial values loaded
            assert config.media.prompts.audio_instructions == "Audio only"
            assert config.media.chunk_sizes.summary_chunk_size == 1100
            
            # Defaults preserved
            assert config.media.prompts.image_instructions is None
            assert config.media.chunk_sizes.transcript_chunk_size == 2000
            assert config.media.processing.ocr_parser_mode == "markdown"
        finally:
            if semantic_toml.exists():
                semantic_toml.unlink()
            if backup_exists:
                backup_path.rename(semantic_toml)
