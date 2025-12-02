"""Инициализация SQLite БД с расширениями vec0 и fts5.

Функции:
    init_peewee_database
        Создаёт и настраивает БД с векторным поиском.
"""

import sqlite3
from pathlib import Path

from playhouse.sqlite_ext import SqliteExtDatabase


class VectorDatabase(SqliteExtDatabase):
    """Расширенная БД SQLite с поддержкой sqlite-vec.

    Автоматически загружает расширение при подключении.
    """

    def __init__(self, database: str | Path, *args, **kwargs):
        """Инициализация БД.

        Args:
            database: Путь к файлу БД.
        """
        super().__init__(database, *args, **kwargs)
        self._vector_extension_loaded = False

    def _add_conn_hooks(self, conn: sqlite3.Connection) -> None:
        """Хук загрузки расширения sqlite-vec.

        Args:
            conn: Объект соединения SQLite.
        """
        super()._add_conn_hooks(conn)

        if not self._vector_extension_loaded:
            conn.enable_load_extension(True)
            try:
                import sqlite_vec

                sqlite_vec.load(conn)
                self._vector_extension_loaded = True
            except Exception as e:
                raise RuntimeError(f"Не удалось загрузить sqlite-vec: {e}")
            finally:
                conn.enable_load_extension(False)


def init_peewee_database(
    db_path: str | Path,
    dimension: int = 768,
) -> VectorDatabase:
    """Инициализирует SQLite БД с расширениями.

    Args:
        db_path: Путь к файлу БД.
        dimension: Размерность векторов (для vec0 таблицы).

    Returns:
        Настроенный экземпляр VectorDatabase.
    """
    database = VectorDatabase(
        str(db_path),
        pragmas={
            "journal_mode": "wal",
            "cache_size": -1024 * 64,  # 64MB
            "foreign_keys": 1,
            "ignore_check_constraints": 0,
            "synchronous": 0,
        },
    )

    # Подключаемся для загрузки расширения
    database.connect()

    return database
