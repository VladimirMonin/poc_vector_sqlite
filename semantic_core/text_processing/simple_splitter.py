"""
Простой сплиттер текста с умной нарезкой по переносам строк.

Алгоритм:
1. Режет текст на куски примерно по chunk_size символов
2. Ищет перенос строки в окне ±threshold от целевой позиции
3. Если перенос найден — режет по нему (чисто)
4. Если нет — режет жестко по позиции (hard cut)
5. Создает перекрытие (overlap) между соседними чанками

Это "тупой как пробка, но надежный" подход (KISS).
Не парсит Markdown, не понимает структуру — просто режет по символам.
"""

from typing import List
from .base import TextSplitter, Chunk


class SimpleTextSplitter(TextSplitter):
    """
    Сплиттер с фиксированным размером и перекрытием.

    Attributes:
        chunk_size: Целевой размер одного чанка в символах
        overlap: Размер перекрытия между соседними чанками
        threshold: Радиус поиска переноса строки от целевой позиции
    """

    def __init__(
        self, chunk_size: int = 1000, overlap: int = 200, threshold: int = 100
    ):
        """
        Инициализирует сплиттер с параметрами нарезки.

        Args:
            chunk_size: Целевой размер куска (по умолчанию 1000 символов)
            overlap: Размер перекрытия между чанками (по умолчанию 200)
            threshold: Окно поиска переноса строки ±threshold от target
                      (по умолчанию 100, т.е. ищем в диапазоне 200 символов)

        Raises:
            ValueError: Если параметры некорректны
        """
        if chunk_size <= 0:
            raise ValueError(f"chunk_size должен быть > 0, получено: {chunk_size}")
        if overlap < 0:
            raise ValueError(f"overlap не может быть отрицательным: {overlap}")
        if overlap >= chunk_size:
            raise ValueError(
                f"overlap ({overlap}) должен быть меньше chunk_size ({chunk_size})"
            )
        if threshold < 0:
            raise ValueError(f"threshold не может быть отрицательным: {threshold}")

        self.chunk_size = chunk_size
        self.overlap = overlap
        self.threshold = threshold

    def split_text(self, text: str) -> List[Chunk]:
        """
        Разбивает текст на чанки с умной нарезкой по переносам.

        Args:
            text: Исходный текст для нарезки

        Returns:
            Список Chunk с индексами и текстом

        Example:
            >>> splitter = SimpleTextSplitter(chunk_size=100, overlap=20)
            >>> chunks = splitter.split_text("Длинный текст...")
            >>> len(chunks)
            5
            >>> chunks[0].index
            0
        """
        if not text:
            return []

        chunks = []
        start = 0
        text_len = len(text)
        chunk_idx = 0

        while start < text_len:
            # 1. Вычисляем идеальную позицию разреза
            target_end = start + self.chunk_size

            # Если это последний чанк (дошли до конца)
            if target_end >= text_len:
                chunk_content = text[start:]
                chunks.append(
                    Chunk(
                        text=chunk_content,
                        index=chunk_idx,
                        metadata={"start": start, "end": text_len, "is_last": True},
                    )
                )
                break

            # 2. Ищем "умный" разрез по переносу строки
            # Окно поиска: [target_end - threshold, target_end + threshold]
            search_start = max(start, target_end - self.threshold)
            search_end = min(text_len, target_end + self.threshold)

            search_window = text[search_start:search_end]

            # Ищем ПОСЛЕДНИЙ перенос строки в окне (rfind = reverse find)
            # Нам выгодно резать как можно позже (ближе к target_end)
            newline_pos = search_window.rfind("\n")

            if newline_pos != -1:
                # Нашли перенос! Режем после него
                cut_point = search_start + newline_pos + 1  # +1 включаем \n в чанк
                cut_type = "newline"
            else:
                # Перенос не найден — жесткий разрез по target_end
                cut_point = target_end
                cut_type = "hard"

            # 3. Создаем чанк
            chunk_content = text[start:cut_point]
            chunks.append(
                Chunk(
                    text=chunk_content,
                    index=chunk_idx,
                    metadata={
                        "start": start,
                        "end": cut_point,
                        "cut_type": cut_type,
                        "is_last": False,
                    },
                )
            )

            # 4. Вычисляем начало следующего чанка с учетом overlap
            # Важно: не уходим назад за границу текущего чанка
            next_start = max(start + 1, cut_point - self.overlap)

            start = next_start
            chunk_idx += 1

        return chunks

    def __repr__(self) -> str:
        return (
            f"SimpleTextSplitter("
            f"chunk_size={self.chunk_size}, "
            f"overlap={self.overlap}, "
            f"threshold={self.threshold})"
        )
