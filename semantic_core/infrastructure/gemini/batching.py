"""Клиент для работы с Google Gemini Batch API.

Реализует асинхронную обработку эмбеддингов через Batch API
для снижения стоимости на 50% (по сравнению с синхронным режимом).

Классы:
    GeminiBatchClient
        Клиент для создания и управления батч-заданиями.
"""

from __future__ import annotations

import json
import struct
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from semantic_core.utils.logger import get_logger

if TYPE_CHECKING:
    from semantic_core.config import SemanticConfig

logger = get_logger(__name__)

# Проверяем доступность нового SDK (google-genai)
try:
    from google import genai
    from google.genai import types as genai_types

    GENAI_SDK_AVAILABLE = True
except ImportError:
    GENAI_SDK_AVAILABLE = False

from semantic_core.domain import Chunk


# Маппинг статусов Google Batch API -> наши внутренние статусы
GOOGLE_STATUS_MAP = {
    "JOB_STATE_QUEUED": "QUEUED",
    "JOB_STATE_PENDING": "QUEUED",
    "JOB_STATE_RUNNING": "RUNNING",
    "JOB_STATE_SUCCEEDED": "SUCCEEDED",
    "JOB_STATE_FAILED": "FAILED",
    "JOB_STATE_CANCELLED": "CANCELLED",
    "JOB_STATE_PAUSED": "PAUSED",
}

# Терминальные статусы (задание завершено)
COMPLETED_STATES = {
    "JOB_STATE_SUCCEEDED",
    "JOB_STATE_FAILED",
    "JOB_STATE_CANCELLED",
    "JOB_STATE_PAUSED",
}


class GeminiBatchClient:
    """Клиент для асинхронной векторизации через Google Batch API.

    Обеспечивает:
    - Формирование JSONL файлов с запросами эмбеддингов.
    - Загрузку файлов в Google Cloud.
    - Отправку батч-заданий и проверку статуса.
    - Скачивание результатов и очистку временных файлов.

    Attributes:
        client: Инициализированный Google GenAI клиент.
        model_name: Название модели (по умолчанию 'models/gemini-embedding-001').
        dimension: Размерность векторов (768 для MRL).

    Examples:
        >>> client = GeminiBatchClient(api_key="YOUR_KEY")
        >>> job_id = client.create_embedding_job(chunks)
        >>> status = client.get_job_status(job_id)
        >>> if status == "SUCCEEDED":
        ...     results = client.retrieve_results(job_id)
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "models/gemini-embedding-001",
        dimension: int = 768,
    ):
        """Инициализация клиента.

        Args:
            api_key: API-ключ Google Gemini для батч-операций.
            model_name: Модель для генерации эмбеддингов.
            dimension: Размерность векторов (MRL).

        Raises:
            ImportError: Если google-genai SDK не установлен.
        """
        if not GENAI_SDK_AVAILABLE:
            logger.error("google-genai SDK not installed")
            raise ImportError(
                "google-genai SDK not installed. "
                "Install with: pip install google-genai"
            )

        self.api_key = api_key
        self.model_name = model_name
        self.dimension = dimension
        
        # Инициализируем клиент нового SDK
        self._client = genai.Client(api_key=api_key)
        
        logger.debug(
            "Batch client initialized",
            model=model_name,
            dimension=dimension,
        )

    @classmethod
    def from_config(cls, config: SemanticConfig) -> "GeminiBatchClient":
        """Создаёт batch client из конфигурации.

        Factory-метод для создания экземпляра с параметрами из SemanticConfig.
        Использует batch_key если настроен, иначе основной api_key.

        Args:
            config: Конфигурация Semantic Core.

        Returns:
            Инициализированный GeminiBatchClient.

        Raises:
            ValueError: Если API ключ не настроен.

        Example:
            >>> from semantic_core.config import get_config
            >>> config = get_config()
            >>> batch_client = GeminiBatchClient.from_config(config)
        """
        # Предпочитаем batch_key, fallback на основной
        api_key = config.gemini_batch_key or config.require_api_key()
        
        return cls(
            api_key=api_key,
            model_name=config.embedding_model,
            dimension=config.embedding_dimension,
        )

    def create_embedding_job(
        self,
        chunks: List[Chunk],
        context_texts: Optional[Dict[str, str]] = None,
    ) -> str:
        """Создаёт батч-задание для генерации эмбеддингов.

        Использует специализированный метод batches.create_embeddings()
        который принимает список текстов напрямую (inlined_requests).

        Args:
            chunks: Список чанков для векторизации.
            context_texts: Словарь {chunk_id -> текст с контекстом}.
                Если None, используется chunk.content.

        Returns:
            Google Job ID (например, 'batches/abc123...').

        Raises:
            ValueError: Если список чанков пустой.
            RuntimeError: Если не удалось создать задание.

        Examples:
            >>> chunks = [Chunk(id="1", content="Text")]
            >>> job_id = client.create_embedding_job(chunks)
        """
        if not chunks:
            logger.warning("Empty chunks list provided")
            raise ValueError("Список чанков не может быть пустым")

        logger.info(
            "Creating batch embedding job",
            chunk_count=len(chunks),
            model=self.model_name,
        )

        try:
            # Собираем тексты для эмбеддинга
            texts = []
            self._chunk_id_order = []  # Сохраняем порядок для retrieve_results
            
            for chunk in chunks:
                text = (
                    context_texts.get(chunk.id, chunk.content)
                    if context_texts
                    else chunk.content
                )
                texts.append(text)
                self._chunk_id_order.append(str(chunk.id))

            # Создаём батч-задание через специальный метод для embeddings
            batch_job = self._client.batches.create_embeddings(
                model=self.model_name,
                src=genai_types.EmbeddingsBatchJobSource(
                    inlined_requests=genai_types.EmbedContentBatch(
                        contents=texts,
                        config=genai_types.EmbedContentConfig(
                            task_type="RETRIEVAL_DOCUMENT",
                            output_dimensionality=self.dimension,
                        ),
                    ),
                ),
            )

            logger.info(
                "Batch embedding job created successfully",
                job_name=batch_job.name,
                chunk_count=len(chunks),
            )

            return batch_job.name

        except Exception as e:
            logger.error(
                "Failed to create batch embedding job",
                error_type=type(e).__name__,
                error_message=str(e)[:200],
            )
            raise RuntimeError(f"Не удалось создать батч-задание: {e}")

    def get_job_status(self, google_job_id: str) -> str:
        """Получить статус батч-задания.

        Args:
            google_job_id: ID задания (например, 'batches/123...').

        Returns:
            Статус: 'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED'.

        Raises:
            RuntimeError: Если не удалось получить статус.

        Examples:
            >>> status = client.get_job_status("batches/abc123")
            >>> print(status)  # "RUNNING"
        """
        logger.debug(
            "Checking batch job status",
            job_id=google_job_id,
        )

        try:
            # Получаем информацию о задании
            batch_job = self._client.batches.get(name=google_job_id)
            
            # Маппим статус Google -> наш
            google_state = batch_job.state
            mapped_status = GOOGLE_STATUS_MAP.get(google_state, google_state)
            
            logger.debug(
                "Batch job status retrieved",
                job_id=google_job_id,
                google_state=google_state,
                mapped_status=mapped_status,
            )
            
            return mapped_status

        except Exception as e:
            logger.error(
                "Failed to get batch job status",
                job_id=google_job_id,
                error_type=type(e).__name__,
                error_message=str(e)[:200],
            )
            raise RuntimeError(f"Ошибка при получении статуса: {e}")

    def retrieve_results(self, google_job_id: str) -> Dict[str, bytes]:
        """Скачать результаты завершённого батч-задания.

        Args:
            google_job_id: ID задания.

        Returns:
            Словарь {chunk_id -> вектор в виде bytes}.

        Raises:
            RuntimeError: Если задание не завершено или произошла ошибка.

        Examples:
            >>> results = client.retrieve_results("batches/abc123")
            >>> vector_blob = results["chunk_1"]
        """
        logger.debug(
            "Retrieving batch results",
            job_id=google_job_id,
        )

        try:
            # Получаем информацию о задании
            batch_job = self._client.batches.get(name=google_job_id)
            
            # Проверяем, что задание завершено успешно
            if batch_job.state != "JOB_STATE_SUCCEEDED":
                raise RuntimeError(
                    f"Задание не завершено успешно. Статус: {batch_job.state}"
                )
            
            results = {}
            failed_count = 0
            
            # Для inlined_requests результаты приходят в dest.inlined_embed_content_responses
            # Порядок соответствует порядку отправки (self._chunk_id_order)
            dest = getattr(batch_job, "dest", None)
            inlined_responses = (
                getattr(dest, "inlined_embed_content_responses", None)
                if dest else None
            )
            
            if inlined_responses:
                chunk_ids = getattr(self, "_chunk_id_order", [])
                
                for idx, item in enumerate(inlined_responses):
                    # Получаем chunk_id по индексу или используем индекс
                    chunk_id = chunk_ids[idx] if idx < len(chunk_ids) else str(idx)
                    
                    try:
                        # Структура: InlinedEmbedContentResponse -> response -> embedding -> values
                        response = getattr(item, "response", None)
                        if not response:
                            logger.warning("No response in item", chunk_id=chunk_id)
                            failed_count += 1
                            continue
                            
                        embedding = getattr(response, "embedding", None)
                        if not embedding:
                            logger.warning("No embedding in response", chunk_id=chunk_id)
                            failed_count += 1
                            continue
                            
                        values = getattr(embedding, "values", None)
                        if values is not None:
                            values_list = list(values)
                            vector_blob = struct.pack(
                                f"{len(values_list)}f",
                                *values_list
                            )
                            results[chunk_id] = vector_blob
                        else:
                            logger.warning("Empty embedding values", chunk_id=chunk_id)
                            failed_count += 1
                    except Exception as e:
                        logger.warning(
                            "Failed to extract embedding",
                            chunk_id=chunk_id,
                            error=str(e)[:100],
                        )
                        failed_count += 1
            else:
                logger.warning(
                    "No inlined_embed_content_responses found in batch job",
                    job_id=google_job_id,
                )
            
            logger.info(
                "Batch results retrieved",
                job_id=google_job_id,
                success_count=len(results),
                failed_count=failed_count,
            )
            
            return results

        except RuntimeError:
            raise
        except Exception as e:
            logger.error(
                "Failed to retrieve batch results",
                job_id=google_job_id,
                error_type=type(e).__name__,
                error_message=str(e)[:200],
            )
            raise RuntimeError(f"Ошибка при скачивании результатов: {e}")
    
    def _cleanup_source_file(self, batch_job) -> None:
        """Удаляет входной файл из Google Cloud.
        
        Args:
            batch_job: Объект BatchJob из Google API.
        """
        try:
            # Получаем source URI из задания
            source = getattr(batch_job, "source", None) or getattr(batch_job, "src", None)
            
            if source:
                # source может быть в формате "files/filename" или URI
                if isinstance(source, str):
                    if source.startswith("files/"):
                        file_name = source
                    else:
                        file_name = f"files/{source.split('/')[-1]}"
                    
                    self._client.files.delete(name=file_name)
                    logger.trace("Source file deleted from Google Cloud", file=file_name)
                    
        except Exception as e:
            # Логируем, но не падаем, если файл не удалось удалить
            logger.warning(
                "Failed to cleanup source file",
                error=str(e)[:100],
            )

    def _create_jsonl_file(
        self,
        chunks: List[Chunk],
        context_texts: Optional[Dict[str, str]] = None,
    ) -> str:
        """Создать временный JSONL файл с запросами эмбеддингов.

        Формат JSONL по спецификации Google Batch API:
        {"key": "chunk_id", "request": {"model": "...", "contents": [...], "config": {...}}}

        Args:
            chunks: Список чанков.
            context_texts: Опциональные тексты с контекстом.

        Returns:
            Путь к временному файлу.
        """
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)

        for chunk in chunks:
            # Берем текст с контекстом или оригинальный content
            text = (
                context_texts.get(chunk.id, chunk.content)
                if context_texts
                else chunk.content
            )

            # Формируем запрос по спецификации Google Batch API
            # ВАЖНО: используем "key" (не "custom_id") и "contents" (массив, не "content")
            request = {
                "key": str(chunk.id),  # Идентификатор для сопоставления результатов
                "request": {
                    "model": self.model_name,
                    "contents": [{"parts": [{"text": text}]}],  # contents - массив!
                    "config": {
                        "task_type": "RETRIEVAL_DOCUMENT",
                        "output_dimensionality": self.dimension,
                    },
                },
            }

            temp_file.write(json.dumps(request, ensure_ascii=False) + "\n")

        temp_file.close()
        
        logger.trace(
            "JSONL file prepared",
            path=temp_file.name,
            chunk_count=len(chunks),
        )
        
        return temp_file.name
