"""Простой сплиттер текста с умной нарезкой.

Классы:
    SimpleSplitter
        Реализация BaseSplitter с нарезкой по размеру.
"""

from semantic_core.interfaces import BaseSplitter
from semantic_core.domain import Document, Chunk


class SimpleSplitter(BaseSplitter):
    """Сплиттер с фиксированным размером и перекрытием.

    Алгоритм:
    1. Режет текст на куски ~chunk_size символов.
    2. Ищет перенос строки в окне ±threshold.
    3. Создаёт перекрытие между чанками.

    Attributes:
        chunk_size: Целевой размер чанка в символах.
        overlap: Размер перекрытия между чанками.
        threshold: Радиус поиска переноса строки.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        overlap: int = 200,
        threshold: int = 100,
    ):
        """Инициализация сплиттера.

        Args:
            chunk_size: Целевой размер куска (по умолчанию 1000).
            overlap: Размер перекрытия (по умолчанию 200).
            threshold: Окно поиска переноса (по умолчанию 100).

        Raises:
            ValueError: Если параметры некорректны.
        """
        if chunk_size <= 0:
            raise ValueError(f"chunk_size должен быть > 0: {chunk_size}")
        if overlap < 0:
            raise ValueError(f"overlap не может быть отрицательным: {overlap}")
        if overlap >= chunk_size:
            raise ValueError(
                f"overlap ({overlap}) должен быть < chunk_size ({chunk_size})"
            )
        if threshold < 0:
            raise ValueError(f"threshold не может быть отрицательным: {threshold}")

        self.chunk_size = chunk_size
        self.overlap = overlap
        self.threshold = threshold

    def split(self, document: Document) -> list[Chunk]:
        """Разбивает документ на чанки.

        Args:
            document: Исходный документ.

        Returns:
            Список чанков БЕЗ векторов (embedding=None).

        Raises:
            ValueError: Если document.content пустой.
        """
        text = document.content

        if not text:
            raise ValueError("Контент документа не может быть пустым")

        chunks = []
        start = 0
        text_len = len(text)
        chunk_idx = 0

        while start < text_len:
            target_end = start + self.chunk_size

            if target_end >= text_len:
                chunk_content = text[start:]
                chunks.append(
                    Chunk(
                        content=chunk_content,
                        chunk_index=chunk_idx,
                        parent_doc_id=document.id,
                        metadata={
                            "start": start,
                            "end": text_len,
                            "is_last": True,
                        },
                    )
                )
                break

            search_start = max(start, target_end - self.threshold)
            search_end = min(text_len, target_end + self.threshold)
            search_window = text[search_start:search_end]

            newline_pos = search_window.rfind("\n")

            if newline_pos != -1:
                cut_point = search_start + newline_pos + 1
                cut_type = "newline"
            else:
                cut_point = target_end
                cut_type = "hard"

            chunk_content = text[start:cut_point]
            chunks.append(
                Chunk(
                    content=chunk_content,
                    chunk_index=chunk_idx,
                    parent_doc_id=document.id,
                    metadata={
                        "start": start,
                        "end": cut_point,
                        "cut_type": cut_type,
                        "is_last": False,
                    },
                )
            )

            next_start = max(start + 1, cut_point - self.overlap)
            start = next_start
            chunk_idx += 1

        return chunks

    def __repr__(self) -> str:
        return (
            f"SimpleSplitter(chunk_size={self.chunk_size}, "
            f"overlap={self.overlap}, threshold={self.threshold})"
        )
