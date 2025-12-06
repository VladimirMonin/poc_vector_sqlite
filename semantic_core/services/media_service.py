"""Сервис для работы с медиа-данными.

Агрегирует разрозненные чанки (summary, transcript, OCR) из БД
в структурированные DTO для использования в UI и RAG.

Классы:
    MediaService
        Сервис для агрегации медиа-чанков.
"""

import json
from pathlib import Path
from typing import Optional

from peewee import DoesNotExist

from semantic_core.domain import (
    Document,
    Chunk,
    ChunkType,
    MediaDetails,
    TimelineItem,
    MediaType,
)
from semantic_core.infrastructure.storage.peewee.models import (
    DocumentModel,
    ChunkModel,
)
from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)


class MediaService:
    """Сервис для агрегации медиа-данных из разрозненных чанков.
    
    Объединяет чанки с разными ролями (summary, transcript, OCR)
    в единое структурированное представление MediaDetails.
    
    Примеры использования:
        >>> service = MediaService()
        >>> details = service.get_media_details("doc-123")
        >>> print(details.summary)
        >>> print(details.full_transcript)
        >>> if details.has_timeline:
        ...     for item in details.timeline:
        ...         print(f"{item.formatted_time}: {item.content_preview}")
    """
    
    def get_media_details(
        self,
        document_id: str,
        include_transcript: bool = True,
        include_ocr: bool = True,
    ) -> MediaDetails:
        """Получает агрегированные данные о медиа-файле.
        
        Загружает документ и все его чанки, группирует по ролям,
        собирает timeline с таймкодами.
        
        Args:
            document_id: ID документа (строка).
            include_transcript: Включать ли transcript чанки в результат.
            include_ocr: Включать ли OCR чанки в результат.
        
        Returns:
            MediaDetails с агрегированными данными.
        
        Raises:
            ValueError: Если документ не найден или не является медиа-файлом.
        
        Examples:
            >>> details = service.get_media_details("abc-123")
            >>> details = service.get_media_details(
            ...     "abc-123",
            ...     include_ocr=False  # Только summary + transcript
            ... )
        """
        # Получаем документ из БД
        try:
            doc_model = DocumentModel.get_by_id(document_id)
        except DoesNotExist:
            raise ValueError(f"Document {document_id} not found")
        
        # Проверяем, что это медиа-файл
        if doc_model.media_type not in ("image", "audio", "video"):
            raise ValueError(
                f"Document {document_id} is not a media file "
                f"(media_type={doc_model.media_type})"
            )
        
        # Получаем все чанки документа
        chunks_query = (
            ChunkModel.select()
            .where(ChunkModel.document == doc_model.id)
            .order_by(ChunkModel.chunk_index)
        )
        
        # Разделяем чанки по ролям
        summary_chunk = None
        transcript_chunks = []
        ocr_chunks = []
        timeline_items = []
        
        for chunk_model in chunks_query:
            # Парсим metadata
            metadata = json.loads(chunk_model.metadata)
            role = metadata.get("role", "")
            
            # Конвертируем ORM модель в domain Chunk
            chunk = self._chunk_model_to_domain(chunk_model)
            
            if role == "summary":
                summary_chunk = chunk
            elif role == "transcript" and include_transcript:
                transcript_chunks.append(chunk)
                # Добавляем в timeline если есть таймкод
                if "start_seconds" in metadata:
                    timeline_items.append(
                        TimelineItem(
                            chunk_id=str(chunk.id),
                            start_seconds=metadata["start_seconds"],
                            content_preview=chunk.content[:100],
                            role="transcript",
                            chunk_type=chunk.chunk_type.value,
                        )
                    )
            elif role == "ocr" and include_ocr:
                ocr_chunks.append(chunk)
                # Добавляем в timeline если есть таймкод
                if "start_seconds" in metadata:
                    timeline_items.append(
                        TimelineItem(
                            chunk_id=str(chunk.id),
                            start_seconds=metadata["start_seconds"],
                            content_preview=chunk.content[:100],
                            role="ocr",
                            chunk_type=chunk.chunk_type.value,
                        )
                    )
        
        # Проверяем наличие summary chunk
        if summary_chunk is None:
            raise ValueError(
                f"Document {document_id} has no summary chunk (role='summary')"
            )
        
        # Извлекаем данные из summary metadata
        summary_metadata = summary_chunk.metadata
        keywords = summary_metadata.get("keywords", [])
        duration_seconds = summary_metadata.get("duration_seconds")
        participants = summary_metadata.get("participants")
        action_items = summary_metadata.get("action_items")
        
        # Склеиваем transcript chunks в единый текст
        full_transcript = None
        if transcript_chunks:
            full_transcript = "\n\n".join(c.content for c in transcript_chunks)
        
        # Склеиваем OCR chunks в единый текст
        full_ocr_text = None
        if ocr_chunks:
            full_ocr_text = "\n\n".join(c.content for c in ocr_chunks)
        
        # Сортируем timeline по времени
        timeline = sorted(timeline_items, key=lambda x: x.start_seconds) if timeline_items else None
        
        # Формируем MediaDetails
        return MediaDetails(
            document_id=document_id,
            media_path=Path(doc_model.source),
            media_type=doc_model.media_type,
            summary=summary_chunk.content,
            keywords=keywords,
            full_transcript=full_transcript,
            transcript_chunks=transcript_chunks,
            full_ocr_text=full_ocr_text,
            ocr_chunks=ocr_chunks,
            timeline=timeline,
            duration_seconds=duration_seconds,
            participants=participants,
            action_items=action_items,
        )
    
    def get_timeline(
        self,
        document_id: str,
        role_filter: Optional[str] = None,
    ) -> list[TimelineItem]:
        """Получает timeline для медиа-плеера.
        
        Возвращает только чанки с таймкодами, отсортированные по времени.
        
        Args:
            document_id: ID документа.
            role_filter: Фильтр по роли ("transcript" | "ocr" | None для всех).
        
        Returns:
            Список TimelineItem, отсортированный по start_seconds.
        
        Raises:
            ValueError: Если документ не найден.
        
        Examples:
            >>> # Все чанки с таймкодами
            >>> timeline = service.get_timeline("doc-123")
            >>> # Только transcript
            >>> timeline = service.get_timeline("doc-123", role_filter="transcript")
        """
        # Получаем документ (проверяем существование)
        try:
            DocumentModel.get_by_id(document_id)
        except DoesNotExist:
            raise ValueError(f"Document {document_id} not found")
        
        # Получаем чанки
        chunks_query = (
            ChunkModel.select()
            .where(ChunkModel.document == document_id)
            .order_by(ChunkModel.chunk_index)
        )
        
        timeline_items = []
        
        for chunk_model in chunks_query:
            metadata = json.loads(chunk_model.metadata)
            role = metadata.get("role", "")
            
            # Фильтруем по role если указан
            if role_filter and role != role_filter:
                continue
            
            # Добавляем только чанки с таймкодами
            if "start_seconds" in metadata:
                timeline_items.append(
                    TimelineItem(
                        chunk_id=str(chunk_model.id),
                        start_seconds=metadata["start_seconds"],
                        content_preview=chunk_model.content[:100],
                        role=role,
                        chunk_type=chunk_model.chunk_type,
                    )
                )
        
        # Сортируем по времени
        return sorted(timeline_items, key=lambda x: x.start_seconds)
    
    def get_chunks_by_role(
        self,
        document_id: str,
        role: str,
    ) -> list[Chunk]:
        """Получает чанки документа с определённой ролью.
        
        Args:
            document_id: ID документа.
            role: Роль чанков ("summary" | "transcript" | "ocr").
        
        Returns:
            Список Chunk с указанной ролью, отсортированный по chunk_index.
        
        Raises:
            ValueError: Если документ не найден.
        
        Examples:
            >>> # Получить все transcript чанки
            >>> chunks = service.get_chunks_by_role("doc-123", "transcript")
            >>> # Получить summary
            >>> summary = service.get_chunks_by_role("doc-123", "summary")[0]
        """
        # Получаем документ (проверяем существование)
        try:
            DocumentModel.get_by_id(document_id)
        except DoesNotExist:
            raise ValueError(f"Document {document_id} not found")
        
        # Получаем чанки
        chunks_query = (
            ChunkModel.select()
            .where(ChunkModel.document == document_id)
            .order_by(ChunkModel.chunk_index)
        )
        
        result_chunks = []
        
        for chunk_model in chunks_query:
            metadata = json.loads(chunk_model.metadata)
            if metadata.get("role") == role:
                chunk = self._chunk_model_to_domain(chunk_model)
                result_chunks.append(chunk)
        
        return result_chunks
    
    def _chunk_model_to_domain(self, chunk_model: ChunkModel) -> Chunk:
        """Конвертирует ORM модель ChunkModel в domain Chunk.
        
        Args:
            chunk_model: ORM модель чанка.
        
        Returns:
            Domain объект Chunk.
        """
        metadata = json.loads(chunk_model.metadata)
        
        return Chunk(
            content=chunk_model.content,
            chunk_index=chunk_model.chunk_index,
            chunk_type=ChunkType(chunk_model.chunk_type),
            language=chunk_model.language,
            embedding=None,  # Не загружаем вектор (экономия памяти)
            parent_doc_id=chunk_model.document.id,
            metadata=metadata,
            id=chunk_model.id,
            created_at=chunk_model.created_at,
        )
