"""Тесты RAG-чата: роуты, сервис, модели.

Проверяет:
- Chat models (ChatSession, ChatMessage)
- ChatService с mock RAG
- Chat routes (HTMX endpoints)
- История и сессии
"""

import json
import pytest
import uuid
from dataclasses import dataclass
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock
from typing import Optional


# ============================================================================
# Chat Models Tests
# ============================================================================


class TestChatSessionModel:
    """Тесты ChatSessionModel."""

    @pytest.fixture
    def memory_db(self):
        """In-memory база для тестов."""
        from peewee import SqliteDatabase

        db = SqliteDatabase(":memory:")
        return db

    @pytest.fixture
    def setup_models(self, memory_db):
        """Инициализация моделей с БД."""
        from app.models.chat import ChatSessionModel, ChatMessageModel

        ChatSessionModel._meta.database = memory_db
        ChatMessageModel._meta.database = memory_db
        memory_db.create_tables([ChatSessionModel, ChatMessageModel])

        return ChatSessionModel, ChatMessageModel

    def test_create_new_session(self, setup_models):
        """Создание новой сессии генерирует UUID."""
        ChatSessionModel, _ = setup_models

        session = ChatSessionModel.create_new()

        assert session.session_id is not None
        assert len(session.session_id) == 36  # UUID format
        assert session.title == "Новый чат"
        assert session.message_count == 0
        assert session.is_active is True

    def test_create_session_with_title(self, setup_models):
        """Создание сессии с кастомным заголовком."""
        ChatSessionModel, _ = setup_models

        session = ChatSessionModel.create_new(title="Тестовый чат")

        assert session.title == "Тестовый чат"

    def test_set_title_from_question(self, setup_models):
        """Установка заголовка из первого вопроса."""
        ChatSessionModel, _ = setup_models

        session = ChatSessionModel.create_new()
        session.set_title_from_question("Как работает гибридный поиск?")

        assert session.title == "Как работает гибридный поиск?"

    def test_set_title_truncates_long_question(self, setup_models):
        """Длинный вопрос обрезается в заголовке."""
        ChatSessionModel, _ = setup_models

        session = ChatSessionModel.create_new()
        long_question = "A" * 100
        session.set_title_from_question(long_question)

        assert len(session.title) == 50
        assert session.title.endswith("...")

    def test_touch_updates_timestamp(self, setup_models):
        """touch() обновляет updated_at и message_count."""
        ChatSessionModel, ChatMessageModel = setup_models

        session = ChatSessionModel.create_new()
        old_updated = session.updated_at

        # Добавляем сообщение
        ChatMessageModel.create(
            session=session,
            role="user",
            content="Test",
        )

        session.touch()

        assert session.updated_at >= old_updated
        assert session.message_count == 1


class TestChatMessageModel:
    """Тесты ChatMessageModel."""

    @pytest.fixture
    def memory_db(self):
        """In-memory база для тестов."""
        from peewee import SqliteDatabase

        db = SqliteDatabase(":memory:")
        return db

    @pytest.fixture
    def setup_models(self, memory_db):
        """Инициализация моделей с БД."""
        from app.models.chat import ChatSessionModel, ChatMessageModel

        ChatSessionModel._meta.database = memory_db
        ChatMessageModel._meta.database = memory_db
        memory_db.create_tables([ChatSessionModel, ChatMessageModel])

        session = ChatSessionModel.create_new()
        return ChatSessionModel, ChatMessageModel, session

    def test_add_user_message(self, setup_models):
        """Добавление сообщения пользователя."""
        _, ChatMessageModel, session = setup_models

        msg = ChatMessageModel.add_user_message(session, "Привет!")

        assert msg.role == "user"
        assert msg.content == "Привет!"
        assert msg.is_user() is True
        assert msg.is_assistant() is False

    def test_add_assistant_message(self, setup_models):
        """Добавление ответа ассистента."""
        _, ChatMessageModel, session = setup_models

        msg = ChatMessageModel.add_assistant_message(
            session,
            "Привет! Чем могу помочь?",
            sources_json='[{"index": 1, "title": "Doc"}]',
            tokens_used=150,
        )

        assert msg.role == "assistant"
        assert msg.is_assistant() is True
        assert msg.sources_json is not None
        assert msg.tokens_used == 150

    def test_message_updates_session(self, setup_models):
        """Добавление сообщения обновляет сессию."""
        _, ChatMessageModel, session = setup_models

        ChatMessageModel.add_user_message(session, "Test")

        session = session.__class__.get_by_id(session.id)
        assert session.message_count == 1


# ============================================================================
# ChatService Tests
# ============================================================================


class TestChatService:
    """Тесты ChatService."""

    @pytest.fixture
    def memory_db(self):
        """In-memory база для тестов."""
        from peewee import SqliteDatabase

        db = SqliteDatabase(":memory:")
        return db

    @pytest.fixture
    def mock_core(self):
        """Mock SemanticCore."""
        return MagicMock()

    @pytest.fixture
    def mock_llm(self):
        """Mock LLM провайдер."""
        llm = MagicMock()
        llm.model_name = "gemini-2.5-flash-lite"
        return llm

    @pytest.fixture
    def mock_rag_result(self):
        """Фабрика для mock RAGResult."""

        def _create(answer="This is an answer", sources_count=2):
            result = MagicMock()
            result.answer = answer
            result.total_tokens = 100

            # Mock sources (ChunkResult)
            sources = []
            for i in range(sources_count):
                source = MagicMock()
                source.content = f"Source content {i + 1}"
                source.parent_doc_title = f"Document {i + 1}"
                source.parent_doc_id = i + 1
                source.chunk_type = MagicMock(value="text")
                source.score = 0.05 - i * 0.01
                sources.append(source)

            result.sources = sources
            return result

        return _create

    @pytest.fixture
    def chat_service(self, mock_core, mock_llm, mock_rag_result, memory_db):
        """ChatService с моками."""
        from app.services.chat_service import ChatService

        # Патчим RAGEngine.ask
        with patch("app.services.chat_service.RAGEngine") as MockRAG:
            mock_rag = MagicMock()
            mock_rag.ask.return_value = mock_rag_result()
            MockRAG.return_value = mock_rag

            service = ChatService(
                core=mock_core,
                llm=mock_llm,
                database=memory_db,
                cache=None,
            )
            service.rag = mock_rag  # Подменяем напрямую

            return service

    def test_ask_creates_session(self, chat_service, mock_rag_result):
        """ask() создаёт новую сессию если session_id=None."""
        chat_service.rag.ask.return_value = mock_rag_result()

        response = chat_service.ask("Что такое RAG?")

        assert response.session_id is not None
        assert len(response.session_id) == 36

    def test_ask_returns_answer(self, chat_service, mock_rag_result):
        """ask() возвращает ответ от RAG."""
        chat_service.rag.ask.return_value = mock_rag_result(
            answer="RAG combines retrieval and generation."
        )

        response = chat_service.ask("Что такое RAG?")

        assert "retrieval" in response.answer.lower()
        assert response.has_sources is True

    def test_ask_extracts_sources(self, chat_service, mock_rag_result):
        """ask() извлекает источники из RAG результата."""
        chat_service.rag.ask.return_value = mock_rag_result(sources_count=3)

        response = chat_service.ask("Вопрос?")

        assert len(response.sources) == 3
        assert response.sources[0].index == 1
        assert response.sources[0].title == "Document 1"

    def test_ask_saves_messages(self, chat_service, mock_rag_result):
        """ask() сохраняет сообщения в историю."""
        chat_service.rag.ask.return_value = mock_rag_result()

        response = chat_service.ask("Тестовый вопрос")

        messages = chat_service.get_session_messages(response.session_id)
        assert len(messages) == 2  # user + assistant
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"

    def test_ask_empty_question_raises(self, chat_service):
        """Пустой вопрос вызывает ValueError."""
        with pytest.raises(ValueError, match="пустым"):
            chat_service.ask("")

        with pytest.raises(ValueError, match="пустым"):
            chat_service.ask("   ")

    def test_ask_uses_existing_session(self, chat_service, mock_rag_result):
        """ask() использует существующую сессию."""
        chat_service.rag.ask.return_value = mock_rag_result()

        # Первый вопрос
        r1 = chat_service.ask("Вопрос 1")
        session_id = r1.session_id

        # Второй вопрос в той же сессии
        r2 = chat_service.ask("Вопрос 2", session_id=session_id)

        assert r2.session_id == session_id

        messages = chat_service.get_session_messages(session_id)
        assert len(messages) == 4  # 2 user + 2 assistant

    def test_get_recent_sessions(self, chat_service, mock_rag_result):
        """get_recent_sessions() возвращает последние сессии."""
        chat_service.rag.ask.return_value = mock_rag_result()

        # Создаём несколько сессий
        chat_service.ask("Вопрос 1")
        chat_service.ask("Вопрос 2")
        chat_service.ask("Вопрос 3")

        sessions = chat_service.get_recent_sessions(limit=2)

        assert len(sessions) == 2

    def test_clear_session(self, chat_service, mock_rag_result):
        """clear_session() деактивирует сессию."""
        chat_service.rag.ask.return_value = mock_rag_result()

        response = chat_service.ask("Вопрос")
        session_id = response.session_id

        result = chat_service.clear_session(session_id)

        assert result is True
        session = chat_service.get_session(session_id)
        assert session.is_active is False

    def test_delete_session(self, chat_service, mock_rag_result):
        """delete_session() удаляет сессию с сообщениями."""
        chat_service.rag.ask.return_value = mock_rag_result()

        response = chat_service.ask("Вопрос")
        session_id = response.session_id

        result = chat_service.delete_session(session_id)

        assert result is True
        assert chat_service.get_session(session_id) is None


# ============================================================================
# Chat Routes Tests
# ============================================================================


class TestChatRoutes:
    """Тесты Chat routes."""

    @pytest.fixture
    def mock_chat_service(self):
        """Mock ChatService."""
        service = MagicMock()
        service.get_recent_sessions.return_value = []
        service.get_session.return_value = None
        service.get_session_messages.return_value = []
        return service

    @pytest.fixture
    def app_with_chat(self, mock_chat_service):
        """Flask app с mock ChatService."""
        from app import create_app

        app = create_app(
            config={
                "TESTING": True,
                "SECRET_KEY": "test-secret-key",
            }
        )

        # Подменяем chat_service
        app.extensions["chat_service"] = mock_chat_service

        return app

    @pytest.fixture
    def client(self, app_with_chat):
        """Flask test client."""
        return app_with_chat.test_client()

    def test_chat_index_page(self, client):
        """GET /chat возвращает страницу чата."""
        response = client.get("/chat/")

        assert response.status_code == 200
        assert "RAG Чат" in response.get_data(as_text=True)

    def test_chat_index_without_service(self, app_with_chat, client):
        """Без ChatService показывает предупреждение."""
        app_with_chat.extensions["chat_service"] = None

        response = client.get("/chat/")

        assert response.status_code == 200
        assert "недоступен" in response.get_data(as_text=True)

    def test_chat_send_empty_question(self, client, mock_chat_service):
        """POST /chat/send с пустым вопросом возвращает ошибку."""
        response = client.post("/chat/send", data={"question": ""})

        assert response.status_code == 200
        assert "Введите вопрос" in response.get_data(as_text=True)

    def test_chat_send_calls_service(self, client, mock_chat_service):
        """POST /chat/send вызывает ChatService.ask()."""
        # Mock response
        mock_response = MagicMock()
        mock_response.answer = "Test answer"
        mock_response.sources = []
        mock_response.session_id = "test-session-id"
        mock_response.tokens_used = 100
        mock_chat_service.ask.return_value = mock_response

        response = client.post(
            "/chat/send",
            data={
                "question": "Тестовый вопрос",
                "mode": "hybrid",
            },
        )

        assert response.status_code == 200
        mock_chat_service.ask.assert_called_once()

    def test_chat_send_renders_response(self, client, mock_chat_service):
        """POST /chat/send рендерит ответ с источниками."""
        # Mock response with sources
        mock_source = MagicMock()
        mock_source.index = 1
        mock_source.title = "Test Document"
        mock_source.chunk_type = "text"
        mock_source.score = 0.05
        mock_source.content_preview = "Preview..."

        mock_response = MagicMock()
        mock_response.answer = "This is the **answer**"
        mock_response.sources = [mock_source]
        mock_response.session_id = "session-123"
        mock_response.tokens_used = 150
        mock_chat_service.ask.return_value = mock_response

        response = client.post(
            "/chat/send",
            data={"question": "Question"},
        )

        html = response.get_data(as_text=True)
        assert "answer" in html.lower()
        assert "session-123" in html

    def test_chat_new_session_redirects(self, client):
        """POST /chat/new редиректит на пустой чат."""
        response = client.post("/chat/new", follow_redirects=False)

        assert response.status_code == 302
        assert "/chat" in response.location

    def test_chat_clear_session(self, client, mock_chat_service):
        """POST /chat/clear очищает сессию."""
        response = client.post(
            "/chat/clear",
            data={"session_id": "test-session"},
            follow_redirects=False,
        )

        assert response.status_code == 302
        mock_chat_service.clear_session.assert_called_with("test-session")

    def test_chat_sessions_list(self, client, mock_chat_service):
        """GET /chat/sessions возвращает список сессий."""
        mock_session = MagicMock()
        mock_session.session_id = "session-1"
        mock_session.title = "Test Chat"
        mock_session.message_count = 5
        mock_session.updated_at = datetime.now()
        mock_chat_service.get_recent_sessions.return_value = [mock_session]

        response = client.get("/chat/sessions")

        assert response.status_code == 200
        assert "Test Chat" in response.get_data(as_text=True)

    def test_chat_delete_session(self, client, mock_chat_service):
        """POST /chat/session/<id>/delete удаляет сессию."""
        response = client.post(
            "/chat/session/test-session-id/delete",
            follow_redirects=False,
        )

        assert response.status_code == 302
        mock_chat_service.delete_session.assert_called_with("test-session-id")

    def test_chat_messages_endpoint(self, client, mock_chat_service):
        """GET /chat/messages возвращает историю."""
        mock_msg = MagicMock()
        mock_msg.role = "user"
        mock_msg.content = "Test message"
        mock_msg.is_user.return_value = True
        mock_msg.is_assistant.return_value = False
        mock_chat_service.get_session_messages.return_value = [mock_msg]

        response = client.get("/chat/messages?session_id=test")

        assert response.status_code == 200


# ============================================================================
# SourceItem Tests
# ============================================================================


class TestSourceItem:
    """Тесты SourceItem dataclass."""

    def test_source_item_creation(self):
        """Создание SourceItem."""
        from app.services.chat_service import SourceItem

        source = SourceItem(
            index=1,
            title="Test Document",
            chunk_type="code",
            score=0.05,
            content_preview="def hello()...",
            doc_id=42,
        )

        assert source.index == 1
        assert source.title == "Test Document"
        assert source.chunk_type == "code"
        assert source.score == 0.05
        assert source.doc_id == 42


# ============================================================================
# ChatResponse Tests
# ============================================================================


class TestChatResponse:
    """Тесты ChatResponse dataclass."""

    def test_chat_response_creation(self):
        """Создание ChatResponse."""
        from app.services.chat_service import ChatResponse, SourceItem

        source = SourceItem(
            index=1,
            title="Doc",
            chunk_type="text",
            score=0.05,
            content_preview="...",
            doc_id=1,
        )

        response = ChatResponse(
            answer="Test answer",
            sources=[source],
            session_id="session-123",
            message_id=42,
            tokens_used=100,
            has_sources=True,
        )

        assert response.answer == "Test answer"
        assert len(response.sources) == 1
        assert response.session_id == "session-123"
        assert response.has_sources is True

    def test_chat_response_without_sources(self):
        """ChatResponse без источников."""
        from app.services.chat_service import ChatResponse

        response = ChatResponse(
            answer="No context found",
            sources=[],
            session_id="session-456",
            message_id=1,
            has_sources=False,
        )

        assert response.has_sources is False
        assert len(response.sources) == 0
