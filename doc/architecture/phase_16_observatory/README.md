# 🔬 Phase 16: Debug Observatory & Multi-Provider Inspection

> "Рентгеновский аппарат" для SemanticCore — визуализация каждого шага pipeline

**Коммиты:**

- `591f972` — Phase 16.0 feat: Реализован Debug Observatory (Inspector Core)
- `aced5f8` — bugfix: Исправлена sanitization FTS5 запросов со спецсимволами
- `9cc8a70` — Phase 16.0 feat: Add local-vision-mlx support with Qwen3-VL-4B

**Зависимости:** Phase 15 (Provider-Agnostic Architecture)  
**Статус:** ✅ Phase 16.0 Complete (Inspector Core + Local Vision MLX)

---

## 🎯 Миссия фазы

**Проблема:**

При разработке SemanticCore возникла задача: **как понять почему у всех результатов поиска similarity ~0.55?**

Нужно было увидеть:

- Что именно отправляется в Gemini?
- Какие embeddings возвращаются?
- Как работает гибридный поиск (vector + FTS)?
- Какие чанки попадают в финальный результат?

**Попытка решения №1 (Phase 13):**
Создали `PipelineInspector` в тестах (`tests/e2e/audit/`):

- ✅ Работал, но только для Gemini провайдеров (hardcoded)
- ❌ Нельзя было использовать из CLI
- ❌ Артефакты сохранялись только в тестах
- ❌ Нет сравнения конфигураций

**Решение (Phase 16):**
Создать полноценную подсистему **Debug Observatory**:

```
semantic_core/core/observatory/
├── inspector.py       # ProviderInspector — перехват любых провайдеров
├── snapshot.py        # SnapshotManager — сохранение артефактов  
├── models.py          # Dataclass'ы для snapshot'ов
└── reporters/         # Экспорт в разные форматы
    ├── console.py     # Rich TUI
    ├── markdown.py    # Human-readable отчёты
    ├── json.py        # Machine-readable dumps
    └── diff.py        # Сравнение снимков
```

---

## 📊 Что изменилось

### До (Phase 13)

```python
# tests/e2e/audit/conftest.py
class PipelineInspector:
    """Hardcoded для Gemini, только для тестов."""
    
    def __init__(self, gemini_embedder: GeminiEmbedder):
        self.embedder = gemini_embedder  # Только Gemini!
        
    def ingest(self, file_path: str):
        # Вызовы hardcoded методов
        embeddings = self.embedder.embed_batch([...])
```

❌ **Проблемы:**

- Работает только с Gemini
- Нельзя использовать с локальными моделями (MLX)
- Нет CLI команды
- Артефакты не сохраняются структурированно

### После (Phase 16.0)

```python
# semantic_core/core/observatory/inspector.py
class ProviderInspector:
    """Provider-agnostic inspector для любых комбинаций."""
    
    def __init__(
        self, 
        core: SemanticCore,  # ← Работает с любыми провайдерами!
        artifacts_root: Optional[Path] = None
    ):
        self.core = core
        self.snapshot_manager = SnapshotManager(artifacts_root)
        
    def ingest_with_inspection(self, path: str) -> InspectionSnapshot:
        """Инспекция с сохранением артефактов."""
        # Duck typing — работает с любыми провайдерами
        embedder_meta = self._extract_provider_metadata(self.core.embedder)
        
        # Pipeline execution с перехватом
        snapshot = InspectionSnapshot(
            embedder_metadata=embedder_meta,
            chunks=[...],
            steps=[...]
        )
        
        return snapshot
```

✅ **Преимущества:**

- Работает с **любыми** провайдерами (Gemini, MLX, OpenAI)
- Доступен из CLI: `semantic inspect docs/example.md`
- Артефакты сохраняются в структурированном виде
- Можно сравнивать конфигурации

---

## 🏗️ Архитектура Observatory

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interaction                          │
│  semantic inspect file.md --save --format markdown          │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│            CLI Command (inspect.py)                          │
│  - Парсинг аргументов                                       │
│  - Создание SemanticCore через ComponentFactory            │
│  - Вызов ProviderInspector                                  │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│         ProviderInspector (inspector.py)                     │
│                                                              │
│  def ingest_with_inspection(path):                          │
│    1. Extract metadata (duck typing)                        │
│    2. Run pipeline (core.ingest)                            │
│    3. Capture intermediate states                           │
│    4. Create InspectionSnapshot                             │
│    5. Return snapshot                                       │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│        InspectionSnapshot (models.py)                        │
│                                                              │
│  @dataclass                                                  │
│  class InspectionSnapshot:                                   │
│    file_path: str                                           │
│    file_content: str              ← Входной файл           │
│    embedder_metadata: ProviderMetadata                      │
│    chunks: List[ChunkInspection]  ← Все чанки с embeddings │
│    searches: List[SearchInspection]  ← Результаты поиска   │
│    steps: List[Dict]              ← Пошаговые логи         │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│         SnapshotManager (snapshot.py)                        │
│                                                              │
│  def save_snapshot(snapshot, session_path, file_prefix):   │
│    - Converts dataclass → dict                              │
│    - Saves as JSON (optionally compressed)                  │
│    - Returns Path to saved file                            │
│                                                              │
│  def load_snapshot(path) → InspectionSnapshot:             │
│    - Loads JSON                                             │
│    - Reconstructs dataclasses                               │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│              Reporters (reporters/)                          │
│                                                              │
│  ConsoleReporter: Rich panels, tables, syntax highlighting  │
│  MarkdownReporter: Human-readable reports                   │
│  JsonReporter: Machine-readable exports                     │
│  DiffReporter: Snapshot comparison                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔑 Ключевые компоненты

### 1. ProviderInspector

**Задача:** Перехватывать вызовы провайдеров и собирать метаданные

**Duck typing подход:**

```python
def _extract_provider_metadata(self, provider) -> ProviderMetadata:
    """Извлекает метаданные из любого провайдера."""
    provider_type = type(provider).__name__
    
    # Пытаемся извлечь атрибуты через duck typing
    model_name = getattr(provider, "model", None)
    dimension = getattr(provider, "dimension", None)
    # ... и так далее
    
    return ProviderMetadata(
        provider_type=provider_type,
        model_name=model_name,
        dimension=dimension
    )
```

**Преимущества:**

- ✅ Работает с любыми провайдерами (не только Gemini)
- ✅ Не требует изменения кода провайдеров
- ✅ Graceful degradation (если атрибут отсутствует → None)

### 2. InspectionSnapshot

**Задача:** Хранить полный снимок выполнения pipeline

**Структура:**

```python
@dataclass
class InspectionSnapshot:
    """Полный снимок инспекции."""
    
    # Метаданные файла
    file_path: str
    file_content: str  # ← Копия входного файла
    processing_timestamp: str
    
    # Метаданные провайдеров
    embedder_metadata: Optional[ProviderMetadata]
    transcriber_metadata: Optional[ProviderMetadata]
    vision_metadata: Optional[ProviderMetadata]
    
    # Результаты обработки
    chunks: List[ChunkInspection]      # Все чанки с embeddings
    searches: List[SearchInspection]   # Результаты поиска
    
    # Пошаговая информация
    steps: List[Dict[str, Any]]        # Логи каждого шага
    total_duration_ms: float
```

**Зачем нужно `file_content`?**

Критически важно сохранять копию входного файла в snapshot! Это позволяет:

- Воспроизвести инспекцию позже (даже если оригинал изменился)
- Сравнивать конфигурации на одном и том же контенте
- Создавать golden-file тесты

### 3. SnapshotManager

**Задача:** Сохранение и загрузка snapshot'ов

**Структура артефактов:**

```
tests/e2e/audit/snapshots/
└── session_2025-12-10_14-30-15/
    ├── example_md_inspection.json      # Полный snapshot
    ├── input_example.md                # Копия входного файла
    ├── similarities.csv                # Similarity matrix
    └── report.md                       # Markdown отчёт
```

**API:**

```python
# Создание сессии
session_path = snapshot_manager.create_session_folder("my_test")

# Сохранение snapshot
snapshot_path = snapshot_manager.save_snapshot(
    snapshot,
    session_path=session_path,
    file_prefix="example_md"
)

# Загрузка snapshot
loaded = snapshot_manager.load_snapshot(snapshot_path)
```

### 4. Reporters

**Задача:** Экспорт snapshot'ов в разные форматы

#### ConsoleReporter (Rich TUI)

```python
reporter = ConsoleReporter()
reporter.display_snapshot(snapshot)
```

**Вывод:**

```
╭─────────────────────── Provider Metadata ──────────────────────╮
│ Type:      GeminiEmbedder                                      │
│ Dimension: 768                                                 │
│ Max Tokens: 2048                                               │
╰────────────────────────────────────────────────────────────────╯

╭─────────────────────── Chunks (3) ─────────────────────────────╮
│ ID    │ Content Preview             │ Embedding Preview        │
│────────────────────────────────────────────────────────────────│
│ 1     │ # Introduction to Python... │ [0.123, -0.456, ...]    │
│ 2     │ Python is a high-level...   │ [0.789, 0.234, ...]     │
│ 3     │ ```python...                │ [-0.123, 0.567, ...]    │
╰────────────────────────────────────────────────────────────────╯
```

#### MarkdownReporter

Генерирует отчёты как в Phase 13:

```markdown
# 🔍 Inspection Report

**File:** `docs/example.md`
**Timestamp:** 2025-12-10 14:30:15
**Duration:** 1549.58ms

## 🔧 Embedder

- **Type:** `GeminiEmbedder`
- **Dimension:** 768

## 📦 Chunks (3)

### Chunk #1
**Content Preview:**
```

# Introduction to Python

```

**Embedding:**
```

[0.123, -0.456, 0.789, ...]

```
```

#### JsonReporter

Полный dump в JSON для машинной обработки.

#### DiffReporter

Сравнение двух snapshot'ов:

```python
diff_reporter = DiffReporter()
diff = diff_reporter.compare(snapshot1, snapshot2)

print(diff.summary())
```

**Вывод:**

```
📊 Snapshot Comparison

Provider Changes:
  ❌ embedder.model_name: gemini-embedding-001 → gemini-embedding-004
  ✅ embedder.dimension: 768 (no change)

Chunks:
  3 → 3 (no change)
  
Embeddings:
  Average diff: 0.234
  Max diff: 0.567
```

---

## 🔍 Критический bugfix: FTS5 Sanitization

**Важно!** Во время разработки Phase 16.0 был обнаружен критический баг в `_sanitize_fts_query`, существовавший **с Phase 2**.

### Проблема

```python
# ❌ СТАРАЯ версия (СЛОМАНО):
def _sanitize_fts_query(query: str) -> str:
    # Обрабатывала ТОЛЬКО:
    # - Дефисы внутри токенов
    # - Квадратные скобки
    # ❌ НЕ обрабатывала: (), ?, и другие спецсимволы!
```

**Последствия:**

```python
# Запросы с круглыми скобками или вопросами ломались:
"What is Python?"        → fts5: syntax error near "?"
"Python (language)"      → fts5: syntax error near "Python"
"machine-learning intro" → работает (дефис обрабатывался)
```

### Решение

```python
# ✅ НОВАЯ версия (ИСПРАВЛЕНО):
def _sanitize_fts_query(query: str) -> str:
    """Экранирует запрос для FTS5."""
    
    # 1. Если уже в кавычках — не трогаем
    if query.startswith('"') and query.endswith('"'):
        return query
    
    # 2. Если есть () или ? — оборачиваем ВСЁ в phrase match "..."
    has_parens = "(" in query or ")" in query
    has_question = "?" in query
    
    if has_parens or has_question:
        escaped = query.replace('"', '""')  # FTS5 uses ""
        return f'"{escaped}"'
    
    # 3. Обрабатываем токены по отдельности (дефисы, скобки)
    # ... остальная логика
```

**Тесты:**

- ✅ 22 новых unit-теста для `_sanitize_fts_query`
- ✅ Все существующие FTS тесты проходят

**Подробнее:** [01_bugfix_fts_sanitization.md](01_bugfix_fts_sanitization.md)

---

## 📝 CLI Команда: `semantic inspect`

```bash
# Базовая инспекция (Rich TUI вывод)
semantic inspect docs/example.md

# Сохранить артефакты
semantic inspect docs/example.md --save

# Кастомный путь для артефактов
semantic inspect docs/example.md --save --artifacts-dir ./my_snapshots

# Markdown отчёт
semantic inspect docs/example.md --format markdown

# JSON экспорт
semantic inspect docs/example.md --format json

# С поисковым запросом
semantic inspect docs/example.md --search "Python programming"

# С кастомным конфигом
semantic inspect audio.mp3 --config alt_config.toml
```

**Пример вывода:**

```
📥 Loading document: docs/example.md
🔧 Creating SemanticCore (provider: gemini)
🧠 Embedding 3 chunks...
💾 Saving document to database...
✅ Inspection complete (1549ms)

╭─────────────────────── Provider Metadata ──────────────────────╮
│ Type:      GeminiEmbedder                                      │
│ Model:     text-embedding-004                                  │
│ Dimension: 768                                                 │
╰────────────────────────────────────────────────────────────────╯

╭─────────────────────── Chunks (3) ─────────────────────────────╮
│ #1: # Introduction to Python...                               │
│ #2: Python is a high-level programming language...            │
│ #3: ```python...                                               │
╰────────────────────────────────────────────────────────────────╯

📊 Processing Steps (4):
  1. splitting (45ms)
  2. embedding (1450ms)
  3. saving (54ms)
  4. inspection_completed (0ms)
```

**Подробнее:** [04_cli_inspect.md](04_cli_inspect.md)

---

## 🧪 Тестирование

### Unit Tests

**22 теста для FTS sanitization:**

```bash
pytest tests/unit/infrastructure/storage/test_fts_sanitization.py -v
# ✅ 22 passed
```

**19 тестов Observatory:**

```bash
pytest tests/unit/core/test_observatory.py -v  
# (будут созданы в следующих коммитах)
```

### E2E Tests

**4 теста с реальным Gemini API:**

```bash
pytest tests/e2e/audit/test_inspector_gemini.py -v

# ✅ test_inspector_ingest_with_gemini PASSED
# ✅ test_inspector_search_with_gemini PASSED  
# ✅ test_inspector_save_artifacts PASSED
# ✅ test_console_reporter_output PASSED
```

### Regression Tests

**Все существующие FTS тесты:**

```bash
pytest tests/test_phase_2_storage.py::TestFTSSearch -v
# ✅ 2 passed

pytest tests/integration/search/test_fts_chunk_level.py -v
# ✅ 3 passed
```

---

## 🎯 Результаты Phase 16.0

### ✅ Реализовано

1. **ProviderInspector** — provider-agnostic инспекция
2. **SnapshotManager** — сохранение/загрузка артефактов
3. **4 Reporter'а** — консоль, markdown, JSON, diff
4. **CLI команда** — `semantic inspect`
5. **Критический bugfix** — FTS5 sanitization
6. **Попутные фиксы** — ComponentFactory bugs

### 📦 Файлы

**Новые модули:**

- `semantic_core/core/observatory/`
  - `inspector.py` (336 lines)
  - `snapshot.py` (192 lines)
  - `models.py` (116 lines)
  - `reporters/` (440 lines total)
- `semantic_core/cli/commands/inspect.py` (280 lines)

**Обновлённые модули:**

- `semantic_core/infrastructure/storage/peewee/adapter.py` — улучшена sanitization
- `semantic_core/core/factory.py` — фиксы в create_semantic_core()

**Тесты:**

- `tests/unit/infrastructure/storage/test_fts_sanitization.py` — 22 теста
- `tests/e2e/audit/test_inspector_gemini.py` — 4 E2E теста
- `tests/unit/core/test_factory.py` — unskipped test

### 📊 Метрики

- **Новый код:** ~1725 строк
- **Тесты:** 26 новых (22 unit + 4 E2E)
- **Баги найдены:** 4 (3 в ComponentFactory, 1 в FTS sanitization)
- **Regression тесты:** ✅ все проходят

---

## 📚 Содержание серии

1. **[README.md](README.md)** — этот файл, обзор фазы
2. **[16_01_local_vision_mlx_integration.md](16_01_local_vision_mlx_integration.md)** — Qwen3-VL-4B и Optional Dependencies

---

## 🔜 Следующие подфазы

- **Phase 16.1** — CLI integration (`semantic compare`, `semantic golden`)
- **Phase 16.2** — Multi-provider snapshots
- **Phase 16.3** — Comparison engine
- **Phase 16.4** — Interactive mode
- **Phase 16.5** — Golden file testing

---

**← [Назад к оглавлению](../00_overview.md)**
