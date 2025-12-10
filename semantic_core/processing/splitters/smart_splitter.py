"""Умный сплиттер для структурированных документов.

Классы:
    SmartSplitter
        Сплиттер, работающий с парсерами для умной группировки сегментов.
"""

from typing import Optional

from semantic_core.domain import Chunk, ChunkType, Document, MEDIA_CHUNK_TYPES
from semantic_core.interfaces.parser import DocumentParser, ParsingSegment
from semantic_core.interfaces.splitter import BaseSplitter
from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)


class SmartSplitter(BaseSplitter):
    """Умный сплиттер для структурированных документов.

    Работает поверх DocumentParser и применяет интеллектуальную
    логику группировки сегментов в чанки:

    - Группирует мелкие текстовые параграфы до достижения chunk_size
    - Изолирует блоки кода в отдельные чанки (даже маленькие)
    - Изолирует медиа-ссылки (IMAGE/AUDIO/VIDEO_REF) в отдельные чанки
    - Сохраняет метаданные иерархии заголовков
    - Режет большие блоки кода построчно с дублированием метаданных

    Attributes:
        parser: Парсер документов (например, MarkdownNodeParser).
        chunk_size: Максимальный размер текстового чанка в символах.
        code_chunk_size: Максимальный размер чанка кода в символах.
        preserve_code: Если True, код никогда не смешивается с текстом.
    """

    def __init__(
        self,
        parser: DocumentParser,
        chunk_size: int = 1800,
        code_chunk_size: int = 2000,
        preserve_code: bool = True,
    ):
        """Инициализирует SmartSplitter.

        Args:
            parser: Экземпляр парсера документов.
            chunk_size: Макс. размер текстового чанка.
            code_chunk_size: Макс. размер чанка кода.
            preserve_code: Изолировать блоки кода.
        """
        self.parser = parser
        self.chunk_size = chunk_size
        self.code_chunk_size = code_chunk_size
        self.preserve_code = preserve_code

    def split(self, document: Document) -> list[Chunk]:
        """Разбивает документ на умные чанки.

        Args:
            document: Исходный документ.

        Returns:
            Список чанков с метаданными структуры.

        Raises:
            ValueError: Если document пустой.
        """
        # Получаем идентификатор для логов: из metadata или id документа
        doc_id = document.metadata.get("doc_id") or (
            str(document.id)[:8] if document.id else "unknown"
        )
        log = logger.bind(doc_id=doc_id)

        if not document.content or not document.content.strip():
            log.error("Попытка разбить пустой документ")
            raise ValueError("Document content is empty")

        log.debug(
            f"Начало разбиения: chunk_size={self.chunk_size}, "
            f"code_chunk_size={self.code_chunk_size}, preserve_code={self.preserve_code}"
        )

        # Парсим документ на сегменты
        segments = list(self.parser.parse(document.content))
        log.debug(f"Получено {len(segments)} сегментов от парсера")

        # Преобразуем сегменты в чанки
        chunks: list[Chunk] = []
        chunk_index = 0

        # Буфер для накопления текстовых сегментов
        text_buffer: list[ParsingSegment] = []

        # Счётчики для статистики
        stats = {"text": 0, "code": 0, "media": 0}

        for seg_idx, segment in enumerate(segments):
            # Обработка блоков кода - всегда изолированно
            if segment.segment_type == ChunkType.CODE and self.preserve_code:
                # Сначала сбрасываем накопленный текст
                if text_buffer:
                    text_chunks = self._flush_text_buffer(text_buffer, chunk_index)
                    chunks.extend(text_chunks)
                    chunk_index += len(text_chunks)
                    stats["text"] += len(text_chunks)
                    text_buffer.clear()

                # Создаем чанк(и) для кода
                code_size = len(segment.content)
                will_split = code_size > self.code_chunk_size
                log.trace(
                    f"Сегмент[{seg_idx}] CODE: {code_size} символов, "
                    f"lang={segment.language or 'none'}, split={will_split}"
                )

                code_chunks = self._create_code_chunks(segment, chunk_index)
                chunks.extend(code_chunks)
                chunk_index += len(code_chunks)
                stats["code"] += len(code_chunks)

            # Обработка изображений/медиа - всегда отдельный чанк
            elif segment.segment_type in MEDIA_CHUNK_TYPES:
                # Сначала сбрасываем накопленный текст
                if text_buffer:
                    text_chunks = self._flush_text_buffer(text_buffer, chunk_index)
                    chunks.extend(text_chunks)
                    chunk_index += len(text_chunks)
                    stats["text"] += len(text_chunks)
                    text_buffer.clear()

                log.trace(
                    f"Сегмент[{seg_idx}] {segment.segment_type.name}: {segment.content[:60]}"
                )

                # Создаём отдельный чанк для медиа-ссылки
                chunks.append(
                    Chunk(
                        content=segment.content,
                        chunk_index=chunk_index,
                        chunk_type=segment.segment_type,  # IMAGE/AUDIO/VIDEO_REF
                        metadata={
                            "headers": segment.headers,
                            "start_line": segment.start_line,
                            "end_line": segment.end_line,
                            "alt": segment.metadata.get("alt", "")
                            if segment.metadata
                            else "",
                            "title": segment.metadata.get("title", "")
                            if segment.metadata
                            else "",
                        },
                    )
                )
                chunk_index += 1
                stats["media"] += 1

            # Обработка текста
            elif segment.segment_type == ChunkType.TEXT:
                text_buffer.append(segment)

                # Проверяем, не переполнен ли буфер
                buffer_size = sum(len(s.content) for s in text_buffer)
                if buffer_size >= self.chunk_size:
                    log.trace(
                        f"Буфер текста переполнен: {buffer_size} >= {self.chunk_size}, сброс"
                    )
                    text_chunks = self._flush_text_buffer(text_buffer, chunk_index)
                    chunks.extend(text_chunks)
                    chunk_index += len(text_chunks)
                    stats["text"] += len(text_chunks)
                    text_buffer.clear()

            else:
                # Для других типов (TABLE и т.д.) - пока обрабатываем как текст
                text_buffer.append(segment)

        # Сбрасываем оставшийся текст
        if text_buffer:
            log.trace(f"Сброс оставшегося буфера: {len(text_buffer)} сегментов")
            text_chunks = self._flush_text_buffer(text_buffer, chunk_index)
            chunks.extend(text_chunks)
            stats["text"] += len(text_chunks)

        log.info(
            f"Разбиение завершено: {len(segments)} сегментов → {len(chunks)} чанков "
            f"(text={stats['text']}, code={stats['code']}, media={stats['media']})"
        )

        return chunks

    def _flush_text_buffer(
        self, buffer: list[ParsingSegment], start_index: int
    ) -> list[Chunk]:
        """Преобразует накопленные текстовые сегменты в чанки.

        Args:
            buffer: Список сегментов для группировки.
            start_index: Начальный индекс для нумерации чанков.

        Returns:
            Список чанков.
        """
        if not buffer:
            return []

        total_size = sum(len(s.content) for s in buffer)
        logger.trace(
            f"Группировка {len(buffer)} текстовых сегментов ({total_size} символов)"
        )

        chunks: list[Chunk] = []
        current_chunk_parts: list[str] = []
        current_size = 0
        current_headers: list[str] = []
        current_start_line: Optional[int] = None
        current_end_line: Optional[int] = None

        for segment in buffer:
            segment_size = len(segment.content)

            # Если добавление этого сегмента превысит размер, создаем чанк
            if current_size + segment_size > self.chunk_size and current_chunk_parts:
                chunks.append(
                    Chunk(
                        content="\n".join(current_chunk_parts),
                        chunk_index=start_index + len(chunks),
                        chunk_type=ChunkType.TEXT,
                        metadata={
                            "headers": current_headers,
                            "start_line": current_start_line,
                            "end_line": current_end_line,
                        },
                    )
                )
                current_chunk_parts.clear()
                current_size = 0

            # Добавляем сегмент в текущий чанк
            current_chunk_parts.append(segment.content)
            current_size += segment_size

            # Обновляем метаданные
            if segment.headers:
                current_headers = segment.headers
            if current_start_line is None and segment.start_line:
                current_start_line = segment.start_line
            if segment.end_line:
                current_end_line = segment.end_line

        # Создаем последний чанк
        if current_chunk_parts:
            chunks.append(
                Chunk(
                    content="\n".join(current_chunk_parts),
                    chunk_index=start_index + len(chunks),
                    chunk_type=ChunkType.TEXT,
                    metadata={
                        "headers": current_headers,
                        "start_line": current_start_line,
                        "end_line": current_end_line,
                    },
                )
            )

        logger.trace(f"Сгруппировано в {len(chunks)} текстовых чанков")
        return chunks

    def _create_code_chunks(
        self, segment: ParsingSegment, start_index: int
    ) -> list[Chunk]:
        """Создает чанк(и) для блока кода.

        Если код маленький - один чанк.
        Если большой - режет построчно.

        Args:
            segment: Сегмент с кодом.
            start_index: Начальный индекс для нумерации.

        Returns:
            Список чанков кода.
        """
        code_content = segment.content
        code_size = len(code_content)

        # Если код влезает в лимит - создаем один чанк
        if code_size <= self.code_chunk_size:
            logger.trace(f"Код ({code_size} символов) влезает в лимит, создаём 1 чанк")
            return [
                Chunk(
                    content=code_content,
                    chunk_index=start_index,
                    chunk_type=ChunkType.CODE,
                    language=segment.language,
                    metadata={
                        "headers": segment.headers,
                        "start_line": segment.start_line,
                        "end_line": segment.end_line,
                    },
                )
            ]

        # Иначе режем построчно
        logger.trace(
            f"Код ({code_size} символов) > {self.code_chunk_size}, режем построчно"
        )
        chunks: list[Chunk] = []
        lines = code_content.splitlines(keepends=True)
        current_chunk_lines: list[str] = []
        current_size = 0

        for line in lines:
            line_size = len(line)

            if current_size + line_size > self.code_chunk_size and current_chunk_lines:
                # Создаем чанк
                chunks.append(
                    Chunk(
                        content="".join(current_chunk_lines),
                        chunk_index=start_index + len(chunks),
                        chunk_type=ChunkType.CODE,
                        language=segment.language,
                        metadata={
                            "headers": segment.headers,
                            "start_line": segment.start_line,
                            "end_line": segment.end_line,
                            "partial": True,  # Помечаем как часть большого блока
                        },
                    )
                )
                current_chunk_lines.clear()
                current_size = 0

            current_chunk_lines.append(line)
            current_size += line_size

        # Последний чанк
        if current_chunk_lines:
            chunks.append(
                Chunk(
                    content="".join(current_chunk_lines),
                    chunk_index=start_index + len(chunks),
                    chunk_type=ChunkType.CODE,
                    language=segment.language,
                    metadata={
                        "headers": segment.headers,
                        "start_line": segment.start_line,
                        "end_line": segment.end_line,
                        "partial": True,
                    },
                )
            )

        logger.trace(f"Большой блок кода разбит на {len(chunks)} чанков")
        return chunks
