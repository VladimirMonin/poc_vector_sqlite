"""Интерфейсы (контракты) для компонентов системы.

Классы:
    BaseEmbedder
        Абстрактный интерфейс для генераторов эмбеддингов.
    BaseVectorStore
        Абстрактный интерфейс для хранилища векторов.
    BaseSplitter
        Абстрактный интерфейс для нарезки текста.
    BaseContextStrategy
        Абстрактный интерфейс для формирования контекста.
    DocumentParser
        Протокол для парсеров документов.
    ParsingSegment
        Промежуточная структура между парсингом и чанкингом.
    BaseLLMProvider
        Абстрактный интерфейс для LLM провайдеров.
    GenerationResult
        DTO с результатом генерации от LLM.
    BaseChatHistoryStrategy
        Абстрактная стратегия управления историей чата.
    ChatMessage
        DTO сообщения в истории чата.
    ITranscriber
        Абстрактный интерфейс для транскрибации аудио.
    TranscriptionResult
        DTO с результатом транскрипции.
    TranscriptionSegment
        Сегмент транскрипции с таймкодами.
    IVisionAnalyzer
        Абстрактный интерфейс для анализа изображений.
    VisionResult
        DTO с результатом анализа изображения.
"""

from semantic_core.interfaces.embedder import BaseEmbedder
from semantic_core.interfaces.vector_store import BaseVectorStore
from semantic_core.interfaces.splitter import BaseSplitter
from semantic_core.interfaces.context import BaseContextStrategy
from semantic_core.interfaces.parser import DocumentParser, ParsingSegment
from semantic_core.interfaces.llm import BaseLLMProvider, GenerationResult
from semantic_core.interfaces.chat_history import BaseChatHistoryStrategy, ChatMessage
from semantic_core.interfaces.transcriber import (
    ITranscriber,
    TranscriptionResult,
    TranscriptionSegment,
)
from semantic_core.interfaces.vision import IVisionAnalyzer, VisionResult

__all__ = [
    "BaseEmbedder",
    "BaseVectorStore",
    "BaseSplitter",
    "BaseContextStrategy",
    "DocumentParser",
    "ParsingSegment",
    "BaseLLMProvider",
    "GenerationResult",
    "BaseChatHistoryStrategy",
    "ChatMessage",
    "ITranscriber",
    "TranscriptionResult",
    "TranscriptionSegment",
    "IVisionAnalyzer",
    "VisionResult",
]
