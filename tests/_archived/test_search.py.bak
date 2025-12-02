"""
Тесты для Parent-Child поиска.

Проверяет корректность работы поиска по чанкам:
- Дедупликация результатов (уникальные документы)
- Агрегация по MIN(distance)
- Векторный, полнотекстовый и гибридный поиск
"""

import pytest

from semantic_core import (
    vector_search_chunks,
    fulltext_search_parents,
    hybrid_search_rrf,
    save_note_with_chunks,
    EmbeddingGenerator,
    SimpleTextSplitter,
)
from domain.models import Note, NoteChunk, Category


class TestVectorSearchChunks:
    """Тесты векторного поиска по чанкам."""

    def test_returns_unique_notes(
        self, test_db, sample_category, embedding_generator, text_splitter, long_text
    ):
        """Проверяет, что возвращаются уникальные документы без дубликатов."""
        # Создаем документ с несколькими чанками
        note = save_note_with_chunks(
            note_model=Note,
            chunk_model=NoteChunk,
            note_data={
                "title": "Python Guide",
                "content": long_text,
                "category": sample_category,
            },
            splitter=text_splitter,
            generator=embedding_generator,
        )

        # Проверяем, что создались чанки
        assert note.chunks.count() > 1, "Должно быть несколько чанков"

        # Выполняем поиск
        results = vector_search_chunks(
            parent_model=Note,
            chunk_model=NoteChunk,
            query="Python программирование",
            limit=10,
            generator=embedding_generator,
        )

        # Проверяем уникальность
        note_ids = [note.id for note, _ in results]
        assert len(note_ids) == len(set(note_ids)), (
            "Все документы должны быть уникальными"
        )

        # Проверяем, что наш документ найден
        assert any(n.id == note.id for n, _ in results), (
            "Созданный документ должен быть найден"
        )

    def test_min_distance_aggregation(
        self, test_db, sample_category, embedding_generator, text_splitter
    ):
        """Проверяет, что выбирается MIN(distance) среди всех чанков."""
        # Создаем два документа
        note1 = save_note_with_chunks(
            note_model=Note,
            chunk_model=NoteChunk,
            note_data={
                "title": "Python Loops",
                "content": "For loop in Python. " * 100,  # Релевантный текст
                "category": sample_category,
            },
            splitter=text_splitter,
            generator=embedding_generator,
        )

        note2 = save_note_with_chunks(
            note_model=Note,
            chunk_model=NoteChunk,
            note_data={
                "title": "JavaScript Arrays",
                "content": "JavaScript array methods. " * 100,  # Нерелевантный
                "category": sample_category,
            },
            splitter=text_splitter,
            generator=embedding_generator,
        )

        # Поиск по Python
        results = vector_search_chunks(
            parent_model=Note,
            chunk_model=NoteChunk,
            query="Python циклы for",
            limit=10,
            generator=embedding_generator,
        )

        # Python документ должен быть первым (меньший distance)
        assert len(results) >= 2
        first_note, first_distance = results[0]
        second_note, second_distance = results[1]

        assert first_note.id == note1.id, "Python документ должен быть первым"
        assert first_distance < second_distance, (
            "Distance для релевантного документа должен быть меньше"
        )

    def test_empty_query_raises_error(self, test_db, embedding_generator):
        """Проверяет, что пустой запрос вызывает ошибку."""
        with pytest.raises(ValueError, match="Текст не может быть пустым"):
            vector_search_chunks(
                parent_model=Note,
                chunk_model=NoteChunk,
                query="",
                limit=10,
                generator=embedding_generator,
            )

    def test_limit_parameter(
        self, test_db, sample_category, embedding_generator, text_splitter
    ):
        """Проверяет, что параметр limit работает корректно."""
        # Создаем 5 документов
        for i in range(5):
            save_note_with_chunks(
                note_model=Note,
                chunk_model=NoteChunk,
                note_data={
                    "title": f"Document {i}",
                    "content": f"Content about topic {i}. " * 50,
                    "category": sample_category,
                },
                splitter=text_splitter,
                generator=embedding_generator,
            )

        # Запрашиваем только 3
        results = vector_search_chunks(
            parent_model=Note,
            chunk_model=NoteChunk,
            query="topic document",
            limit=3,
            generator=embedding_generator,
        )

        assert len(results) <= 3, "Не должно возвращаться больше limit результатов"

    def test_filter_by_category(self, test_db, embedding_generator, text_splitter):
        """Проверяет фильтрацию по категории."""
        cat1 = Category.create(name="Python")
        cat2 = Category.create(name="JavaScript")

        note1 = save_note_with_chunks(
            note_model=Note,
            chunk_model=NoteChunk,
            note_data={
                "title": "Python Guide",
                "content": "Python programming. " * 50,
                "category": cat1,
            },
            splitter=text_splitter,
            generator=embedding_generator,
        )

        note2 = save_note_with_chunks(
            note_model=Note,
            chunk_model=NoteChunk,
            note_data={
                "title": "JS Guide",
                "content": "JavaScript programming. " * 50,
                "category": cat2,
            },
            splitter=text_splitter,
            generator=embedding_generator,
        )

        # Поиск только в Python категории
        results = vector_search_chunks(
            parent_model=Note,
            chunk_model=NoteChunk,
            query="programming guide",
            limit=10,
            generator=embedding_generator,
            category_id=cat1.id,
        )

        # Должен вернуть только Python документ
        assert all(note.category_id == cat1.id for note, _ in results), (
            "Все результаты должны быть из указанной категории"
        )


class TestFulltextSearchParents:
    """Тесты полнотекстового поиска по родителям."""

    def test_fts_search_basic(
        self, test_db, sample_category, embedding_generator, text_splitter
    ):
        """Проверяет базовый полнотекстовый поиск."""
        note = save_note_with_chunks(
            note_model=Note,
            chunk_model=NoteChunk,
            note_data={
                "title": "SQLite Tutorial",
                "content": "SQLite is a lightweight database. " * 50,
                "category": sample_category,
            },
            splitter=text_splitter,
            generator=embedding_generator,
        )

        # Поиск по ключевому слову
        results = fulltext_search_parents(parent_model=Note, query="SQLite", limit=10)

        assert len(results) > 0, "Должны найтись результаты"
        found_note, rank = results[0]
        assert found_note.id == note.id, "Должен найтись созданный документ"

    def test_fts_boolean_operators(
        self, test_db, sample_category, embedding_generator, text_splitter
    ):
        """Проверяет работу FTS5 операторов (AND, OR, NOT)."""
        note1 = save_note_with_chunks(
            note_model=Note,
            chunk_model=NoteChunk,
            note_data={
                "title": "Python and SQLite",
                "content": "Using Python with SQLite database. " * 50,
                "category": sample_category,
            },
            splitter=text_splitter,
            generator=embedding_generator,
        )

        note2 = save_note_with_chunks(
            note_model=Note,
            chunk_model=NoteChunk,
            note_data={
                "title": "JavaScript Tutorial",
                "content": "JavaScript programming basics. " * 50,
                "category": sample_category,
            },
            splitter=text_splitter,
            generator=embedding_generator,
        )

        # Поиск с AND
        results = fulltext_search_parents(
            parent_model=Note, query="Python AND SQLite", limit=10
        )

        assert len(results) > 0
        # Первый результат должен содержать оба слова
        found_note = results[0][0]
        content_lower = (found_note.title + " " + found_note.content).lower()
        assert "python" in content_lower and "sqlite" in content_lower


class TestHybridSearchRRF:
    """Тесты гибридного поиска с RRF."""

    def test_hybrid_combines_results(
        self, test_db, sample_category, embedding_generator, text_splitter
    ):
        """Проверяет, что гибридный поиск комбинирует векторный и FTS."""
        # Документ с точным совпадением слов, но возможно менее релевантный семантически
        note1 = save_note_with_chunks(
            note_model=Note,
            chunk_model=NoteChunk,
            note_data={
                "title": "Machine Learning",
                "content": "Machine learning algorithms. " * 50,
                "category": sample_category,
            },
            splitter=text_splitter,
            generator=embedding_generator,
        )

        # Документ семантически близкий, но без точного совпадения
        note2 = save_note_with_chunks(
            note_model=Note,
            chunk_model=NoteChunk,
            note_data={
                "title": "AI Tutorial",
                "content": "Artificial intelligence and neural networks. " * 50,
                "category": sample_category,
            },
            splitter=text_splitter,
            generator=embedding_generator,
        )

        results = hybrid_search_rrf(
            parent_model=Note,
            chunk_model=NoteChunk,
            query="machine learning",
            limit=10,
            generator=embedding_generator,
        )

        assert len(results) >= 2, "Должны найтись оба документа"

        # Проверяем, что возвращаются кортежи (note, score)
        assert all(isinstance(item, tuple) and len(item) == 2 for item in results)

        # Проверяем уникальность
        note_ids = [note.id for note, _ in results]
        assert len(note_ids) == len(set(note_ids)), "Документы должны быть уникальными"

    def test_rrf_score_ordering(
        self, test_db, sample_category, embedding_generator, text_splitter
    ):
        """Проверяет корректность ранжирования по RRF."""
        # Создаем документы
        for i in range(3):
            save_note_with_chunks(
                note_model=Note,
                chunk_model=NoteChunk,
                note_data={
                    "title": f"Document {i}",
                    "content": f"Python programming topic {i}. " * 50,
                    "category": sample_category,
                },
                splitter=text_splitter,
                generator=embedding_generator,
            )

        results = hybrid_search_rrf(
            parent_model=Note,
            chunk_model=NoteChunk,
            query="Python programming",
            limit=10,
            k=60,
            generator=embedding_generator,
        )

        # Проверяем, что скоры упорядочены по убыванию
        if len(results) > 1:
            scores = [score for _, score in results]
            assert scores == sorted(scores, reverse=True), (
                "RRF скоры должны быть отсортированы по убыванию"
            )

    def test_rrf_with_filters(self, test_db, embedding_generator, text_splitter):
        """Проверяет работу фильтров в гибридном поиске."""
        cat1 = Category.create(name="Python")
        cat2 = Category.create(name="Java")

        note1 = save_note_with_chunks(
            note_model=Note,
            chunk_model=NoteChunk,
            note_data={
                "title": "Python Guide",
                "content": "Python programming. " * 50,
                "category": cat1,
            },
            splitter=text_splitter,
            generator=embedding_generator,
        )

        note2 = save_note_with_chunks(
            note_model=Note,
            chunk_model=NoteChunk,
            note_data={
                "title": "Java Guide",
                "content": "Java programming. " * 50,
                "category": cat2,
            },
            splitter=text_splitter,
            generator=embedding_generator,
        )

        # Гибридный поиск только в Python
        results = hybrid_search_rrf(
            parent_model=Note,
            chunk_model=NoteChunk,
            query="programming",
            limit=10,
            generator=embedding_generator,
            category_id=cat1.id,
        )

        # Все результаты должны быть из Python категории
        assert all(note.category_id == cat1.id for note, _ in results)


class TestCascadeDelete:
    """Тесты каскадного удаления."""

    def test_delete_note_deletes_chunks(
        self, test_db, sample_category, embedding_generator, text_splitter, long_text
    ):
        """Проверяет CASCADE DELETE при удалении заметки."""
        # Создаем заметку с чанками
        note = save_note_with_chunks(
            note_model=Note,
            chunk_model=NoteChunk,
            note_data={
                "title": "Test Note",
                "content": long_text,
                "category": sample_category,
            },
            splitter=text_splitter,
            generator=embedding_generator,
        )

        note_id = note.id
        chunk_count = note.chunks.count()

        assert chunk_count > 0, "Должны быть созданы чанки"

        # Удаляем родительскую заметку
        note.delete_instance()

        # Проверяем, что чанки удалились
        remaining_chunks = (
            NoteChunk.select().where(NoteChunk.note_id == note_id).count()
        )
        assert remaining_chunks == 0, "Все чанки должны быть удалены (CASCADE)"


class TestChunkingIntegration:
    """Интеграционные тесты нарезки и поиска."""

    def test_long_document_splitting(
        self, test_db, sample_category, embedding_generator, long_text
    ):
        """Проверяет корректную нарезку длинного документа."""
        splitter = SimpleTextSplitter(chunk_size=500, overlap=100)

        note = save_note_with_chunks(
            note_model=Note,
            chunk_model=NoteChunk,
            note_data={
                "title": "Long Document",
                "content": long_text,
                "category": sample_category,
            },
            splitter=splitter,
            generator=embedding_generator,
        )

        chunks = list(note.chunks)

        # Проверяем количество чанков
        assert len(chunks) > 1, "Длинный документ должен быть разбит на чанки"

        # Проверяем индексы
        indices = [chunk.chunk_index for chunk in chunks]
        assert indices == list(range(len(chunks))), (
            "Индексы должны быть последовательными"
        )

        # Проверяем размер чанков
        for chunk in chunks[:-1]:  # Все кроме последнего
            assert len(chunk.content) > 0, "Чанки не должны быть пустыми"
            # Размер может отличаться из-за smart cut, но не должен быть слишком большим
            assert len(chunk.content) < splitter.chunk_size * 2, (
                f"Чанк слишком большой: {len(chunk.content)} символов"
            )

    def test_context_preservation(
        self, test_db, sample_category, embedding_generator, text_splitter
    ):
        """Проверяет, что контекст добавляется к чанкам."""
        note = save_note_with_chunks(
            note_model=Note,
            chunk_model=NoteChunk,
            note_data={
                "title": "Important Document",
                "content": "Content here. " * 100,
                "category": sample_category,
            },
            splitter=text_splitter,
            generator=embedding_generator,
        )

        # Контекст должен быть в get_context_text()
        context = note.get_context_text()
        assert "Important Document" in context, "Заголовок должен быть в контексте"
        assert sample_category.name in context, "Категория должна быть в контексте"
