"""OCRStep — разбивка OCR текста на чанки с детекцией code blocks.

Этот шаг извлекает ocr_text из analysis и разбивает его на чанки.
Поддерживает два режима парсинга:
- markdown: использует MarkdownNodeParser для детекции code blocks
  (code → ChunkType.CODE, text → ChunkType.TEXT)
- plain: обычный текст без структуры (всё → ChunkType.TEXT)

Архитектурный контекст:
-----------------------
- Phase 14.1.1: Smart Steps Implementation
- Phase 14.5 (финальное улучшение): OCR Markdown parsing для code isolation
- Заменяет логику _split_ocr_into_chunks() из legacy pipeline.py
- Мониторинг code_ratio для обнаружения false positives (UI text как code)

Пример использования:
--------------------
>>> from semantic_core.processing.parsers.markdown_parser import MarkdownNodeParser
>>>
>>> # Инициализация парсера для markdown режима
>>> parser = MarkdownNodeParser()
>>>
>>> # Создание шага с разными chunk_size для text и code
>>> step = OCRStep(
...     parser=parser,
...     ocr_text_chunk_size=1800,
...     ocr_code_chunk_size=2000,
...     parser_mode="markdown",
... )
>>>
>>> # Контекст с OCR текстом, содержащим код
>>> context = MediaContext(
...     media_path=Path("screencast.mp4"),
...     document=Document(...),
...     analysis={"type": "video", "ocr_text": "# Tutorial\\n```python\\nprint('hello')\\n```"},
...     chunks=[],
...     base_index=5,  # После summary + transcript chunks
... )
>>>
>>> new_context = step.process(context)
>>> # Code blocks изолированы в ChunkType.CODE с ocr_code_chunk_size
>>> # Обычный текст в ChunkType.TEXT с ocr_text_chunk_size
"""

from pathlib import Path
from typing import Literal, Optional

from semantic_core.core.media_context import MediaContext
from semantic_core.domain import Chunk, ChunkType
from semantic_core.interfaces.parser import DocumentParser
from semantic_core.processing.steps.base import BaseProcessingStep
from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)


class OCRStep(BaseProcessingStep):
    """Разбивает OCR текст на чанки с детекцией code blocks.

    Использует MarkdownNodeParser для выделения code blocks из OCR текста
    и применяет разные chunk_size для кода и текста.

    Attributes:
        parser: Парсер для Markdown (MarkdownNodeParser) или None для plain режима.
        ocr_text_chunk_size: Размер чанка для обычного текста (токены).
        ocr_code_chunk_size: Размер чанка для code blocks (токены).
        parser_mode: Режим парсинга ("markdown" или "plain").

    Example:
        >>> from semantic_core.processing.parsers.markdown_parser import MarkdownNodeParser
        >>>
        >>> # Для видео с кодом — markdown режим
        >>> parser = MarkdownNodeParser()
        >>> step = OCRStep(
        ...     parser=parser,
        ...     ocr_text_chunk_size=1800,
        ...     ocr_code_chunk_size=2000,
        ...     parser_mode="markdown",
        ... )
        >>>
        >>> context = MediaContext(
        ...     media_path=Path("tutorial.mp4"),
        ...     document=Document(...),
        ...     analysis={"ocr_text": "# Code\\n```python\\nprint('hi')\\n```"},
        ...     chunks=[],
        ...     base_index=0,
        ... )
        >>> new_context = step.process(context)
        >>> # Code blocks изолированы в ChunkType.CODE с ocr_code_chunk_size
    """

    def __init__(
        self,
        parser: Optional[DocumentParser] = None,
        ocr_text_chunk_size: int = 1800,
        ocr_code_chunk_size: int = 2000,
        parser_mode: Literal["markdown", "plain"] = "markdown",
    ):
        """Инициализация шага.

        Args:
            parser: Парсер Markdown (MarkdownNodeParser) для markdown режима.
                Если None, используется plain режим без детекции code blocks.
            ocr_text_chunk_size: Размер чанка в токенах для обычного текста.
                Default 1800 (~2048 токенов Gemini).
            ocr_code_chunk_size: Размер чанка в токенов для code blocks.
                Default 2000 (код плотнее текста).
            parser_mode: Режим парсинга:
                - "markdown": используется parser для детекции code blocks
                - "plain": весь OCR текст → одни TEXT чанки

        Note:
            Если parser_mode="markdown", но parser=None, режим автоматически
            переключится на "plain" с предупреждением.
        """
        self.parser = parser
        self.ocr_text_chunk_size = ocr_text_chunk_size
        self.ocr_code_chunk_size = ocr_code_chunk_size
        self._parser_mode = parser_mode

        # Валидация: markdown требует parser
        if self._parser_mode == "markdown" and self.parser is None:
            logger.warning(
                "[ocr] parser_mode='markdown' requires parser, switching to 'plain'",
                ocr_text_chunk_size=ocr_text_chunk_size,
            )
            self._parser_mode = "plain"

    @property
    def parser_mode(self) -> str:
        """Текущий режим парсинга."""
        return self._parser_mode

    @property
    def step_name(self) -> str:
        """Уникальное имя шага."""
        return "ocr"

    def should_run(self, context: MediaContext) -> bool:
        """Запускаем только если есть ocr_text в analysis.

        Args:
            context: Текущий контекст обработки медиа.

        Returns:
            True, если analysis содержит непустой ocr_text.
        """
        return bool(context.analysis.get("ocr_text"))

    def _split_text_into_chunks(
        self, content: str, chunk_size: int, chunk_type: ChunkType
    ) -> list[str]:
        """Разбивает текст на чанки фиксированного размера.

        Args:
            content: Текст для разбиения.
            chunk_size: Максимальный размер чанка в символах.
            chunk_type: Тип чанка (для логирования).

        Returns:
            Список текстовых чанков.
        """
        if len(content) <= chunk_size:
            return [content]

        chunks = []
        current_pos = 0

        while current_pos < len(content):
            # Берём chunk_size символов
            chunk_end = min(current_pos + chunk_size, len(content))
            chunk_text = content[current_pos:chunk_end]

            # Если не конец текста, пытаемся найти перенос строки для разрыва
            if chunk_end < len(content):
                last_newline = chunk_text.rfind("\n")
                if last_newline > chunk_size * 0.7:  # Не слишком короткий чанк
                    chunk_end = current_pos + last_newline + 1
                    chunk_text = content[current_pos:chunk_end]

            chunks.append(chunk_text)
            current_pos = chunk_end

        return chunks

    def process(self, context: MediaContext) -> MediaContext:
        """Разбивает OCR текст на чанки с детекцией code blocks.

        Args:
            context: Текущий контекст обработки медиа.

        Returns:
            Обновлённый контекст с добавленными OCR чанками.

        Note:
            Markdown режим создаёт отдельные чанки для:
            - CODE блоков (```python) → ChunkType.CODE с ocr_code_chunk_size
            - TEXT контента → ChunkType.TEXT с ocr_text_chunk_size

            Plain режим создаёт только TEXT чанки.
        """
        ocr_text = context.analysis["ocr_text"]

        logger.info(
            f"[{self.step_name}] Splitting OCR text",
            path=str(context.media_path),
            parser_mode=self.parser_mode,
            length=len(ocr_text),
        )

        ocr_chunks: list[Chunk] = []

        if self.parser_mode == "markdown" and self.parser:
            # Парсим Markdown и создаём чанки по сегментам
            segments = list(self.parser.parse(ocr_text))

            logger.trace(
                f"[{self.step_name}] Markdown parsing produced segments",
                segments_count=len(segments),
            )

            for segment in segments:
                # Определяем chunk_size по типу сегмента
                if segment.segment_type == ChunkType.CODE:
                    chunk_size = self.ocr_code_chunk_size
                else:
                    chunk_size = self.ocr_text_chunk_size

                # Разбиваем длинные сегменты на части
                segment_chunks = self._split_text_into_chunks(
                    content=segment.content,
                    chunk_size=chunk_size,
                    chunk_type=segment.segment_type,
                )

                for chunk_text in segment_chunks:
                    # Создаём метаданные
                    metadata = {
                        "_original_path": str(context.media_path),
                        "role": "ocr",
                        "parent_media_path": str(context.media_path),
                    }

                    # Добавляем hierarchical context
                    if segment.headers:
                        metadata["hierarchical_context"] = " > ".join(segment.headers)

                    # Язык для CODE
                    if segment.segment_type == ChunkType.CODE and segment.language:
                        metadata["language"] = segment.language

                    # Номера строк
                    if segment.start_line is not None:
                        metadata["start_line"] = segment.start_line
                    if segment.end_line is not None:
                        metadata["end_line"] = segment.end_line

                    chunk = Chunk(
                        content=chunk_text,
                        chunk_type=segment.segment_type,
                        chunk_index=context.base_index + len(ocr_chunks),
                        metadata=metadata,
                    )
                    ocr_chunks.append(chunk)

        else:
            # Plain режим — весь текст как TEXT
            plain_chunks = self._split_text_into_chunks(
                content=ocr_text,
                chunk_size=self.ocr_text_chunk_size,
                chunk_type=ChunkType.TEXT,
            )

            for idx, chunk_text in enumerate(plain_chunks):
                metadata = {
                    "_original_path": str(context.media_path),
                    "role": "ocr",
                    "parent_media_path": str(context.media_path),
                }

                chunk = Chunk(
                    content=chunk_text,
                    chunk_type=ChunkType.TEXT,
                    chunk_index=context.base_index + idx,
                    metadata=metadata,
                )
                ocr_chunks.append(chunk)

        # Мониторинг code_ratio для обнаружения false positives
        code_chunks = [c for c in ocr_chunks if c.chunk_type == ChunkType.CODE]
        code_ratio = len(code_chunks) / len(ocr_chunks) if ocr_chunks else 0

        logger.info(
            f"[{self.step_name}] Created chunks",
            count=len(ocr_chunks),
            code_chunks=len(code_chunks),
            text_chunks=len(ocr_chunks) - len(code_chunks),
            code_ratio=f"{code_ratio:.2%}",
        )

        # WARNING: Если code_ratio > 50%, возможны ложные срабатывания (UI text как code)
        if code_ratio > 0.5:
            logger.warning(
                f"[{self.step_name}] High code ratio detected (possibly UI text misdetected as code)",
                code_ratio=f"{code_ratio:.2%}",
                path=str(context.media_path),
                code_chunks=len(code_chunks),
                total_chunks=len(ocr_chunks),
                suggestion="Consider using parser_mode='plain' if OCR text is mostly UI",
            )

        return context.with_chunks(ocr_chunks)
