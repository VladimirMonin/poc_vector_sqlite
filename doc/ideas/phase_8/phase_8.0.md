````markdown
# 📋 Phase 8.0: Core CLI — Базовый интерфейс

**Статус:** 🔲 Планируется  
**Зависимости:** Phase 8.3 (Config & Init) ✅, Phase 7.0 (Logging Core) ✅

---

## 🎯 Цель

Создать минимальный, но полнофункциональный CLI для взаимодействия с SemanticCore:
- **ingest** — загрузка документов в базу
- **search** — семантический поиск
- **docs** — встроенная документация в терминале

---

## 🧠 Философия дизайна

### Human-Friendly + Machine-Readable

CLI имеет два "лица":

1. **Для человека:** Rich-таблицы, спиннеры, Markdown-рендеринг, эмодзи
2. **Для скриптов:** Флаг `--json` отключает красоту, выдаёт чистые данные

### Thin Client

CLI — это **тонкий клиент**. Вся логика в ядре (`SemanticCore`, `BatchManager`).
CLI занимается только:
- Парсингом аргументов (Typer)
- Презентацией данных (Rich)
- Обработкой сигналов (Ctrl+C)

---

## 📦 Структура пакета

```text
semantic_core/cli/
├── __init__.py           # main() entry point
├── app.py                # Typer приложение, глобальные callback'и
├── context.py            # CLIContext (DI контейнер)
├── console.py            # Rich Console singleton
├── commands/             # Группы команд (sub-apps)
│   ├── __init__.py
│   ├── ingest.py         # semantic ingest <path>
│   ├── search.py         # semantic search "query"
│   └── docs.py           # semantic docs <topic>
└── ui/                   # Слой представления
    ├── __init__.py
    ├── renderers.py      # render_results_table, render_chunk
    └── spinners.py       # Контекстные менеджеры прогресса
```

---

## 🔧 Зависимости

**Добавить в `pyproject.toml`:**

```toml
[project.dependencies]
# ... существующие ...
"typer[all]>=0.9.0"       # CLI framework (включает rich, click)
```

**Примечание:** `typer[all]` включает `rich` и `shellingham` для автодополнения.

**Точка входа:**

```toml
[project.scripts]
semantic = "semantic_core.cli:main"
```

---

## 📐 Модуль `app.py` — Главное приложение

### Глобальные опции

```python
import typer
from typing import Optional
from pathlib import Path

app = typer.Typer(
    name="semantic",
    help="🧠 Semantic Core CLI — Ваш второй мозг в терминале.",
    add_completion=True,
)

@app.callback()
def main_callback(
    ctx: typer.Context,
    db_path: Optional[Path] = typer.Option(
        None, "--db-path", "-d",
        help="Путь к SQLite базе данных",
    ),
    log_level: str = typer.Option(
        "WARNING", "--log-level", "-l",
        help="Уровень логирования: TRACE, DEBUG, INFO, WARNING, ERROR",
    ),
    json_output: bool = typer.Option(
        False, "--json", "-j",
        help="Вывод в формате JSON (для скриптов)",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Подробный вывод (эквивалент --log-level INFO)",
    ),
):
    """Инициализация контекста для всех команд."""
    # Создаём CLIContext и сохраняем в ctx.obj
    ...
```

### Монтирование команд

```python
from semantic_core.cli.commands import ingest, search, docs

app.add_typer(ingest.app, name="ingest")
app.add_typer(search.app, name="search")  # Или просто команда, не группа
app.add_typer(docs.app, name="docs")
```

---

## 📐 Модуль `context.py` — Контейнер зависимостей

```python
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
from rich.console import Console

from semantic_core import SemanticCore
from semantic_core.config import SemanticConfig
from semantic_core.batch_manager import BatchManager
from semantic_core.utils.logger import setup_logging, LoggingConfig

@dataclass
class CLIContext:
    """Контейнер зависимостей для CLI команд.
    
    Использует SemanticConfig (Phase 8.3) для загрузки настроек.
    Все компоненты создаются лениво для быстрого --help.
    """
    
    # CLI overrides (приоритет над config)
    db_path: Optional[Path] = None
    log_level: Optional[str] = None
    json_output: bool = False
    console: Console = field(default_factory=Console)
    
    # Ленивая инициализация
    _config: Optional[SemanticConfig] = field(default=None, init=False)
    _core: Optional[SemanticCore] = field(default=None, init=False)
    _batch_manager: Optional[BatchManager] = field(default=None, init=False)
    
    def get_config(self) -> SemanticConfig:
        """Загрузить конфигурацию (с учётом CLI overrides)."""
        if self._config is None:
            # CLI аргументы имеют приоритет
            overrides = {}
            if self.db_path:
                overrides["db_path"] = self.db_path
            if self.log_level:
                overrides["log_level"] = self.log_level
            
            self._config = SemanticConfig(**overrides)
        return self._config
    
    def get_core(self) -> SemanticCore:
        """Получить или создать экземпляр SemanticCore."""
        if self._core is None:
            config = self.get_config()
            self._init_logging(config)
            self._core = self._build_core(config)
        return self._core
    
    def get_batch_manager(self) -> BatchManager:
        """Получить BatchManager (для queue команд)."""
        if self._batch_manager is None:
            config = self.get_config()
            if not config.gemini_batch_key:
                raise RuntimeError(
                    "GEMINI_BATCH_KEY not configured. "
                    "Run 'semantic doctor' for diagnostics."
                )
            self._batch_manager = self._build_batch_manager(config)
        return self._batch_manager
    
    def _init_logging(self, config: SemanticConfig) -> None:
        """Настройка логирования из конфига."""
        log_config = LoggingConfig(
            level=config.log_level,
            log_file=config.log_file,
        )
        setup_logging(log_config)
    
    def _build_core(self, config: SemanticConfig) -> SemanticCore:
        """Сборка SemanticCore из конфига."""
        # Выбор компонентов по конфигу
        from semantic_core.infrastructure.gemini import GeminiEmbedder
        from semantic_core.infrastructure.storage.peewee import (
            PeeweeVectorStore,
            init_peewee_database,
        )
        from semantic_core.processing.splitters import SmartSplitter, SimpleSplitter
        from semantic_core.processing.context import (
            HierarchicalContextStrategy,
            BasicContextStrategy,
        )
        
        # Database
        db = init_peewee_database(config.db_path, config.embedding_dimension)
        
        # Embedder
        embedder = GeminiEmbedder(
            api_key=config.gemini_api_key,
            model_name=config.embedding_model,
            dimension=config.embedding_dimension,
        )
        
        # Store
        store = PeeweeVectorStore(database=db)
        
        # Splitter (по конфигу)
        splitter = (
            SmartSplitter() if config.splitter == "smart"
            else SimpleSplitter()
        )
        
        # Context Strategy (по конфигу)
        context_strategy = (
            HierarchicalContextStrategy() if config.context_strategy == "hierarchical"
            else BasicContextStrategy()
        )
        
        return SemanticCore(
            embedder=embedder,
            store=store,
            splitter=splitter,
            context_strategy=context_strategy,
        )
    
    def _build_batch_manager(self, config: SemanticConfig) -> BatchManager:
        """Сборка BatchManager из конфига."""
        from semantic_core.domain import GoogleKeyring
        
        keyring = GoogleKeyring(
            default=config.gemini_api_key,
            batch=config.gemini_batch_key,
        )
        
        return BatchManager(
            keyring=keyring,
            vector_store=self.get_core().store,
            model_name=config.embedding_model,
            dimension=config.embedding_dimension,
        )
```

---

## 📐 Команда `ingest` — Загрузка данных

**Файл:** `commands/ingest.py`

### Сигнатура

```bash
semantic ingest <path> [OPTIONS]
```

### Опции

| Опция | Тип | Описание |
|-------|-----|----------|
| `<path>` | PATH | Файл или папка для загрузки |
| `--mode` | sync/async | Режим обработки (default: sync) |
| `--pattern` | TEXT | Glob-паттерн для фильтрации файлов в папке |
| `--recursive / --no-recursive` | FLAG | Рекурсивный обход папок (default: True) |

### Логика

1. Если `path` — файл: `core.ingest(path, mode=mode)`
2. Если `path` — папка:
   - Собрать файлы по `pattern` (default: `*.md`)
   - Для каждого: `core.ingest(file)` с Rich Progress

### UX

```
$ semantic ingest ./docs/

📥 Ingesting documents from ./docs/
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:05
✅ Ingested 12 documents, 156 chunks created
   Pending in queue: 3 images, 1 audio
```

### JSON Output

```json
{
  "status": "success",
  "documents": 12,
  "chunks": 156,
  "queue": {"images": 3, "audio": 1}
}
```

---

## 📐 Команда `search` — Семантический поиск

**Файл:** `commands/search.py`

### Сигнатура

```bash
semantic search "query" [OPTIONS]
```

### Опции

| Опция | Тип | Описание |
|-------|-----|----------|
| `"query"` | TEXT | Поисковый запрос |
| `--limit` | INT | Количество результатов (default: 5) |
| `--type` | all/vector/hybrid | Тип поиска (default: hybrid) |
| `--threshold` | FLOAT | Минимальный score (default: 0.0) |

### Логика

```python
results = core.search(
    query=query,
    limit=limit,
    search_type=search_type,
)
```

### UX — Rich Table

```
$ semantic search "как установить библиотеку" --limit 3

🔍 Search: "как установить библиотеку" (hybrid, limit=3)

┏━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Score ┃ Preview                              ┃ Source                 ┃
┡━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 0.92 │ Установка через pip: pip install... │ docs/install.md:12     │
│ 0.87 │ Для начала работы выполните...      │ docs/quickstart.md:5   │
│ 0.81 │ Зависимости: Python 3.10+...        │ docs/requirements.md:1 │
└──────┴──────────────────────────────────────┴────────────────────────┘

💡 Tip: Use 'semantic search "query" --type vector' for pure vector search
```

### JSON Output

```json
{
  "query": "как установить библиотеку",
  "results": [
    {"score": 0.92, "content": "...", "source": "docs/install.md", "line": 12},
    ...
  ]
}
```

---

## 📐 Команда `docs` — Встроенная документация

**Файл:** `commands/docs.py`

### Сигнатура

```bash
semantic docs [topic]
```

### Темы (topics)

| Topic | Файл | Описание |
|-------|------|----------|
| `overview` | `00_overview.md` | Оглавление документации |
| `architecture` | `06_project_architecture.md` | Архитектура проекта |
| `search` | `04_search_types.md` | Типы поиска |
| `batch` | `21_batch_api_economics.md` | Batch API |
| `logging` | `35_semantic_logging.md` | Система логирования |

**Без аргумента:** Показывает список доступных тем.

### Логика

1. Маппинг `topic` → путь к MD файлу
2. Чтение файла из пакета (или из файловой системы в dev mode)
3. Рендеринг через `rich.markdown.Markdown`

### UX

```
$ semantic docs search

📚 Documentation: Search Types

────────────────────────────────────────────────────────────────
## 🔍 Типы поиска

Semantic Core поддерживает три режима поиска:

1. **Vector Search** — семантический поиск по смыслу
2. **Exact Search** — точное совпадение + FTS5
3. **Hybrid Search** — комбинация через RRF
...
────────────────────────────────────────────────────────────────

💡 Tip: Use 'semantic docs' to see all available topics
```

---

## 🎨 Слой представления `ui/`

### `renderers.py`

```python
def render_search_results(results: list, console: Console) -> None:
    """Вывод результатов поиска в виде таблицы."""

def render_ingest_summary(stats: dict, console: Console) -> None:
    """Вывод итогов загрузки."""

def render_error(exc: Exception, console: Console, verbose: bool = False) -> None:
    """Красивый вывод ошибки (с трейсбеком в verbose)."""

def render_success(message: str, console: Console) -> None:
    """Зелёная галочка с сообщением."""
```

### `spinners.py`

```python
@contextmanager
def progress_spinner(console: Console, description: str):
    """Контекстный менеджер для спиннера."""
    with console.status(description, spinner="dots"):
        yield

@contextmanager  
def progress_bar(console: Console, total: int, description: str):
    """Контекстный менеджер для прогресс-бара."""
    ...
```

---

## 🔤 CLI Эмодзи (идея для логгера)

**Обсуждение:** Нужны ли отдельные эмодзи для CLI модулей?

| Паттерн | Эмодзи | Комментарий |
|---------|--------|-------------|
| `cli`, `commands` | 🖥️ | CLI операции |
| `ingest` (CLI) | 📥 | Уже есть для pipeline |
| `search` (CLI) | 🔍 | Уже есть для search |
| `docs` | 📚 | Документация |
| `worker` | 👷 | Фоновые задачи |
| `queue` | 📦 | Уже есть для batch |

**Вывод:** Большинство эмодзи уже есть. Добавить только:
- `cli` → 🖥️ (общий для CLI модулей)
- `docs` → 📚 (для команды docs)
- `worker` → 👷 (для Phase 8.1)

**Решение:** Отложить до Phase 8.1, когда будет ясна полная картина.

---

## ✅ Acceptance Criteria

### Функциональные

1. [ ] Команда `semantic --help` выводит красивое меню
2. [ ] `semantic ingest <file>` загружает один файл
3. [ ] `semantic ingest <folder>` загружает папку рекурсивно
4. [ ] `semantic search "query"` возвращает результаты в Rich-таблице
5. [ ] `semantic docs` показывает список тем
6. [ ] `semantic docs <topic>` рендерит MD в терминале
7. [ ] Флаг `--json` работает для ingest и search
8. [ ] Флаг `--log-level` настраивает логирование

### Качество

9. [ ] `--help` работает мгновенно (ленивая загрузка ядра)
10. [ ] Ошибки выводятся красиво через Rich Panel
11. [ ] Ctrl+C корректно прерывает операции

### Тесты

12. [ ] Unit-тесты на парсинг аргументов
13. [ ] Integration-тесты на CLI через `CliRunner`

---

## 📚 Документация (после реализации)

### Архитектурный сериал

1. **Episode 39:** `39_cli_architecture.md` — Модульная архитектура CLI
   - Паттерн Command as Service
   - Typer + Rich интеграция
   - Ленивая загрузка ядра

2. **Episode 40:** `40_cli_ux_patterns.md` — UX паттерны CLI
   - Human vs Machine output
   - Rich Tables, Spinners, Progress
   - Error presentation

### README обновления

- Добавить секцию "CLI Usage" в главный README
- Примеры команд для быстрого старта

### Логирование

- CLI модули используют существующий `get_logger(__name__)`
- Паттерны `cli`, `commands` добавить в EMOJI_MAP (если решим)

---

## 🔗 Связанные документы

- **Предыдущая:** [Phase 8.3 — Config & Init](phase_8.3.md) (обязательная зависимость)
- **Исходный план:** [Phase 8 — CLI Architecture](phase_8.md)
- **Следующая:** [Phase 8.1 — Operations CLI](phase_8.1.md)
- **Logging:** [Phase 7.0 — Logging Core](../phase_7/phase_7.0.md)

````
