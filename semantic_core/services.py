"""
Сервисный слой для работы с заметками и чанками.

Обеспечивает атомарное сохранение заметок с автоматической нарезкой
на чанки и векторизацией. Использует транзакции для гарантии целостности данных.
"""

from typing import List, Optional, Dict, Any

from peewee import Model

from semantic_core.database import db
from semantic_core.embeddings import EmbeddingGenerator
from semantic_core.text_processing import TextSplitter


def save_note_with_chunks(
    note_model: Model,
    chunk_model: Model,
    note_data: Dict[str, Any],
    splitter: TextSplitter,
    generator: EmbeddingGenerator,
    update_existing: bool = False,
) -> Model:
    """
    Сохраняет заметку с автоматической нарезкой на чанки и векторизацией.

    Алгоритм:
    1. Создает/обновляет родительскую заметку (Note)
    2. Удаляет старые чанки (если update_existing=True)
    3. Нарезает контент на чанки
    4. Генерирует эмбеддинги для каждого чанка с добавлением контекста
    5. Массово вставляет чанки (bulk_create)
    6. Массово вставляет векторы в виртуальную таблицу

    Все операции выполняются в транзакции: либо всё успешно, либо откат.

    Args:
        note_model: Класс модели Note (родитель)
        chunk_model: Класс модели NoteChunk (ребенок)
        note_data: Словарь с данными заметки (title, content, category, etc.)
        splitter: Экземпляр TextSplitter для нарезки
        generator: Экземпляр EmbeddingGenerator для векторизации
        update_existing: Если True, обновляет существующую заметку

    Returns:
        Model: Созданный/обновленный объект заметки

    Raises:
        Exception: При ошибке в процессе сохранения (откат транзакции)

    Example:
        >>> from semantic_core.text_processing import SimpleTextSplitter
        >>> from semantic_core.embeddings import EmbeddingGenerator
        >>> from domain.models import Note, NoteChunk
        >>>
        >>> splitter = SimpleTextSplitter(chunk_size=1000, overlap=200)
        >>> generator = EmbeddingGenerator()
        >>>
        >>> note_data = {
        ...     "title": "Длинная статья",
        ...     "content": "Текст на 10000 символов...",
        ...     "category": some_category
        ... }
        >>>
        >>> note = save_note_with_chunks(
        ...     note_model=Note,
        ...     chunk_model=NoteChunk,
        ...     note_data=note_data,
        ...     splitter=splitter,
        ...     generator=generator
        ... )
        >>> print(f"Создано {len(note.chunks)} чанков")
    """
    with db.atomic():  # Транзакция
        # 1. Создаем/обновляем родительскую заметку
        if update_existing and "id" in note_data:
            note_id = note_data.pop("id")
            note = note_model.get_by_id(note_id)

            # Обновляем поля
            for field, value in note_data.items():
                setattr(note, field, value)
            note.save()

            # Удаляем старые чанки (каскадно удалятся и векторы)
            chunk_model.delete().where(chunk_model.note == note).execute()
        else:
            # Создаем новую заметку
            note = note_model.create(**note_data)

        # 2. Нарезаем контент на чанки
        content = note_data.get("content", note.content)
        chunks_data = splitter.split_text(content)

        if not chunks_data:
            # Пустой контент — ничего не индексируем
            return note

        # 3. Получаем контекст для добавления к чанкам
        # Используем метод get_context_text() из модели Note
        context_text = (
            note.get_context_text() if hasattr(note, "get_context_text") else ""
        )

        # 4. Подготавливаем данные для bulk_create
        chunks_to_insert = []
        embeddings = []

        for chunk in chunks_data:
            # Формируем текст для векторизации: контекст + текст чанка
            if context_text:
                vector_text = f"{context_text}\n\n{chunk.text}"
            else:
                vector_text = chunk.text

            # Генерируем эмбеддинг
            vector = generator.embed_document(vector_text)

            # Готовим запись для вставки
            chunks_to_insert.append(
                {
                    "note": note,
                    "chunk_index": chunk.index,
                    "content": chunk.text,
                }
            )
            embeddings.append(vector)

        # 5. Массовая вставка чанков (INSERT INTO note_chunks ...)
        # Важно: bulk_create возвращает список созданных объектов с ID
        created_chunks = chunk_model.bulk_create(
            [chunk_model(**data) for data in chunks_to_insert]
        )

        # 6. Массовая вставка векторов в виртуальную таблицу vec0
        # note_chunks_vec(id, embedding)
        table_name = chunk_model._meta.table_name
        vector_table_name = f"{table_name}_vec"

        for chunk_obj, vector in zip(created_chunks, embeddings):
            blob = generator.vector_to_blob(vector)
            db.obj.execute_sql(
                f"INSERT INTO {vector_table_name}(id, embedding) VALUES (?, ?)",
                (chunk_obj.id, blob),
            )

    return note


def delete_note_with_chunks(note_model: Model, chunk_model: Model, note_id: int) -> int:
    """
    Удаляет заметку вместе со всеми чанками и векторами.

    Благодаря CASCADE DELETE в определении ForeignKey,
    при удалении Note автоматически удаляются:
    - Все связанные NoteChunk
    - Все векторы из note_chunks_vec (через триггер или вручную)

    Args:
        note_model: Класс модели Note
        chunk_model: Класс модели NoteChunk
        note_id: ID заметки для удаления

    Returns:
        int: Количество удаленных строк (должно быть 1)

    Example:
        >>> from domain.models import Note, NoteChunk
        >>> delete_note_with_chunks(Note, NoteChunk, note_id=5)
        1
    """
    with db.atomic():
        # Получаем заметку
        try:
            note = note_model.get_by_id(note_id)
        except note_model.DoesNotExist:
            return 0

        # Удаляем векторы из vec0 таблицы
        # (если нет триггера CASCADE на виртуальной таблице)
        table_name = chunk_model._meta.table_name
        vector_table_name = f"{table_name}_vec"

        # Получаем ID всех чанков этой заметки
        chunk_ids = [chunk.id for chunk in note.chunks]

        if chunk_ids:
            # Формируем плейсхолдеры для IN (?, ?, ?)
            placeholders = ", ".join("?" * len(chunk_ids))
            db.obj.execute_sql(
                f"DELETE FROM {vector_table_name} WHERE id IN ({placeholders})",
                chunk_ids,
            )

        # Удаляем саму заметку (чанки удалятся каскадно)
        rows_deleted = note.delete_instance()

        return rows_deleted
