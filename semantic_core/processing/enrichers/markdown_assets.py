"""Обогащение медиа-чанков контекстом из Markdown документа.

Классы:
    MediaContext: DTO с извлечённым контекстом для Vision/Audio/Video API.
    MarkdownAssetEnricher: Извлекает контекст для медиа-чанков (IMAGE/AUDIO/VIDEO_REF).
"""

from dataclasses import dataclass, field
from typing import Optional

from semantic_core.domain import Chunk, ChunkType, MEDIA_CHUNK_TYPES
from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MediaContext:
    """Контекст для медиа-ресурса из Markdown.

    Собирает информацию о том, где и зачем медиа-файл
    появился в документе.

    Attributes:
        breadcrumbs: Иерархия заголовков ("Setup > Nginx > Configuration").
        surrounding_text: Текст до и после медиа-элемента.
        alt_text: Alt-текст из Markdown синтаксиса.
        title: Title из Markdown синтаксиса (если есть).
        role: Семантическая роль медиа-ресурса.
        media_type: Тип медиа (image/audio/video).
    """

    breadcrumbs: str = ""
    surrounding_text: str = ""
    alt_text: str = ""
    title: str = ""
    role: str = "Media embedded in document"
    media_type: str = "image"  # image, audio, video

    def format_for_api(self) -> str:
        """Форматирует контекст для промпта API (Vision/Audio/Video).

        Returns:
            Структурированный текст для context_text параметра.
        """
        parts = []

        if self.breadcrumbs:
            parts.append(f"Document section: {self.breadcrumbs}")

        if self.alt_text:
            label = "Caption" if self.media_type == "image" else "Description"
            parts.append(f"{label}: {self.alt_text}")

        if self.title:
            parts.append(f"Title: {self.title}")

        if self.surrounding_text:
            parts.append(f"Surrounding text:\n{self.surrounding_text}")

        parts.append(f"Role: {self.role}")

        return "\n".join(parts)

    # Backward compatibility alias
    def format_for_vision(self) -> str:
        """Алиас для format_for_api() (обратная совместимость)."""
        return self.format_for_api()


class MarkdownAssetEnricher:
    """Извлекает контекст для медиа-чанков из Markdown.

    Находит текст вокруг медиа-элемента и формирует контекст
    для Vision/Audio/Video API, чтобы улучшить качество анализа.

    Поддерживаемые типы:
        - IMAGE_REF → контекст для Vision API
        - AUDIO_REF → контекст для Audio API (транскрипция)
        - VIDEO_REF → контекст для Video API (кадры + аудио)

    Атрибуты:
        context_window: Количество символов до/после для surrounding_text.
        skip_code_chunks: Пропускать ли CODE чанки как соседей.

    Пример:
        >>> enricher = MarkdownAssetEnricher(context_window=200)
        >>> context = enricher.get_context(audio_chunk, all_chunks)
        >>> print(context.format_for_api())
    """

    def __init__(
        self,
        context_window: int = 200,
        skip_code_chunks: bool = True,
    ):
        """Инициализация enricher.

        Args:
            context_window: Максимум символов до/после картинки.
            skip_code_chunks: Пропускать CODE чанки при поиске соседей.
        """
        self.context_window = context_window
        self.skip_code_chunks = skip_code_chunks

    def get_context(
        self,
        media_chunk: Chunk,
        all_chunks: list[Chunk],
    ) -> MediaContext:
        """Извлекает контекст для медиа-чанка.

        Алгоритм:
        1. Берёт headers из metadata → breadcrumbs
        2. Находит предыдущий TEXT-чанк → последние N символов
        3. Находит следующий TEXT-чанк → первые N символов
        4. Извлекает alt и title из metadata
        5. Определяет media_type по chunk_type

        Args:
            media_chunk: Медиа-чанк (IMAGE/AUDIO/VIDEO_REF) для обогащения.
            all_chunks: Все чанки документа (для поиска соседей).

        Returns:
            MediaContext с извлечённым контекстом.
        """
        log = logger.bind(chunk_id=f"chunk-{media_chunk.chunk_index}")
        log.debug(
            f"Извлечение контекста для {media_chunk.chunk_type.name}: "
            f"{media_chunk.content[:50]}{'...' if len(media_chunk.content) > 50 else ''}"
        )

        # 1. Формируем breadcrumbs из headers
        headers = media_chunk.metadata.get("headers", [])
        breadcrumbs = " > ".join(headers) if headers else ""

        if breadcrumbs:
            log.trace(f"Breadcrumbs: {breadcrumbs}")

        # 2. Находим позицию чанка
        chunk_index = media_chunk.chunk_index

        # 3. Ищем текст ДО (предыдущий текстовый чанк)
        before_text = self._find_neighbor_text(
            all_chunks,
            chunk_index,
            direction="before",
        )

        # 4. Ищем текст ПОСЛЕ (следующий текстовый чанк)
        after_text = self._find_neighbor_text(
            all_chunks,
            chunk_index,
            direction="after",
        )

        # 5. Формируем surrounding_text
        surrounding_parts = []
        if before_text:
            surrounding_parts.append(f"[Before]: ...{before_text}")
        if after_text:
            surrounding_parts.append(f"[After]: {after_text}...")

        surrounding_text = "\n".join(surrounding_parts)

        if before_text or after_text:
            log.trace(
                f"Найден окружающий текст: before={len(before_text)} chars, "
                f"after={len(after_text)} chars"
            )

        # 6. Извлекаем alt и title
        alt_text = media_chunk.metadata.get("alt", "")
        title = media_chunk.metadata.get("title", "")

        # 7. Определяем media_type и role
        media_type = self._get_media_type_name(media_chunk.chunk_type)
        role = self._get_default_role(media_chunk.chunk_type)

        context = MediaContext(
            breadcrumbs=breadcrumbs,
            surrounding_text=surrounding_text,
            alt_text=alt_text,
            title=title,
            media_type=media_type,
            role=role,
        )

        log.info(
            f"Контекст извлечён: type={media_type}, "
            f"has_breadcrumbs={bool(breadcrumbs)}, "
            f"has_surrounding={bool(surrounding_text)}, "
            f"has_alt={bool(alt_text)}"
        )

        return context

    def _get_media_type_name(self, chunk_type: ChunkType) -> str:
        """Возвращает название типа медиа."""
        mapping = {
            ChunkType.IMAGE_REF: "image",
            ChunkType.AUDIO_REF: "audio",
            ChunkType.VIDEO_REF: "video",
        }
        return mapping.get(chunk_type, "media")

    def _get_default_role(self, chunk_type: ChunkType) -> str:
        """Возвращает дефолтную роль для типа медиа."""
        roles = {
            ChunkType.IMAGE_REF: "Illustration embedded in document",
            ChunkType.AUDIO_REF: "Audio recording embedded in document",
            ChunkType.VIDEO_REF: "Video embedded in document",
        }
        return roles.get(chunk_type, "Media embedded in document")

    def _find_neighbor_text(
        self,
        all_chunks: list[Chunk],
        current_index: int,
        direction: str,
    ) -> str:
        """Находит текст из соседнего TEXT чанка.

        Args:
            all_chunks: Все чанки документа.
            current_index: Индекс текущего чанка.
            direction: 'before' или 'after'.

        Returns:
            Фрагмент текста (обрезанный до context_window).
        """
        # Определяем диапазон поиска
        if direction == "before":
            candidates = [c for c in all_chunks if c.chunk_index < current_index]
            candidates.sort(key=lambda c: c.chunk_index, reverse=True)
        else:
            candidates = [c for c in all_chunks if c.chunk_index > current_index]
            candidates.sort(key=lambda c: c.chunk_index)

        # Ищем первый подходящий TEXT чанк
        for chunk in candidates:
            # Пропускаем не-TEXT чанки
            if chunk.chunk_type != ChunkType.TEXT:
                if self.skip_code_chunks:
                    continue
                # Если не пропускаем код — всё равно берём только TEXT
                continue

            text = chunk.content.strip()
            if not text:
                continue

            logger.trace(
                f"Найден соседний TEXT чанк [{direction}]: "
                f"chunk_index={chunk.chunk_index}, {len(text)} chars"
            )

            # Обрезаем до нужного размера
            if direction == "before":
                # Берём последние N символов
                return text[-self.context_window :]
            else:
                # Берём первые N символов
                return text[: self.context_window]

        logger.trace(f"Соседний TEXT чанк [{direction}] не найден")
        return ""
