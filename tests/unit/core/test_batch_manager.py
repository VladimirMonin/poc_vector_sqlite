"""Unit-тесты для BatchManager логики.

Проверяет:
- Группировку чанков в батчи
- Смену статусов PENDING -> SUBMITTED
- Логику flush_queue с min_size
- Обработку пустой очереди
"""

import json
import pytest

from semantic_core.domain import Document, ChunkType
from semantic_core.infrastructure.storage.peewee.models import (
    ChunkModel,
    EmbeddingStatus,
    BatchJobModel,
)


class TestBatchManagerLogic:
    """Тесты логики BatchManager (с моками)."""

    def test_flush_empty_queue(self, batch_manager):
        """flush_queue должен вернуть None если нет PENDING чанков."""
        batch_id = batch_manager.flush_queue()
        assert batch_id is None, "Не должно создаваться задание для пустой очереди"

    def test_flush_below_min_size(self, semantic_core, batch_manager, in_memory_db):
        """flush_queue не должен отправлять батч если чанков меньше min_size."""
        # Создаём документ с малым количеством чанков
        doc = Document(
            content="Short text for testing",
            metadata={"title": "Test"},
        )

        semantic_core.ingest(doc, mode="async")

        # Пытаемся отправить с min_size=10 (а у нас только 1 чанк)
        batch_id = batch_manager.flush_queue(min_size=10, force=False)

        assert batch_id is None, "Не должно создаваться задание если чанков < min_size"

        # Но с force=True должно сработать
        batch_id = batch_manager.flush_queue(min_size=10, force=True)
        assert batch_id is not None, "С force=True должно создаться задание"

    def test_flush_creates_batch_job(self, semantic_core, batch_manager, in_memory_db):
        """flush_queue должен создать BatchJob в БД."""
        # Создаём несколько документов
        for i in range(3):
            doc = Document(
                content=f"Document {i} with some content",
                metadata={"title": f"Doc {i}"},
            )
            semantic_core.ingest(doc, mode="async")

        # Отправляем батч
        batch_id = batch_manager.flush_queue(force=True)

        assert batch_id is not None, "Должен вернуться batch_id"

        # Проверяем, что создался BatchJob
        batch_job = BatchJobModel.get_by_id(batch_id)
        assert batch_job is not None, "Должна создаться запись BatchJob"
        assert batch_job.google_job_id.startswith("mock-batch-job"), (
            "Должен быть mock google_job_id"
        )
        assert batch_job.status == "SUBMITTED", "Статус должен быть SUBMITTED"

        # Проверяем stats
        stats = json.loads(batch_job.stats)
        assert stats["submitted"] > 0, "Должны быть submitted чанки"

    def test_chunks_linked_to_batch(self, semantic_core, batch_manager, in_memory_db):
        """Чанки должны привязаться к BatchJob после flush_queue."""
        doc = Document(
            content="Content for batch linking test",
            metadata={"title": "Test"},
        )
        semantic_core.ingest(doc, mode="async")

        # Отправляем батч
        batch_id = batch_manager.flush_queue(force=True)

        # Проверяем, что все PENDING чанки теперь привязаны к батчу
        pending_chunks = ChunkModel.select().where(
            ChunkModel.embedding_status == EmbeddingStatus.PENDING.value
        )

        for chunk in pending_chunks:
            assert chunk.batch_job_id == batch_id, (
                f"Чанк {chunk.id} должен быть привязан к batch {batch_id}"
            )

    def test_queue_stats(self, semantic_core, batch_manager):
        """get_queue_stats должен возвращать правильную статистику."""
        # Начальное состояние
        stats = batch_manager.get_queue_stats()
        assert stats["pending"] == 0
        assert stats["ready"] == 0

        # Создаём async документы
        for i in range(5):
            doc = Document(
                content=f"Test document {i}",
                metadata={"title": f"Doc {i}"},
            )
            semantic_core.ingest(doc, mode="async")

        # Проверяем статистику
        stats = batch_manager.get_queue_stats()
        assert stats["pending"] > 0, "Должны появиться PENDING чанки"
        assert stats["ready"] == 0, "READY чанков пока быть не должно"


class TestBatchManagerSync:
    """Тесты синхронизации статусов через sync_status."""

    def test_sync_completed_job(
        self, semantic_core, batch_manager, mock_batch_client, in_memory_db
    ):
        """sync_status должен обработать COMPLETED задание."""
        # Создаём документ
        doc = Document(
            content="Test document for completion",
            metadata={"title": "Test"},
        )
        semantic_core.ingest(doc, mode="async")

        # Отправляем батч
        batch_id = batch_manager.flush_queue(force=True)
        assert batch_id is not None

        # Получаем google_job_id
        batch_job = BatchJobModel.get_by_id(batch_id)
        google_job_id = batch_job.google_job_id

        # Устанавливаем статус SUCCEEDED в моке
        mock_batch_client.set_job_status(google_job_id, "SUCCEEDED")

        # Синхронизируем
        statuses = batch_manager.sync_status()

        # Проверяем результаты
        assert batch_id in statuses, "Должен вернуться статус для нашего батча"
        assert statuses[batch_id] == "COMPLETED", "Статус должен быть COMPLETED"

        # Проверяем, что в БД статус обновился
        batch_job = BatchJobModel.get_by_id(batch_id)
        assert batch_job.status == "COMPLETED", "BatchJob должен иметь статус COMPLETED"

        # Проверяем, что чанки получили статус READY
        chunks = ChunkModel.select().where(ChunkModel.batch_job == batch_job)
        for chunk in chunks:
            assert chunk.embedding_status == EmbeddingStatus.READY.value, (
                f"Чанк {chunk.id} должен иметь статус READY"
            )

    def test_sync_failed_job(
        self, semantic_core, batch_manager, mock_batch_client, in_memory_db
    ):
        """sync_status должен обработать FAILED задание."""
        doc = Document(
            content="Test document for failure",
            metadata={"title": "Test"},
        )
        semantic_core.ingest(doc, mode="async")

        batch_id = batch_manager.flush_queue(force=True)
        batch_job = BatchJobModel.get_by_id(batch_id)
        google_job_id = batch_job.google_job_id

        # Эмулируем ошибку
        mock_batch_client.set_job_status(google_job_id, "FAILED")

        # Синхронизируем
        statuses = batch_manager.sync_status()

        assert statuses[batch_id] == "FAILED", "Статус должен быть FAILED"

        # Проверяем БД
        batch_job = BatchJobModel.get_by_id(batch_id)
        assert batch_job.status == "FAILED", "BatchJob должен иметь статус FAILED"

        # Проверяем, что чанки тоже помечены как FAILED
        chunks = ChunkModel.select().where(ChunkModel.batch_job == batch_job)
        for chunk in chunks:
            assert chunk.embedding_status == EmbeddingStatus.FAILED.value, (
                f"Чанк {chunk.id} должен иметь статус FAILED"
            )
            assert chunk.error_message is not None, "Должно быть сообщение об ошибке"
