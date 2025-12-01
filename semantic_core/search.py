"""
Функции поиска для Parent-Child архитектуры.

Поиск ведется по дочерним чанкам (NoteChunk), но возвращаются
уникальные родительские документы (Note) с агрегированными скорами.
"""

from typing import Any, Optional, List, Tuple

from peewee import Model

from semantic_core.database import db
from semantic_core.embeddings import EmbeddingGenerator


def vector_search_chunks(
    parent_model: Model,
    chunk_model: Model,
    query: str,
    limit: int = 10,
    generator: Optional[EmbeddingGenerator] = None,
    **filters,
) -> List[Tuple[Any, float]]:
    """
    Векторный поиск по чанкам с возвратом уникальных родителей.

    Алгоритм:
    1. Генерирует эмбеддинг запроса
    2. Ищет топ-N чанков по косинусному расстоянию
    3. Группирует по note_id
    4. Для каждой заметки берет MIN(distance) - самый похожий чанк
    5. Возвращает уникальные Note, отсортированные по лучшему расстоянию

    Args:
        parent_model: Класс модели Note (родитель)
        chunk_model: Класс модели NoteChunk (ребенок)
        query: Текст поискового запроса
        limit: Максимальное количество результатов (уникальных заметок)
        generator: Генератор эмбеддингов (создается автоматически)
        **filters: Фильтры для родительской модели (например, category_id=5)

    Returns:
        List[Tuple[Note, float]]: Список кортежей (заметка, distance)

    Example:
        >>> from domain.models import Note, NoteChunk
        >>> results = vector_search_chunks(
        ...     parent_model=Note,
        ...     chunk_model=NoteChunk,
        ...     query="как написать цикл?",
        ...     limit=5
        ... )
        >>> for note, distance in results:
        ...     print(f"{note.title}: {distance:.4f}")
    """
    if generator is None:
        generator = EmbeddingGenerator()

    # Генерируем эмбеддинг запроса
    query_embedding = generator.embed_query(query)
    query_blob = generator.vector_to_blob(query_embedding)

    chunk_table = chunk_model._meta.table_name
    parent_table = parent_model._meta.table_name
    vector_table = f"{chunk_table}_vec"

    # Строим WHERE clause для фильтров родителя
    where_conditions = []
    where_params = []
    for field, value in filters.items():
        where_conditions.append(f"parent.{field} = ?")
        where_params.append(value)

    where_clause = f"AND {' AND '.join(where_conditions)}" if where_conditions else ""

    # SQL: Ищем чанки → группируем по note_id → берем MIN(distance)
    sql = f"""
        SELECT 
            chunk.note_id,
            MIN(vec_distance_cosine(vec.embedding, ?)) as best_distance
        FROM {chunk_table} chunk
        INNER JOIN {vector_table} vec ON chunk.id = vec.id
        INNER JOIN {parent_table} parent ON chunk.note_id = parent.id
        WHERE vec.embedding MATCH ?
          AND vec.k = ?
          {where_clause}
        GROUP BY chunk.note_id
        ORDER BY best_distance ASC
        LIMIT ?
    """

    # Параметры: query_blob (для distance), query_blob (для MATCH), k, [filters], limit
    # MATCH с k - это предфильтр: сначала найти топ-(limit*10) чанков
    params = [query_blob, query_blob, limit * 10] + where_params + [limit]

    cursor = db.obj.execute_sql(sql, params)
    results = cursor.fetchall()  # [(note_id, distance), ...]

    if not results:
        return []

    # Получаем объекты Note в правильном порядке
    note_ids = [row[0] for row in results]
    id_to_distance = {row[0]: row[1] for row in results}

    # Загружаем заметки
    notes = {
        note.id: note
        for note in parent_model.select().where(parent_model.id.in_(note_ids))
    }

    # Возвращаем в порядке релевантности
    return [
        (notes[note_id], id_to_distance[note_id])
        for note_id in note_ids
        if note_id in notes
    ]


def fulltext_search_parents(
    parent_model: Model,
    query: str,
    limit: int = 10,
    **filters,
) -> List[Tuple[Any, float]]:
    """
    Полнотекстовый поиск по родительским документам (Note).

    FTS5 индекс строится на полном тексте заметки (title + content),
    а не на чанках. Это позволяет находить точные совпадения слов.

    Args:
        parent_model: Класс модели Note
        query: Текст запроса (поддерживает FTS5 синтаксис)
        limit: Максимальное количество результатов
        **filters: Фильтры (например, category_id=5)

    Returns:
        List[Tuple[Note, float]]: Список кортежей (заметка, bm25_rank)

    Example:
        >>> results = fulltext_search_parents(
        ...     parent_model=Note,
        ...     query="python AND цикл",
        ...     limit=5
        ... )
    """
    parent_table = parent_model._meta.table_name
    fts_table = f"{parent_table}_fts"

    # Строим WHERE clause для фильтров
    where_conditions = []
    where_params = []
    for field, value in filters.items():
        where_conditions.append(f"parent.{field} = ?")
        where_params.append(value)

    where_clause = f"AND {' AND '.join(where_conditions)}" if where_conditions else ""

    sql = f"""
        SELECT 
            parent.id,
            fts.rank as bm25_rank
        FROM {parent_table} parent
        INNER JOIN {fts_table} fts ON parent.id = fts.rowid
        WHERE {fts_table} MATCH ?
          {where_clause}
        ORDER BY bm25_rank
        LIMIT ?
    """

    params = [query] + where_params + [limit]

    cursor = db.obj.execute_sql(sql, params)
    results = cursor.fetchall()

    if not results:
        return []

    note_ids = [row[0] for row in results]
    id_to_rank = {row[0]: row[1] for row in results}

    notes = {
        note.id: note
        for note in parent_model.select().where(parent_model.id.in_(note_ids))
    }

    return [
        (notes[note_id], id_to_rank[note_id])
        for note_id in note_ids
        if note_id in notes
    ]


def hybrid_search_rrf(
    parent_model: Model,
    chunk_model: Model,
    query: str,
    limit: int = 10,
    k: int = 60,
    generator: Optional[EmbeddingGenerator] = None,
    **filters,
) -> List[Tuple[Any, float]]:
    """
    Гибридный поиск с Reciprocal Rank Fusion (RRF).

    Объединяет:
    1. Векторный поиск по чанкам (семантическое понимание)
    2. Полнотекстовый поиск по родителям (точные совпадения)

    Формула RRF:
        score = 1/(k + rank_vector) + 1/(k + rank_fts)

    где k=60 (константа из статьи Cormack et al., 2009)

    Args:
        parent_model: Класс модели Note
        chunk_model: Класс модели NoteChunk
        query: Текст запроса
        limit: Максимальное количество результатов
        k: Параметр RRF (по умолчанию 60)
        generator: Генератор эмбеддингов
        **filters: Фильтры для родительской модели

    Returns:
        List[Tuple[Note, float]]: Список кортежей (заметка, rrf_score)

    Example:
        >>> results = hybrid_search_rrf(
        ...     parent_model=Note,
        ...     chunk_model=NoteChunk,
        ...     query="срочный скрипт",
        ...     limit=10,
        ...     category_id=1
        ... )
    """
    if generator is None:
        generator = EmbeddingGenerator()

    # Генерируем эмбеддинг запроса
    query_embedding = generator.embed_query(query)
    query_blob = generator.vector_to_blob(query_embedding)

    chunk_table = chunk_model._meta.table_name
    parent_table = parent_model._meta.table_name
    vector_table = f"{chunk_table}_vec"
    fts_table = f"{parent_table}_fts"

    # Строим WHERE clause для фильтров
    where_conditions = []
    where_params = []
    for field, value in filters.items():
        where_conditions.append(f"parent.{field} = ?")
        where_params.append(value)

    where_clause_vector = (
        f"AND {' AND '.join(where_conditions)}" if where_conditions else ""
    )
    where_clause_fts = (
        f"AND {' AND '.join(where_conditions)}" if where_conditions else ""
    )

    # Гибридный поиск через CTE
    sql = f"""
        WITH vector_results AS (
            SELECT 
                chunk.note_id,
                MIN(vec_distance_cosine(vec.embedding, ?)) as best_distance,
                ROW_NUMBER() OVER (ORDER BY MIN(vec_distance_cosine(vec.embedding, ?))) as rank
            FROM {chunk_table} chunk
            INNER JOIN {vector_table} vec ON chunk.id = vec.id
            INNER JOIN {parent_table} parent ON chunk.note_id = parent.id
            WHERE vec.embedding MATCH ?
              AND vec.k = ?
              {where_clause_vector}
            GROUP BY chunk.note_id
            ORDER BY best_distance ASC
            LIMIT 100
        ),
        fts_results AS (
            SELECT 
                parent.id as note_id,
                fts.rank as bm25_rank,
                ROW_NUMBER() OVER (ORDER BY fts.rank) as rank
            FROM {parent_table} parent
            INNER JOIN {fts_table} fts ON parent.id = fts.rowid
            WHERE {fts_table} MATCH ?
              {where_clause_fts}
            ORDER BY bm25_rank
            LIMIT 100
        ),
        rrf_scores AS (
            SELECT 
                COALESCE(v.note_id, f.note_id) as note_id,
                (
                    COALESCE(1.0 / (? + v.rank), 0) + 
                    COALESCE(1.0 / (? + f.rank), 0)
                ) as rrf_score
            FROM vector_results v
            FULL OUTER JOIN fts_results f ON v.note_id = f.note_id
        )
        SELECT note_id, rrf_score
        FROM rrf_scores
        ORDER BY rrf_score DESC
        LIMIT ?
    """

    # Параметры:
    # - vector: query_blob (distance), query_blob (distance в ROW_NUMBER), query_blob (MATCH), k, filters
    # - fts: query, filters
    # - rrf: k, k, limit
    params = (
        [query_blob, query_blob, query_blob, limit * 10]
        + where_params
        + [query]
        + where_params
        + [k, k, limit]
    )

    cursor = db.obj.execute_sql(sql, params)
    results = cursor.fetchall()

    if not results:
        return []

    note_ids = [row[0] for row in results]
    id_to_score = {row[0]: row[1] for row in results}

    notes = {
        note.id: note
        for note in parent_model.select().where(parent_model.id.in_(note_ids))
    }

    return [
        (notes[note_id], id_to_score[note_id])
        for note_id in note_ids
        if note_id in notes
    ]
