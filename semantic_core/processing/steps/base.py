"""Processing steps base classes and exceptions.

Этот модуль содержит базовые классы для step-based media processing pipeline:
- ProcessingStepError: Исключение для ошибок в шагах
- BaseProcessingStep: Абстрактный базовый класс для всех шагов

Архитектурный контекст:
-----------------------
- Phase 14.1.0: Core Architecture — фундамент step-based pipeline
- Заменяет монолитную логику _build_media_chunks() модульными шагами
- Каждый шаг реализует один аспект обработки (summary, transcription, OCR)

Пример реализации кастомного шага:
---------------------------------
>>> from semantic_core.processing.steps.base import BaseProcessingStep
>>> from semantic_core.core.media_context import MediaContext
>>> from semantic_core.domain import Chunk
>>> 
>>> class SentimentStep(BaseProcessingStep):
...     @property
...     def step_name(self) -> str:
...         return "sentiment"
...     
...     def process(self, context: MediaContext) -> MediaContext:
...         # Анализируем sentiment через LLM
...         sentiment = analyze_sentiment(context.document.content)
...         
...         # Создаём metadata chunk
...         chunk = Chunk(
...             content="",
...             chunk_index=context.base_index,
...             metadata={"sentiment": sentiment, "role": "metadata"},
...         )
...         
...         return context.with_chunks([chunk])
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from semantic_core.core.media_context import MediaContext


class ProcessingStepError(Exception):
    """Исключение при ошибке обработки в processing step.
    
    Используется для ошибок, которые не должны останавливать весь pipeline
    (если step.is_optional == True).
    
    Attributes:
        step_name: Имя шага, где произошла ошибка
        context: MediaContext на момент ошибки (опционально)
        original_error: Оригинальное исключение (если есть)
    
    Example:
        >>> try:
        ...     result = gemini_api.analyze(image)
        ... except APIError as e:
        ...     raise ProcessingStepError(
        ...         step_name="ocr",
        ...         message="Gemini API failed",
        ...         context=context,
        ...     ) from e
    """
    
    def __init__(
        self,
        step_name: str,
        message: str,
        context: "MediaContext | None" = None,
    ):
        """Инициализация.
        
        Args:
            step_name: Имя шага (например, "summary", "transcription")
            message: Описание ошибки
            context: Контекст обработки на момент ошибки
        """
        self.step_name = step_name
        self.context = context
        super().__init__(f"[{step_name}] {message}")


class BaseProcessingStep(ABC):
    """Базовый класс для шага обработки медиа-файла.
    
    Каждый шаг получает MediaContext, обрабатывает его и возвращает
    обновлённый контекст с добавленными чанками.
    
    Lifecycle:
        1. MediaPipeline проверяет should_run()
        2. Если True — вызывает process()
        3. process() возвращает новый MediaContext
        4. Pipeline передаёт его следующему шагу
    
    Обязательные методы для реализации:
        - step_name: Уникальное имя шага
        - process(): Основная логика обработки
    
    Опциональные методы для переопределения:
        - should_run(): Условие запуска шага
        - is_optional: Флаг опциональности (если True, ошибка не останавливает pipeline)
    
    Thread Safety:
        Шаги должны быть stateless — вся state храниться в MediaContext.
        Можно безопасно переиспользовать один экземпляр шага для разных файлов.
    
    Example:
        >>> class SummaryStep(BaseProcessingStep):
        ...     @property
        ...     def step_name(self) -> str:
        ...         return "summary"
        ...     
        ...     def process(self, context: MediaContext) -> MediaContext:
        ...         summary_chunk = self._create_summary(context.analysis)
        ...         return context.with_chunks([summary_chunk])
    """
    
    @property
    @abstractmethod
    def step_name(self) -> str:
        """Уникальное имя шага (для логирования и rerun).
        
        Должно быть lowercase, snake_case.
        Примеры: "summary", "transcription", "ocr", "sentiment".
        
        Используется:
        - В логах для трассировки
        - В SemanticCore.rerun_step() для повторного запуска
        - В metadata['role'] для фильтрации чанков
        
        Returns:
            Имя шага
        """
        pass
    
    @abstractmethod
    def process(self, context: "MediaContext") -> "MediaContext":
        """Обрабатывает контекст и возвращает обновлённый.
        
        Это основной метод шага. Должен быть чистой функцией:
        - Не модифицировать входной context
        - Не иметь side effects (кроме логирования)
        - Возвращать новый MediaContext через context.with_chunks()
        
        Args:
            context: Текущий контекст обработки
        
        Returns:
            Новый MediaContext с добавленными чанками
        
        Raises:
            ProcessingStepError: При ошибках обработки (если is_optional=False)
        
        Example:
            >>> def process(self, context: MediaContext) -> MediaContext:
            ...     analysis = context.analysis
            ...     
            ...     # Создаём чанки
            ...     chunks = self._build_chunks(analysis)
            ...     
            ...     # Возвращаем обновлённый контекст
            ...     return context.with_chunks(chunks)
        """
        pass
    
    @property
    def is_optional(self) -> bool:
        """Флаг опциональности шага.
        
        Если True:
        - Ошибка в process() логируется, но не останавливает pipeline
        - Pipeline продолжает выполнение следующих шагов
        
        Если False (по умолчанию):
        - Ошибка в process() пробрасывается выше
        - Pipeline останавливается
        
        Returns:
            True если шаг опциональный, False если критичный
        
        Example:
            >>> class OptionalOCRStep(BaseProcessingStep):
            ...     @property
            ...     def is_optional(self) -> bool:
            ...         return True  # OCR может провалиться, это не критично
        """
        return False
    
    def should_run(self, context: "MediaContext") -> bool:
        """Проверяет, нужно ли запускать шаг для данного контекста.
        
        Позволяет пропустить шаг на основе analysis или других условий.
        
        Args:
            context: Контекст обработки
        
        Returns:
            True если шаг нужно запустить, False если пропустить
        
        Example:
            >>> def should_run(self, context: MediaContext) -> bool:
            ...     # Запускаем только если есть transcription
            ...     return bool(context.analysis.get("transcription"))
        """
        return True
