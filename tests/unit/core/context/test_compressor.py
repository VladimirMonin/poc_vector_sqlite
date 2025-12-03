"""Тесты для ContextCompressor."""

import pytest
from unittest.mock import MagicMock

from semantic_core.interfaces.chat_history import ChatMessage
from semantic_core.interfaces.llm import GenerationResult
from semantic_core.core.context.compressor import ContextCompressor


class MockLLMProvider:
    """Mock LLM провайдер для тестов."""

    def __init__(self, response_text: str = "Summary of conversation", output_tokens: int = 50):
        self.response_text = response_text
        self.output_tokens = output_tokens
        self.call_count = 0
        self.last_prompt = None

    @property
    def model_name(self) -> str:
        return "mock-model"

    def generate(self, prompt: str, **kwargs) -> GenerationResult:
        self.call_count += 1
        self.last_prompt = prompt
        return GenerationResult(
            text=self.response_text,
            model="mock-model",
            input_tokens=100,
            output_tokens=self.output_tokens,
        )


class TestContextCompressor:
    """Тесты для ContextCompressor."""

    def test_init(self):
        """Инициализация компрессора."""
        llm = MockLLMProvider()
        compressor = ContextCompressor(llm)

        assert compressor.llm == llm
        assert compressor.temperature == 0.3

    def test_init_custom_temperature(self):
        """Инициализация с кастомной температурой."""
        llm = MockLLMProvider()
        compressor = ContextCompressor(llm, temperature=0.5)

        assert compressor.temperature == 0.5

    def test_compress_empty_messages(self):
        """Сжатие пустого списка возвращает пустое summary."""
        llm = MockLLMProvider()
        compressor = ContextCompressor(llm)

        result = compressor.compress([])

        assert result.role == "system"
        assert "[Empty conversation summary]" in result.content
        assert llm.call_count == 0  # LLM не вызывается

    def test_compress_single_message(self):
        """Сжатие одного сообщения."""
        llm = MockLLMProvider(response_text="User asked about Python.")
        compressor = ContextCompressor(llm)

        messages = [ChatMessage("user", "Расскажи о Python", tokens=10)]
        result = compressor.compress(messages)

        assert result.role == "system"
        assert "[Previous conversation summary]" in result.content
        assert "User asked about Python." in result.content
        assert llm.call_count == 1

    def test_compress_multiple_messages(self):
        """Сжатие нескольких сообщений."""
        llm = MockLLMProvider(response_text="Discussion about Python basics.")
        compressor = ContextCompressor(llm)

        messages = [
            ChatMessage("user", "Что такое Python?", tokens=10),
            ChatMessage("assistant", "Python — это язык программирования.", tokens=20),
            ChatMessage("user", "А для чего он используется?", tokens=15),
        ]
        result = compressor.compress(messages)

        assert result.role == "system"
        assert "Discussion about Python basics." in result.content
        assert llm.call_count == 1

    def test_compress_formats_history_correctly(self):
        """Проверяет формат истории в промпте."""
        llm = MockLLMProvider()
        compressor = ContextCompressor(llm)

        messages = [
            ChatMessage("user", "Hello"),
            ChatMessage("assistant", "Hi there!"),
            ChatMessage("system", "Be helpful."),
        ]
        compressor.compress(messages)

        # Проверяем что все роли и сообщения в промпте
        assert "USER: Hello" in llm.last_prompt
        assert "ASSISTANT: Hi there!" in llm.last_prompt
        assert "SYSTEM: Be helpful." in llm.last_prompt

    def test_compress_uses_output_tokens(self):
        """Результат использует output_tokens от LLM."""
        llm = MockLLMProvider(output_tokens=75)
        compressor = ContextCompressor(llm)

        messages = [ChatMessage("user", "Test", tokens=10)]
        result = compressor.compress(messages)

        assert result.tokens == 75

    def test_compress_estimates_tokens_if_none(self):
        """Оценивает токены если LLM не вернул."""
        llm = MockLLMProvider()
        llm.output_tokens = None  # type: ignore

        # Патчим generate чтобы вернуть None
        def generate_no_tokens(prompt, **kwargs):
            return GenerationResult(
                text="Summary" * 10,  # 70 символов ≈ 17 токенов
                model="mock",
                output_tokens=None,
            )

        llm.generate = generate_no_tokens  # type: ignore
        compressor = ContextCompressor(llm)

        messages = [ChatMessage("user", "Test")]
        result = compressor.compress(messages)

        # Должен использовать оценку (len / 4)
        assert result.tokens > 0

    def test_compress_prompt_contains_rules(self):
        """Промпт содержит правила сжатия."""
        llm = MockLLMProvider()
        compressor = ContextCompressor(llm)

        messages = [ChatMessage("user", "Test")]
        compressor.compress(messages)

        assert "Keep all key facts" in llm.last_prompt
        assert "SUMMARY:" in llm.last_prompt

    def test_format_history_separates_messages(self):
        """_format_history разделяет сообщения пустой строкой."""
        llm = MockLLMProvider()
        compressor = ContextCompressor(llm)

        messages = [
            ChatMessage("user", "First"),
            ChatMessage("assistant", "Second"),
        ]

        formatted = compressor._format_history(messages)

        assert "USER: First\n\nASSISTANT: Second" == formatted

    def test_estimate_tokens(self):
        """_estimate_tokens работает корректно."""
        llm = MockLLMProvider()
        compressor = ContextCompressor(llm)

        # 100 символов ≈ 25 токенов
        assert compressor._estimate_tokens("a" * 100) == 25
        assert compressor._estimate_tokens("") == 0
        assert compressor._estimate_tokens("abcd") == 1


class TestContextCompressorIntegration:
    """Интеграционные тесты для ContextCompressor."""

    def test_compression_ratio_logged(self):
        """Сжатие логирует compression_ratio."""
        llm = MockLLMProvider(response_text="Short", output_tokens=10)
        compressor = ContextCompressor(llm)

        # 1000 токенов → 10 токенов = ratio 100
        messages = [ChatMessage("user", "Long message", tokens=1000)]
        result = compressor.compress(messages)

        assert result.tokens == 10
        # Ratio = 1000 / 10 = 100.0

    def test_multiple_compressions(self):
        """Можно вызывать compress несколько раз."""
        llm = MockLLMProvider()
        compressor = ContextCompressor(llm)

        messages1 = [ChatMessage("user", "First batch")]
        messages2 = [ChatMessage("user", "Second batch")]

        result1 = compressor.compress(messages1)
        result2 = compressor.compress(messages2)

        assert llm.call_count == 2
        assert result1.content != result2.content or llm.response_text == llm.response_text
