"""Обработчик очереди медиа-задач.

Классы:
    MediaQueueProcessor
        Обрабатывает задачи из очереди с Rate Limiting.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from semantic_core.domain.media import (
    TaskStatus,
    MediaResource,
    MediaRequest,
    MediaAnalysisResult,
)
from semantic_core.infrastructure.storage.peewee.models import MediaTaskModel

if TYPE_CHECKING:
    from semantic_core.infrastructure.gemini.image_analyzer import GeminiImageAnalyzer
    from semantic_core.infrastructure.gemini.rate_limiter import RateLimiter


class MediaQueueProcessor:
    """Обработчик очереди медиа-задач.

    Извлекает pending задачи из БД, анализирует их через Gemini,
    и сохраняет результаты.

    Attributes:
        analyzer: Анализатор изображений.
        rate_limiter: Rate Limiter для контроля RPM.
        embedder: Опциональный embedder для создания чанков.
        store: Опциональный VectorStore для сохранения чанков.

    Пример использования:
        >>> processor = MediaQueueProcessor(
        ...     analyzer=analyzer,
        ...     rate_limiter=limiter,
        ... )
        >>> processed = processor.process_batch(max_tasks=10)
        >>> print(f"Processed {processed} tasks")
    """

    def __init__(
        self,
        analyzer: "GeminiImageAnalyzer",
        rate_limiter: "RateLimiter",
        embedder=None,
        store=None,
    ):
        """Инициализация процессора.

        Args:
            analyzer: Анализатор изображений.
            rate_limiter: Rate Limiter для API.
            embedder: Опциональный embedder (для создания векторов).
            store: Опциональный VectorStore (для сохранения чанков).
        """
        self.analyzer = analyzer
        self.rate_limiter = rate_limiter
        self.embedder = embedder
        self.store = store

    def process_one(self) -> bool:
        """Обрабатывает одну задачу из очереди.

        Returns:
            True если задача была обработана (успешно или с ошибкой).
            False если очередь пуста.
        """
        # Получаем pending задачу
        task = self._get_pending_task()
        if not task:
            return False

        # Обновляем статус
        self._update_status(task.id, TaskStatus.PROCESSING)

        try:
            # Rate limiting
            self.rate_limiter.wait()

            # Конвертируем в request
            request = self._to_request(task)

            # Анализируем
            result = self.analyzer.analyze(request)

            # Сохраняем результат
            self._save_result(task.id, result)

            return True

        except Exception as e:
            # Обновляем статус с ошибкой
            self._update_status(task.id, TaskStatus.FAILED, error=str(e))
            return True

    def process_batch(self, max_tasks: int = 10) -> int:
        """Обрабатывает пачку задач.

        Args:
            max_tasks: Максимальное количество задач.

        Returns:
            Количество обработанных задач.
        """
        processed = 0
        for _ in range(max_tasks):
            if not self.process_one():
                break
            processed += 1
        return processed

    def process_task(self, task_id: str) -> bool:
        """Обрабатывает конкретную задачу по ID.

        Args:
            task_id: ID задачи.

        Returns:
            True если успешно, False при ошибке.
        """
        task = MediaTaskModel.get_or_none(MediaTaskModel.id == task_id)
        if not task:
            return False

        self._update_status(task.id, TaskStatus.PROCESSING)

        try:
            self.rate_limiter.wait()
            request = self._to_request(task)
            result = self.analyzer.analyze(request)
            self._save_result(task.id, result)
            return True
        except Exception as e:
            self._update_status(task.id, TaskStatus.FAILED, error=str(e))
            return False

    def get_pending_count(self) -> int:
        """Возвращает количество задач в очереди.

        Returns:
            Количество pending задач.
        """
        return (
            MediaTaskModel.select()
            .where(MediaTaskModel.status == TaskStatus.PENDING.value)
            .count()
        )

    def _get_pending_task(self) -> Optional[MediaTaskModel]:
        """Получает одну pending задачу.

        Returns:
            MediaTaskModel или None.
        """
        return (
            MediaTaskModel.select()
            .where(MediaTaskModel.status == TaskStatus.PENDING.value)
            .order_by(MediaTaskModel.created_at)
            .first()
        )

    def _update_status(
        self,
        task_id: str,
        status: TaskStatus,
        error: Optional[str] = None,
    ) -> None:
        """Обновляет статус задачи.

        Args:
            task_id: ID задачи.
            status: Новый статус.
            error: Сообщение об ошибке (опционально).
        """
        update_data = {"status": status.value}

        if error:
            update_data["error_message"] = error

        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            update_data["processed_at"] = datetime.now()

        MediaTaskModel.update(update_data).where(MediaTaskModel.id == task_id).execute()

    def _to_request(self, task: MediaTaskModel) -> MediaRequest:
        """Конвертирует модель задачи в MediaRequest.

        Args:
            task: ORM модель задачи.

        Returns:
            MediaRequest для анализатора.
        """
        resource = MediaResource(
            path=Path(task.media_path),
            media_type=task.media_type,
            mime_type=task.mime_type,
        )

        return MediaRequest(
            resource=resource,
            user_prompt=task.user_prompt,
            context_text=task.context_text,
        )

    def _save_result(
        self,
        task_id: str,
        result: MediaAnalysisResult,
        chunk_id: Optional[int] = None,
    ) -> None:
        """Сохраняет результат анализа.

        Args:
            task_id: ID задачи.
            result: Результат анализа.
            chunk_id: ID созданного чанка (опционально).
        """
        MediaTaskModel.update(
            {
                "status": TaskStatus.COMPLETED.value,
                "result_description": result.description,
                "result_alt_text": result.alt_text,
                "result_keywords": json.dumps(result.keywords),
                "result_ocr_text": result.ocr_text,
                "result_chunk_id": chunk_id,
                "processed_at": datetime.now(),
            }
        ).where(MediaTaskModel.id == task_id).execute()
