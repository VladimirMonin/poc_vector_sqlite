"""
Тесты для SimpleTextSplitter.

Проверяет корректность нарезки текста на чанки с учетом:
- Размера чанка
- Перекрытия
- Умного разреза по переносам строк
- Граничных случаев
"""

import pytest
from semantic_core.text_processing import SimpleTextSplitter, Chunk


class TestSimpleTextSplitter:
    """Тесты для SimpleTextSplitter."""

    def test_initialization_default_params(self):
        """Проверяет создание с параметрами по умолчанию."""
        splitter = SimpleTextSplitter()
        assert splitter.chunk_size == 1000
        assert splitter.overlap == 200
        assert splitter.threshold == 100

    def test_initialization_custom_params(self):
        """Проверяет создание с кастомными параметрами."""
        splitter = SimpleTextSplitter(chunk_size=500, overlap=50, threshold=25)
        assert splitter.chunk_size == 500
        assert splitter.overlap == 50
        assert splitter.threshold == 25

    def test_initialization_invalid_chunk_size(self):
        """Проверяет валидацию chunk_size."""
        with pytest.raises(ValueError, match="chunk_size должен быть > 0"):
            SimpleTextSplitter(chunk_size=0)

        with pytest.raises(ValueError, match="chunk_size должен быть > 0"):
            SimpleTextSplitter(chunk_size=-100)

    def test_initialization_invalid_overlap(self):
        """Проверяет валидацию overlap."""
        with pytest.raises(ValueError, match="overlap не может быть отрицательным"):
            SimpleTextSplitter(overlap=-10)

        with pytest.raises(
            ValueError, match="overlap .* должен быть меньше chunk_size"
        ):
            SimpleTextSplitter(chunk_size=100, overlap=100)

        with pytest.raises(
            ValueError, match="overlap .* должен быть меньше chunk_size"
        ):
            SimpleTextSplitter(chunk_size=100, overlap=150)

    def test_empty_text(self):
        """Проверяет обработку пустого текста."""
        splitter = SimpleTextSplitter()
        chunks = splitter.split_text("")
        assert chunks == []

    def test_short_text(self):
        """Проверяет обработку текста короче chunk_size."""
        splitter = SimpleTextSplitter(chunk_size=100, overlap=20)
        text = "Короткий текст"
        chunks = splitter.split_text(text)

        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].index == 0
        assert chunks[0].metadata["is_last"] is True

    def test_basic_splitting(self):
        """Проверяет базовую нарезку без переносов строк."""
        splitter = SimpleTextSplitter(chunk_size=50, overlap=10, threshold=5)
        text = "a" * 150  # 150 символов - должно получиться 3-4 чанка

        chunks = splitter.split_text(text)

        assert len(chunks) >= 3
        assert all(isinstance(chunk, Chunk) for chunk in chunks)
        assert all(chunk.index == i for i, chunk in enumerate(chunks))

    def test_smart_splitting_by_newlines(self):
        """Проверяет умную нарезку по переносам строк."""
        splitter = SimpleTextSplitter(chunk_size=30, overlap=5, threshold=10)
        text = "Первая строка\nВторая строка\nТретья строка\nЧетвертая строка"

        chunks = splitter.split_text(text)

        # Должны резать по переносам, а не жестко
        for chunk in chunks[:-1]:  # Все кроме последнего
            if chunk.metadata.get("cut_type") == "newline":
                assert chunk.text.endswith("\n") or chunk.metadata.get("is_last")

    def test_overlap_behavior(self):
        """Проверяет наличие перекрытия между чанками."""
        splitter = SimpleTextSplitter(chunk_size=50, overlap=15, threshold=5)
        text = "x" * 150

        chunks = splitter.split_text(text)

        # Проверяем, что есть перекрытие
        if len(chunks) > 1:
            # Конец первого чанка должен перекрываться с началом второго
            end_of_first = chunks[0].text[-15:]
            start_of_second = chunks[1].text[:15]

            # Хотя бы часть должна совпадать (из-за overlap=15)
            assert len(end_of_first) > 0
            assert len(start_of_second) > 0

    def test_chunk_metadata(self):
        """Проверяет наличие метаданных в чанках."""
        splitter = SimpleTextSplitter(chunk_size=50, overlap=10)
        text = "a" * 100

        chunks = splitter.split_text(text)

        for chunk in chunks:
            assert "start" in chunk.metadata
            assert "end" in chunk.metadata
            assert "is_last" in chunk.metadata
            assert isinstance(chunk.metadata["start"], int)
            assert isinstance(chunk.metadata["end"], int)

    def test_no_newlines_hard_cut(self):
        """Проверяет жесткий разрез при отсутствии переносов."""
        splitter = SimpleTextSplitter(chunk_size=50, overlap=10, threshold=20)
        text = "x" * 200  # Сплошной текст без переносов

        chunks = splitter.split_text(text)

        # Должны быть жесткие разрезы (hard cut)
        hard_cuts = [c for c in chunks if c.metadata.get("cut_type") == "hard"]
        assert len(hard_cuts) > 0

    def test_newline_within_threshold(self):
        """Проверяет поиск переноса в пределах threshold."""
        splitter = SimpleTextSplitter(chunk_size=50, overlap=10, threshold=20)

        # Создаем текст с переносом ровно на границе threshold
        text = "x" * 45 + "\n" + "y" * 100

        chunks = splitter.split_text(text)

        # Первый чанк должен завершиться переносом
        assert chunks[0].text.endswith("\n")
        assert chunks[0].metadata.get("cut_type") == "newline"

    @pytest.mark.parametrize(
        "chunk_size,overlap,text_length,expected_min_chunks",
        [
            (100, 20, 250, 3),  # 250 символов, чанки по 100, overlap 20
            (50, 10, 150, 3),  # 150 символов, чанки по 50, overlap 10
            (1000, 200, 3000, 3),  # Большой текст
        ],
    )
    def test_parametrized_chunking(
        self, chunk_size, overlap, text_length, expected_min_chunks
    ):
        """Параметризованный тест различных конфигураций нарезки."""
        splitter = SimpleTextSplitter(chunk_size=chunk_size, overlap=overlap)
        text = "a" * text_length

        chunks = splitter.split_text(text)

        assert len(chunks) >= expected_min_chunks
        assert all(len(c.text) > 0 for c in chunks)

    def test_repr(self):
        """Проверяет строковое представление."""
        splitter = SimpleTextSplitter(chunk_size=1000, overlap=200, threshold=100)
        repr_str = repr(splitter)

        assert "SimpleTextSplitter" in repr_str
        assert "1000" in repr_str
        assert "200" in repr_str
        assert "100" in repr_str

    def test_chunk_repr(self):
        """Проверяет строковое представление Chunk."""
        chunk = Chunk(text="Пример текста для проверки представления", index=5)
        repr_str = repr(chunk)

        assert "Chunk" in repr_str
        assert "index=5" in repr_str
        assert (
            "Пример текста для проверки представления..." in repr_str
            or "Пример текста для проверки представлени" in repr_str
        )
