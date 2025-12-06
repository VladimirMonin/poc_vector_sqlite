"""OCRStep — разбивка OCR текста на чанки через SmartSplitter.

Этот шаг извлекает ocr_text из analysis и разбивает его на чанки
с использованием BaseSplitter. Поддерживает два режима парсинга:
- markdown: для видео с кодом (MarkdownNodeParser детектит code blocks)
- plain: для обычного текста (SimpleSplitter)

Архитектурный контекст:
-----------------------
- Phase 14.1.1: Smart Steps Implementation
- Заменяет логику _split_ocr_into_chunks() из legacy pipeline.py
- Мониторинг code_ratio для обнаружения false positives (UI text как code)

Пример использования:
--------------------
>>> from semantic_core.processing.splitters.smart import SmartSplitter
>>> from semantic_core.processing.parsers.markdown import MarkdownNodeParser
>>> 
>>> # Инициализация splitter с Markdown парсером
>>> parser = MarkdownNodeParser()
>>> splitter = SmartSplitter(parser=parser, ...)
>>> 
>>> # Создание шага с markdown режимом (для видео с кодом)
>>> step = OCRStep(splitter=splitter, parser_mode="markdown")
>>> 
>>> # Контекст с OCR текстом
>>> context = MediaContext(
...     media_path=Path("screencast.mp4"),
...     document=Document(...),
...     analysis={"type": "video", "ocr_text": "# Code\\n```python\\nprint('hello')\\n```"},
...     chunks=[],
...     base_index=5,  # После summary + transcript chunks
... )
>>> 
>>> new_context = step.process(context)
>>> # OCR текст разбит на чанки, code blocks изолированы в ChunkType.CODE
"""

from pathlib import Path
from typing import Literal

from semantic_core.core.media_context import MediaContext
from semantic_core.domain import Chunk, ChunkType, Document, MediaType
from semantic_core.interfaces.splitter import BaseSplitter
from semantic_core.processing.steps.base import BaseProcessingStep
from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)


class OCRStep(BaseProcessingStep):
    """Разбивает OCR текст на чанки через SmartSplitter.
    
    Поддерживает Markdown-парсинг для обнаружения code blocks в видео с кодом.
    
    Attributes:
        splitter: Экземпляр BaseSplitter для чанкинга.
        default_chunk_size: Размер чанка для OCR текста (токены).
        parser_mode: Режим парсинга ("markdown" или "plain").
    
    Example:
        >>> from semantic_core.processing.splitters.smart import SmartSplitter
        >>> splitter = SmartSplitter(...)
        >>> 
        >>> # Для видео с кодом — markdown режим
        >>> step = OCRStep(
        ...     splitter=splitter,
        ...     default_chunk_size=1800,
        ...     parser_mode="markdown",
        ... )
        >>> 
        >>> context = MediaContext(
        ...     media_path=Path("tutorial.mp4"),
        ...     document=Document(...),
        ...     analysis={"ocr_text": "Code from video..."},
        ...     chunks=[],
        ...     base_index=0,
        ... )
        >>> new_context = step.process(context)
        >>> # Code blocks изолированы в ChunkType.CODE
    """
    
    def __init__(
        self,
        splitter: BaseSplitter,
        default_chunk_size: int = 1800,
        parser_mode: Literal["markdown", "plain"] = "markdown",
    ):
        """Инициализация шага.
        
        Args:
            splitter: Сплиттер для разбиения OCR текста.
                Рекомендуется SmartSplitter с MarkdownNodeParser для markdown режима.
            default_chunk_size: Размер чанка в токенах для OCR текста.
                Default 1800. Временно меняет splitter.chunk_size на время обработки.
            parser_mode: Режим парсинга:
                - "markdown": используется для видео с кодом (детектит code blocks)
                - "plain": обычный текст без структуры
        """
        self.splitter = splitter
        self.default_chunk_size = default_chunk_size
        self.parser_mode = parser_mode
    
    @property
    def step_name(self) -> str:
        """Уникальное имя шага."""
        return "ocr"
    
    def should_run(self, context: MediaContext) -> bool:
        """Запускаем только если есть ocr_text в analysis.
        
        Args:
            context: Текущий контекст обработки медиа.
            
        Returns:
            True, если analysis содержит непустой ocr_text.
        """
        return bool(context.analysis.get("ocr_text"))
    
    def process(self, context: MediaContext) -> MediaContext:
        """Разбивает OCR текст на чанки.
        
        Args:
            context: Текущий контекст обработки медиа.
            
        Returns:
            Обновлённый контекст с добавленными OCR чанками.
        """
        ocr_text = context.analysis["ocr_text"]
        
        logger.info(
            f"[{self.step_name}] Splitting OCR text",
            path=str(context.media_path),
            parser_mode=self.parser_mode,
            length=len(ocr_text),
        )
        
        # Создаём временный Document для splitter
        # parser_mode влияет на выбор parser в SmartSplitter, но MediaType всегда TEXT
        temp_doc = Document(
            content=ocr_text,
            metadata={"source": str(context.media_path)},
            media_type=MediaType.TEXT,
        )
        
        # Временно меняем chunk_size у splitter для OCR
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
        
        # Обогащаем metadata
        ocr_chunks = []
        for idx, chunk in enumerate(split_chunks):
            meta = dict(chunk.metadata or {})
            meta.setdefault("_original_path", str(context.media_path))
            meta["role"] = "ocr"
            meta["parent_media_path"] = str(context.media_path)
            
            # Обновляем chunk_index
            chunk.chunk_index = context.base_index + idx
            chunk.metadata = meta
            
            ocr_chunks.append(chunk)
        
        # Мониторинг code_ratio для обнаружения false positives
        code_chunks = [c for c in ocr_chunks if c.chunk_type == ChunkType.CODE]
        code_ratio = len(code_chunks) / len(ocr_chunks) if ocr_chunks else 0
        
        logger.info(
            f"[{self.step_name}] Created chunks",
            count=len(ocr_chunks),
            code_chunks=len(code_chunks),
            code_ratio=f"{code_ratio:.2%}",
        )
        
        # WARNING: Если code_ratio > 50%, возможны ложные срабатывания (UI text как code)
        if code_ratio > 0.5:
            logger.warning(
                f"[{self.step_name}] High code ratio detected (possibly UI text misdetected as code)",
                code_ratio=f"{code_ratio:.2%}",
                path=str(context.media_path),
                code_chunks=len(code_chunks),
                total_chunks=len(ocr_chunks),
            )
        
        return context.with_chunks(ocr_chunks)
