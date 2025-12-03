"""Unit-тесты для формирования JSONL запросов в GeminiBatchClient.

Проверяет:
- Валидность JSON в каждой строке
- Правильность структуры запроса Google Batch API
- Соответствие key и chunk.id
- Корректность обработки context_texts
"""

import json
import tempfile
from pathlib import Path

import pytest

from semantic_core.domain import Chunk, ChunkType
from semantic_core.infrastructure.gemini.batching import GeminiBatchClient


class TestJSONLBuilder:
    """Тесты для формирования JSONL файлов."""

    def test_jsonl_format_validation(self):
        """Проверка, что каждая строка JSONL - валидный JSON."""
        client = GeminiBatchClient(api_key="MOCK_KEY", dimension=768)

        chunks = [
            Chunk(
                id="1",
                content="Test content 1",
                chunk_type=ChunkType.TEXT,
                chunk_index=0,
                metadata={},
            ),
            Chunk(
                id="2",
                content="Test content 2",
                chunk_type=ChunkType.TEXT,
                chunk_index=1,
                metadata={},
            ),
            Chunk(
                id="3",
                content="Test content 3",
                chunk_type=ChunkType.CODE,
                chunk_index=2,
                language="python",
                metadata={},
            ),
        ]

        # Создаём JSONL файл
        jsonl_path = client._create_jsonl_file(chunks)

        try:
            with open(jsonl_path, "r") as f:
                lines = f.readlines()

            # Проверяем количество строк
            assert len(lines) == 3, "Должно быть 3 строки для 3 чанков"

            # Проверяем, что каждая строка - валидный JSON
            for i, line in enumerate(lines):
                try:
                    json.loads(line)
                except json.JSONDecodeError as e:
                    pytest.fail(f"Строка {i + 1} не валидный JSON: {e}")

        finally:
            Path(jsonl_path).unlink(missing_ok=True)

    def test_google_request_structure(self):
        """Проверка структуры запроса согласно Google Batch API спецификации.
        
        Формат JSONL по документации google-genai SDK:
        {"key": "id", "request": {"model": "...", "contents": [...], "config": {...}}}
        """
        client = GeminiBatchClient(
            api_key="MOCK_KEY",
            model_name="models/text-embedding-004",
            dimension=768,
        )

        chunks = [
            Chunk(
                id="chunk_123",
                content="Sample text for embedding",
                chunk_type=ChunkType.TEXT,
                chunk_index=0,
                metadata={},
            ),
        ]

        jsonl_path = client._create_jsonl_file(chunks)

        try:
            with open(jsonl_path, "r") as f:
                line = f.readline()
                request = json.loads(line)

            # Проверяем верхний уровень
            assert "key" in request, "Должен быть key (не custom_id!)"
            assert "request" in request, "Должен быть request"

            # Проверяем key
            assert request["key"] == "chunk_123", (
                "key должен совпадать с chunk.id"
            )

            # Проверяем структуру request
            req = request["request"]
            assert "model" in req, "Должна быть model"
            assert req["model"] == "models/text-embedding-004", "Неверная модель"

            # ВАЖНО: contents - массив, не content объект!
            assert "contents" in req, "Должен быть contents (массив)"
            assert "content" not in req, "Не должно быть content (объект)"
            assert isinstance(req["contents"], list), "contents должен быть списком"
            assert len(req["contents"]) > 0, "contents не должен быть пустым"
            assert "parts" in req["contents"][0], "contents[0] должен иметь parts"
            assert "text" in req["contents"][0]["parts"][0], "parts[0] должен иметь text"

            assert "config" in req, "Должен быть config"
            assert req["config"]["task_type"] == "RETRIEVAL_DOCUMENT", (
                "Неверный task_type"
            )
            assert req["config"]["output_dimensionality"] == 768, "Неверная размерность"

        finally:
            Path(jsonl_path).unlink(missing_ok=True)

    def test_context_texts_integration(self):
        """Проверка использования context_texts вместо chunk.content."""
        client = GeminiBatchClient(api_key="MOCK_KEY", dimension=768)

        chunks = [
            Chunk(
                id="1",
                content="Short content",
                chunk_type=ChunkType.TEXT,
                chunk_index=0,
                metadata={},
            ),
        ]

        context_texts = {
            "1": "Title: Document Title\n\nContent: Short content with context"
        }

        jsonl_path = client._create_jsonl_file(chunks, context_texts)

        try:
            with open(jsonl_path, "r") as f:
                line = f.readline()
                request = json.loads(line)

            # Новый формат: contents[0].parts[0].text
            text_content = request["request"]["contents"][0]["parts"][0]["text"]

            # Проверяем, что использовался context_text, а не просто content
            assert "Title: Document Title" in text_content, (
                "Должен быть контекст из context_texts"
            )
            assert text_content == context_texts["1"], (
                "Текст должен полностью совпадать с context_texts"
            )

        finally:
            Path(jsonl_path).unlink(missing_ok=True)

    def test_multiple_chunks_keys(self):
        """Проверка соответствия key для нескольких чанков."""
        client = GeminiBatchClient(api_key="MOCK_KEY", dimension=768)

        expected_ids = ["chunk_a", "chunk_b", "chunk_c", "chunk_d"]
        chunks = [
            Chunk(
                id=chunk_id,
                content=f"Content for {chunk_id}",
                chunk_type=ChunkType.TEXT,
                chunk_index=i,
                metadata={},
            )
            for i, chunk_id in enumerate(expected_ids)
        ]

        jsonl_path = client._create_jsonl_file(chunks)

        try:
            with open(jsonl_path, "r") as f:
                lines = f.readlines()

            # Извлекаем key из каждой строки
            keys = []
            for line in lines:
                request = json.loads(line)
                keys.append(request["key"])

            # Проверяем соответствие
            assert keys == expected_ids, (
                "key должны совпадать с chunk.id в том же порядке"
            )

        finally:
            Path(jsonl_path).unlink(missing_ok=True)


class TestGoogleKeyring:
    """Тесты для валидации GoogleKeyring."""

    def test_batch_key_available(self):
        """Проверка, что get_batch_key() работает когда ключ установлен."""
        from semantic_core.domain import GoogleKeyring

        keyring = GoogleKeyring(
            default_key="DEFAULT_KEY",
            batch_key="BATCH_KEY",
        )

        assert keyring.has_batch_support() is True
        assert keyring.get_batch_key() == "BATCH_KEY"

    def test_batch_key_missing_raises_error(self):
        """Проверка, что get_batch_key() выбрасывает ValueError если ключа нет."""
        from semantic_core.domain import GoogleKeyring

        keyring = GoogleKeyring(
            default_key="DEFAULT_KEY",
            batch_key=None,
        )

        assert keyring.has_batch_support() is False

        with pytest.raises(
            ValueError, match="Batch operations require a dedicated API key"
        ):
            keyring.get_batch_key()

    def test_batch_manager_requires_batch_key(self, in_memory_db):
        """Проверка, что BatchManager не создаётся без batch_key."""
        from semantic_core import BatchManager, PeeweeVectorStore, GoogleKeyring

        keyring_no_batch = GoogleKeyring(
            default_key="DEFAULT_KEY",
            batch_key=None,
        )

        store = PeeweeVectorStore(in_memory_db)

        # Должен выбросить ValueError при попытке создать BatchManager
        with pytest.raises(ValueError, match="Batch operations require"):
            BatchManager(
                keyring=keyring_no_batch,
                vector_store=store,
            )
