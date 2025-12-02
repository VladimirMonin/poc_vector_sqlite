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

try:
    import google.generativeai as genai

    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

from semantic_core.domain import Chunk


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
        """
        if not GENAI_AVAILABLE:
            raise ImportError(
                "google-generativeai not installed. "
                "Install with: pip install google-generativeai"
            )

        genai.configure(api_key=api_key)
        self.api_key = api_key
        self.model_name = model_name
        self.dimension = dimension

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
            raise ValueError("Список чанков не может быть пустым")

        # 1. Формируем JSONL файл
        jsonl_path = self._create_jsonl_file(chunks, context_texts)

        try:
            # TODO: Implement real Google Batch API calls
            # For now, this is a placeholder that works with mocks in tests
            raise NotImplementedError(
                "Real Google Batch API integration is not yet implemented. "
                "Use mock_batch_client for testing."
            )

            # # 2. Загружаем файл в Google Cloud
            # uploaded_file = genai.files.upload(path=jsonl_path)
            #
            # # 3. Создаём батч-задание
            # batch_job = genai.batches.create(
            #     model=self.model_name,
            #     src=uploaded_file.uri,
            # )
            #
            # return batch_job.name

        except NotImplementedError:
            raise
        except Exception as e:
            raise RuntimeError(f"Не удалось создать батч-задание: {e}")

        finally:
            # Удаляем временный JSONL файл
            Path(jsonl_path).unlink(missing_ok=True)

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
        try:
            # TODO: Implement real Google Batch API status check
            raise NotImplementedError(
                "Real Google Batch API integration is not yet implemented. "
                "Use mock_batch_client for testing."
            )

            # batch_job = genai.batches.get(name=google_job_id)
            # return batch_job.state.name  # Enum -> String

        except NotImplementedError:
            raise
        except Exception as e:
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
        try:
            # TODO: Implement real Google Batch API results retrieval
            raise NotImplementedError(
                "Real Google Batch API integration is not yet implemented. "
                "Use mock_batch_client for testing."
            )

            # # Получаем информацию о задании
            # batch_job = genai.batches.get(name=google_job_id)
            #
            # if batch_job.state.name != "SUCCEEDED":
            #     raise RuntimeError(
            #         f"Задание не завершено. Статус: {batch_job.state.name}"
            #     )
            #
            # # Скачиваем выходной файл
            # output_file_uri = batch_job.output_uri
            # if not output_file_uri:
            #     raise RuntimeError("Нет выходного файла у батч-задания")
            #
            # # Парсим результаты из JSONL
            # results = self._parse_results_jsonl(output_file_uri)
            #
            # # Очищаем файлы в Google Cloud
            # self._cleanup_files(batch_job)
            #
            # return results

        except NotImplementedError:
            raise
        except Exception as e:
            raise RuntimeError(f"Ошибка при скачивании результатов: {e}")

    def _create_jsonl_file(
        self,
        chunks: List[Chunk],
        context_texts: Optional[Dict[str, str]] = None,
    ) -> str:
        """Создать временный JSONL файл с запросами эмбеддингов.

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

            # Формируем запрос по спецификации Gemini Batch API
            request = {
                "custom_id": chunk.id,  # Для идентификации результата
                "request": {
                    "model": self.model_name,
                    "content": {"parts": [{"text": text}]},
                    "config": {
                        "task_type": "RETRIEVAL_DOCUMENT",
                        "output_dimensionality": self.dimension,
                    },
                },
            }

            temp_file.write(json.dumps(request) + "\n")

        temp_file.close()
        return temp_file.name

    def _parse_results_jsonl(self, file_uri: str) -> Dict[str, bytes]:
        """Парсит JSONL файл с результатами.

        Args:
            file_uri: URI выходного файла в Google Cloud.

        Returns:
            Словарь {chunk_id -> вектор (bytes)}.
        """
        # Скачиваем файл
        file_info = self.client.files.get(name=file_uri.split("/")[-1])

        # Создаём временный файл для результатов
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as temp_out:
            temp_out.write(file_info.bytes)
            temp_out_path = temp_out.name

        results = {}

        try:
            with open(temp_out_path, "r") as f:
                for line in f:
                    if not line.strip():
                        continue

                    response = json.loads(line)
                    chunk_id = response.get("custom_id")

                    # Извлекаем вектор
                    embedding_data = response.get("response", {}).get("embedding")
                    if embedding_data and "values" in embedding_data:
                        values = embedding_data["values"]

                        # Конвертируем в bytes через struct.pack
                        vector_blob = struct.pack(f"{len(values)}f", *values)
                        results[chunk_id] = vector_blob

        finally:
            Path(temp_out_path).unlink(missing_ok=True)

        return results

    def _cleanup_files(self, batch_job) -> None:
        """Удаляет входной и выходной файлы из Google Cloud.

        Args:
            batch_job: Объект BatchJob из Google API.
        """
        try:
            # Удаляем входной файл
            if batch_job.source_uri:
                input_file_name = batch_job.source_uri.split("/")[-1]
                self.client.files.delete(name=input_file_name)

            # Удаляем выходной файл
            if batch_job.output_uri:
                output_file_name = batch_job.output_uri.split("/")[-1]
                self.client.files.delete(name=output_file_name)

        except Exception as e:
            # Логируем, но не падаем, если файлы не удалось удалить
            print(f"[Warning] Не удалось очистить файлы: {e}")
