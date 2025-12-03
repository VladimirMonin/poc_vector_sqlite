"""Оркестратор пайплайна обработки документов.

Классы:
    SemanticCore
        Фасад для всей системы семантического поиска.
"""

import json
import logging
import uuid
from pathlib import Path
from typing import Optional, Literal, TYPE_CHECKING

from semantic_core.interfaces import (
    BaseEmbedder,
    BaseVectorStore,
    BaseSplitter,
    BaseContextStrategy,
)
from semantic_core.domain import Document, SearchResult, ChunkResult, MediaConfig, MediaType
from semantic_core.domain.chunk import Chunk, ChunkType, MEDIA_CHUNK_TYPES
from semantic_core.infrastructure.storage.peewee.models import EmbeddingStatus
from semantic_core.utils.logger import get_logger, setup_logging, LoggingConfig

if TYPE_CHECKING:
    from semantic_core.infrastructure.gemini.image_analyzer import GeminiImageAnalyzer
    from semantic_core.infrastructure.gemini.audio_analyzer import GeminiAudioAnalyzer
    from semantic_core.infrastructure.gemini.video_analyzer import GeminiVideoAnalyzer
    from semantic_core.infrastructure.gemini.rate_limiter import RateLimiter
    from semantic_core.core.media_queue import MediaQueueProcessor


logger = get_logger(__name__)

IngestionMode = Literal["sync", "async"]


class SemanticCore:
    """Главный оркестратор системы семантического поиска.

    Связывает все компоненты через Dependency Injection:
    - Splitter: Нарезка документов на чанки.
    - Context Strategy: Обогащение чанков контекстом.
    - Embedder: Генерация векторов.
    - Vector Store: Хранение и поиск.

    Пример использования:
        >>> from semantic_core import SemanticCore
        >>> from semantic_core.infrastructure.gemini import GeminiEmbedder
        >>> from semantic_core.infrastructure.storage import PeeweeVectorStore
        >>> from semantic_core.infrastructure.text_processing import (
        ...     SimpleSplitter,
        ...     BasicContextStrategy,
        ... )
        >>>
        >>> embedder = GeminiEmbedder(api_key="...")
        >>> store = PeeweeVectorStore(database=db)
        >>> splitter = SimpleSplitter()
        >>> context = BasicContextStrategy()
        >>>
        >>> core = SemanticCore(
        ...     embedder=embedder,
        ...     store=store,
        ...     splitter=splitter,
        ...     context_strategy=context,
        ... )
        >>>
        >>> doc = Document(content="Текст", metadata={"title": "Тест"})
        >>> core.ingest(doc)
        >>> results = core.search("запрос")
    """

    def __init__(
        self,
        embedder: BaseEmbedder,
        store: BaseVectorStore,
        splitter: BaseSplitter,
        context_strategy: BaseContextStrategy,
        image_analyzer: Optional["GeminiImageAnalyzer"] = None,
        audio_analyzer: Optional["GeminiAudioAnalyzer"] = None,
        video_analyzer: Optional["GeminiVideoAnalyzer"] = None,
        media_config: Optional[MediaConfig] = None,
        log_level: Optional[str] = None,
        log_file: Optional[str | Path] = None,
        logging_config: Optional[LoggingConfig] = None,
    ):
        """Инициализация оркестратора.

        Args:
            embedder: Генератор эмбеддингов.
            store: Хранилище векторов.
            splitter: Сплиттер документов.
            context_strategy: Стратегия формирования контекста.
            image_analyzer: Анализатор изображений (опционально).
            audio_analyzer: Анализатор аудио (опционально).
            video_analyzer: Анализатор видео (опционально).
            media_config: Конфигурация обработки медиа.
            log_level: Уровень логирования (DEBUG/INFO/WARNING/ERROR).
            log_file: Путь к файлу логов.
            logging_config: Полная конфигурация логирования (приоритет над log_level/log_file).
        """
        # === Настройка логирования ===
        if logging_config:
            setup_logging(logging_config)
        elif log_level or log_file:
            # Создаём конфиг из отдельных параметров
            config_kwargs: dict = {}
            if log_level:
                config_kwargs["level"] = log_level
            if log_file:
                config_kwargs["log_file"] = Path(log_file)
            setup_logging(LoggingConfig(**config_kwargs))

        # === Основные компоненты ===
        self.embedder = embedder
        self.store = store
        self.splitter = splitter
        self.context_strategy = context_strategy
        self.image_analyzer = image_analyzer
        self.audio_analyzer = audio_analyzer
        self.video_analyzer = video_analyzer
        self.media_config = media_config or MediaConfig()

        # Lazy-инициализация компонентов для медиа
        self._rate_limiter: Optional["RateLimiter"] = None
        self._media_queue: Optional["MediaQueueProcessor"] = None

        logger.debug("SemanticCore initialized")

    def ingest(
        self,
        document: Document,
        mode: IngestionMode = "sync",
        enrich_media: bool = False,
    ) -> Document:
        """Обрабатывает и сохраняет документ.

        Алгоритм (sync):
        1. Нарезает документ на чанки (splitter.split).
        2. [Опционально] Обогащает IMAGE_REF чанки через Vision API.
        3. Формирует контекст для каждого чанка (context_strategy).
        4. Генерирует эмбеддинги (embedder.embed_documents).
        5. Записывает векторы в чанки.
        6. Сохраняет документ с чанками (store.save).

        Алгоритм (async):
        1. Нарезает документ на чанки.
        2. [Опционально] Создаёт задачи на обогащение IMAGE_REF.
        3. Формирует контекст и сохраняет в metadata['_vector_source'].
        4. Сохраняет чанки со статусом PENDING (без векторов).
        5. Пользователь позже вызывает batch_manager.flush_queue().

        Args:
            document: Исходный документ.
            mode: Режим обработки ('sync' или 'async').
            enrich_media: Обогащать ли IMAGE_REF чанки через Vision API.

        Returns:
            Document с заполненным id.

        Raises:
            ValueError: Если данные некорректны.
            RuntimeError: Если произошла ошибка.
        """
        # 1. Нарезаем на чанки
        chunks = self.splitter.split(document)

        if not chunks:
            raise ValueError("Сплиттер вернул пустой список чанков")

        # 2. Обогащаем медиа-чанки (если включено)
        if enrich_media:
            chunks = self._enrich_media_chunks(chunks, document, mode)

        # 3. Формируем тексты для векторизации
        vector_texts = []
        for chunk in chunks:
            text = self.context_strategy.form_vector_text(chunk, document)
            vector_texts.append(text)

            # Сохраняем текст в metadata для async режима
            if mode == "async":
                chunk.metadata["_vector_source"] = text

        if mode == "sync":
            # 3. Генерируем эмбеддинги
            embeddings = self.embedder.embed_documents(vector_texts)

            # 4. Записываем векторы в чанки
            for chunk, embedding in zip(chunks, embeddings):
                chunk.embedding = embedding

        else:  # mode == "async"
            # Помечаем чанки как PENDING (без векторов)
            for chunk in chunks:
                chunk.embedding = None
                chunk.metadata["_embedding_status"] = EmbeddingStatus.PENDING.value

        # 5. Сохраняем в БД
        saved_document = self.store.save(document, chunks)

        return saved_document

    def search(
        self,
        query: str,
        filters: Optional[dict] = None,
        limit: int = 10,
        mode: str = "hybrid",
        k: int = 60,
    ) -> list[SearchResult]:
        """Выполняет поиск документов.

        Args:
            query: Поисковый запрос.
            filters: Фильтры по метаданным.
            limit: Максимальное количество результатов.
            mode: Режим поиска ('vector', 'fts', 'hybrid').
            k: Константа для RRF алгоритма (по умолчанию 60).

        Returns:
            Список SearchResult с документами и скорами.

        Raises:
            ValueError: Если query пустой.
        """
        if not query or not query.strip():
            raise ValueError("Запрос не может быть пустым")

        # Генерируем вектор для поиска (для vector/hybrid режимов)
        query_vector = None
        if mode in ("vector", "hybrid"):
            query_vector = self.embedder.embed_query(query)

        # Выполняем поиск
        results = self.store.search(
            query_vector=query_vector,
            query_text=query if mode in ("fts", "hybrid") else None,
            filters=filters,
            limit=limit,
            mode=mode,
            k=k,
        )

        return results

    def search_chunks(
        self,
        query: str,
        filters: Optional[dict] = None,
        limit: int = 10,
        mode: str = "hybrid",
        k: int = 60,
        chunk_type_filter: Optional[str] = None,
    ) -> list[ChunkResult]:
        """Выполняет гранулярный поиск по отдельным чанкам.

        В отличие от search(), который группирует результаты по документам,
        этот метод возвращает конкретные фрагменты (чанки).

        Args:
            query: Поисковый запрос.
            filters: Фильтры по метаданным документа.
            limit: Максимальное количество результатов.
            mode: Режим поиска ('vector', 'fts', 'hybrid').
            k: Константа для RRF алгоритма (по умолчанию 60).
            chunk_type_filter: Фильтр по типу чанка ('text', 'code', 'table', 'image_ref').

        Returns:
            Список ChunkResult с чанками и их скорами.

        Raises:
            ValueError: Если query пустой.
        """
        if not query or not query.strip():
            raise ValueError("Запрос не может быть пустым")

        # Генерируем вектор для поиска (для vector/hybrid режимов)
        query_vector = None
        if mode in ("vector", "hybrid"):
            query_vector = self.embedder.embed_query(query)

        # Выполняем гранулярный поиск
        results = self.store.search_chunks(
            query_vector=query_vector,
            query_text=query if mode in ("fts", "hybrid") else None,
            filters=filters,
            limit=limit,
            mode=mode,
            k=k,
            chunk_type_filter=chunk_type_filter,
        )

        return results

    def delete(self, document_id: int) -> int:
        """Удаляет документ и все его чанки.

        Args:
            document_id: ID документа.

        Returns:
            Количество удалённых строк.
        """
        return self.store.delete(document_id)

    def delete_by_metadata(self, filters: dict) -> int:
        """Удаляет чанки по фильтрам метаданных.

        Используется для удаления всех чанков, связанных с объектом
        перед переиндексацией (например, при обновлении).

        Args:
            filters: Словарь фильтров по метаданным (например, {"source_id": "123"}).

        Returns:
            Количество удалённых чанков.
        """
        return self.store.delete_by_metadata(filters)

    # =========================================================================
    # Media Processing (Phase 6)
    # =========================================================================

    def ingest_image(
        self,
        path: str,
        user_prompt: Optional[str] = None,
        context_text: Optional[str] = None,
        mode: IngestionMode = "sync",
    ) -> str:
        """Индексирует изображение.

        Создаёт задачу на анализ изображения. В sync режиме
        обрабатывает сразу, в async — помещает в очередь.

        Args:
            path: Путь к файлу изображения.
            user_prompt: Пользовательский промпт для анализа.
            context_text: Контекст из метаданных (заголовки).
            mode: Режим обработки ('sync' или 'async').

        Returns:
            sync: chunk_id (ID созданного чанка).
            async: task_id (ID задачи в очереди).

        Raises:
            ValueError: Если файл не является поддерживаемым изображением.
            RuntimeError: Если image_analyzer не настроен.
        """
        from semantic_core.infrastructure.media.utils import (
            is_image_valid,
            get_media_type,
            get_file_mime_type,
        )
        from semantic_core.infrastructure.storage.peewee.models import MediaTaskModel

        # Проверяем, что image_analyzer настроен
        if self.image_analyzer is None:
            raise RuntimeError(
                "image_analyzer not configured. "
                "Pass GeminiImageAnalyzer to SemanticCore constructor."
            )

        # Валидация файла
        if not is_image_valid(path):
            raise ValueError(f"Unsupported image format: {path}")

        # Создаём задачу в БД
        task_id = self._create_media_task(
            path=path,
            user_prompt=user_prompt,
            context_text=context_text,
        )

        if mode == "sync":
            # Обрабатываем сразу
            self._ensure_media_queue()
            success = self._media_queue.process_task(task_id)

            if not success:
                task = MediaTaskModel.get_by_id(task_id)
                raise RuntimeError(
                    f"Failed to process image: {task.error_message or 'Unknown error'}"
                )

            # Возвращаем task_id (chunk_id будет добавлен в Phase 6.1)
            return task_id

        else:  # async
            return task_id

    def process_media_queue(self, max_tasks: int = 10) -> int:
        """Обрабатывает очередь медиа-задач.

        Args:
            max_tasks: Максимальное количество задач за раз.

        Returns:
            Количество обработанных задач.
        """
        self._ensure_media_queue()
        return self._media_queue.process_batch(max_tasks)

    def get_media_queue_size(self) -> int:
        """Возвращает размер очереди медиа-задач.

        Returns:
            Количество pending задач.
        """
        self._ensure_media_queue()
        return self._media_queue.get_pending_count()

    def _ensure_media_queue(self) -> None:
        """Lazy-инициализация Rate Limiter и MediaQueueProcessor."""
        if self._rate_limiter is None:
            from semantic_core.infrastructure.gemini.rate_limiter import RateLimiter

            self._rate_limiter = RateLimiter(rpm_limit=self.media_config.rpm_limit)

        if self._media_queue is None:
            from semantic_core.core.media_queue import MediaQueueProcessor

            self._media_queue = MediaQueueProcessor(
                analyzer=self.image_analyzer,
                rate_limiter=self._rate_limiter,
                embedder=self.embedder,
                store=self.store,
            )

    def _create_media_task(
        self,
        path: str,
        user_prompt: Optional[str] = None,
        context_text: Optional[str] = None,
    ) -> str:
        """Создаёт задачу на обработку медиа в БД.

        Args:
            path: Путь к файлу.
            user_prompt: Пользовательский промпт.
            context_text: Контекст.

        Returns:
            ID созданной задачи (UUID).
        """
        from semantic_core.infrastructure.media.utils import (
            get_media_type,
            get_file_mime_type,
        )
        from semantic_core.infrastructure.storage.peewee.models import MediaTaskModel

        task_id = str(uuid.uuid4())
        media_type = get_media_type(path)
        mime_type = get_file_mime_type(path)

        MediaTaskModel.create(
            id=task_id,
            media_path=path,
            media_type=media_type,
            mime_type=mime_type,
            user_prompt=user_prompt,
            context_text=context_text,
            status="pending",
        )

        return task_id

    # =========================================================================
    # Markdown Asset Enrichment (Phase 6.4 + 6.5)
    # =========================================================================

    def _enrich_media_chunks(
        self,
        chunks: list[Chunk],
        document: Document,
        mode: IngestionMode,
    ) -> list[Chunk]:
        """Обогащает медиа-чанки через Vision/Audio/Video API.

        Для каждого IMAGE_REF/AUDIO_REF/VIDEO_REF чанка:
        1. Резолвит путь к медиа-файлу
        2. Извлекает контекст (текст вокруг, заголовки)
        3. Вызывает соответствующий API (sync) или создаёт задачу (async)
        4. Обновляет chunk.content результатом анализа

        Args:
            chunks: Все чанки документа.
            document: Родительский документ.
            mode: Режим обработки.

        Returns:
            Обновлённый список чанков.
        """
        from semantic_core.processing.enrichers.markdown_assets import (
            MarkdownAssetEnricher,
        )

        # Проверяем, есть ли хотя бы один анализатор
        has_any_analyzer = (
            self.image_analyzer is not None
            or self.audio_analyzer is not None
            or self.video_analyzer is not None
        )

        if not has_any_analyzer:
            logger.warning(
                "enrich_media=True, but no media analyzers configured. "
                "Skipping media enrichment."
            )
            return chunks

        enricher = MarkdownAssetEnricher()
        doc_dir = self._get_document_directory(document)

        for chunk in chunks:
            if chunk.chunk_type not in MEDIA_CHUNK_TYPES:
                continue

            # Резолвим путь к медиа-файлу
            media_path = self._resolve_media_path(chunk.content, doc_dir)

            if media_path is None:
                # URL или не найден — пропускаем
                logger.debug(f"Skipping external/missing media: {chunk.content}")
                continue

            # Проверяем, есть ли анализатор для этого типа
            if not self._has_analyzer_for_type(chunk.chunk_type):
                logger.debug(
                    f"No analyzer for {chunk.chunk_type.value}, skipping: {chunk.content}"
                )
                continue

            # Извлекаем контекст
            context = enricher.get_context(chunk, chunks)
            context_text = context.format_for_api()

            # Сохраняем оригинальный путь в metadata
            chunk.metadata["_original_path"] = chunk.content

            if mode == "sync":
                # Обрабатываем сразу
                result = self._analyze_media_for_chunk(
                    chunk.chunk_type, media_path, context_text
                )

                if result is not None:
                    self._apply_analysis_result(chunk, result)
                else:
                    chunk.metadata["_media_error"] = "Media analysis failed"

            else:  # async
                # Создаём задачу в очереди (обработается позже)
                try:
                    task_id = self._create_media_task(
                        path=str(media_path),
                        context_text=context_text,
                    )
                    chunk.metadata["_media_task_id"] = task_id
                    chunk.metadata["_pending_enrichment"] = True
                except Exception as e:
                    logger.error(f"Failed to create media task: {e}")
                    chunk.metadata["_media_error"] = str(e)

        return chunks

    def _has_analyzer_for_type(self, chunk_type: ChunkType) -> bool:
        """Проверяет, есть ли анализатор для данного типа чанка."""
        return {
            ChunkType.IMAGE_REF: self.image_analyzer is not None,
            ChunkType.AUDIO_REF: self.audio_analyzer is not None,
            ChunkType.VIDEO_REF: self.video_analyzer is not None,
        }.get(chunk_type, False)

    def _resolve_media_path(
        self,
        media_ref: str,
        doc_dir: Optional[Path],
    ) -> Optional[Path]:
        """Резолвит путь к медиа-файлу.

        Порядок проверок:
        1. Пропускаем URL (http://, https://, data:)
        2. Абсолютный путь
        3. Относительно директории документа
        4. Относительно CWD

        Args:
            media_ref: Ссылка на медиа из Markdown.
            doc_dir: Директория документа.

        Returns:
            Абсолютный Path к файлу или None.
        """
        # Пропускаем URL
        if media_ref.startswith(("http://", "https://", "data:")):
            return None

        path = Path(media_ref)

        # 1. Абсолютный путь
        if path.is_absolute():
            if path.exists():
                return path
            logger.warning(f"Media not found (absolute): {path}")
            return None

        # 2. Относительно директории документа
        if doc_dir:
            doc_relative = doc_dir / path
            if doc_relative.exists():
                return doc_relative.resolve()

        # 3. Относительно CWD
        cwd_relative = Path.cwd() / path
        if cwd_relative.exists():
            return cwd_relative.resolve()

        logger.warning(f"Media not found: {media_ref}")
        return None

    def _analyze_media_for_chunk(
        self,
        chunk_type: ChunkType,
        media_path: Path,
        context_text: str,
    ) -> Optional[dict]:
        """Анализирует медиа-файл для обогащения чанка.

        Роутит на нужный анализатор по типу чанка.

        Args:
            chunk_type: Тип чанка (IMAGE/AUDIO/VIDEO_REF).
            media_path: Путь к файлу.
            context_text: Контекст для API.

        Returns:
            Словарь с результатами или None при ошибке.
        """
        from semantic_core.domain.media import MediaRequest, MediaResource

        try:
            # Rate limiting
            self._ensure_media_queue()
            self._rate_limiter.wait()

            # Определяем тип медиа
            media_type_map = {
                ChunkType.IMAGE_REF: "image",
                ChunkType.AUDIO_REF: "audio",
                ChunkType.VIDEO_REF: "video",
            }
            media_type = media_type_map.get(chunk_type, "image")

            # Создаём запрос
            resource = MediaResource(
                path=str(media_path),
                media_type=media_type,
                mime_type=self._get_mime_type(media_path),
            )
            request = MediaRequest(
                resource=resource,
                context_text=context_text,
            )

            # Роутим на нужный анализатор
            if chunk_type == ChunkType.IMAGE_REF:
                result = self.image_analyzer.analyze(request)
                return {
                    "type": "image",
                    "description": result.description,
                    "alt_text": result.alt_text,
                    "keywords": result.keywords,
                    "ocr_text": result.ocr_text,
                }

            elif chunk_type == ChunkType.AUDIO_REF:
                result = self.audio_analyzer.analyze(request)
                return {
                    "type": "audio",
                    "description": result.description,
                    "transcription": result.transcription,
                    "keywords": result.keywords,
                    "participants": result.participants,
                    "action_items": result.action_items,
                    "duration_seconds": result.duration_seconds,
                }

            elif chunk_type == ChunkType.VIDEO_REF:
                from semantic_core.domain.media import VideoAnalysisConfig

                config = VideoAnalysisConfig()  # TODO: сделать настраиваемым
                result = self.video_analyzer.analyze(request, config)
                return {
                    "type": "video",
                    "description": result.description,
                    "transcription": result.transcription,
                    "keywords": result.keywords,
                    "ocr_text": result.ocr_text,
                    "duration_seconds": result.duration_seconds,
                }

            return None

        except Exception as e:
            logger.error(f"Media analysis error for {media_path}: {e}")
            return None

    def _apply_analysis_result(self, chunk: Chunk, result: dict) -> None:
        """Применяет результат анализа к чанку.

        Args:
            chunk: Чанк для обновления.
            result: Результат от анализатора.
        """
        media_type = result.get("type", "unknown")

        if media_type == "image":
            chunk.content = result["description"]
            chunk.metadata["_vision_alt"] = result.get("alt_text", "")
            chunk.metadata["_vision_keywords"] = result.get("keywords", [])
            if result.get("ocr_text"):
                chunk.metadata["_vision_ocr"] = result["ocr_text"]

        elif media_type == "audio":
            # Для аудио content = транскрипция (или описание если нет транскрипции)
            chunk.content = result.get("transcription") or result.get("description", "")
            chunk.metadata["_audio_description"] = result.get("description", "")
            chunk.metadata["_audio_keywords"] = result.get("keywords", [])
            chunk.metadata["_audio_participants"] = result.get("participants", [])
            chunk.metadata["_audio_action_items"] = result.get("action_items", [])
            if result.get("duration_seconds"):
                chunk.metadata["_audio_duration"] = result["duration_seconds"]

        elif media_type == "video":
            # Для видео content = описание (транскрипция в metadata)
            chunk.content = result.get("description", "")
            if result.get("transcription"):
                chunk.metadata["_video_transcription"] = result["transcription"]
            chunk.metadata["_video_keywords"] = result.get("keywords", [])
            if result.get("ocr_text"):
                chunk.metadata["_video_ocr"] = result["ocr_text"]
            if result.get("duration_seconds"):
                chunk.metadata["_video_duration"] = result["duration_seconds"]

        chunk.metadata["_enriched"] = True

    def _get_mime_type(self, path: Path) -> str:
        """Определяет MIME-тип файла по расширению."""
        import mimetypes

        mime_type, _ = mimetypes.guess_type(str(path))
        return mime_type or "application/octet-stream"

    def _get_document_directory(self, document: Document) -> Optional[Path]:
        """Получает директорию документа из metadata.

        Args:
            document: Документ.

        Returns:
            Path к директории или None.
        """
        # Пробуем разные ключи метаданных
        source = document.metadata.get("source") or document.metadata.get("path")

        if source:
            path = Path(source)
            if path.is_file():
                return path.parent
            elif path.is_dir():
                return path

        return None
