"""Менеджер управления очередью батч-заданий.

Предоставляет высокоуровневое API для работы с асинхронной векторизацией.

Классы:
    BatchManager
        Координатор батч-обработки эмбеддингов.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Dict, List

from semantic_core.domain import GoogleKeyring
from semantic_core.infrastructure.gemini import GeminiBatchClient
from semantic_core.infrastructure.storage.peewee.models import (
    BatchJobModel,
    ChunkModel,
    BatchStatus,
    EmbeddingStatus,
)
from semantic_core.interfaces import BaseVectorStore

if TYPE_CHECKING:
    from semantic_core.config import SemanticConfig


class BatchManager:
    """Менеджер управления батч-очередью эмбеддингов.

    Координирует процесс асинхронной векторизации:
    1. Формирует батчи из PENDING чанков.
    2. Отправляет задания в Google Batch API.
    3. Синхронизирует статусы и результаты.
    4. Обновляет векторы через VectorStore.

    Attributes:
        keyring: Контейнер с API-ключами.
        vector_store: Хранилище для массового обновления векторов.
        batch_client: Клиент Google Batch API.

    Examples:
        >>> keys = GoogleKeyring(default="...", batch="...")
        >>> manager = BatchManager(keys, vector_store)
        >>>
        >>> # Отправить чанки на обработку
        >>> batch_id = manager.flush_queue(min_size=10)
        >>>
        >>> # Проверить статусы и скачать результаты
        >>> manager.sync_status()
    """

    def __init__(
        self,
        keyring: GoogleKeyring,
        vector_store: BaseVectorStore,
        model_name: str = "models/gemini-embedding-001",
        dimension: int = 768,
    ):
        """Инициализация менеджера.

        Args:
            keyring: GoogleKeyring с настроенными ключами.
            vector_store: Адаптер для массового обновления векторов.
            model_name: Название модели Gemini.
            dimension: Размерность векторов.

        Raises:
            ValueError: Если batch_key не установлен в keyring.
        """
        self.keyring = keyring
        self.vector_store = vector_store

        # Инициализируем батч-клиент с выделенным ключом
        self.batch_client = GeminiBatchClient(
            api_key=keyring.get_batch_key(),
            model_name=model_name,
            dimension=dimension,
        )

    @classmethod
    def from_config(
        cls,
        config: SemanticConfig,
        vector_store: BaseVectorStore,
    ) -> "BatchManager":
        """Создаёт BatchManager из конфигурации.

        Factory-метод для создания экземпляра с параметрами из SemanticConfig.

        Args:
            config: Конфигурация Semantic Core.
            vector_store: Хранилище для массового обновления векторов.

        Returns:
            Инициализированный BatchManager.

        Raises:
            ValueError: Если batch_key не настроен.

        Example:
            >>> from semantic_core.config import get_config
            >>> config = get_config()
            >>> manager = BatchManager.from_config(config, vector_store)
        """
        keyring = GoogleKeyring(
            default=config.require_api_key(),
            batch=config.gemini_batch_key,
        )
        return cls(
            keyring=keyring,
            vector_store=vector_store,
            model_name=config.embedding_model,
            dimension=config.embedding_dimension,
        )

    def flush_queue(
        self,
        min_size: int = 10,
        force: bool = False,
    ) -> Optional[str]:
        """Отправляет PENDING чанки на батч-обработку.

        Args:
            min_size: Минимальный размер батча.
                Если чанков меньше, ничего не делает (если не force=True).
            force: Игнорировать min_size и отправить даже маленький батч.

        Returns:
            UUID батч-задания или None, если нечего отправлять.

        Raises:
            RuntimeError: Если не удалось создать задание.

        Examples:
            >>> # Отправить только если накопилось >= 10 чанков
            >>> batch_id = manager.flush_queue(min_size=10)
            >>>
            >>> # Принудительно отправить всё, что есть
            >>> batch_id = manager.flush_queue(force=True)
        """
        # Находим все PENDING чанки без batch_job
        pending_chunks = ChunkModel.select().where(
            (ChunkModel.embedding_status == EmbeddingStatus.PENDING.value)
            & (ChunkModel.batch_job.is_null())
        )

        chunk_count = pending_chunks.count()

        # Проверяем минимальный размер
        if not force and chunk_count < min_size:
            print(
                f"[BatchManager] Недостаточно чанков ({chunk_count} < {min_size}). "
                f"Используйте force=True для принудительной отправки."
            )
            return None

        if chunk_count == 0:
            print("[BatchManager] Нет чанков в очереди.")
            return None

        # Извлекаем метаданные для контекста
        context_texts = {}
        chunk_objects = []

        for chunk_model in pending_chunks:
            # Парсим metadata для получения _vector_source
            meta = json.loads(chunk_model.metadata)
            vector_text = meta.get("_vector_source", chunk_model.content)
            context_texts[str(chunk_model.id)] = vector_text

            # Сохраняем объект для дальнейшего использования
            chunk_objects.append(chunk_model)

        # Создаём батч-задание в Google
        from semantic_core.domain import Chunk  # Для передачи в batch_client

        chunks_dto = [
            Chunk(
                id=str(c.id),
                content=c.content,
                chunk_type=c.chunk_type,
                language=c.language,
                metadata=json.loads(c.metadata),
                chunk_index=c.chunk_index,
            )
            for c in chunk_objects
        ]

        try:
            google_job_id = self.batch_client.create_embedding_job(
                chunks=chunks_dto,
                context_texts=context_texts,
            )
        except Exception as e:
            raise RuntimeError(f"Не удалось создать батч-задание: {e}")

        # Создаём запись BatchJob в БД
        batch_id = str(uuid.uuid4())
        batch_job = BatchJobModel.create(
            id=batch_id,
            google_job_id=google_job_id,
            status=BatchStatus.SUBMITTED.value,
            stats=json.dumps(
                {
                    "submitted": chunk_count,
                    "succeeded": 0,
                    "failed": 0,
                }
            ),
        )

        # Привязываем чанки к батчу
        ChunkModel.update(batch_job=batch_job).where(
            ChunkModel.id.in_([c.id for c in chunk_objects])
        ).execute()

        print(
            f"[BatchManager] Создан батч {batch_id[:8]}... "
            f"с {chunk_count} чанками. Google Job: {google_job_id}"
        )

        return batch_id

    def sync_status(self) -> Dict[str, str]:
        """Синхронизирует статусы активных батч-заданий.

        Проверяет все задания в статусах SUBMITTED/PROCESSING.
        Если задание завершено (COMPLETED), скачивает результаты
        и обновляет векторы в БД.

        Returns:
            Словарь {batch_id -> новый статус}.

        Examples:
            >>> statuses = manager.sync_status()
            >>> print(statuses)
            {'abc123...': 'COMPLETED', 'def456...': 'PROCESSING'}
        """
        # Находим активные батчи
        active_jobs = BatchJobModel.select().where(
            BatchJobModel.status.in_(
                [
                    BatchStatus.SUBMITTED.value,
                    BatchStatus.PROCESSING.value,
                ]
            )
        )

        results = {}

        for job in active_jobs:
            try:
                # Проверяем статус в Google
                google_status = self.batch_client.get_job_status(job.google_job_id)

                # Обновляем локальный статус
                if google_status == "SUCCEEDED":
                    self._process_completed_job(job)
                    job.status = BatchStatus.COMPLETED.value
                    results[job.id] = "COMPLETED"

                elif google_status in ["FAILED", "CANCELLED"]:
                    job.status = BatchStatus.FAILED.value
                    results[job.id] = "FAILED"

                    # Помечаем чанки как FAILED
                    ChunkModel.update(
                        embedding_status=EmbeddingStatus.FAILED.value,
                        error_message=f"Батч завершился с ошибкой: {google_status}",
                    ).where(ChunkModel.batch_job == job).execute()

                elif google_status in ["RUNNING", "QUEUED"]:
                    job.status = BatchStatus.PROCESSING.value
                    results[job.id] = "PROCESSING"

                # Обновляем timestamp
                job.updated_at = datetime.now()
                job.save()

            except Exception as e:
                print(f"[BatchManager] Ошибка при проверке {job.id[:8]}...: {e}")
                results[job.id] = "ERROR"

        return results

    def _process_completed_job(self, job: BatchJobModel) -> None:
        """Обрабатывает завершённое задание: скачивает и сохраняет векторы.

        Args:
            job: Модель BatchJobModel в статусе SUCCEEDED.

        Raises:
            RuntimeError: Если не удалось обработать результаты.
        """
        try:
            # Скачиваем результаты из Google
            vectors_dict = self.batch_client.retrieve_results(job.google_job_id)

            # Массово обновляем векторы через VectorStore
            updated_count = self.vector_store.bulk_update_vectors(vectors_dict)

            # Обновляем статистику
            stats = json.loads(job.stats)
            stats["succeeded"] = updated_count
            stats["failed"] = stats["submitted"] - updated_count
            job.stats = json.dumps(stats)

            print(
                f"[BatchManager] Обработан батч {job.id[:8]}... "
                f"Обновлено векторов: {updated_count}/{stats['submitted']}"
            )

        except Exception as e:
            raise RuntimeError(f"Ошибка при обработке завершённого батча: {e}")

    def get_queue_stats(self) -> Dict[str, int]:
        """Получить статистику очереди.

        Returns:
            Словарь со счётчиками чанков по статусам.

        Examples:
            >>> stats = manager.get_queue_stats()
            >>> print(stats)
            {'pending': 42, 'processing': 10, 'ready': 1000, 'failed': 2}
        """
        return {
            "pending": ChunkModel.select()
            .where(ChunkModel.embedding_status == EmbeddingStatus.PENDING.value)
            .count(),
            "processing": ChunkModel.select()
            .where(
                (ChunkModel.embedding_status == EmbeddingStatus.PENDING.value)
                & (ChunkModel.batch_job.is_null(False))
            )
            .count(),
            "ready": ChunkModel.select()
            .where(ChunkModel.embedding_status == EmbeddingStatus.READY.value)
            .count(),
            "failed": ChunkModel.select()
            .where(ChunkModel.embedding_status == EmbeddingStatus.FAILED.value)
            .count(),
        }
