"""Processing steps package — модульная система обработки медиа.

Этот пакет содержит step-based архитектуру для media processing pipeline.

Экспортируемые классы:
- BaseProcessingStep: Абстрактный базовый класс для шагов
- ProcessingStepError: Исключение для ошибок в шагах

Использование:
    from semantic_core.processing.steps import BaseProcessingStep, ProcessingStepError
"""

from semantic_core.processing.steps.base import BaseProcessingStep, ProcessingStepError

__all__ = [
    "BaseProcessingStep",
    "ProcessingStepError",
]
