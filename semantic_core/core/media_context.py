"""MediaContext — immutable контейнер данных для media processing pipeline.

Этот модуль содержит MediaContext dataclass, который передаётся между шагами
обработки медиа-файлов. Контекст является immutable — каждый шаг возвращает
новый экземпляр через метод with_chunks().

Архитектурный контекст:
-----------------------
- Phase 14.1.0: Core Architecture — фундамент step-based pipeline
- Используется в MediaPipeline для координации шагов обработки
- Заменяет прямую передачу параметров между методами в legacy pipeline.py

Пример использования:
--------------------
>>> from pathlib import Path
>>> from semantic_core.domain import Document, Chunk
>>> 
>>> # Создаём начальный контекст
>>> context = MediaContext(
...     media_path=Path("video.mp4"),
...     document=Document(...),
...     analysis={"type": "video", "description": "..."},
...     chunks=[],
...     base_index=0,
... )
>>> 
>>> # Шаг добавляет чанки
>>> summary_chunk = Chunk(content="Summary", chunk_index=0)
>>> new_context = context.with_chunks([summary_chunk])
>>> 
>>> # Базовый индекс автоматически обновился
>>> assert new_context.base_index == 1
>>> assert len(new_context.chunks) == 1
"""

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from semantic_core.domain import Chunk, Document


@dataclass(frozen=True)
class MediaContext:
    """Immutable контекст обработки медиа-файла.
    
    Передаётся между шагами processing pipeline. Каждый шаг возвращает
    обновлённый контекст через метод with_chunks().
    
    Attributes:
        media_path: Путь к исходному медиа-файлу
        document: Document объект (контейнер метаданных)
        analysis: Результат анализа от Gemini API (dict)
        chunks: Накопленные чанки от всех выполненных шагов
        base_index: Текущий индекс для следующего чанка
        services: Service Locator для зависимостей (splitter, embedder, etc.)
        user_instructions: Опциональные инструкции от пользователя для промптов
    
    Invariants:
        - base_index всегда равен len(chunks) (если increment_index=True)
        - chunks список append-only (новые чанки добавляются, старые не меняются)
        - Frozen dataclass — нельзя изменить поля напрямую
    
    Thread Safety:
        Immutable — безопасно для чтения из нескольких потоков.
        Для модификации используйте with_chunks() (возвращает новый объект).
    """
    
    media_path: Path
    document: Document
    analysis: dict[str, Any]
    chunks: list[Chunk] = field(default_factory=list)
    base_index: int = 0
    services: dict[str, Any] = field(default_factory=dict)
    user_instructions: str | None = None
    
    def with_chunks(
        self,
        new_chunks: list[Chunk],
        increment_index: bool = True,
    ) -> "MediaContext":
        """Возвращает новый контекст с добавленными чанками.
        
        Это единственный способ "изменить" контекст — через создание нового.
        
        Args:
            new_chunks: Список чанков для добавления
            increment_index: Увеличить base_index на количество чанков
        
        Returns:
            Новый MediaContext с обновлёнными chunks и base_index
        
        Example:
            >>> context = MediaContext(...)
            >>> chunk1 = Chunk(content="Text", chunk_index=0)
            >>> chunk2 = Chunk(content="More", chunk_index=1)
            >>> 
            >>> new_ctx = context.with_chunks([chunk1, chunk2])
            >>> assert len(new_ctx.chunks) == 2
            >>> assert new_ctx.base_index == 2
            >>> 
            >>> # Оригинальный контекст не изменился
            >>> assert len(context.chunks) == 0
        """
        updated_chunks = self.chunks + new_chunks
        new_base_index = self.base_index + len(new_chunks) if increment_index else self.base_index
        
        return replace(
            self,
            chunks=updated_chunks,
            base_index=new_base_index,
        )
    
    def get_service(self, key: str, default: Any = None) -> Any:
        """Получает сервис из Service Locator.
        
        Service Locator pattern используется для опциональных зависимостей,
        которые нужны только некоторым шагам (например, splitter, embedder).
        
        Args:
            key: Ключ сервиса (например, "splitter", "embedder")
            default: Значение по умолчанию, если сервис не найден
        
        Returns:
            Экземпляр сервиса или default
        
        Example:
            >>> context = MediaContext(
            ...     ...,
            ...     services={"splitter": SmartSplitter()},
            ... )
            >>> splitter = context.get_service("splitter")
            >>> assert splitter is not None
        """
        return self.services.get(key, default)
