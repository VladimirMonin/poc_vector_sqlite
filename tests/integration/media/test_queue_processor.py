"""Интеграционные тесты MediaQueueProcessor."""

import pytest
from unittest.mock import patch

from semantic_core.core.media_queue import MediaQueueProcessor
from semantic_core.infrastructure.gemini.rate_limiter import RateLimiter
from semantic_core.infrastructure.storage.peewee.models import MediaTaskModel
from semantic_core.domain.media import TaskStatus


class TestMediaQueueProcessorEmpty:
    """Тесты для пустой очереди."""

    def test_empty_queue_returns_false(self, media_queue_processor):
        """Пустая очередь → process_one возвращает False."""
        result = media_queue_processor.process_one()
        assert result is False

    def test_empty_queue_batch_returns_zero(self, media_queue_processor):
        """Пустая очередь → process_batch возвращает 0."""
        count = media_queue_processor.process_batch(max_tasks=5)
        assert count == 0

    def test_pending_count_zero(self, media_queue_processor):
        """Пустая очередь → get_pending_count = 0."""
        assert media_queue_processor.get_pending_count() == 0


class TestMediaQueueProcessorSingle:
    """Тесты обработки одной задачи."""

    def test_process_pending_task_success(
        self, media_db, mock_image_analyzer, rate_limiter, red_square_path
    ):
        """Успешная обработка pending задачи."""
        processor = MediaQueueProcessor(
            analyzer=mock_image_analyzer,
            rate_limiter=rate_limiter,
        )

        # Создаём задачу
        MediaTaskModel.create(
            id="test-task-1",
            media_path=str(red_square_path),
            media_type="image",
            mime_type="image/png",
            status="pending",
        )

        # Обрабатываем
        with patch("time.sleep"):  # Не ждём в тестах
            result = processor.process_one()

        assert result is True

        # Проверяем статус
        task = MediaTaskModel.get_by_id("test-task-1")
        assert task.status == TaskStatus.COMPLETED.value
        assert task.result_description is not None
        assert task.processed_at is not None

    def test_process_task_calls_analyzer(
        self, media_db, mock_image_analyzer, rate_limiter, red_square_path
    ):
        """Анализатор вызывается с правильным запросом."""
        processor = MediaQueueProcessor(
            analyzer=mock_image_analyzer,
            rate_limiter=rate_limiter,
        )

        MediaTaskModel.create(
            id="test-task-2",
            media_path=str(red_square_path),
            media_type="image",
            mime_type="image/png",
            context_text="Test context",
            status="pending",
        )

        with patch("time.sleep"):
            processor.process_one()

        # Проверяем что analyze был вызван
        mock_image_analyzer.analyze.assert_called_once()

        # Проверяем request
        call_args = mock_image_analyzer.analyze.call_args
        request = call_args[0][0]
        assert request.context_text == "Test context"

    def test_process_task_with_error(
        self, media_db, mock_image_analyzer, rate_limiter, red_square_path
    ):
        """Ошибка в анализаторе → статус FAILED."""
        mock_image_analyzer.analyze.side_effect = Exception("API Error")

        processor = MediaQueueProcessor(
            analyzer=mock_image_analyzer,
            rate_limiter=rate_limiter,
        )

        MediaTaskModel.create(
            id="test-task-3",
            media_path=str(red_square_path),
            media_type="image",
            mime_type="image/png",
            status="pending",
        )

        with patch("time.sleep"):
            result = processor.process_one()

        # Возвращает True (задача обработана, хоть и с ошибкой)
        assert result is True

        task = MediaTaskModel.get_by_id("test-task-3")
        assert task.status == TaskStatus.FAILED.value
        assert "API Error" in task.error_message


class TestMediaQueueProcessorBatch:
    """Тесты обработки пачки задач."""

    def test_process_batch_multiple(
        self, media_db, mock_image_analyzer, rate_limiter, red_square_path
    ):
        """Обработка нескольких задач."""
        processor = MediaQueueProcessor(
            analyzer=mock_image_analyzer,
            rate_limiter=rate_limiter,
        )

        # Создаём 5 задач
        for i in range(5):
            MediaTaskModel.create(
                id=f"batch-task-{i}",
                media_path=str(red_square_path),
                media_type="image",
                mime_type="image/png",
                status="pending",
            )

        with patch("time.sleep"):
            processed = processor.process_batch(max_tasks=3)

        assert processed == 3

        # 2 задачи остались pending
        pending = processor.get_pending_count()
        assert pending == 2

    def test_process_batch_less_than_max(
        self, media_db, mock_image_analyzer, rate_limiter, red_square_path
    ):
        """Если задач меньше max_tasks - обрабатывает все."""
        processor = MediaQueueProcessor(
            analyzer=mock_image_analyzer,
            rate_limiter=rate_limiter,
        )

        # Создаём 2 задачи
        for i in range(2):
            MediaTaskModel.create(
                id=f"small-batch-{i}",
                media_path=str(red_square_path),
                media_type="image",
                mime_type="image/png",
                status="pending",
            )

        with patch("time.sleep"):
            processed = processor.process_batch(max_tasks=10)

        assert processed == 2
        assert processor.get_pending_count() == 0

    def test_process_preserves_order(
        self, media_db, mock_image_analyzer, rate_limiter, red_square_path
    ):
        """Задачи обрабатываются в порядке создания (FIFO)."""
        processor = MediaQueueProcessor(
            analyzer=mock_image_analyzer,
            rate_limiter=rate_limiter,
        )

        # Создаём задачи с разным временем
        from datetime import datetime, timedelta

        for i in range(3):
            MediaTaskModel.create(
                id=f"ordered-{i}",
                media_path=str(red_square_path),
                media_type="image",
                mime_type="image/png",
                status="pending",
                created_at=datetime.now() + timedelta(seconds=i),
            )

        processed_ids = []

        def track_call(request):
            # Получаем ID из пути (не идеально, но работает для теста)
            task = MediaTaskModel.get_or_none(
                MediaTaskModel.status == TaskStatus.PROCESSING.value
            )
            if task:
                processed_ids.append(task.id)
            return mock_image_analyzer.analyze.return_value

        mock_image_analyzer.analyze.side_effect = track_call

        with patch("time.sleep"):
            processor.process_batch(max_tasks=3)

        # Проверяем порядок
        assert processed_ids == ["ordered-0", "ordered-1", "ordered-2"]


class TestMediaQueueProcessorById:
    """Тесты process_task (обработка по ID)."""

    def test_process_specific_task(
        self, media_db, mock_image_analyzer, rate_limiter, red_square_path
    ):
        """Обработка конкретной задачи по ID."""
        processor = MediaQueueProcessor(
            analyzer=mock_image_analyzer,
            rate_limiter=rate_limiter,
        )

        MediaTaskModel.create(
            id="specific-task",
            media_path=str(red_square_path),
            media_type="image",
            mime_type="image/png",
            status="pending",
        )

        with patch("time.sleep"):
            result = processor.process_task("specific-task")

        assert result is True

        task = MediaTaskModel.get_by_id("specific-task")
        assert task.status == TaskStatus.COMPLETED.value

    def test_process_nonexistent_task(
        self, media_db, mock_image_analyzer, rate_limiter
    ):
        """Несуществующая задача → False."""
        processor = MediaQueueProcessor(
            analyzer=mock_image_analyzer,
            rate_limiter=rate_limiter,
        )

        result = processor.process_task("nonexistent-id")
        assert result is False


class TestMediaQueueProcessorRateLimiting:
    """Тесты Rate Limiting."""

    def test_rate_limiter_called(self, media_db, mock_image_analyzer, red_square_path):
        """Rate limiter вызывается для каждой задачи."""
        from unittest.mock import MagicMock

        mock_limiter = MagicMock()
        mock_limiter.wait.return_value = 0.0

        processor = MediaQueueProcessor(
            analyzer=mock_image_analyzer,
            rate_limiter=mock_limiter,
        )

        MediaTaskModel.create(
            id="rate-limit-test",
            media_path=str(red_square_path),
            media_type="image",
            mime_type="image/png",
            status="pending",
        )

        processor.process_one()

        mock_limiter.wait.assert_called_once()
