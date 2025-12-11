# Debug Observatory

> Инспекция и отладка pipeline SemanticCore

**Сложность:** 🟡 intermediate  
**Требует понимания:** Multi-Provider Architecture

---

## 🎯 Что это такое?

**Debug Observatory** — это подсистема для визуализации внутренних процессов SemanticCore:

- Что отправляется в embedder?
- Какие embeddings возвращаются?
- Как работает гибридный поиск?
- Какие чанки попадают в результат?

**Философия:** "Рентген" для pipeline — видеть каждый шаг обработки данных.

---

## 🏗️ Архитектура

```
semantic_core/core/observatory/
├── inspector.py       # ProviderInspector — перехват вызовов
├── snapshot.py        # SnapshotManager — сохранение артефактов
├── models.py          # InspectionSnapshot — структура данных
└── reporters/         # Экспорт в разные форматы
    ├── console.py     # Rich TUI для терминала
    ├── markdown.py    # Human-readable отчёты
    ├── json.py        # Machine-readable dumps
    └── diff.py        # Сравнение снимков
```

---

## 🔍 Основные компоненты

### 1. ProviderInspector

Обёртка над `SemanticCore`, которая перехватывает вызовы и собирает метаданные:

```python
from semantic_core.core.observatory import ProviderInspector
from semantic_core.core.factory import ComponentFactory
from semantic_core import get_config

# Создаём SemanticCore
config = get_config()
core = ComponentFactory.create_semantic_core(config)

# Оборачиваем в инспектор
inspector = ProviderInspector(core, artifacts_root="./snapshots")

# Индексируем с инспекцией
snapshot = inspector.ingest_with_inspection("docs/example.md")

# Snapshot содержит:
# - Метаданные провайдеров (embedder, transcriber, vision)
# - Все чанки с их embeddings
# - Пошаговые логи
# - Время выполнения
```

**Ключевая фишка:** Duck typing — работает с **любыми** провайдерами (Gemini, Local, OpenAI).

### 2. InspectionSnapshot

Структура данных для хранения результатов инспекции:

```python
@dataclass
class InspectionSnapshot:
    """Полный снимок инспекции."""
    
    # Метаданные файла
    file_path: str
    file_content: str              # Копия входного файла
    processing_timestamp: str
    
    # Метаданные провайдеров
    embedder_metadata: Optional[ProviderMetadata]
    transcriber_metadata: Optional[ProviderMetadata]
    vision_metadata: Optional[ProviderMetadata]
    
    # Результаты обработки
    chunks: List[ChunkInspection]       # Все чанки
    searches: List[SearchInspection]    # Результаты поиска
    
    # Пошаговая информация
    steps: List[Dict[str, Any]]         # Логи
    total_duration_ms: float
```

**Зачем `file_content`?**

Критически важно сохранять копию входного файла! Это позволяет:

- Воспроизвести инспекцию позже
- Сравнивать конфигурации на одном контенте
- Создавать golden-file тесты

### 3. SnapshotManager

Сохранение и загрузка артефактов:

```python
from semantic_core.core.observatory import SnapshotManager

manager = SnapshotManager(artifacts_root="./snapshots")

# Создаём сессию
session_path = manager.create_session_folder("my_test")

# Сохраняем snapshot
snapshot_path = manager.save_snapshot(
    snapshot,
    session_path=session_path,
    file_prefix="example_md"
)

# Загружаем обратно
loaded = manager.load_snapshot(snapshot_path)
```

**Структура артефактов:**

```
snapshots/
└── session_2025-12-10_14-30-15/
    ├── example_md_inspection.json    # Полный snapshot
    ├── input_example.md              # Копия входного файла
    ├── similarities.csv              # Similarity matrix (опционально)
    └── report.md                     # Markdown отчёт (опционально)
```

### 4. Reporters

Экспорт snapshot'ов в разные форматы:

#### ConsoleReporter (Rich TUI)

```python
from semantic_core.core.observatory.reporters import ConsoleReporter

reporter = ConsoleReporter()
reporter.display_snapshot(snapshot)
```

**Вывод:**

```
╭─────────────────────── Provider Metadata ──────────────────────╮
│ Type:      GeminiEmbedder                                      │
│ Model:     text-embedding-004                                  │
│ Dimension: 768                                                 │
╰────────────────────────────────────────────────────────────────╯

╭─────────────────────── Chunks (3) ─────────────────────────────╮
│ ID    │ Content Preview             │ Embedding Preview        │
├───────┼─────────────────────────────┼─────────────────────────┤
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
- **Model:** `text-embedding-004`
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

#### DiffReporter

Сравнение двух конфигураций:

```python
from semantic_core.core.observatory.reporters import DiffReporter

diff_reporter = DiffReporter()
diff = diff_reporter.compare(snapshot_gemini, snapshot_local)

print(diff.summary())
```

**Вывод:**

```
📊 Snapshot Comparison

Provider Changes:
  ❌ embedder.type: GeminiEmbedder → LocalEmbedder
  ❌ embedder.dimension: 768 → 384
  ✅ transcriber: None (no change)

Chunks:
  3 → 3 (no change)
  
Embeddings:
  Average diff: 0.234
  Max diff: 0.567
```

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
semantic inspect docs/example.md --format json --output report.json

# С поисковым запросом
semantic inspect docs/example.md --search "Python programming"

# С кастомным конфигом
semantic inspect audio.mp3 --config alt_config.toml
```

---

## 🎬 Use Cases

### Use Case 1: Отладка нового провайдера

**Ситуация:** Внедрили локальный embedder, хотим проверить качество.

```bash
# 1. Baseline с Gemini
semantic inspect example.md \
  --config gemini_config.toml \
  --save --artifacts-dir snapshots/gemini/

# 2. Новый провайдер
semantic inspect example.md \
  --config local_config.toml \
  --save --artifacts-dir snapshots/local/

# 3. Сравнение
semantic compare \
  snapshots/gemini/example_md_inspection.json \
  snapshots/local/example_md_inspection.json
```

### Use Case 2: Диагностика низкого similarity

**Ситуация:** Все результаты поиска имеют similarity ~0.55, хотим понять почему.

```bash
# Инспектируем с поисковым запросом
semantic inspect docs/python_guide.md \
  --search "Python type hints" \
  --save
```

**В отчёте увидим:**

- Какой текст отправился в embedder (с контекстом заголовков)
- Какие embeddings вернулись
- Similarity между запросом и каждым чанком
- Почему именно эти чанки попали в результат

### Use Case 3: Проверка чанкинга

**Ситуация:** Хотим проверить, правильно ли разбивается Markdown.

```bash
semantic inspect complex_doc.md --format markdown
```

**В отчёте увидим:**

- Границы чанков
- Иерархию заголовков для каждого чанка
- Context text (что пойдёт в embedder)
- Размеры чанков

---

## 🔧 Программное использование

### Пример: Автотест с golden-file

```python
from semantic_core.core.observatory import ProviderInspector, SnapshotManager
from semantic_core.core.factory import ComponentFactory
from semantic_core import get_config

def test_golden_file():
    """Тест с эталонным snapshot."""
    
    # 1. Загружаем конфиг и создаём core
    config = get_config()
    core = ComponentFactory.create_semantic_core(config)
    
    # 2. Создаём инспектор
    inspector = ProviderInspector(core)
    
    # 3. Инспектируем тестовый файл
    snapshot = inspector.ingest_with_inspection("tests/fixtures/example.md")
    
    # 4. Загружаем golden-файл
    manager = SnapshotManager()
    golden = manager.load_snapshot("tests/golden/example_md.json")
    
    # 5. Сравниваем
    assert snapshot.chunks[0].content == golden.chunks[0].content
    assert len(snapshot.chunks) == len(golden.chunks)
    
    # 6. Проверяем embeddings (допускаем небольшую разницу)
    import numpy as np
    for snap_chunk, golden_chunk in zip(snapshot.chunks, golden.chunks):
        diff = np.linalg.norm(
            np.array(snap_chunk.embedding_preview) - 
            np.array(golden_chunk.embedding_preview)
        )
        assert diff < 0.01, f"Embedding drift: {diff}"
```

---

## ⚠️ Важные детали

### Duck Typing

`ProviderInspector` не требует, чтобы провайдеры имели специальные методы:

```python
def _extract_provider_metadata(self, provider) -> ProviderMetadata:
    """Извлекает метаданные через duck typing."""
    
    provider_type = type(provider).__name__
    
    # Пытаемся извлечь атрибуты
    model_name = getattr(provider, "model", None)
    dimension = getattr(provider, "dimension", None)
    
    return ProviderMetadata(
        provider_type=provider_type,
        model_name=model_name,
        dimension=dimension
    )
```

**Преимущества:**

- ✅ Работает с любыми провайдерами
- ✅ Не требует изменений в провайдерах
- ✅ Graceful degradation (если атрибута нет → None)

### Overhead

Инспекция добавляет ~5-10% overhead:

- Копирование данных для snapshot
- Сохранение промежуточных состояний
- Подсчёт времени выполнения

**Рекомендация:** Используйте инспекцию только для отладки, не в production.

---

## 📚 Связанные концепции

- [Multi-Provider](11_multi_provider.md) — как работают провайдеры
- [Observability](09_observability.md) — логирование и TRACE
- [Plugin System](10_plugin_system.md) — интерфейсы

---

## 🔗 Архитектурные статьи

Детальная документация в архитектурном сериале:

- [Phase 16: Debug Observatory](../../doc/architecture/phase_16_observatory/README.md)
- [02: Inspector Core](../../doc/architecture/phase_16_observatory/02_inspector_core.md)
- [03: Reporters](../../doc/architecture/phase_16_observatory/03_reporters.md)
- [04: CLI Inspect](../../doc/architecture/phase_16_observatory/04_cli_inspect.md)

---

## 🎓 Следующие шаги

1. Прочитайте [Inspect Command Guide](../guides/core/inspect-command.md)
2. Попробуйте: `semantic inspect your_file.md`
3. Сравните разные конфигурации
4. Создайте golden-файлы для своих тестов
