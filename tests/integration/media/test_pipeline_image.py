"""Интеграционные тесты SemanticCore для изображений."""

import pytest
from unittest.mock import patch, MagicMock

from semantic_core.pipeline import SemanticCore
from semantic_core.domain import MediaConfig
from semantic_core.infrastructure.storage.peewee.models import MediaTaskModel


class TestSemanticCoreImageIngestion:
    """Тесты ingest_image() в SemanticCore."""

    @pytest.fixture
    def core_with_image_analyzer(self, mock_embedder, media_db, mock_image_analyzer):
        """SemanticCore с настроенным image analyzer.

        Использует media_db вместо in_memory_db для поддержки MediaTaskModel.
        """
        from semantic_core import (
            PeeweeVectorStore,
            SimpleSplitter,
            BasicContextStrategy,
        )

        store = PeeweeVectorStore(media_db)
        splitter = SimpleSplitter(chunk_size=500)
        context_strategy = BasicContextStrategy()
        media_config = MediaConfig(rpm_limit=60)

        core = SemanticCore(
            embedder=mock_embedder,
            store=store,
            splitter=splitter,
            context_strategy=context_strategy,
            image_analyzer=mock_image_analyzer,
            media_config=media_config,
        )

        return core

    def test_ingest_image_sync_success(self, core_with_image_analyzer, red_square_path):
        """Sync mode: успешная индексация изображения создаёт searchable документ."""
        from semantic_core.infrastructure.storage.peewee.models import (
            DocumentModel,
            ChunkModel,
        )

        with patch("time.sleep"):
            document_id = core_with_image_analyzer.ingest_image(
                path=str(red_square_path),
                mode="sync",
            )

        assert document_id is not None
        assert isinstance(document_id, str)

        # Документ создан в БД
        doc = DocumentModel.get_by_id(int(document_id))
        assert doc is not None
        assert doc.media_type == "image"

        # Чанк создан с вектором
        chunks = list(ChunkModel.select().where(ChunkModel.document_id == int(document_id)))
        assert len(chunks) >= 1
        assert chunks[0].embedding_status == "READY"

    def test_ingest_image_async_returns_task_id(
        self, core_with_image_analyzer, red_square_path
    ):
        """Async mode: возвращает task_id, не обрабатывает сразу."""
        task_id = core_with_image_analyzer.ingest_image(
            path=str(red_square_path),
            mode="async",
        )

        assert task_id is not None

        # Задача в БД со статусом pending
        task = MediaTaskModel.get_by_id(task_id)
        assert task.status == "pending"
        assert task.result_description is None

    def test_ingest_image_with_context(
        self, core_with_image_analyzer, red_square_path, mock_image_analyzer
    ):
        """Контекст передаётся в анализатор."""
        with patch("time.sleep"):
            core_with_image_analyzer.ingest_image(
                path=str(red_square_path),
                context_text="Section: Paris Photos",
                user_prompt="Describe this landmark",
                mode="sync",
            )

        # Проверяем что анализатор получил контекст
        call_args = mock_image_analyzer.analyze.call_args
        request = call_args[0][0]
        assert request.context_text == "Section: Paris Photos"
        assert request.user_prompt == "Describe this landmark"

    def test_ingest_invalid_image_raises(self, core_with_image_analyzer, tmp_path):
        """Невалидный файл вызывает ValueError."""
        invalid_path = tmp_path / "not_image.txt"
        invalid_path.write_text("not an image")

        with pytest.raises(ValueError, match="Unsupported image format"):
            core_with_image_analyzer.ingest_image(
                path=str(invalid_path),
                mode="sync",
            )

    def test_ingest_without_analyzer_raises(
        self, mock_embedder, media_db, red_square_path
    ):
        """Без image_analyzer вызывает RuntimeError."""
        from semantic_core import (
            PeeweeVectorStore,
            SimpleSplitter,
            BasicContextStrategy,
        )

        store = PeeweeVectorStore(media_db)

        core = SemanticCore(
            embedder=mock_embedder,
            store=store,
            splitter=SimpleSplitter(),
            context_strategy=BasicContextStrategy(),
            # image_analyzer не передан!
        )

        with pytest.raises(RuntimeError, match="image_analyzer not configured"):
            core.ingest_image(path=str(red_square_path), mode="sync")


class TestSemanticCoreMediaQueue:
    """Тесты process_media_queue() в SemanticCore."""

    @pytest.fixture
    def core_with_pending_tasks(
        self, mock_embedder, media_db, mock_image_analyzer, red_square_path
    ):
        """Core с несколькими pending задачами."""
        from semantic_core import (
            PeeweeVectorStore,
            SimpleSplitter,
            BasicContextStrategy,
        )

        # Создаём pending задачи
        for i in range(5):
            MediaTaskModel.create(
                id=f"queue-task-{i}",
                media_path=str(red_square_path),
                media_type="image",
                mime_type="image/png",
                status="pending",
            )

        store = PeeweeVectorStore(media_db)
        media_config = MediaConfig(rpm_limit=60)

        core = SemanticCore(
            embedder=mock_embedder,
            store=store,
            splitter=SimpleSplitter(),
            context_strategy=BasicContextStrategy(),
            image_analyzer=mock_image_analyzer,
            media_config=media_config,
        )

        return core

    def test_process_media_queue(self, core_with_pending_tasks):
        """process_media_queue обрабатывает задачи."""
        with patch("time.sleep"):
            processed = core_with_pending_tasks.process_media_queue(max_tasks=3)

        assert processed == 3

        # 2 задачи остались
        remaining = core_with_pending_tasks.get_media_queue_size()
        assert remaining == 2

    def test_get_media_queue_size(self, core_with_pending_tasks):
        """get_media_queue_size возвращает количество pending."""
        size = core_with_pending_tasks.get_media_queue_size()
        assert size == 5

    def test_process_all_queue(self, core_with_pending_tasks):
        """Обработка всей очереди."""
        with patch("time.sleep"):
            core_with_pending_tasks.process_media_queue(max_tasks=100)

        assert core_with_pending_tasks.get_media_queue_size() == 0


class TestSemanticCoreMediaConfig:
    """Тесты конфигурации MediaConfig."""

    def test_default_media_config(self, mock_embedder, media_db):
        """По умолчанию создаётся MediaConfig."""
        from semantic_core import (
            PeeweeVectorStore,
            SimpleSplitter,
            BasicContextStrategy,
        )

        core = SemanticCore(
            embedder=mock_embedder,
            store=PeeweeVectorStore(media_db),
            splitter=SimpleSplitter(),
            context_strategy=BasicContextStrategy(),
        )

        assert core.media_config is not None
        assert core.media_config.rpm_limit == 15  # Default

    def test_custom_media_config(self, mock_embedder, media_db, mock_image_analyzer):
        """Кастомный MediaConfig."""
        from semantic_core import (
            PeeweeVectorStore,
            SimpleSplitter,
            BasicContextStrategy,
        )

        config = MediaConfig(
            rpm_limit=30,
            image_model="gemini-2.5-flash-lite",
            max_image_dimension=1280,
        )

        core = SemanticCore(
            embedder=mock_embedder,
            store=PeeweeVectorStore(media_db),
            splitter=SimpleSplitter(),
            context_strategy=BasicContextStrategy(),
            image_analyzer=mock_image_analyzer,
            media_config=config,
        )

        assert core.media_config.rpm_limit == 30
        assert core.media_config.image_model == "gemini-2.5-flash-lite"
