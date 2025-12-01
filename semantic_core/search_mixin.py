"""
Миксин для добавления гибридного поиска в Peewee модели.

Предоставляет методы векторного, полнотекстового и гибридного поиска
с использованием Reciprocal Rank Fusion (RRF).
"""

from typing import Any, ClassVar

import numpy as np
from peewee import Model

from semantic_core.database import db
from semantic_core.embeddings import EmbeddingGenerator


class HybridSearchMixin:
    """
    Миксин для добавления возможностей семантического поиска в Peewee модели.
    
    Добавляет методы:
    - vector_search() - чисто векторный поиск
    - fulltext_search() - чисто FTS5 поиск  
    - hybrid_search() - гибридный поиск с RRF
    - update_vector_index() - обновление векторного индекса
    
    Требования к модели:
    - Должна наследоваться от peewee.Model
    - Должна определить метод get_search_text() -> str
    
    Examples:
        >>> class Note(HybridSearchMixin, Model):
        ...     content = TextField()
        ...     
        ...     def get_search_text(self):
        ...         return self.content
        ...
        >>> results = Note.hybrid_search("python циклы", limit=10)
    """
    
    # Метаданные для поиска (переопределяются в конкретных моделях)
    _vector_column: ClassVar[str] = "embedding"
    _fts_columns: ClassVar[list[str]] = ["content"]
    
    def get_search_text(self) -> str:
        """
        АБСТРАКТНЫЙ МЕТОД: Возвращает текст для индексации.
        
        Должен быть переопределен в конкретной модели.
        
        Returns:
            str: Текст, который будет векторизован и проиндексирован
        
        Raises:
            NotImplementedError: Если метод не переопределен
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} должен реализовать метод get_search_text()"
        )
    
    def update_vector_index(self, generator: EmbeddingGenerator | None = None) -> None:
        """
        Обновляет векторный индекс для текущего экземпляра.
        
        Args:
            generator: Генератор эмбеддингов (создается автоматически, если не передан)
        
        Examples:
            >>> note = Note.create(content="Пример заметки")
            >>> note.update_vector_index()
        """
        if generator is None:
            generator = EmbeddingGenerator()
        
        # Получаем текст для индексации
        text = self.get_search_text()
        
        # Генерируем эмбеддинг
        embedding = generator.embed_document(text)
        blob = generator.vector_to_blob(embedding)
        
        # Обновляем векторную таблицу
        table_name = self._meta.table_name
        vector_table = f"{table_name}_vec"
        
        db.execute_sql(f"""
            INSERT OR REPLACE INTO {vector_table} (id, {self._vector_column})
            VALUES (?, ?)
        """, (self.id, blob))
    
    @classmethod
    def vector_search(
        cls,
        query: str,
        limit: int = 10,
        generator: EmbeddingGenerator | None = None
    ) -> list[Any]:
        """
        Выполняет чисто векторный поиск (семантический).
        
        Args:
            query: Текст поискового запроса
            limit: Максимальное количество результатов
            generator: Генератор эмбеддингов
        
        Returns:
            list: Список объектов модели, отсортированных по релевантности
        
        Examples:
            >>> results = Note.vector_search("как написать цикл", limit=5)
        """
        if generator is None:
            generator = EmbeddingGenerator()
        
        # Генерируем эмбеддинг запроса
        query_embedding = generator.embed_query(query)
        query_blob = generator.vector_to_blob(query_embedding)
        
        table_name = cls._meta.table_name
        vector_table = f"{table_name}_vec"
        
        # Выполняем векторный поиск
        sql = f"""
            SELECT 
                main.id,
                vec_distance_cosine(vec.{cls._vector_column}, ?) as distance
            FROM {table_name} main
            INNER JOIN {vector_table} vec ON main.id = vec.id
            ORDER BY distance ASC
            LIMIT ?
        """
        
        cursor = db.execute_sql(sql, (query_blob, limit))
        ids = [row[0] for row in cursor.fetchall()]
        
        # Возвращаем объекты в порядке релевантности
        id_to_obj = {obj.id: obj for obj in cls.select().where(cls.id.in_(ids))}
        return [id_to_obj[id_] for id_ in ids if id_ in id_to_obj]
    
    @classmethod
    def fulltext_search(
        cls,
        query: str,
        limit: int = 10
    ) -> list[Any]:
        """
        Выполняет полнотекстовый поиск через FTS5.
        
        Args:
            query: Текст запроса (поддерживает FTS5 синтаксис)
            limit: Максимальное количество результатов
        
        Returns:
            list: Список объектов модели, отсортированных по BM25
        
        Examples:
            >>> results = Note.fulltext_search("python AND цикл", limit=5)
        """
        table_name = cls._meta.table_name
        fts_table = f"{table_name}_fts"
        
        sql = f"""
            SELECT 
                main.id,
                fts.rank as rank
            FROM {table_name} main
            INNER JOIN {fts_table} fts ON main.id = fts.rowid
            WHERE {fts_table} MATCH ?
            ORDER BY rank
            LIMIT ?
        """
        
        cursor = db.execute_sql(sql, (query, limit))
        ids = [row[0] for row in cursor.fetchall()]
        
        # Возвращаем объекты в порядке релевантности
        id_to_obj = {obj.id: obj for obj in cls.select().where(cls.id.in_(ids))}
        return [id_to_obj[id_] for id_ in ids if id_ in id_to_obj]
    
    @classmethod
    def hybrid_search(
        cls,
        query: str,
        limit: int = 10,
        k: int = 60,
        generator: EmbeddingGenerator | None = None,
        **filters
    ) -> list[Any]:
        """
        Выполняет гибридный поиск с использованием RRF.
        
        Объединяет результаты векторного и полнотекстового поиска
        с помощью Reciprocal Rank Fusion для максимальной точности.
        
        Args:
            query: Текст запроса
            limit: Максимальное количество результатов
            k: Параметр RRF (обычно 60)
            generator: Генератор эмбеддингов
            **filters: Дополнительные фильтры (например, category_id=5)
        
        Returns:
            list: Список объектов модели, отсортированных по RRFScore
        
        Examples:
            >>> # Гибридный поиск с фильтром по категории
            >>> results = Note.hybrid_search(
            ...     "python циклы",
            ...     limit=10,
            ...     category_id=5
            ... )
        """
        if generator is None:
            generator = EmbeddingGenerator()
        
        # Генерируем эмбеддинг запроса
        query_embedding = generator.embed_query(query)
        query_blob = generator.vector_to_blob(query_embedding)
        
        table_name = cls._meta.table_name
        vector_table = f"{table_name}_vec"
        fts_table = f"{table_name}_fts"
        
        # Строим WHERE clause для фильтров
        where_conditions = []
        where_params = []
        for field, value in filters.items():
            where_conditions.append(f"main.{field} = ?")
            where_params.append(value)
        
        where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
        
        # Гибридный поиск с RRF через CTE
        sql = f"""
            WITH vector_results AS (
                SELECT 
                    main.id,
                    ROW_NUMBER() OVER (ORDER BY vec_distance_cosine(vec.{cls._vector_column}, ?)) as rank
                FROM {table_name} main
                INNER JOIN {vector_table} vec ON main.id = vec.id
                {where_clause}
                LIMIT 100
            ),
            fts_results AS (
                SELECT 
                    main.id,
                    ROW_NUMBER() OVER (ORDER BY fts.rank) as rank
                FROM {table_name} main
                INNER JOIN {fts_table} fts ON main.id = fts.rowid
                WHERE {fts_table} MATCH ?
                {f"AND {' AND '.join(where_conditions)}" if where_conditions else ""}
                LIMIT 100
            ),
            rrf_scores AS (
                SELECT 
                    COALESCE(v.id, f.id) as id,
                    (COALESCE(1.0 / (? + v.rank), 0) + COALESCE(1.0 / (? + f.rank), 0)) as rrf_score
                FROM vector_results v
                FULL OUTER JOIN fts_results f ON v.id = f.id
            )
            SELECT id, rrf_score
            FROM rrf_scores
            ORDER BY rrf_score DESC
            LIMIT ?
        """
        
        params = [query_blob] + where_params + [query] + where_params + [k, k, limit]
        
        cursor = db.execute_sql(sql, params)
        ids = [row[0] for row in cursor.fetchall()]
        
        # Возвращаем объекты в порядке RRF
        id_to_obj = {obj.id: obj for obj in cls.select().where(cls.id.in_(ids))}
        return [id_to_obj[id_] for id_ in ids if id_ in id_to_obj]
