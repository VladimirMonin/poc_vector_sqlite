# Debug Observatory: Концептуальный дизайн

**Дата:** 10 декабря 2025  
**Статус:** Концепция  
**Цель:** Визуализация внутренних процессов pipeline для отладки и аудита

---

## 🎯 Что это такое?

**Debug Observatory** — это **паттерн Observability-Driven Development**, который позволяет:

1. **Видеть** промежуточные состояния обработки данных
2. **Сохранять** артефакты для сравнения между запусками
3. **Отлаживать** проблемы через визуализацию pipeline

---

## 🏗️ Архитектура: 3 компонента

```
┌─────────────────────────────────────────────────────────────┐
│                    Debug Observatory                         │
└─────────────────────────────────────────────────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
    ┌──────────┐        ┌──────────┐        ┌──────────┐
    │   CLI    │        │  Tests   │        │  Files   │
    │ Command  │        │Inspector │        │Artifacts │
    └──────────┘        └──────────┘        └──────────┘
         │                    │                    │
         │              Uses  │              Saves │
         ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│              PipelineInspector (Core Engine)                 │
│  • Перехватывает вызовы split(), embed(), analyze()         │
│  • Записывает промежуточные данные в InspectionReport       │
│  • Экспортирует в Markdown / JSON / Console                  │
└─────────────────────────────────────────────────────────────┘
```

### Компонент 1: **PipelineInspector** (ядро)

**Уже реализован** в `tests/e2e/audit/conftest.py`

**Что делает:**

- Оборачивает `SemanticCore` и перехватывает данные
- Записывает промежуточные состояния в `InspectionReport`
- Аккумулирует данные в `AuditCollector`

**Ключевой метод:**

```python
def ingest_with_inspection(self, document: Document) -> Document:
    # 1. Split - разбивка на чанки
    chunks = self.core.splitter.split(document)
    
    # 2. Context - формирование текста для embedder
    for chunk in chunks:
        context_text = self.core.context_strategy.form_vector_text(chunk, document)
        
        # 🔍 ИНСПЕКЦИЯ - сохраняем промежуточные данные
        inspection = ChunkInspection(
            content=chunk.content,           # Исходный контент
            context_text=context_text,       # Что пойдёт в embedder
            headers=chunk.metadata.get("headers", []),
            language=chunk.language,
        )
    
    # 3. Embed - получаем векторы
    embeddings = self.core.embedder.embed_documents(vector_texts)
    
    # 🔍 ИНСПЕКЦИЯ - добавляем вектора
    for embedding, inspection in zip(embeddings, inspections):
        inspection.embedding_preview = embedding[:20]  # Первые 20 значений
        inspection.embedding_dimension = len(embedding)
    
    # 4. Save - сохраняем в БД (как обычно)
    return self.core.index.add_document(document, enriched_chunks)
```

### Компонент 2: **E2E Tests** (существующие)

**Уже реализован** в `tests/e2e/audit/test_*.py`

**Как работает:**

```python
# tests/e2e/audit/test_chunking_audit.py
def test_structured_markdown_chunking(pipeline_inspector, test_assets_path):
    """Визуальная проверка чанкинга Markdown."""
    
    # 1. Загружаем файл
    md_file = test_assets_path / "mixed_content_example.md"
    doc = Document(content=md_file.read_text())
    
    # 2. Индексируем ЧЕРЕЗ ИНСПЕКТОР
    saved = pipeline_inspector.ingest_with_inspection(doc, mode="sync")
    
    # 3. Данные автоматически записаны в AuditCollector
    # 4. В конце сессии pytest создаёт Markdown отчёты
```

**Что происходит:**

1. Pytest запускает тесты
2. `PipelineInspector` перехватывает данные
3. `AuditCollector` накапливает их в памяти
4. В конце сессии (`pytest_sessionfinish`) генерируются файлы:

   ```
   tests/audit_reports/2025-12-10_15-30-45/
   ├── 01_chunking_audit.md    # 173 KB - все чанки с векторами
   ├── 02_media_audit.md       # 37 KB - медиа с промптами
   └── 03_search_audit.md      # 98 KB - поисковые запросы
   ```

### Компонент 3: **CLI Command** (планируется)

**Новая команда:** `semantic inspect <file>`

**Режимы работы:**

#### Режим A: Console Output (Rich TUI)

```bash
semantic inspect docs/example.md --mode=console
```

**Вывод в терминал:**

```
╭─────────────────────────────────────────────────────────╮
│  📄 File: docs/example.md                               │
│  Size: 5.2 KB | Chunks: 7 | Embeddings: 7               │
╰─────────────────────────────────────────────────────────╯

┌─ Step 1: Parsing ─────────────────────────────────────┐
│ Parser: MarkdownNodeParser                             │
│ Segments: 12 (7 text, 3 code, 2 images)               │
│ Duration: 12ms                                         │
└────────────────────────────────────────────────────────┘

┌─ Step 2: Splitting ───────────────────────────────────┐
│ Splitter: SmartSplitter (chunk_size=512, overlap=50)  │
│                                                        │
│ Chunk #1 [TEXT] 📝                                     │
│ ├─ Headers: Introduction > Overview                   │
│ ├─ Size: 487 chars                                    │
│ └─ Content: "Semantic search is a technique..."       │
│                                                        │
│ Chunk #2 [CODE] 💻                                     │
│ ├─ Language: python                                   │
│ ├─ Size: 324 chars                                    │
│ └─ Content: "from semantic_core import..."            │
│                                                        │
│ [+] Show 5 more chunks                                │
└────────────────────────────────────────────────────────┘

┌─ Step 3: Context Formation ───────────────────────────┐
│ Strategy: HierarchicalContextStrategy                  │
│                                                        │
│ Chunk #1 Vector Context:                              │
│ ┌────────────────────────────────────────────────┐   │
│ │ Document: example.md                            │   │
│ │ Path: Introduction > Overview                   │   │
│ │                                                 │   │
│ │ Semantic search is a technique...               │   │
│ └────────────────────────────────────────────────┘   │
│                                                        │
│ [+] Show context for 6 more chunks                    │
└────────────────────────────────────────────────────────┘

┌─ Step 4: Embedding ───────────────────────────────────┐
│ Model: gemini-embedding-001                            │
│ Batch size: 7 texts                                    │
│ Dimension: 768                                         │
│ Duration: 1.2s                                         │
│                                                        │
│ Chunk #1 Embedding (first 10 values):                 │
│ [-0.053591, -0.004871, 0.028734, -0.019283, ...]     │
│                                                        │
│ [+] Show embeddings for 6 more chunks                 │
└────────────────────────────────────────────────────────┘

┌─ Step 5: Storage ─────────────────────────────────────┐
│ Store: PeeweeVectorStore                               │
│ Database: semantic.db                                  │
│ Document ID: 42                                        │
│ Chunks saved: 7                                        │
│ Duration: 45ms                                         │
└────────────────────────────────────────────────────────┘

╭─────────────────────────────────────────────────────────╮
│  ✅ Processing Complete                                 │
│  Total time: 1.3s                                       │
╰─────────────────────────────────────────────────────────╯
```

#### Режим B: Save Artifacts (JSON/Markdown)

```bash
semantic inspect docs/example.md --save-artifacts
```

**Создаёт папку:**

```
inspection_artifacts/2025-12-10_15-30-45/
├── example_md_inspection.json    # Полный дамп данных
├── example_md_report.md          # Красивый отчёт (как в Phase 13)
└── example_md_chunks/            # Каждый чанк отдельно
    ├── chunk_001_text.json
    ├── chunk_002_code.json
    ├── chunk_003_image_ref.json
    └── ...
```

**Содержимое `example_md_inspection.json`:**

```json
{
  "file_path": "docs/example.md",
  "processing_timestamp": "2025-12-10T15:30:45.123456",
  "total_duration_ms": 1347.2,
  "steps": [
    {
      "step_name": "parsing",
      "duration_ms": 12.3,
      "parser": "MarkdownNodeParser",
      "segments_count": 12
    },
    {
      "step_name": "splitting",
      "duration_ms": 8.7,
      "splitter": "SmartSplitter",
      "config": {
        "chunk_size": 512,
        "overlap": 50
      },
      "chunks_count": 7
    }
  ],
  "chunks": [
    {
      "chunk_id": 1,
      "chunk_type": "text",
      "content": "Semantic search is a technique...",
      "size": 487,
      "headers": ["Introduction", "Overview"],
      "language": null,
      "context_text": "Document: example.md\nPath: Introduction > Overview\n\nSemantic search...",
      "embedding": [-0.053591, -0.004871, ...],  // Полный вектор 768D
      "embedding_dimension": 768
    },
    {
      "chunk_id": 2,
      "chunk_type": "code",
      "content": "from semantic_core import SemanticCore\n...",
      "size": 324,
      "language": "python",
      "context_text": "...",
      "embedding": [...],
      "embedding_dimension": 768
    }
  ]
}
```

#### Режим C: Interactive Step-by-Step

```bash
semantic inspect docs/example.md --interactive
```

**Интерактивный режим:**

```
╭─────────────────────────────────────────────────────────╮
│  🔍 Interactive Inspection Mode                         │
│  File: docs/example.md                                  │
╰─────────────────────────────────────────────────────────╯

[1/5] Parsing...
✅ Done (12ms) - 12 segments found

Press ENTER to continue or 's' to save current state...
> s

Saved: inspection_artifacts/.../step_1_parsing.json

[2/5] Splitting...
✅ Done (8ms) - 7 chunks created

┌─ Chunk Preview ───────────────────────────────────────┐
│ Chunk #1 [TEXT] 📝                                     │
│ Headers: Introduction > Overview                       │
│ Size: 487 chars                                        │
│                                                        │
│ "Semantic search is a technique that understands       │
│  the meaning of your query..."                        │
└────────────────────────────────────────────────────────┘

Press ENTER to continue, 'p' for full preview, 's' to save...
> p

[Full content shown in pager...]

Press ENTER to continue...

[3/5] Forming context...
✅ Done (5ms)

┌─ Vector Context for Chunk #1 ─────────────────────────┐
│ Document: example.md                                   │
│ Path: Introduction > Overview                          │
│                                                        │
│ Semantic search is a technique...                      │
└────────────────────────────────────────────────────────┘

Press ENTER to continue...

[4/5] Generating embeddings...
⏳ Calling Gemini API...
✅ Done (1.2s) - 7 vectors (768D each)

┌─ Embedding Preview (Chunk #1) ────────────────────────┐
│ Dimension: 768                                         │
│ First 20 values:                                       │
│ [-0.053591, -0.004871, 0.028734, -0.019283, ...]     │
│                                                        │
│ Norm: 1.0000 (normalized ✓)                          │
└────────────────────────────────────────────────────────┘

Press ENTER to continue...

[5/5] Saving to database...
✅ Done (45ms) - Document ID: 42

╭─────────────────────────────────────────────────────────╮
│  ✅ Processing Complete                                 │
│  Total time: 1.3s                                       │
│                                                         │
│  Artifacts saved to:                                    │
│  inspection_artifacts/2025-12-10_15-30-45/             │
╰─────────────────────────────────────────────────────────╯
```

---

## 🔄 Интеграция с тестами

### Вариант 1: Тесты используют Inspector (текущая архитектура)

**Текущая реализация Phase 13:**

```python
# tests/e2e/audit/conftest.py

@pytest.fixture(scope="session")
def audit_collector(audit_session: Path) -> AuditCollector:
    """Глобальный коллектор на всю сессию pytest."""
    collector = AuditCollector(session_path=audit_session)
    yield collector
    # 🔑 В конце сессии сохраняем отчёты
    collector.save_all_reports()


@pytest.fixture
def pipeline_inspector(semantic_core, audit_collector) -> PipelineInspector:
    """PipelineInspector для каждого теста."""
    return PipelineInspector(core=semantic_core, collector=audit_collector)


# tests/e2e/audit/test_chunking_audit.py

def test_markdown_chunking(pipeline_inspector):
    """Тест чанкинга Markdown."""
    doc = Document(content="# Hello\n\nWorld")
    
    # Используем ИНСПЕКТОР вместо core.index.add_document()
    saved = pipeline_inspector.ingest_with_inspection(doc)
    
    # Данные автоматически записаны в collector
    # Ничего руками сохранять не нужно!
```

**Что происходит:**

1. **Запуск теста:** `pytest tests/e2e/audit/`
2. **Setup:** `audit_collector` создаёт папку `tests/audit_reports/2025-12-10_15-30/`
3. **Тест:** Вызывает `pipeline_inspector.ingest_with_inspection(doc)`
4. **Inspector:** Перехватывает данные и пишет в `collector.reports`
5. **Teardown (session):** `collector.save_all_reports()` создаёт файлы:
   - `01_chunking_audit.md`
   - `02_media_audit.md`
   - `03_search_audit.md`

**Преимущества:**

- ✅ Тесты и инспектор — одна сущность
- ✅ Автоматическая генерация отчётов
- ✅ Zero duplication — один код для тестов и аудита

### Вариант 2: Inspector дополняет тесты (планируется)

**Новая возможность:**

```python
# tests/integration/test_full_pipeline.py

def test_full_pipeline_integration(semantic_core):
    """Обычный интеграционный тест."""
    doc = Document(content="Test")
    
    # Обычная индексация БЕЗ инспектора
    saved = semantic_core.index.add_document(doc)
    
    # Проверки
    assert saved.id is not None
```

**Но можно запустить с инспектором:**

```bash
# Обычный запуск - быстрые тесты
pytest tests/integration/

# Запуск с аудитом - генерация отчётов
pytest tests/integration/ --enable-inspector --save-artifacts
```

**Как это работает:**

```python
# tests/conftest.py

def pytest_addoption(parser):
    parser.addoption(
        "--enable-inspector",
        action="store_true",
        help="Enable PipelineInspector for all tests"
    )
    parser.addoption(
        "--save-artifacts",
        action="store_true",
        help="Save inspection artifacts"
    )


@pytest.fixture
def semantic_core_with_inspector(request, semantic_core, audit_collector):
    """Условно включаем инспектор."""
    if request.config.getoption("--enable-inspector"):
        # Оборачиваем SemanticCore в PipelineInspector
        return PipelineInspector(core=semantic_core, collector=audit_collector)
    else:
        # Возвращаем обычный core
        return semantic_core
```

**Преимущества:**

- ✅ Обычные тесты не замедляются
- ✅ Аудит включается по требованию
- ✅ Один код для обоих режимов

---

## 📦 Что мы получим?

### Уровень 1: **Консольный вывод** (Rich TUI)

**Когда использовать:** Быстрая отладка, понимание что происходит

**Команда:**

```bash
semantic inspect docs/example.md
```

**Что видим:**

- Красивые Rich панели в терминале
- Пошаговое отображение pipeline
- Превью данных (content, context, embeddings)
- Время выполнения каждого шага

**Сохраняется:** Ничего (только вывод в консоль)

### Уровень 2: **Файловые артефакты** (JSON + Markdown)

**Когда использовать:** Детальный анализ, сравнение между запусками

**Команда:**

```bash
semantic inspect docs/example.md --save-artifacts
```

**Что получаем:**

```
inspection_artifacts/2025-12-10_15-30-45/
├── example_md_inspection.json    # Полный дамп (chunks, embeddings, timings)
├── example_md_report.md          # Markdown отчёт (как в Phase 13)
└── example_md_chunks/            # Опционально: каждый чанк отдельным файлом
    ├── chunk_001.json
    ├── chunk_002.json
    └── ...
```

**JSON файл** — для программной обработки:

- Все чанки с полными векторами (768D)
- Метаданные, таймеры, конфигурация
- Можно загрузить и сравнить с другими запусками

**Markdown отчёт** — для человека:

- Читаемое форматирование
- Превью векторов (первые 20 значений)
- Syntax highlighting для кода
- Таблицы с метриками

### Уровень 3: **E2E Test Reports** (существующие)

**Когда использовать:** Комплексный аудит всей системы

**Команда:**

```bash
pytest tests/e2e/audit/ -v -s
```

**Что получаем:**

```
tests/audit_reports/2025-12-10_15-30-45/
├── 01_chunking_audit.md    # 173 KB - ВСЕ файлы, ВСЕ чанки
├── 02_media_audit.md       # 37 KB - 6 медиа с промптами и ответами
└── 03_search_audit.md      # 98 KB - 14 поисковых запросов
```

**Отличие от Level 2:**

- **Множественные файлы** в одном отчёте
- **Реальные Gemini API вызовы** (промпты, ответы, таймеры)
- **Поисковые запросы** с результатами
- **Агрегированные метрики** (средние времена, размеры, counts)

---

## 🎨 Визуальное сравнение уровней

### Level 1: Console (semantic inspect)

```
┌────────────────────────┐
│  📄 example.md         │  ← Rich Panel в терминале
├────────────────────────┤
│ Step 1: Parsing        │  ← Прогресс в реальном времени
│ ✅ 12ms - 7 chunks     │
└────────────────────────┘

💾 Ничего не сохраняется
```

### Level 2: Artifacts (semantic inspect --save-artifacts)

```
┌────────────────────────┐
│  📄 example.md         │  ← Rich Panel в терминале
├────────────────────────┤
│ Step 1: Parsing        │  
│ ✅ 12ms - 7 chunks     │
└────────────────────────┘

💾 Сохраняет:
   inspection_artifacts/2025-12-10_15-30/
   ├── example_md_inspection.json   ← Полный дамп
   └── example_md_report.md         ← Markdown отчёт
```

### Level 3: E2E Tests (pytest tests/e2e/audit/)

```
pytest tests/e2e/audit/ -v

test_simple_text_chunking PASSED
test_markdown_chunking PASSED
test_media_enrichment PASSED   ← Реальные Gemini API вызовы
test_search_quality PASSED

💾 Сохраняет:
   tests/audit_reports/2025-12-10_15-30/
   ├── 01_chunking_audit.md    ← 13 файлов, 127 чанков
   ├── 02_media_audit.md       ← 6 медиа (image/audio/video)
   └── 03_search_audit.md      ← 14 запросов
```

---

## 🛠️ Технические детали

### Как это работает внутри?

**Ключевой паттерн: Decorator/Wrapper**

```python
class PipelineInspector:
    """Обёртка над SemanticCore."""
    
    def __init__(self, core: SemanticCore, collector: AuditCollector):
        self.core = core          # Оригинальный SemanticCore
        self.collector = collector # Куда пишем данные
    
    def ingest_with_inspection(self, document: Document) -> Document:
        """Индексация с перехватом данных."""
        
        # 1. Вызываем оригинальные методы
        chunks = self.core.splitter.split(document)
        
        # 2. Перехватываем результат
        for chunk in chunks:
            context_text = self.core.context_strategy.form_vector_text(chunk, document)
            
            # 3. Записываем в collector
            inspection = ChunkInspection(
                content=chunk.content,
                context_text=context_text,
                # ...
            )
            self.collector.add_chunk_inspection(inspection)
        
        # 4. Продолжаем обычную обработку
        embeddings = self.core.embedder.embed_documents(...)
        
        # 5. Дополняем inspection данными
        for i, emb in enumerate(embeddings):
            self.collector.inspections[i].embedding = emb
        
        # 6. Обычное сохранение в БД
        return self.core.index.add_document(document, enriched_chunks)
```

**Почему это работает:**

1. **Не меняет SemanticCore** — оригинальный код не трогаем
2. **Минимальный overhead** — только перехват данных
3. **Прозрачно для кода** — можно использовать `inspector.ingest()` вместо `core.index.add_document()`

### Data Flow

```
User Input
    │
    ▼
┌──────────────────────────────────────────┐
│  PipelineInspector                       │
│  ┌────────────────────────────────────┐  │
│  │ 1. Split                           │  │ → ChunkInspection
│  │    chunks = core.splitter.split()  │  │
│  └────────────────────────────────────┘  │
│  ┌────────────────────────────────────┐  │
│  │ 2. Context                         │  │ → context_text
│  │    context = strategy.form_text()  │  │
│  └────────────────────────────────────┘  │
│  ┌────────────────────────────────────┐  │
│  │ 3. Embed                           │  │ → embedding vector
│  │    vectors = embedder.embed()      │  │
│  └────────────────────────────────────┘  │
│  ┌────────────────────────────────────┐  │
│  │ 4. Save                            │  │ → document.id
│  │    doc = index.add_document()      │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
    │
    ▼
AuditCollector (in-memory)
    │
    ▼
File Export (on session end / on demand)
    │
    ├─ 📄 Markdown Reports (human-readable)
    └─ 📦 JSON Artifacts (machine-readable)
```

---

## 🚀 Roadmap реализации

### Phase 14.1: CLI Inspector (базовый)

**Что реализуем:**

- ✅ `semantic inspect <file>` команда
- ✅ Console output с Rich panels
- ✅ `--save-artifacts` флаг для JSON/Markdown экспорта
- ✅ Переиспользование `PipelineInspector` из Phase 13

**Примерная сложность:** 2-3 дня

**Файлы:**

```
semantic_core/cli/commands/inspect_cmd.py    ← Новая команда
semantic_core/core/inspector.py              ← Перенос из tests/
semantic_core/cli/ui/inspector_panels.py     ← Rich UI компоненты
```

### Phase 14.2: Interactive Mode

**Что реализуем:**

- ✅ `--interactive` флаг
- ✅ Pause на каждом шаге
- ✅ Preview данных (pager для больших текстов)
- ✅ Save intermediate states

**Примерная сложность:** 1-2 дня

### Phase 14.3: Compare Mode

**Что реализуем:**

- ✅ `semantic inspect --compare <baseline>`
- ✅ Diff между двумя inspection artifacts
- ✅ Highlight изменений (chunk boundaries, embeddings drift)
- ✅ Regression detection

**Примерная сложность:** 2-3 дня

### Phase 14.4: Test Integration

**Что реализуем:**

- ✅ `pytest --enable-inspector` флаг
- ✅ Условное включение инспектора в обычных тестах
- ✅ Автоматическое сравнение с golden files

**Примерная сложность:** 1-2 дня

---

## 📊 Примеры использования

### Use Case 1: Отладка chunking

**Проблема:** Чанки получаются слишком большие

```bash
# Запускаем инспекцию
semantic inspect docs/long_article.md

# Видим в консоли:
┌─ Chunk #1 [TEXT] 📝 ─────────────────────────────────┐
│ Size: 1247 chars  ⚠️ EXCEEDS chunk_size=512          │
└───────────────────────────────────────────────────────┘

# Сохраняем для анализа
semantic inspect docs/long_article.md --save-artifacts

# Смотрим JSON
cat inspection_artifacts/.../long_article_inspection.json | jq '.chunks[] | {id, size}'
```

### Use Case 2: Проверка media enrichment

**Проблема:** Изображения обрабатываются некорректно

```bash
# Инспектируем документ с изображениями
semantic inspect docs/tutorial_with_images.md --save-artifacts

# Смотрим отчёт
cat inspection_artifacts/.../tutorial_with_images_report.md
```

**Видим в отчёте:**

```markdown
## Chunk #5 [IMAGE_REF] 🖼️

**Asset:** `cat_photo.png`
**Alt text:** "Tabby cat portrait"

### Media Processing

**System Prompt:**
```

You are an image analyst. Describe this image...

```

**User Prompt:**
```

The image appears in context:
"Here's our mascot cat, Mr. Whiskers"

```

**Gemini Response:**
```json
{
  "description": "Close-up portrait of a tabby cat...",
  "keywords": ["cat", "pet", "tabby", "portrait"],
  "confidence": 0.95
}
```

### Final Chunk Content

```
Document: tutorial_with_images.md
Section: Team > Mascot

Context: Here's our mascot cat, Mr. Whiskers

[Image: cat_photo.png]
Alt: Tabby cat portrait
Description: Close-up portrait of a tabby cat with green eyes...
Keywords: cat, pet, tabby, portrait
```

```

### Use Case 3: Сравнение версий

**Проблема:** После изменения конфига качество поиска упало

```bash
# Baseline (старая версия)
git checkout v1.0
semantic inspect docs/example.md --save-artifacts
cp -r inspection_artifacts/latest inspection_artifacts/baseline

# Current (новая версия)
git checkout main
semantic inspect docs/example.md --save-artifacts

# Compare
semantic inspect --compare inspection_artifacts/baseline/example_md_inspection.json \
                           inspection_artifacts/latest/example_md_inspection.json
```

**Вывод:**

```
╭────────────────────────────────────────────────────────╮
│  📊 Comparison Report                                  │
╰────────────────────────────────────────────────────────╯

Comparing:
  Baseline: inspection_artifacts/baseline/example_md_inspection.json
  Current:  inspection_artifacts/latest/example_md_inspection.json

┌─ Chunking Differences ────────────────────────────────┐
│ ⚠️  Chunk count changed: 7 → 9 (+2)                   │
│ ⚠️  Chunk #3 size: 487 → 324 (-163 chars)             │
│ ✅ Chunk types: identical                              │
└────────────────────────────────────────────────────────┘

┌─ Embedding Differences ───────────────────────────────┐
│ ⚠️  Avg cosine similarity: 0.87 (13% drift)           │
│ 🔴 Chunk #1 embedding drift: 0.23 (HIGH)              │
│ 🟡 Chunk #2 embedding drift: 0.11 (MEDIUM)            │
│ ✅ Chunks #3-7 embedding drift: <0.05 (LOW)           │
└────────────────────────────────────────────────────────┘

🚨 Potential Issues:
  - Chunk boundaries changed significantly
  - Embedding drift detected (may affect search quality)
```

---

## 🎯 Резюме

### Что уже есть (Phase 13)

✅ **PipelineInspector** — перехватывает данные  
✅ **E2E Audit Tests** — генерируют Markdown отчёты  
✅ **AuditCollector** — накапливает данные в памяти  
✅ **Session-scoped reports** — автоматическое сохранение в конце сессии  

### Что добавим (Phase 14)

🔨 **CLI команда** `semantic inspect` — консольная визуализация  
🔨 **Save artifacts** — экспорт в JSON/Markdown по требованию  
🔨 **Interactive mode** — пошаговое выполнение с паузами  
🔨 **Compare mode** — diff между запусками  
🔨 **Test integration** — условное включение инспектора в тестах  

### Как это работает

1. **Inspector оборачивает SemanticCore** — перехватывает вызовы методов
2. **Записывает промежуточные данные** в InspectionReport
3. **Экспортирует в 3 формата:**
   - 📺 Console (Rich TUI) — для быстрой отладки
   - 📄 Markdown — для человека (читаемые отчёты)
   - 📦 JSON — для программ (полные дампы данных)

### Интеграция с тестами

**Вариант А** (Phase 13 — текущий):

- Тесты ИСПОЛЬЗУЮТ Inspector
- Автоматическая генерация отчётов
- Тесты И инспектор — одна сущность

**Вариант Б** (Phase 14 — планируется):

- Инспектор ДОПОЛНЯЕТ тесты
- Включается флагом `--enable-inspector`
- Обычные тесты не замедляются
