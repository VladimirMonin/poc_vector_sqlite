"""Базовая стратегия формирования контекста.

Классы:
    BasicContextStrategy
        Простая реализация BaseContextStrategy.
"""

from semantic_core.interfaces import BaseContextStrategy
from semantic_core.domain import Document, Chunk


class BasicContextStrategy(BaseContextStrategy):
    """Базовая стратегия добавления контекста к чанкам.

    Формирует текст для векторизации:
    - Заголовок документа (если есть).
    - Метаданные (category, tags и т.д.).
    - Текст чанка.
    """

    def form_vector_text(self, chunk: Chunk, document: Document) -> str:
        """Формирует текст для генерации эмбеддинга.

        Args:
            chunk: Чанк для обогащения.
            document: Родительский документ.

        Returns:
            Строка вида: "Заголовок: ...\nКатегория: ...\n\n{chunk.content}"
        """
        parts = []

        # Добавляем заголовок
        title = document.metadata.get("title")
        if title:
            parts.append(f"Заголовок: {title}")

        # Добавляем категорию
        category = document.metadata.get("category")
        if category:
            parts.append(f"Категория: {category}")

        # Добавляем теги
        tags = document.metadata.get("tags", [])
        if tags:
            tags_str = ", ".join(tags)
            parts.append(f"Теги: {tags_str}")

        # Объединяем контекст с текстом чанка
        if parts:
            context_header = "\n".join(parts)
            return f"{context_header}\n\n{chunk.content}"
        else:
            return chunk.content
