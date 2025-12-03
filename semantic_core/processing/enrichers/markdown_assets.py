"""Обогащение медиа-чанков контекстом из Markdown документа.

Классы:
    MediaContext: DTO с извлечённым контекстом для Vision API.
    MarkdownAssetEnricher: Извлекает контекст для IMAGE_REF чанков.
"""

from dataclasses import dataclass, field
from typing import Optional

from semantic_core.domain import Chunk, ChunkType


@dataclass
class MediaContext:
    """Контекст для медиа-ресурса из Markdown.

    Собирает информацию о том, где и зачем изображение
    появилось в документе.

    Attributes:
        breadcrumbs: Иерархия заголовков ("Setup > Nginx > Configuration").
        surrounding_text: Текст до и после картинки.
        alt_text: Alt-текст из Markdown синтаксиса.
        title: Title из Markdown синтаксиса (если есть).
        role: Семантическая роль изображения.
    """

    breadcrumbs: str = ""
    surrounding_text: str = ""
    alt_text: str = ""
    title: str = ""
    role: str = "Illustration embedded in document"

    def format_for_vision(self) -> str:
        """Форматирует контекст для промпта Vision API.

        Returns:
            Структурированный текст для context_text параметра.
        """
        parts = []

        if self.breadcrumbs:
            parts.append(f"Document section: {self.breadcrumbs}")

        if self.alt_text:
            parts.append(f"Image caption: {self.alt_text}")

        if self.title:
            parts.append(f"Title: {self.title}")

        if self.surrounding_text:
            parts.append(f"Surrounding text:\n{self.surrounding_text}")

        parts.append(f"Role: {self.role}")

        return "\n".join(parts)


class MarkdownAssetEnricher:
    """Извлекает контекст для медиа-чанков из Markdown.

    Находит текст вокруг изображения и формирует контекст
    для Vision API, чтобы улучшить качество описания.

    Атрибуты:
        context_window: Количество символов до/после для surrounding_text.
        skip_code_chunks: Пропускать ли CODE чанки как соседей.

    Пример:
        >>> enricher = MarkdownAssetEnricher(context_window=200)
        >>> context = enricher.get_context(image_chunk, all_chunks)
        >>> print(context.format_for_vision())
    """

    def __init__(
        self,
        context_window: int = 200,
        skip_code_chunks: bool = True,
    ):
        """Инициализация enricher.

        Args:
            context_window: Максимум символов до/после картинки.
            skip_code_chunks: Пропускать CODE чанки при поиске соседей.
        """
        self.context_window = context_window
        self.skip_code_chunks = skip_code_chunks

    def get_context(
        self,
        media_chunk: Chunk,
        all_chunks: list[Chunk],
    ) -> MediaContext:
        """Извлекает контекст для медиа-чанка.

        Алгоритм:
        1. Берёт headers из metadata → breadcrumbs
        2. Находит предыдущий TEXT-чанк → последние N символов
        3. Находит следующий TEXT-чанк → первые N символов
        4. Извлекает alt и title из metadata

        Args:
            media_chunk: IMAGE_REF чанк для обогащения.
            all_chunks: Все чанки документа (для поиска соседей).

        Returns:
            MediaContext с извлечённым контекстом.
        """
        # 1. Формируем breadcrumbs из headers
        headers = media_chunk.metadata.get("headers", [])
        breadcrumbs = " > ".join(headers) if headers else ""

        # 2. Находим позицию чанка
        chunk_index = media_chunk.chunk_index

        # 3. Ищем текст ДО (предыдущий текстовый чанк)
        before_text = self._find_neighbor_text(
            all_chunks,
            chunk_index,
            direction="before",
        )

        # 4. Ищем текст ПОСЛЕ (следующий текстовый чанк)
        after_text = self._find_neighbor_text(
            all_chunks,
            chunk_index,
            direction="after",
        )

        # 5. Формируем surrounding_text
        surrounding_parts = []
        if before_text:
            surrounding_parts.append(f"[Before]: ...{before_text}")
        if after_text:
            surrounding_parts.append(f"[After]: {after_text}...")

        surrounding_text = "\n".join(surrounding_parts)

        # 6. Извлекаем alt и title
        alt_text = media_chunk.metadata.get("alt", "")
        title = media_chunk.metadata.get("title", "")

        return MediaContext(
            breadcrumbs=breadcrumbs,
            surrounding_text=surrounding_text,
            alt_text=alt_text,
            title=title,
        )

    def _find_neighbor_text(
        self,
        all_chunks: list[Chunk],
        current_index: int,
        direction: str,
    ) -> str:
        """Находит текст из соседнего TEXT чанка.

        Args:
            all_chunks: Все чанки документа.
            current_index: Индекс текущего чанка.
            direction: 'before' или 'after'.

        Returns:
            Фрагмент текста (обрезанный до context_window).
        """
        # Определяем диапазон поиска
        if direction == "before":
            candidates = [c for c in all_chunks if c.chunk_index < current_index]
            candidates.sort(key=lambda c: c.chunk_index, reverse=True)
        else:
            candidates = [c for c in all_chunks if c.chunk_index > current_index]
            candidates.sort(key=lambda c: c.chunk_index)

        # Ищем первый подходящий TEXT чанк
        for chunk in candidates:
            # Пропускаем не-TEXT чанки
            if chunk.chunk_type != ChunkType.TEXT:
                if self.skip_code_chunks:
                    continue
                # Если не пропускаем код — всё равно берём только TEXT
                continue

            text = chunk.content.strip()
            if not text:
                continue

            # Обрезаем до нужного размера
            if direction == "before":
                # Берём последние N символов
                return text[-self.context_window :]
            else:
                # Берём первые N символов
                return text[: self.context_window]

        return ""
