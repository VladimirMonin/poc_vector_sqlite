"""
Модели предметной области для системы заметок.

Архитектура Parent-Child для работы с большими документами:
- Note (родитель) — хранит полный текст, используется для FTS и людей
- NoteChunk (ребенок) — фрагменты текста для векторного поиска
- Category → Note (один-ко-многим)
- Note ← Tag (многие-ко-многим)

Векторы хранятся ТОЛЬКО в чанках, что позволяет обрабатывать
документы размером >2000 токенов (лимит Gemini).
"""

from datetime import datetime

from peewee import (
    Model,
    AutoField,
    CharField,
    TextField,
    ForeignKeyField,
    DateTimeField,
    IntegerField,
)

from semantic_core import db


class BaseModel(Model):
    """Базовая модель с общими настройками."""

    class Meta:
        database = db


class Category(BaseModel):
    """
    Категория заметок (например: "Python", "Рецепты", "Идеи").

    Связь: Один-ко-многим с Note.

    Attributes:
        id: Автоинкремент ID
        name: Название категории (уникальное)
        created_at: Дата создания
    """

    id = AutoField(primary_key=True)
    name = CharField(max_length=100, unique=True, index=True)
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "categories"

    def __str__(self) -> str:
        return f"Category({self.name})"


class Tag(BaseModel):
    """
    Тег для заметок (например: "#код", "#срочно", "#вкусно").

    Связь: Многие-ко-многим с Note через NoteTag.

    Attributes:
        id: Автоинкремент ID
        name: Название тега (уникальное, с префиксом #)
        created_at: Дата создания
    """

    id = AutoField(primary_key=True)
    name = CharField(max_length=50, unique=True, index=True)
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "tags"

    def __str__(self) -> str:
        return f"Tag({self.name})"


class Note(BaseModel):
    """
    Заметка (родительский документ).

    Хранит полный текст для:
    - Полнотекстового поиска (FTS5)
    - Отображения пользователю
    - Метаданных (категория, теги)

    Векторы хранятся в связанных NoteChunk.

    Связи:
    - Многие-к-одному с Category
    - Один-ко-многим с NoteChunk (CASCADE DELETE)
    - Многие-ко-многим с Tag

    Attributes:
        id: Автоинкремент ID
        title: Заголовок заметки
        content: ПОЛНЫЙ текст заметки (может быть >2000 токенов)
        category: Ссылка на категорию
        created_at: Дата создания
        updated_at: Дата последнего обновления
    """

    id = AutoField(primary_key=True)
    title = CharField(max_length=255, index=True)
    content = TextField()  # Полный текст БЕЗ ограничений
    category = ForeignKeyField(
        Category,
        backref="notes",
        on_delete="CASCADE",
        null=True,
    )
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "notes"
        indexes = ((("category", "created_at"), False),)

    def get_context_text(self) -> str:
        """
        Возвращает контекст для добавления к чанкам при векторизации.

        Этот текст будет добавлен к каждому чанку при генерации эмбеддингов,
        чтобы сохранить смысловой контекст документа.

        Returns:
            str: Контекст (заголовок + категория)
        """
        parts = []

        if self.category:
            parts.append(f"Категория: {self.category.name}")

        if self.title:
            parts.append(f"Заголовок: {self.title}")

        return "\n".join(parts) if parts else ""

    def save(self, *args, **kwargs):
        """
        Переопределяем save для автоматического обновления updated_at.

        Args:
            *args: Позиционные аргументы для Model.save()
            **kwargs: Именованные аргументы для Model.save()

        Returns:
            int: Количество обновленных строк
        """
        self.updated_at = datetime.now()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Note({self.title[:30]}...)"


class NoteChunk(BaseModel):
    """
    Фрагмент заметки (дочерний документ) для векторного поиска.

    Каждая заметка разбивается на чанки фиксированного размера.
    Векторы (эмбеддинги) хранятся ТОЛЬКО здесь, в связанной
    виртуальной таблице note_chunks_vec.

    Это позволяет:
    1. Обрабатывать документы >2000 токенов (лимит Gemini)
    2. Находить релевантную ЧАСТЬ документа, а не весь документ целиком
    3. Возвращать пользователю полную заметку (parent)

    Связи:
    - Многие-к-одному с Note (CASCADE DELETE)

    Attributes:
        id: Автоинкремент ID
        note: Ссылка на родительскую заметку
        chunk_index: Порядковый номер чанка (0, 1, 2...)
        content: Текст этого фрагмента
        created_at: Дата создания чанка
    """

    id = AutoField(primary_key=True)
    note = ForeignKeyField(
        Note,
        backref="chunks",  # Обратная связь: note.chunks
        on_delete="CASCADE",  # При удалении заметки удаляются все чанки
        index=True,
    )
    chunk_index = IntegerField()  # Позиция в документе
    content = TextField()  # Текст фрагмента
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "note_chunks"
        indexes = (
            (("note", "chunk_index"), True),  # Уникальная пара (note_id, index)
        )

    def __str__(self) -> str:
        preview = self.content[:40] + "..." if len(self.content) > 40 else self.content
        return (
            f"NoteChunk(note={self.note_id}, idx={self.chunk_index}, text='{preview}')"
        )


class NoteTag(BaseModel):
    """
    Промежуточная таблица для связи Many-to-Many между Note и Tag.

    Attributes:
        note: Ссылка на заметку
        tag: Ссылка на тег
        created_at: Дата присвоения тега
    """

    note = ForeignKeyField(Note, backref="note_tags", on_delete="CASCADE")
    tag = ForeignKeyField(Tag, backref="tag_notes", on_delete="CASCADE")
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "note_tags"
        indexes = (
            (("note", "tag"), True),  # Уникальная пара (note_id, tag_id)
        )

    def __str__(self) -> str:
        return f"NoteTag({self.note.title} - {self.tag.name})"
