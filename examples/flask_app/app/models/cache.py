"""Модель кэша поисковых запросов.

Локальная таблица Flask app для кэширования эмбеддингов запросов.
Экономит API-вызовы и обеспечивает автокомплит популярных запросов.

Classes:
    SearchQueryModel: Peewee модель для кэширования query → embedding.
"""

import hashlib
from datetime import datetime

from peewee import (
    Model,
    AutoField,
    TextField,
    BlobField,
    IntegerField,
    DateTimeField,
    CharField,
)


class SearchQueryModel(Model):
    """Кэш поисковых запросов.

    Хранит эмбеддинги запросов для:
    - Экономии API-вызовов (повторные запросы бесплатны)
    - Автокомплита популярных запросов
    - Аналитики частотности поиска

    Attributes:
        id: Первичный ключ.
        query_hash: SHA256 хэш нормализованного запроса (индекс).
        query_text: Оригинальный текст запроса.
        embedding: Бинарный blob эмбеддинга (768 * 4 bytes).
        frequency: Счётчик использований запроса.
        created_at: Время первого запроса.
        last_used_at: Время последнего использования.
    """

    id = AutoField()
    query_hash = CharField(max_length=64, unique=True, index=True)
    query_text = TextField()
    embedding = BlobField()
    frequency = IntegerField(default=1)
    created_at = DateTimeField(default=datetime.now)
    last_used_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "search_query_cache"
        database = None  # Устанавливается при инициализации

    @staticmethod
    def compute_hash(query: str) -> str:
        """Вычислить хэш нормализованного запроса.

        Нормализация: lowercase + strip.

        Args:
            query: Текст запроса.

        Returns:
            SHA256 хэш строки.
        """
        normalized = query.lower().strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def increment_frequency(self) -> None:
        """Увеличить счётчик использований и обновить last_used_at."""
        self.frequency += 1
        self.last_used_at = datetime.now()
        self.save()
