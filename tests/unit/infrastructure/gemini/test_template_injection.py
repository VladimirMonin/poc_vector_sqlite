"""Unit-тесты Template Injection для Gemini анализаторов.

Проверяет:
- custom_instructions injection в промпт
- placeholder escaping (не ломает JSON schema)
- corrupted template handling
"""

import pytest
from unittest.mock import MagicMock, patch

from semantic_core.infrastructure.gemini.audio_analyzer import (
    GeminiAudioAnalyzer,
    DEFAULT_SYSTEM_PROMPT,
)
from semantic_core.infrastructure.gemini.image_analyzer import (
    GeminiImageAnalyzer,
    DEFAULT_SYSTEM_PROMPT as IMAGE_DEFAULT_PROMPT,
)
from semantic_core.infrastructure.gemini.video_analyzer import (
    GeminiVideoAnalyzer,
    DEFAULT_SYSTEM_PROMPT as VIDEO_DEFAULT_PROMPT,
)


class TestAudioAnalyzerTemplateInjection:
    """Тесты Template Injection для AudioAnalyzer."""

    def test_default_prompt_no_custom_instructions(self):
        """Проверка дефолтного промпта без кастомных инструкций."""
        analyzer = GeminiAudioAnalyzer(
            api_key="test_key",
            output_language="English",
        )
        
        assert "{custom_instructions}" not in analyzer.system_prompt
        assert "{language}" not in analyzer.system_prompt
        assert "Response language: English" in analyzer.system_prompt
        assert "CUSTOM INSTRUCTIONS:" not in analyzer.system_prompt

    def test_custom_instructions_injection(self):
        """Проверка injection кастомных инструкций."""
        custom_instr = "Focus on technical terms and code examples"
        analyzer = GeminiAudioAnalyzer(
            api_key="test_key",
            output_language="Russian",
            custom_instructions=custom_instr,
        )
        
        assert "CUSTOM INSTRUCTIONS:" in analyzer.system_prompt
        assert custom_instr in analyzer.system_prompt
        assert "Response language: Russian" in analyzer.system_prompt
        assert "{custom_instructions}" not in analyzer.system_prompt  # Replaced

    def test_placeholder_escaping(self):
        """Проверка что placeholders корректно экранируются."""
        # Если юзер передаст строку с {}, они не должны конфликтовать с .format()
        custom_instr = "Detect patterns like {variable_name} in code"
        analyzer = GeminiAudioAnalyzer(
            api_key="test_key",
            custom_instructions=custom_instr,
        )
        
        # Должна остаться в итоговом промпте как есть
        assert "{variable_name}" in analyzer.system_prompt
        # Но плейсхолдеры шаблона должны быть заменены
        assert "{custom_instructions}" not in analyzer.system_prompt
        assert "{language}" not in analyzer.system_prompt

    def test_json_schema_not_corrupted(self):
        """Проверка что JSON schema описание не повреждено."""
        custom_instr = "Extract all speaker names"
        analyzer = GeminiAudioAnalyzer(
            api_key="test_key",
            custom_instructions=custom_instr,
        )
        
        # JSON schema должна быть после CUSTOM INSTRUCTIONS
        assert '{\n  "description"' in analyzer.system_prompt
        assert '"transcription": "MARKDOWN_FORMATTED_TRANSCRIPT_HERE"' in analyzer.system_prompt
        
        # Кастомные инструкции идут ПЕРЕД JSON schema
        custom_idx = analyzer.system_prompt.index("CUSTOM INSTRUCTIONS:")
        json_idx = analyzer.system_prompt.index("Return a JSON")
        assert custom_idx < json_idx

    def test_multiline_custom_instructions(self):
        """Проверка мультистрочных кастомных инструкций."""
        custom_instr = """Focus on:
- Technical terminology
- Code snippets
- Speaker names"""
        
        analyzer = GeminiAudioAnalyzer(
            api_key="test_key",
            custom_instructions=custom_instr,
        )
        
        assert "Technical terminology" in analyzer.system_prompt
        assert "Code snippets" in analyzer.system_prompt
        assert "Speaker names" in analyzer.system_prompt

    def test_build_system_prompt_method(self):
        """Проверка метода _build_system_prompt()."""
        analyzer = GeminiAudioAnalyzer(
            api_key="test_key",
            output_language="French",
            custom_instructions="Custom rules",
        )
        
        rebuilt_prompt = analyzer._build_system_prompt()
        
        # Должен совпадать с сохранённым
        assert rebuilt_prompt == analyzer.system_prompt
        assert "Response language: French" in rebuilt_prompt
        assert "Custom rules" in rebuilt_prompt


class TestImageAnalyzerTemplateInjection:
    """Тесты Template Injection для ImageAnalyzer."""

    def test_default_prompt_no_custom_instructions(self):
        """Проверка дефолтного промпта без кастомных инструкций."""
        analyzer = GeminiImageAnalyzer(
            api_key="test_key",
            output_language="English",
        )
        
        assert "{custom_instructions}" not in analyzer.system_prompt
        assert "{language}" not in analyzer.system_prompt
        assert "Answer in English language" in analyzer.system_prompt
        assert "CUSTOM INSTRUCTIONS:" not in analyzer.system_prompt

    def test_custom_instructions_injection(self):
        """Проверка injection кастомных инструкций."""
        custom_instr = "Focus on diagrams and code screenshots"
        analyzer = GeminiImageAnalyzer(
            api_key="test_key",
            output_language="German",
            custom_instructions=custom_instr,
        )
        
        assert "CUSTOM INSTRUCTIONS:" in analyzer.system_prompt
        assert custom_instr in analyzer.system_prompt
        assert "Answer in German language" in analyzer.system_prompt
        assert "{custom_instructions}" not in analyzer.system_prompt

    def test_json_schema_order(self):
        """Проверка порядка: custom instructions → schema."""
        custom_instr = "Detect all text"
        analyzer = GeminiImageAnalyzer(
            api_key="test_key",
            custom_instructions=custom_instr,
        )
        
        # Кастомные инструкции идут ПЕРЕД "Analyze the image"
        custom_idx = analyzer.system_prompt.index("CUSTOM INSTRUCTIONS:")
        analyze_idx = analyzer.system_prompt.index("Analyze the image")
        assert custom_idx < analyze_idx


class TestVideoAnalyzerTemplateInjection:
    """Тесты Template Injection для VideoAnalyzer."""

    def test_default_prompt_no_custom_instructions(self):
        """Проверка дефолтного промпта без кастомных инструкций."""
        analyzer = GeminiVideoAnalyzer(
            api_key="test_key",
            output_language="Spanish",
        )
        
        assert "{custom_instructions}" not in analyzer.system_prompt
        assert "{language}" not in analyzer.system_prompt
        assert "Response language: Spanish" in analyzer.system_prompt
        assert "CUSTOM INSTRUCTIONS:" not in analyzer.system_prompt

    def test_custom_instructions_injection(self):
        """Проверка injection кастомных инструкций."""
        custom_instr = "Transcribe all code from screen recordings"
        analyzer = GeminiVideoAnalyzer(
            api_key="test_key",
            output_language="Italian",
            custom_instructions=custom_instr,
        )
        
        assert "CUSTOM INSTRUCTIONS:" in analyzer.system_prompt
        assert custom_instr in analyzer.system_prompt
        assert "Response language: Italian" in analyzer.system_prompt

    def test_ocr_and_transcription_instructions_preserved(self):
        """Проверка что OCR/Transcription инструкции не повреждены."""
        custom_instr = "Extract diagrams"
        analyzer = GeminiVideoAnalyzer(
            api_key="test_key",
            custom_instructions=custom_instr,
        )
        
        # OCR instructions должны остаться
        assert "CRITICAL INSTRUCTIONS FOR OCR_TEXT FIELD:" in analyzer.system_prompt
        assert "CRITICAL INSTRUCTIONS FOR TRANSCRIPTION FIELD:" in analyzer.system_prompt
        assert "Use `## Slide Title` headers" in analyzer.system_prompt
        
        # Кастомные инструкции идут ПЕРЕД JSON schema
        custom_idx = analyzer.system_prompt.index("CUSTOM INSTRUCTIONS:")
        json_idx = analyzer.system_prompt.index("Return a JSON")
        assert custom_idx < json_idx


class TestTemplateInjectionEdgeCases:
    """Тесты крайних случаев Template Injection."""

    def test_empty_string_custom_instructions(self):
        """Проверка пустой строки кастомных инструкций."""
        analyzer = GeminiAudioAnalyzer(
            api_key="test_key",
            custom_instructions="",
        )
        
        # Пустая строка не должна вставляться
        # (Но empty string is falsy, так что блок не вставится вообще)
        # Проверяем что промпт валидный
        assert "Response language:" in analyzer.system_prompt
        assert "Return a JSON" in analyzer.system_prompt

    def test_unicode_custom_instructions(self):
        """Проверка Unicode символов в кастомных инструкциях."""
        custom_instr = "Транскрибируйте с русскими символами: привет, мир! 🎯"
        analyzer = GeminiAudioAnalyzer(
            api_key="test_key",
            output_language="Russian",
            custom_instructions=custom_instr,
        )
        
        assert "Транскрибируйте" in analyzer.system_prompt
        assert "🎯" in analyzer.system_prompt

    def test_special_characters_in_instructions(self):
        """Проверка спецсимволов в кастомных инструкциях."""
        custom_instr = 'Detect patterns: <tag>, [bracket], {brace}, "quote"'
        analyzer = GeminiImageAnalyzer(
            api_key="test_key",
            custom_instructions=custom_instr,
        )
        
        assert "<tag>" in analyzer.system_prompt
        assert "[bracket]" in analyzer.system_prompt
        assert "{brace}" in analyzer.system_prompt
        assert '"quote"' in analyzer.system_prompt

    def test_long_custom_instructions(self):
        """Проверка очень длинных кастомных инструкций."""
        custom_instr = "Focus on: " + ", ".join([f"item_{i}" for i in range(100)])
        
        analyzer = GeminiVideoAnalyzer(
            api_key="test_key",
            custom_instructions=custom_instr,
        )
        
        assert "item_0" in analyzer.system_prompt
        assert "item_99" in analyzer.system_prompt
        # Промпт должен быть длинным, но корректным
        assert len(analyzer.system_prompt) > 1000


class TestAnalyzerInitializationLogging:
    """Тесты логирования при инициализации анализаторов."""

    @patch("semantic_core.infrastructure.gemini.audio_analyzer.logger")
    def test_audio_analyzer_logs_custom_instructions(self, mock_logger):
        """Проверка что AudioAnalyzer логирует has_custom_instructions."""
        analyzer = GeminiAudioAnalyzer(
            api_key="test_key",
            custom_instructions="Test instructions",
        )
        
        # Должен залогировать has_custom_instructions=True
        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args
        assert call_args[0][0] == "Audio analyzer initialized"
        assert call_args[1]["has_custom_instructions"] is True

    @patch("semantic_core.infrastructure.gemini.image_analyzer.logger")
    def test_image_analyzer_logs_custom_instructions(self, mock_logger):
        """Проверка что ImageAnalyzer логирует has_custom_instructions."""
        analyzer = GeminiImageAnalyzer(
            api_key="test_key",
            custom_instructions="Test instructions",
        )
        
        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args
        assert call_args[0][0] == "Image analyzer initialized"
        assert call_args[1]["has_custom_instructions"] is True

    @patch("semantic_core.infrastructure.gemini.video_analyzer.logger")
    def test_video_analyzer_logs_custom_instructions(self, mock_logger):
        """Проверка что VideoAnalyzer логирует has_custom_instructions."""
        analyzer = GeminiVideoAnalyzer(
            api_key="test_key",
            custom_instructions="Test instructions",
        )
        
        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args
        assert call_args[0][0] == "Video analyzer initialized"
        assert call_args[1]["has_custom_instructions"] is True
