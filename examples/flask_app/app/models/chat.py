"""Модели чата для RAG-интерфейса.

Локальные таблицы Flask app для хранения истории чата.
Сессии и сообщения хранятся в той же SQLite БД что и semantic_core.

Classes:
    ChatSessionModel: Сессия чата с метаданными.
    ChatMessageModel: Сообщение в истории чата.
"""

import uuid
from datetime import datetime
from typing import Literal, Optional

from peewee import (
    Model,
    AutoField,
    TextField,
    IntegerField,
    DateTimeField,
    CharField,
    ForeignKeyField,
    BooleanField,
)


class ChatSessionModel(Model):
    """Сессия чата.

    Группирует сообщения одного диалога.
    Позволяет переключаться между сессиями.

    Attributes:
        id: Первичный ключ.
        session_id: UUID сессии (для URL).
        title: Название сессии (по первому вопросу).
        created_at: Время создания.
        updated_at: Время последнего сообщения.
        message_count: Количество сообщений.
        is_active: Активная ли сессия.
    """

    id = AutoField()
    session_id = CharField(max_length=36, unique=True, index=True)
    title = TextField(default="Новый чат")
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)
    message_count = IntegerField(default=0)
    is_active = BooleanField(default=True)

    class Meta:
        table_name = "chat_sessions"
        database = None  # Устанавливается при инициализации

    @classmethod
    def create_new(cls, title: Optional[str] = None) -> "ChatSessionModel":
        """Создать новую сессию чата.

        Args:
            title: Заголовок сессии (опционально).

        Returns:
            Созданная сессия.
        """
        return cls.create(
            session_id=str(uuid.uuid4()),
            title=title or "Новый чат",
        )

    def touch(self) -> None:
        """Обновить updated_at и message_count."""
        self.updated_at = datetime.now()
        self.message_count = self.messages.count()
        self.save()

    def set_title_from_question(self, question: str) -> None:
        """Установить заголовок из первого вопроса.

        Args:
            question: Текст первого вопроса.
        """
        # Ограничиваем до 50 символов
        if len(question) > 50:
            self.title = question[:47] + "..."
        else:
            self.title = question
        self.save()


class ChatMessageModel(Model):
    """Сообщение в истории чата.

    Хранит как user, так и assistant сообщения.
    Для assistant хранит также источники (JSON).

    Attributes:
        id: Первичный ключ.
        session: Ссылка на сессию.
        role: Роль (user/assistant).
        content: Текст сообщения.
        sources_json: JSON с источниками (для assistant).
        created_at: Время сообщения.
        tokens_used: Количество токенов (для assistant).
    """

    id = AutoField()
    session = ForeignKeyField(
        ChatSessionModel,
        backref="messages",
        on_delete="CASCADE",
    )
    role = CharField(max_length=16)  # 'user' или 'assistant'
    content = TextField()
    sources_json = TextField(null=True)  # JSON со списком источников
    created_at = DateTimeField(default=datetime.now)
    tokens_used = IntegerField(null=True)

    class Meta:
        table_name = "chat_messages"
        database = None  # Устанавливается при инициализации
        order_by = ["created_at"]

    @classmethod
    def add_user_message(
        cls,
        session: ChatSessionModel,
        content: str,
    ) -> "ChatMessageModel":
        """Добавить сообщение пользователя.

        Args:
            session: Сессия чата.
            content: Текст сообщения.

        Returns:
            Созданное сообщение.
        """
        msg = cls.create(
            session=session,
            role="user",
            content=content,
        )
        session.touch()
        return msg

    @classmethod
    def add_assistant_message(
        cls,
        session: ChatSessionModel,
        content: str,
        sources_json: Optional[str] = None,
        tokens_used: Optional[int] = None,
    ) -> "ChatMessageModel":
        """Добавить ответ ассистента.

        Args:
            session: Сессия чата.
            content: Текст ответа.
            sources_json: JSON с источниками.
            tokens_used: Использованные токены.

        Returns:
            Созданное сообщение.
        """
        msg = cls.create(
            session=session,
            role="assistant",
            content=content,
            sources_json=sources_json,
            tokens_used=tokens_used,
        )
        session.touch()
        return msg

    def is_user(self) -> bool:
        """Сообщение от пользователя?"""
        return self.role == "user"

    def is_assistant(self) -> bool:
        """Сообщение от ассистента?"""
        return self.role == "assistant"


__all__ = ["ChatSessionModel", "ChatMessageModel"]
