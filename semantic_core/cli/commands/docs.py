"""Команда docs для CLI.

Встроенная документация по Semantic Core.

Usage:
    semantic docs           # Список доступных топиков
    semantic docs search    # Документация по поиску
    semantic docs config    # Документация по конфигурации
"""

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table


docs_cmd = typer.Typer(
    name="docs",
    help="Встроенная документация по Semantic Core",
)

console = Console()


# Встроенная документация
DOCS_TOPICS = {
    "overview": {
        "title": "📚 Обзор Semantic Core",
        "content": """
# Semantic Core

**Semantic Core** — production-ready библиотека для локального семантического
поиска и мультимодального анализа.

## Философия

- **Local-First:** SQLite (`vec0` + `fts5`) вместо векторных БД
- **Gemini-Powered:** Интеллект через Google Gemini
- **Modular:** SOLID архитектура

## Быстрый старт

```bash
# Инициализация проекта
semantic init

# Индексация документов
semantic ingest ./docs/ --recursive --pattern "*.md"

# Поиск
semantic search "как работает эмбеддинг"
```

## Ссылки

- `semantic docs search` — подробнее о поиске
- `semantic docs config` — настройка конфигурации
- `semantic docs ingest` — индексация документов
""",
    },
    "search": {
        "title": "🔍 Поиск",
        "content": """
# Типы поиска

Semantic Core поддерживает три режима поиска:

## 1. Vector Search (семантический)

Поиск по смыслу через векторные эмбеддинги.

```bash
semantic search "обработка ошибок" --type vector
```

Лучше всего подходит для:
- Поиска по смыслу, а не по ключевым словам
- Нахождения концептуально похожих документов

## 2. FTS Search (полнотекстовый)

Классический полнотекстовый поиск через SQLite FTS5.

```bash
semantic search "rate limiting" --type fts
```

Лучше всего подходит для:
- Точного поиска по ключевым словам
- Поиска технических терминов, имён, ID

## 3. Hybrid Search (гибридный)

Объединение векторного и FTS через Reciprocal Rank Fusion (RRF).

```bash
semantic search "запрос" --type hybrid --k 60
```

**Параметр `--k`** управляет балансом:
- Меньше k → больше веса топовым результатам
- Больше k → более равномерное распределение

## Параметры

| Опция | Описание |
|-------|----------|
| `--limit, -l` | Количество результатов (по умолчанию 10) |
| `--type, -t` | Тип поиска: vector, fts, hybrid |
| `--threshold, -T` | Минимальный порог релевантности (0.0-1.0) |
| `--k` | Параметр RRF для гибридного поиска |
| `--verbose, -v` | Детальная информация о результатах |
""",
    },
    "ingest": {
        "title": "📥 Индексация",
        "content": """
# Индексация документов

## Базовое использование

```bash
# Один файл
semantic ingest document.md

# Директория (все файлы)
semantic ingest ./docs/

# Рекурсивно с фильтром
semantic ingest ./docs/ --recursive --pattern "*.md"
```

## Режимы обработки

### Sync (синхронный)

По умолчанию. Документ обрабатывается сразу.

```bash
semantic ingest doc.md --mode sync
```

### Async (асинхронный)

Документ добавляется в очередь для batch-обработки.

```bash
semantic ingest doc.md --mode async
```

## Медиа-файлы

При индексации медиа можно включить обогащение через Gemini:

```bash
semantic ingest ./images/ -r -e  # --enrich-media
```

Поддерживаемые форматы:
- **Изображения:** jpg, png, gif, webp
- **Аудио:** mp3, wav, ogg, flac
- **Видео:** mp4, avi, mov, mkv

## Опции

| Опция | Описание |
|-------|----------|
| `--mode, -m` | Режим: sync (по умолчанию), async |
| `--pattern, -p` | Glob-паттерн для фильтрации файлов |
| `--recursive, -r` | Рекурсивный обход директорий |
| `--enrich-media, -e` | Анализировать медиа через Gemini |
| `--dry-run, -n` | Показать файлы без индексации |
""",
    },
    "config": {
        "title": "⚙️ Конфигурация",
        "content": """
# Конфигурация Semantic Core

## Файл конфигурации

Semantic Core использует TOML-файл `semantic.toml`:

```toml
# Путь к базе данных
db_path = "semantic.db"

# Уровень логирования (DEBUG, INFO, WARNING, ERROR)
log_level = "INFO"

# Модель для эмбеддингов
embedding_model = "text-embedding-004"

# Размерность векторов
embedding_dimensions = 768
```

## Переопределение через CLI

Любые параметры можно переопределить:

```bash
semantic --db-path custom.db search "запрос"
semantic --log-level DEBUG ingest doc.md
```

## Переменные окружения

API-ключ можно задать через:

```bash
export GOOGLE_API_KEY=your_key_here
```

Или через файл `.env` в корне проекта.

## Команды управления

```bash
# Показать текущую конфигурацию
semantic config show

# Показать путь к файлу
semantic config path

# Проверить здоровье системы
semantic doctor
```
""",
    },
    "api": {
        "title": "🔌 Python API",
        "content": """
# Использование как Python библиотеки

## Инициализация

```python
from semantic_core import SemanticCore
from semantic_core.domain import Document

# Автоматическая конфигурация
core = SemanticCore.from_config("semantic.toml")

# Или ручная настройка
from semantic_core.infrastructure.gemini import GeminiEmbedder
from semantic_core.infrastructure.storage import PeeweeVectorStore

embedder = GeminiEmbedder(api_key="...")
store = PeeweeVectorStore("semantic.db")
core = SemanticCore(embedder=embedder, store=store)
```

## Индексация

```python
doc = Document(
    content="Текст документа...",
    metadata={"title": "Мой документ", "author": "Иван"},
)

core.ingest(doc)
```

## Поиск

```python
results = core.search(
    query="семантический поиск",
    limit=10,
    mode="hybrid",  # vector, fts, hybrid
)

for r in results:
    print(f"Score: {r.score:.3f}")
    print(f"Content: {r.content[:100]}...")
```

## Batch API

```python
from semantic_core import BatchManager

batch = BatchManager(core)
batch.add_document(doc1)
batch.add_document(doc2)
batch.process()  # Экономия через Batch API
```
""",
    },
}


@docs_cmd.callback(invoke_without_command=True)
def docs(
    ctx: typer.Context,
    topic: Optional[str] = typer.Argument(
        None,
        help="Топик документации (overview, search, ingest, config, api)",
    ),
) -> None:
    """Показать встроенную документацию.

    Без аргументов показывает список доступных топиков.

    Примеры:
        semantic docs
        semantic docs search
        semantic docs config
    """
    if topic is None:
        _show_topics_list()
    elif topic in DOCS_TOPICS:
        _show_topic(topic)
    else:
        console.print(Panel(
            f"[red]Неизвестный топик: {topic}[/red]\n\n"
            f"Доступные топики: {', '.join(DOCS_TOPICS.keys())}",
            title="❌ Ошибка",
        ))
        raise typer.Exit(1)


def _show_topics_list() -> None:
    """Показывает список доступных топиков."""
    console.print(Panel(
        "[cyan]Semantic Core — встроенная документация[/cyan]",
        title="📚 Документация",
    ))

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Топик", width=15)
    table.add_column("Описание")

    topics_info = {
        "overview": "Обзор библиотеки и быстрый старт",
        "search": "Типы поиска и параметры",
        "ingest": "Индексация документов и медиа",
        "config": "Конфигурация и настройка",
        "api": "Использование как Python библиотеки",
    }

    for topic_key, desc in topics_info.items():
        topic_data = DOCS_TOPICS.get(topic_key, {})
        icon = topic_data.get("title", "").split()[0] if topic_data else "📄"
        table.add_row(f"{icon} {topic_key}", desc)

    console.print(table)
    console.print("\n[dim]Используйте: semantic docs <топик>[/dim]")


def _show_topic(topic: str) -> None:
    """Отображает конкретный топик документации."""
    topic_data = DOCS_TOPICS[topic]
    console.print(Panel(
        Markdown(topic_data["content"]),
        title=topic_data["title"],
        border_style="blue",
    ))
