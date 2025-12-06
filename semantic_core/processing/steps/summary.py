"""SummaryStep — создание summary chunk из результата анализа медиа.

Этот шаг извлекает description из analysis и формирует summary chunk
с соответствующими метаданными. Поддерживает image, audio, video.

Архитектурный контекст:
-----------------------
- Phase 14.1.1: Smart Steps Implementation
- Заменяет логику _build_content_from_analysis() из legacy pipeline.py
- Работает с MediaContext, возвращает обновлённый контекст

Пример использования:
--------------------
>>> from pathlib import Path
>>> from semantic_core.domain import Document
>>> from semantic_core.core.media_context import MediaContext
>>> 
>>> # Анализ изображения
>>> analysis = {
...     "type": "image",
...     "description": "A sunset over mountains",
...     "alt_text": "Sunset landscape",
...     "keywords": ["sunset", "mountains", "nature"]
... }
>>> 
>>> context = MediaContext(
...     media_path=Path("image.jpg"),
...     document=Document(...),
...     analysis=analysis,
...     chunks=[],
...     base_index=0,
... )
>>> 
>>> step = SummaryStep(include_keywords=True)
>>> new_context = step.process(context)
>>> 
>>> # Summary chunk создан
>>> assert len(new_context.chunks) == 1
>>> assert new_context.chunks[0].metadata["role"] == "summary"
>>> assert "_vision_keywords" in new_context.chunks[0].metadata
"""

from pathlib import Path

from semantic_core.core.media_context import MediaContext
from semantic_core.domain import Chunk, ChunkType
from semantic_core.processing.steps.base import BaseProcessingStep
from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)


class SummaryStep(BaseProcessingStep):
    """Создаёт summary chunk из результата анализа медиа.
    
    Attributes:
        include_keywords: Включать ли keywords в metadata summary чанка.
        CHUNK_TYPE_MAP: Маппинг media type → ChunkType для summary.
    
    Example:
        >>> step = SummaryStep(include_keywords=True)
        >>> context = MediaContext(
        ...     media_path=Path("audio.mp3"),
        ...     document=Document(...),
        ...     analysis={"type": "audio", "description": "Podcast episode"},
        ...     chunks=[],
        ...     base_index=0,
        ... )
        >>> new_context = step.process(context)
        >>> assert len(new_context.chunks) == 1
    """
    
    CHUNK_TYPE_MAP = {
        "image": ChunkType.IMAGE_REF,
        "audio": ChunkType.AUDIO_REF,
        "video": ChunkType.VIDEO_REF,
    }
    
    def __init__(self, include_keywords: bool = True):
        """Инициализация шага.
        
        Args:
            include_keywords: Включать ли keywords в metadata summary чанка.
                Полезно отключить для экономии места в БД.
        """
        self.include_keywords = include_keywords
    
    @property
    def step_name(self) -> str:
        """Уникальное имя шага."""
        return "summary"
    
    def process(self, context: MediaContext) -> MediaContext:
        """Создаёт summary chunk из analysis.
        
        Args:
            context: Текущий контекст обработки медиа.
            
        Returns:
            Обновлённый контекст с добавленным summary chunk.
        """
        logger.info(
            f"[{self.step_name}] Creating summary chunk",
            path=str(context.media_path),
        )
        
        analysis = context.analysis
        media_type = analysis.get("type", "unknown")
        
        # Формируем content (только description, без transcript/OCR)
        summary_content = self._build_summary_content(analysis)
        
        # Формируем metadata
        summary_metadata = self._build_summary_metadata(analysis, context.media_path)
        summary_metadata["role"] = "summary"
        
        # Определяем chunk_type
        chunk_type = self.CHUNK_TYPE_MAP.get(media_type, ChunkType.TEXT)
        
        # Создаём chunk
        summary_chunk = Chunk(
            content=summary_content,
            chunk_index=context.base_index,
            chunk_type=chunk_type,
            metadata=summary_metadata,
        )
        
        logger.debug(
            f"[{self.step_name}] Summary created",
            chunk_type=chunk_type.value,
            content_length=len(summary_content),
        )
        
        return context.with_chunks([summary_chunk])
    
    def _build_summary_content(self, analysis: dict) -> str:
        """Формирует текст для summary chunk (без transcript/OCR).
        
        Args:
            analysis: Словарь с результатом анализа от Gemini API.
            
        Returns:
            Текст description для summary chunk.
        """
        media_type = analysis.get("type", "unknown")
        
        if media_type == "image":
            return analysis.get("description", "")
        elif media_type in ("audio", "video"):
            # Только description, transcript будет в отдельных чанках
            return analysis.get("description", "")
        
        return ""
    
    def _build_summary_metadata(self, analysis: dict, media_path: Path) -> dict:
        """Формирует metadata для summary chunk.
        
        Args:
            analysis: Словарь с результатом анализа от Gemini API.
            media_path: Путь к медиа-файлу.
            
        Returns:
            Словарь метаданных для summary chunk.
        """
        metadata = {"_original_path": str(media_path)}
        media_type = analysis.get("type", "unknown")
        
        if media_type == "image":
            metadata["_vision_alt"] = analysis.get("alt_text", "")
            if self.include_keywords:
                metadata["_vision_keywords"] = analysis.get("keywords", [])
            if analysis.get("ocr_text"):
                metadata["_vision_ocr"] = analysis["ocr_text"]
        
        elif media_type == "audio":
            metadata["_audio_description"] = analysis.get("description", "")
            if self.include_keywords:
                metadata["_audio_keywords"] = analysis.get("keywords", [])
            metadata["_audio_participants"] = analysis.get("participants", [])
            metadata["_audio_action_items"] = analysis.get("action_items", [])
            if analysis.get("duration_seconds"):
                metadata["_audio_duration"] = analysis["duration_seconds"]
        
        elif media_type == "video":
            if self.include_keywords:
                metadata["_video_keywords"] = analysis.get("keywords", [])
            if analysis.get("duration_seconds"):
                metadata["_video_duration"] = analysis["duration_seconds"]
        
        return metadata
