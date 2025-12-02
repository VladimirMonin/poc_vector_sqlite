"""Интерфейс для парсеров документов.

Классы:
    ParsingSegment
        Промежуточная структура между парсингом и чанкингом.
    DocumentParser
        Протокол для любого парсера документов.
"""

from dataclasses import dataclass, field
from typing import Iterator, Optional, Protocol

from semantic_core.domain import ChunkType


@dataclass
class ParsingSegment:
    """Промежуточная единица контента после парсинга.
    
    Это логический сегмент документа (параграф, заголовок, блок кода),
    который еще не разбит на чанки, но уже содержит всю структурную информацию.
    
    Attributes:
        content: Текстовое содержимое сегмента.
        segment_type: Тип контента (TEXT/CODE/TABLE/IMAGE_REF).
        language: Язык программирования для блоков кода.
        headers: Иерархия заголовков (breadcrumbs) в момент парсинга.
        start_line: Номер начальной строки в исходном документе.
        end_line: Номер конечной строки в исходном документе.
        metadata: Дополнительные метаданные специфичные для типа контента.
    """
    
    content: str
    segment_type: ChunkType = ChunkType.TEXT
    language: Optional[str] = None
    headers: list[str] = field(default_factory=list)
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    metadata: dict = field(default_factory=dict)
    
    def __repr__(self) -> str:
        preview = self.content[:30] + "..." if len(self.content) > 30 else self.content
        lang_info = f"[{self.language}]" if self.language else ""
        headers_info = " > ".join(self.headers) if self.headers else "no headers"
        return (
            f"Segment(type={self.segment_type.value}{lang_info}, "
            f"headers='{headers_info}', lines={self.start_line}-{self.end_line})"
        )


class DocumentParser(Protocol):
    """Протокол для парсеров документов.
    
    Любой парсер должен уметь преобразовывать сырой текст
    в поток структурированных сегментов.
    """
    
    def parse(self, content: str) -> Iterator[ParsingSegment]:
        """Парсит текст и возвращает поток логических сегментов.
        
        Args:
            content: Сырой текст документа.
            
        Yields:
            ParsingSegment: Логические сегменты с метаданными структуры.
        """
        ...
