"""Unit-тесты для GeminiBatchClient.

Проверяет:
- Формат JSONL файла (key, contents, config)
- Маппинг статусов Google -> наши
- Извлечение embedding values
- Cleanup логика
"""

import json
import struct
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from semantic_core.domain import Chunk


class TestJsonlFormat:
    """Тесты формата JSONL файла для Batch API."""

    def test_jsonl_uses_key_not_custom_id(self, mock_embedder):
        """JSONL должен использовать 'key' вместо 'custom_id'."""
        from semantic_core.infrastructure.gemini.batching import (
            GeminiBatchClient,
            GENAI_SDK_AVAILABLE,
        )

        if not GENAI_SDK_AVAILABLE:
            pytest.skip("google-genai SDK not installed")

        # Мокаем Client
        with patch("semantic_core.infrastructure.gemini.batching.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client

            client = GeminiBatchClient(api_key="test-key")

            chunks = [
                Chunk(
                    id="chunk_123",
                    content="Test content",
                    chunk_type="text",
                    metadata={},
                    chunk_index=0,
                ),
            ]

            # Создаём JSONL файл
            jsonl_path = client._create_jsonl_file(chunks)

            try:
                with open(jsonl_path, "r") as f:
                    line = f.readline()
                    data = json.loads(line)

                # Проверяем формат
                assert "key" in data, "Должен быть ключ 'key'"
                assert "custom_id" not in data, "Не должно быть 'custom_id'"
                assert data["key"] == "chunk_123"

            finally:
                Path(jsonl_path).unlink(missing_ok=True)

    def test_jsonl_uses_contents_array(self, mock_embedder):
        """JSONL должен использовать 'contents' массив, а не 'content' объект."""
        from semantic_core.infrastructure.gemini.batching import (
            GeminiBatchClient,
            GENAI_SDK_AVAILABLE,
        )

        if not GENAI_SDK_AVAILABLE:
            pytest.skip("google-genai SDK not installed")

        with patch("semantic_core.infrastructure.gemini.batching.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client

            client = GeminiBatchClient(api_key="test-key")

            chunks = [
                Chunk(
                    id="1",
                    content="Test",
                    chunk_type="text",
                    metadata={},
                    chunk_index=0,
                ),
            ]

            jsonl_path = client._create_jsonl_file(chunks)

            try:
                with open(jsonl_path, "r") as f:
                    data = json.loads(f.readline())

                request = data["request"]

                # Проверяем структуру
                assert "contents" in request, "Должен быть 'contents'"
                assert "content" not in request, "Не должно быть 'content'"
                assert isinstance(request["contents"], list), "'contents' должен быть списком"
                assert len(request["contents"]) == 1
                assert "parts" in request["contents"][0]

            finally:
                Path(jsonl_path).unlink(missing_ok=True)

    def test_jsonl_includes_config(self, mock_embedder):
        """JSONL должен включать config с task_type и output_dimensionality."""
        from semantic_core.infrastructure.gemini.batching import (
            GeminiBatchClient,
            GENAI_SDK_AVAILABLE,
        )

        if not GENAI_SDK_AVAILABLE:
            pytest.skip("google-genai SDK not installed")

        with patch("semantic_core.infrastructure.gemini.batching.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client

            client = GeminiBatchClient(
                api_key="test-key",
                dimension=512,  # Кастомная размерность
            )

            chunks = [
                Chunk(
                    id="1",
                    content="Test",
                    chunk_type="text",
                    metadata={},
                    chunk_index=0,
                ),
            ]

            jsonl_path = client._create_jsonl_file(chunks)

            try:
                with open(jsonl_path, "r") as f:
                    data = json.loads(f.readline())

                config = data["request"]["config"]

                assert config["task_type"] == "RETRIEVAL_DOCUMENT"
                assert config["output_dimensionality"] == 512

            finally:
                Path(jsonl_path).unlink(missing_ok=True)

    def test_jsonl_uses_context_text_when_provided(self, mock_embedder):
        """JSONL должен использовать context_text если он предоставлен."""
        from semantic_core.infrastructure.gemini.batching import (
            GeminiBatchClient,
            GENAI_SDK_AVAILABLE,
        )

        if not GENAI_SDK_AVAILABLE:
            pytest.skip("google-genai SDK not installed")

        with patch("semantic_core.infrastructure.gemini.batching.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client

            client = GeminiBatchClient(api_key="test-key")

            chunks = [
                Chunk(
                    id="1",
                    content="Original content",
                    chunk_type="text",
                    metadata={},
                    chunk_index=0,
                ),
            ]

            context_texts = {"1": "Context enriched content"}

            jsonl_path = client._create_jsonl_file(chunks, context_texts)

            try:
                with open(jsonl_path, "r") as f:
                    data = json.loads(f.readline())

                text = data["request"]["contents"][0]["parts"][0]["text"]
                assert text == "Context enriched content", "Должен использоваться context_text"

            finally:
                Path(jsonl_path).unlink(missing_ok=True)


class TestStatusMapping:
    """Тесты маппинга статусов Google -> наши."""

    def test_status_mapping_values(self):
        """Проверка всех маппингов статусов."""
        from semantic_core.infrastructure.gemini.batching import GOOGLE_STATUS_MAP

        # Проверяем известные статусы
        assert GOOGLE_STATUS_MAP["JOB_STATE_QUEUED"] == "QUEUED"
        assert GOOGLE_STATUS_MAP["JOB_STATE_PENDING"] == "QUEUED"
        assert GOOGLE_STATUS_MAP["JOB_STATE_RUNNING"] == "RUNNING"
        assert GOOGLE_STATUS_MAP["JOB_STATE_SUCCEEDED"] == "SUCCEEDED"
        assert GOOGLE_STATUS_MAP["JOB_STATE_FAILED"] == "FAILED"
        assert GOOGLE_STATUS_MAP["JOB_STATE_CANCELLED"] == "CANCELLED"

    def test_completed_states(self):
        """Проверка терминальных статусов."""
        from semantic_core.infrastructure.gemini.batching import COMPLETED_STATES

        assert "JOB_STATE_SUCCEEDED" in COMPLETED_STATES
        assert "JOB_STATE_FAILED" in COMPLETED_STATES
        assert "JOB_STATE_CANCELLED" in COMPLETED_STATES
        assert "JOB_STATE_RUNNING" not in COMPLETED_STATES
        assert "JOB_STATE_QUEUED" not in COMPLETED_STATES


class TestVectorConversion:
    """Тесты конвертации векторов в bytes."""

    def test_vector_to_bytes_format(self):
        """Проверка формата bytes для вектора."""
        values = [0.1, 0.2, 0.3, 0.4]

        # Конвертируем как в batching.py
        blob = struct.pack(f"{len(values)}f", *values)

        # Проверяем размер (4 float32 = 16 bytes)
        assert len(blob) == 16

        # Декодируем обратно
        unpacked = struct.unpack(f"{len(values)}f", blob)
        assert len(unpacked) == 4
        assert abs(unpacked[0] - 0.1) < 0.0001
        assert abs(unpacked[1] - 0.2) < 0.0001


class TestClientInitialization:
    """Тесты инициализации клиента."""

    def test_init_with_custom_params(self):
        """Инициализация с кастомными параметрами."""
        from semantic_core.infrastructure.gemini.batching import (
            GeminiBatchClient,
            GENAI_SDK_AVAILABLE,
        )

        if not GENAI_SDK_AVAILABLE:
            pytest.skip("google-genai SDK not installed")

        with patch("semantic_core.infrastructure.gemini.batching.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client

            client = GeminiBatchClient(
                api_key="test-key",
                model_name="models/custom-embedding",
                dimension=1024,
            )

            assert client.model_name == "models/custom-embedding"
            assert client.dimension == 1024
            assert client.api_key == "test-key"

    def test_init_raises_on_missing_sdk(self):
        """Должен поднять ImportError если SDK не установлен."""
        from semantic_core.infrastructure.gemini import batching

        # Временно "отключаем" SDK
        original_available = batching.GENAI_SDK_AVAILABLE
        batching.GENAI_SDK_AVAILABLE = False

        try:
            with pytest.raises(ImportError, match="google-genai SDK not installed"):
                batching.GeminiBatchClient(api_key="test")
        finally:
            batching.GENAI_SDK_AVAILABLE = original_available
