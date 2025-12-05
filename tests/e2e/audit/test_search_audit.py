"""E2E тесты: Сценарий B — Качество поиска.

Проверяет релевантность выдачи после индексации.

Запуск:
    pytest tests/e2e/audit/test_search_audit.py -v -s
    
Отчёты сохраняются в: tests/audit_reports/YYYY-MM-DD_HH-MM/
"""

import pytest
from pathlib import Path

from semantic_core.domain import Document


class TestSearchQualityAudit:
    """Тесты визуальной проверки качества поиска."""
    
    def test_search_after_full_indexing(
        self,
        pipeline_inspector,
        test_assets_path: Path,
    ):
        """Индексирует все документы и выполняет поисковые запросы.
        
        Критерии проверки (для человека):
        1. Находится ли нужный документ первым?
        2. Работает ли поиск по коду?
        3. Релевантны ли результаты запросу?
        """
        # 1. Индексируем текстовые файлы
        txt_file = test_assets_path / "sample_article.txt"
        if txt_file.exists():
            content = txt_file.read_text(encoding="utf-8")
            doc = Document(
                content=content,
                metadata={"source": txt_file.name, "category": "text"},
            )
            pipeline_inspector.ingest_with_inspection(doc, mode="sync")
        
        # 2. Индексируем MD файлы
        for md_name in ["nested_headers_example.md", "mixed_content_example.md"]:
            md_file = test_assets_path / md_name
            if md_file.exists():
                content = md_file.read_text(encoding="utf-8")
                doc = Document(
                    content=content,
                    metadata={"source": md_name, "category": "markdown"},
                )
                pipeline_inspector.ingest_with_inspection(doc, mode="sync")
        
        # 3. Поисковые запросы
        queries = [
            "семантический поиск эмбеддинги",
            "Python функции классы",
            "RRF гибридный поиск",
            "sqlite-vec векторные базы данных",
        ]
        
        for query in queries:
            results = pipeline_inspector.search_with_inspection(
                query=query,
                limit=5,
                mode="hybrid",
            )
            # Базовая проверка — результаты есть
            assert results is not None
    
    def test_code_search(
        self,
        pipeline_inspector,
        test_assets_path: Path,
    ):
        """Проверка поиска по коду.
        
        Индексирует документы с кодом и ищет по:
        - Именам функций
        - Ключевым словам языка
        - Комментариям
        """
        # Индексируем документы с кодом
        for md_name in ["nested_headers_example.md", "mixed_content_example.md"]:
            md_path = test_assets_path / md_name
            if not md_path.exists():
                continue
            
            content = md_path.read_text(encoding="utf-8")
            doc = Document(
                content=content,
                metadata={"source": md_name},
            )
            pipeline_inspector.ingest_with_inspection(doc, mode="sync")
        
        # Поисковые запросы по коду
        code_queries = [
            "def greet function",
            "SearchResult dataclass",
            "SELECT embedding MATCH",
            "lambda square",
        ]
        
        for query in code_queries:
            pipeline_inspector.search_with_inspection(
                query=query,
                limit=3,
                mode="vector",
            )


class TestSearchModesAudit:
    """Тесты разных режимов поиска."""
    
    def test_compare_search_modes(
        self,
        pipeline_inspector,
        test_assets_path: Path,
    ):
        """Сравнение результатов vector/fts/hybrid режимов.
        
        Показывает как отличаются результаты в зависимости от режима.
        """
        # Индексируем документ
        md_path = test_assets_path / "mixed_content_example.md"
        if not md_path.exists():
            pytest.skip(f"Файл не найден: {md_path}")
        
        content = md_path.read_text(encoding="utf-8")
        doc = Document(
            content=content,
            metadata={"source": "mixed_content_example.md"},
        )
        pipeline_inspector.ingest_with_inspection(doc, mode="sync")
        
        # Один запрос в разных режимах
        query = "гибридный поиск"
        
        # Vector mode
        pipeline_inspector.search_with_inspection(
            query=query,
            limit=3,
            mode="vector",
        )
        
        # Hybrid mode (FTS часть)
        pipeline_inspector.search_with_inspection(
            query=query,
            limit=3,
            mode="hybrid",
        )
    
    def test_edge_case_queries(
        self,
        pipeline_inspector,
        test_assets_path: Path,
    ):
        """Проверка edge-case запросов.
        
        - Запрос с дефисами (sqlite-vec)
        - Запрос с кавычками
        - Очень короткий запрос
        - Запрос на другом языке
        """
        # Индексируем документ
        txt_file = test_assets_path / "sample_article.txt"
        if txt_file.exists():
            content = txt_file.read_text(encoding="utf-8")
            doc = Document(
                content=content,
                metadata={"source": txt_file.name},
            )
            pipeline_inspector.ingest_with_inspection(doc, mode="sync")
        
        edge_queries = [
            "sqlite-vec",               # Дефис в запросе
            "CREATE VIRTUAL TABLE",     # Многословный термин
            "RRF",                       # Аббревиатура
            "эмбеддинг",                 # Русский термин
        ]
        
        for query in edge_queries:
            pipeline_inspector.search_with_inspection(
                query=query,
                limit=3,
                mode="hybrid",
            )
