"""Integration-тест полного жизненного цикла батч-обработки.

Эмулирует:
1. ingest(mode='async') - сохранение в БД
2. flush_queue() - создание батча
3. Mock API response - эмуляция ответа Google
4. sync_status() - синхронизация результатов
5. Проверка векторов - валидация данных в БД
"""

import pytest

from semantic_core.domain import Document
from semantic_core.infrastructure.storage.peewee.models import (
    ChunkModel,
    BatchJobModel,
    EmbeddingStatus,
)


class TestWorkerLifecycle:
    """End-to-end тест с mock API."""

    def test_full_batch_lifecycle_success(
        self, semantic_core, batch_manager, mock_batch_client, in_memory_db
    ):
        """Полный успешный цикл: ingest -> flush -> mock complete -> sync."""

        # === 1. Ingest ===
        documents = [
            Document(
                content=f"Document {i} for lifecycle test",
                metadata={"title": f"Doc {i}", "index": i},
            )
            for i in range(3)
        ]

        saved_docs = []
        for doc in documents:
            saved = semantic_core.ingest(doc, mode="async")
            saved_docs.append(saved)

        # Проверяем начальное состояние
        stats = batch_manager.get_queue_stats()
        assert stats["pending"] > 0, "Должны быть PENDING чанки"
        assert stats["ready"] == 0, "READY чанков быть не должно"

        # === 2. Flush ===
        batch_id = batch_manager.flush_queue(force=True)
        assert batch_id is not None, "Должен создаться батч"

        # Проверяем BatchJob
        batch_job = BatchJobModel.get_by_id(batch_id)
        assert batch_job.status == "SUBMITTED", "Статус должен быть SUBMITTED"
        assert batch_job.google_job_id.startswith("mock-batch-job"), (
            "Должен быть mock job_id"
        )

        # Проверяем, что чанки привязаны
        all_chunks = ChunkModel.select().where(
            ChunkModel.document_id.in_([d.id for d in saved_docs])
        )
        for chunk in all_chunks:
            assert chunk.batch_job_id == batch_id, "Чанк должен быть привязан к батчу"

        # === 3. Mock API Response ===
        # Устанавливаем статус SUCCEEDED в моке
        mock_batch_client.set_job_status(batch_job.google_job_id, "SUCCEEDED")

        # === 4. Sync ===
        statuses = batch_manager.sync_status()

        assert batch_id in statuses, "Должен вернуться статус батча"
        assert statuses[batch_id] == "COMPLETED", "Статус должен стать COMPLETED"

        # === 5. Validation ===
        # Проверяем BatchJob
        batch_job = BatchJobModel.get_by_id(batch_id)
        assert batch_job.status == "COMPLETED", "BatchJob должен быть COMPLETED"

        # Проверяем чанки
        for chunk in all_chunks:
            chunk = ChunkModel.get_by_id(chunk.id)  # Перечитываем из БД
            assert chunk.embedding_status == EmbeddingStatus.READY.value, (
                f"Чанк {chunk.id} должен иметь статус READY"
            )

            # Проверяем наличие вектора в vec0
            cursor = in_memory_db.execute_sql(
                "SELECT embedding FROM chunks_vec WHERE id = ?", (chunk.id,)
            )
            result = cursor.fetchone()
            assert result is not None, (
                f"Чанк {chunk.id} должен иметь вектор в chunks_vec"
            )
            assert len(result[0]) > 0, "Вектор не должен быть пустым"

        # Проверяем статистику
        stats = batch_manager.get_queue_stats()
        assert stats["pending"] == 0, "Не должно остаться PENDING чанков"
        assert stats["ready"] > 0, "Должны появиться READY чанки"

    def test_batch_lifecycle_with_failure(
        self, semantic_core, batch_manager, mock_batch_client
    ):
        """Цикл с ошибкой: чанки должны помечаться как FAILED."""

        doc = Document(
            content="Document for failure test",
            metadata={"title": "Fail Test"},
        )
        saved_doc = semantic_core.ingest(doc, mode="async")

        # Отправляем батч
        batch_id = batch_manager.flush_queue(force=True)
        batch_job = BatchJobModel.get_by_id(batch_id)

        # Эмулируем ошибку
        mock_batch_client.set_job_status(batch_job.google_job_id, "FAILED")

        # Синхронизируем
        statuses = batch_manager.sync_status()

        assert statuses[batch_id] == "FAILED", "Статус должен быть FAILED"

        # Проверяем чанки
        chunks = ChunkModel.select().where(ChunkModel.document_id == saved_doc.id)
        for chunk in chunks:
            assert chunk.embedding_status == EmbeddingStatus.FAILED.value, (
                f"Чанк {chunk.id} должен иметь статус FAILED"
            )
            assert chunk.error_message is not None, "Должно быть error_message"
            assert "FAILED" in chunk.error_message, "Сообщение должно содержать FAILED"

    def test_multiple_batches_independent(
        self, semantic_core, batch_manager, mock_batch_client
    ):
        """Несколько батчей должны обрабатываться независимо."""

        # Создаём первый батч
        doc1 = Document(content="Batch 1 document", metadata={"title": "Batch 1"})
        semantic_core.ingest(doc1, mode="async")
        batch_id_1 = batch_manager.flush_queue(force=True)

        # Создаём второй батч
        doc2 = Document(content="Batch 2 document", metadata={"title": "Batch 2"})
        semantic_core.ingest(doc2, mode="async")
        batch_id_2 = batch_manager.flush_queue(force=True)

        assert batch_id_1 != batch_id_2, "Батчи должны иметь разные ID"

        # Устанавливаем разные статусы
        job1 = BatchJobModel.get_by_id(batch_id_1)
        job2 = BatchJobModel.get_by_id(batch_id_2)

        mock_batch_client.set_job_status(job1.google_job_id, "SUCCEEDED")
        mock_batch_client.set_job_status(job2.google_job_id, "RUNNING")

        # Синхронизируем
        statuses = batch_manager.sync_status()

        # Первый должен завершиться, второй - ещё в процессе
        assert statuses[batch_id_1] == "COMPLETED", "Batch 1 должен быть COMPLETED"
        assert statuses[batch_id_2] == "PROCESSING", "Batch 2 должен быть PROCESSING"

        # Проверяем статусы в БД
        job1 = BatchJobModel.get_by_id(batch_id_1)
        job2 = BatchJobModel.get_by_id(batch_id_2)

        assert job1.status == "COMPLETED"
        assert job2.status == "PROCESSING"
