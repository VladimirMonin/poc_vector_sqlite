---
title: Опции конфигурации
description: Полный справочник всех параметров SemanticConfig
tags: [reference, config, toml, env]
---

# Опции конфигурации 📋

Полный справочник параметров `SemanticConfig`.

## Источники конфигурации 🔄

Приоритет загрузки (от высшего к низшему):

| Приоритет | Источник              | Пример                          |
| :-------: | :-------------------- | :------------------------------ |
|     1     | CLI аргументы         | `--db-path ./data.db`           |
|     2     | Environment variables | `export SEMANTIC_DB_PATH=...`   |
|     3     | semantic.toml         | `[database] path = "..."`       |
|     4     | Default values        | Встроенные значения по умолчанию |

## Параметры базы данных 💾

| Параметр  | Тип    | Default         | Описание               |
| :-------- | :----- | :-------------- | :--------------------- |
| `db_path` | `Path` | `semantic.db`   | Путь к SQLite базе     |

**Environment:** `SEMANTIC_DB_PATH`

**TOML:**
```toml
[database]
path = "data/semantic.db"
```

## Параметры Gemini API 🤖

| Параметр              | Тип            | Default                          | Описание                  |
| :-------------------- | :------------- | :------------------------------- | :------------------------ |
| `gemini_api_key`      | `str \| None`  | `None`                           | API ключ (обязательный)   |
| `gemini_batch_key`    | `str \| None`  | `None`                           | Ключ для Batch API        |
| `embedding_model`     | `str`          | `models/gemini-embedding-001`    | Модель эмбеддингов        |
| `embedding_dimension` | `int`          | `768`                            | Размерность (256–3072)    |

**Environment:**
```bash
# Без префикса (совместимость)
export GEMINI_API_KEY=AIza...

# С префиксом
export SEMANTIC_GEMINI_API_KEY=AIza...
export SEMANTIC_GEMINI_BATCH_KEY=AIza...
export SEMANTIC_EMBEDDING_MODEL=models/gemini-embedding-001
export SEMANTIC_EMBEDDING_DIMENSION=1536
```

**TOML:**
```toml
[gemini]
api_key = "AIza..."
batch_key = "AIza..."  # опционально
model = "models/gemini-embedding-001"
embedding_dimension = 768
```

## Параметры обработки 🔧

| Параметр           | Тип                       | Default         | Описание                 |
| :----------------- | :------------------------ | :-------------- | :----------------------- |
| `splitter`         | `simple \| smart`         | `smart`         | Тип сплиттера            |
| `context_strategy` | `basic \| hierarchical`   | `hierarchical`  | Стратегия контекста      |

**Типы сплиттеров:**

| Значение | Описание                                    |
| :------- | :------------------------------------------ |
| `simple` | Наивная нарезка по символам                 |
| `smart`  | AST-парсинг Markdown, сохранение структуры  |

**Стратегии контекста:**

| Значение        | Описание                              |
| :-------------- | :------------------------------------ |
| `basic`         | Только содержимое чанка               |
| `hierarchical`  | Иерархия заголовков + родитель        |

**Environment:**
```bash
export SEMANTIC_SPLITTER=smart
export SEMANTIC_CONTEXT_STRATEGY=hierarchical
```

**TOML:**
```toml
[processing]
splitter = "smart"
context_strategy = "hierarchical"
```

## Параметры медиа 🖼️

| Параметр          | Тип    | Default | Описание                          |
| :---------------- | :----- | :------ | :-------------------------------- |
| `media_enabled`   | `bool` | `true`  | Включить обработку медиа          |
| `media_rpm_limit` | `int`  | `15`    | Rate limit Vision/Audio (1–100)   |

**Environment:**
```bash
export SEMANTIC_MEDIA_ENABLED=true
export SEMANTIC_MEDIA_RPM_LIMIT=15
```

**TOML:**
```toml
[media]
enabled = true
rpm_limit = 15
```

## Параметры поиска 🔍

| Параметр       | Тип                       | Default   | Описание                    |
| :------------- | :------------------------ | :-------- | :-------------------------- |
| `search_limit` | `int`                     | `10`      | Результатов по умолчанию    |
| `search_type`  | `vector \| fts \| hybrid` | `hybrid`  | Тип поиска по умолчанию     |

**Типы поиска:**

| Значение | Описание                                  |
| :------- | :---------------------------------------- |
| `vector` | Только семантический поиск                |
| `fts`    | Только полнотекстовый (FTS5)              |
| `hybrid` | Комбинация vector + fts через RRF         |

**Environment:**
```bash
export SEMANTIC_SEARCH_LIMIT=20
export SEMANTIC_SEARCH_TYPE=hybrid
```

**TOML:**
```toml
[search]
limit = 10
type = "hybrid"
```

## Параметры логирования 📝

| Параметр    | Тип            | Default | Описание                         |
| :---------- | :------------- | :------ | :------------------------------- |
| `log_level` | `LogLevel`     | `INFO`  | Уровень логирования              |
| `log_file`  | `Path \| None` | `None`  | Файл логов (None = только консоль) |

**Уровни логирования:**

| Уровень    | Описание                              |
| :--------- | :------------------------------------ |
| `TRACE`    | Детальная отладка (кастомный уровень) |
| `DEBUG`    | Отладочная информация                 |
| `INFO`     | Информационные сообщения              |
| `WARNING`  | Предупреждения                        |
| `ERROR`    | Ошибки                                |
| `CRITICAL` | Критические ошибки                    |

**Environment:**
```bash
export SEMANTIC_LOG_LEVEL=DEBUG
export SEMANTIC_LOG_FILE=logs/semantic.log
```

**TOML:**
```toml
[logging]
level = "INFO"
file = "logs/semantic.log"
```

## Полный пример semantic.toml 📄

```toml
# Semantic Core Configuration

[database]
path = "data/semantic.db"

[gemini]
api_key = "AIza..."
model = "models/gemini-embedding-001"
embedding_dimension = 768

[processing]
splitter = "smart"
context_strategy = "hierarchical"

[media]
enabled = true
rpm_limit = 15

[search]
limit = 10
type = "hybrid"

[logging]
level = "INFO"
# file = "logs/semantic.log"  # раскомментировать для файлового логирования
```

## Программный доступ 🐍

```python
from semantic_core.config import SemanticConfig, get_config

# Автоматическая загрузка (env + TOML)
config = SemanticConfig()

# С override'ами
config = get_config(
    db_path="custom.db",
    log_level="DEBUG",
    search_limit=20,
)

# Чтение значений
print(config.db_path)           # Path('custom.db')
print(config.embedding_model)   # 'models/gemini-embedding-001'
print(config.search_type)       # 'hybrid'
```

## См. также 🔗

- [Конфигурация (гайд)](../guides/core/configuration.md) — практическое руководство
- [CLI команды](cli-commands.md) — использование `config` команды
