"""Сервис для работы с медиа-данными.

Агрегирует разрозненные чанки (summary, transcript, OCR) из БД
в структурированные DTO для использования в UI и RAG.

Классы:
    MediaService
        Сервис для работы с медиа-данными.
"""

import json
from pathlib import Path
from typing import Optional, TYPE_CHECKING

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

if TYPE_CHECKING:
    from semantic_core.infrastructure.gemini.image_analyzer import GeminiImageAnalyzer
    from semantic_core.infrastructure.gemini.audio_analyzer import GeminiAudioAnalyzer
    from semantic_core.infrastructure.gemini.video_analyzer import GeminiVideoAnalyzer
    from semantic_core.interfaces import BaseSplitter, BaseVectorStore
    from semantic_core.config import SemanticConfig

logger = get_logger(__name__)


class MediaService:
    """Сервис для работы с медиа-данными.
    
    Объединяет чанки с разными ролями (summary, transcript, OCR)
    в единое структурированное представление MediaDetails.
    
    Также предоставляет метод reprocess_document() для повторного анализа
    медиа-файлов с новыми custom_instructions (Phase 14.3.3).
    
    Примеры использования:
        >>> service = MediaService(
        ...     image_analyzer=image_analyzer,
        ...     audio_analyzer=audio_analyzer,
        ...     video_analyzer=video_analyzer,
        ...     splitter=splitter,
        ...     store=store,
        ...     config=config,
        ... )
        >>> 
        >>> # Агрегация данных
        >>> details = service.get_media_details("doc-123")
        >>> print(details.summary)
        >>> 
        >>> # Повторный анализ с новыми инструкциями
        >>> service.reprocess_document(
        ...     document_id="doc-123",
        ...     custom_instructions="Extract technical terms",
        ... )
    """
    
    def __init__(
        self,
        image_analyzer: Optional["GeminiImageAnalyzer"] = None,
        audio_analyzer: Optional["GeminiAudioAnalyzer"] = None,
        video_analyzer: Optional["GeminiVideoAnalyzer"] = None,
        splitter: Optional["BaseSplitter"] = None,
        store: Optional["BaseVectorStore"] = None,
        config: Optional["SemanticConfig"] = None,
    ):
        """Инициализация MediaService.
        
        Args:
            image_analyzer: Анализатор изображений (для reprocess_document).
            audio_analyzer: Анализатор аудио (для reprocess_document).
            video_analyzer: Анализатор видео (для reprocess_document).
            splitter: Сплиттер для MediaPipeline (для reprocess_document).
            store: Хранилище для удаления/сохранения чанков (для reprocess_document).
            config: Конфигурация SemanticCore (для MediaPipeline).
        
        Note:
            Для использования только get_media_details() / get_timeline() / get_chunks_by_role()
            можно создать без аргументов: MediaService().
            
            Для reprocess_document() требуются все аргументы.
        """
        self.image_analyzer = image_analyzer
        self.audio_analyzer = audio_analyzer
        self.video_analyzer = video_analyzer
        self.splitter = splitter
        self.store = store
        self.config = config
    
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
    
    def reprocess_document(
        self,
        document_id: str,
        custom_instructions: Optional[str] = None,
    ) -> Document:
        """Повторно анализирует медиа-файл с новыми custom_instructions.
        
        Phase 14.3.3: SRP-compliant метод для переобработки медиа.
        
        Алгоритм:
        1. Загружает Document из БД (проверяет существование и media_type)
        2. Извлекает media_path из Document.metadata["source"]
        3. Удаляет старые медиа-чанки (роли: summary, transcript, ocr)
        4. Повторно анализирует через Gemini с custom_instructions
        5. Создаёт новые чанки через MediaPipeline
        6. Сохраняет чанки в БД через store.save()
        
        Args:
            document_id: ID документа для переобработки.
            custom_instructions: Опциональные инструкции для Gemini.
                Примеры:
                - "Focus on technical terms and code snippets"
                - "Extract medical terminology"
                - "Identify speaker names and timestamps"
        
        Returns:
            Обновлённый Document с новыми чанками.
        
        Raises:
            ValueError: Если документ не найден, не медиа-файл, или отсутствуют зависимости.
            FileNotFoundError: Если медиа-файл не найден по пути из metadata["source"].
        
        Examples:
            >>> # Переобработать с новыми инструкциями
            >>> service.reprocess_document(
            ...     document_id="doc-123",
            ...     custom_instructions="Extract medical terms",
            ... )
            >>> 
            >>> # Переобработать с дефолтными промптами
            >>> service.reprocess_document("doc-123")
        
        Note:
            Требует наличия analyzers, splitter, store и config в __init__.
            Удаляет ВСЕ старые медиа-чанки перед созданием новых.
        """
        # 1. Проверяем зависимости
        if not all([self.splitter, self.store, self.config]):
            raise ValueError(
                "MediaService.reprocess_document() requires splitter, store, and config. "
                "Initialize MediaService with these dependencies."
            )
        
        # 2. Загружаем документ из БД
        try:
            doc_model = DocumentModel.get_by_id(document_id)
        except DoesNotExist:
            raise ValueError(f"Document {document_id} not found")
        
        # 3. Проверяем media_type
        media_type_str = doc_model.media_type
        if media_type_str not in ("image", "audio", "video"):
            raise ValueError(
                f"Document {document_id} is not a media file "
                f"(media_type={media_type_str})"
            )
        
        media_type = MediaType(media_type_str)  # ← БЕЗ .upper(), т.к. "audio"/"video"/"image"
        
        # 4. Извлекаем media_path из metadata
        doc_metadata = json.loads(doc_model.metadata)
        media_path_str = doc_metadata.get("source")
        
        if not media_path_str:
            raise ValueError(
                f"Document {document_id} has no 'source' in metadata. "
                "Cannot determine media file path."
            )
        
        media_path = Path(media_path_str)
        
        if not media_path.exists():
            raise FileNotFoundError(
                f"Media file not found: {media_path}. "
                f"Document {document_id} references missing file."
            )
        
        logger.info(
            f"🔄 Reprocessing document {document_id}",
            media_path=str(media_path),
            media_type=media_type_str,
            has_custom_instructions=bool(custom_instructions),
        )
        
        # 5. Удаляем старые медиа-чанки
        deleted_count = self._delete_media_chunks(document_id)
        logger.debug(
            f"Deleted {deleted_count} old media chunks",
            document_id=document_id,
        )
        
        # 6. Выбираем analyzer по media_type
        analyzer = self._get_analyzer_for_media_type(media_type)
        
        if analyzer is None:
            raise ValueError(
                f"No analyzer available for media_type={media_type_str}. "
                "Initialize MediaService with image_analyzer/audio_analyzer/video_analyzer."
            )
        
        # 7. Повторный анализ через Gemini
        analysis = analyzer.analyze(
            media_path=media_path,
            custom_instructions=custom_instructions,
        )
        
        logger.debug(
            "Media analysis completed",
            document_id=document_id,
            analysis_keys=list(analysis.keys()),
        )
        
        # 8. Создаём Document для MediaPipeline
        document = Document(
            content=str(media_path),
            metadata=doc_metadata,
            media_type=media_type,
            id=document_id,
        )
        
        # 9. Создаём новые чанки через MediaPipeline
        new_chunks = self._build_chunks_via_pipeline(
            document=document,
            media_path=media_path,
            analysis=analysis,
            media_type=media_type,
        )
        
        logger.info(
            f"Created {len(new_chunks)} new chunks",
            document_id=document_id,
            chunk_roles=[c.metadata.get("role") for c in new_chunks],
        )
        
        # 10. Добавляем чанки в document
        document.chunks = new_chunks
        
        # 11. Сохраняем в БД (без векторизации — векторы будут созданы batch-процессом)
        # store.save() обновит чанки документа
        self.store.save(document)
        
        logger.info(
            f"✅ Document {document_id} reprocessed successfully",
            chunk_count=len(new_chunks),
        )
        
        return document
    
    def _delete_media_chunks(self, document_id: str) -> int:
        """Удаляет все медиа-чанки документа (роли: summary, transcript, ocr).
        
        Args:
            document_id: ID документа.
        
        Returns:
            Количество удалённых чанков.
        """
        chunks_query = ChunkModel.select().where(
            ChunkModel.document == document_id
        )
        
        deleted_count = 0
        for chunk_model in chunks_query:
            metadata = json.loads(chunk_model.metadata)
            role = metadata.get("role", "")
            
            if role in ("summary", "transcript", "ocr"):
                chunk_model.delete_instance()
                deleted_count += 1
        
        return deleted_count
    
    def _get_analyzer_for_media_type(
        self, media_type: MediaType
    ) -> Optional["GeminiImageAnalyzer | GeminiAudioAnalyzer | GeminiVideoAnalyzer"]:
        """Возвращает analyzer для заданного media_type.
        
        Args:
            media_type: Тип медиа (IMAGE/AUDIO/VIDEO).
        
        Returns:
            Соответствующий analyzer или None.
        """
        if media_type == MediaType.IMAGE:
            return self.image_analyzer
        elif media_type == MediaType.AUDIO:
            return self.audio_analyzer
        elif media_type == MediaType.VIDEO:
            return self.video_analyzer
        else:
            return None
    
    def _build_chunks_via_pipeline(
        self,
        document: Document,
        media_path: Path,
        analysis: dict,
        media_type: MediaType,
    ) -> list[Chunk]:
        """Создаёт чанки через MediaPipeline.
        
        Args:
            document: Document для контекста.
            media_path: Путь к медиа-файлу.
            analysis: Результат анализа от Gemini.
            media_type: Тип медиа (IMAGE/AUDIO/VIDEO).
        
        Returns:
            Список новых Chunk.
        """
        from semantic_core.core.media_context import MediaContext
        from semantic_core.core.media_pipeline import MediaPipeline
        from semantic_core.processing.steps import SummaryStep, TranscriptionStep, OCRStep
        
        # Определяем chunk_type по media_type
        chunk_type_map = {
            MediaType.IMAGE: ChunkType.IMAGE_REF,
            MediaType.AUDIO: ChunkType.AUDIO_REF,
            MediaType.VIDEO: ChunkType.VIDEO_REF,
        }
        chunk_type = chunk_type_map[media_type]
        
        # Создаём MediaContext
        context = MediaContext(
            media_path=media_path,
            document=document,
            analysis=analysis,
            chunks=[],
            base_index=0,
            services={
                "chunk_type": chunk_type,
                "fallback_metadata": {},
            },
        )
        
        # Создаём pipeline со всеми шагами
        pipeline = MediaPipeline(
            steps=[
                SummaryStep(),
                TranscriptionStep(
                    splitter=self.splitter,
                    default_chunk_size=self.config.media.chunk_sizes.transcript_chunk_size,
                    enable_timecodes=self.config.media.processing.enable_timecodes,
                ),
                OCRStep(
                    splitter=self.splitter,
                    default_chunk_size=self.config.media.chunk_sizes.ocr_text_chunk_size,
                    parser_mode=self.config.media.processing.ocr_parser_mode,
                ),
            ]
        )
        
        # Выполняем pipeline
        final_context = pipeline.build_chunks(context)
        
        return final_context.chunks
