"""Unit-тесты для LLM провайдеров (Phase 9.0).

Тестирует:
- GeminiLLMProvider с моками
- Обработку ошибок
"""

from unittest.mock import MagicMock, patch

import pytest

from semantic_core.interfaces.llm import GenerationResult


# ============================================================================
# Tests: GeminiLLMProvider
# ============================================================================


class TestGeminiLLMProvider:
    """Тесты для GeminiLLMProvider."""

    @patch("semantic_core.infrastructure.llm.gemini.genai")
    def test_initialization(self, mock_genai):
        """Инициализация провайдера."""
        from semantic_core.infrastructure.llm.gemini import GeminiLLMProvider

        provider = GeminiLLMProvider(
            api_key="test-api-key",
            model="gemini-2.0-flash",
        )

        assert provider.model_name == "gemini-2.0-flash"
        mock_genai.Client.assert_called_once_with(api_key="test-api-key")

    @patch("semantic_core.infrastructure.llm.gemini.genai")
    def test_generate_basic(self, mock_genai):
        """Базовая генерация."""
        from semantic_core.infrastructure.llm.gemini import GeminiLLMProvider

        # Настраиваем мок ответа
        mock_response = MagicMock()
        mock_response.text = "This is the generated response"
        mock_response.usage_metadata.prompt_token_count = 50
        mock_response.usage_metadata.candidates_token_count = 30
        mock_response.candidates = [
            MagicMock(finish_reason=MagicMock(name="STOP"))
        ]

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client

        provider = GeminiLLMProvider(api_key="test-key")
        result = provider.generate("What is Python?")

        assert isinstance(result, GenerationResult)
        assert result.text == "This is the generated response"
        assert result.model == "gemini-2.0-flash"
        assert result.input_tokens == 50
        assert result.output_tokens == 30

    @patch("semantic_core.infrastructure.llm.gemini.genai")
    def test_generate_with_system_prompt(self, mock_genai):
        """Генерация с системным промптом."""
        from semantic_core.infrastructure.llm.gemini import GeminiLLMProvider
        from google.genai import types

        mock_response = MagicMock()
        mock_response.text = "Response"
        mock_response.usage_metadata = None
        mock_response.candidates = []

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client

        provider = GeminiLLMProvider(api_key="test-key")
        provider.generate(
            "What is Python?",
            system_prompt="You are a helpful assistant.",
            temperature=0.5,
            max_tokens=100,
        )

        # Проверяем вызов с правильными параметрами
        call_kwargs = mock_client.models.generate_content.call_args
        assert call_kwargs.kwargs["model"] == "gemini-2.0-flash"
        assert call_kwargs.kwargs["contents"] == "What is Python?"

    @patch("semantic_core.infrastructure.llm.gemini.genai")
    def test_generate_handles_error(self, mock_genai):
        """Обработка ошибок API."""
        from semantic_core.infrastructure.llm.gemini import GeminiLLMProvider

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("API Error")
        mock_genai.Client.return_value = mock_client

        provider = GeminiLLMProvider(api_key="test-key")

        with pytest.raises(RuntimeError, match="Ошибка генерации LLM"):
            provider.generate("query")

    @patch("semantic_core.infrastructure.llm.gemini.genai")
    def test_generate_with_custom_model(self, mock_genai):
        """Генерация с кастомной моделью."""
        from semantic_core.infrastructure.llm.gemini import GeminiLLMProvider

        mock_response = MagicMock()
        mock_response.text = "Response"
        mock_response.usage_metadata = None
        mock_response.candidates = []

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client

        provider = GeminiLLMProvider(
            api_key="test-key",
            model="gemini-1.5-pro",
        )

        assert provider.model_name == "gemini-1.5-pro"

        provider.generate("test")

        call_kwargs = mock_client.models.generate_content.call_args
        assert call_kwargs.kwargs["model"] == "gemini-1.5-pro"

    @patch("semantic_core.infrastructure.llm.gemini.genai")
    def test_generate_no_usage_metadata(self, mock_genai):
        """Генерация без метаданных использования."""
        from semantic_core.infrastructure.llm.gemini import GeminiLLMProvider

        mock_response = MagicMock()
        mock_response.text = "Response"
        mock_response.usage_metadata = None
        mock_response.candidates = []

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client

        provider = GeminiLLMProvider(api_key="test-key")
        result = provider.generate("query")

        assert result.input_tokens is None
        assert result.output_tokens is None
        assert result.total_tokens is None

    @patch("semantic_core.infrastructure.llm.gemini.genai")
    def test_generate_empty_text(self, mock_genai):
        """Обработка пустого ответа."""
        from semantic_core.infrastructure.llm.gemini import GeminiLLMProvider

        mock_response = MagicMock()
        mock_response.text = None  # API может вернуть None
        mock_response.usage_metadata = None
        mock_response.candidates = []

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client

        provider = GeminiLLMProvider(api_key="test-key")
        result = provider.generate("query")

        assert result.text == ""  # Должен вернуть пустую строку, не None
