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
from semantic_core.domain import Document, SearchResult, MediaConfig, MediaType
from semantic_core.domain.chunk import Chunk, ChunkType
from semantic_core.infrastructure.storage.peewee.models import EmbeddingStatus

if TYPE_CHECKING:
    from semantic_core.infrastructure.gemini.image_analyzer import GeminiImageAnalyzer
    from semantic_core.infrastructure.gemini.rate_limiter import RateLimiter
    from semantic_core.core.media_queue import MediaQueueProcessor


logger = logging.getLogger(__name__)

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
        media_config: Optional[MediaConfig] = None,
    ):
        """Инициализация оркестратора.

        Args:
            embedder: Генератор эмбеддингов.
            store: Хранилище векторов.
            splitter: Сплиттер документов.
            context_strategy: Стратегия формирования контекста.
            image_analyzer: Анализатор изображений (опционально).
            media_config: Конфигурация обработки медиа.
        """
        self.embedder = embedder
        self.store = store
        self.splitter = splitter
        self.context_strategy = context_strategy
        self.image_analyzer = image_analyzer
        self.media_config = media_config or MediaConfig()

        # Lazy-инициализация компонентов для медиа
        self._rate_limiter: Optional["RateLimiter"] = None
        self._media_queue: Optional["MediaQueueProcessor"] = None

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
    # Markdown Asset Enrichment (Phase 6.4)
    # =========================================================================

    def _enrich_media_chunks(
        self,
        chunks: list[Chunk],
        document: Document,
        mode: IngestionMode,
    ) -> list[Chunk]:
        """Обогащает IMAGE_REF чанки через Vision API.

        Для каждого IMAGE_REF чанка:
        1. Резолвит путь к изображению
        2. Извлекает контекст (текст вокруг, заголовки)
        3. Вызывает Vision API (sync) или создаёт задачу (async)
        4. Обновляет chunk.content описанием от Vision

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

        # Проверяем, что image_analyzer настроен
        if self.image_analyzer is None:
            logger.warning(
                "enrich_media=True, but image_analyzer not configured. "
                "Skipping media enrichment."
            )
            return chunks

        enricher = MarkdownAssetEnricher()
        doc_dir = self._get_document_directory(document)

        for chunk in chunks:
            if chunk.chunk_type != ChunkType.IMAGE_REF:
                continue

            # Резолвим путь к изображению
            image_path = self._resolve_image_path(chunk.content, doc_dir)

            if image_path is None:
                # URL или не найден — пропускаем
                logger.debug(f"Skipping external/missing image: {chunk.content}")
                continue

            # Извлекаем контекст
            context = enricher.get_context(chunk, chunks)
            context_text = context.format_for_vision()

            # Сохраняем оригинальный путь в metadata
            chunk.metadata["_original_path"] = chunk.content

            if mode == "sync":
                # Обрабатываем сразу
                result = self._analyze_image_for_chunk(image_path, context_text)

                if result is not None:
                    # Заменяем content на описание
                    chunk.content = result["description"]
                    chunk.metadata["_vision_alt"] = result.get("alt_text", "")
                    chunk.metadata["_vision_keywords"] = result.get("keywords", [])
                    if result.get("ocr_text"):
                        chunk.metadata["_vision_ocr"] = result["ocr_text"]
                    chunk.metadata["_enriched"] = True
                else:
                    # Ошибка уже залогирована в _analyze_image_for_chunk
                    chunk.metadata["_media_error"] = "Vision API failed"

            else:  # async
                # Создаём задачу в очереди (обработается позже)
                try:
                    task_id = self._create_media_task(
                        path=str(image_path),
                        context_text=context_text,
                    )
                    chunk.metadata["_media_task_id"] = task_id
                    chunk.metadata["_pending_enrichment"] = True
                except Exception as e:
                    logger.error(f"Failed to create media task: {e}")
                    chunk.metadata["_media_error"] = str(e)

        return chunks

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

    def _resolve_image_path(
        self,
        image_ref: str,
        doc_dir: Optional[Path],
    ) -> Optional[Path]:
        """Резолвит путь к изображению.

        Порядок проверок:
        1. Пропускаем URL (http://, https://, data:)
        2. Абсолютный путь
        3. Относительно директории документа
        4. Относительно CWD

        Args:
            image_ref: Ссылка на изображение из Markdown.
            doc_dir: Директория документа.

        Returns:
            Абсолютный Path к файлу или None.
        """
        # Пропускаем URL
        if image_ref.startswith(("http://", "https://", "data:")):
            return None

        path = Path(image_ref)

        # 1. Абсолютный путь
        if path.is_absolute():
            if path.exists():
                return path
            logger.warning(f"Image not found (absolute): {path}")
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

        logger.warning(f"Image not found: {image_ref}")
        return None

    def _analyze_image_for_chunk(
        self,
        image_path: Path,
        context_text: str,
    ) -> Optional[dict]:
        """Анализирует изображение для обогащения чанка.

        Args:
            image_path: Путь к изображению.
            context_text: Контекст для Vision API.

        Returns:
            Словарь с результатами или None при ошибке.
        """
        from semantic_core.domain.media import MediaRequest, MediaResource

        try:
            # Rate limiting
            self._ensure_media_queue()
            self._rate_limiter.wait_if_needed()

            # Создаём запрос
            resource = MediaResource(
                path=str(image_path),
                mime_type=f"image/{image_path.suffix.lstrip('.')}",
            )
            request = MediaRequest(
                resource=resource,
                context_text=context_text,
            )

            # Вызываем анализатор
            result = self.image_analyzer.analyze(request)

            return {
                "description": result.description,
                "alt_text": result.alt_text,
                "keywords": result.keywords,
                "ocr_text": result.ocr_text,
            }

        except Exception as e:
            logger.error(f"Vision API error for {image_path}: {e}")
            return None
