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


class MarkdownNodeParser:
    """AST-парсер для Markdown документов.
    
    Использует markdown-it-py для разбора документа на токены
    и преобразует их в структурированные сегменты с контекстом.
    
    Возможности:
        - Отслеживание иерархии заголовков (breadcrumbs)
        - Изоляция блоков кода с определением языка
        - Сохранение номеров строк для навигации
        - Определение типов контента (TEXT/CODE/TABLE/IMAGE_REF)
    
    Attributes:
        md: Экземпляр MarkdownIt парсера.
    """
    
    def __init__(self):
        """Инициализирует парсер с настройками CommonMark."""
        self.md = MarkdownIt("commonmark")
    
    def parse(self, content: str) -> Iterator[ParsingSegment]:
        """Парсит Markdown и возвращает поток сегментов.
        
        Args:
            content: Сырой Markdown текст.
            
        Yields:
            ParsingSegment: Структурированные сегменты документа.
        """
        tokens = self.md.parse(content)
        
        # Стек заголовков для отслеживания иерархии
        headers_stack: list[tuple[int, str]] = []  # [(level, text), ...]
        
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
                    text_content = inline_token.content
                    
                    # Проверяем на наличие изображений в inline токенах
                    has_images = any(
                        child.type == "image" 
                        for child in inline_token.children or []
                    )
                    
                    # Если есть только изображение, пометим как IMAGE_REF
                    if has_images and not text_content.strip():
                        # Извлекаем информацию об изображении
                        img_token = next(
                            (t for t in inline_token.children if t.type == "image"),
                            None
                        )
                        if img_token:
                            yield ParsingSegment(
                                content=img_token.attrGet("src") or "",
                                segment_type=ChunkType.IMAGE_REF,
                                headers=[txt for _, txt in headers_stack],
                                start_line=token.map[0] + 1 if token.map else None,
                                end_line=token.map[1] if token.map else None,
                                metadata={
                                    "alt": img_token.content or "",
                                    "title": img_token.attrGet("title") or "",
                                }
                            )
                    else:
                        # Обычный текстовый параграф
                        yield ParsingSegment(
                            content=text_content,
                            segment_type=ChunkType.TEXT,
                            headers=[txt for _, txt in headers_stack],
                            start_line=token.map[0] + 1 if token.map else None,
                            end_line=token.map[1] if token.map else None,
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
                    t.content for t in list_content_tokens 
                    if t.type == "inline"
                )
                
                if list_text.strip():
                    yield ParsingSegment(
                        content=list_text,
                        segment_type=ChunkType.TEXT,
                        headers=[txt for _, txt in headers_stack],
                        start_line=token.map[0] + 1 if token.map else None,
                        end_line=tokens[j-1].map[1] if j > 0 and tokens[j-1].map else None,
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
                    t.content for t in quote_content_tokens 
                    if t.type == "inline"
                )
                
                if quote_text.strip():
                    yield ParsingSegment(
                        content=quote_text,
                        segment_type=ChunkType.TEXT,
                        headers=[txt for _, txt in headers_stack],
                        start_line=token.map[0] + 1 if token.map else None,
                        end_line=tokens[j-1].map[1] if j > 0 and tokens[j-1].map else None,
                        metadata={"quote": True}
                    )
                
                i = j
                continue
            
            i += 1
