"""Компрессор контекста чата.

Классы:
    ContextCompressor
        Сжимает историю чата через LLM summarization.
"""

from semantic_core.interfaces.chat_history import ChatMessage
from semantic_core.interfaces.llm import BaseLLMProvider
from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)


class ContextCompressor:
    """Сжимает историю чата через LLM summarization.

    Использует LLM для создания краткого резюме истории,
    сохраняя ключевые факты и контекст.

    Attributes:
        llm: Провайдер LLM для генерации summary.

    Example:
        >>> compressor = ContextCompressor(llm_provider)
        >>> messages = [
        ...     ChatMessage("user", "Расскажи о Python"),
        ...     ChatMessage("assistant", "Python — это язык..."),
        ... ]
        >>> summary = compressor.compress(messages)
        >>> print(summary.content)  # [Сжатая история]
    """

    COMPRESS_PROMPT = """You are a conversation summarizer. Compress the following chat history into a concise summary.

RULES:
1. Keep all key facts, decisions, and important context
2. Preserve technical details, code snippets, and specific values
3. Be concise but don't lose critical information
4. Write in the same language as the conversation
5. Format as 2-3 paragraphs maximum

CONVERSATION:
{history}

SUMMARY:"""

    def __init__(self, llm: BaseLLMProvider, temperature: float = 0.3):
        """Инициализация компрессора.

        Args:
            llm: Провайдер LLM для генерации summary.
            temperature: Температура генерации (низкая для детерминированности).
        """
        self.llm = llm
        self.temperature = temperature

        logger.debug(
            "ContextCompressor initialized",
            model=llm.model_name,
            temperature=temperature,
        )

    def compress(self, messages: list[ChatMessage]) -> ChatMessage:
        """Сжимает список сообщений в одно summary-сообщение.

        Args:
            messages: Список сообщений для сжатия.

        Returns:
            ChatMessage с ролью 'system' содержащее summary.

        Raises:
            RuntimeError: Если LLM вернул ошибку.
        """
        if not messages:
            logger.warning("compress() called with empty messages")
            return ChatMessage(
                role="system",
                content="[Empty conversation summary]",
                tokens=5,
            )

        # Формируем текст истории
        history_text = self._format_history(messages)
        input_tokens = sum(m.tokens for m in messages)

        logger.debug(
            "Compressing history",
            message_count=len(messages),
            input_tokens=input_tokens,
        )

        # Генерируем summary через LLM
        result = self.llm.generate(
            prompt=self.COMPRESS_PROMPT.format(history=history_text),
            temperature=self.temperature,
        )

        summary_message = ChatMessage(
            role="system",
            content=f"[Previous conversation summary]\n{result.text}",
            tokens=result.output_tokens or self._estimate_tokens(result.text),
        )

        logger.info(
            "History compressed",
            input_messages=len(messages),
            input_tokens=input_tokens,
            output_tokens=summary_message.tokens,
            compression_ratio=round(input_tokens / max(summary_message.tokens, 1), 1),
        )

        return summary_message

    def _format_history(self, messages: list[ChatMessage]) -> str:
        """Форматирует историю для промпта.

        Args:
            messages: Список сообщений.

        Returns:
            Отформатированная строка.
        """
        lines = []
        for msg in messages:
            role_label = msg.role.upper()
            lines.append(f"{role_label}: {msg.content}")
        return "\n\n".join(lines)

    def _estimate_tokens(self, text: str) -> int:
        """Грубая оценка токенов (4 символа ≈ 1 токен).

        Args:
            text: Текст для оценки.

        Returns:
            Приблизительное количество токенов.
        """
        return len(text) // 4


__all__ = ["ContextCompressor"]
