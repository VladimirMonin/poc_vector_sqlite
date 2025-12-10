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
from typing import Optional

from semantic_core.core.media_context import MediaContext
from semantic_core.domain import Document, MediaType
from semantic_core.interfaces.splitter import BaseSplitter
from semantic_core.processing.steps.base import BaseProcessingStep
from semantic_core.utils.logger import get_logger
from semantic_core.utils.timecode_parser import TimecodeParser

logger = get_logger(__name__)


class TranscriptionStep(BaseProcessingStep):
    """Разбивает транскрипцию на чанки через SmartSplitter.
    
    Attributes:
        splitter: Экземпляр BaseSplitter для чанкинга.
        default_chunk_size: Размер чанка для transcript текста (токены).
        enable_timecodes: Включить парсинг таймкодов [MM:SS] из транскрипции.
    
    Example:
        >>> from semantic_core.processing.splitters.smart import SmartSplitter
        >>> splitter = SmartSplitter(...)
        >>> step = TranscriptionStep(
        ...     splitter=splitter,
        ...     default_chunk_size=2000,
        ...     enable_timecodes=True,
        ... )
        >>> context = MediaContext(
        ...     media_path=Path("audio.mp3"),
        ...     document=Document(...),
        ...     analysis={
        ...         "transcription": "[00:00] Intro\n[05:30] Chapter 1",
        ...         "duration_seconds": 600,
        ...     },
        ...     chunks=[],
        ...     base_index=1,
        ... )
        >>> new_context = step.process(context)
        >>> # Чанки с role='transcript' и start_seconds metadata созданы
    """
    
    def __init__(
        self,
        splitter: BaseSplitter,
        default_chunk_size: int = 2000,
        enable_timecodes: bool = True,
    ):
        """Инициализация шага.
        
        Args:
            splitter: Сплиттер для разбиения транскрипции.
                Обычно SmartSplitter с MarkdownNodeParser.
            default_chunk_size: Размер чанка в токенах для transcript текста.
                Default 2000. Временно меняет splitter.chunk_size на время обработки.
            enable_timecodes: Если True, парсит таймкоды [MM:SS] и добавляет
                start_seconds в metadata. Default True.
        """
        self.splitter = splitter
        self.default_chunk_size = default_chunk_size
        self.enable_timecodes = enable_timecodes
    
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
        """Разбивает транскрипцию на чанки с опциональным парсингом таймкодов.
        
        Args:
            context: Текущий контекст обработки медиа.
            
        Returns:
            Обновлённый контекст с добавленными transcript чанками.
            Metadata включает start_seconds (если enable_timecodes=True).
        """
        transcription = context.analysis["transcription"]
        duration_seconds = context.analysis.get("duration_seconds")
        
        logger.info(
            f"[{self.step_name}] Splitting transcription",
            path=str(context.media_path),
            length=len(transcription),
            enable_timecodes=self.enable_timecodes,
        )
        
        # Инициализируем TimecodeParser если нужен
        timecode_parser: Optional[TimecodeParser] = None
        if self.enable_timecodes:
            timecode_parser = TimecodeParser(
                max_duration_seconds=duration_seconds,
                strict_ordering=False,  # Gemini может ошибиться в порядке
            )
        
        # Создаём временный Document для splitter
        temp_doc = Document(
            content=transcription,
            metadata={"source": str(context.media_path)},
            media_type=MediaType.TEXT,
        )
        
        # Временно меняем chunk_size у splitter для transcript
        original_chunk_size = getattr(self.splitter, 'chunk_size', None)
        if original_chunk_size is not None:
            self.splitter.chunk_size = self.default_chunk_size
        
        try:
            # Режем через splitter
            split_chunks = self.splitter.split(temp_doc)
        finally:
            # Восстанавливаем оригинальный размер
            if original_chunk_size is not None:
                self.splitter.chunk_size = original_chunk_size
        
        # Обогащаем metadata (с таймкодами если enabled)
        transcript_chunks = []
        last_timecode: Optional[int] = None
        
        for idx, chunk in enumerate(split_chunks):
            meta = dict(chunk.metadata or {})
            meta.setdefault("_original_path", str(context.media_path))
            meta["role"] = "transcript"
            meta["parent_media_path"] = str(context.media_path)
            
            # Парсинг таймкода из контента чанка
            if timecode_parser:
                timecode_info = timecode_parser.parse(chunk.content)
                
                if timecode_info:
                    # Найден явный таймкод
                    meta["start_seconds"] = timecode_info.seconds
                    meta["timecode_original"] = timecode_info.original
                    last_timecode = timecode_info.seconds
                else:
                    # Наследуем от предыдущего чанка
                    meta["start_seconds"] = timecode_parser.inherit_timecode(
                        last_timecode_seconds=last_timecode,
                        chunk_position=idx,
                        total_chunks=len(split_chunks),
                        total_duration_seconds=duration_seconds or 0,
                    )
            
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
            with_timecodes=self.enable_timecodes,
        )
        
        return context.with_chunks(transcript_chunks)
