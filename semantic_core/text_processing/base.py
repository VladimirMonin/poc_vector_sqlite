"""
Абстрактный интерфейс для сплиттеров текста.

Определяет контракт для всех реализаций нарезки текста.
Позволяет легко заменять SimpleTextSplitter на более сложные
варианты (Markdown, HTML, Code-aware) без изменения кода базы данных.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class Chunk:
    """
    Фрагмент текста после нарезки.
    
    Attributes:
        text: Содержимое чанка
        index: Порядковый номер чанка в документе (начиная с 0)
        metadata: Дополнительные данные (например, заголовок секции, номер строки)
    """
    text: str
    index: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __repr__(self) -> str:
        preview = self.text[:50] + "..." if len(self.text) > 50 else self.text
        return f"Chunk(index={self.index}, text='{preview}')"


class TextSplitter(ABC):
    """
    Абстрактный базовый класс для всех сплиттеров.
    
    Реализации должны определить метод split_text(),
    который принимает текст и возвращает список Chunk.
    """
    
    @abstractmethod
    def split_text(self, text: str) -> List[Chunk]:
        """
        Разбивает текст на чанки согласно логике конкретного сплиттера.
        
        Args:
            text: Исходный текст для нарезки
            
        Returns:
            Список объектов Chunk с индексами и метаданными
            
        Raises:
            NotImplementedError: Если метод не переопределен в подклассе
        """
        raise NotImplementedError("Метод split_text() должен быть реализован")
