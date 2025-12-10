"""Реализация BaseVectorStore для Peewee + SQLite.

Классы:
    PeeweeVectorStore
        Адаптер для хранилища векторов на основе SQLite.
"""

import json
import re
import time
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
    BatchJobModel,
    MediaTaskModel,
)
from semantic_core.infrastructure.storage.peewee.engine import VectorDatabase
from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)


def _sanitize_fts_query(query: str) -> str:
    """Экранирует запрос для FTS5.

    FTS5 использует специальные операторы:
    - `-` (минус/дефис) = NOT оператор
    - `*` = prefix match
    - `"..."` = phrase match
    - `[...]` = column filter
    - `OR`, `AND`, `NOT` = логические операторы

    Стратегия:
    - Токены с дефисами (не в начале) оборачиваем в кавычки
    - Токены с квадратными скобками оборачиваем в кавычки

    Args:
        query: Пользовательский запрос.

    Returns:
        Экранированный запрос для FTS5 MATCH.
    """
    # Разбиваем на токены
    tokens = query.split()
    result = []

    for token in tokens:
        needs_quoting = False

        # Дефис внутри токена (не в начале) — нужно экранировать
        if "-" in token and not token.startswith("-"):
            needs_quoting = True

        # Квадратные скобки — FTS5 column filter syntax
        if "[" in token or "]" in token:
            needs_quoting = True

        if needs_quoting:
            # Удаляем кавычки если уже есть
            token = token.strip('"')
            result.append(f'"{token}"')
        else:
            result.append(token)

    return " ".join(result)


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
        BatchJobModel._meta.database = self.db
        MediaTaskModel._meta.database = self.db

        # Создаём таблицы
        self._create_tables()

        logger.debug(
            "PeeweeVectorStore initialized",
            dimension=dimension,
        )

    def _create_tables(self) -> None:
        """Создаёт таблицы и виртуальные индексы."""
        logger.debug("Creating tables and indexes")

        # Создаём обычные таблицы
        self.db.create_tables(
            [DocumentModel, BatchJobModel, ChunkModel, MediaTaskModel], safe=True
        )

        # Создаём векторную таблицу vec0
        self.db.execute_sql(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec
            USING vec0(
                id INTEGER PRIMARY KEY,
                embedding FLOAT[{self.dimension}]
            )
        """)

        # Создаём FTS5 таблицу для чанков (не документов!)
        # Это позволяет RRF объединять результаты на уровне chunk_id
        self.db.execute_sql("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
            USING fts5(
                content,
                content='chunks',
                content_rowid='id'
            )
        """)

        # Составной индекс для быстрой фильтрации chunk_type + language
        self.db.execute_sql("""
            CREATE INDEX IF NOT EXISTS idx_chunks_type_lang
            ON chunks(chunk_type, language)
        """)

        # Триггеры для автоматического обновления chunks_fts
        self.db.execute_sql("""
            CREATE TRIGGER IF NOT EXISTS chunks_fts_insert
            AFTER INSERT ON chunks BEGIN
                INSERT INTO chunks_fts(rowid, content)
                VALUES (new.id, new.content);
            END
        """)

        self.db.execute_sql("""
            CREATE TRIGGER IF NOT EXISTS chunks_fts_delete
            AFTER DELETE ON chunks BEGIN
                DELETE FROM chunks_fts WHERE rowid = old.id;
            END
        """)

        self.db.execute_sql("""
            CREATE TRIGGER IF NOT EXISTS chunks_fts_update
            AFTER UPDATE ON chunks BEGIN
                UPDATE chunks_fts
                SET content = new.content
                WHERE rowid = new.id;
            END
        """)

        # Автомиграция: если chunks_fts пуста, но chunks полна — заполняем
        self._migrate_fts_if_needed()

    def _migrate_fts_if_needed(self) -> None:
        """Автоматически заполняет chunks_fts из существующих чанков.

        Проверяет, есть ли расхождение между chunks и chunks_fts.
        Если chunks не пуста, а chunks_fts пуста — выполняет миграцию.
        """
        try:
            # Проверяем количество записей в chunks
            cursor = self.db.execute_sql("SELECT COUNT(*) FROM chunks")
            chunks_count = cursor.fetchone()[0]

            # Проверяем количество записей в chunks_fts
            cursor = self.db.execute_sql("SELECT COUNT(*) FROM chunks_fts")
            fts_count = cursor.fetchone()[0]

            if chunks_count > 0 and fts_count == 0:
                logger.warning(
                    "FTS index is empty, populating from existing chunks",
                    chunks_count=chunks_count,
                )

                # Массовая вставка существующих чанков в FTS
                self.db.execute_sql("""
                    INSERT INTO chunks_fts(rowid, content)
                    SELECT id, content FROM chunks
                """)

                logger.info(
                    "FTS index populated from existing chunks",
                    migrated_count=chunks_count,
                )
            elif chunks_count > 0 and fts_count > 0 and chunks_count != fts_count:
                logger.warning(
                    "FTS index count mismatch, rebuilding",
                    chunks_count=chunks_count,
                    fts_count=fts_count,
                )
                # Ребилдим FTS индекс
                self.db.execute_sql("DELETE FROM chunks_fts")
                self.db.execute_sql("""
                    INSERT INTO chunks_fts(rowid, content)
                    SELECT id, content FROM chunks
                """)
                logger.info(
                    "FTS index rebuilt",
                    migrated_count=chunks_count,
                )
        except Exception as e:
            # FTS таблица может ещё не существовать
            logger.debug(
                "FTS migration check skipped",
                reason=str(e),
            )

    def save(self, document: Document, chunks: list[Chunk]) -> Document:
        """Сохраняет документ с чанками атомарно.

        Args:
            document: Родительский документ.
            chunks: Список чанков с векторами (или без для async режима).

        Returns:
            Document с заполненным id.

        Raises:
            ValueError: Если данные некорректны.
            RuntimeError: Если БД вернула ошибку.
        """
        start_time = time.perf_counter()
        logger.debug(
            "Saving document",
            chunk_count=len(chunks),
            media_type=document.media_type.value,
        )

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
            vectors_saved = 0
            for chunk in chunks:
                chunk.parent_doc_id = doc_model.id

                # Проверяем статус эмбеддинга из metadata (для async режима)
                embedding_status = chunk.metadata.get(
                    "_embedding_status",
                    "READY",  # По умолчанию READY для sync режима
                )

                # Создаём чанк
                chunk_model = ChunkModel.create(
                    document=doc_model,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    chunk_type=chunk.chunk_type.value,
                    language=chunk.language,
                    metadata=json.dumps(chunk.metadata, ensure_ascii=False),
                    embedding_status=embedding_status,
                    created_at=chunk.created_at,
                )

                chunk.id = chunk_model.id

                # Сохраняем вектор только если он есть (sync режим)
                vector = getattr(chunk, "vector", None)
                if vector is None:
                    vector = getattr(chunk, "embedding", None)

                if vector is not None:
                    blob = vector.tobytes()
                    self.db.execute_sql(
                        "INSERT INTO chunks_vec(id, embedding) VALUES (?, ?)",
                        (chunk_model.id, blob),
                    )
                    vectors_saved += 1

        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Document saved",
            doc_id=document.id,
            chunk_count=len(chunks),
            vectors_saved=vectors_saved,
            latency_ms=round(latency_ms, 2),
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
        start_time = time.perf_counter()
        logger.debug(
            "Search started",
            mode=mode,
            limit=limit,
            has_vector=query_vector is not None,
            has_text=query_text is not None,
            has_filters=filters is not None,
        )

        if mode == "vector":
            results = self._vector_search(query_vector, filters, limit)
        elif mode == "fts":
            results = self._fts_search(query_text, filters, limit)
        elif mode == "hybrid":
            results = self._hybrid_search(query_vector, query_text, filters, limit, k)
        else:
            logger.error("Unknown search mode", mode=mode)
            raise ValueError(f"Неизвестный режим поиска: {mode}")

        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Search completed",
            mode=mode,
            results_count=len(results),
            latency_ms=round(latency_ms, 2),
        )

        return results

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
            logger.warning("Vector search called without query_vector")
            raise ValueError("Для векторного поиска нужен query_vector")

        logger.trace(
            "Vector search",
            vector_dim=len(query_vector),
            limit=limit,
        )

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
        """Полнотекстовый поиск через FTS5 на уровне чанков.

        Args:
            query_text: Текст запроса.
            filters: Фильтры по метаданным документа (JSON).
            limit: Количество результатов.

        Returns:
            Список SearchResult с chunk_id.
        """
        if not query_text:
            logger.warning("FTS search called without query_text")
            raise ValueError("Для FTS поиска нужен query_text")

        # Экранируем специальные символы FTS5
        sanitized_query = _sanitize_fts_query(query_text)

        logger.trace(
            "FTS chunk search",
            query_length=len(query_text),
            sanitized_query=sanitized_query,
            limit=limit,
        )

        # Формируем WHERE условия для фильтров по метаданным документа
        where_conditions = []
        where_params = []
        if filters:
            for key, value in filters.items():
                where_conditions.append(f"json_extract(d.metadata, '$.{key}') = ?")
                where_params.append(value)

        where_clause = (
            f"AND {' AND '.join(where_conditions)}" if where_conditions else ""
        )

        # Поиск по chunks_fts (вместо documents_fts)
        sql = f"""
            SELECT
                c.id as chunk_id,
                c.document_id,
                fts.rank
            FROM chunks_fts fts
            JOIN chunks c ON c.id = fts.rowid
            JOIN documents d ON d.id = c.document_id
            WHERE chunks_fts MATCH ?
            {where_clause}
            ORDER BY fts.rank
            LIMIT ?
        """

        params = [sanitized_query] + where_params + [limit]
        cursor = self.db.execute_sql(sql, params)
        results = []

        for row in cursor.fetchall():
            chunk_id, doc_id, rank = row

            doc_model = DocumentModel.get_by_id(doc_id)
            document = self._model_to_document(doc_model)

            results.append(
                SearchResult(
                    document=document,
                    score=abs(rank),  # rank отрицательный, инвертируем
                    match_type=MatchType.FTS,
                    chunk_id=chunk_id,  # Теперь возвращаем chunk_id
                )
            )

        return results

    def _hybrid_search(
        self,
        query_vector: Optional[np.ndarray],
        query_text: Optional[str],
        filters: Optional[dict],
        limit: int,
        k: int = 1,
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
            k: Константа RRF (default=1 для максимального контраста).

        Returns:
            Список SearchResult, отсортированный по RRF score.
        """
        if query_vector is None and query_text is None:
            logger.warning("Hybrid search called without query_vector or query_text")
            raise ValueError("Нужен хотя бы один параметр: query_vector или query_text")

        logger.trace(
            "Hybrid search (RRF) at chunk level",
            k=k,
            limit=limit,
        )

        # Если только один метод, используем его напрямую
        if query_vector is None:
            return self._fts_search(query_text, filters, limit)
        if query_text is None:
            return self._vector_search(query_vector, filters, limit)

        # Экранируем специальные символы FTS5 для query_text
        sanitized_query = _sanitize_fts_query(query_text)

        # Формируем WHERE условия для фильтров по метаданным документа
        where_conditions = []
        where_params = []
        if filters:
            for key, value in filters.items():
                where_conditions.append(f"json_extract(d.metadata, '$.{key}') = ?")
                where_params.append(value)

        where_clause = (
            f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
        )

        # Подготовка blob для векторного поиска
        blob = query_vector.tobytes()

        # SQL запрос с RRF через CTE — теперь на уровне chunk_id!
        # Это ключевое изменение: оба метода возвращают chunk_id,
        # что позволяет RRF корректно находить пересечения
        sql = f"""
            WITH vector_results AS (
                SELECT 
                    cv.id as chunk_id,
                    ROW_NUMBER() OVER (
                        ORDER BY vec_distance_cosine(cv.embedding, ?)
                    ) as rank
                FROM chunks_vec cv
                JOIN chunks c ON c.id = cv.id
                JOIN documents d ON d.id = c.document_id
                {where_clause}
                LIMIT 100
            ),
            fts_results AS (
                SELECT 
                    fts.rowid as chunk_id,
                    ROW_NUMBER() OVER (ORDER BY fts.rank) as rank
                FROM chunks_fts fts
                JOIN chunks c ON c.id = fts.rowid
                JOIN documents d ON d.id = c.document_id
                WHERE chunks_fts MATCH ?
                {f"AND {' AND '.join(where_conditions)}" if where_conditions else ""}
                LIMIT 100
            ),
            rrf_scores AS (
                SELECT 
                    COALESCE(v.chunk_id, f.chunk_id) as chunk_id,
                    (
                        COALESCE(1.0 / (? + v.rank), 0.0) + 
                        COALESCE(1.0 / (? + f.rank), 0.0)
                    ) as rrf_score
                FROM vector_results v
                FULL OUTER JOIN fts_results f ON v.chunk_id = f.chunk_id
            )
            SELECT chunk_id, rrf_score
            FROM rrf_scores
            ORDER BY rrf_score DESC
            LIMIT ?
        """

        # Собираем параметры: blob, where_params, sanitized_query, where_params, k, k, limit
        params = (
            [blob] + where_params + [sanitized_query] + where_params + [k, k, limit]
        )

        cursor = self.db.execute_sql(sql, params)
        results = []

        for row in cursor.fetchall():
            chunk_id, rrf_score = row

            # Загружаем чанк и документ
            chunk_model = ChunkModel.get_by_id(chunk_id)
            doc_model = DocumentModel.get_by_id(chunk_model.document_id)
            document = self._model_to_document(doc_model)

            results.append(
                SearchResult(
                    document=document,
                    score=rrf_score,
                    match_type=MatchType.HYBRID,
                    chunk_id=chunk_id,  # Теперь возвращаем chunk_id
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
        logger.debug(
            "Deleting document",
            doc_id=document_id,
        )

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
            result = doc_model.delete_instance()

            logger.info(
                "Document deleted",
                doc_id=document_id,
                chunks_deleted=len(chunk_ids),
            )

            return result

    def delete_by_metadata(self, filters: dict) -> int:
        """Удаляет чанки по фильтрам метаданных.

        Args:
            filters: Словарь фильтров по метаданным (например, {"source_id": "123"}).

        Returns:
            Количество удалённых чанков.
        """
        logger.debug(
            "Deleting chunks by metadata",
            filters=filters,
        )

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
            logger.debug("No chunks found for deletion")
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

            logger.info(
                "Chunks deleted by metadata",
                deleted_count=deleted_count,
            )

            return deleted_count

    def search_chunks(
        self,
        query_vector: Optional[np.ndarray] = None,
        query_text: Optional[str] = None,
        filters: Optional[dict] = None,
        limit: int = 10,
        mode: str = "hybrid",
        k: int = 1,
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
            k: Константа для RRF алгоритма (default=1).
            chunk_type_filter: Фильтр по типу чанка.
            language_filter: Фильтр по языку программирования.

        Returns:
            Список ChunkResult.
        """
        start_time = time.perf_counter()
        logger.debug(
            "Chunk search started",
            mode=mode,
            limit=limit,
            chunk_type_filter=chunk_type_filter,
            language_filter=language_filter,
        )

        if mode == "vector":
            results = self._vector_search_chunks(
                query_vector, filters, limit, chunk_type_filter, language_filter
            )
        elif mode == "fts":
            # FTS для чанков пока не реализован, возвращаем пустой список
            logger.debug("FTS chunk search not implemented")
            results = []
        elif mode == "hybrid":
            results = self._hybrid_search_chunks(
                query_vector,
                query_text,
                filters,
                limit,
                k,
                chunk_type_filter,
                language_filter,
            )
        else:
            logger.error("Unknown search mode", mode=mode)
            raise ValueError(f"Неизвестный режим поиска: {mode}")

        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Chunk search completed",
            mode=mode,
            results_count=len(results),
            latency_ms=round(latency_ms, 2),
        )

        return results

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
            # Используем линейную формулу: 1.0 - distance
            score = max(0.0, 1.0 - distance)

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
            logger.warning("Empty vectors_dict provided")
            raise ValueError("Словарь векторов не может быть пустым")

        start_time = time.perf_counter()
        logger.debug(
            "Bulk updating vectors",
            count=len(vectors_dict),
        )

        # Подготавливаем данные для executemany
        data = [(int(chunk_id), blob) for chunk_id, blob in vectors_dict.items()]

        try:
            # Вставляем/обновляем векторы в vec0 таблице (по одному)
            with self.db.atomic():
                for chunk_id, blob in data:
                    self.db.execute_sql(
                        "INSERT OR REPLACE INTO chunks_vec(id, embedding) VALUES (?, ?)",
                        (chunk_id, blob),
                    )

                # Обновляем статус чанков на READY
                chunk_ids = [int(cid) for cid in vectors_dict.keys()]
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
                )

            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "Vectors bulk updated",
                count=len(vectors_dict),
                latency_ms=round(latency_ms, 2),
            )

            return len(vectors_dict)

        except Exception as e:
            self.db.rollback()
            logger.error(
                "Bulk vector update failed",
                error_type=type(e).__name__,
                count=len(vectors_dict),
            )
            raise RuntimeError(f"Ошибка при массовом обновлении векторов: {e}")

    def get_sibling_chunks(
        self,
        chunk_id: int,
        window: int = 1,
    ) -> list[Chunk]:
        """Получает соседние чанки того же документа.

        Args:
            chunk_id: ID центрального чанка.
            window: Количество соседей в каждую сторону.

        Returns:
            Список Chunk, отсортированный по chunk_index.
        """
        try:
            center = ChunkModel.get_by_id(chunk_id)
        except ChunkModel.DoesNotExist:
            logger.warning("Chunk not found for siblings", chunk_id=chunk_id)
            return []

        doc_id = center.document_id
        position = center.chunk_index

        # Получаем общее количество чанков в документе
        total_chunks = self.get_document_chunks_count(doc_id)

        # Если window >= количества чанков, возвращаем все
        if window * 2 + 1 >= total_chunks:
            siblings = (
                ChunkModel.select()
                .where(ChunkModel.document == doc_id)
                .order_by(ChunkModel.chunk_index)
            )
        else:
            # Запрос соседей в диапазоне
            siblings = (
                ChunkModel.select()
                .where(ChunkModel.document == doc_id)
                .where(
                    ChunkModel.chunk_index.between(
                        position - window,
                        position + window,
                    )
                )
                .order_by(ChunkModel.chunk_index)
            )

        return [self._chunk_model_to_chunk(s) for s in siblings]

    def get_document_chunks_count(self, document_id: int) -> int:
        """Возвращает количество чанков в документе.

        Args:
            document_id: ID документа.

        Returns:
            Количество чанков.
        """
        return ChunkModel.select().where(ChunkModel.document == document_id).count()

    def _chunk_model_to_chunk(self, model: ChunkModel) -> Chunk:
        """Конвертирует ChunkModel в Chunk DTO.

        Args:
            model: Модель чанка из БД.

        Returns:
            Chunk DTO.
        """
        # Парсим metadata
        metadata = {}
        if model.metadata:
            try:
                metadata = json.loads(model.metadata)
            except json.JSONDecodeError:
                pass

        return Chunk(
            id=model.id,
            content=model.content,
            chunk_index=model.chunk_index,
            chunk_type=ChunkType(model.chunk_type),
            language=model.language,
            metadata=metadata,
            parent_doc_id=model.document_id,
            created_at=model.created_at,
        )

    def _hybrid_search_chunks(
        self,
        query_vector: Optional[np.ndarray],
        query_text: Optional[str],
        filters: Optional[dict],
        limit: int,
        k: int = 1,
        chunk_type_filter: Optional[str] = None,
        language_filter: Optional[str] = None,
    ) -> list[ChunkResult]:
        """Гибридный поиск чанков (RRF).

        Args:
            query_vector: Вектор запроса.
            query_text: Текст запроса.
            filters: Фильтры по метаданным документа.
            limit: Количество результатов.
            k: Константа RRF.
            chunk_type_filter: Фильтр по типу чанка.
            language_filter: Фильтр по языку программирования.

        Returns:
            Список ChunkResult.
        """
        if query_vector is None and query_text is None:
            return []

        # Если только один метод, используем его напрямую
        if query_vector is None:
            # TODO: Реализовать _fts_search_chunks
            return []
        if query_text is None:
            return self._vector_search_chunks(
                query_vector, filters, limit, chunk_type_filter, language_filter
            )

        # Экранируем специальные символы FTS5 для query_text
        sanitized_query = _sanitize_fts_query(query_text)

        # Формируем WHERE условия для фильтров
        where_conditions = []
        where_params = []
        
        # Фильтры по метаданным документа
        if filters:
            for key, value in filters.items():
                where_conditions.append(f"json_extract(d.metadata, '$.{key}') = ?")
                where_params.append(value)

        # Фильтр по типу чанка
        if chunk_type_filter:
            where_conditions.append("c.chunk_type = ?")
            chunk_type_value = (
                chunk_type_filter.value
                if hasattr(chunk_type_filter, "value")
                else chunk_type_filter
            )
            where_params.append(chunk_type_value)

        # Фильтр по языку
        if language_filter:
            where_conditions.append("c.language = ?")
            where_params.append(language_filter)

        where_clause = (
            f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
        )

        blob = query_vector.tobytes()

        # SQL запрос с RRF через CTE
        sql = f"""
            WITH vector_results AS (
                SELECT 
                    cv.id as chunk_id,
                    ROW_NUMBER() OVER (
                        ORDER BY vec_distance_cosine(cv.embedding, ?)
                    ) as rank
                FROM chunks_vec cv
                JOIN chunks c ON c.id = cv.id
                JOIN documents d ON d.id = c.document_id
                {where_clause}
                LIMIT 100
            ),
            fts_results AS (
                SELECT 
                    fts.rowid as chunk_id,
                    ROW_NUMBER() OVER (ORDER BY fts.rank) as rank
                FROM chunks_fts fts
                JOIN chunks c ON c.id = fts.rowid
                JOIN documents d ON d.id = c.document_id
                WHERE chunks_fts MATCH ?
                {f"AND {' AND '.join(where_conditions)}" if where_conditions else ""}
                LIMIT 100
            ),
            rrf_scores AS (
                SELECT 
                    COALESCE(v.chunk_id, f.chunk_id) as chunk_id,
                    (
                        COALESCE(1.0 / (? + v.rank), 0.0) + 
                        COALESCE(1.0 / (? + f.rank), 0.0)
                    ) as rrf_score
                FROM vector_results v
                FULL OUTER JOIN fts_results f ON v.chunk_id = f.chunk_id
            )
            SELECT 
                r.chunk_id, 
                r.rrf_score,
                c.chunk_index,
                c.content,
                c.chunk_type,
                c.language,
                c.metadata as chunk_metadata,
                c.created_at,
                d.id as doc_id,
                d.metadata as doc_metadata
            FROM rrf_scores r
            JOIN chunks c ON c.id = r.chunk_id
            JOIN documents d ON d.id = c.document_id
            ORDER BY r.rrf_score DESC
            LIMIT ?
        """

        # Параметры: blob, where_params, sanitized_query, where_params, k, k, limit
        params = (
            [blob] + where_params + [sanitized_query] + where_params + [k, k, limit]
        )

        cursor = self.db.execute_sql(sql, params)
        results = []

        for row in cursor.fetchall():
            (
                chunk_id,
                rrf_score,
                chunk_index,
                content,
                chunk_type,
                language,
                chunk_metadata,
                chunk_created_at,
                doc_id,
                doc_metadata,
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

            doc_meta = json.loads(doc_metadata)
            doc_title = doc_meta.get("title")

            results.append(
                ChunkResult(
                    chunk=chunk,
                    score=rrf_score,
                    match_type=MatchType.HYBRID,
                    parent_doc_id=doc_id,
                    parent_doc_title=doc_title,
                    parent_metadata=doc_meta,
                )
            )

        return results
