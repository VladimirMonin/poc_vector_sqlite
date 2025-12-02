"""Внутренние ORM модели для Peewee (скрыты от внешнего API).

Классы:
    BaseModel
        Базовая модель с общими настройками.
    DocumentModel
        Модель родительского документа.
    ChunkModel
        Модель чанка с привязкой к документу.
    BatchJob
        Модель задания для батч-обработки.
    BatchStatus
        Статусы батч-задания.
    EmbeddingStatus
        Статусы векторизации чанка.
"""

from datetime import datetime
from enum import Enum

from peewee import (
    Model,
    AutoField,
    TextField,
    ForeignKeyField,
    DateTimeField,
    IntegerField,
)


class BatchStatus(str, Enum):
    """Статусы батч-задания в жизненном цикле обработки.
    
    Attributes:
        CREATED: Задание создано, но еще не отправлено в Google.
        SUBMITTED: JSONL файл загружен, задание отправлено.
        PROCESSING: Google обрабатывает батч.
        COMPLETED: Обработка завершена, результаты доступны.
        FAILED: Критическая ошибка в обработке.
    """
    
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class EmbeddingStatus(str, Enum):
    """Статусы векторизации чанка.
    
    Attributes:
        READY: Вектор готов и сохранён в vec0.
        PENDING: Чанк в очереди на векторизацию.
        FAILED: Ошибка при получении вектора.
    """
    
    READY = "READY"
    PENDING = "PENDING"
    FAILED = "FAILED"


class BaseModel(Model):
    """Базовая модель (без привязки к конкретной БД).

    База данных устанавливается в адаптере через _meta.database.
    """

    class Meta:
        database = None  # Будет установлена в адаптере


class DocumentModel(BaseModel):
    """Внутренняя ORM модель документа (родитель).

    Хранит полный текст и метаданные для FTS и отображения.

    Attributes:
        id: Автоинкремент ID.
        content: Полный текст документа.
        metadata: JSON строка с метаданными.
        media_type: Тип медиа (text, image, video).
        created_at: Дата создания.
    """

    id = AutoField(primary_key=True)
    content = TextField()
    metadata = TextField()  # JSON строка
    media_type = TextField(default="text")
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "documents"


class BatchJobModel(BaseModel):
    """Внутренняя ORM модель задания для батч-обработки.
    
    Хранит состояние батч-задания в Google Cloud и статистику.
    
    Attributes:
        id: UUID первичный ключ.
        google_job_id: Идентификатор задания в Google (например, batches/123...).
        status: Текущий статус задания (CREATED/SUBMITTED/PROCESSING/COMPLETED/FAILED).
        stats: JSON строка с метриками (submitted/succeeded/failed).
        created_at: Время создания задания.
        updated_at: Время последнего обновления статуса.
    """
    
    id = TextField(primary_key=True)  # UUID
    google_job_id = TextField(null=True, unique=True)
    status = TextField(default=BatchStatus.CREATED.value)
    stats = TextField(default="{}")  # JSON строка
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)
    
    class Meta:
        table_name = "batch_jobs"


class ChunkModel(BaseModel):
    """Внутренняя ORM модель чанка (ребёнок).

    Хранит фрагменты текста для векторного поиска.
    Векторы хранятся в отдельной виртуальной таблице vec0.

    Attributes:
        id: Автоинкремент ID.
        document: Ссылка на родительский документ.
        chunk_index: Порядковый номер чанка.
        content: Текст фрагмента.
        chunk_type: Тип контента (text/code/table/image_ref).
        language: Язык программирования для блоков кода.
        metadata: JSON строка с метаданными чанка.
        embedding_status: Статус векторизации (READY/PENDING/FAILED).
        batch_job: Ссылка на батч-задание (nullable).
        error_message: Сообщение об ошибке векторизации (nullable).
        created_at: Дата создания.
    """

    id = AutoField(primary_key=True)
    document = ForeignKeyField(
        DocumentModel,
        backref="chunks",
        on_delete="CASCADE",
        index=True,
    )
    chunk_index = IntegerField()
    content = TextField()
    chunk_type = TextField(default="text")  # text, code, table, image_ref
    language = TextField(null=True)  # Python, JavaScript и т.д.
    metadata = TextField()  # JSON строка
    
    # Новые поля для батчинга (Phase 5)
    embedding_status = TextField(default=EmbeddingStatus.READY.value)
    batch_job = ForeignKeyField(
        BatchJobModel,
        backref="chunks",
        on_delete="SET NULL",
        null=True,
        index=True,
    )
    error_message = TextField(null=True)
    
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "chunks"
        indexes = (
            (("document", "chunk_index"), True),  # Уникальная пара
            (("chunk_type",), False),  # Индекс для фильтрации по типу
            (("embedding_status",), False),  # Индекс для поиска PENDING чанков
        )
