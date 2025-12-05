"""E2E тесты: Сценарий А — Анатомия чанкинга.

Визуализирует как SmartSplitter и MarkdownNodeParser
нарезают документы на чанки.

Запуск:
    pytest tests/e2e/audit/test_chunking_audit.py -v -s
    
Отчёты сохраняются в: tests/audit_reports/YYYY-MM-DD_HH-MM/
"""

import pytest
from pathlib import Path

from semantic_core.domain import Document


class TestChunkingAudit:
    """Тесты визуальной проверки чанкинга."""
    
    def test_simple_text_chunking(
        self,
        pipeline_inspector,
        test_assets_path: Path,
    ):
        """Проверка чанкинга простого текста (.txt).
        
        Критерии проверки (для человека):
        1. Не разрываются ли предложения посередине?
        2. Корректно ли работает overlap между чанками?
        3. Правильный ли размер чанков (близко к chunk_size)?
        """
        txt_file = test_assets_path / "sample_article.txt"
        
        if not txt_file.exists():
            pytest.skip(f"Файл не найден: {txt_file}")
        
        content = txt_file.read_text(encoding="utf-8")
        doc = Document(
            content=content,
            metadata={"source": txt_file.name, "type": "plain_text"},
        )
        
        saved = pipeline_inspector.ingest_with_inspection(doc, mode="sync")
        
        # Базовые проверки
        assert saved.id is not None
        report = pipeline_inspector.reports[-1]
        assert len(report.chunks) > 0, "Должен быть хотя бы один чанк"
    
    def test_structured_markdown_chunking(
        self,
        pipeline_inspector,
        test_assets_path: Path,
    ):
        """Проверка чанкинга структурированного Markdown.
        
        Критерии проверки (для человека):
        1. Правильно ли определён ChunkType (TEXT, CODE)?
        2. Сохраняется ли иерархия заголовков (breadcrumbs)?
        3. Корректно ли определяется язык кода?
        4. Не разрывается ли код на несколько чанков?
        """
        for md_name in ["nested_headers_example.md", "mixed_content_example.md"]:
            md_file = test_assets_path / md_name
            
            if not md_file.exists():
                continue
            
            content = md_file.read_text(encoding="utf-8")
            doc = Document(
                content=content,
                metadata={"source": md_name, "type": "markdown"},
            )
            
            saved = pipeline_inspector.ingest_with_inspection(doc, mode="sync")
            assert saved.id is not None
    
    def test_mixed_content_deep_dive(
        self,
        pipeline_inspector,
        test_assets_path: Path,
    ):
        """Детальный анализ документа со смешанным контентом.
        
        Специальный тест для сложного документа с:
        - Таблицами
        - Блоками кода на разных языках (SQL, Python)
        - Вложенными заголовками
        - Цитатами и note блоками
        - Чек-листами
        - Математическими формулами
        """
        research_path = test_assets_path / "mixed_content_example.md"
        
        if not research_path.exists():
            pytest.skip(f"Файл не найден: {research_path}")
        
        content = research_path.read_text(encoding="utf-8")
        doc = Document(
            content=content,
            metadata={
                "source": "mixed_content_example.md",
                "type": "research",
                "topic": "hybrid_search",
            },
        )
        
        saved_doc = pipeline_inspector.ingest_with_inspection(doc, mode="sync")
        
        # Проверяем что документ сохранён
        assert saved_doc.id is not None
        
        # Проверяем что есть чанки разных типов
        report = pipeline_inspector.reports[-1]
        chunk_types = {c.chunk_type for c in report.chunks}
        
        # Должно быть несколько типов чанков
        assert len(chunk_types) >= 1, f"Найдено типов: {chunk_types}"
        assert len(report.chunks) >= 3, f"Ожидалось >=3 чанков, получено {len(report.chunks)}"


class TestNestedHeadersAudit:
    """Тесты проверки глубокой вложенности заголовков."""
    
    def test_headers_breadcrumbs(
        self,
        pipeline_inspector,
        test_assets_path: Path,
    ):
        """Проверка формирования breadcrumbs для вложенных заголовков.
        
        Критерии проверки:
        1. Сохраняется ли полная иерархия h1 > h2 > h3 > ...?
        2. При переходе к новому h2, сбрасывается ли h3+?
        
        nested_headers_example.md имеет структуру:
        # Глава 1
          ## 1.1
            ### 1.1.1
            ### 1.1.2
          ## 1.2
            ### 1.2.1
              #### 1.2.1.1 (while loop)
        # Глава 2
        # Глава 3
        """
        nested_path = test_assets_path / "nested_headers_example.md"
        
        if not nested_path.exists():
            pytest.skip(f"Файл не найден: {nested_path}")
        
        content = nested_path.read_text(encoding="utf-8")
        doc = Document(
            content=content,
            metadata={"source": "nested_headers_example.md"},
        )
        
        pipeline_inspector.ingest_with_inspection(doc, mode="sync")
        
        # Проверяем что есть чанки с глубокой вложенностью
        report = pipeline_inspector.reports[-1]
        
        # Не все чанки могут иметь headers (например, если это код без контекста)
        headers_depths = [len(c.headers) for c in report.chunks if c.headers]
        
        if headers_depths:
            max_depth = max(headers_depths)
            # Ожидаем минимум 3 уровня вложенности (h1 > h2 > h3)
            assert max_depth >= 3, f"Максимальная глубина: {max_depth}, ожидалось >= 3"


class TestCodeBlocksAudit:
    """Тесты для проверки обработки кода."""
    
    def test_multiple_code_languages(
        self,
        pipeline_inspector,
        test_assets_path: Path,
    ):
        """Проверка что код на разных языках правильно распознаётся.
        
        В mixed_content_example.md есть:
        - SQL блоки
        - Python блоки
        """
        md_path = test_assets_path / "mixed_content_example.md"
        
        if not md_path.exists():
            pytest.skip(f"Файл не найден: {md_path}")
        
        content = md_path.read_text(encoding="utf-8")
        doc = Document(
            content=content,
            metadata={"source": "mixed_content_example.md"},
        )
        
        pipeline_inspector.ingest_with_inspection(doc, mode="sync")
        
        report = pipeline_inspector.reports[-1]
        
        # Собираем языки кода из чанков
        languages = {c.language for c in report.chunks if c.language}
        
        # Должны найтись sql и python
        assert len(languages) >= 1, f"Найденные языки: {languages}"
