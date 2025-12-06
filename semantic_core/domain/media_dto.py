"""DTO для агрегированных медиа-данных.

Используется для объединения разрозненных чанков в структурированное представление.
Применение: Flask UI, CLI, RAG context.

Классы:
    TimelineItem
        Элемент timeline для медиа-плеера (навигация по таймкодам).
    MediaDetails
        Агрегированные данные о медиа-файле (summary, transcript, OCR, timeline).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from semantic_core.domain.chunk import Chunk


@dataclass
class TimelineItem:
    """Элемент timeline для навигации по медиа-контенту.
    
    Используется для построения интерактивного timeline в медиа-плеере.
    
    Attributes:
        chunk_id: ID чанка в БД.
        start_seconds: Временная метка начала фрагмента.
        content_preview: Превью контента (первые 100 символов).
        role: Роль чанка ("transcript" | "ocr").
        chunk_type: Тип контента ("text" | "code").
    """
    
    chunk_id: str
    start_seconds: int
    content_preview: str
    role: str
    chunk_type: str
    
    @property
    def formatted_time(self) -> str:
        """Форматирует время в MM:SS или HH:MM:SS.
        
        Returns:
            Строка вида "01:23" или "1:23:45".
        """
        hours = self.start_seconds // 3600
        minutes = (self.start_seconds % 3600) // 60
        seconds = self.start_seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"


@dataclass
class MediaDetails:
    """Агрегированные данные о медиа-файле.
    
    Объединяет разрозненные чанки (summary, transcript, OCR) в единое DTO.
    Используется для отображения в UI и формирования контекста для RAG.
    
    Attributes:
        document_id: ID документа в БД.
        media_path: Путь к медиа-файлу.
        media_type: Тип медиа ("image" | "audio" | "video").
        summary: Краткое описание (из summary chunk).
        keywords: Ключевые слова для поиска.
        full_transcript: Полная транскрипция (склеенная из transcript chunks).
        transcript_chunks: Список чанков с транскрипцией (для детального отображения).
        full_ocr_text: Полный OCR текст (склеенный из OCR chunks).
        ocr_chunks: Список чанков с OCR (для детального отображения).
        timeline: Timeline для навигации (если есть таймкоды).
        duration_seconds: Длительность медиа в секундах.
        participants: Участники (для аудио/видео).
        action_items: Список action items (для встреч).
    """
    
    # Базовая информация
    document_id: str
    media_path: Path
    media_type: str
    
    # Summary chunk
    summary: str
    keywords: list[str] = field(default_factory=list)
    
    # Transcript chunks
    full_transcript: Optional[str] = None
    transcript_chunks: list[Chunk] = field(default_factory=list)
    
    # OCR chunks
    full_ocr_text: Optional[str] = None
    ocr_chunks: list[Chunk] = field(default_factory=list)
    
    # Timeline для плеера
    timeline: Optional[list[TimelineItem]] = None
    
    # Дополнительные метаданные
    duration_seconds: Optional[int] = None
    participants: Optional[list[str]] = None
    action_items: Optional[list[str]] = None
    
    @property
    def has_timeline(self) -> bool:
        """Проверяет наличие таймкодов для навигации.
        
        Returns:
            True, если есть хотя бы один элемент timeline.
        """
        return self.timeline is not None and len(self.timeline) > 0
    
    @property
    def total_chunks(self) -> int:
        """Подсчитывает общее количество чанков.
        
        Returns:
            Сумма: 1 summary + transcript chunks + OCR chunks.
        """
        return 1 + len(self.transcript_chunks) + len(self.ocr_chunks)
    
    @property
    def has_transcript(self) -> bool:
        """Проверяет наличие транскрипции.
        
        Returns:
            True, если есть хотя бы один transcript chunk.
        """
        return bool(self.transcript_chunks)
    
    @property
    def has_ocr(self) -> bool:
        """Проверяет наличие OCR данных.
        
        Returns:
            True, если есть хотя бы один OCR chunk.
        """
        return bool(self.ocr_chunks)
