# 🔥 Phase 14.0: The Critical Fix — Остановка потери данных

**Дата:** 2025-12-06  
**Статус:** ✅ **ЧАСТИЧНО РЕАЛИЗОВАНО** | ❌ **OCR Markdown parsing НЕ ЗАВЕРШЁН**  
**Зависимости:** Phase 12 (max_output_tokens fix), Phase 2-3 (SmartSplitter + Config)  
**Цель:** Перейти от "1 файл = 1 чанк" к "1 файл = Дерево семантических чанков"

---

## 📋 Оглавление

1. [Проблемы текущей архитектуры](#1-проблемы-текущей-архитектуры)
2. [Что уже исправлено](#2-что-уже-исправлено)
3. [Что НЕ завершено](#3-что-не-завершено)
4. [План завершения Phase 14.0](#4-план-завершения-phase-140)
5. [Реализация — Step by Step](#5-реализация--step-by-step)
6. [Validation & Testing](#6-validation--testing)
7. [Риски и мониторинг](#7-риски-и-мониторинг)

---

## 1. Проблемы текущей архитектуры

### 1.1 Симптомы

При загрузке **3-минутного аудиофайла**:

- ❌ В БД сохраняется **1 чанк** вместо ожидаемых 6-8
- ❌ Транскрипция содержит только **~50 секунд** из 180 секунд
- ❌ Semantic search находит только начало аудио
- ❌ Code в видео-скринкастах не детектится (plain text вместо CODE chunks)

### 1.2 Корневые причины

| Проблема | Файл | Статус |
|----------|------|--------|
| **max_output_tokens=8192** (лимит 8x меньше модели) | `*_analyzer.py` | ✅ **ИСПРАВЛЕНО** (→ 65,536) |
| **1 чанк на медиа** (без SmartSplitter) | `pipeline.py` | ✅ **ИСПРАВЛЕНО** (`_build_media_chunks()`) |
| **OCR uses MediaType.TEXT** (code не детектится) | `pipeline.py:1501` | ❌ **НЕ ИСПРАВЛЕНО** |
| **Промпты не требуют Markdown** | `*_analyzer.py` | ❌ **НЕ ИСПРАВЛЕНО** |

---

## 2. Что уже исправлено ✅

### 2.1 Снятие лимитов max_output_tokens

**Исправлено в:** Phase 12

**Файлы:**
- `semantic_core/infrastructure/gemini/audio_analyzer.py:85`
- `semantic_core/infrastructure/gemini/video_analyzer.py:109`

**Изменение:**
```python
# БЫЛО (ограничение в 8x):
max_output_tokens: int = 8_192

# СТАЛО (полный лимит модели):
max_output_tokens: int = 65_536
```

**Эффект:**
- Gemini может вернуть ~50,000 слов (~130 минут транскрипции)
- Модель больше не обрезает длинные аудио

---

### 2.2 Внедрение SmartSplitter для транскрипций и OCR

**Исправлено в:** Текущая сессия (bugfix video reindex)

**Архитектура:**

#### Метод `_build_media_chunks()` (pipeline.py:1394-1454)

```python
def _build_media_chunks(
    self,
    document: Document,
    media_path: Path,
    chunk_type: ChunkType,
    analysis: Optional[dict],
    fallback_metadata: Optional[dict] = None,
) -> list[Chunk]:
    """Формирует список чанков для медиа: summary + transcript + OCR."""
    
    # 1. Создаём summary chunk (role='summary')
    summary_metadata = self._build_metadata_from_analysis(analysis, media_path)
    summary_metadata["role"] = "summary"
    
    chunks = [
        Chunk(
            content=self._build_content_from_analysis(analysis),
            chunk_index=0,
            chunk_type=chunk_type,
            metadata=summary_metadata,
        )
    ]
    
    # 2. Разбиваем транскрипцию через SmartSplitter
    transcription = analysis.get("transcription")
    if transcription:
        transcript_chunks = self._split_transcription_into_chunks(
            transcription=transcription,
            base_index=len(chunks),
            media_path=media_path,
        )
        chunks.extend(transcript_chunks)
    
    # 3. Разбиваем OCR через SmartSplitter
    ocr_text = analysis.get("ocr_text")
    if ocr_text:
        ocr_chunks = self._split_ocr_into_chunks(
            ocr_text=ocr_text,
            base_index=len(chunks),
            media_path=media_path,
        )
        chunks.extend(ocr_chunks)
    
    return chunks
```

#### Метод `_split_transcription_into_chunks()` (pipeline.py:1456-1482)

```python
def _split_transcription_into_chunks(
    self,
    transcription: str,
    base_index: int,
    media_path: Path,
) -> list[Chunk]:
    """Режет транскрипцию на чанки через SmartSplitter."""
    
    # Создаём временный Document
    temp_doc = Document(
        content=transcription,
        metadata={"source": str(media_path)},
        media_type=MediaType.TEXT,
    )
    
    # Режем через splitter (chunk_size=1800 из конфига)
    split_chunks = self.splitter.split(temp_doc)
    
    # Обогащаем metadata
    for idx, chunk in enumerate(split_chunks):
        meta = dict(chunk.metadata or {})
        meta.setdefault("_original_path", str(media_path))
        meta["role"] = "transcript"
        meta["parent_media_path"] = str(media_path)
        
        chunk.chunk_index = base_index + idx
        chunk.metadata = meta
    
    return split_chunks
```

#### Метод `_split_ocr_into_chunks()` (pipeline.py:1484-1518)

```python
def _split_ocr_into_chunks(
    self,
    ocr_text: str,
    base_index: int,
    media_path: Path,
) -> list[Chunk]:
    """Режет OCR текст на чанки через SmartSplitter."""
    
    temp_doc = Document(
        content=ocr_text,
        metadata={"source": str(media_path)},
        media_type=MediaType.TEXT,  # ❌ ПРОБЛЕМА: должен быть MARKDOWN!
    )
    
    split_chunks = self.splitter.split(temp_doc)
    
    for idx, chunk in enumerate(split_chunks):
        meta = dict(chunk.metadata or {})
        meta.setdefault("_original_path", str(media_path))
        meta["role"] = "ocr"
        meta["parent_media_path"] = str(media_path)
        
        chunk.chunk_index = base_index + idx
        chunk.metadata = meta
    
    return split_chunks
```

**Что работает:**

✅ Транскрипция разбивается на N чанков (не 1 гигантский)  
✅ OCR разбивается на N чанков  
✅ `role="summary"/"transcript"/"ocr"` metadata добавлена  
✅ Chunk indexes последовательны (0, 1, 2, 3...)  
✅ `parent_media_path` связывает чанки с оригинальным файлом

---

### 2.3 Конфигурация chunk_size

**Исправлено в:** Phase 2-3 (SOLID рефакторинг)

**Файлы:**
- `semantic_core/config.py:138-158`
- `semantic_core/cli/context.py:159-163`

**Доказательство:**

```python
# config.py
class SemanticConfig(BaseSettings):
    chunk_size: int = Field(default=1800, ge=500, le=8000)
    code_chunk_size: int = Field(default=2000, ge=500, le=10000)

# cli/context.py
splitter = SmartSplitter(
    parser=parser,
    chunk_size=config.chunk_size,        # ← Читает из semantic.toml
    code_chunk_size=config.code_chunk_size,
)
```

**Эффект:**
- ✅ Пользователь может менять `chunk_size` через `semantic.toml`
- ✅ SmartSplitter использует конфигурированные значения

---

## 3. Что НЕ завершено ❌

### 3.1 OCR Markdown Parsing

**Проблема:** Видео с кодом (скринкасты, туториалы) → код возвращается как plain text.

**Текущее поведение:**

```python
# Gemini OCR output:
ocr_text = """
Function Example
def calculate_total(items):
    return sum(item.price for item in items)
This function iterates...
"""

# SmartSplitter парсит как plain TEXT (media_type=MediaType.TEXT)
# Результат: 1 большой TEXT chunk, CODE BLOCKS НЕ ДЕТЕКТЯТСЯ
```

**Целевое поведение:**

```python
# Gemini OCR output (Markdown):
ocr_text = """
## Function Example

```python
def calculate_total(items):
    return sum(item.price for item in items)
```

This function iterates...
"""

# SmartSplitter парсит как MARKDOWN (media_type=MediaType.MARKDOWN)
# Результат:
# - Chunk 1: ChunkType.TEXT, content="## Function Example"
# - Chunk 2: ChunkType.CODE, language="python", content="def calculate..."
# - Chunk 3: ChunkType.TEXT, content="This function iterates..."
```

**Решение:** Изменить 1 строку в `pipeline.py:1501`

```python
# БЫЛО:
media_type=MediaType.TEXT,

# ДОЛЖНО БЫТЬ:
media_type=MediaType.MARKDOWN,
```

**Приоритет:** 🔴 **P0** (критично для технических видео)

---

### 3.2 Промпты не требуют Markdown

**Проблема:** Текущие промпты не инструктируют Gemini форматировать ответы в Markdown.

**Текущий промпт (audio_analyzer.py:37):**

```python
SYSTEM_PROMPT_TEMPLATE = """You are an audio analyst creating descriptions for semantic search indexing.

Analyze the audio and provide:
1. transcription: Full transcript of the spoken content
2. description: Summary of the audio content (2-4 sentences)
...

Output valid JSON matching the schema.
Answer in {language} language."""
```

**Проблемы:**
- ❌ Нет инструкций по Markdown форматированию
- ❌ Длинные лекции → "простыня текста" без параграфов
- ❌ Code snippets в транскрипциях не выделяются

**Целевой промпт:**

```python
SYSTEM_PROMPT_TEMPLATE = """You are an audio analyst creating descriptions for semantic search indexing.
Response language: {language}

Return a JSON with:

{{
  "description": "Brief 2-3 sentence summary",
  "keywords": ["keyword1", ...],
  "participants": ["Speaker1", ...],
  "action_items": ["Task 1", ...],
  "transcription": "MARKDOWN_FORMATTED_TRANSCRIPT"
}}

CRITICAL INSTRUCTIONS FOR TRANSCRIPTION FIELD:
- Use Markdown formatting (paragraphs, headers, lists)
- Split long monologues into logical paragraphs (every 3-5 sentences)
- Use `## Speaker Name` headers for speaker changes
- Use `**bold**` for emphasis or key terms
- For code snippets, wrap in triple backticks with language:
  ```python
  def example():
      pass
  ```
- DO NOT escape newlines as \\n — use actual line breaks

Example:

## Introduction

The speaker introduces semantic search.

Key points:
- Embeddings capture meaning
- Vector databases enable similarity

## Technical Deep Dive

Here's the similarity formula:

```python
def cosine_similarity(a, b):
    return dot(a, b) / (norm(a) * norm(b))
```

This is fundamental to vector search.
"""
```

**Аналогично для video_analyzer.py — OCR секция:**

```python
CRITICAL INSTRUCTIONS FOR OCR_TEXT FIELD:
- Detect and preserve code blocks from screenshots
- Wrap code in triple backticks with language
- Use `## Slide Title` headers for new slides
- Use bullet points for slide lists
- For UI text (buttons), use plain text

Example OCR:

## Introduction to SOLID

### Single Responsibility Principle

A class should have only one reason to change.

**Example:**

```python
class UserService:
    def validate(self, user): ...
    def save(self, user): ...
```

**Problem:** Mixes validation and persistence.
"""
```

**Приоритет:** 🟡 **P1** (улучшает quality, не критично для работы)

---

## 4. План завершения Phase 14.0

### 4.1 Immediate Actions (этот спринт)

| ID | Задача | Сложность | Приоритет |
|----|--------|-----------|-----------|
| **A1** | Изменить `MediaType.TEXT` → `MARKDOWN` в `pipeline.py:1501` | 5 мин | 🔴 **P0** |
| **A2** | Обновить `SYSTEM_PROMPT_TEMPLATE` в `audio_analyzer.py` | 30 мин | 🟡 **P1** |
| **A3** | Обновить `SYSTEM_PROMPT_TEMPLATE` в `video_analyzer.py` | 30 мин | 🟡 **P1** |
| **A4** | Создать тест `test_media_code_detection.py` | 2 часа | 🟡 **P1** |
| **A5** | Протестировать на реальном видео с кодом | 1 час | 🟢 **P2** |

**Total time:** ~4 часа

---

### 4.2 Validation Criteria (критерии приёмки)

- [ ] **V1:** Видео с Python кодом → хотя бы 1 CODE chunk с `role="ocr"`, `language="python"`
- [ ] **V2:** 5-минутное аудио → минимум 5 чанков с `role="transcript"`
- [ ] **V3:** Chunk indexes последовательны (0, 1, 2, 3...) без пропусков
- [ ] **V4:** Semantic search находит фразу из **середины** 10-минутной лекции
- [ ] **V5:** Транскрипция содержит Markdown параграфы (не простыня текста)

---

### 4.3 Post-Implementation Monitoring

- [ ] **M1:** Собрать статистику `code_ratio` по 100 реальным видео
- [ ] **M2:** Проверить false positives (UI text детектится как CODE)
- [ ] **M3:** Если `code_ratio > 50%`, добавить config toggle `ocr_parser_mode` (Phase 14.3)

**Метрика code_ratio:**

```python
code_chunks = len([c for c in ocr_chunks if c.chunk_type == ChunkType.CODE])
total_ocr_chunks = len(ocr_chunks)
code_ratio = code_chunks / total_ocr_chunks

if code_ratio > 0.5:
    logger.warning(
        "High code ratio — possible UI text false positives",
        code_ratio=f"{code_ratio:.2%}",
        path=str(media_path),
    )
```

---

## 5. Реализация — Step by Step

### 5.1 Action A1: OCR Markdown Parsing

**Файл:** `semantic_core/pipeline.py`  
**Строка:** 1501

**Изменение:**

```python
# BEFORE:
def _split_ocr_into_chunks(...):
    temp_doc = Document(
        content=ocr_text,
        metadata={"source": str(media_path)},
        media_type=MediaType.TEXT,  # ❌ Plain text
    )

# AFTER:
def _split_ocr_into_chunks(...):
    temp_doc = Document(
        content=ocr_text,
        metadata={"source": str(media_path)},
        media_type=MediaType.MARKDOWN,  # ✅ Activates MarkdownNodeParser
    )
```

**Эффект:**
- ✅ Code blocks из Gemini OCR изолируются в отдельные чанки
- ✅ `ChunkType.CODE` с `language="python"` для code chunks
- ✅ Заголовки слайдов сохраняются в `metadata["headers"]`

**Риск:** False positives (UI text как Markdown syntax).  
**Mitigation:** Monitoring `code_ratio` (см. раздел 7).

---

### 5.2 Action A2: Обновить audio_analyzer промпт

**Файл:** `semantic_core/infrastructure/gemini/audio_analyzer.py`  
**Строка:** 37

**Полный новый промпт:**

```python
SYSTEM_PROMPT_TEMPLATE = """You are an audio analyst creating descriptions for semantic search indexing.
Response language: {language}

Return a JSON with the following structure:

{{
  "description": "Brief 2-3 sentence summary of the audio content",
  "keywords": ["keyword1", "keyword2", ...],
  "participants": ["Speaker1", "Speaker2", ...],
  "action_items": ["Task 1", "Task 2", ...],
  "duration_seconds": <number>,
  "transcription": "MARKDOWN_FORMATTED_TRANSCRIPT_HERE"
}}

CRITICAL INSTRUCTIONS FOR TRANSCRIPTION FIELD:
- Use Markdown formatting (paragraphs, headers, lists)
- Split long monologues into logical paragraphs (every 3-5 sentences)
- Use `## Speaker Name` headers for speaker changes
- Use `**bold**` for emphasis or key terms
- Use `> quote` for direct quotations
- For technical content, wrap code snippets in triple backticks with language:
  ```python
  def example():
      pass
  ```
- DO NOT escape newlines as \\n — use actual line breaks inside the JSON string

Example transcription format:

## Introduction

The speaker introduces the topic of semantic search and explains how embeddings work in modern NLP systems.

Key points:
- Embeddings capture semantic meaning
- Vector databases enable similarity search
- Context matters more than keywords

## Technical Deep Dive

Here's how we calculate cosine similarity:

```python
def cosine_similarity(a, b):
    return dot(a, b) / (norm(a) * norm(b))
```

This formula is fundamental to understanding vector search.

## Conclusion

The session concludes with practical examples of implementing semantic search in production systems.
"""
```

---

### 5.3 Action A3: Обновить video_analyzer промпт

**Файл:** `semantic_core/infrastructure/gemini/video_analyzer.py`  
**Строка:** 52

**Дополнительная секция для OCR:**

```python
SYSTEM_PROMPT_TEMPLATE = """You are a video analyst for semantic search indexing.
Response language: {language}

Return a JSON with:

{{
  "description": "What happens in the video (3-5 sentences)",
  "keywords": ["keyword1", ...],
  "transcription": "MARKDOWN_FORMATTED_SPEECH_TRANSCRIPT",
  "ocr_text": "MARKDOWN_FORMATTED_VISUAL_TEXT",
  "duration_seconds": <number>
}}

CRITICAL INSTRUCTIONS FOR OCR_TEXT FIELD:
- Detect and preserve code blocks from screenshots/screencasts
- Wrap code in triple backticks with language:
  ```python
  class Example:
      pass
  ```
- Use `## Slide Title` headers for new slides
- Use bullet points for slide bullet lists:
  - Point 1
  - Point 2
- For UI text (buttons, labels), use plain text
- For diagrams/charts, describe structure in Markdown tables if possible

Example OCR output:

## Introduction to SOLID Principles

### Single Responsibility Principle

A class should have only one reason to change.

**Example:**

```python
class UserService:
    def validate(self, user): ...
    def save(self, user): ...
```

**Problem:** Mixes validation and persistence.

## Better Design

Split into two classes:

```python
class UserValidator:
    def validate(self, user): ...

class UserRepository:
    def save(self, user): ...
```
"""
```

---

### 5.4 Action A4: Интеграционный тест

**Файл:** `tests/integration/test_media_code_detection.py`

```python
import pytest
from pathlib import Path
from semantic_core.domain import ChunkType
from semantic_core.infrastructure.storage.peewee.models import ChunkModel


@pytest.fixture
def sample_ocr_with_code():
    """OCR text with Python code block."""
    return """
## Function Example

```python
def calculate_total(items):
    return sum(item.price for item in items)
```

This function iterates over items and sums their prices.
"""


def test_ocr_detects_code_blocks(core, tmp_path):
    """Проверяет, что OCR с кодом создаёт CODE chunks."""
    from semantic_core.domain import Document, MediaType, Chunk
    
    # Симулируем OCR chunking напрямую
    ocr_text = """
## Example

```python
def hello():
    print("world")
```
"""
    
    temp_doc = Document(
        content=ocr_text,
        metadata={"source": "test.mp4"},
        media_type=MediaType.MARKDOWN,  # ← Ключевое изменение
    )
    
    chunks = core.splitter.split(temp_doc)
    
    # Assertions
    code_chunks = [c for c in chunks if c.chunk_type == ChunkType.CODE]
    assert len(code_chunks) == 1, "Expected exactly 1 CODE chunk"
    assert code_chunks[0].language == "python"
    assert "def hello():" in code_chunks[0].content


def test_video_with_code_creates_ocr_code_chunks_e2e(core, tmp_path):
    """E2E тест: видео с кодом → проверка БД."""
    # NOTE: Требует реального видео или mock GeminiVideoAnalyzer
    # Для полноты можно добавить mock, который возвращает OCR с кодом
    pass  # TODO: Implement with mocked analyzer
```

---

## 6. Validation & Testing

### 6.1 Manual Testing Workflow

**Step 1:** Индексируем видео с кодом

```bash
# Используем реальное видео (Python tutorial screencast)
semantic ingest examples/test_assets/python_tutorial.mp4
```

**Step 2:** Проверяем БД

```python
from semantic_core.infrastructure.storage.peewee.models import ChunkModel

chunks = list(ChunkModel.select().order_by(ChunkModel.chunk_index))

for chunk in chunks:
    print(f"Index: {chunk.chunk_index}, Type: {chunk.chunk_type}, Role: {chunk.metadata.get('role')}")
    if chunk.chunk_type == "code":
        print(f"  Language: {chunk.language}")
        print(f"  Content: {chunk.content[:100]}...")
```

**Ожидаемый output:**

```
Index: 0, Type: video_ref, Role: summary
Index: 1, Type: text, Role: transcript
Index: 2, Type: text, Role: transcript
Index: 3, Type: text, Role: ocr
Index: 4, Type: code, Role: ocr
  Language: python
  Content: def calculate_total(items):
    return sum(item.price for item in items)
Index: 5, Type: text, Role: ocr
```

---

### 6.2 Automated Testing

**Unit tests:**

```bash
pytest tests/unit/core/test_pipeline.py::test_split_ocr_into_chunks -v
```

**Integration tests:**

```bash
pytest tests/integration/test_media_code_detection.py -v
```

**E2E tests (с реальным Gemini API):**

```bash
pytest tests/e2e/test_video_analysis.py::test_video_with_code_creates_code_chunks -v
```

---

## 7. Риски и мониторинг

### 7.1 Риск: False Positives в OCR

**Сценарий:** UI text детектится как Markdown code blocks.

**Пример:**

```
# OCR from mobile app screenshot:
Settings
  > Dark Mode
  > Font Size: Large
  > Language: English

# MarkdownNodeParser может распознать ">" как quote block
# и создать лишний chunk
```

**Detection:**

Добавляем warning в `_split_ocr_into_chunks()`:

```python
# После split_chunks:
code_chunks = [c for c in split_chunks if c.chunk_type == ChunkType.CODE]
code_ratio = len(code_chunks) / len(split_chunks) if split_chunks else 0

if code_ratio > 0.5:
    logger.warning(
        "High code ratio in OCR — possible UI text false positives",
        code_ratio=f"{code_ratio:.2%}",
        media_path=str(media_path),
    )
```

**Mitigation (Phase 14.3):**

Добавить config field:

```toml
# semantic.toml
[processing.media]
ocr_parser_mode = "markdown"  # or "plain"
```

---

### 7.2 Риск: Gemini игнорирует Markdown инструкции

**Сценарий:** Модель возвращает plain text несмотря на промпт.

**Detection:**

Проверяем наличие Markdown в транскрипциях:

```python
# В audio_analyzer.py после получения ответа:
if "```" not in result["transcription"] and len(result["transcription"]) > 5000:
    logger.warning(
        "Long transcription without code blocks — model might ignore Markdown instructions",
        length=len(result["transcription"]),
    )
```

**Mitigation:**

- Добавить few-shot examples в промпт
- Использовать `gemini-2.5-flash` вместо `flash-lite` (лучше instruction following)

---

### 7.3 Success Metrics

**После завершения Phase 14.0:**

| Метрика | Текущее значение | Целевое | Статус |
|---------|------------------|---------|--------|
| Avg chunks per 5-min audio | 1 | 5-7 | ❌ |
| Code detection rate (tech videos) | 0% | >80% | ❌ |
| Search recall @10 (middle of audio) | 15% | >90% | ❌ |
| Chunk index errors | 0% | 0% | ✅ |

**Целевые значения после реализации:**

| Метрика | Целевое |
|---------|---------|
| Avg chunks per 5-min audio | ✅ 5-7 |
| Code detection rate (tech videos) | ✅ >80% |
| Search recall @10 (middle of audio) | ✅ >90% |

---

## 8. Roadmap — Next Steps

После завершения Phase 14.0:

**Phase 14.1: ProcessingStep Abstraction** (3-4 недели)
- Рефакторинг `_build_media_chunks()` → step-based system
- `SummaryStep`, `TranscriptionStep`, `OCRStep`
- `register_step()` для кастомизации
- `rerun_step()` для идемпотентности

**Phase 14.2: Aggregation & Service Layer** (2 недели)
- `MediaService.get_media_details(doc_id)` — сборка чанков
- Flask UI `/media/<id>` с timeline
- Search filters по `role`

**Phase 14.3: User Flexibility** (2 недели)
- Конфигурируемые промпты через `semantic.toml`
- `ocr_parser_mode` config toggle
- Per-role chunk sizing

---

**End of Phase 14.0 Plan**  
**Status:** Ready for immediate implementation  
**Estimated time:** 4 hours  
**Risk level:** LOW (minimal code changes, backward compatible)
