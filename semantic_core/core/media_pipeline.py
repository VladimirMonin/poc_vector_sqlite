"""MediaPipeline — executor для step-based media processing.

Этот модуль содержит MediaPipeline класс, который оркеструет выполнение
последовательности processing steps для обработки медиа-файлов.

Архитектурный контекст:
-----------------------
- Phase 14.1.0: Core Architecture — фундамент step-based pipeline
- Заменяет монолитный _build_media_chunks() модульной системой
- Используется в SemanticCore.ingest_audio/video/image()

Пример использования:
--------------------
>>> from semantic_core.core.media_pipeline import MediaPipeline
>>> from semantic_core.processing.steps import BaseProcessingStep
>>> from semantic_core.core.media_context import MediaContext
>>> 
>>> # Создаём pipeline с шагами
>>> pipeline = MediaPipeline(steps=[
...     SummaryStep(),
...     TranscriptionStep(splitter=splitter),
...     OCRStep(splitter=splitter),
... ])
>>> 
>>> # Создаём контекст
>>> context = MediaContext(
...     media_path=Path("video.mp4"),
...     document=doc,
...     analysis={"type": "video", ...},
...     chunks=[],
...     base_index=0,
... )
>>> 
>>> # Выполняем pipeline
>>> final_context = pipeline.build_chunks(context)
>>> chunks = final_context.chunks
"""

from typing import TYPE_CHECKING

from semantic_core.processing.steps.base import ProcessingStepError
from semantic_core.utils.logger import get_logger

if TYPE_CHECKING:
    from semantic_core.core.media_context import MediaContext
    from semantic_core.processing.steps.base import BaseProcessingStep

logger = get_logger(__name__)


class MediaPipeline:
    """Executor для step-based media processing pipeline.
    
    Координирует выполнение последовательности processing steps.
    Каждый шаг получает MediaContext, обрабатывает его и возвращает
    обновлённый контекст.
    
    Алгоритм:
        1. Для каждого шага проверяем should_run()
        2. Если True — вызываем process()
        3. Обрабатываем ошибки (опциональные шаги vs критичные)
        4. Передаём обновлённый контекст следующему шагу
    
    Attributes:
        steps: Список processing steps в порядке выполнения
    
    Thread Safety:
        Безопасно для использования из одного потока.
        Для параллельной обработки создавайте отдельные экземпляры.
    
    Example:
        >>> pipeline = MediaPipeline([
        ...     SummaryStep(),
        ...     TranscriptionStep(splitter),
        ... ])
        >>> 
        >>> context = MediaContext(...)
        >>> result = pipeline.build_chunks(context)
        >>> assert len(result.chunks) >= 1
    """
    
    def __init__(self, steps: list["BaseProcessingStep"]):
        """Инициализация pipeline.
        
        Args:
            steps: Список processing steps в порядке выполнения
        """
        self.steps = steps
        
        logger.debug(
            "MediaPipeline initialized",
            step_count=len(steps),
            step_names=[s.step_name for s in steps],
        )
    
    def build_chunks(self, context: "MediaContext") -> "MediaContext":
        """Выполняет все шаги и возвращает финальный контекст.
        
        Args:
            context: Начальный контекст обработки
        
        Returns:
            Финальный MediaContext с чанками от всех шагов
        
        Raises:
            ProcessingStepError: Если критичный шаг (is_optional=False) провалился
        
        Example:
            >>> context = MediaContext(
            ...     media_path=Path("audio.mp3"),
            ...     document=doc,
            ...     analysis={"transcription": "Hello world"},
            ...     chunks=[],
            ...     base_index=0,
            ... )
            >>> 
            >>> result = pipeline.build_chunks(context)
            >>> assert len(result.chunks) > 0
        """
        current_context = context
        executed_steps = []
        
        logger.info(
            "Starting media pipeline",
            path=str(context.media_path),
            total_steps=len(self.steps),
        )
        
        for step in self.steps:
            step_name = step.step_name
            
            # Проверяем, нужно ли запускать шаг
            if not step.should_run(current_context):
                logger.debug(
                    f"Skipping step (should_run=False)",
                    step=step_name,
                    path=str(context.media_path),
                )
                continue
            
            # Выполняем шаг
            try:
                logger.debug(
                    f"Executing step",
                    step=step_name,
                    current_chunks=len(current_context.chunks),
                    base_index=current_context.base_index,
                )
                
                new_context = step.process(current_context)
                
                # Вычисляем сколько чанков добавил шаг
                added_chunks = len(new_context.chunks) - len(current_context.chunks)
                
                logger.info(
                    f"Step completed",
                    step=step_name,
                    added_chunks=added_chunks,
                    total_chunks=len(new_context.chunks),
                )
                
                current_context = new_context
                executed_steps.append(step_name)
            
            except ProcessingStepError as e:
                # Ошибка в шаге
                if step.is_optional:
                    # Опциональный шаг — логируем и продолжаем
                    logger.warning(
                        f"Optional step failed (continuing)",
                        step=step_name,
                        error=str(e),
                        path=str(context.media_path),
                    )
                else:
                    # Критичный шаг — пробрасываем ошибку
                    logger.error(
                        f"Critical step failed (stopping)",
                        step=step_name,
                        error=str(e),
                        executed_steps=executed_steps,
                        path=str(context.media_path),
                    )
                    raise
            
            except Exception as e:
                # Неожиданная ошибка — оборачиваем в ProcessingStepError
                error = ProcessingStepError(
                    step_name=step_name,
                    message=f"Unexpected error: {e!r}",
                    context=current_context,
                )
                
                if step.is_optional:
                    logger.warning(
                        f"Optional step crashed (continuing)",
                        step=step_name,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                else:
                    logger.error(
                        f"Critical step crashed (stopping)",
                        step=step_name,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    raise error from e
        
        logger.info(
            "Media pipeline completed",
            path=str(context.media_path),
            total_chunks=len(current_context.chunks),
            executed_steps=executed_steps,
        )
        
        return current_context
    
    def register_step(
        self,
        step: "BaseProcessingStep",
        position: int | None = None,
    ) -> None:
        """Добавляет новый шаг в pipeline.
        
        Args:
            step: Экземпляр ProcessingStep
            position: Позиция в списке (None = добавить в конец)
        
        Example:
            >>> pipeline = MediaPipeline([SummaryStep()])
            >>> pipeline.register_step(TranscriptionStep(splitter), position=1)
            >>> assert len(pipeline.steps) == 2
        """
        if position is None:
            self.steps.append(step)
            position = len(self.steps) - 1
        else:
            self.steps.insert(position, step)
        
        logger.info(
            "Registered processing step",
            step=step.step_name,
            position=position,
            total_steps=len(self.steps),
        )
