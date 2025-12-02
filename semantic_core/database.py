"""
Модуль инициализации базы данных с поддержкой sqlite-vec.

Предоставляет расширенное подключение к SQLite с автоматической
загрузкой векторного расширения sqlite-vec.

Parent-Child архитектура:
- Note (parent): FTS5 для полнотекстового поиска
- NoteChunk (child): vec0 для векторного поиска

Функции:
    init_database: Инициализация базы данных с векторным расширением.
    create_vector_table: Создание виртуальной таблицы vec0.
    create_fts_table: Создание виртуальной таблицы FTS5.
    ensure_schema_compatibility: Автоматическая миграция схемы для новых полей.
"""

import sqlite3
from pathlib import Path
from typing import Optional

from peewee import DatabaseProxy
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


# Глобальный прокси для отложенной инициализации БД
db = DatabaseProxy()


def init_database(db_path: Optional[Path] = None) -> VectorDatabase:
    """
    Инициализирует глобальное подключение к базе данных.

    Args:
        db_path: Путь к файлу БД (по умолчанию из settings)

    Returns:
        VectorDatabase: Инициализированный экземпляр базы данных

    Examples:
        >>> from semantic_core import init_database
        >>> database = init_database()
        >>> database.connect()
    """
    if db_path is None:
        db_path = settings.sqlite_db_path

    database = VectorDatabase(
        str(db_path),
        pragmas={
            "journal_mode": "wal",  # Write-Ahead Logging для производительности
            "cache_size": -1024 * 64,  # 64MB cache
            "foreign_keys": 1,  # Включаем FK constraints
            "ignore_check_constraints": 0,
            "synchronous": 0,  # Быстрее, но менее безопасно для crash
        },
    )

    # Инициализируем прокси реальной базой данных
    db.initialize(database)

    return database


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
    db.obj.execute_sql(f"""
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
    db.obj.execute_sql(f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS {fts_table_name} 
        USING fts5(
            id UNINDEXED,
            {columns_str},
            content={table_name},
            content_rowid=id
        )
    """)

    # Создаем триггеры для автоматического обновления FTS индекса
    db.obj.execute_sql(f"""
        CREATE TRIGGER IF NOT EXISTS {table_name}_fts_insert 
        AFTER INSERT ON {table_name} BEGIN
            INSERT INTO {fts_table_name}(rowid, {columns_str})
            VALUES (new.id, {", ".join(f"new.{col}" for col in text_columns)});
        END
    """)

    db.obj.execute_sql(f"""
        CREATE TRIGGER IF NOT EXISTS {table_name}_fts_delete 
        AFTER DELETE ON {table_name} BEGIN
            DELETE FROM {fts_table_name} WHERE rowid = old.id;
        END
    """)

    db.obj.execute_sql(f"""
        CREATE TRIGGER IF NOT EXISTS {table_name}_fts_update 
        AFTER UPDATE ON {table_name} BEGIN
            UPDATE {fts_table_name} 
            SET {", ".join(f"{col} = new.{col}" for col in text_columns)}
            WHERE rowid = new.id;
        END
    """)


def ensure_schema_compatibility(database: VectorDatabase) -> None:
    """Автоматическая миграция схемы для обратной совместимости.
    
    Проверяет наличие новых колонок (добавленных в Phase 5) и создаёт их,
    если база данных была создана на более старой версии библиотеки.
    
    Миграции:
        - batch_jobs: Таблица для батч-заданий (Phase 5)
        - chunks.embedding_status: Статус векторизации (Phase 5)
        - chunks.batch_job_id: Связь с батч-заданием (Phase 5)
        - chunks.error_message: Сообщение об ошибке (Phase 5)
    
    Args:
        database: Инициализированная база данных VectorDatabase.
    
    Examples:
        >>> database = init_database()
        >>> database.connect()
        >>> ensure_schema_compatibility(database)
    """
    conn = database.connection()
    cursor = conn.cursor()
    
    # === Миграция 1: Создание таблицы batch_jobs ===
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='batch_jobs'
    """)
    if not cursor.fetchone():
        cursor.execute("""
            CREATE TABLE batch_jobs (
                id TEXT PRIMARY KEY,
                google_job_id TEXT UNIQUE,
                status TEXT DEFAULT 'CREATED',
                stats TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("[Migration] Created table 'batch_jobs'")
    
    # === Миграция 2: Добавление новых колонок в chunks ===
    cursor.execute("PRAGMA table_info(chunks)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    
    migrations_applied = False
    
    if "embedding_status" not in existing_columns:
        cursor.execute("""
            ALTER TABLE chunks 
            ADD COLUMN embedding_status TEXT DEFAULT 'READY'
        """)
        print("[Migration] Added column 'chunks.embedding_status'")
        migrations_applied = True
    
    if "batch_job_id" not in existing_columns:
        cursor.execute("""
            ALTER TABLE chunks 
            ADD COLUMN batch_job_id TEXT
        """)
        # Создаем индекс для FK
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS chunks_batch_job_id 
            ON chunks(batch_job_id)
        """)
        print("[Migration] Added column 'chunks.batch_job_id' with index")
        migrations_applied = True
    
    if "error_message" not in existing_columns:
        cursor.execute("""
            ALTER TABLE chunks 
            ADD COLUMN error_message TEXT
        """)
        print("[Migration] Added column 'chunks.error_message'")
        migrations_applied = True
    
    # Добавляем индекс для embedding_status, если его нет
    if "embedding_status" in existing_columns:
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='chunks_embedding_status'
        """)
        if not cursor.fetchone():
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS chunks_embedding_status 
                ON chunks(embedding_status)
            """)
            print("[Migration] Created index on 'chunks.embedding_status'")
            migrations_applied = True
    
    conn.commit()
    
    if not migrations_applied:
        print("[Migration] Schema is up-to-date, no migrations needed")
