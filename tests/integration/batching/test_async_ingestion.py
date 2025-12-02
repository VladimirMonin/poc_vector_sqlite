"""Integration-тесты для асинхронного режима ingest.

Проверяет:
- ingest(mode='async') сохраняет чанки со статусом PENDING
- Векторы не создаются в vec0 таблице
- metadata['_vector_source'] сохраняется
- Регрессия: mode='sync' работает как прежде
"""

import pytest
import json

from semantic_core.domain import Document
from semantic_core.infrastructure.storage.peewee.models import (
    ChunkModel,
    EmbeddingStatus,
)


class TestAsyncIngestion:
    """Тесты асинхронного режима загрузки документов."""
    
    def test_async_mode_creates_pending_chunks(self, semantic_core, in_memory_db):
        """ingest(mode='async') должен создавать PENDING чанки."""
        doc = Document(
            content="This is a test document for async ingestion",
            metadata={"title": "Async Test", "category": "test"},
        )
        
        saved_doc = semantic_core.ingest(doc, mode="async")
        
        # Проверяем, что документ сохранился
        assert saved_doc.id is not None, "Документ должен получить ID"
        
        # Проверяем чанки в БД
        chunks = ChunkModel.select().where(ChunkModel.document_id == saved_doc.id)
        assert chunks.count() > 0, "Должны быть созданы чанки"
        
        # Проверяем статусы
        for chunk in chunks:
            assert chunk.embedding_status == EmbeddingStatus.PENDING.value, \
                f"Чанк {chunk.id} должен иметь статус PENDING"
    
    def test_async_mode_no_vectors_in_vec0(self, semantic_core, in_memory_db):
        """В async режиме векторы не должны попадать в chunks_vec."""
        doc = Document(
            content="Document without immediate vectors",
            metadata={"title": "No Vectors"},
        )
        
        saved_doc = semantic_core.ingest(doc, mode="async")
        
        # Проверяем, что в chunks_vec нет записей для этих чанков
        chunks = ChunkModel.select().where(ChunkModel.document_id == saved_doc.id)
        
        for chunk in chunks:
            # Проверяем отсутствие в vec0
            cursor = in_memory_db.execute_sql(
                "SELECT id FROM chunks_vec WHERE id = ?",
                (chunk.id,)
            )
            result = cursor.fetchone()
            assert result is None, f"Чанк {chunk.id} не должен быть в chunks_vec"
    
    def test_async_mode_saves_vector_source(self, semantic_core):
        """metadata['_vector_source'] должен сохраняться для async чанков."""
        doc = Document(
            content="# Title\n\nContent with context",
            metadata={"title": "Context Test"},
        )
        
        saved_doc = semantic_core.ingest(doc, mode="async")
        
        # Проверяем metadata
        chunks = ChunkModel.select().where(ChunkModel.document_id == saved_doc.id)
        
        for chunk in chunks:
            meta = json.loads(chunk.metadata)
            assert "_vector_source" in meta, "Должен быть _vector_source в metadata"
            assert len(meta["_vector_source"]) > 0, "_vector_source не должен быть пустым"
    
    def test_sync_mode_still_works(self, semantic_core, in_memory_db):
        """Регрессия: mode='sync' должен работать как раньше."""
        doc = Document(
            content="Document in sync mode",
            metadata={"title": "Sync Test"},
        )
        
        saved_doc = semantic_core.ingest(doc, mode="sync")
        
        # Проверяем статусы
        chunks = ChunkModel.select().where(ChunkModel.document_id == saved_doc.id)
        
        for chunk in chunks:
            # Должен быть READY, а не PENDING
            assert chunk.embedding_status == EmbeddingStatus.READY.value, \
                f"Чанк {chunk.id} должен иметь статус READY в sync режиме"
            
            # Должен быть вектор в vec0
            cursor = in_memory_db.execute_sql(
                "SELECT id FROM chunks_vec WHERE id = ?",
                (chunk.id,)
            )
            result = cursor.fetchone()
            assert result is not None, f"Чанк {chunk.id} должен быть в chunks_vec"
    
    def test_default_mode_is_sync(self, semantic_core):
        """По умолчанию (без mode) должен использоваться sync."""
        doc = Document(
            content="Document with default mode",
            metadata={"title": "Default Mode"},
        )
        
        # Вызываем без параметра mode
        saved_doc = semantic_core.ingest(doc)
        
        # Проверяем, что чанки READY (sync режим)
        chunks = ChunkModel.select().where(ChunkModel.document_id == saved_doc.id)
        
        for chunk in chunks:
            assert chunk.embedding_status == EmbeddingStatus.READY.value, \
                "По умолчанию должен быть sync режим"


class TestMixedModeUsage:
    """Тесты совместного использования sync и async режимов."""
    
    def test_sync_and_async_documents_coexist(self, semantic_core):
        """Sync и async документы могут существовать в одной БД."""
        # Создаём sync документ
        sync_doc = Document(
            content="Sync document content",
            metadata={"title": "Sync", "mode": "sync"},
        )
        saved_sync = semantic_core.ingest(sync_doc, mode="sync")
        
        # Создаём async документ
        async_doc = Document(
            content="Async document content",
            metadata={"title": "Async", "mode": "async"},
        )
        saved_async = semantic_core.ingest(async_doc, mode="async")
        
        # Проверяем sync чанки
        sync_chunks = ChunkModel.select().where(
            ChunkModel.document_id == saved_sync.id
        )
        for chunk in sync_chunks:
            assert chunk.embedding_status == EmbeddingStatus.READY.value
        
        # Проверяем async чанки
        async_chunks = ChunkModel.select().where(
            ChunkModel.document_id == saved_async.id
        )
        for chunk in async_chunks:
            assert chunk.embedding_status == EmbeddingStatus.PENDING.value
