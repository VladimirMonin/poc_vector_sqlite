"""Модель результата поиска.

Классы:
    MatchType
        Перечисление типов совпадения.
    SearchResult
        DTO для унифицированного результата поиска (документ).
    ChunkResult
        DTO для гранулярного поиска (отдельный чанк).
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from semantic_core.domain.document import Document
from semantic_core.domain.chunk import Chunk, ChunkType


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


@dataclass
class ChunkResult:
    """Результат гранулярного поиска (отдельный чанк).

    Используется когда нужно найти конкретные фрагменты документа,
    а не весь документ целиком. Удобно для поиска кода, цитат или
    специфических абзацев.

    Attributes:
        chunk: Найденный чанк.
        score: Релевантность (0.0 - 1.0).
        match_type: Тип совпадения (VECTOR, FTS, HYBRID).
        parent_doc_id: ID родительского документа.
        parent_doc_title: Заголовок родительского документа.
        parent_metadata: Метаданные родительского документа.
        highlight: Подсвеченный фрагмент (для FTS).
    """

    chunk: Chunk
    score: float
    match_type: MatchType
    parent_doc_id: int
    parent_doc_title: Optional[str] = None
    parent_metadata: dict[str, Any] = None
    highlight: Optional[str] = None

    # Convenience properties для прямого доступа к атрибутам чанка
    @property
    def chunk_id(self) -> Optional[int]:
        """ID чанка."""
        return self.chunk.id

    @property
    def chunk_index(self) -> int:
        """Индекс чанка в документе."""
        return self.chunk.chunk_index

    @property
    def chunk_type(self) -> ChunkType:
        """Тип чанка."""
        return self.chunk.chunk_type

    @property
    def language(self) -> Optional[str]:
        """Язык программирования (для CODE чанков)."""
        return self.chunk.language

    @property
    def content(self) -> str:
        """Содержимое чанка."""
        return self.chunk.content

    def __repr__(self) -> str:
        chunk_type = self.chunk.chunk_type.value
        lang = f"[{self.chunk.language}]" if self.chunk.language else ""
        parent = self.parent_doc_title or f"Doc#{self.parent_doc_id}"
        preview = (
            self.chunk.content[:30] + "..."
            if len(self.chunk.content) > 30
            else self.chunk.content
        )

        return (
            f"ChunkResult(type={chunk_type}{lang}, parent='{parent}', "
            f"score={self.score:.3f}, preview='{preview}')"
        )
