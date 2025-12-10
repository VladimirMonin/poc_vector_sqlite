"""Сервис чата с RAG-интеграцией.

Оркестрирует RAGEngine для ответов с источниками.
Управляет историей чата через ChatSessionModel.

Classes:
    ChatService: Фасад для RAG-чата с историей.
    ChatResponse: DTO ответа чата.
    SourceItem: DTO источника.

Usage:
    service = ChatService(core, llm, cache, db)
    response = service.ask("Как работает гибридный поиск?", session_id=session_id)
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from peewee import Database

from semantic_core.core.rag import RAGEngine, RAGResult
from semantic_core.interfaces.chat_history import ChatMessage
from semantic_core.utils.logger import get_logger

from app.models.chat import ChatSessionModel, ChatMessageModel

if TYPE_CHECKING:
    from semantic_core.pipeline import SemanticCore
    from semantic_core.interfaces.llm import BaseLLMProvider
    from app.services.cache_service import QueryCacheService

logger = get_logger("flask_app.chat")


@dataclass
class SourceItem:
    """Источник для ответа.

    Attributes:
        index: Индекс источника (1, 2, 3...).
        title: Заголовок документа.
        chunk_type: Тип чанка (text, code, etc.).
        score: Релевантность.
        content_preview: Превью контента.
        doc_id: ID документа для ссылки.
    """

    index: int
    title: str
    chunk_type: str
    score: float
    content_preview: str
    doc_id: int


@dataclass
class ChatResponse:
    """Ответ чата с источниками.

    Attributes:
        answer: Сгенерированный ответ.
        sources: Список источников.
        session_id: ID сессии.
        message_id: ID сообщения.
        tokens_used: Использованные токены текущего ответа.
        total_tokens: Общее количество токенов в сессии.
        has_sources: Найдены ли источники.
    """

    answer: str
    sources: list[SourceItem]
    session_id: str
    message_id: int
    tokens_used: Optional[int] = None
    total_tokens: int = 0
    has_sources: bool = True


class ChatService:
    """Сервис RAG-чата с историей.

    Объединяет:
    - RAGEngine для генерации ответов
    - ChatSessionModel для персистентности
    - QueryCacheService для экономии эмбеддингов

    Attributes:
        rag: RAGEngine для Retrieval-Augmented Generation.
        cache: Опциональный кэш запросов.
        db: База данных для chat моделей.

    Example:
        >>> service = ChatService(core=core, llm=llm, cache=cache, database=db)
        >>> response = service.ask("Что такое RAG?", session_id=None)
        >>> print(response.answer)
        >>> print([s.title for s in response.sources])
    """

    def __init__(
        self,
        core: "SemanticCore",
        llm: "BaseLLMProvider",
        database: Database,
        cache: Optional["QueryCacheService"] = None,
        context_chunks: int = 5,
    ):
        """Инициализация сервиса.

        Args:
            core: SemanticCore для поиска.
            llm: LLM провайдер для генерации.
            database: Peewee база данных.
            cache: Опциональный кэш запросов.
            context_chunks: Количество чанков контекста.
        """
        self.rag = RAGEngine(
            core=core,
            llm=llm,
            context_chunks=context_chunks,
        )
        self.cache = cache
        self.db = database

        # Привязываем модели к базе
        ChatSessionModel._meta.database = database
        ChatMessageModel._meta.database = database

        # Создаём таблицы если нужно
        database.create_tables([ChatSessionModel, ChatMessageModel], safe=True)

        logger.info(
            "ChatService initialized",
            llm_model=llm.model_name,
            context_chunks=context_chunks,
            cache_enabled=cache is not None,
        )

    def ask(
        self,
        question: str,
        session_id: Optional[str] = None,
        search_mode: str = "hybrid",
        temperature: float = 0.7,
    ) -> ChatResponse:
        """Задать вопрос и получить RAG-ответ.

        Args:
            question: Вопрос пользователя.
            session_id: ID существующей сессии (None для новой).
            search_mode: Режим поиска (hybrid/vector/fts).
            temperature: Температура генерации.

        Returns:
            ChatResponse с ответом и источниками.

        Raises:
            ValueError: Если вопрос пустой.
        """
        if not question or not question.strip():
            raise ValueError("Вопрос не может быть пустым")

        question = question.strip()

        logger.info(
            "💬 Chat question",
            question_length=len(question),
            session_id=session_id,
            search_mode=search_mode,
        )

        # Получаем или создаём сессию
        session = self._get_or_create_session(session_id)

        # Если это первый вопрос — устанавливаем заголовок
        if session.message_count == 0:
            session.set_title_from_question(question)

        # Сохраняем вопрос пользователя
        ChatMessageModel.add_user_message(session, question)

        # Формируем историю для RAG
        history = self._build_history(session)

        # Кэшируем эмбеддинг запроса если есть cache
        if self.cache:
            try:
                self.cache.get_or_create_embedding(question)
            except Exception as e:
                logger.warning(f"Cache error: {e}")

        # Вызываем RAG
        try:
            rag_result = self.rag.ask(
                query=question,
                search_mode=search_mode,  # type: ignore
                temperature=temperature,
                history=history if history else None,
            )
        except Exception as e:
            logger.error(f"🔥 RAG error: {e}")
            # Сохраняем ошибку как ответ
            error_msg = f"Произошла ошибка при генерации ответа: {str(e)}"
            msg = ChatMessageModel.add_assistant_message(
                session,
                error_msg,
                sources_json=None,
                tokens_used=None,
            )
            return ChatResponse(
                answer=error_msg,
                sources=[],
                session_id=session.session_id,
                message_id=msg.id,
                has_sources=False,
            )

        # Формируем источники
        sources = self._extract_sources(rag_result)
        sources_json = json.dumps([s.__dict__ for s in sources], ensure_ascii=False)

        # Сохраняем ответ
        msg = ChatMessageModel.add_assistant_message(
            session,
            rag_result.answer,
            sources_json=sources_json,
            tokens_used=rag_result.total_tokens,
        )

        # Считаем общее количество токенов в сессии
        total_tokens = self.get_session_total_tokens(session.session_id)

        logger.info(
            "✅ Chat response generated",
            session_id=session.session_id,
            sources_count=len(sources),
            tokens=rag_result.total_tokens,
            total_tokens=total_tokens,
        )

        return ChatResponse(
            answer=rag_result.answer,
            sources=sources,
            session_id=session.session_id,
            message_id=msg.id,
            tokens_used=rag_result.total_tokens,
            total_tokens=total_tokens,
            has_sources=len(sources) > 0,
        )

    def get_session(self, session_id: str) -> Optional[ChatSessionModel]:
        """Получить сессию по ID.

        Args:
            session_id: UUID сессии.

        Returns:
            Сессия или None.
        """
        try:
            return ChatSessionModel.get(ChatSessionModel.session_id == session_id)
        except ChatSessionModel.DoesNotExist:
            return None

    def get_session_messages(self, session_id: str) -> list[ChatMessageModel]:
        """Получить все сообщения сессии.

        Args:
            session_id: UUID сессии.

        Returns:
            Список сообщений в хронологическом порядке.
        """
        session = self.get_session(session_id)
        if not session:
            return []

        return list(
            ChatMessageModel.select()
            .where(ChatMessageModel.session == session)
            .order_by(ChatMessageModel.created_at)
        )

    def get_recent_sessions(self, limit: int = 10) -> list[ChatSessionModel]:
        """Получить последние активные сессии.

        Args:
            limit: Максимум сессий.

        Returns:
            Список сессий, отсортированных по updated_at DESC.
        """
        return list(
            ChatSessionModel.select()
            .where(ChatSessionModel.is_active == True)
            .order_by(ChatSessionModel.updated_at.desc())
            .limit(limit)
        )

    def clear_session(self, session_id: str) -> bool:
        """Очистить историю сессии (soft delete).

        Деактивирует сессию вместо удаления.

        Args:
            session_id: UUID сессии.

        Returns:
            True если сессия найдена и очищена.
        """
        session = self.get_session(session_id)
        if not session:
            return False

        session.is_active = False
        session.save()

        logger.info(f"🗑️ Session cleared: {session_id}")
        return True

    def delete_message(self, message_id: int) -> Optional[str]:
        """Удалить сообщение из истории.

        Args:
            message_id: ID сообщения.

        Returns:
            session_id если успешно, None если сообщение не найдено.
        """
        try:
            message = ChatMessageModel.get_by_id(message_id)
            session = message.session
            session_id = session.session_id
            message.delete_instance()
            session.touch()
            logger.info(f"🗑️ Message deleted: {message_id}")
            return session_id
        except ChatMessageModel.DoesNotExist:
            return None

    def get_session_total_tokens(self, session_id: str) -> int:
        """Получить общее количество токенов в сессии.

        Args:
            session_id: UUID сессии.

        Returns:
            Сумма токенов всех assistant-сообщений.
        """
        session = self.get_session(session_id)
        if not session:
            return 0

        from peewee import fn

        result = (
            ChatMessageModel.select(fn.SUM(ChatMessageModel.tokens_used))
            .where(
                (ChatMessageModel.session == session)
                & (ChatMessageModel.tokens_used.is_null(False))
            )
            .scalar()
        )
        return result or 0

    def delete_session(self, session_id: str) -> bool:
        """Полностью удалить сессию с сообщениями.

        Args:
            session_id: UUID сессии.

        Returns:
            True если сессия найдена и удалена.
        """
        session = self.get_session(session_id)
        if not session:
            return False

        # CASCADE удалит сообщения
        session.delete_instance()

        logger.info(f"🗑️ Session deleted: {session_id}")
        return True

    def _get_or_create_session(self, session_id: Optional[str]) -> ChatSessionModel:
        """Получить существующую или создать новую сессию.

        Args:
            session_id: UUID сессии или None.

        Returns:
            ChatSessionModel.
        """
        if session_id:
            session = self.get_session(session_id)
            if session:
                return session
            logger.warning(f"Session not found: {session_id}, creating new")

        return ChatSessionModel.create_new()

    def _build_history(self, session: ChatSessionModel) -> list[ChatMessage]:
        """Сформировать историю чата для RAG.

        Args:
            session: Сессия чата.

        Returns:
            Список ChatMessage для RAGEngine.
        """
        messages = (
            ChatMessageModel.select()
            .where(ChatMessageModel.session == session)
            .order_by(ChatMessageModel.created_at)
            .limit(20)  # Ограничиваем историю
        )

        history = []
        for msg in messages:
            role = "user" if msg.is_user() else "assistant"
            history.append(ChatMessage(role=role, content=msg.content))  # type: ignore

        return history

    def _extract_sources(self, rag_result: RAGResult) -> list[SourceItem]:
        """Извлечь источники из RAG результата.

        Args:
            rag_result: Результат RAGEngine.ask().

        Returns:
            Список SourceItem для UI.
        """
        sources = []

        for i, chunk in enumerate(rag_result.sources, 1):
            # Превью контента
            content = chunk.content
            if len(content) > 150:
                content = content[:147] + "..."

            sources.append(
                SourceItem(
                    index=i,
                    title=chunk.parent_doc_title or f"Doc #{chunk.parent_doc_id}",
                    chunk_type=chunk.chunk_type.value,
                    score=chunk.score,
                    content_preview=content,
                    doc_id=chunk.parent_doc_id,
                )
            )

        return sources


__all__ = ["ChatService", "ChatResponse", "SourceItem"]
