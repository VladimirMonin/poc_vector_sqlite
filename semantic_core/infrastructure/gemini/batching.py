"""Клиент для работы с Google Gemini Batch API.

Реализует асинхронную обработку эмбеддингов через Batch API
для снижения стоимости на 50% (по сравнению с синхронным режимом).

Классы:
    GeminiBatchClient
        Клиент для создания и управления батч-заданиями.
"""

import json
import struct
import tempfile
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from semantic_core.utils.logger import get_logger

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
        model_name: Название модели (по умолчанию 'models/text-embedding-004').
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
        model_name: str = "models/text-embedding-004",
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

    def create_embedding_job(
        self,
        chunks: List[Chunk],
        context_texts: Optional[Dict[str, str]] = None,
    ) -> str:
        """Создаёт батч-задание для генерации эмбеддингов.

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
            "Creating batch job",
            chunk_count=len(chunks),
            model=self.model_name,
        )

        # 1. Формируем JSONL файл
        jsonl_path = self._create_jsonl_file(chunks, context_texts)
        logger.debug("JSONL file created", path=jsonl_path)

        try:
            # 2. Загружаем файл в Google Cloud
            batch_id = uuid4().hex[:8]
            uploaded_file = self._client.files.upload(
                file=jsonl_path,
                config=genai_types.UploadFileConfig(
                    display_name=f"batch_embeddings_{batch_id}"
                ),
            )
            
            logger.debug(
                "JSONL file uploaded",
                file_name=uploaded_file.name,
                display_name=f"batch_embeddings_{batch_id}",
            )

            # 3. Создаём батч-задание
            # Используем display_name загруженного файла для src
            batch_job = self._client.batches.create(
                model=self.model_name,
                src=f"files/{uploaded_file.name}",
            )

            logger.info(
                "Batch job created successfully",
                job_name=batch_job.name,
                file_name=uploaded_file.name,
                chunk_count=len(chunks),
            )

            return batch_job.name

        except Exception as e:
            logger.error(
                "Failed to create batch job",
                error_type=type(e).__name__,
                error_message=str(e)[:200],
            )
            raise RuntimeError(f"Не удалось создать батч-задание: {e}")

        finally:
            # Удаляем локальный временный JSONL файл
            Path(jsonl_path).unlink(missing_ok=True)
            logger.trace("Local JSONL file deleted")

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
            
            # Результаты инлайнятся в job.responses
            # Каждый response содержит key (наш chunk_id) и результат
            if hasattr(batch_job, "responses") and batch_job.responses:
                for response in batch_job.responses:
                    chunk_id = response.key
                    
                    # Проверяем на ошибку
                    if hasattr(response, "error") and response.error:
                        logger.warning(
                            "Chunk embedding failed in batch",
                            chunk_id=chunk_id,
                            error=str(response.error)[:100],
                        )
                        failed_count += 1
                        continue
                    
                    # Извлекаем embedding из response
                    # Структура: response.response.embeddings[0].values
                    try:
                        embedding_values = self._extract_embedding_values(response)
                        if embedding_values:
                            # Конвертируем в bytes через struct.pack
                            vector_blob = struct.pack(
                                f"{len(embedding_values)}f",
                                *embedding_values
                            )
                            results[chunk_id] = vector_blob
                        else:
                            logger.warning(
                                "Empty embedding values",
                                chunk_id=chunk_id,
                            )
                            failed_count += 1
                    except Exception as e:
                        logger.warning(
                            "Failed to extract embedding",
                            chunk_id=chunk_id,
                            error=str(e)[:100],
                        )
                        failed_count += 1
            
            logger.info(
                "Batch results retrieved",
                job_id=google_job_id,
                success_count=len(results),
                failed_count=failed_count,
            )
            
            # Cleanup: удаляем входной файл из Google Cloud
            self._cleanup_source_file(batch_job)
            
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
    
    def _extract_embedding_values(self, response) -> Optional[List[float]]:
        """Извлекает значения embedding из ответа batch job.
        
        Args:
            response: Объект ответа из batch_job.responses.
            
        Returns:
            Список float значений вектора или None если не удалось извлечь.
        """
        # Пробуем разные структуры ответа
        # Структура может отличаться в зависимости от версии API
        
        # Вариант 1: response.response.embeddings[0].values
        if hasattr(response, "response"):
            resp = response.response
            if hasattr(resp, "embeddings") and resp.embeddings:
                if hasattr(resp.embeddings[0], "values"):
                    return list(resp.embeddings[0].values)
            
            # Вариант 2: response.response.embedding.values
            if hasattr(resp, "embedding"):
                if hasattr(resp.embedding, "values"):
                    return list(resp.embedding.values)
        
        # Вариант 3: Прямой доступ через dict-like интерфейс
        if hasattr(response, "get"):
            resp_data = response.get("response", {})
            if "embeddings" in resp_data and resp_data["embeddings"]:
                return resp_data["embeddings"][0].get("values")
            if "embedding" in resp_data:
                return resp_data["embedding"].get("values")
        
        return None
    
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
