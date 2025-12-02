"""Внутренние ORM модели для Peewee (скрыты от внешнего API).

Классы:
    BaseModel
        Базовая модель с общими настройками.
    DocumentModel
        Модель родительского документа.
    ChunkModel
        Модель чанка с привязкой к документу.
"""

from datetime import datetime

from peewee import (
    Model,
    AutoField,
    TextField,
    ForeignKeyField,
    DateTimeField,
    IntegerField,
)


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


class ChunkModel(BaseModel):
    """Внутренняя ORM модель чанка (ребёнок).
    
    Хранит фрагменты текста для векторного поиска.
    Векторы хранятся в отдельной виртуальной таблице vec0.
    
    Attributes:
        id: Автоинкремент ID.
        document: Ссылка на родительский документ.
        chunk_index: Порядковый номер чанка.
        content: Текст фрагмента.
        metadata: JSON строка с метаданными чанка.
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
    metadata = TextField()  # JSON строка
    created_at = DateTimeField(default=datetime.now)
    
    class Meta:
        table_name = "chunks"
        indexes = (
            (("document", "chunk_index"), True),  # Уникальная пара
        )
