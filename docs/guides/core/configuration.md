---
title: "Configuration"
description: "Настройка Semantic Core через semantic.toml, env и CLI"
tags: ["configuration", "toml", "settings", "env"]
difficulty: "beginner"
prerequisites: ["quickstart"]
---

# Configuration ⚙️

> Гибкая конфигурация: CLI args → env → semantic.toml → defaults.

---

## Что получим 🎯

- Понимание иерархии настроек
- Рабочий semantic.toml
- Знание всех доступных опций

---

## Иерархия приоритетов 📊

```
┌─────────────────────────────────────────────┐
│     CLI Arguments (высший приоритет)        │
│     semantic search --limit 20              │
├─────────────────────────────────────────────┤
│     Environment Variables                    │
│     SEMANTIC_LOG_LEVEL=DEBUG                │
├─────────────────────────────────────────────┤
│     semantic.toml                           │
│     log_level = "INFO"                      │
├─────────────────────────────────────────────┤
│     Default Values (низший приоритет)       │
│     log_level = "INFO"                      │
└─────────────────────────────────────────────┘
```

---

## semantic.toml 📄

Создайте файл `semantic.toml` в корне проекта:

```toml
# semantic.toml — главный конфигурационный файл

# === База данных ===
db_path = "semantic.db"

# === Gemini API ===
[gemini]
api_key = "AIza..."              # Лучше через .env!
batch_key = "AIza..."            # Отдельный ключ для Batch API

# === Модели ===
[embedding]
model = "models/gemini-embedding-001"
dimension = 768                  # MRL: 768 / 1536 / 3072

# === Обработка ===
[processing]
splitter = "smart"               # simple | smart
context_strategy = "hierarchical" # basic | hierarchical

# === Медиа ===
[media]
enabled = true
rpm_limit = 15                   # Rate limit Vision API

# === Поиск ===
[search]
limit = 10
type = "hybrid"                  # vector | fts | hybrid

# === Логирование ===
[logging]
level = "INFO"                   # TRACE | DEBUG | INFO | WARNING | ERROR
file = "logs/semantic.log"       # null = только консоль
```

---

## Auto-Discovery 🔍

Semantic Core ищет `semantic.toml` вверх по дереву директорий:

```
project/
├── semantic.toml    ← Найден!
├── src/
│   └── app.py       ← Запуск отсюда
└── docs/
```

Поиск идёт от текущей директории до корня (максимум 10 уровней).

---

## Environment Variables 🌍

Все настройки доступны через env с префиксом `SEMANTIC_`:

| Переменная | semantic.toml эквивалент |
|------------|-------------------------|
| `GEMINI_API_KEY` | `gemini.api_key` |
| `GEMINI_BATCH_KEY` | `gemini.batch_key` |
| `SEMANTIC_DB_PATH` | `db_path` |
| `SEMANTIC_LOG_LEVEL` | `logging.level` |
| `SEMANTIC_SPLITTER` | `processing.splitter` |
| `SEMANTIC_SEARCH_TYPE` | `search.type` |

**.env файл** читается автоматически:

```bash
# .env
GEMINI_API_KEY=AIzaSy...
SEMANTIC_LOG_LEVEL=DEBUG
```

---

## Все опции (таблица) 📋

| Опция | Тип | Default | Описание |
|-------|-----|---------|----------|
| `db_path` | Path | `semantic.db` | Путь к SQLite |
| `gemini.api_key` | str | - | API ключ Gemini |
| `gemini.batch_key` | str | null | Отдельный ключ для Batch |
| `embedding.model` | str | `gemini-embedding-001` | Модель эмбеддингов |
| `embedding.dimension` | int | 768 | Размерность векторов |
| `processing.splitter` | str | `smart` | Тип сплиттера |
| `processing.context_strategy` | str | `hierarchical` | Стратегия контекста |
| `media.enabled` | bool | true | Обработка медиа |
| `media.rpm_limit` | int | 15 | Rate limit Vision API |
| `search.limit` | int | 10 | Результатов по умолчанию |
| `search.type` | str | `hybrid` | Тип поиска |
| `logging.level` | str | `INFO` | Уровень логов |
| `logging.file` | Path | null | Файл логов |

---

## CLI Override 🖥️

CLI аргументы переопределяют всё:

```bash
# Переопределение db_path
semantic search "query" --db-path /custom/path.db

# Переопределение log level
semantic ingest ./docs/ --log-level DEBUG

# JSON output (для скриптов)
semantic search "query" --json
```

---

## Проверка ✅

```bash
# Показать текущую конфигурацию
semantic config show

# Валидация конфигурации
semantic doctor
```

---

## Пресеты конфигурации 🎛️

### Максимальная экономия

```toml
[embedding]
dimension = 768                  # Минимальная размерность

[gemini]
batch_key = "AIza..."            # Batch API = -50% cost
```

### Максимальное качество

```toml
[embedding]
dimension = 3072                 # Полная размерность

[processing]
splitter = "smart"
context_strategy = "hierarchical"
```

### Development

```toml
[logging]
level = "DEBUG"
file = "logs/dev.log"

[media]
rpm_limit = 5                    # Медленнее, но безопаснее
```

---

## Частые проблемы ⚠️

| Проблема | Решение |
|----------|---------|
| `Config file not found` | Создайте semantic.toml |
| `Invalid TOML syntax` | Проверьте синтаксис (кавычки, секции) |
| `API key not set` | Добавьте в .env или semantic.toml |
| `Dimension mismatch` | Переиндексируйте после смены dimension |

---

## Следующие шаги 🔗

| Гайд | Что узнаете |
|------|-------------|
| [CLI Usage](cli-usage.md) | Все команды CLI |
| [Model Configuration](model-configuration.md) | Выбор моделей Gemini |
| [Configuration Reference](../../reference/configuration.md) | Полный справочник |
