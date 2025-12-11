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

# === Провайдеры по умолчанию (Phase 15) ===
[defaults]
embedding_provider = "gemini"        # gemini | local | openai
llm_provider = "gemini"              # gemini | openai | ollama
transcription_provider = "none"      # gemini | whisper | none
vision_provider = "none"             # gemini | local | none

# === Gemini Providers ===
[providers.gemini]
api_key = "${GEMINI_API_KEY}"        # Лучше через .env!
embedding_model = "text-embedding-004"
llm_model = "gemini-2.0-flash"
batch_key = ""                       # Отдельный ключ для Batch API

# === Local Providers (MLX/CPU) ===
[providers.local]
device = "mps"                       # mps (Apple) | cuda | cpu
embedding_model = "all-MiniLM-L6-v2"
whisper_model = "base"
vision_model = "Qwen/Qwen2.5-VL-4B"

# === OpenAI Providers ===
[providers.openai]
api_key = "${OPENAI_API_KEY}"
llm_preset = "openai"                # openai | ollama | openrouter
llm_model = "gpt-4o"
embedding_model = "text-embedding-3-large"  # Not implemented yet

# === Ollama Providers ===
[providers.ollama]
base_url = "http://localhost:11434"
model = "llama3.2:3b"

# === Обработка ===
[processing]
splitter = "smart"               # simple | smart
context_strategy = "hierarchical" # basic | hierarchical

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
| `SEMANTIC_GEMINI_API_KEY` | `gemini.api_key` |
| `SEMANTIC_GEMINI_BATCH_KEY` | `gemini.batch_key` |
| `SEMANTIC_DB_PATH` | `db_path` |
| `SEMANTIC_LOG_LEVEL` | `logging.level` |

> ⚠️ **Важно:** Все переменные требуют префикс `SEMANTIC_`!  
> `GEMINI_API_KEY` без префикса **не работает**.

### macOS / Linux

```bash
export SEMANTIC_GEMINI_API_KEY="AIzaSy..."
export SEMANTIC_LOG_LEVEL="DEBUG"
```

### Windows (PowerShell)

```powershell
$env:SEMANTIC_GEMINI_API_KEY = "AIzaSy..."
$env:SEMANTIC_LOG_LEVEL = "DEBUG"
```

### Постоянные переменные (Windows)

```powershell
# Для текущего пользователя
[Environment]::SetEnvironmentVariable("SEMANTIC_GEMINI_API_KEY", "AIzaSy...", "User")
```

---

## Multi-Provider Configuration (Phase 15) 🔌

С Phase 15 SemanticCore поддерживает разные AI провайдеры. Настройки разделены на:

1. **`[defaults]`** — какие провайдеры использовать
2. **`[providers.*]`** — настройки конкретных провайдеров

### Пример: Гибридная конфигурация

```toml
[defaults]
embedding_provider = "local"      # Локальные embeddings (экономия)
llm_provider = "gemini"           # Облачный LLM (качество)
transcription_provider = "whisper" # Локальная транскрипция (privacy)

[providers.local]
device = "mps"
embedding_model = "all-MiniLM-L6-v2"
whisper_model = "base"

[providers.gemini]
api_key = "${GEMINI_API_KEY}"
llm_model = "gemini-2.0-flash"
```

**См. также:** [Multi-Provider Architecture](../../concepts/11_multi_provider.md)

---

## Все опции (таблица) 📋

### Общие настройки

| Опция | Тип | Default | Описание |
|-------|-----|---------|----------|
| `db_path` | Path | `semantic.db` | Путь к SQLite |
| `processing.splitter` | str | `smart` | Тип сплиттера |
| `processing.context_strategy` | str | `hierarchical` | Стратегия контекста |
| `search.limit` | int | 10 | Результатов по умолчанию |
| `search.type` | str | `hybrid` | Тип поиска |
| `logging.level` | str | `INFO` | Уровень логов |
| `logging.file` | Path | null | Файл логов |

### Defaults (Phase 15)

| Опция | Тип | Default | Варианты |
|-------|-----|---------|----------|
| `defaults.embedding_provider` | str | `gemini` | gemini, local, openai |
| `defaults.llm_provider` | str | `gemini` | gemini, openai, ollama |
| `defaults.transcription_provider` | str | `none` | gemini, whisper, none |
| `defaults.vision_provider` | str | `none` | gemini, local, none |

### Gemini Provider

| Опция | Тип | Default | Описание |
|-------|-----|---------|----------|
| `providers.gemini.api_key` | str | - | API ключ |
| `providers.gemini.embedding_model` | str | `text-embedding-004` | Модель embeddings |
| `providers.gemini.llm_model` | str | `gemini-2.0-flash` | LLM модель |
| `providers.gemini.batch_key` | str | null | Ключ для Batch API |

### Local Provider (MLX/CPU)

| Опция | Тип | Default | Описание |
|-------|-----|---------|----------|
| `providers.local.device` | str | `mps` | mps, cuda, cpu |
| `providers.local.embedding_model` | str | `all-MiniLM-L6-v2` | SentenceTransformers модель |
| `providers.local.whisper_model` | str | `base` | tiny, base, small, medium, large-v3-turbo |
| `providers.local.vision_model` | str | `Qwen/Qwen2.5-VL-4B` | HuggingFace model ID |

### OpenAI Provider

| Опция | Тип | Default | Описание |
|-------|-----|---------|----------|
| `providers.openai.api_key` | str | - | API ключ |
| `providers.openai.llm_preset` | str | `openai` | openai, ollama, openrouter, vllm |
| `providers.openai.llm_model` | str | `gpt-4o` | Модель |

### Ollama Provider

| Опция | Тип | Default | Описание |
|-------|-----|---------|----------|
| `providers.ollama.base_url` | str | `http://localhost:11434` | Ollama endpoint |
| `providers.ollama.model` | str | `llama3.2:3b` | Модель |

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
