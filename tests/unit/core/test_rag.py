"""Unit-тесты для RAG Engine (Phase 9.0).

Тестирует:
- RAGResult dataclass
- RAGEngine.ask() с моками
- Формирование контекста из чанков (по умолчанию)
- Формирование контекста из полных документов (full_docs)
- Кастомные системные промпты
"""

from unittest.mock import MagicMock, patch

import pytest

from semantic_core.interfaces.llm import BaseLLMProvider, GenerationResult
from semantic_core.core.rag import RAGEngine, RAGResult
from semantic_core.domain import SearchResult, Document, ChunkResult, MatchType
from semantic_core.domain.chunk import Chunk, ChunkType


# ============================================================================
# Fixtures
# ============================================================================


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM провайдер для тестов."""

    def __init__(
        self,
        response_text: str = "This is a mock response",
        model: str = "mock-model",
        input_tokens: int = 100,
        output_tokens: int = 50,
    ):
        self._model = model
        self._response_text = response_text
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self.calls: list[dict] = []  # Для проверки вызовов

    @property
    def model_name(self) -> str:
        return self._model

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        history: list[dict] | None = None,
    ) -> GenerationResult:
        # Сохраняем вызов
        self.calls.append(
            {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "history": history,
            }
        )

        return GenerationResult(
            text=self._response_text,
            model=self._model,
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            finish_reason="STOP",
        )


@pytest.fixture
def mock_llm():
    """Mock LLM провайдер."""
    return MockLLMProvider(
        response_text="Based on the context, the answer is 42.",
        model="gemini-2.0-flash",
    )


@pytest.fixture
def mock_chunk_results():
    """Список mock ChunkResult для тестов (по умолчанию режим)."""
    return [
        ChunkResult(
            chunk=Chunk(
                content="The answer to life is 42.",
                chunk_index=0,
                chunk_type=ChunkType.TEXT,
                id=1,
            ),
            score=0.95,
            match_type=MatchType.HYBRID,
            parent_doc_id=1,
            parent_doc_title="hitchhikers_guide.md",
        ),
        ChunkResult(
            chunk=Chunk(
                content="Deep Thought calculated for 7.5 million years.",
                chunk_index=1,
                chunk_type=ChunkType.TEXT,
                id=2,
            ),
            score=0.82,
            match_type=MatchType.HYBRID,
            parent_doc_id=1,
            parent_doc_title="deep_thought.md",
        ),
        ChunkResult(
            chunk=Chunk(
                content="def answer(): return 42",
                chunk_index=0,
                chunk_type=ChunkType.CODE,
                language="python",
                id=3,
            ),
            score=0.71,
            match_type=MatchType.HYBRID,
            parent_doc_id=2,
            parent_doc_title="questions.md",
        ),
    ]


@pytest.fixture
def mock_search_results():
    """Список mock SearchResult с Document (для full_docs режима)."""
    return [
        SearchResult(
            document=Document(
                content="The answer to life is 42.",
                metadata={"source": "hitchhikers_guide.md"},
                id=1,
            ),
            score=0.95,
            match_type=MatchType.HYBRID,
            chunk_id=1,
        ),
        SearchResult(
            document=Document(
                content="Deep Thought calculated for 7.5 million years.",
                metadata={"source": "deep_thought.md"},
                id=1,
            ),
            score=0.82,
            match_type=MatchType.HYBRID,
            chunk_id=2,
        ),
        SearchResult(
            document=Document(
                content="The ultimate question remains unknown.",
                metadata={"source": "questions.md"},
                id=2,
            ),
            score=0.71,
            match_type=MatchType.HYBRID,
            chunk_id=3,
        ),
    ]


@pytest.fixture
def mock_core(mock_chunk_results, mock_search_results):
    """Mock SemanticCore с фейковым поиском."""
    core = MagicMock()
    core.search_chunks.return_value = mock_chunk_results
    core.search.return_value = mock_search_results
    return core


@pytest.fixture
def rag_engine(mock_core, mock_llm):
    """RAGEngine с моками для тестов."""
    return RAGEngine(
        core=mock_core,
        llm=mock_llm,
        context_chunks=5,
    )


# ============================================================================
# Tests: GenerationResult
# ============================================================================


class TestGenerationResult:
    """Тесты для GenerationResult dataclass."""

    def test_basic_creation(self):
        """Базовое создание результата."""
        result = GenerationResult(
            text="Hello, world!",
            model="gemini-2.0-flash",
        )

        assert result.text == "Hello, world!"
        assert result.model == "gemini-2.0-flash"
        assert result.input_tokens is None
        assert result.output_tokens is None

    def test_with_token_counts(self):
        """Результат с токенами."""
        result = GenerationResult(
            text="Response",
            model="gemini-2.0-flash",
            input_tokens=100,
            output_tokens=50,
        )

        assert result.total_tokens == 150

    def test_total_tokens_none(self):
        """total_tokens возвращает None если токены не указаны."""
        result = GenerationResult(text="Test", model="model")
        assert result.total_tokens is None

        result2 = GenerationResult(text="Test", model="model", input_tokens=10)
        assert result2.total_tokens is None


# ============================================================================
# Tests: RAGResult
# ============================================================================


class TestRAGResult:
    """Тесты для RAGResult dataclass."""

    def test_basic_creation_chunks(self, mock_chunk_results):
        """Базовое создание RAG результата с чанками."""
        generation = GenerationResult(
            text="Answer",
            model="gemini-2.0-flash",
            input_tokens=100,
            output_tokens=50,
        )

        result = RAGResult(
            answer="Answer",
            sources=mock_chunk_results,
            generation=generation,
            query="What is the answer?",
            full_docs=False,
        )

        assert result.answer == "Answer"
        assert result.has_sources is True
        assert len(result.sources) == 3
        assert result.query == "What is the answer?"
        assert result.total_tokens == 150
        assert result.full_docs is False

    def test_basic_creation_full_docs(self, mock_search_results):
        """Создание RAG результата с полными документами."""
        generation = GenerationResult(text="Answer", model="model")

        result = RAGResult(
            answer="Answer",
            sources=mock_search_results,
            generation=generation,
            full_docs=True,
        )

        assert result.full_docs is True
        assert len(result.sources) == 3

    def test_no_sources(self):
        """RAGResult без источников."""
        generation = GenerationResult(text="No info", model="model")

        result = RAGResult(
            answer="No info",
            sources=[],
            generation=generation,
        )

        assert result.has_sources is False


# ============================================================================
# Tests: RAGEngine
# ============================================================================


class TestRAGEngine:
    """Тесты для RAGEngine."""

    def test_initialization(self, mock_core, mock_llm):
        """Инициализация RAGEngine."""
        engine = RAGEngine(
            core=mock_core,
            llm=mock_llm,
            context_chunks=10,
        )

        assert engine.core == mock_core
        assert engine.llm == mock_llm
        assert engine.context_chunks == 10

    def test_ask_basic_uses_chunks(self, rag_engine, mock_core, mock_llm):
        """Базовый RAG запрос использует search_chunks по умолчанию."""
        result = rag_engine.ask("What is the answer?")

        # Проверяем вызов search_chunks (не search!)
        mock_core.search_chunks.assert_called_once_with(
            query="What is the answer?",
            limit=5,
            mode="hybrid",
        )
        mock_core.search.assert_not_called()

        # Проверяем результат
        assert result.answer == "Based on the context, the answer is 42."
        assert len(result.sources) == 3
        assert result.query == "What is the answer?"
        assert result.full_docs is False

        # Проверяем вызов LLM
        assert len(mock_llm.calls) == 1
        call = mock_llm.calls[0]
        assert call["prompt"] == "What is the answer?"
        assert "CONTEXT" in call["system_prompt"]
        assert "The answer to life is 42" in call["system_prompt"]

    def test_ask_full_docs_mode(self, rag_engine, mock_core, mock_llm):
        """RAG запрос с full_docs=True использует search."""
        result = rag_engine.ask("What is the answer?", full_docs=True)

        # Проверяем вызов search (не search_chunks!)
        mock_core.search.assert_called_once_with(
            query="What is the answer?",
            limit=5,
            mode="hybrid",
        )
        mock_core.search_chunks.assert_not_called()

        # Проверяем результат
        assert result.full_docs is True
        assert len(result.sources) == 3

    def test_ask_vector_mode(self, rag_engine, mock_core):
        """RAG запрос с векторным поиском."""
        rag_engine.ask("query", search_mode="vector")

        mock_core.search_chunks.assert_called_once_with(
            query="query",
            limit=5,
            mode="vector",
        )

    def test_ask_fts_mode(self, rag_engine, mock_core):
        """RAG запрос с FTS поиском."""
        rag_engine.ask("query", search_mode="fts")

        mock_core.search_chunks.assert_called_once_with(
            query="query",
            limit=5,
            mode="fts",
        )

    def test_ask_with_temperature(self, rag_engine, mock_llm):
        """RAG запрос с кастомной температурой."""
        rag_engine.ask("query", temperature=0.2)

        assert mock_llm.calls[0]["temperature"] == 0.2

    def test_ask_with_max_tokens(self, rag_engine, mock_llm):
        """RAG запрос с ограничением токенов."""
        rag_engine.ask("query", max_tokens=500)

        assert mock_llm.calls[0]["max_tokens"] == 500

    def test_ask_empty_query_raises(self, rag_engine):
        """Пустой запрос выбрасывает ValueError."""
        with pytest.raises(ValueError, match="Запрос не может быть пустым"):
            rag_engine.ask("")

        with pytest.raises(ValueError, match="Запрос не может быть пустым"):
            rag_engine.ask("   ")

    def test_ask_no_sources(self, mock_core, mock_llm):
        """RAG запрос без найденных источников."""
        mock_core.search_chunks.return_value = []

        engine = RAGEngine(core=mock_core, llm=mock_llm)
        result = engine.ask("obscure query")

        assert result.has_sources is False
        # Проверяем, что контекст пустой
        call = mock_llm.calls[0]
        assert "No relevant context found" in call["system_prompt"]


class TestRAGEngineContextBuilding:
    """Тесты формирования контекста."""

    def test_build_chunks_context(self, rag_engine, mock_chunk_results):
        """Тест формирования контекста из чанков."""
        context = rag_engine._build_chunks_context(mock_chunk_results)

        # Проверяем структуру
        assert "[1]" in context
        assert "[2]" in context
        assert "[3]" in context
        assert "hitchhikers_guide.md" in context
        assert "The answer to life is 42" in context
        assert "score: 0.95" in context.lower()
        # Проверяем информацию о типе чанка
        assert "[text]" in context
        assert "[code]" in context
        assert "(python)" in context

    def test_build_chunks_context_empty(self, rag_engine):
        """Пустой контекст при отсутствии источников."""
        context = rag_engine._build_chunks_context([])
        assert context == "No relevant context found."

    def test_build_full_docs_context(self, rag_engine, mock_search_results):
        """Тест формирования контекста из полных документов."""
        context = rag_engine._build_full_docs_context(mock_search_results)

        assert "[1]" in context
        assert "hitchhikers_guide.md" in context
        assert "The answer to life is 42" in context
        assert "score: 0.95" in context.lower()

    def test_build_full_docs_context_empty(self, rag_engine):
        """Пустой контекст при отсутствии документов."""
        context = rag_engine._build_full_docs_context([])
        assert context == "No relevant context found."

    def test_build_chunks_context_long_title(self, rag_engine):
        """Обрезка длинных заголовков документов."""
        long_title_chunk = ChunkResult(
            chunk=Chunk(
                content="Content",
                chunk_index=0,
                chunk_type=ChunkType.TEXT,
            ),
            score=0.9,
            match_type=MatchType.HYBRID,
            parent_doc_id=1,
            parent_doc_title="/very/long/path/to/some/deeply/nested/document/file/with/too/many/parts.md",
        )

        context = rag_engine._build_chunks_context([long_title_chunk])
        # Заголовок должен быть обрезан (начинается с ...)
        assert "..." in context


class TestRAGEngineCustomPrompt:
    """Тесты кастомных системных промптов."""

    def test_custom_system_prompt_with_placeholder(
        self, mock_core, mock_llm, mock_chunk_results
    ):
        """Кастомный промпт с {context} placeholder."""
        mock_core.search_chunks.return_value = mock_chunk_results
        custom_prompt = "You are a Python expert. Use this context:\n{context}"

        engine = RAGEngine(
            core=mock_core,
            llm=mock_llm,
            system_prompt=custom_prompt,
        )

        engine.ask("How to use decorators?")

        call = mock_llm.calls[0]
        assert "You are a Python expert" in call["system_prompt"]
        assert "The answer to life is 42" in call["system_prompt"]

    def test_custom_system_prompt_without_placeholder(
        self, mock_core, mock_llm, mock_chunk_results
    ):
        """Кастомный промпт без placeholder - контекст добавляется в конец."""
        mock_core.search_chunks.return_value = mock_chunk_results
        custom_prompt = "Be concise and helpful."

        engine = RAGEngine(
            core=mock_core,
            llm=mock_llm,
            system_prompt=custom_prompt,
        )

        engine.ask("question")

        call = mock_llm.calls[0]
        assert call["system_prompt"].startswith("Be concise and helpful")
        assert "CONTEXT:" in call["system_prompt"]


class TestBaseLLMProvider:
    """Тесты для интерфейса BaseLLMProvider."""

    def test_mock_provider_implements_interface(self, mock_llm):
        """MockLLMProvider реализует BaseLLMProvider."""
        assert isinstance(mock_llm, BaseLLMProvider)
        assert mock_llm.model_name == "gemini-2.0-flash"

    def test_abstract_methods(self):
        """Проверка абстрактных методов."""
        with pytest.raises(TypeError):
            # Нельзя создать экземпляр абстрактного класса
            BaseLLMProvider()  # type: ignore


class TestRAGEngineWithHistory:
    """Тесты RAGEngine с историей чата."""

    def test_ask_without_history(self, rag_engine, mock_llm):
        """Запрос без истории (по умолчанию)."""
        rag_engine.ask("question")

        call = mock_llm.calls[0]
        assert call["history"] is None

    def test_ask_with_history(self, rag_engine, mock_llm):
        """Запрос с историей чата."""
        from semantic_core.interfaces.chat_history import ChatMessage

        history = [
            ChatMessage("user", "Hello", tokens=5),
            ChatMessage("assistant", "Hi there!", tokens=10),
        ]

        rag_engine.ask("What is RAG?", history=history)

        call = mock_llm.calls[0]
        assert call["history"] is not None
        assert len(call["history"]) == 2
        assert call["history"][0]["role"] == "user"
        assert call["history"][0]["content"] == "Hello"
        assert call["history"][1]["role"] == "assistant"

    def test_ask_with_empty_history(self, rag_engine, mock_llm):
        """Запрос с пустой историей."""
        rag_engine.ask("question", history=[])

        call = mock_llm.calls[0]
        # Пустой список конвертируется в None или пустой список
        assert call["history"] == [] or call["history"] is None
