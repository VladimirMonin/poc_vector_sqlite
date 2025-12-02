"""Реализация BaseVectorStore для Peewee + SQLite.

Классы:
    PeeweeVectorStore
        Адаптер для хранилища векторов на основе SQLite.
"""

import json
from typing import Optional, Any

import numpy as np
from peewee import fn

from semantic_core.interfaces import BaseVectorStore
from semantic_core.domain import Document, Chunk, SearchResult, MatchType, MediaType
from semantic_core.infrastructure.storage.peewee.models import (
    DocumentModel,
    ChunkModel,
)
from semantic_core.infrastructure.storage.peewee.engine import VectorDatabase


class PeeweeVectorStore(BaseVectorStore):
    """Адаптер хранилища для SQLite + Peewee + sqlite-vec.
    
    Реализует BaseVectorStore с поддержкой:
    - Parent-Child архитектуры (Document → Chunks).
    - Векторного поиска через vec0.
    - Полнотекстового поиска через fts5.
    - Гибридного поиска (RRF).
    
    Attributes:
        db: Экземпляр VectorDatabase.
        dimension: Размерность векторов.
    """
    
    def __init__(self, database: VectorDatabase, dimension: int = 768):
        """Инициализация адаптера.
        
        Args:
            database: Настроенный экземпляр VectorDatabase.
            dimension: Размерность векторов (для vec0 таблицы).
        """
        self.db = database
        self.dimension = dimension
        
        # Привязываем модели к БД
        DocumentModel._meta.database = self.db
        ChunkModel._meta.database = self.db
        
        # Создаём таблицы
        self._create_tables()
    
    def _create_tables(self) -> None:
        """Создаёт таблицы и виртуальные индексы."""
        # Создаём обычные таблицы
        self.db.create_tables([DocumentModel, ChunkModel], safe=True)
        
        # Создаём векторную таблицу vec0
        self.db.execute_sql(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec
            USING vec0(
                id INTEGER PRIMARY KEY,
                embedding FLOAT[{self.dimension}]
            )
        """)
        
        # Создаём FTS5 таблицу для документов
        self.db.execute_sql("""
            CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts
            USING fts5(
                id UNINDEXED,
                content,
                content=documents,
                content_rowid=id
            )
        """)
        
        # Триггеры для автоматического обновления FTS
        self.db.execute_sql("""
            CREATE TRIGGER IF NOT EXISTS documents_fts_insert
            AFTER INSERT ON documents BEGIN
                INSERT INTO documents_fts(rowid, content)
                VALUES (new.id, new.content);
            END
        """)
        
        self.db.execute_sql("""
            CREATE TRIGGER IF NOT EXISTS documents_fts_delete
            AFTER DELETE ON documents BEGIN
                DELETE FROM documents_fts WHERE rowid = old.id;
            END
        """)
        
        self.db.execute_sql("""
            CREATE TRIGGER IF NOT EXISTS documents_fts_update
            AFTER UPDATE ON documents BEGIN
                UPDATE documents_fts
                SET content = new.content
                WHERE rowid = new.id;
            END
        """)
    
    def save(self, document: Document, chunks: list[Chunk]) -> Document:
        """Сохраняет документ с чанками атомарно.
        
        Args:
            document: Родительский документ.
            chunks: Список чанков с векторами.
            
        Returns:
            Document с заполненным id.
            
        Raises:
            ValueError: Если данные некорректны.
            RuntimeError: Если БД вернула ошибку.
        """
        with self.db.atomic():
            # Сохраняем документ
            doc_model = DocumentModel.create(
                content=document.content,
                metadata=json.dumps(document.metadata, ensure_ascii=False),
                media_type=document.media_type.value,
                created_at=document.created_at,
            )
            
            # Обновляем ID документа
            document.id = doc_model.id
            
            # Сохраняем чанки
            for chunk in chunks:
                chunk.parent_doc_id = doc_model.id
                
                # Создаём чанк
                chunk_model = ChunkModel.create(
                    document=doc_model,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    metadata=json.dumps(chunk.metadata, ensure_ascii=False),
                    created_at=chunk.created_at,
                )
                
                chunk.id = chunk_model.id
                
                # Сохраняем вектор
                if chunk.embedding is not None:
                    blob = chunk.embedding.tobytes()
                    self.db.execute_sql(
                        "INSERT INTO chunks_vec(id, embedding) VALUES (?, ?)",
                        (chunk_model.id, blob),
                    )
        
        return document
    
    def search(
        self,
        query_vector: Optional[np.ndarray] = None,
        query_text: Optional[str] = None,
        filters: Optional[dict] = None,
        limit: int = 10,
        mode: str = "hybrid",
    ) -> list[SearchResult]:
        """Выполняет поиск документов.
        
        Args:
            query_vector: Вектор запроса (для векторного поиска).
            query_text: Текст запроса (для FTS).
            filters: Словарь фильтров (metadata).
            limit: Максимальное количество результатов.
            mode: Режим поиска ('vector', 'fts', 'hybrid').
            
        Returns:
            Список SearchResult с документами и скорами.
            
        Raises:
            ValueError: Если не передан ни vector, ни text.
        """
        if mode == "vector":
            return self._vector_search(query_vector, filters, limit)
        elif mode == "fts":
            return self._fts_search(query_text, filters, limit)
        elif mode == "hybrid":
            return self._hybrid_search(query_vector, query_text, filters, limit)
        else:
            raise ValueError(f"Неизвестный режим поиска: {mode}")
    
    def _vector_search(
        self,
        query_vector: np.ndarray,
        filters: Optional[dict],
        limit: int,
    ) -> list[SearchResult]:
        """Векторный поиск через sqlite-vec."""
        if query_vector is None:
            raise ValueError("Для векторного поиска нужен query_vector")
        
        blob = query_vector.tobytes()
        
        # Поиск через vec0
        sql = """
            SELECT
                c.id as chunk_id,
                c.document_id,
                vec_distance_cosine(cv.embedding, ?) as distance
            FROM chunks_vec cv
            JOIN chunks c ON c.id = cv.id
            ORDER BY distance
            LIMIT ?
        """
        
        cursor = self.db.execute_sql(sql, (blob, limit))
        results = []
        
        for row in cursor.fetchall():
            chunk_id, doc_id, distance = row
            score = 1.0 - distance  # Конвертируем distance в similarity
            
            # Загружаем документ
            doc_model = DocumentModel.get_by_id(doc_id)
            document = self._model_to_document(doc_model)
            
            results.append(
                SearchResult(
                    document=document,
                    score=score,
                    match_type=MatchType.VECTOR,
                    chunk_id=chunk_id,
                )
            )
        
        return results
    
    def _fts_search(
        self,
        query_text: str,
        filters: Optional[dict],
        limit: int,
    ) -> list[SearchResult]:
        """Полнотекстовый поиск через FTS5."""
        if not query_text:
            raise ValueError("Для FTS поиска нужен query_text")
        
        sql = """
            SELECT
                d.id,
                rank
            FROM documents_fts fts
            JOIN documents d ON d.id = fts.rowid
            WHERE documents_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """
        
        cursor = self.db.execute_sql(sql, (query_text, limit))
        results = []
        
        for row in cursor.fetchall():
            doc_id, rank = row
            
            doc_model = DocumentModel.get_by_id(doc_id)
            document = self._model_to_document(doc_model)
            
            results.append(
                SearchResult(
                    document=document,
                    score=abs(rank),  # rank отрицательный, инвертируем
                    match_type=MatchType.FTS,
                )
            )
        
        return results
    
    def _hybrid_search(
        self,
        query_vector: Optional[np.ndarray],
        query_text: Optional[str],
        filters: Optional[dict],
        limit: int,
    ) -> list[SearchResult]:
        """Гибридный поиск (RRF) - упрощённая версия."""
        # TODO: Реализовать полноценный RRF алгоритм через CTE
        # Пока возвращаем векторные результаты
        if query_vector is not None:
            return self._vector_search(query_vector, filters, limit)
        elif query_text is not None:
            return self._fts_search(query_text, filters, limit)
        else:
            raise ValueError("Нужен хотя бы один параметр: query_vector или query_text")
    
    def delete(self, document_id: int) -> int:
        """Удаляет документ и все его чанки.
        
        Args:
            document_id: ID документа.
            
        Returns:
            Количество удалённых строк.
        """
        with self.db.atomic():
            doc_model = DocumentModel.get_by_id(document_id)
            
            # Удаляем векторы чанков
            chunk_ids = [chunk.id for chunk in doc_model.chunks]
            if chunk_ids:
                placeholders = ", ".join("?" * len(chunk_ids))
                self.db.execute_sql(
                    f"DELETE FROM chunks_vec WHERE id IN ({placeholders})",
                    chunk_ids,
                )
            
            # Удаляем документ (чанки удалятся каскадно)
            return doc_model.delete_instance()
    
    def _model_to_document(self, doc_model: DocumentModel) -> Document:
        """Конвертирует ORM модель в DTO.
        
        Args:
            doc_model: Экземпляр DocumentModel.
            
        Returns:
            Document DTO.
        """
        return Document(
            id=doc_model.id,
            content=doc_model.content,
            metadata=json.loads(doc_model.metadata),
            media_type=MediaType(doc_model.media_type),
            created_at=doc_model.created_at,
        )
