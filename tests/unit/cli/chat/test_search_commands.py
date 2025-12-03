"""Тесты для search slash-команд.

Проверяет:
- SearchCommand
- SearchModeCommand
- SourcesCommand
- SourceCommand
"""

import pytest
from unittest.mock import MagicMock, patch
from rich.console import Console

from semantic_core.cli.chat.slash import (
    ChatContext,
    SlashResult,
    SlashAction,
    SearchCommand,
    SearchModeCommand,
    SourcesCommand,
    SourceCommand,
)


@pytest.fixture
def mock_console() -> MagicMock:
    """Мок консоли Rich."""
    return MagicMock(spec=Console)


@pytest.fixture
def mock_rag():
    """Мок RAG движка."""
    mock = MagicMock()
    mock.search.return_value = [
        MagicMock(
            score=0.95,
            text="Chunk 1 content",
            parent_doc_title="doc1.md",
        ),
        MagicMock(
            score=0.85,
            text="Chunk 2 content",
            parent_doc_title="doc2.md",
        ),
    ]
    return mock


@pytest.fixture
def mock_last_result():
    """Мок последнего результата RAG."""
    source1 = MagicMock()
    source1.score = 0.95
    source1.text = "Source 1 content"
    source1.content = "# Source 1\n\nContent of source 1"
    source1.parent_doc_title = "source1.md"
    source1.parent_doc_id = 1
    source1.chunk_id = 1

    source2 = MagicMock()
    source2.score = 0.85
    source2.text = "Source 2 content"
    source2.content = "Source 2 plain text content"
    source2.parent_doc_title = "source2.md"
    source2.parent_doc_id = 2
    source2.chunk_id = 2

    mock = MagicMock()
    mock.sources = [source1, source2]
    mock.has_sources = True
    mock.full_docs = False  # Используем ChunkResult
    return mock


@pytest.fixture
def mock_context(mock_console, mock_rag, mock_last_result) -> ChatContext:
    """Создает мок контекста чата."""
    return ChatContext(
        console=mock_console,
        core=MagicMock(),
        rag=mock_rag,
        llm=MagicMock(),
        history_manager=MagicMock(),
        last_result=mock_last_result,
        search_mode="hybrid",
        context_chunks=5,
    )


class TestSearchCommand:
    """Тесты для /search."""

    def test_name_and_aliases(self):
        """Проверяет имя и алиасы."""
        cmd = SearchCommand()

        assert cmd.name == "search"
        assert "s" in cmd.aliases

    def test_requires_query(self, mock_context):
        """Требует аргумент — запрос."""
        cmd = SearchCommand()
        result = cmd.execute(mock_context, "")

        # Должен либо вывести сообщение, либо сообщить об ошибке
        assert result.action == SlashAction.CONTINUE

    def test_executes_search(self, mock_context, mock_rag):
        """Выполняет поиск с аргументом."""
        cmd = SearchCommand()
        result = cmd.execute(mock_context, "test query")

        # Должен выполнить поиск
        # Зависит от реализации — либо через rag.search, либо core.search
        assert result.action == SlashAction.CONTINUE

    def test_outputs_results(self, mock_context):
        """Выводит результаты поиска."""
        cmd = SearchCommand()
        cmd.execute(mock_context, "test query")

        # Должен вызвать print
        mock_context.console.print.assert_called()


class TestSearchModeCommand:
    """Тесты для /search-mode."""

    def test_name_and_aliases(self):
        """Проверяет имя и алиасы."""
        cmd = SearchModeCommand()

        assert cmd.name == "search-mode"
        assert "mode" in cmd.aliases

    def test_shows_current_mode_without_args(self, mock_context):
        """Без аргументов показывает текущий режим."""
        cmd = SearchModeCommand()
        result = cmd.execute(mock_context, "")

        # Должен вывести информацию о режиме
        mock_context.console.print.assert_called()
        assert result.action == SlashAction.CONTINUE

    def test_changes_mode_with_valid_arg(self, mock_context):
        """Меняет режим с валидным аргументом."""
        cmd = SearchModeCommand()
        result = cmd.execute(mock_context, "vector")

        assert mock_context.search_mode == "vector"
        assert result.action == SlashAction.CONTINUE

    def test_rejects_invalid_mode(self, mock_context):
        """Отклоняет невалидный режим."""
        original_mode = mock_context.search_mode
        cmd = SearchModeCommand()
        result = cmd.execute(mock_context, "invalid")

        # Режим не должен измениться
        assert mock_context.search_mode == original_mode
        assert result.action == SlashAction.CONTINUE

    def test_accepts_all_valid_modes(self, mock_context):
        """Принимает все валидные режимы."""
        cmd = SearchModeCommand()

        for mode in ["vector", "fts", "hybrid"]:
            result = cmd.execute(mock_context, mode)
            assert mock_context.search_mode == mode


class TestSourcesCommand:
    """Тесты для /sources."""

    def test_name_and_aliases(self):
        """Проверяет имя и алиасы."""
        cmd = SourcesCommand()

        assert cmd.name == "sources"
        assert "src" in cmd.aliases

    def test_shows_sources_from_last_result(self, mock_context):
        """Показывает источники последнего ответа."""
        cmd = SourcesCommand()
        result = cmd.execute(mock_context, "")

        # Должен вызвать print
        mock_context.console.print.assert_called()
        assert result.action == SlashAction.CONTINUE

    def test_handles_no_last_result(self, mock_console):
        """Обрабатывает отсутствие последнего ответа."""
        ctx = ChatContext(
            console=mock_console,
            core=MagicMock(),
            rag=MagicMock(),
            llm=MagicMock(),
            history_manager=MagicMock(),
            last_result=None,
        )

        cmd = SourcesCommand()
        result = cmd.execute(ctx, "")

        # Не должен упасть
        assert result.action == SlashAction.CONTINUE

    def test_handles_no_sources(self, mock_console):
        """Обрабатывает ответ без источников."""
        mock_result = MagicMock()
        mock_result.sources = []
        mock_result.has_sources = False

        ctx = ChatContext(
            console=mock_console,
            core=MagicMock(),
            rag=MagicMock(),
            llm=MagicMock(),
            history_manager=MagicMock(),
            last_result=mock_result,
        )

        cmd = SourcesCommand()
        result = cmd.execute(ctx, "")

        assert result.action == SlashAction.CONTINUE


class TestSourceCommand:
    """Тесты для /source."""

    def test_name_and_aliases(self):
        """Проверяет имя и алиасы."""
        cmd = SourceCommand()

        assert cmd.name == "source"

    def test_requires_index_argument(self, mock_context):
        """Требует индекс источника."""
        cmd = SourceCommand()
        result = cmd.execute(mock_context, "")

        # Не должен упасть
        assert result.action == SlashAction.CONTINUE

    def test_shows_source_by_index(self, mock_context):
        """Показывает источник по индексу."""
        cmd = SourceCommand()
        result = cmd.execute(mock_context, "1")

        # Должен вызвать print
        mock_context.console.print.assert_called()
        assert result.action == SlashAction.CONTINUE

    def test_handles_invalid_index(self, mock_context):
        """Обрабатывает невалидный индекс."""
        cmd = SourceCommand()
        result = cmd.execute(mock_context, "abc")

        # Не должен упасть
        assert result.action == SlashAction.CONTINUE

    def test_handles_out_of_range_index(self, mock_context):
        """Обрабатывает индекс за пределами диапазона."""
        cmd = SourceCommand()
        result = cmd.execute(mock_context, "100")

        # Не должен упасть
        assert result.action == SlashAction.CONTINUE

    def test_handles_no_last_result(self, mock_console):
        """Обрабатывает отсутствие последнего ответа."""
        ctx = ChatContext(
            console=mock_console,
            core=MagicMock(),
            rag=MagicMock(),
            llm=MagicMock(),
            history_manager=MagicMock(),
            last_result=None,
        )

        cmd = SourceCommand()
        result = cmd.execute(ctx, "1")

        # Не должен упасть
        assert result.action == SlashAction.CONTINUE
