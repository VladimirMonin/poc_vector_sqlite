"""Обработчик очереди медиа-задач.

Классы:
    MediaQueueProcessor
        Обрабатывает задачи из очереди с Rate Limiting.
        Роутит на нужный анализатор по типу медиа.
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
    VideoAnalysisConfig,
)
from semantic_core.infrastructure.storage.peewee.models import MediaTaskModel
from semantic_core.infrastructure.media.utils.audio import is_audio_supported
from semantic_core.infrastructure.media.utils.video import is_video_supported
from semantic_core.utils.logger import get_logger

if TYPE_CHECKING:
    from semantic_core.infrastructure.gemini.image_analyzer import GeminiImageAnalyzer
    from semantic_core.infrastructure.gemini.audio_analyzer import GeminiAudioAnalyzer
    from semantic_core.infrastructure.gemini.video_analyzer import GeminiVideoAnalyzer
    from semantic_core.infrastructure.gemini.rate_limiter import RateLimiter

logger = get_logger(__name__)


class MediaQueueProcessor:
    """Обработчик очереди медиа-задач.

    Извлекает pending задачи из БД, роутит на нужный анализатор
    по mime-type, и сохраняет результаты.

    Поддерживаемые типы:
    - image/* → GeminiImageAnalyzer
    - audio/* → GeminiAudioAnalyzer
    - video/* → GeminiVideoAnalyzer

    Attributes:
        image_analyzer: Анализатор изображений.
        audio_analyzer: Анализатор аудио (опционально).
        video_analyzer: Анализатор видео (опционально).
        rate_limiter: Rate Limiter для контроля RPM.
        embedder: Опциональный embedder для создания чанков.
        store: Опциональный VectorStore для сохранения чанков.

    Пример использования:
        >>> processor = MediaQueueProcessor(
        ...     image_analyzer=image_analyzer,
        ...     audio_analyzer=audio_analyzer,
        ...     video_analyzer=video_analyzer,
        ...     rate_limiter=limiter,
        ... )
        >>> processed = processor.process_batch(max_tasks=10)
        >>> print(f"Processed {processed} tasks")
    """

    def __init__(
        self,
        image_analyzer: Optional["GeminiImageAnalyzer"] = None,
        rate_limiter: Optional["RateLimiter"] = None,
        audio_analyzer: Optional["GeminiAudioAnalyzer"] = None,
        video_analyzer: Optional["GeminiVideoAnalyzer"] = None,
        video_config: Optional[VideoAnalysisConfig] = None,
        embedder=None,
        store=None,
        # Обратная совместимость с Phase 6.0
        analyzer: Optional["GeminiImageAnalyzer"] = None,
    ):
        """Инициализация процессора.

        Args:
            image_analyzer: Анализатор изображений (опциональный).
            rate_limiter: Rate Limiter для API.
            audio_analyzer: Анализатор аудио (опциональный).
            video_analyzer: Анализатор видео (опциональный).
            video_config: Конфигурация для видео-анализа.
            embedder: Опциональный embedder (для создания векторов).
            store: Опциональный VectorStore (для сохранения чанков).
            analyzer: DEPRECATED - используй image_analyzer.
        """
        # Обратная совместимость: analyzer → image_analyzer
        if analyzer is not None and image_analyzer is None:
            image_analyzer = analyzer

        # Хотя бы один анализатор должен быть передан
        if not any([image_analyzer, audio_analyzer, video_analyzer]):
            raise ValueError(
                "At least one analyzer (image/audio/video) must be provided"
            )
        if rate_limiter is None:
            raise ValueError("rate_limiter is required")

        self.image_analyzer = image_analyzer
        self.audio_analyzer = audio_analyzer
        self.video_analyzer = video_analyzer
        self.video_config = video_config or VideoAnalysisConfig()
        self.rate_limiter = rate_limiter
        self.embedder = embedder
        self.store = store

        # Для обратной совместимости
        self.analyzer = image_analyzer

        logger.info(
            "MediaQueueProcessor initialized",
            has_image_analyzer=True,
            has_audio_analyzer=audio_analyzer is not None,
            has_video_analyzer=video_analyzer is not None,
            has_embedder=embedder is not None,
            has_store=store is not None,
        )

    def process_one(self) -> bool:
        """Обрабатывает одну задачу из очереди.

        Returns:
            True если задача была обработана (успешно или с ошибкой).
            False если очередь пуста.
        """
        # Получаем pending задачу
        task = self._get_pending_task()
        if not task:
            logger.trace("No pending tasks in queue")
            return False

        task_logger = logger.bind(task_id=task.id, mime_type=task.mime_type)
        task_logger.debug("Processing task", media_path=task.media_path)

        # Обновляем статус
        self._update_status(task.id, TaskStatus.PROCESSING)

        try:
            # Rate limiting
            self.rate_limiter.wait()

            # Конвертируем в request
            request = self._to_request(task)

            # Роутим на нужный анализатор по mime-type
            result = self._route_and_analyze(request, task.mime_type)

            # Сохраняем результат
            self._save_result(task.id, result)

            task_logger.info(
                "Task completed successfully",
                has_description=bool(result.description),
                keywords_count=len(result.keywords) if result.keywords else 0,
            )

            return True

        except Exception as e:
            # Обновляем статус с ошибкой
            self._update_status(task.id, TaskStatus.FAILED, error=str(e))
            task_logger.error_with_context(
                "Task processing failed",
                e,
                media_path=task.media_path,
            )
            return True

    def _route_and_analyze(
        self,
        request: MediaRequest,
        mime_type: str,
    ) -> MediaAnalysisResult:
        """Роутит запрос на нужный анализатор по mime-type.

        Args:
            request: Запрос на анализ.
            mime_type: MIME-тип медиа.

        Returns:
            Результат анализа.

        Raises:
            ValueError: Если тип медиа не поддерживается.
        """
        if is_audio_supported(mime_type):
            if self.audio_analyzer is None:
                logger.error("Audio analyzer not configured", mime_type=mime_type)
                raise ValueError(
                    f"Audio analyzer not configured, cannot process {mime_type}"
                )
            logger.debug("Routing to audio analyzer", mime_type=mime_type)
            return self.audio_analyzer.analyze(request)

        elif is_video_supported(mime_type):
            if self.video_analyzer is None:
                logger.error("Video analyzer not configured", mime_type=mime_type)
                raise ValueError(
                    f"Video analyzer not configured, cannot process {mime_type}"
                )
            logger.debug("Routing to video analyzer", mime_type=mime_type)
            return self.video_analyzer.analyze(request, self.video_config)

        elif mime_type.startswith("image/"):
            logger.debug("Routing to image analyzer", mime_type=mime_type)
            return self.image_analyzer.analyze(request)

        else:
            logger.error("Unsupported media type", mime_type=mime_type)
            raise ValueError(f"Unsupported media type: {mime_type}")

    def process_batch(self, max_tasks: int = 10) -> int:
        """Обрабатывает пачку задач.

        Args:
            max_tasks: Максимальное количество задач.

        Returns:
            Количество обработанных задач.
        """
        logger.info("Starting batch processing", max_tasks=max_tasks)
        processed = 0
        for _ in range(max_tasks):
            if not self.process_one():
                break
            processed += 1
        logger.info("Batch processing completed", processed=processed)
        return processed

    def process_task(self, task_id: str) -> bool:
        """Обрабатывает конкретную задачу по ID.

        Args:
            task_id: ID задачи.

        Returns:
            True если успешно, False при ошибке.
        """
        task_logger = logger.bind(task_id=task_id)
        task = MediaTaskModel.get_or_none(MediaTaskModel.id == task_id)
        if not task:
            task_logger.warning("Task not found")
            return False

        task_logger.debug("Processing specific task", mime_type=task.mime_type)
        self._update_status(task.id, TaskStatus.PROCESSING)

        try:
            self.rate_limiter.wait()
            request = self._to_request(task)
            result = self._route_and_analyze(request, task.mime_type)
            self._save_result(task.id, result)
            task_logger.info("Task completed successfully")
            return True
        except Exception as e:
            self._update_status(task.id, TaskStatus.FAILED, error=str(e))
            task_logger.error_with_context("Task processing failed", e)
            return False

    def get_pending_count(self) -> int:
        """Возвращает количество задач в очереди.

        Returns:
            Количество pending задач.
        """
        count = (
            MediaTaskModel.select()
            .where(MediaTaskModel.status == TaskStatus.PENDING.value)
            .count()
        )
        logger.trace("Got pending count", count=count)
        return count

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
        update_data = {
            "status": TaskStatus.COMPLETED.value,
            "result_description": result.description,
            "result_alt_text": result.alt_text,
            "result_keywords": json.dumps(result.keywords),
            "result_ocr_text": result.ocr_text,
            "result_chunk_id": chunk_id,
            "processed_at": datetime.now(),
        }

        # Audio/Video fields (Phase 6.2)
        if result.transcription:
            update_data["result_transcription"] = result.transcription
        if result.participants:
            update_data["result_participants"] = json.dumps(result.participants)
        if result.action_items:
            update_data["result_action_items"] = json.dumps(result.action_items)
        if result.duration_seconds:
            update_data["result_duration_seconds"] = result.duration_seconds

        MediaTaskModel.update(update_data).where(MediaTaskModel.id == task_id).execute()
