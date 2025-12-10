"""Processing steps package — модульная система обработки медиа.

Этот пакет содержит step-based архитектуру для media processing pipeline.

Экспортируемые классы:
- BaseProcessingStep: Абстрактный базовый класс для шагов
- ProcessingStepError: Исключение для ошибок в шагах
- SummaryStep: Извлечение summary из analysis
- TranscriptionStep: Обработка transcription через splitter
- OCRStep: Обработка OCR текста с мониторингом code ratio

Использование:
    from semantic_core.processing.steps import (
        BaseProcessingStep,
        ProcessingStepError,
        SummaryStep,
        TranscriptionStep,
        OCRStep,
    )
"""

from semantic_core.processing.steps.base import BaseProcessingStep, ProcessingStepError
from semantic_core.processing.steps.ocr import OCRStep
from semantic_core.processing.steps.summary import SummaryStep
from semantic_core.processing.steps.transcription import TranscriptionStep

__all__ = [
    "BaseProcessingStep",
    "ProcessingStepError",
    "SummaryStep",
    "TranscriptionStep",
    "OCRStep",
]
