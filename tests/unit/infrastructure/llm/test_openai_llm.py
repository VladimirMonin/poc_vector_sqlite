"""Unit-тесты для OpenAI LLM провайдера (Phase 15.3).

Тестирует:
- OpenAILLMProvider с моками OpenAI SDK
- Генерация ответов и streaming
- Подсчёт токенов через tiktoken
- Обработку ошибок (rate limits, API errors)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

# Skip all tests if openai is not installed
pytest.importorskip("openai", reason="openai package not installed")

from semantic_core.infrastructure.openai import OpenAILLMProvider
from semantic_core.interfaces.llm import BaseLLMProvider, GenerationResult


# ============================================================================
# Tests: Initialization
# ============================================================================


class TestOpenAILLMProviderInit:
    """Тесты инициализации OpenAILLMProvider."""

    @patch("semantic_core.infrastructure.openai.llm.OpenAI")
    def test_llm_initialization(self, mock_openai_class):
        """Проверка инициализации с разными параметрами."""
        provider = OpenAILLMProvider(
            model="gpt-4o-mini",
            api_key="test-key",
            temperature=0.5,
        )

        assert provider.model_name == "gpt-4o-mini"
        assert provider._temperature == 0.5
        mock_openai_class.assert_called_once()

    @patch("semantic_core.infrastructure.openai.llm.OpenAI")
    def test_initialization_with_defaults(self, mock_openai_class):
        """Проверка инициализации с дефолтными параметрами."""
        provider = OpenAILLMProvider(api_key="test-key")

        assert provider.model_name == "gpt-4o-mini"
        assert provider._temperature == 0.7
        assert provider._max_tokens == 2000

    @patch("semantic_core.infrastructure.openai.llm.OpenAI")
    def test_interface_compliance(self, mock_openai_class):
        """Проверка соответствия интерфейсу BaseLLMProvider."""
        provider = OpenAILLMProvider(api_key="test-key")

        assert isinstance(provider, BaseLLMProvider)
        assert hasattr(provider, "generate")
        assert hasattr(provider, "generate_stream")
        assert hasattr(provider, "count_tokens")


# ============================================================================
# Tests: Generate
# ============================================================================


class TestOpenAILLMProviderGenerate:
    """Тесты метода generate()."""

    @patch("semantic_core.infrastructure.openai.llm.OpenAI")
    def test_generate_response(self, mock_openai_class):
        """Проверка генерации ответа."""
        # Mock OpenAI response
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="Test response"), finish_reason="stop")
        ]
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=5)

        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        provider = OpenAILLMProvider(api_key="test-key")
        result = provider.generate("Test prompt")

        assert isinstance(result, GenerationResult)
        assert result.text == "Test response"
        assert result.input_tokens == 10
        assert result.output_tokens == 5
        assert result.finish_reason == "stop"

    @patch("semantic_core.infrastructure.openai.llm.OpenAI")
    def test_generate_with_system_message(self, mock_openai_class):
        """Проверка использования system_prompt."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="Response"), finish_reason="stop")
        ]
        mock_response.usage = Mock(prompt_tokens=20, completion_tokens=10)

        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        provider = OpenAILLMProvider(api_key="test-key")
        provider.generate(
            prompt="User question",
            system_prompt="You are a helpful assistant",
        )

        # Проверка что system message передан
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant"
        assert messages[1]["role"] == "user"

    @patch("semantic_core.infrastructure.openai.llm.OpenAI")
    def test_temperature_parameter(self, mock_openai_class):
        """Проверка передачи параметра temperature."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="Response"), finish_reason="stop")
        ]
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=5)

        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        provider = OpenAILLMProvider(api_key="test-key", temperature=0.2)
        provider.generate("Test prompt")

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["temperature"] == 0.2

    @patch("semantic_core.infrastructure.openai.llm.OpenAI")
    def test_max_tokens_parameter(self, mock_openai_class):
        """Проверка передачи параметра max_tokens."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="Response"), finish_reason="stop")
        ]
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=5)

        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        provider = OpenAILLMProvider(api_key="test-key", max_tokens=1000)
        provider.generate("Test prompt")

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["max_tokens"] == 1000

    @patch("semantic_core.infrastructure.openai.llm.OpenAI")
    def test_different_models(self, mock_openai_class):
        """Проверка работы с разными моделями."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="Response"), finish_reason="stop")
        ]
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=5)

        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        models = ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]

        for model in models:
            provider = OpenAILLMProvider(model=model, api_key="test-key")
            provider.generate("Test")

            call_args = mock_client.chat.completions.create.call_args
            assert call_args.kwargs["model"] == model


# ============================================================================
# Tests: Streaming
# ============================================================================


class TestOpenAILLMProviderStreaming:
    """Тесты метода generate_stream()."""

    @patch("semantic_core.infrastructure.openai.llm.OpenAI")
    def test_streaming_support(self, mock_openai_class):
        """Проверка streaming генерации."""
        mock_client = Mock()

        # Mock streaming response
        mock_chunks = [
            Mock(
                choices=[Mock(delta=Mock(content="Hello"), finish_reason=None)]
            ),
            Mock(
                choices=[Mock(delta=Mock(content=" world"), finish_reason=None)]
            ),
            Mock(choices=[Mock(delta=Mock(content="!"), finish_reason="stop")]),
        ]

        mock_client.chat.completions.create.return_value = iter(mock_chunks)
        mock_openai_class.return_value = mock_client

        provider = OpenAILLMProvider(api_key="test-key")
        chunks = list(provider.generate_stream("Test prompt"))

        assert chunks == ["Hello", " world", "!"]

    @patch("semantic_core.infrastructure.openai.llm.OpenAI")
    def test_streaming_with_system_prompt(self, mock_openai_class):
        """Проверка streaming с system_prompt."""
        mock_client = Mock()

        mock_chunks = [Mock(choices=[Mock(delta=Mock(content="Hi"))])]
        mock_client.chat.completions.create.return_value = iter(mock_chunks)
        mock_openai_class.return_value = mock_client

        provider = OpenAILLMProvider(api_key="test-key")
        list(
            provider.generate_stream(
                "Test", system_prompt="You are helpful"
            )
        )

        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]

        assert messages[0]["role"] == "system"
        assert call_args.kwargs["stream"] is True


# ============================================================================
# Tests: Token Counting
# ============================================================================


class TestOpenAILLMProviderTokens:
    """Тесты подсчёта токенов через tiktoken."""

    @patch("semantic_core.infrastructure.openai.llm.OpenAI")
    def test_token_counting(self, mock_openai_class):
        """Проверка подсчёта токенов через tiktoken."""
        provider = OpenAILLMProvider(model="gpt-4o-mini", api_key="test-key")

        text = "Hello, how are you?"
        token_count = provider.count_tokens(text)

        assert token_count > 0
        assert isinstance(token_count, int)

    @patch("semantic_core.infrastructure.openai.llm.OpenAI")
    def test_token_counting_different_models(self, mock_openai_class):
        """Проверка что tiktoken использует правильный encoding для модели."""
        provider_gpt4 = OpenAILLMProvider(model="gpt-4o", api_key="test-key")
        provider_gpt35 = OpenAILLMProvider(
            model="gpt-3.5-turbo", api_key="test-key"
        )

        text = "Test tokenization"

        tokens_gpt4 = provider_gpt4.count_tokens(text)
        tokens_gpt35 = provider_gpt35.count_tokens(text)

        # Должны быть примерно одинаковыми (используют cl100k_base)
        assert abs(tokens_gpt4 - tokens_gpt35) <= 2

    @patch("semantic_core.infrastructure.openai.llm.OpenAI")
    def test_token_counting_empty_text(self, mock_openai_class):
        """Проверка подсчёта токенов для пустого текста."""
        provider = OpenAILLMProvider(api_key="test-key")

        tokens = provider.count_tokens("")
        assert tokens == 0


# ============================================================================
# Tests: Error Handling
# ============================================================================


class TestOpenAILLMProviderErrors:
    """Тесты обработки ошибок."""

    @patch("semantic_core.infrastructure.openai.llm.OpenAI")
    def test_error_handling_rate_limit(self, mock_openai_class):
        """Проверка обработки rate limits."""
        from openai import RateLimitError

        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = RateLimitError(
            "Rate limit exceeded",
            response=Mock(status_code=429),
            body=None,
        )
        mock_openai_class.return_value = mock_client

        provider = OpenAILLMProvider(api_key="test-key")

        with pytest.raises(RateLimitError):
            provider.generate("Test prompt")

    @patch("semantic_core.infrastructure.openai.llm.OpenAI")
    def test_error_handling_api_error(self, mock_openai_class):
        """Проверка обработки API ошибок."""
        from openai import APIError

        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = APIError(
            "API Error",
            response=Mock(status_code=500),
            body=None,
        )
        mock_openai_class.return_value = mock_client

        provider = OpenAILLMProvider(api_key="test-key")

        with pytest.raises(APIError):
            provider.generate("Test prompt")

    @patch("semantic_core.infrastructure.openai.llm.OpenAI")
    def test_error_handling_timeout(self, mock_openai_class):
        """Проверка обработки timeout."""
        from openai import APITimeoutError

        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = APITimeoutError(
            "Request timed out"
        )
        mock_openai_class.return_value = mock_client

        provider = OpenAILLMProvider(api_key="test-key")

        with pytest.raises(RuntimeError, match="OpenAI API timeout"):
            provider.generate("Test prompt")

    @patch("semantic_core.infrastructure.openai.llm.OpenAI")
    def test_error_handling_unexpected(self, mock_openai_class):
        """Проверка обработки неожиданных ошибок."""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception(
            "Unexpected error"
        )
        mock_openai_class.return_value = mock_client

        provider = OpenAILLMProvider(api_key="test-key")

        with pytest.raises(RuntimeError, match="Ошибка генерации LLM"):
            provider.generate("Test prompt")


# ============================================================================
# Tests: History Support
# ============================================================================


class TestOpenAILLMProviderHistory:
    """Тесты поддержки истории чата."""

    @patch("semantic_core.infrastructure.openai.llm.OpenAI")
    def test_generate_with_history(self, mock_openai_class):
        """Проверка генерации с историей."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="Response"), finish_reason="stop")
        ]
        mock_response.usage = Mock(prompt_tokens=30, completion_tokens=10)

        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        history = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]

        provider = OpenAILLMProvider(api_key="test-key")
        provider.generate("How are you?", history=history)

        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]

        assert len(messages) == 3
        assert messages[0]["content"] == "Hi"
        assert messages[1]["content"] == "Hello!"
        assert messages[2]["content"] == "How are you?"

    @patch("semantic_core.infrastructure.openai.llm.OpenAI")
    def test_generate_with_history_and_system(self, mock_openai_class):
        """Проверка генерации с историей и system_prompt."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="Response"), finish_reason="stop")
        ]
        mock_response.usage = Mock(prompt_tokens=30, completion_tokens=10)

        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        history = [{"role": "user", "content": "Hi"}]

        provider = OpenAILLMProvider(api_key="test-key")
        provider.generate(
            "Test", system_prompt="You are helpful", history=history
        )

        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]

        # system, history, current
        assert len(messages) == 3
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "user"
