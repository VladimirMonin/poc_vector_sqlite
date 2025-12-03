"""Тесты для ChatHistoryManager."""

import pytest

from semantic_core.interfaces.chat_history import ChatMessage
from semantic_core.core.context.strategies import LastNMessages, TokenBudget, Unlimited
from semantic_core.core.context.manager import ChatHistoryManager


class TestChatHistoryManager:
    """Тесты для ChatHistoryManager."""

    def test_init(self):
        """Инициализация с стратегией."""
        strategy = LastNMessages(n=10)
        manager = ChatHistoryManager(strategy)

        assert manager.strategy == strategy
        assert len(manager) == 0
        assert manager.is_empty

    def test_add_user_message(self):
        """Добавление сообщения пользователя."""
        manager = ChatHistoryManager(Unlimited())
        manager.add_user("Привет!", tokens=10)

        history = manager.get_history()
        assert len(history) == 1
        assert history[0].role == "user"
        assert history[0].content == "Привет!"
        assert history[0].tokens == 10

    def test_add_assistant_message(self):
        """Добавление сообщения ассистента."""
        manager = ChatHistoryManager(Unlimited())
        manager.add_assistant("Здравствуйте!", tokens=15)

        history = manager.get_history()
        assert len(history) == 1
        assert history[0].role == "assistant"
        assert history[0].content == "Здравствуйте!"

    def test_add_system_message(self):
        """Добавление системного сообщения."""
        manager = ChatHistoryManager(Unlimited())
        manager.add_system("Ты помощник.", tokens=5)

        history = manager.get_history()
        assert len(history) == 1
        assert history[0].role == "system"

    def test_add_generic(self):
        """Добавление через общий метод add()."""
        manager = ChatHistoryManager(Unlimited())
        manager.add("user", "Тест", tokens=5)

        history = manager.get_history()
        assert history[0].role == "user"
        assert history[0].content == "Тест"

    def test_get_history_returns_copy(self):
        """get_history() возвращает копию."""
        manager = ChatHistoryManager(Unlimited())
        manager.add_user("msg1")

        history1 = manager.get_history()
        history2 = manager.get_history()

        assert history1 == history2
        assert history1 is not history2  # Разные объекты

    def test_get_messages_for_llm(self):
        """Формат для LLM API."""
        manager = ChatHistoryManager(Unlimited())
        manager.add_user("Привет")
        manager.add_assistant("Здравствуйте")

        messages = manager.get_messages_for_llm()

        assert messages == [
            {"role": "user", "content": "Привет"},
            {"role": "assistant", "content": "Здравствуйте"},
        ]

    def test_clear(self):
        """Очистка истории."""
        manager = ChatHistoryManager(Unlimited())
        manager.add_user("msg1")
        manager.add_assistant("msg2")

        manager.clear()

        assert len(manager) == 0
        assert manager.is_empty

    def test_total_tokens(self):
        """Подсчёт общего количества токенов."""
        manager = ChatHistoryManager(Unlimited())
        manager.add_user("msg1", tokens=10)
        manager.add_assistant("msg2", tokens=20)
        manager.add_user("msg3", tokens=15)

        assert manager.total_tokens() == 45

    def test_len(self):
        """Количество сообщений."""
        manager = ChatHistoryManager(Unlimited())
        assert len(manager) == 0

        manager.add_user("msg1")
        assert len(manager) == 1

        manager.add_assistant("msg2")
        assert len(manager) == 2

    def test_is_empty(self):
        """Проверка на пустоту."""
        manager = ChatHistoryManager(Unlimited())
        assert manager.is_empty is True

        manager.add_user("msg")
        assert manager.is_empty is False


class TestChatHistoryManagerAutoTrim:
    """Тесты автоматического тримминга."""

    def test_auto_trim_last_n_messages(self):
        """Автотримминг по количеству сообщений."""
        manager = ChatHistoryManager(LastNMessages(n=3))

        for i in range(5):
            manager.add_user(f"msg{i}")

        history = manager.get_history()
        assert len(history) == 3
        assert history[0].content == "msg2"
        assert history[1].content == "msg3"
        assert history[2].content == "msg4"

    def test_auto_trim_token_budget(self):
        """Автотримминг по токенам."""
        manager = ChatHistoryManager(TokenBudget(max_tokens=50))

        # Добавляем сообщения по 20 токенов
        for i in range(5):
            manager.add_user(f"msg{i}", tokens=20)

        # Должны остаться последние 2 (40 токенов)
        history = manager.get_history()
        total = sum(m.tokens for m in history)
        assert total <= 50

    def test_no_auto_trim_unlimited(self):
        """Без автотримминга для Unlimited."""
        manager = ChatHistoryManager(Unlimited())

        for i in range(100):
            manager.add_user(f"msg{i}")

        assert len(manager) == 100

    def test_auto_trim_preserves_order(self):
        """Автотримминг сохраняет порядок (новые в конце)."""
        manager = ChatHistoryManager(LastNMessages(n=2))

        manager.add_user("first")
        manager.add_assistant("second")
        manager.add_user("third")  # Триггерит тримминг

        history = manager.get_history()
        assert len(history) == 2
        assert history[0].content == "second"
        assert history[1].content == "third"


class TestChatHistoryManagerConversation:
    """Тесты реального диалога."""

    def test_conversation_flow(self):
        """Симуляция реального диалога."""
        manager = ChatHistoryManager(LastNMessages(n=10))

        # Диалог
        manager.add_user("Привет!", tokens=5)
        manager.add_assistant("Здравствуйте! Чем могу помочь?", tokens=15)
        manager.add_user("Что такое RAG?", tokens=10)
        manager.add_assistant("RAG — это Retrieval-Augmented Generation...", tokens=50)

        assert len(manager) == 4
        assert manager.total_tokens() == 80

        # Формат для LLM
        llm_messages = manager.get_messages_for_llm()
        assert len(llm_messages) == 4
        assert llm_messages[0]["role"] == "user"
        assert llm_messages[1]["role"] == "assistant"

    def test_conversation_with_system_prompt(self):
        """Диалог с системным промптом."""
        manager = ChatHistoryManager(LastNMessages(n=10))

        manager.add_system("Ты полезный ассистент.")
        manager.add_user("Привет!")
        manager.add_assistant("Здравствуйте!")

        history = manager.get_history()
        assert history[0].role == "system"
        assert history[1].role == "user"
        assert history[2].role == "assistant"
