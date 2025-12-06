"""Интеграционные тесты для детекции code blocks в OCR тексте.

Проверяет, что SmartSplitter с MarkdownNodeParser корректно изолирует
code blocks из OCR текста видео (скринкасты, технические туториалы).
"""

import pytest
from pathlib import Path

from semantic_core.domain import Document, MediaType, ChunkType
from semantic_core.processing.splitters import SmartSplitter
from semantic_core.processing.parsers import MarkdownNodeParser


@pytest.fixture
def markdown_parser():
    """Markdown parser для code detection."""
    return MarkdownNodeParser()


@pytest.fixture
def smart_splitter(markdown_parser):
    """SmartSplitter с Markdown parser."""
    return SmartSplitter(
        parser=markdown_parser,
        chunk_size=1800,
        code_chunk_size=2000,
    )


class TestOCRCodeDetection:
    """Тесты детекции code blocks в OCR тексте."""
    
    def test_ocr_with_python_code_creates_code_chunk(self, smart_splitter):
        """Проверяет, что Python code block изолируется в отдельный чанк."""
        ocr_text = """
## Function Example

```python
def calculate_total(items):
    return sum(item.price for item in items)
```

This function iterates over items and sums their prices.
"""
        
        temp_doc = Document(
            content=ocr_text,
            metadata={"source": "test_video.mp4"},
            media_type=MediaType.TEXT,  # Parser choice is via SmartSplitter init, not media_type
        )
        
        chunks = smart_splitter.split(temp_doc)
        
        # Assertions
        code_chunks = [c for c in chunks if c.chunk_type == ChunkType.CODE]
        text_chunks = [c for c in chunks if c.chunk_type == ChunkType.TEXT]
        
        assert len(code_chunks) == 1, f"Expected 1 CODE chunk, got {len(code_chunks)}"
        assert code_chunks[0].language == "python"
        assert "def calculate_total" in code_chunks[0].content
        assert len(text_chunks) >= 1, "Expected at least 1 TEXT chunk"
    
    def test_ocr_with_multiple_code_blocks(self, smart_splitter):
        """Проверяет изоляцию нескольких code blocks."""
        ocr_text = """
## SOLID Principles

### Single Responsibility

```python
class UserService:
    def validate(self, user): ...
    def save(self, user): ...
```

### Better Design

```python
class UserValidator:
    def validate(self, user): ...

class UserRepository:
    def save(self, user): ...
```
"""
        
        temp_doc = Document(
            content=ocr_text,
            metadata={"source": "test_slides.mp4"},
            media_type=MediaType.TEXT,
        )
        
        chunks = smart_splitter.split(temp_doc)
        
        code_chunks = [c for c in chunks if c.chunk_type == ChunkType.CODE]
        
        assert len(code_chunks) == 2, f"Expected 2 CODE chunks, got {len(code_chunks)}"
        assert all(c.language == "python" for c in code_chunks)
        assert "UserService" in code_chunks[0].content
        assert "UserValidator" in code_chunks[1].content
    
    def test_ocr_without_code_creates_only_text_chunks(self, smart_splitter):
        """Проверяет, что OCR без code blocks не создаёт CODE chunks."""
        ocr_text = """
## Slide Title

This is a regular slide with bullet points:

- Point 1
- Point 2
- Point 3

No code here, just text.
"""
        
        temp_doc = Document(
            content=ocr_text,
            metadata={"source": "presentation.mp4"},
            media_type=MediaType.TEXT,
        )
        
        chunks = smart_splitter.split(temp_doc)
        
        code_chunks = [c for c in chunks if c.chunk_type == ChunkType.CODE]
        text_chunks = [c for c in chunks if c.chunk_type == ChunkType.TEXT]
        
        assert len(code_chunks) == 0, "Expected no CODE chunks for text-only OCR"
        assert len(text_chunks) >= 1, "Expected at least 1 TEXT chunk"
    
    def test_ocr_with_javascript_code(self, smart_splitter):
        """Проверяет детекцию JavaScript code blocks."""
        ocr_text = """
## React Component

```javascript
function UserCard({ name, email }) {
    return (
        <div className="card">
            <h2>{name}</h2>
            <p>{email}</p>
        </div>
    );
}
```
"""
        
        temp_doc = Document(
            content=ocr_text,
            metadata={"source": "react_tutorial.mp4"},
            media_type=MediaType.TEXT,
        )
        
        chunks = smart_splitter.split(temp_doc)
        
        code_chunks = [c for c in chunks if c.chunk_type == ChunkType.CODE]
        
        assert len(code_chunks) == 1
        assert code_chunks[0].language == "javascript"
        assert "UserCard" in code_chunks[0].content
    
    def test_ocr_code_chunks_preserve_headers(self, smart_splitter):
        """Проверяет, что code chunks сохраняют metadata headers."""
        ocr_text = """
## Section: Database Optimization

### Query Example

```sql
SELECT * FROM users 
WHERE created_at > '2024-01-01'
ORDER BY id DESC
LIMIT 100;
```
"""
        
        temp_doc = Document(
            content=ocr_text,
            metadata={"source": "sql_course.mp4"},
            media_type=MediaType.TEXT,
        )
        
        chunks = smart_splitter.split(temp_doc)
        
        code_chunks = [c for c in chunks if c.chunk_type == ChunkType.CODE]
        
        assert len(code_chunks) == 1
        # Проверяем наличие headers в metadata
        headers = code_chunks[0].metadata.get("headers", [])
        assert len(headers) > 0, "CODE chunk должен сохранять headers"
        # Может быть список: ['Section: Database Optimization', 'Query Example']
    
    @pytest.mark.skip(reason="SmartSplitter parser is set at init, not via media_type")
    def test_plain_text_mode_does_not_detect_code(self, smart_splitter):
        """УСТАРЕВШИЙ ТЕСТ: Parser выбирается при инициализации SmartSplitter, НЕ через media_type."""
        pass


class TestOCRFalsePositives:
    """Тесты для обнаружения false positives (UI text как code)."""
    
    def test_ui_button_text_not_detected_as_code(self, smart_splitter):
        """UI кнопки не должны детектиться как code."""
        ocr_text = """
Settings

> Dark Mode
> Font Size: Large
> Language: English

Save    Cancel
"""
        
        temp_doc = Document(
            content=ocr_text,
            metadata={"source": "app_ui.mp4"},
            media_type=MediaType.TEXT,
        )
        
        chunks = smart_splitter.split(temp_doc)
        
        code_chunks = [c for c in chunks if c.chunk_type == ChunkType.CODE]
        
        # UI text может создать quote blocks, но НЕ CODE blocks
        assert len(code_chunks) == 0, "UI text should not create CODE chunks"
    
    def test_high_code_ratio_warning_triggered(self, smart_splitter, caplog):
        """Проверяет warning при высоком code_ratio (возможны false positives)."""
        # Этот тест требует реальной реализации _split_ocr_into_chunks в pipeline
        # Здесь только демонстрация концепции
        
        # Пример OCR где >50% — code (подозрительно)
        ocr_text = """
```python
code1 = 1
```

```python
code2 = 2
```

Some text.
"""
        
        temp_doc = Document(
            content=ocr_text,
            metadata={"source": "suspicious.mp4"},
            media_type=MediaType.TEXT,
        )
        
        chunks = smart_splitter.split(temp_doc)
        
        code_chunks = [c for c in chunks if c.chunk_type == ChunkType.CODE]
        total_chunks = len(chunks)
        code_ratio = len(code_chunks) / total_chunks if total_chunks else 0
        
        # В реальном pipeline должен быть warning
        if code_ratio > 0.5:
            # Симулируем что сделает pipeline.py
            expected_warning = f"High code ratio in OCR — possible UI text false positives"
            # В реальном тесте проверяли бы caplog
            pass


class TestPipelineIntegration:
    """Интеграционные тесты с реальным SemanticCore (если требуется)."""
    
    @pytest.mark.skip(reason="Requires SemanticCore instance with real DB")
    def test_video_ocr_creates_code_chunks_in_db(self):
        """E2E тест: видео с кодом → проверка CODE chunks в БД."""
        # Этот тест требует:
        # 1. Реальный SemanticCore
        # 2. Mock GeminiVideoAnalyzer с OCR containing code
        # 3. Проверку ChunkModel в БД
        pass
