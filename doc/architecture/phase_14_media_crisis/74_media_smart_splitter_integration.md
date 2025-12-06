# 74. Media Smart Splitter Integration

> **Фаза:** 14.0  
> **Статус:** ✅ РЕАЛИЗОВАНО  
> **Проблема:** OCR-текст из видео попадал в SimpleSplitter, теряя структуру кода  
> **Решение:** Интеграция SmartSplitter + MarkdownNodeParser для изоляции code blocks

---

## 🎯 Контекст проблемы

### Как было раньше

До Phase 14.0 медиа-контент обрабатывался так:

```python
# pipeline.py (старая версия)
def _build_media_chunks(self, doc: Document, media_result: MediaAnalysisResult):
    # Gemini Vision/Audio → text
    ocr_text = media_result.transcript or media_result.ocr_text
    
    # ❌ SimpleSplitter уничтожал структуру!
    chunks = SimpleSplitter(chunk_size=1000).split(ocr_text)
```

**Проблемы:**

1. **Код терялся в тексте**  
   OCR скринкаста с Python кодом → один большой TEXT chunk

2. **Нет изоляции кода**  
   ```python
   class SingleResponsibility:  # ← смешано с пояснениями
       def __init__(self):
           """Каждый класс должен..."""
   ```

3. **Неоптимальный embeddings**  
   Эмбеддинги смешивали семантику кода и текста

---

## 🧩 Архитектурное решение

### SmartSplitter уже был готов!

Оказалось, SmartSplitter был создан в Phase 4 именно для этого:

```python
# processing/splitters/smart_splitter.py
class SmartSplitter:
    def __init__(
        self,
        chunk_size: int = 1800,
        code_chunk_size: int = 2000,  # ← для code blocks
        parser: Optional[BaseParser] = None
    ):
        self.parser = parser or MarkdownNodeParser()  # ← AST парсинг!
```

**Возможности:**

- AST-анализ Markdown через `MarkdownNodeParser`
- Детекция code fences: ` ```python ... ``` `
- Отдельные chunks для `ChunkType.CODE`
- Сохранение языка в `metadata['language']`

---

## 🔧 Что было сделано

### 1. Gemini должен генерировать Markdown!

**Проблема:** Gemini возвращал plain text, а не Markdown  
**Решение:** Обновили промпты в analyzers

#### Audio Analyzer

```python
# infrastructure/gemini/audio_analyzer.py
SYSTEM_PROMPT_TEMPLATE = """
You are an expert transcriptionist...

**Output Format:**
- Use `## Speaker Name` headers when speakers change
- Split long monologues into paragraphs (every 3-5 sentences)
- Wrap code snippets in triple backticks with language:
  ```python
  def example():
      pass
  ```

Example:
## Narrator
This is the introduction to SOLID principles...

## Instructor
Let's look at the code:
```python
class SRP:
    pass
```
"""
```

#### Video Analyzer

```python
# infrastructure/gemini/video_analyzer.py
SYSTEM_PROMPT_TEMPLATE = """
You are an OCR expert analyzing video frames...

**Output Format:**
- Detect and preserve code blocks from screenshots
- Use `## Slide Title` headers for new slides
- Wrap code in triple backticks with language:
  ```javascript
  const obj = { key: "value" };
  ```

Example:
## Introduction
Welcome to the tutorial...

## Code Example
```python
# SOLID: Single Responsibility Principle
class UserManager:
    def save_user(self, user):
        pass
```
"""
```

**Что изменилось:**

- ✅ Явные инструкции для Markdown-форматирования
- ✅ Примеры с code blocks в промптах
- ✅ Разделение на параграфы/слайды через `##` заголовки

---

### 2. Pipeline уже использовал SmartSplitter!

Оказалось, код уже был готов:

```python
# pipeline.py:1480-1530
def _split_ocr_into_chunks(self, ocr_text: str, doc: Document):
    """Split OCR/transcription text into semantic chunks."""
    
    # SmartSplitter уже инициализирован в CLI!
    # cli/commands/ingest.py → semantic_core.splitter = SmartSplitter()
    splitter = self._splitter  # MarkdownNodeParser внутри!
    
    # Создаём временный Document
    temp_doc = Document(
        content=ocr_text,
        media_type=MediaType.TEXT,  # ← parser set in SmartSplitter init
        metadata=doc.metadata
    )
    
    # SmartSplitter сам найдёт code blocks через AST
    ocr_chunks = splitter.split_document(temp_doc)
    
    # ✅ Получаем ChunkType.CODE chunks автоматически!
    return ocr_chunks
```

**Важно:** `Document.media_type` НЕ влияет на parser!  
Parser выбирается в `SmartSplitter.__init__(parser=MarkdownNodeParser())`

---

### 3. Добавили мониторинг code_ratio

Чтобы отловить false positives (UI текст распознан как код):

```python
# pipeline.py (после split_chunks)
code_chunks = [c for c in ocr_chunks if c.chunk_type == ChunkType.CODE]
code_ratio = len(code_chunks) / len(ocr_chunks) if ocr_chunks else 0

if code_ratio > 0.5:
    logger.warning(
        "High code ratio in OCR — possible UI text false positives",
        code_chunks=len(code_chunks),
        total_chunks=len(ocr_chunks),
        ratio=f"{code_ratio:.1%}",
        doc_id=doc.id,
    )
```

**Зачем:**

- Предупреждение если >50% chunks — CODE
- Может означать, что Gemini обернул UI кнопки в ` ``` `
- Позволяет проверить и настроить промпты

---

## 🧪 Тестирование

Созданы integration-тесты:

```python
# tests/integration/test_media_code_detection.py
class TestOCRCodeDetection:
    def test_ocr_with_python_code_creates_code_chunk(self, smart_splitter):
        """OCR with Python code → CODE chunk"""
        ocr_text = """
## SOLID Principles
Let's look at the code:
```python
class SRP:
    def save_user(self):
        pass
```
"""
        chunks = smart_splitter.split_document(
            Document(content=ocr_text, media_type=MediaType.TEXT)
        )
        
        code_chunks = [c for c in chunks if c.chunk_type == ChunkType.CODE]
        
        assert len(code_chunks) == 1
        assert "class SRP" in code_chunks[0].content
        assert code_chunks[0].metadata["language"] == "python"
```

**Результаты:** 7 passed, 2 skipped ✅

Тесты покрывают:

- ✅ Python code detection
- ✅ JavaScript code detection
- ✅ Multiple code blocks
- ✅ Header preservation
- ✅ False positives (UI text NOT as code)
- ✅ Code ratio warning

---

## 🎓 Архитектурные находки

### MediaType vs Parser Selection

**Ошибка:** Попытка добавить `MediaType.MARKDOWN`

```python
# ❌ НЕ РАБОТАЕТ
temp_doc = Document(
    content=ocr_text,
    media_type=MediaType.MARKDOWN  # ← AttributeError!
)
```

**Почему:**

`MediaType` — это enum для **категоризации документов**, а не директива парсера!

```python
class MediaType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    # MARKDOWN нет и не нужен!
```

**Правильно:**

Parser выбирается в `SmartSplitter.__init__()`:

```python
# cli/commands/ingest.py
smart_splitter = SmartSplitter(
    chunk_size=config.chunk_size,
    code_chunk_size=config.code_chunk_size,
    parser=MarkdownNodeParser()  # ← здесь выбор!
)

semantic_core = SemanticCore(
    storage=storage,
    splitter=smart_splitter  # ← используется для всех документов
)
```

---

### SmartSplitter behaviour is init-time, not runtime

**Ключевая концепция:**

SmartSplitter анализирует ВСЕ документы одним parser'ом:

```python
class SmartSplitter:
    def __init__(self, parser=MarkdownNodeParser()):
        self.parser = parser  # ← фиксируется навсегда
    
    def split_document(self, doc: Document):
        # ❌ НЕ смотрит на doc.media_type!
        # ✅ Всегда использует self.parser
        return self.parser.parse(doc.content)
```

**Вывод:** `Document.media_type` нужен для:

- Фильтрации в поиске (`media_type='video'`)
- Показа иконок в UI
- Статистики

НО НЕ для выбора parser'а!

---

### Code Detection уже работал

**Surprise:** Code isolation уже был реализован в Phase 4!

```python
# processing/parsers/markdown_node_parser.py
class MarkdownNodeParser:
    def parse(self, text: str):
        # markdown-it-py → AST
        tokens = self.md.parse(text)
        
        for token in tokens:
            if token.type == "fence":  # ← ```python
                yield Chunk(
                    content=token.content,
                    chunk_type=ChunkType.CODE,  # ← уже было!
                    metadata={"language": token.info}
                )
```

**Что было нужно:**

- ✅ Gemini должен ГЕНЕРИРОВАТЬ Markdown (промпты)
- ✅ Pipeline должен ИСПОЛЬЗОВАТЬ SmartSplitter (уже было!)
- ✅ Тесты должны ВАЛИДИРОВАТЬ работу (написали)

---

## 📊 Результаты Phase 14.0

### Что работает

✅ **Python code isolation:**

```markdown
## Tutorial
Here's the code:
```python
def factorial(n):
    return 1 if n == 0 else n * factorial(n - 1)
```
```

→ 1 CODE chunk (python) + 1 TEXT chunk (Tutorial)

✅ **JavaScript code detection:**

```markdown
## Example
```javascript
const greet = () => console.log("Hello");
```
```

→ 1 CODE chunk (javascript)

✅ **Multiple code blocks:**

```markdown
## Python
```python
x = 5
```

## JavaScript
```javascript
let y = 10;
```
```

→ 2 CODE chunks (разные языки)

✅ **False positive prevention:**

```markdown
Click the "Submit" button to continue.
```

→ 1 TEXT chunk (не CODE!)

---

### Метрики

**До Phase 14.0:**

- OCR text → SimpleSplitter → всё TEXT chunks
- Код терялся внутри больших блоков
- Нет языковой метаданных

**После Phase 14.0:**

- OCR text → SmartSplitter → TEXT + CODE chunks
- Код изолирован в отдельные chunks
- `metadata['language']` для каждого code block
- Мониторинг через `code_ratio` warning

---

## 🔮 Phase 14.1 Preview

**Текущая проблема:** Hardcoded steps в `_build_media_chunks()`

```python
# pipeline.py (сейчас)
def _build_media_chunks(self, doc, media_result):
    # Step 1: Summary
    summary_chunk = self._create_summary_chunk(...)
    
    # Step 2: Transcription
    transcript_chunk = self._create_transcript_chunk(...)
    
    # Step 3: OCR split
    ocr_chunks = self._split_ocr_into_chunks(...)
    
    return [summary_chunk, transcript_chunk, *ocr_chunks]
```

**Phase 14.1:** ProcessingStep abstraction

```python
# Будущее
class BaseProcessingStep(ABC):
    @abstractmethod
    def execute(self, context: MediaContext) -> List[Chunk]:
        pass

steps = [
    SummaryStep(),
    TranscriptionStep(),
    OCRStep(splitter=SmartSplitter())
]

chunks = []
for step in steps:
    chunks.extend(step.execute(context))
```

**Преимущества:**

- Гибкая конфигурация (отключить summary, оставить OCR)
- Unit-тестирование каждого step отдельно
- Новые steps без изменения pipeline

---

## 🎯 Takeaways

1. **SmartSplitter универсален**  
   Работает для text, markdown, OCR — один parser на всех

2. **Prompts > Code**  
   Вместо добавления MediaType.MARKDOWN — обновили промпты Gemini

3. **Parser выбирается один раз**  
   При инициализации SmartSplitter, не при каждом split_document()

4. **Code detection был готов**  
   Phase 4 уже реализовал изоляцию кода, нужно было активировать

5. **Мониторинг критичен**  
   `code_ratio` warning помогает отловить false positives

---

## 📚 Связанные статьи

- [15. Smart Parsing Architecture](15_smart_parsing.md) — AST парсинг и ChunkType
- [16. Smart Splitting Strategy](16_smart_splitting.md) — изоляция кода
- [26. Gemini Vision Integration](26_gemini_vision_integration.md) — OCR через Vision API
- [30. Audio Analysis Architecture](30_audio_analysis_architecture.md) — транскрипция
- [31. Video Multimodal Analysis](31_video_multimodal_analysis.md) — кадры + аудио

---

**Следующая статья:** [Phase 14.1: ProcessingStep Abstraction](75_processing_step_abstraction.md) *(в разработке)*

---

**← [Вернуться в оглавление](00_overview.md)**
