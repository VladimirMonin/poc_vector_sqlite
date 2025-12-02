"""Модель результата поиска.

Классы:
    MatchType
        Перечисление типов совпадения.
    SearchResult
        DTO для унифицированного результата поиска.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from semantic_core.domain.document import Document


class MatchType(str, Enum):
    """Тип совпадения в результатах поиска.
    
    Attributes:
        VECTOR: Найдено через векторный поиск (семантическое сходство).
        FTS: Найдено через полнотекстовый поиск (ключевые слова).
        HYBRID: Комбинированный результат (RRF).
    """
    
    VECTOR = "vector"
    FTS = "fts"
    HYBRID = "hybrid"


@dataclass
class SearchResult:
    """Результат поиска (унифицированная обёртка).
    
    Скрывает детали реализации хранилища и предоставляет
    единый интерфейс для работы с результатами поиска.
    
    Attributes:
        document: Найденный документ.
        score: Релевантность (0.0 - 1.0 для векторного, rank для гибридного).
        match_type: Тип совпадения (VECTOR, FTS, HYBRID).
        chunk_id: ID чанка, который дал совпадение (если применимо).
        highlight: Подсвеченный фрагмент текста (для FTS).
    """
    
    document: Document
    score: float
    match_type: MatchType
    chunk_id: Optional[int] = None
    highlight: Optional[str] = None
    
    def __repr__(self) -> str:
        title = self.document.metadata.get("title", "Untitled")
        return (
            f"SearchResult(doc='{title}', score={self.score:.3f}, "
            f"type={self.match_type.value})"
        )
