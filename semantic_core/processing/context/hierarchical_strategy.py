"""Иерархическая стратегия формирования контекста.

Классы:
    HierarchicalContextStrategy
        Формирует обогащенный контекст с учетом структуры документа.
"""

from semantic_core.domain import Chunk, ChunkType, Document
from semantic_core.interfaces.context import BaseContextStrategy


class HierarchicalContextStrategy(BaseContextStrategy):
    """Стратегия формирования контекста с учетом иерархии.
    
    Создает обогащенный промпт для эмбеддинга, включающий:
    - Название документа
    - Иерархию заголовков (breadcrumbs)
    - Тип контента и язык (для кода)
    - Сам контент
    
    Это помогает векторной модели понять контекст чанка
    без необходимости читать весь документ.
    
    Примеры сформированного текста:
    
    Для TEXT:
        Document: API Documentation
        Section: Database > Models > User Model
        Content: The User model represents...
    
    Для CODE:
        Document: API Documentation
        Context: Database > Models > User Model
        Type: Python Code
        Code:
        class User(BaseModel):
            ...
    """
    
    def __init__(self, include_doc_title: bool = True):
        """Инициализирует стратегию.
        
        Args:
            include_doc_title: Включать ли название документа в контекст.
        """
        self.include_doc_title = include_doc_title
    
    def form_vector_text(self, chunk: Chunk, document: Document) -> str:
        """Формирует обогащенный текст для эмбеддинга.
        
        Args:
            chunk: Чанк для обогащения контекстом.
            document: Родительский документ.
            
        Returns:
            Структурированный промпт для эмбеддинга.
        """
        parts: list[str] = []
        
        # Добавляем название документа
        if self.include_doc_title and document.title:
            parts.append(f"Document: {document.title}")
        
        # Извлекаем иерархию заголовков из метаданных
        headers = chunk.metadata.get("headers", [])
        
        # Формируем контекст в зависимости от типа чанка
        if chunk.chunk_type == ChunkType.CODE:
            # Для кода используем специальный формат
            if headers:
                breadcrumbs = " > ".join(headers)
                parts.append(f"Context: {breadcrumbs}")
            
            # Указываем тип контента
            if chunk.language:
                parts.append(f"Type: {chunk.language.title()} Code")
            else:
                parts.append("Type: Code")
            
            # Добавляем сам код
            parts.append("Code:")
            parts.append(chunk.content)
        
        elif chunk.chunk_type == ChunkType.IMAGE_REF:
            # Для изображений добавляем контекст и метаданные
            if headers:
                breadcrumbs = " > ".join(headers)
                parts.append(f"Section: {breadcrumbs}")
            
            parts.append("Type: Image Reference")
            
            # Добавляем alt-текст и title если есть
            alt_text = chunk.metadata.get("alt", "")
            title_text = chunk.metadata.get("title", "")
            
            if alt_text:
                parts.append(f"Description: {alt_text}")
            if title_text:
                parts.append(f"Title: {title_text}")
            
            parts.append(f"Source: {chunk.content}")
        
        else:
            # Для обычного текста
            if headers:
                breadcrumbs = " > ".join(headers)
                parts.append(f"Section: {breadcrumbs}")
            
            # Проверяем, является ли это цитатой
            if chunk.metadata.get("quote"):
                parts.append("Type: Quote")
            
            parts.append("Content:")
            parts.append(chunk.content)
        
        return "\n".join(parts)
