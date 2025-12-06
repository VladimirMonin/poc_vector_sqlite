"""TranscriptionStep — разбивка транскрипции на чанки через SmartSplitter.

Этот шаг извлекает transcription из analysis и разбивает её на чанки
с использованием BaseSplitter. Поддерживает Constructor Injection
для гибкой настройки splitter.

Архитектурный контекст:
-----------------------
- Phase 14.1.1: Smart Steps Implementation
- Заменяет логику _split_transcription_into_chunks() из legacy pipeline.py
- Использует BaseSplitter для разбивки (обычно SmartSplitter)

Пример использования:
--------------------
>>> from semantic_core.processing.splitters.smart import SmartSplitter
>>> from semantic_core.processing.parsers.markdown import MarkdownNodeParser
>>> from semantic_core.processing.context.hierarchical import HierarchicalContextStrategy
>>> 
>>> # Инициализация splitter
>>> parser = MarkdownNodeParser()
>>> context_strategy = HierarchicalContextStrategy()
>>> splitter = SmartSplitter(parser=parser, context_strategy=context_strategy)
>>> 
>>> # Создание шага
>>> step = TranscriptionStep(splitter=splitter)
>>> 
>>> # Контекст с транскрипцией
>>> context = MediaContext(
...     media_path=Path("podcast.mp3"),
...     document=Document(...),
...     analysis={"type": "audio", "transcription": "Long transcript..."},
...     chunks=[],
...     base_index=1,  # После summary chunk
... )
>>> 
>>> new_context = step.process(context)
>>> # Транскрипция разбита на чанки с role='transcript'
"""

from pathlib import Path

from semantic_core.core.media_context import MediaContext
from semantic_core.domain import Document, MediaType
from semantic_core.interfaces.splitter import BaseSplitter
from semantic_core.processing.steps.base import BaseProcessingStep
from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)


class TranscriptionStep(BaseProcessingStep):
    """Разбивает транскрипцию на чанки через SmartSplitter.
    
    Attributes:
        splitter: Экземпляр BaseSplitter для чанкинга.
    
    Example:
        >>> from semantic_core.processing.splitters.smart import SmartSplitter
        >>> splitter = SmartSplitter(...)
        >>> step = TranscriptionStep(splitter=splitter)
        >>> context = MediaContext(
        ...     media_path=Path("audio.mp3"),
        ...     document=Document(...),
        ...     analysis={"transcription": "Full transcript text"},
        ...     chunks=[],
        ...     base_index=1,
        ... )
        >>> new_context = step.process(context)
        >>> # Чанки с role='transcript' созданы
    """
    
    def __init__(self, splitter: BaseSplitter):
        """Инициализация шага.
        
        Args:
            splitter: Сплиттер для разбиения транскрипции.
                Обычно SmartSplitter с MarkdownNodeParser.
        """
        self.splitter = splitter
    
    @property
    def step_name(self) -> str:
        """Уникальное имя шага."""
        return "transcription"
    
    def should_run(self, context: MediaContext) -> bool:
        """Запускаем только если есть transcription в analysis.
        
        Args:
            context: Текущий контекст обработки медиа.
            
        Returns:
            True, если analysis содержит непустую transcription.
        """
        return bool(context.analysis.get("transcription"))
    
    def process(self, context: MediaContext) -> MediaContext:
        """Разбивает транскрипцию на чанки.
        
        Args:
            context: Текущий контекст обработки медиа.
            
        Returns:
            Обновлённый контекст с добавленными transcript чанками.
        """
        transcription = context.analysis["transcription"]
        
        logger.info(
            f"[{self.step_name}] Splitting transcription",
            path=str(context.media_path),
            length=len(transcription),
        )
        
        # Создаём временный Document для splitter
        temp_doc = Document(
            content=transcription,
            metadata={"source": str(context.media_path)},
            media_type=MediaType.TEXT,
        )
        
        # Режем через splitter
        split_chunks = self.splitter.split(temp_doc)
        
        # Обогащаем metadata
        transcript_chunks = []
        for idx, chunk in enumerate(split_chunks):
            meta = dict(chunk.metadata or {})
            meta.setdefault("_original_path", str(context.media_path))
            meta["role"] = "transcript"
            meta["parent_media_path"] = str(context.media_path)
            
            # Обновляем chunk_index
            chunk.chunk_index = context.base_index + idx
            chunk.metadata = meta
            
            transcript_chunks.append(chunk)
        
        logger.info(
            f"[{self.step_name}] Created chunks",
            count=len(transcript_chunks),
            avg_size=(
                sum(len(c.content) for c in transcript_chunks) // len(transcript_chunks)
                if transcript_chunks
                else 0
            ),
        )
        
        return context.with_chunks(transcript_chunks)
