# 🖥️ CLI Inspect: Команда `semantic inspect`

> Удобный интерфейс для Debug Observatory

**Коммит:** `591f972` — phase 16.0 feat: Реализован Debug Observatory (CLI)

---

## 🎯 Задача

Предоставить удобный CLI интерфейс для инспекции pipeline:

- ✅ Команда `semantic inspect <path>` — инспекция файла
- ✅ Команда `semantic compare <old> <new>` — сравнение snapshots
- ✅ Выбор формата вывода (`--format json|markdown|console`)
- ✅ Сохранение артефактов (`--save-artifacts`)
- ✅ Интеграция с существующими командами (ingest/search)

---

## 📋 Команды

### `semantic inspect`

**Назначение:** Инспекция ingest pipeline для файла.

**Синтаксис:**
```bash
semantic inspect <file_path> [OPTIONS]
```

**Опции:**

| Опция | Тип | По умолчанию | Описание |
|-------|-----|-------------|----------|
| `--format` | choice | `console` | Формат вывода: `console`, `markdown`, `json` |
| `--save-artifacts` | flag | `False` | Сохранить snapshot и артефакты в папку |
| `--artifacts-root` | path | `./snapshots` | Путь для сохранения артефактов |
| `--session-name` | str | `auto` | Имя сессии (или авто timestamp) |

**Примеры:**

```bash
# Базовая инспекция (console output)
semantic inspect docs/example.md

# Markdown отчёт
semantic inspect docs/example.md --format markdown

# JSON вывод для автоматизации
semantic inspect docs/example.md --format json > snapshot.json

# С сохранением артефактов
semantic inspect docs/example.md --save-artifacts --artifacts-root ./my_snapshots

# С кастомным именем сессии
semantic inspect docs/example.md --save-artifacts --session-name experiment_1
```

---

### `semantic compare`

**Назначение:** Сравнение двух inspection snapshots.

**Синтаксис:**
```bash
semantic compare <old_snapshot> <new_snapshot> [OPTIONS]
```

**Опции:**

| Опция | Тип | По умолчанию | Описание |
|-------|-----|-------------|----------|
| `--format` | choice | `markdown` | Формат вывода: `markdown`, `json` |

**Примеры:**

```bash
# Сравнить два snapshot
semantic compare snapshots/old.json snapshots/new.json

# JSON diff
semantic compare snapshots/old.json snapshots/new.json --format json
```

---

## 🔧 Реализация

### `inspect` команда

```python
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console

from semantic_core import create_core
from semantic_core.core.observatory import (
    ProviderInspector,
    ConsoleReporter,
    MarkdownReporter,
    JsonReporter,
)

app = typer.Typer()
console = Console()


@app.command()
def inspect(
    file_path: str = typer.Argument(..., help="Path to file to inspect"),
    format: str = typer.Option(
        "console",
        "--format",
        "-f",
        help="Output format: console, markdown, json"
    ),
    save_artifacts: bool = typer.Option(
        False,
        "--save-artifacts",
        help="Save snapshot and artifacts to folder"
    ),
    artifacts_root: Optional[str] = typer.Option(
        None,
        "--artifacts-root",
        help="Root directory for artifacts (default: ./snapshots)"
    ),
    session_name: Optional[str] = typer.Option(
        None,
        "--session-name",
        help="Custom session name (default: auto timestamp)"
    ),
):
    """
    Inspect the ingest pipeline for a file.
    
    Examples:
        semantic inspect docs/example.md
        semantic inspect docs/example.md --format markdown
        semantic inspect docs/example.md --save-artifacts
    """
    
    # 1. Валидация файла
    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        console.print(f"[red]Error: File not found: {file_path}[/red]")
        raise typer.Exit(code=1)
    
    # 2. Создаём SemanticCore
    core = create_core()
    
    # 3. Создаём ProviderInspector
    artifacts_root_path = Path(artifacts_root) if artifacts_root else None
    inspector = ProviderInspector(
        core=core,
        artifacts_root=artifacts_root_path
    )
    
    # 4. Выполняем инспекцию
    console.print(f"[cyan]🔍 Inspecting:[/cyan] {file_path}")
    
    try:
        snapshot = inspector.ingest_with_inspection(file_path)
    except Exception as e:
        console.print(f"[red]Error during inspection: {e}[/red]")
        raise typer.Exit(code=1)
    
    # 5. Сохраняем артефакты (если указано)
    if save_artifacts:
        session = inspector.snapshot_manager.create_session_folder(session_name)
        file_prefix = file_path_obj.stem.replace(".", "_")
        
        snapshot_path = inspector.snapshot_manager.save_snapshot(
            snapshot,
            session_path=session,
            file_prefix=file_prefix
        )
        
        console.print(f"[green]✅ Snapshot saved:[/green] {snapshot_path}")
    
    # 6. Выводим результат в нужном формате
    if format == "console":
        reporter = ConsoleReporter()
        reporter.report(snapshot)
    
    elif format == "markdown":
        reporter = MarkdownReporter()
        output = reporter.report(snapshot)
        console.print(output)
    
    elif format == "json":
        reporter = JsonReporter()
        output = reporter.report(snapshot)
        console.print(output)
    
    else:
        console.print(f"[red]Unknown format: {format}[/red]")
        raise typer.Exit(code=1)
```

**Ключевые моменты:**

**1. Создание SemanticCore:**
```python
core = create_core()  # Используем фабрику из config
```

Автоматически загружаются настройки из `semantic.toml`:
- Embedder (Gemini)
- Vision analyzer
- Storage (SQLite)

**2. ProviderInspector с artifacts_root:**
```python
inspector = ProviderInspector(
    core=core,
    artifacts_root=Path(artifacts_root) if artifacts_root else None
)
```

Если `--artifacts-root` не указан → используется дефолтный путь из SnapshotManager.

**3. Условное сохранение:**
```python
if save_artifacts:
    session = inspector.snapshot_manager.create_session_folder(session_name)
    snapshot_path = inspector.snapshot_manager.save_snapshot(...)
```

Сохраняем только если пользователь явно указал `--save-artifacts`.

**4. Динамический выбор reporter:**
```python
if format == "console":
    reporter = ConsoleReporter()
elif format == "markdown":
    reporter = MarkdownReporter()
elif format == "json":
    reporter = JsonReporter()
```

---

### `compare` команда

```python
@app.command()
def compare(
    old_snapshot: str = typer.Argument(..., help="Path to old snapshot JSON"),
    new_snapshot: str = typer.Argument(..., help="Path to new snapshot JSON"),
    format: str = typer.Option(
        "markdown",
        "--format",
        "-f",
        help="Output format: markdown, json"
    ),
):
    """
    Compare two inspection snapshots.
    
    Examples:
        semantic compare snapshots/old.json snapshots/new.json
        semantic compare old.json new.json --format json
    """
    
    # 1. Валидация файлов
    old_path = Path(old_snapshot)
    new_path = Path(new_snapshot)
    
    if not old_path.exists():
        console.print(f"[red]Error: Old snapshot not found: {old_snapshot}[/red]")
        raise typer.Exit(code=1)
    
    if not new_path.exists():
        console.print(f"[red]Error: New snapshot not found: {new_snapshot}[/red]")
        raise typer.Exit(code=1)
    
    # 2. Загружаем snapshots
    from semantic_core.core.observatory import SnapshotManager
    
    manager = SnapshotManager()
    
    console.print(f"[cyan]📂 Loading old snapshot:[/cyan] {old_snapshot}")
    old = manager.load_snapshot(old_path)
    
    console.print(f"[cyan]📂 Loading new snapshot:[/cyan] {new_snapshot}")
    new = manager.load_snapshot(new_path)
    
    # 3. Сравниваем
    from semantic_core.core.observatory import DiffReporter
    
    diff_reporter = DiffReporter()
    
    console.print("[cyan]🔍 Comparing snapshots...[/cyan]\n")
    
    if format == "markdown":
        output = diff_reporter.compare(old, new)
        console.print(output)
    
    elif format == "json":
        # JSON diff (структурированный)
        diff_data = {
            "old_timestamp": old.processing_timestamp,
            "new_timestamp": new.processing_timestamp,
            "provider_changes": diff_reporter._diff_providers(old, new),
            "chunks_changes": diff_reporter._diff_chunks(old, new),
            "embeddings_changes": diff_reporter._diff_embeddings(old, new),
            "metrics_changes": diff_reporter._diff_metrics(old, new),
        }
        
        import json
        output = json.dumps(diff_data, ensure_ascii=False, indent=2)
        console.print(output)
    
    else:
        console.print(f"[red]Unknown format: {format}[/red]")
        raise typer.Exit(code=1)
```

**Ключевые моменты:**

**1. Загрузка snapshots:**
```python
manager = SnapshotManager()
old = manager.load_snapshot(old_path)
new = manager.load_snapshot(new_path)
```

SnapshotManager умеет загружать как `.json`, так и `.json.gz`.

**2. DiffReporter:**
```python
diff_reporter = DiffReporter()
output = diff_reporter.compare(old, new)
```

Markdown diff для удобного чтения.

**3. JSON diff (структурированный):**
```python
diff_data = {
    "old_timestamp": old.processing_timestamp,
    "new_timestamp": new.processing_timestamp,
    "provider_changes": diff_reporter._diff_providers(old, new),
    ...
}
```

Для автоматизации (CI/CD, алерты).

---

## 📚 Примеры использования

### Базовая инспекция

```bash
$ semantic inspect docs/example.md

╭────────────────────────────────────────╮
│ 🔍 Inspection Snapshot                 │
│ 2025-12-10T14:30:15.123456            │
╰────────────────────────────────────────╯

📦 Providers Configuration
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━┓
┃ Provider         ┃ Type             ┃ Model ┃ Dimension ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━┩
│ Embedder         │ GeminiEmbedder   │ -     │       768 │
└──────────────────┴──────────────────┴───────┴───────────┘

📄 Chunks (5)
...
```

### Markdown отчёт в файл

```bash
$ semantic inspect docs/example.md --format markdown > report.md

$ cat report.md
# Inspection Snapshot

**Timestamp:** 2025-12-10T14:30:15.123456
**File:** `docs/example.md`

## Providers Configuration
...
```

### JSON для автоматизации

```bash
$ semantic inspect docs/example.md --format json | jq '.chunks | length'
5

$ semantic inspect docs/example.md --format json | jq '.total_duration_ms'
1234.56
```

### С сохранением артефактов

```bash
$ semantic inspect docs/example.md --save-artifacts --session-name test_run

🔍 Inspecting: docs/example.md
✅ Snapshot saved: ./snapshots/test_run/example_md_inspection.json

$ tree snapshots/
snapshots/
└── test_run/
    └── example_md_inspection.json
```

### Сравнение snapshots

```bash
$ semantic compare snapshots/old.json snapshots/new.json

# Snapshot Comparison

**Old:** 2025-12-09T10:30:00.000000
**New:** 2025-12-10T14:30:15.123456

## Provider Changes

- **Embedder Type:** `GeminiEmbedder` → `MLXEmbedder`
- **Dimension:** `768` → `384`

## Chunks Changes

- **Chunk Count:** 5 (unchanged)

## Embedding Changes

- **Embeddings Changed:** 5 chunks
  - Chunk IDs: 1, 2, 3, 4, 5
...
```

---

## 🔧 Интеграция с существующими командами

### Добавление `--inspect` флага в `ingest`

Можно расширить команду `semantic ingest` для автоматической инспекции:

```python
@app.command()
def ingest(
    path: str,
    inspect: bool = typer.Option(
        False,
        "--inspect",
        help="Run inspection after ingest"
    ),
):
    """Ingest documents with optional inspection."""
    
    # Обычный ingest
    core = create_core()
    core.ingest(path)
    
    console.print(f"[green]✅ Ingested:[/green] {path}")
    
    # Опциональная инспекция
    if inspect:
        inspector = ProviderInspector(core=core)
        snapshot = inspector.ingest_with_inspection(path)
        
        reporter = ConsoleReporter()
        reporter.report(snapshot)
```

**Использование:**
```bash
# Обычный ingest
semantic ingest docs/example.md

# Ingest с инспекцией
semantic ingest docs/example.md --inspect
```

### Добавление `--inspect` флага в `search`

```python
@app.command()
def search(
    query: str,
    inspect: bool = typer.Option(
        False,
        "--inspect",
        help="Run inspection of search results"
    ),
):
    """Search with optional inspection."""
    
    core = create_core()
    results = core.search(query)
    
    # Обычный вывод
    for result in results:
        console.print(f"[green]→[/green] {result.document.content[:100]}")
    
    # Опциональная инспекция
    if inspect:
        inspector = ProviderInspector(core=core)
        snapshot = inspector.search_with_inspection(query)
        
        reporter = ConsoleReporter()
        reporter.report(snapshot)
```

---

## 🎯 Типовые сценарии

### 1. Отладка embedding качества

**Проблема:** Embeddings кажутся некорректными.

**Решение:**
```bash
# 1. Инспектируем файл
semantic inspect docs/example.md --save-artifacts --session-name debug_embeddings

# 2. Смотрим embedding previews
cat snapshots/debug_embeddings/example_md_inspection.json | jq '.chunks[0].embedding_preview'

# 3. Проверяем hash consistency
cat snapshots/debug_embeddings/example_md_inspection.json | jq '.chunks[] | {id: .chunk_id, hash: .embedding_hash}'
```

### 2. Сравнение провайдеров

**Проблема:** Хотим сравнить Gemini vs MLX embeddings.

**Решение:**
```bash
# 1. Инспектируем с Gemini
semantic inspect docs/example.md --save-artifacts --session-name gemini_run

# 2. Меняем провайдера в semantic.toml на MLX

# 3. Инспектируем с MLX
semantic inspect docs/example.md --save-artifacts --session-name mlx_run

# 4. Сравниваем
semantic compare snapshots/gemini_run/example_md_inspection.json snapshots/mlx_run/example_md_inspection.json

# Output покажет:
# - Provider Changes: GeminiEmbedder → MLXEmbedder
# - Embeddings Changed: 5 chunks (все!)
# - Performance: 1234ms → 890ms (-28%)
```

### 3. Regression testing

**Проблема:** После апдейта библиотеки embeddings изменились.

**Решение:**
```bash
# 1. Сохраняем golden snapshot ДО апдейта
semantic inspect docs/example.md --save-artifacts --session-name golden_v1.0

# 2. Апдейтим библиотеку
pip install --upgrade semantic-core

# 3. Создаём новый snapshot
semantic inspect docs/example.md --save-artifacts --session-name after_upgrade

# 4. Сравниваем
semantic compare snapshots/golden_v1.0/example_md_inspection.json snapshots/after_upgrade/example_md_inspection.json

# Если embeddings changed → расследуем регрессию!
```

### 4. CI/CD интеграция

**Проблема:** Хотим автоматически тестировать качество embeddings в CI.

**Решение:**

`.github/workflows/test_embeddings.yml`:
```yaml
name: Test Embeddings Quality

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install dependencies
        run: pip install -e .
      
      - name: Run inspection
        run: |
          semantic inspect tests/fixtures/example.md --format json > snapshot.json
      
      - name: Validate snapshot
        run: |
          # Проверяем что все чанки имеют embeddings
          chunk_count=$(jq '.chunks | length' snapshot.json)
          echo "Chunks: $chunk_count"
          
          if [ "$chunk_count" -eq 0 ]; then
            echo "Error: No chunks found!"
            exit 1
          fi
          
          # Проверяем dimension
          dimension=$(jq '.chunks[0].embedding_dimension' snapshot.json)
          echo "Dimension: $dimension"
          
          if [ "$dimension" -ne 768 ]; then
            echo "Error: Expected dimension 768, got $dimension"
            exit 1
          fi
      
      - name: Compare with golden file
        run: |
          semantic compare tests/fixtures/golden_snapshot.json snapshot.json --format json > diff.json
          
          # Проверяем что embeddings не изменились
          changed_count=$(jq '.embeddings_changes | length' diff.json)
          
          if [ "$changed_count" -gt 0 ]; then
            echo "Warning: $changed_count embeddings changed!"
            cat diff.json
          fi
```

---

## 📊 Таблица опций

### `semantic inspect`

| Опция | Короткий вариант | Тип | По умолчанию | Описание |
|-------|------------------|-----|-------------|----------|
| `--format` | `-f` | choice | `console` | Формат: console, markdown, json |
| `--save-artifacts` | - | flag | `False` | Сохранить snapshot |
| `--artifacts-root` | - | path | `./snapshots` | Путь для артефактов |
| `--session-name` | - | str | `auto` | Имя сессии |

### `semantic compare`

| Опция | Короткий вариант | Тип | По умолчанию | Описание |
|-------|------------------|-----|-------------|----------|
| `--format` | `-f` | choice | `markdown` | Формат: markdown, json |

---

## 🔗 Связанные материалы

- [README.md](README.md) — обзор Phase 16
- [02_inspector_core.md](02_inspector_core.md) — ProviderInspector и SnapshotManager
- [03_reporters.md](03_reporters.md) — Reporters (Console/Markdown/JSON/Diff)

---

**← [Назад к Phase 16](README.md)**
