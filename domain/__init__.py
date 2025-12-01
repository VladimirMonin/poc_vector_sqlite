"""
Domain models - бизнес-логика приложения для управления заметками.

Демонстрирует использование semantic_core для реализации
семантического поиска в конкретной предметной области.
"""

from domain.models import Note, Category, Tag, NoteTag

__all__ = ["Note", "Category", "Tag", "NoteTag"]
