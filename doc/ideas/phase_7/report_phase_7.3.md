# Отчёт Phase 7.3: Configuration & UX

> **Статус:** ✅ Завершена  
> **Дата:** 2025-12-03  
> **Ветка:** `phase_7`

---

## 1. Цель фазы

Завершить систему логирования, предоставив пользователю **удобные инструменты управления конфигурацией**:

- Environment variables для настройки без изменения кода
- Диагностические утилиты для баг-репортов
- JSON-формат для интеграции с log aggregators
- Интеграция с `SemanticCore` для удобства использования

**Проблема "до":**

```python
# Нужно вручную создавать конфиг
from semantic_core.utils.logger import setup_logging, LoggingConfig

config = LoggingConfig(level="DEBUG", log_file="/tmp/app.log")
setup_logging(config)

# Затем создавать SemanticCore
core = SemanticCore(...)
```

**Решение "после":**

```python
# Через SemanticCore напрямую
core = SemanticCore(
    embedder=embedder,
    store=store,
    splitter=splitter,
    context_strategy=context,
    log_level="DEBUG",  # NEW!
    log_file="/tmp/app.log",  # NEW!
)

# Или через environment variables
# export SEMANTIC_LOG_LEVEL=DEBUG
# export SEMANTIC_LOG_FILE=/tmp/app.log
core = SemanticCore(...)  # Конфиг подхватится автоматически

# Диагностика для баг-репортов
from semantic_core.utils.logger import dump_debug_info
print(dump_debug_info())
```

---

## 2. Ключевые решения

### 2.1 pydantic-settings вместо BaseModel

| Решение | Обоснование |
|---------|-------------|
| Миграция на `BaseSettings` | Встроенная поддержка env variables, приоритет настроек |
| Префикс `SEMANTIC_LOG_` | Namespace isolation, избежание конфликтов |
| Алиасы полей (`file` → `log_file`) | Краткость env переменных: `SEMANTIC_LOG_FILE` вместо `SEMANTIC_LOG_LOG_FILE` |
| `frozen=True` | Immutability для безопасности в многопоточном коде |

### 2.2 Приоритет настроек

pydantic-settings обеспечивает чёткий порядок:

```
1. Явный параметр в коде (highest priority)
   LoggingConfig(level="DEBUG")

2. Environment variable
   export SEMANTIC_LOG_LEVEL=INFO

3. Default value (lowest priority)
   level: str = "INFO"
```

### 2.3 Диагностика без секретов

| Требование | Реализация |
|------------|------------|
| API-ключи не в дампе | `get_environment_vars()` маскирует `*KEY*`, `*SECRET*`, `*TOKEN*` |
| Версии пакетов | Динамическое определение через `__import__` |
| SQLite extensions | Проверка загрузки `vec0` и `fts5` в runtime |

### 2.4 JSONFormatter для observability

| Поле | Источник |
|------|----------|
| `timestamp` | ISO формат с `Z` суффиксом |
| `level` | `record.levelname` |
| `logger` | `record.name` (полный путь модуля) |
| `message` | `record.getMessage()` |
| `context` | `batch_id`, `doc_id`, `chunk_id` из bind() |
| `extra` | Дополнительные поля, не входящие в стандартные |
| `location` | `file`, `line`, `function` |
| `exception` | `type`, `message`, `traceback` (если есть) |

---

## 3. Архитектура изменений

### 3.1 Модифицированные файлы

```
semantic_core/utils/logger/
├── config.py           # MODIFIED: BaseModel → BaseSettings
├── formatters.py       # MODIFIED: +JSONFormatter
├── diagnostics.py      # NEW: dump_debug_info(), check_config()
└── __init__.py         # MODIFIED: новые экспорты, docstring

semantic_core/
└── pipeline.py         # MODIFIED: log_level, log_file, logging_config параметры
```

### 3.2 Новый модуль: diagnostics.py

```
semantic_core/utils/logger/diagnostics.py
├── get_package_versions() → dict[str, str]
│   └── semantic_core, peewee, pydantic, rich, sqlite-vec
│
├── get_sqlite_info() → dict[str, str]
│   ├── sqlite_version
│   ├── vec0 (loaded/error)
│   └── fts5 (available/not available)
│
├── get_handlers_info() → list[dict]
│   └── type, level, file (если FileHandler), filters
│
├── get_environment_vars() → dict[str, str]
│   └── SEMANTIC_* переменные (с маскированием секретов)
│
├── dump_debug_info(config?) → str
│   └── Полный текстовый отчёт для баг-репортов
│
└── check_config(config?) → list[str]
    └── Список предупреждений (пустой если всё OK)
```

### 3.3 LoggingConfig после изменений

| Поле | Тип | Default | Env Variable |
|------|-----|---------|--------------|
| `level` | `LogLevel` | `"INFO"` | `SEMANTIC_LOG_LEVEL` |
| `file_level` | `LogLevel` | `"TRACE"` | `SEMANTIC_LOG_FILE_LEVEL` |
| `log_file` | `Path \| None` | `None` | `SEMANTIC_LOG_FILE` |
| `json_format` | `bool` | `False` | `SEMANTIC_LOG_JSON` |
| `show_path` | `bool` | `True` | `SEMANTIC_LOG_SHOW_PATH` |
| `redact_secrets` | `bool` | `True` | `SEMANTIC_LOG_REDACT` |
| `console_width` | `int` | `120` | `SEMANTIC_LOG_WIDTH` |

### 3.4 SemanticCore новые параметры

| Параметр | Тип | Описание |
|----------|-----|----------|
| `log_level` | `str \| None` | Быстрая настройка уровня (DEBUG/INFO/...) |
| `log_file` | `str \| Path \| None` | Путь к файлу логов |
| `logging_config` | `LoggingConfig \| None` | Полная конфигурация (приоритет) |

---

## 4. Формат dump_debug_info()

```
========================================
Semantic Core Debug Info
========================================
Generated: 2025-12-03T14:30:00.123456

[System]
Python: 3.12.1
Platform: macOS-14.1-arm64-arm-64bit
Architecture: arm64
OS: Darwin 23.1.0

[Packages]
peewee: 3.17.0
pydantic: 2.5.0
pydantic-settings: 2.1.0
rich: 13.7.0
semantic_core: unknown
sqlite-vec: installed

[Logging Config]
level: INFO
file_level: TRACE
log_file: None (console only)
json_format: False
show_path: True
redact_secrets: True
console_width: 120

[Environment Variables]
SEMANTIC_LOG_LEVEL: DEBUG
SEMANTIC_API_KEY: ***SET***

[SQLite]
sqlite_version: 3.45.0
sqlite_version_info: 3.45.0
vec0: loaded (v0.1.6)
fts5: available

[Active Handlers]
1. RichHandler (level=INFO)
   Filters: SensitiveDataFilter

========================================
```

---

## 5. JSONFormatter формат

```json
{
    "timestamp": "2025-12-03T14:30:00.123456Z",
    "level": "INFO",
    "logger": "semantic_core.pipeline",
    "message": "📥 [batch-123] Document processed",
    "context": {
        "batch_id": "batch-123",
        "doc_id": "doc-456"
    },
    "extra": {
        "chunk_count": 15,
        "duration_ms": 1250
    },
    "location": {
        "file": "pipeline.py",
        "line": 142,
        "function": "ingest"
    }
}
```

---

## 6. Разведка и анализ

### 6.1 Существующая конфигурация

Перед началом работы был проведён анализ:

- **Поиск конфигов:** `LoggingConfig` использует `BaseModel`, domain/ использует dataclass
- **Поиск инициализации:** Найдены `LoggingConfig`, `MediaConfig`, `VideoAnalysisConfig`
- **Проверка CLI:** CLI не существует (Phase 8)

### 6.2 Принятые решения по результатам разведки

| Обнаружено | Решение |
|------------|---------|
| CLI отсутствует | Пропустить CLI-опции (будет в Phase 8) |
| `LoggingConfig` уже существует | Расширить, а не создавать новый |
| `pydantic-settings` в зависимостях | Использовать `BaseSettings` |
| `SemanticCore` не имеет log-параметров | Добавить `log_level`, `log_file`, `logging_config` |

---

## 7. Отклонения от плана

| Планировалось | Реализовано | Причина |
|---------------|-------------|---------|
| CLI опции (`--log-level`) | Нет | CLI не существует, запланирован в Phase 8 |
| Интеграция с GeminiConfig | Отдельный LoggingConfig | GeminiConfig не существует, logging изолирован |
| .env файл поддержка | Только env variables | `env_file=None` — явность над магией |

---

## 8. Известные ограничения

### 8.1 Версия semantic_core

`dump_debug_info()` показывает `semantic_core: unknown` — нет `__version__` в пакете.

---

## 9. Метрики реализации

| Метрика | Значение |
|---------|----------|
| Новых файлов | 1 (diagnostics.py) |
| Изменённых файлов | 4 (config.py, formatters.py, **init**.py, pipeline.py) |
| Строк кода (prod) | ~400 |
| Новых функций | 6 |
| Новых классов | 1 (`JSONFormatter`) |

---

## 10. Definition of Done

- [x] `LoggingConfig` мигрирован на `BaseSettings` с поддержкой env variables
- [x] Prefix `SEMANTIC_LOG_` для всех переменных
- [x] `dump_debug_info()` собирает полную диагностику
- [x] API-ключи НЕ попадают в дамп (маскируются)
- [x] `check_config()` валидирует настройки
- [x] `JSONFormatter` для log aggregators
- [x] `SemanticCore` принимает `log_level`, `log_file`, `logging_config`
- [x] Все новые функции экспортируются в `__all__`
- [x] Docstrings в Google-стиле
- [x] Ошибки линтера исправлены

---

## 11. Проверка работоспособности

```bash
$ python -c "from semantic_core.utils.logger import ..."

✅ All imports successful
✅ LoggingConfig loaded: level=INFO
✅ dump_debug_info: 805 chars
✅ check_config: 0 warnings
✅ get_handlers_info: 1 handlers
✅ JSONFormatter output: {"timestamp": "2025-12-03T...

🎉 Phase 7.3 all components working!
```

---

## 12. Связанные документы

- **План:** [Phase 7.3 — Configuration & UX](phase_7.3.md)
- **Архитектура:** [35_semantic_logging.md](../../architecture/35_semantic_logging.md)
- **README:** [Logger Package](../../../semantic_core/utils/logger/README.md)
