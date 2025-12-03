"""Тесты для стратегий управления историей чата."""

import pytest
from unittest.mock import MagicMock

from semantic_core.interfaces.chat_history import ChatMessage
from semantic_core.interfaces.llm import GenerationResult
from semantic_core.core.context.strategies import (
    LastNMessages,
    TokenBudget,
    Unlimited,
    AdaptiveWithCompression,
)
from semantic_core.core.context.compressor import ContextCompressor


class TestLastNMessages:
    """Тесты для стратегии LastNMessages."""

    def test_init_valid(self):
        """Инициализация с валидным n."""
        strategy = LastNMessages(n=5)
        assert strategy.n == 5

    def test_init_invalid_zero(self):
        """Ошибка при n=0."""
        with pytest.raises(ValueError, match="n должно быть >= 1"):
            LastNMessages(n=0)

    def test_init_invalid_negative(self):
        """Ошибка при отрицательном n."""
        with pytest.raises(ValueError, match="n должно быть >= 1"):
            LastNMessages(n=-1)

    def test_should_trim_under_limit(self):
        """Не требует обрезки если меньше лимита."""
        strategy = LastNMessages(n=5)
        messages = [ChatMessage("user", f"msg{i}") for i in range(3)]
        assert strategy.should_trim(messages) is False

    def test_should_trim_at_limit(self):
        """Не требует обрезки если ровно лимит."""
        strategy = LastNMessages(n=5)
        messages = [ChatMessage("user", f"msg{i}") for i in range(5)]
        assert strategy.should_trim(messages) is False

    def test_should_trim_over_limit(self):
        """Требует обрезки если больше лимита."""
        strategy = LastNMessages(n=5)
        messages = [ChatMessage("user", f"msg{i}") for i in range(7)]
        assert strategy.should_trim(messages) is True

    def test_trim_keeps_last_n(self):
        """Обрезка оставляет N последних сообщений."""
        strategy = LastNMessages(n=3)
        messages = [ChatMessage("user", f"msg{i}") for i in range(5)]

        trimmed = strategy.trim(messages)

        assert len(trimmed) == 3
        assert trimmed[0].content == "msg2"
        assert trimmed[1].content == "msg3"
        assert trimmed[2].content == "msg4"

    def test_trim_no_change_under_limit(self):
        """Обрезка не меняет если меньше лимита."""
        strategy = LastNMessages(n=5)
        messages = [ChatMessage("user", f"msg{i}") for i in range(3)]

        trimmed = strategy.trim(messages)

        assert len(trimmed) == 3
        assert trimmed == messages


class TestTokenBudget:
    """Тесты для стратегии TokenBudget."""

    def test_init_valid(self):
        """Инициализация с валидным бюджетом."""
        strategy = TokenBudget(max_tokens=1000)
        assert strategy.max_tokens == 1000

    def test_init_invalid_zero(self):
        """Ошибка при max_tokens=0."""
        with pytest.raises(ValueError, match="max_tokens должно быть >= 1"):
            TokenBudget(max_tokens=0)

    def test_init_invalid_negative(self):
        """Ошибка при отрицательном бюджете."""
        with pytest.raises(ValueError, match="max_tokens должно быть >= 1"):
            TokenBudget(max_tokens=-100)

    def test_should_trim_under_budget(self):
        """Не требует обрезки если меньше бюджета."""
        strategy = TokenBudget(max_tokens=100)
        messages = [
            ChatMessage("user", "msg1", tokens=20),
            ChatMessage("assistant", "msg2", tokens=30),
        ]
        assert strategy.should_trim(messages) is False

    def test_should_trim_at_budget(self):
        """Не требует обрезки если ровно бюджет."""
        strategy = TokenBudget(max_tokens=100)
        messages = [
            ChatMessage("user", "msg1", tokens=50),
            ChatMessage("assistant", "msg2", tokens=50),
        ]
        assert strategy.should_trim(messages) is False

    def test_should_trim_over_budget(self):
        """Требует обрезки если больше бюджета."""
        strategy = TokenBudget(max_tokens=100)
        messages = [
            ChatMessage("user", "msg1", tokens=60),
            ChatMessage("assistant", "msg2", tokens=60),
        ]
        assert strategy.should_trim(messages) is True

    def test_trim_removes_old_messages(self):
        """Обрезка удаляет старые сообщения."""
        strategy = TokenBudget(max_tokens=100)
        messages = [
            ChatMessage("user", "old1", tokens=40),
            ChatMessage("assistant", "old2", tokens=40),
            ChatMessage("user", "new1", tokens=30),
            ChatMessage("assistant", "new2", tokens=30),
        ]

        trimmed = strategy.trim(messages)

        # Должны остаться последние 2-3 сообщения (30+30+30 = 90 < 100)
        assert len(trimmed) <= 3
        assert sum(m.tokens for m in trimmed) <= 100
        # Последнее сообщение должно быть new2
        assert trimmed[-1].content == "new2"

    def test_trim_no_change_under_budget(self):
        """Обрезка не меняет если меньше бюджета."""
        strategy = TokenBudget(max_tokens=1000)
        messages = [
            ChatMessage("user", "msg1", tokens=100),
            ChatMessage("assistant", "msg2", tokens=100),
        ]

        trimmed = strategy.trim(messages)

        assert len(trimmed) == 2
        assert trimmed == messages

    def test_trim_handles_single_large_message(self):
        """Обрезка справляется с одним большим сообщением."""
        strategy = TokenBudget(max_tokens=50)
        messages = [
            ChatMessage("user", "huge", tokens=100),  # Больше бюджета
        ]

        trimmed = strategy.trim(messages)

        # Не можем удалить последнее сообщение, возвращаем пустой список
        assert len(trimmed) == 0


class TestUnlimited:
    """Тесты для стратегии Unlimited."""

    def test_should_trim_always_false(self):
        """Никогда не требует обрезки."""
        strategy = Unlimited()
        messages = [ChatMessage("user", f"msg{i}") for i in range(1000)]
        assert strategy.should_trim(messages) is False

    def test_trim_no_change(self):
        """Обрезка не меняет список."""
        strategy = Unlimited()
        messages = [ChatMessage("user", f"msg{i}") for i in range(100)]

        trimmed = strategy.trim(messages)

        assert len(trimmed) == 100
        assert trimmed == messages

    def test_trim_empty_list(self):
        """Обрезка работает с пустым списком."""
        strategy = Unlimited()
        trimmed = strategy.trim([])
        assert trimmed == []


class MockLLMProvider:
    """Mock LLM провайдер для тестов AdaptiveWithCompression."""

    def __init__(self, response_text: str = "Summary", output_tokens: int = 50):
        self.response_text = response_text
        self.output_tokens = output_tokens
        self.call_count = 0

    @property
    def model_name(self) -> str:
        return "mock-model"

    def generate(self, prompt: str, **kwargs) -> GenerationResult:
        self.call_count += 1
        return GenerationResult(
            text=self.response_text,
            model="mock-model",
            output_tokens=self.output_tokens,
        )


class TestAdaptiveWithCompression:
    """Тесты для стратегии AdaptiveWithCompression."""

    def make_compressor(
        self, response_text: str = "Summary", output_tokens: int = 50
    ) -> tuple[ContextCompressor, MockLLMProvider]:
        """Создаёт compressor с mock LLM."""
        llm = MockLLMProvider(response_text, output_tokens)
        return ContextCompressor(llm), llm

    def test_init_valid(self):
        """Инициализация с валидными параметрами."""
        compressor, _ = self.make_compressor()
        strategy = AdaptiveWithCompression(
            compressor=compressor,
            threshold_tokens=30000,
            target_tokens=10000,
        )

        assert strategy.threshold == 30000
        assert strategy.target == 10000
        assert strategy.summary is None

    def test_init_invalid_threshold_lte_target(self):
        """Ошибка если threshold <= target."""
        compressor, _ = self.make_compressor()

        with pytest.raises(ValueError, match="threshold_tokens должен быть > target_tokens"):
            AdaptiveWithCompression(
                compressor=compressor,
                threshold_tokens=10000,
                target_tokens=10000,
            )

        with pytest.raises(ValueError, match="threshold_tokens должен быть > target_tokens"):
            AdaptiveWithCompression(
                compressor=compressor,
                threshold_tokens=5000,
                target_tokens=10000,
            )

    def test_init_invalid_target_zero(self):
        """Ошибка если target < 1."""
        compressor, _ = self.make_compressor()

        with pytest.raises(ValueError, match="target_tokens должно быть >= 1"):
            AdaptiveWithCompression(
                compressor=compressor,
                threshold_tokens=30000,
                target_tokens=0,
            )

    def test_should_trim_under_threshold(self):
        """Не требует сжатия если меньше порога."""
        compressor, _ = self.make_compressor()
        strategy = AdaptiveWithCompression(
            compressor=compressor,
            threshold_tokens=1000,
            target_tokens=500,
        )

        messages = [
            ChatMessage("user", "msg1", tokens=200),
            ChatMessage("assistant", "msg2", tokens=300),
        ]

        assert strategy.should_trim(messages) is False

    def test_should_trim_over_threshold(self):
        """Требует сжатия если больше порога."""
        compressor, _ = self.make_compressor()
        strategy = AdaptiveWithCompression(
            compressor=compressor,
            threshold_tokens=1000,
            target_tokens=500,
        )

        messages = [
            ChatMessage("user", "msg1", tokens=600),
            ChatMessage("assistant", "msg2", tokens=600),
        ]

        assert strategy.should_trim(messages) is True

    def test_should_trim_includes_summary_tokens(self):
        """should_trim учитывает токены из summary."""
        compressor, llm = self.make_compressor(output_tokens=400)
        strategy = AdaptiveWithCompression(
            compressor=compressor,
            threshold_tokens=1000,
            target_tokens=200,
        )

        # Первый раз: 600 + 600 = 1200 > 1000 → сжимаем
        messages = [
            ChatMessage("user", "old", tokens=600),
            ChatMessage("assistant", "new", tokens=600),
        ]
        strategy.trim(messages)

        # Теперь есть summary (400 токенов)
        # Новые сообщения: 300 + 300 = 600
        # Всего: 400 + 600 = 1000 = порог → False
        new_messages = [
            ChatMessage("user", "m1", tokens=300),
            ChatMessage("assistant", "m2", tokens=300),
        ]
        assert strategy.should_trim(new_messages) is False

        # Ещё добавим → 400 + 700 = 1100 > 1000 → True
        more_messages = [
            ChatMessage("user", "m1", tokens=300),
            ChatMessage("assistant", "m2", tokens=400),
        ]
        assert strategy.should_trim(more_messages) is True

    def test_trim_separates_to_compress_and_keep(self):
        """trim разделяет сообщения на сжимаемые и сохраняемые."""
        compressor, llm = self.make_compressor(output_tokens=100)
        strategy = AdaptiveWithCompression(
            compressor=compressor,
            threshold_tokens=1000,
            target_tokens=500,
        )

        # Всего 800 токенов, target 500
        # Должны сохранить последние ~500 токенов
        messages = [
            ChatMessage("user", "old1", tokens=200),
            ChatMessage("assistant", "old2", tokens=200),
            ChatMessage("user", "new1", tokens=200),
            ChatMessage("assistant", "new2", tokens=200),
        ]

        trimmed = strategy.trim(messages)

        # Должны остаться последние 2-3 сообщения
        assert len(trimmed) >= 2
        assert trimmed[-1].content == "new2"
        assert sum(m.tokens for m in trimmed) <= 500

        # LLM должен быть вызван для сжатия
        assert llm.call_count == 1

    def test_trim_creates_summary(self):
        """trim создаёт summary из сжатых сообщений."""
        compressor, llm = self.make_compressor(
            response_text="Compressed history",
            output_tokens=50,
        )
        strategy = AdaptiveWithCompression(
            compressor=compressor,
            threshold_tokens=500,
            target_tokens=100,
        )

        messages = [
            ChatMessage("user", "old", tokens=300),
            ChatMessage("assistant", "new", tokens=100),
        ]

        strategy.trim(messages)

        assert strategy.summary is not None
        assert strategy.summary.role == "system"
        assert "Compressed history" in strategy.summary.content
        assert strategy.summary.tokens == 50

    def test_trim_includes_old_summary(self):
        """trim включает старый summary в сжатие."""
        compressor, llm = self.make_compressor(output_tokens=50)
        strategy = AdaptiveWithCompression(
            compressor=compressor,
            threshold_tokens=300,
            target_tokens=100,
        )

        # Первое сжатие
        messages1 = [
            ChatMessage("user", "first", tokens=200),
            ChatMessage("assistant", "second", tokens=100),
        ]
        strategy.trim(messages1)
        first_summary = strategy.summary

        # Второе сжатие — должен включить первый summary
        messages2 = [
            ChatMessage("user", "third", tokens=200),
            ChatMessage("assistant", "fourth", tokens=100),
        ]
        strategy.trim(messages2)

        # LLM вызван 2 раза
        assert llm.call_count == 2

    def test_trim_no_compression_if_all_fits(self):
        """trim не сжимает если всё умещается в target."""
        compressor, llm = self.make_compressor()
        strategy = AdaptiveWithCompression(
            compressor=compressor,
            threshold_tokens=1000,
            target_tokens=500,
        )

        messages = [
            ChatMessage("user", "small", tokens=100),
            ChatMessage("assistant", "tiny", tokens=100),
        ]

        trimmed = strategy.trim(messages)

        # Всё умещается, сжатие не нужно
        assert len(trimmed) == 2
        assert llm.call_count == 0
        assert strategy.summary is None

    def test_get_full_context_without_summary(self):
        """get_full_context без summary возвращает только messages."""
        compressor, _ = self.make_compressor()
        strategy = AdaptiveWithCompression(
            compressor=compressor,
            threshold_tokens=1000,
            target_tokens=500,
        )

        messages = [ChatMessage("user", "test", tokens=100)]
        result = strategy.get_full_context(messages)

        assert result == messages

    def test_get_full_context_with_summary(self):
        """get_full_context с summary добавляет его в начало."""
        compressor, llm = self.make_compressor(
            response_text="Previous context",
            output_tokens=50,
        )
        strategy = AdaptiveWithCompression(
            compressor=compressor,
            threshold_tokens=300,
            target_tokens=100,
        )

        # Сжимаем чтобы создать summary
        messages = [
            ChatMessage("user", "old", tokens=200),
            ChatMessage("assistant", "new", tokens=100),
        ]
        kept = strategy.trim(messages)

        # Получаем полный контекст
        full = strategy.get_full_context(kept)

        assert len(full) > len(kept)
        assert full[0].role == "system"
        assert "Previous context" in full[0].content

    def test_summary_property(self):
        """Проверка property summary."""
        compressor, _ = self.make_compressor()
        strategy = AdaptiveWithCompression(
            compressor=compressor,
            threshold_tokens=1000,
            target_tokens=500,
        )

        # Изначально None
        assert strategy.summary is None

        # После внутренней установки
        strategy._summary = ChatMessage("system", "test", tokens=10)
        assert strategy.summary is not None
        assert strategy.summary.content == "test"
