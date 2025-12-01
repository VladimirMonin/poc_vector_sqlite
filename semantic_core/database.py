"""
Модуль инициализации базы данных с поддержкой sqlite-vec.

Предоставляет расширенное подключение к SQLite с автоматической
загрузкой векторного расширения sqlite-vec.
"""

import sqlite3
from pathlib import Path
from typing import Optional

from peewee import SqliteDatabase
from playhouse.sqlite_ext import SqliteExtDatabase

from config import settings


class VectorDatabase(SqliteExtDatabase):
    """
    Расширенная база данных SQLite с поддержкой векторного поиска.

    Автоматически загружает расширение sqlite-vec при подключении.
    """

    def __init__(self, database: str | Path, *args, **kwargs):
        """
        Инициализация БД с векторным расширением.

        Args:
            database: Путь к файлу базы данных
            *args: Дополнительные аргументы для SqliteExtDatabase
            **kwargs: Дополнительные параметры для SqliteExtDatabase
        """
        super().__init__(database, *args, **kwargs)
        self._vector_extension_loaded = False

    def _add_conn_hooks(self, conn: sqlite3.Connection) -> None:
        """
        Хук, вызываемый при создании нового соединения.

        Загружает расширение sqlite-vec в соединение.

        Args:
            conn: Объект соединения SQLite
        """
        super()._add_conn_hooks(conn)

        if not self._vector_extension_loaded:
            # Загружаем расширение sqlite-vec
            conn.enable_load_extension(True)
            try:
                # sqlite-vec загружается автоматически при импорте пакета
                import sqlite_vec

                sqlite_vec.load(conn)
                self._vector_extension_loaded = True
            except Exception as e:
                raise RuntimeError(f"Не удалось загрузить sqlite-vec: {e}")
            finally:
                conn.enable_load_extension(False)


# Глобальный экземпляр базы данных
db: Optional[VectorDatabase] = None


def init_database(db_path: Optional[Path] = None) -> VectorDatabase:
    """
    Инициализирует глобальное подключение к базе данных.

    Args:
        db_path: Путь к файлу БД (по умолчанию из settings)

    Returns:
        VectorDatabase: Инициализированный экземпляр базы данных

    Examples:
        >>> from semantic_core import init_database
        >>> db = init_database()
        >>> db.connect()
    """
    global db

    if db_path is None:
        db_path = settings.sqlite_db_path

    db = VectorDatabase(
        str(db_path),
        pragmas={
            "journal_mode": "wal",  # Write-Ahead Logging для производительности
            "cache_size": -1024 * 64,  # 64MB cache
            "foreign_keys": 1,  # Включаем FK constraints
            "ignore_check_constraints": 0,
            "synchronous": 0,  # Быстрее, но менее безопасно для crash
        },
    )

    return db


def create_vector_table(model_class, vector_column: str = "embedding") -> None:
    """
    Создает виртуальную таблицу vec0 для векторного индекса.

    Args:
        model_class: Класс модели Peewee
        vector_column: Имя колонки с векторами (по умолчанию "embedding")

    Examples:
        >>> from domain.models import Note
        >>> create_vector_table(Note)
    """
    table_name = model_class._meta.table_name
    vector_table_name = f"{table_name}_vec"

    # Создаем виртуальную таблицу для векторного поиска
    db.execute_sql(f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS {vector_table_name} 
        USING vec0(
            id INTEGER PRIMARY KEY,
            {vector_column} FLOAT[{settings.embedding_dimension}]
        )
    """)


def create_fts_table(model_class, text_columns: list[str]) -> None:
    """
    Создает виртуальную таблицу FTS5 для полнотекстового поиска.

    Args:
        model_class: Класс модели Peewee
        text_columns: Список колонок для индексации

    Examples:
        >>> from domain.models import Note
        >>> create_fts_table(Note, ["title", "content"])
    """
    table_name = model_class._meta.table_name
    fts_table_name = f"{table_name}_fts"

    columns_str = ", ".join(text_columns)

    # Создаем виртуальную таблицу для полнотекстового поиска
    db.execute_sql(f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS {fts_table_name} 
        USING fts5(
            id UNINDEXED,
            {columns_str},
            content={table_name},
            content_rowid=id
        )
    """)

    # Создаем триггеры для автоматического обновления FTS индекса
    db.execute_sql(f"""
        CREATE TRIGGER IF NOT EXISTS {table_name}_fts_insert 
        AFTER INSERT ON {table_name} BEGIN
            INSERT INTO {fts_table_name}(rowid, {columns_str})
            VALUES (new.id, {", ".join(f"new.{col}" for col in text_columns)});
        END
    """)

    db.execute_sql(f"""
        CREATE TRIGGER IF NOT EXISTS {table_name}_fts_delete 
        AFTER DELETE ON {table_name} BEGIN
            DELETE FROM {fts_table_name} WHERE rowid = old.id;
        END
    """)

    db.execute_sql(f"""
        CREATE TRIGGER IF NOT EXISTS {table_name}_fts_update 
        AFTER UPDATE ON {table_name} BEGIN
            UPDATE {fts_table_name} 
            SET {", ".join(f"{col} = new.{col}" for col in text_columns)}
            WHERE rowid = new.id;
        END
    """)
