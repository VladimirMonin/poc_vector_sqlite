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
from semantic_core.domain import (
    Document,
    Chunk,
    SearchResult,
    ChunkResult,
    MatchType,
    MediaType,
    ChunkType,
)
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

        # Составной индекс для быстрой фильтрации chunk_type + language
        self.db.execute_sql("""
            CREATE INDEX IF NOT EXISTS idx_chunks_type_lang
            ON chunks(chunk_type, language)
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
                    chunk_type=chunk.chunk_type.value,
                    language=chunk.language,
                    metadata=json.dumps(chunk.metadata, ensure_ascii=False),
                    created_at=chunk.created_at,
                )

                chunk.id = chunk_model.id

                # Сохраняем вектор (поддержка обеих версий: embedding и vector для обратной совместимости)
                vector = getattr(chunk, "vector", None)
                if vector is None:
                    vector = getattr(chunk, "embedding", None)

                if vector is not None:
                    blob = vector.tobytes()
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
        k: int = 60,
    ) -> list[SearchResult]:
        """Выполняет поиск документов.

        Args:
            query_vector: Вектор запроса (для векторного поиска).
            query_text: Текст запроса (для FTS).
            filters: Словарь фильтров по метаданным (например, {"category": "Python"}).
            limit: Максимальное количество результатов.
            mode: Режим поиска ('vector', 'fts', 'hybrid').
            k: Константа для RRF алгоритма (по умолчанию 60).

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
            return self._hybrid_search(query_vector, query_text, filters, limit, k)
        else:
            raise ValueError(f"Неизвестный режим поиска: {mode}")

    def _vector_search(
        self,
        query_vector: np.ndarray,
        filters: Optional[dict],
        limit: int,
    ) -> list[SearchResult]:
        """Векторный поиск через sqlite-vec.

        Args:
            query_vector: Вектор запроса.
            filters: Фильтры по метаданным (JSON).
            limit: Количество результатов.

        Returns:
            Список SearchResult.
        """
        if query_vector is None:
            raise ValueError("Для векторного поиска нужен query_vector")

        blob = query_vector.tobytes()

        # Формируем WHERE условия для фильтров
        where_conditions = []
        where_params = []
        if filters:
            for key, value in filters.items():
                where_conditions.append(f"json_extract(d.metadata, '$.{key}') = ?")
                where_params.append(value)

        where_clause = (
            f"AND {' AND '.join(where_conditions)}" if where_conditions else ""
        )

        # Поиск через vec0
        sql = f"""
            SELECT
                c.id as chunk_id,
                c.document_id,
                vec_distance_cosine(cv.embedding, ?) as distance
            FROM chunks_vec cv
            JOIN chunks c ON c.id = cv.id
            JOIN documents d ON d.id = c.document_id
            WHERE 1=1 {where_clause}
            ORDER BY distance
            LIMIT ?
        """

        params = [blob] + where_params + [limit]
        cursor = self.db.execute_sql(sql, params)
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
        """Полнотекстовый поиск через FTS5.

        Args:
            query_text: Текст запроса.
            filters: Фильтры по метаданным (JSON).
            limit: Количество результатов.

        Returns:
            Список SearchResult.
        """
        if not query_text:
            raise ValueError("Для FTS поиска нужен query_text")

        # Формируем WHERE условия для фильтров
        where_conditions = []
        where_params = []
        if filters:
            for key, value in filters.items():
                where_conditions.append(f"json_extract(d.metadata, '$.{key}') = ?")
                where_params.append(value)

        where_clause = (
            f"AND {' AND '.join(where_conditions)}" if where_conditions else ""
        )

        sql = f"""
            SELECT
                d.id,
                fts.rank
            FROM documents_fts fts
            JOIN documents d ON d.id = fts.rowid
            WHERE documents_fts MATCH ?
            {where_clause}
            ORDER BY fts.rank
            LIMIT ?
        """

        params = [query_text] + where_params + [limit]
        cursor = self.db.execute_sql(sql, params)
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
        k: int = 60,
    ) -> list[SearchResult]:
        """Гибридный поиск с RRF (Reciprocal Rank Fusion).

        Алгоритм:
        1. Выполняет векторный поиск (TOP 100).
        2. Выполняет FTS поиск (TOP 100).
        3. Объединяет через RRF: score = 1/(k+rank_vec) + 1/(k+rank_fts).
        4. Возвращает TOP N по RRF score.

        Args:
            query_vector: Вектор запроса.
            query_text: Текст запроса.
            filters: Фильтры по метаданным.
            limit: Итоговое количество результатов.
            k: Константа RRF (обычно 60).

        Returns:
            Список SearchResult, отсортированный по RRF score.
        """
        if query_vector is None and query_text is None:
            raise ValueError("Нужен хотя бы один параметр: query_vector или query_text")

        # Если только один метод, используем его напрямую
        if query_vector is None:
            return self._fts_search(query_text, filters, limit)
        if query_text is None:
            return self._vector_search(query_vector, filters, limit)

        # Формируем WHERE условия для фильтров
        where_conditions = []
        where_params = []
        if filters:
            for key, value in filters.items():
                # Фильтруем по metadata JSON
                where_conditions.append(f"json_extract(main.metadata, '$.{key}') = ?")
                where_params.append(value)

        where_clause = (
            f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
        )

        # Подготовка blob для векторного поиска
        blob = query_vector.tobytes()

        # SQL запрос с RRF через CTE
        sql = f"""
            WITH vector_results AS (
                SELECT 
                    c.document_id as doc_id,
                    ROW_NUMBER() OVER (
                        ORDER BY vec_distance_cosine(cv.embedding, ?)
                    ) as rank
                FROM chunks_vec cv
                JOIN chunks c ON c.id = cv.id
                JOIN documents main ON main.id = c.document_id
                {where_clause}
                LIMIT 100
            ),
            fts_results AS (
                SELECT 
                    main.id as doc_id,
                    ROW_NUMBER() OVER (ORDER BY fts.rank) as rank
                FROM documents_fts fts
                JOIN documents main ON main.id = fts.rowid
                WHERE documents_fts MATCH ?
                {f"AND {' AND '.join(where_conditions)}" if where_conditions else ""}
                LIMIT 100
            ),
            rrf_scores AS (
                SELECT 
                    COALESCE(v.doc_id, f.doc_id) as doc_id,
                    (
                        COALESCE(1.0 / (? + v.rank), 0.0) + 
                        COALESCE(1.0 / (? + f.rank), 0.0)
                    ) as rrf_score
                FROM vector_results v
                FULL OUTER JOIN fts_results f ON v.doc_id = f.doc_id
            )
            SELECT doc_id, rrf_score
            FROM rrf_scores
            ORDER BY rrf_score DESC
            LIMIT ?
        """

        # Собираем параметры: blob, where_params, query_text, where_params, k, k, limit
        params = [blob] + where_params + [query_text] + where_params + [k, k, limit]

        cursor = self.db.execute_sql(sql, params)
        results = []

        for row in cursor.fetchall():
            doc_id, rrf_score = row

            # Загружаем документ
            doc_model = DocumentModel.get_by_id(doc_id)
            document = self._model_to_document(doc_model)

            results.append(
                SearchResult(
                    document=document,
                    score=rrf_score,
                    match_type=MatchType.HYBRID,
                )
            )

        return results

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

    def delete_by_metadata(self, filters: dict) -> int:
        """Удаляет чанки по фильтрам метаданных.

        Args:
            filters: Словарь фильтров по метаданным (например, {"source_id": "123"}).

        Returns:
            Количество удалённых чанков.
        """
        # Находим все чанки, которые соответствуют фильтрам
        query = ChunkModel.select()

        for key, value in filters.items():
            # Используем JSON функции SQLite для фильтрации по метаданным
            # json_extract может вернуть число, строку или null
            # Сравниваем без приведения типов - SQLite сам справится
            query = query.where(
                fn.json_extract(ChunkModel.metadata, f"$.{key}") == value
            )

        chunk_ids = [chunk.id for chunk in query]

        if not chunk_ids:
            return 0

        with self.db.atomic():
            # Удаляем векторы из vec0
            placeholders = ", ".join("?" * len(chunk_ids))
            self.db.execute_sql(
                f"DELETE FROM chunks_vec WHERE id IN ({placeholders})",
                chunk_ids,
            )

            # Удаляем сами чанки
            deleted_count = (
                ChunkModel.delete().where(ChunkModel.id.in_(chunk_ids)).execute()
            )

            return deleted_count

    def search_chunks(
        self,
        query_vector: Optional[np.ndarray] = None,
        query_text: Optional[str] = None,
        filters: Optional[dict] = None,
        limit: int = 10,
        mode: str = "hybrid",
        k: int = 60,
        chunk_type_filter: Optional[str] = None,
        language_filter: Optional[str] = None,
    ) -> list[ChunkResult]:
        """Выполняет гранулярный поиск отдельных чанков.

        Args:
            query_vector: Вектор запроса (для векторного поиска).
            query_text: Текст запроса (для FTS).
            filters: Словарь фильтров по метаданным документа.
            limit: Максимальное количество результатов.
            mode: Режим поиска ('vector', 'fts', 'hybrid').
            k: Константа для RRF алгоритма.
            chunk_type_filter: Фильтр по типу чанка.
            language_filter: Фильтр по языку программирования.

        Returns:
            Список ChunkResult.
        """
        if mode == "vector":
            return self._vector_search_chunks(
                query_vector, filters, limit, chunk_type_filter, language_filter
            )
        elif mode == "fts":
            # FTS для чанков пока не реализован, возвращаем пустой список
            return []
        elif mode == "hybrid":
            # Для гибридного используем только векторный поиск чанков
            return self._vector_search_chunks(
                query_vector, filters, limit, chunk_type_filter, language_filter
            )
        else:
            raise ValueError(f"Неизвестный режим поиска: {mode}")

    def _vector_search_chunks(
        self,
        query_vector: np.ndarray,
        filters: Optional[dict],
        limit: int,
        chunk_type_filter: Optional[str],
        language_filter: Optional[str],
    ) -> list[ChunkResult]:
        """Векторный поиск чанков.

        Args:
            query_vector: Вектор запроса.
            filters: Фильтры по метаданным документа.
            limit: Количество результатов.
            chunk_type_filter: Фильтр по типу чанка.
            language_filter: Фильтр по языку программирования.

        Returns:
            Список ChunkResult.
        """
        if query_vector is None:
            return []

        query_blob = query_vector.tobytes()

        # SQL для векторного поиска с JOIN к документу
        # Используем тот же подход, что в _vector_search: только distance, без MATCH
        sql = """
            SELECT 
                c.id,
                c.chunk_index,
                c.content,
                c.chunk_type,
                c.language,
                c.metadata as chunk_metadata,
                c.created_at,
                d.id as doc_id,
                d.content as doc_content,
                d.metadata as doc_metadata,
                d.media_type,
                d.created_at as doc_created_at,
                vec_distance_cosine(cv.embedding, ?) as distance
            FROM chunks_vec cv
            JOIN chunks c ON c.id = cv.id
            JOIN documents d ON d.id = c.document_id
            WHERE 1=1
        """

        # Параметры в порядке появления плейсхолдеров
        params = [query_blob]  # Для vec_distance_cosine

        # Дополнительные фильтры
        filter_conditions = []

        # Фильтр по типу чанка
        if chunk_type_filter:
            filter_conditions.append("c.chunk_type = ?")
            # Конвертируем ChunkType enum в строку для SQL
            chunk_type_value = (
                chunk_type_filter.value
                if hasattr(chunk_type_filter, "value")
                else chunk_type_filter
            )
            params.append(chunk_type_value)

        # Фильтр по языку
        if language_filter:
            filter_conditions.append("c.language = ?")
            params.append(language_filter)

        # Фильтры по метаданным документа
        if filters:
            for key, value in filters.items():
                filter_conditions.append(f"json_extract(d.metadata, '$.{key}') = ?")
                params.append(value)

        if filter_conditions:
            sql += " AND " + " AND ".join(filter_conditions)

        sql += f"""
            ORDER BY distance
            LIMIT ?
        """
        params.append(limit)

        # Выполняем запрос
        cursor = self.db.execute_sql(sql, params)
        rows = cursor.fetchall()

        # Преобразуем результаты в ChunkResult
        results = []
        for row in rows:
            (
                chunk_id,
                chunk_index,
                content,
                chunk_type,
                language,
                chunk_metadata,
                chunk_created_at,
                doc_id,
                doc_content,
                doc_metadata,
                media_type,
                doc_created_at,
                distance,  # distance теперь в конце
            ) = row

            # Создаём Chunk DTO
            chunk = Chunk(
                id=chunk_id,
                content=content,
                chunk_index=chunk_index,
                chunk_type=ChunkType(chunk_type),
                language=language,
                parent_doc_id=doc_id,
                metadata=json.loads(chunk_metadata),
                created_at=chunk_created_at,
            )

            # Извлекаем заголовок из метаданных документа
            doc_meta = json.loads(doc_metadata)
            doc_title = doc_meta.get("title")

            # Конвертируем расстояние в скор (0.0 - 1.0)
            score = 1.0 / (1.0 + distance)

            results.append(
                ChunkResult(
                    chunk=chunk,
                    score=score,
                    match_type=MatchType.VECTOR,
                    parent_doc_id=doc_id,
                    parent_doc_title=doc_title,
                    parent_metadata=doc_meta,
                )
            )

        return results

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

    def bulk_update_vectors(self, vectors_dict: dict[str, bytes]) -> int:
        """Массово обновляет векторы для чанков.
        
        Используется для высокоскоростной записи результатов батч-обработки.
        Применяет executemany() для максимальной производительности.
        
        Args:
            vectors_dict: Словарь {chunk_id -> vector_blob}.
                chunk_id должен быть строковым представлением int ID.
        
        Returns:
            Количество обновлённых чанков.
        
        Raises:
            ValueError: Если словарь пустой.
            RuntimeError: Если произошла ошибка БД.
        """
        if not vectors_dict:
            raise ValueError("Словарь векторов не может быть пустым")
        
        # Подготавливаем данные для executemany
        data = [(int(chunk_id), blob) for chunk_id, blob in vectors_dict.items()]
        
        try:
            # Вставляем/обновляем векторы в vec0 таблице
            cursor = self.db.execute_sql(
                "INSERT OR REPLACE INTO chunks_vec(id, embedding) VALUES (?, ?)",
                data,
                commit=False,
            )
            
            # Обновляем статус чанков на READY
            chunk_ids = list(vectors_dict.keys())
            placeholders = ",".join(["?"] * len(chunk_ids))
            
            self.db.execute_sql(
                f"""
                UPDATE chunks 
                SET embedding_status = 'READY',
                    batch_job_id = NULL,
                    error_message = NULL
                WHERE id IN ({placeholders})
                """,
                chunk_ids,
                commit=False,
            )
            
            # Коммитим транзакцию
            self.db.commit()
            
            return len(vectors_dict)
        
        except Exception as e:
            self.db.rollback()
            raise RuntimeError(f"Ошибка при массовом обновлении векторов: {e}")
