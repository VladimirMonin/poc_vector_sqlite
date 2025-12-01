"""
Модели предметной области для системы заметок.

Демонстрирует:
- Один-ко-многим (Category -> Note)
- Многие-ко-многим (Note <-> Tag)
- Использование HybridSearchMixin для семантического поиска
"""

from datetime import datetime

from peewee import (
    Model,
    AutoField,
    CharField,
    TextField,
    ForeignKeyField,
    DateTimeField,
)

from semantic_core import db, HybridSearchMixin


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


class Note(HybridSearchMixin, BaseModel):
    """
    Заметка с поддержкой семантического поиска.
    
    Наследует HybridSearchMixin для получения методов:
    - vector_search()
    - fulltext_search()
    - hybrid_search()
    - update_vector_index()
    
    Связи:
    - Многие-к-одному с Category
    - Многие-ко-многим с Tag
    
    Attributes:
        id: Автоинкремент ID
        title: Заголовок заметки
        content: Содержимое заметки
        category: Ссылка на категорию
        created_at: Дата создания
        updated_at: Дата последнего обновления
    """
    
    id = AutoField(primary_key=True)
    title = CharField(max_length=255, index=True)
    content = TextField()
    category = ForeignKeyField(
        Category,
        backref='notes',
        on_delete='CASCADE',
        null=True  # Категория опциональна
    )
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)
    
    # Конфигурация для HybridSearchMixin
    _vector_column = "embedding"
    _fts_columns = ["title", "content"]
    
    class Meta:
        table_name = "notes"
        indexes = (
            (('category', 'created_at'), False),  # Составной индекс
        )
    
    def get_search_text(self) -> str:
        """
        Формирует текст для индексации и векторизации.
        
        Включает контекст категории для улучшения семантического поиска.
        
        Returns:
            str: Объединенный текст заметки с метаданными
        """
        parts = []
        
        if self.category:
            parts.append(f"Категория: {self.category.name}")
        
        if self.title:
            parts.append(f"Заголовок: {self.title}")
        
        parts.append(self.content)
        
        return "\n".join(parts)
    
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


class NoteTag(BaseModel):
    """
    Промежуточная таблица для связи Many-to-Many между Note и Tag.
    
    Attributes:
        note: Ссылка на заметку
        tag: Ссылка на тег
        created_at: Дата присвоения тега
    """
    
    note = ForeignKeyField(Note, backref='note_tags', on_delete='CASCADE')
    tag = ForeignKeyField(Tag, backref='tag_notes', on_delete='CASCADE')
    created_at = DateTimeField(default=datetime.now)
    
    class Meta:
        table_name = "note_tags"
        indexes = (
            (('note', 'tag'), True),  # Уникальная пара (note_id, tag_id)
        )
    
    def __str__(self) -> str:
        return f"NoteTag({self.note.title} - {self.tag.name})"
