"""Парсер Markdown с использованием AST (markdown-it-py).

Классы:
    MarkdownNodeParser
        Парсер Markdown, отслеживающий иерархию заголовков и типы контента.
"""

from typing import Iterator

from markdown_it import MarkdownIt
from markdown_it.token import Token

from semantic_core.domain import ChunkType
from semantic_core.interfaces.parser import ParsingSegment
from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)


# Расширения медиа-файлов (case-insensitive)
AUDIO_EXTENSIONS = frozenset({".mp3", ".wav", ".ogg", ".flac", ".aac", ".aiff"})
VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".avi", ".mkv", ".webm"})
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"})


def _get_media_type_by_extension(path: str) -> ChunkType | None:
    """Определяет тип медиа по расширению файла.

    Args:
        path: Путь к файлу или URL.

    Returns:
        ChunkType или None если расширение не медийное.
    """
    if not path:
        return None

    # Убираем query string и fragment
    clean_path = path.split("?")[0].split("#")[0]
    ext = "." + clean_path.rsplit(".", 1)[-1].lower() if "." in clean_path else ""

    if ext in AUDIO_EXTENSIONS:
        return ChunkType.AUDIO_REF
    if ext in VIDEO_EXTENSIONS:
        return ChunkType.VIDEO_REF
    if ext in IMAGE_EXTENSIONS:
        return ChunkType.IMAGE_REF
    return None


class MarkdownNodeParser:
    """AST-парсер для Markdown документов.

    Использует markdown-it-py для разбора документа на токены
    и преобразует их в структурированные сегменты с контекстом.

    Возможности:
        - Отслеживание иерархии заголовков (breadcrumbs)
        - Изоляция блоков кода с определением языка
        - Сохранение номеров строк для навигации
        - Определение типов контента (TEXT/CODE/TABLE/IMAGE_REF/AUDIO_REF/VIDEO_REF)
        - Детекция медиа-ссылок по расширению файла

    Attributes:
        md: Экземпляр MarkdownIt парсера.
    """

    def __init__(self):
        """Инициализирует парсер с настройками CommonMark."""
        self.md = MarkdownIt("commonmark")

    def _has_text_outside_media(self, children: list[Token]) -> bool:
        """Проверяет, есть ли текст вне медиа-элементов (изображений/ссылок на аудио/видео).

        Не считает текстом:
        - Текст внутри медиа-ссылок (между link_open и link_close с медиа-расширением)
        - Пустой текст (whitespace)

        Args:
            children: Список inline-токенов.

        Returns:
            True если есть текстовый контент вне медиа-ссылок.
        """
        inside_media_link = False
        i = 0

        while i < len(children):
            child = children[i]

            # Отслеживаем вход в медиа-ссылку
            if child.type == "link_open":
                href = child.attrGet("href") or ""
                media_type = _get_media_type_by_extension(href)
                if media_type in (ChunkType.AUDIO_REF, ChunkType.VIDEO_REF):
                    inside_media_link = True
                i += 1
                continue

            if child.type == "link_close":
                inside_media_link = False
                i += 1
                continue

            # Изображения - это медиа, их текст (alt) не считаем
            if child.type == "image":
                i += 1
                continue

            # Текст вне медиа-ссылок
            if child.type == "text" and not inside_media_link:
                if child.content.strip():
                    return True

            i += 1

        return False

    def _process_inline_children(
        self,
        children: list[Token],
        headers: list[str],
        start_line: int | None,
        end_line: int | None,
    ) -> Iterator[ParsingSegment]:
        """Обрабатывает inline-токены и извлекает медиа-ссылки.

        Детектирует:
        - Изображения: ![alt](path) → IMAGE_REF (или VIDEO_REF по расширению)
        - Ссылки на аудио: [text](file.mp3) → AUDIO_REF
        - Ссылки на видео: [text](file.mp4) → VIDEO_REF

        Args:
            children: Список inline-токенов.
            headers: Текущий стек заголовков.
            start_line: Начальная строка параграфа.
            end_line: Конечная строка параграфа.

        Yields:
            ParsingSegment для найденных медиа-элементов.
        """
        i = 0
        while i < len(children):
            child = children[i]

            # Обработка изображений: ![alt](src)
            if child.type == "image":
                src = child.attrGet("src") or ""
                alt = child.content or ""
                title = child.attrGet("title") or ""

                # Определяем тип по расширению (может быть VIDEO!)
                media_type = _get_media_type_by_extension(src)
                if media_type is None:
                    media_type = ChunkType.IMAGE_REF  # fallback

                yield ParsingSegment(
                    content=src,
                    segment_type=media_type,
                    headers=headers,
                    start_line=start_line,
                    end_line=end_line,
                    metadata={"alt": alt, "title": title},
                )
                i += 1
                continue

            # Обработка ссылок: [text](href)
            if child.type == "link_open":
                href = child.attrGet("href") or ""
                media_type = _get_media_type_by_extension(href)

                if media_type in (ChunkType.AUDIO_REF, ChunkType.VIDEO_REF):
                    # Собираем текст ссылки (между link_open и link_close)
                    link_text_parts = []
                    j = i + 1
                    while j < len(children) and children[j].type != "link_close":
                        if children[j].type == "text":
                            link_text_parts.append(children[j].content)
                        j += 1

                    link_text = "".join(link_text_parts)

                    yield ParsingSegment(
                        content=href,
                        segment_type=media_type,
                        headers=headers,
                        start_line=start_line,
                        end_line=end_line,
                        metadata={"alt": link_text},
                    )

                    # Пропускаем до link_close включительно
                    i = j + 1
                    continue

            i += 1

    def parse(self, content: str) -> Iterator[ParsingSegment]:
        """Парсит Markdown и возвращает поток сегментов.

        Args:
            content: Сырой Markdown текст.

        Yields:
            ParsingSegment: Структурированные сегменты документа.
        """
        # Создаём логгер с контекстом документа
        content_hash = hash(content) & 0xFFFFFF  # 6 hex digits
        log = logger.bind(doc_id=f"doc-{content_hash:06x}")

        content_len = len(content)
        has_frontmatter = content.strip().startswith("---")
        log.debug(
            f"Начало парсинга: {content_len} символов, frontmatter={has_frontmatter}"
        )

        tokens = self.md.parse(content)
        log.trace(f"markdown-it выдал {len(tokens)} токенов верхнего уровня")

        # Стек заголовков для отслеживания иерархии
        headers_stack: list[tuple[int, str]] = []  # [(level, text), ...]

        # Счётчики для статистики
        stats = {
            "headers": 0,
            "paragraphs": 0,
            "code_blocks": 0,
            "media": 0,
            "lists": 0,
            "quotes": 0,
        }

        i = 0
        while i < len(tokens):
            token = tokens[i]

            # Обработка заголовков
            if token.type == "heading_open":
                level = int(token.tag[1])  # h1 -> 1, h2 -> 2, ...

                # Получаем содержимое заголовка из следующего токена
                inline_token = tokens[i + 1] if i + 1 < len(tokens) else None
                header_text = inline_token.content if inline_token else ""

                # Обновляем стек: удаляем заголовки того же или меньшего уровня
                headers_stack = [
                    (lvl, txt) for lvl, txt in headers_stack if lvl < level
                ]
                headers_stack.append((level, header_text))
                stats["headers"] += 1

                log.trace(
                    f"Заголовок h{level}: '{header_text[:50]}{'...' if len(header_text) > 50 else ''}'"
                )

                # Пропускаем heading_open, inline, heading_close
                i += 3
                continue

            # Обработка блоков кода (fence)
            if token.type == "fence":
                language = token.info.strip() if token.info else None
                code_content = token.content

                # Извлекаем номера строк из карты токена
                start_line = token.map[0] + 1 if token.map else None
                end_line = token.map[1] if token.map else None

                stats["code_blocks"] += 1
                log.trace(
                    f"Блок кода: lang={language or 'none'}, "
                    f"{len(code_content)} символов, строки {start_line}-{end_line}"
                )

                yield ParsingSegment(
                    content=code_content,
                    segment_type=ChunkType.CODE,
                    language=language,
                    headers=[txt for _, txt in headers_stack],
                    start_line=start_line,
                    end_line=end_line,
                )
                i += 1
                continue

            # Обработка параграфов и другого текстового контента
            if token.type == "paragraph_open":
                # Получаем содержимое из inline токена
                inline_token = tokens[i + 1] if i + 1 < len(tokens) else None
                if inline_token and inline_token.type == "inline":
                    children = inline_token.children or []
                    current_headers = [txt for _, txt in headers_stack]
                    start_line = token.map[0] + 1 if token.map else None
                    end_line = token.map[1] if token.map else None

                    # Извлекаем медиа-элементы из inline-токенов
                    media_segments = list(
                        self._process_inline_children(
                            children, current_headers, start_line, end_line
                        )
                    )

                    # Проверяем, есть ли текст ВНЕ медиа-элементов
                    has_text = self._has_text_outside_media(children)

                    # Если есть только медиа (без текста), отдаём их как отдельные сегменты
                    if media_segments and not has_text:
                        stats["media"] += len(media_segments)
                        for seg in media_segments:
                            log.trace(
                                f"Медиа-элемент: type={seg.segment_type.name}, path={seg.content[:60]}"
                            )
                        yield from media_segments
                    else:
                        # Обычный текстовый параграф
                        stats["paragraphs"] += 1
                        text_content = inline_token.content
                        yield ParsingSegment(
                            content=text_content,
                            segment_type=ChunkType.TEXT,
                            headers=current_headers,
                            start_line=start_line,
                            end_line=end_line,
                        )

                # Пропускаем paragraph_open, inline, paragraph_close
                i += 3
                continue

            # Обработка списков (извлекаем текст из list_item)
            if token.type == "list_item_open":
                # Собираем содержимое list item
                list_content_tokens = []
                j = i + 1
                depth = 1

                while j < len(tokens) and depth > 0:
                    if tokens[j].type == "list_item_open":
                        depth += 1
                    elif tokens[j].type == "list_item_close":
                        depth -= 1
                    if depth > 0:
                        list_content_tokens.append(tokens[j])
                    j += 1

                # Извлекаем текст из inline токенов
                list_text = " ".join(
                    t.content for t in list_content_tokens if t.type == "inline"
                )

                if list_text.strip():
                    stats["lists"] += 1
                    yield ParsingSegment(
                        content=list_text,
                        segment_type=ChunkType.TEXT,
                        headers=[txt for _, txt in headers_stack],
                        start_line=token.map[0] + 1 if token.map else None,
                        end_line=tokens[j - 1].map[1]
                        if j > 0 and tokens[j - 1].map
                        else None,
                    )

                i = j
                continue

            # Обработка blockquote
            if token.type == "blockquote_open":
                # Собираем содержимое blockquote
                quote_content_tokens = []
                j = i + 1
                depth = 1

                while j < len(tokens) and depth > 0:
                    if tokens[j].type == "blockquote_open":
                        depth += 1
                    elif tokens[j].type == "blockquote_close":
                        depth -= 1
                    if depth > 0:
                        quote_content_tokens.append(tokens[j])
                    j += 1

                # Извлекаем текст
                quote_text = " ".join(
                    t.content for t in quote_content_tokens if t.type == "inline"
                )

                if quote_text.strip():
                    stats["quotes"] += 1
                    yield ParsingSegment(
                        content=quote_text,
                        segment_type=ChunkType.TEXT,
                        headers=[txt for _, txt in headers_stack],
                        start_line=token.map[0] + 1 if token.map else None,
                        end_line=tokens[j - 1].map[1]
                        if j > 0 and tokens[j - 1].map
                        else None,
                        metadata={"quote": True},
                    )

                i = j
                continue

            i += 1

        # Итоговая статистика
        log.info(
            f"Парсинг завершён: headers={stats['headers']}, paragraphs={stats['paragraphs']}, "
            f"code_blocks={stats['code_blocks']}, media={stats['media']}, "
            f"lists={stats['lists']}, quotes={stats['quotes']}"
        )
