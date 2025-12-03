"""E2E тесты с реальным Google Batch API для эмбеддингов.

⚠️ ВНИМАНИЕ: Эти тесты тратят токены! (но на 50% дешевле синхронного режима)

Запуск:
    export GEMINI_API_KEY="your-key"
    pytest tests/e2e/gemini/test_real_batch.py -v -s --timeout=0

Batch API особенности:
    - SLA до 24 часов, но обычно быстрее (минуты для маленьких заданий)
    - 50% скидка на embeddings
    - Используем gemini-embedding-001 (единственная модель с asyncBatchEmbedContent)
    - MRL позволяет использовать 768 dimensions (совместимо с нашей БД)
"""

import os
import struct
import time

import pytest

from semantic_core.domain import Chunk, ChunkType


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def api_key():
    """API ключ из окружения."""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        pytest.skip("GEMINI_API_KEY not set")
    return key


@pytest.fixture
def batch_client(api_key):
    """Реальный GeminiBatchClient для gemini-embedding-001."""
    from semantic_core.infrastructure.gemini.batching import (
        GeminiBatchClient,
        GENAI_SDK_AVAILABLE,
    )
    
    if not GENAI_SDK_AVAILABLE:
        pytest.skip("google-genai SDK not installed")
    
    # gemini-embedding-001 поддерживает Batch API и MRL (768 dimensions)
    return GeminiBatchClient(
        api_key=api_key,
        model_name="models/gemini-embedding-001",
        dimension=768,
    )


# =============================================================================
# E2E Tests - БЕЗ ТАЙМАУТА (ждём сколько нужно)
# =============================================================================


@pytest.mark.real_api
@pytest.mark.timeout(0)  # Отключаем таймаут pytest
class TestRealBatchAPI:
    """E2E тесты с реальным Google Batch API.
    
    ВАЖНО: Batch API может работать до 24 часов (SLA Google).
    Обычно маленькие задачи выполняются за минуты, но гарантий нет.
    Таймаут отключён - тест будет ждать сколько нужно.
    """

    def test_full_batch_lifecycle(self, batch_client):
        """Полный цикл: создание job -> ожидание -> получение результатов.
        
        Этот тест:
        1. Создаёт 3 чанка с реальным текстом
        2. Отправляет batch job в Google Cloud
        3. Ожидает завершения (polling каждые 30 сек, БЕЗ таймаута)
        4. Скачивает и проверяет embeddings
        """
        # 1. Подготовка чанков
        chunks = [
            Chunk(
                id="test_chunk_1",
                content="Python is a high-level programming language known for its simplicity.",
                chunk_type=ChunkType.TEXT,
                chunk_index=0,
                metadata={"source": "e2e_test"},
            ),
            Chunk(
                id="test_chunk_2", 
                content="Machine learning enables computers to learn from data without explicit programming.",
                chunk_type=ChunkType.TEXT,
                chunk_index=1,
                metadata={"source": "e2e_test"},
            ),
            Chunk(
                id="test_chunk_3",
                content="SQLite is a lightweight embedded database engine.",
                chunk_type=ChunkType.TEXT,
                chunk_index=2,
                metadata={"source": "e2e_test"},
            ),
        ]
        
        # 2. Создаём batch job
        print("\n📤 Creating batch job...")
        job_id = batch_client.create_embedding_job(chunks)
        
        assert job_id is not None, "Job ID should not be None"
        assert "batches/" in job_id, f"Job ID format unexpected: {job_id}"
        print(f"✅ Job created: {job_id}")
        
        # 3. Ожидаем завершения БЕЗ таймаута
        print("⏳ Waiting for job completion (no timeout, Ctrl+C to abort)...")
        poll_interval = 30  # 30 секунд между проверками
        elapsed = 0
        status = None
        
        while True:
            status = batch_client.get_job_status(job_id)
            print(f"   [{elapsed//60}m {elapsed%60}s] Status: {status}")
            
            if status == "SUCCEEDED":
                print("✅ Job completed successfully!")
                break
            elif status in ("FAILED", "CANCELLED"):
                pytest.fail(f"Job failed with status: {status}")
            
            time.sleep(poll_interval)
            elapsed += poll_interval
        
        # 4. Получаем результаты
        print("📥 Retrieving results...")
        results = batch_client.retrieve_results(job_id)
        
        # 5. Проверяем результаты
        assert len(results) == 3, f"Expected 3 results, got {len(results)}"
        
        for chunk_id in ["test_chunk_1", "test_chunk_2", "test_chunk_3"]:
            assert chunk_id in results, f"Missing result for {chunk_id}"
            
            vector_blob = results[chunk_id]
            assert isinstance(vector_blob, bytes), f"Result should be bytes, got {type(vector_blob)}"
            
            # Проверяем размер: 768 floats * 4 bytes = 3072 bytes
            expected_size = 768 * 4
            assert len(vector_blob) == expected_size, (
                f"Vector size mismatch for {chunk_id}: "
                f"expected {expected_size}, got {len(vector_blob)}"
            )
            
            # Декодируем и проверяем значения
            values = struct.unpack("768f", vector_blob)
            assert len(values) == 768, f"Expected 768 values, got {len(values)}"
            
            # Проверяем, что это реальные числа (не NaN, не Inf)
            assert all(-10 < v < 10 for v in values), "Values should be normalized"
            
            print(f"   ✅ {chunk_id}: {len(values)} dimensions, first 3: {values[:3]}")
        
        total_time = elapsed
        print(f"\n🎉 Full batch lifecycle test passed! Total time: {total_time//60}m {total_time%60}s")


@pytest.mark.real_api
class TestBatchJobCreation:
    """Быстрые тесты создания job (без ожидания завершения)."""

    def test_job_creation_returns_valid_id(self, batch_client):
        """Проверка, что создание job возвращает валидный ID."""
        chunks = [
            Chunk(
                id="status_test",
                content="Quick test content",
                chunk_type=ChunkType.TEXT,
                chunk_index=0,
                metadata={},
            ),
        ]
        
        job_id = batch_client.create_embedding_job(chunks)
        
        # Проверяем формат
        assert job_id.startswith("batches/"), f"Unexpected format: {job_id}"
        
        # Проверяем, что можем получить статус
        status = batch_client.get_job_status(job_id)
        assert status in ("QUEUED", "RUNNING", "SUCCEEDED"), f"Unexpected status: {status}"
        
        print(f"✅ Job {job_id} created, status: {status}")
        print("   (Job left running - will complete in background)")
    
    def test_job_with_context_texts_creates(self, batch_client):
        """Тест создания batch с context_texts."""
        chunks = [
            Chunk(
                id="ctx_chunk_1",
                content="Short content",
                chunk_type=ChunkType.TEXT,
                chunk_index=0,
                metadata={},
            ),
        ]
        
        context_texts = {
            "ctx_chunk_1": "# Document Title\n\nSection: Introduction\n\nShort content"
        }
        
        print("\n📤 Creating batch job with context_texts...")
        job_id = batch_client.create_embedding_job(chunks, context_texts)
        
        assert job_id.startswith("batches/")
        status = batch_client.get_job_status(job_id)
        assert status in ("QUEUED", "RUNNING", "SUCCEEDED")
        
        print(f"✅ Job {job_id} created with context_texts, status: {status}")
