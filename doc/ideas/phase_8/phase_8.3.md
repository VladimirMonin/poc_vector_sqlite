````markdown
# 📋 Phase 8.3: Config & Init — Управление конфигурацией

**Статус:** 🔲 Планируется  
**Зависимости:** Phase 7.0 (Logging Core) ✅  
**Приоритет:** 🔴 Высокий (ПЕРВАЯ фаза CLI — фундамент для остальных)

---

## 🎯 Цель

Создать **фундамент CLI** — единую систему конфигурации и диагностики:
- **SemanticConfig** — единый Pydantic Settings класс для всей библиотеки
- **init** — создание конфиг-файла в проекте
- **config** — просмотр и валидация настроек
- **doctor** — диагностика окружения

> **Почему это первая фаза?**  
> Все остальные CLI команды (ingest, search, queue, chat) зависят от конфигурации.
> Без единого `SemanticConfig` каждая команда создавала бы компоненты по-своему.

---

## 📦 Новые модули

```text
semantic_core/
├── config.py             # SemanticConfig (Pydantic Settings)
└── cli/
    ├── __init__.py       # main() entry point
    ├── app.py            # Typer приложение
    ├── context.py        # CLIContext (использует SemanticConfig)
    ├── console.py        # Rich Console singleton
    └── commands/
        ├── __init__.py
        ├── init.py       # semantic init
        ├── config.py     # semantic config show/check
        └── doctor.py     # semantic doctor
```

---

## 🔧 Единый SemanticConfig

**Файл:** `semantic_core/config.py`

Это **центральный модуль конфигурации** всей библиотеки. Заменяет legacy `config.py` в корне проекта.

```python
"""Единая конфигурация Semantic Core.

Загружает настройки из (в порядке приоритета):
1. CLI аргументы (--db-path, --log-level)
2. Environment variables (SEMANTIC_*, GEMINI_API_KEY)
3. semantic.toml в текущей директории
4. Default values
"""

from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SemanticConfig(BaseSettings):
    """Единая конфигурация Semantic Core.
    
    Все секции объединены в один flat namespace для простоты.
    TOML-файл может использовать вложенные секции, они будут
    преобразованы через env_nested_delimiter.
    
    Attributes:
        db_path: Путь к SQLite базе данных.
        gemini_api_key: API ключ для Gemini (обязательный).
        gemini_batch_key: Отдельный ключ для Batch API (опционально).
        embedding_model: Модель для эмбеддингов.
        embedding_dimension: Размерность векторов.
        splitter: Тип сплиттера (simple/smart).
        context_strategy: Стратегия контекста (basic/hierarchical).
        media_enabled: Включить обработку медиа.
        media_rpm_limit: Rate limit для Vision API.
        search_limit: Лимит результатов по умолчанию.
        search_type: Тип поиска по умолчанию.
        log_level: Уровень логирования.
        log_file: Путь к файлу логов.
    
    Environment Variables:
        GEMINI_API_KEY: API ключ (без префикса SEMANTIC_)
        GEMINI_BATCH_KEY: Batch API ключ
        SEMANTIC_DB_PATH: Путь к БД
        SEMANTIC_LOG_LEVEL: Уровень логов
        SEMANTIC_SPLITTER: Тип сплиттера
        ... и другие с префиксом SEMANTIC_
    """
    
    # === Database ===
    db_path: Path = Field(
        default=Path("semantic.db"),
        description="Путь к SQLite базе данных",
    )
    
    # === Gemini API ===
    gemini_api_key: str = Field(
        ...,  # Обязательный
        description="API ключ для Google Gemini",
    )
    
    gemini_batch_key: Optional[str] = Field(
        default=None,
        description="Отдельный ключ для Batch API (опционально)",
    )
    
    embedding_model: str = Field(
        default="text-embedding-004",
        description="Модель для генерации эмбеддингов",
    )
    
    embedding_dimension: int = Field(
        default=768,
        ge=256,
        le=3072,
        description="Размерность векторов",
    )
    
    # === Processing ===
    splitter: Literal["simple", "smart"] = Field(
        default="smart",
        description="Тип сплиттера документов",
    )
    
    context_strategy: Literal["basic", "hierarchical"] = Field(
        default="hierarchical",
        description="Стратегия формирования контекста",
    )
    
    # === Media ===
    media_enabled: bool = Field(
        default=True,
        description="Включить обработку изображений/аудио/видео",
    )
    
    media_rpm_limit: int = Field(
        default=15,
        ge=1,
        le=100,
        description="Rate limit для Vision/Audio API (запросов/мин)",
    )
    
    # === Search ===
    search_limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Количество результатов по умолчанию",
    )
    
    search_type: Literal["vector", "fts", "hybrid"] = Field(
        default="hybrid",
        description="Тип поиска по умолчанию",
    )
    
    # === Logging ===
    log_level: Literal["TRACE", "DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Уровень логирования",
    )
    
    log_file: Optional[Path] = Field(
        default=None,
        description="Путь к файлу логов (None = только консоль)",
    )
    
    # === Validators ===
    @field_validator("db_path", mode="before")
    @classmethod
    def resolve_db_path(cls, v) -> Path:
        """Преобразует строку в Path."""
        return Path(v).resolve() if isinstance(v, str) else v
    
    @field_validator("log_file", mode="before")
    @classmethod
    def resolve_log_file(cls, v) -> Optional[Path]:
        """Преобразует строку в Path."""
        if v is None or v == "":
            return None
        return Path(v).resolve() if isinstance(v, str) else v
    
    model_config = SettingsConfigDict(
        # Префикс для env variables
        env_prefix="SEMANTIC_",
        
        # Gemini ключи БЕЗ префикса (обратная совместимость)
        # Поддержка GEMINI_API_KEY вместо SEMANTIC_GEMINI_API_KEY
        
        # Читаем .env файл
        env_file=".env",
        env_file_encoding="utf-8",
        
        # TOML поддержка (Pydantic v2.6+)
        # toml_file="semantic.toml",
        
        # Разрешаем extra поля (для будущих расширений)
        extra="ignore",
        
        # Замораживаем после создания
        frozen=False,  # Позволяем CLI override
        
        # Case-insensitive для env
        case_sensitive=False,
    )


# === Глобальный singleton (опционально) ===
_config: Optional[SemanticConfig] = None


def get_config(**overrides) -> SemanticConfig:
    """Получить конфигурацию с возможными override'ами.
    
    Args:
        **overrides: CLI аргументы для переопределения.
        
    Returns:
        SemanticConfig с учётом всех источников.
    """
    global _config
    
    if overrides or _config is None:
        _config = SemanticConfig(**overrides)
    
    return _config
```

### Приоритет настроек

```
CLI args (--db-path)
    ↓
Environment (SEMANTIC_DB_PATH, GEMINI_API_KEY)
    ↓
semantic.toml (если существует)
    ↓
Default values
```

### Разделение секретов

| Источник | Что хранить |
|----------|-------------|
| `semantic.toml` | paths, limits, features (несекретное) |
| `.env` / environment | API ключи (GEMINI_API_KEY, GEMINI_BATCH_KEY) |
| CLI args | runtime overrides |

> **Важно:** `semantic init` НИКОГДА не записывает API ключи в TOML.

---

## 📐 Команда `init` — Инициализация проекта

**Файл:** `commands/init.py`

### Сигнатура

```bash
semantic init [OPTIONS]
```

### Логика

1. Создаёт `semantic.toml` (или `.env`) в текущей директории
2. Интерактивно запрашивает настройки (или использует defaults)
3. Проверяет наличие API ключей в окружении

### Опции

| Опция | Тип | Описание |
|-------|-----|----------|
| `--format` | toml/env | Формат конфига (default: toml) |
| `--force` | FLAG | Перезаписать существующий |
| `--non-interactive` | FLAG | Использовать defaults без вопросов |

### UX

```
$ semantic init

⚙️ Initializing Semantic Core project...

? Database path [semantic.db]: 
? Log level [INFO]: DEBUG
? Enable media analysis? [Y/n]: y
? Gemini API key found in GEMINI_API_KEY ✅

Created: semantic.toml

📁 Project structure:
   ./semantic.toml     # Configuration
   ./semantic.db       # Database (will be created on first run)

💡 Next steps:
   1. Add your documents: semantic ingest ./docs/
   2. Search: semantic search "query"
   3. See docs: semantic docs overview
```

### Генерируемый `semantic.toml`

```toml
# Semantic Core Configuration
# Generated by: semantic init

[database]
path = "semantic.db"

[logging]
level = "DEBUG"
file = "semantic.log"  # optional

[gemini]
# API key is read from GEMINI_API_KEY environment variable
model = "text-embedding-004"
embedding_dimension = 768

[media]
enabled = true
image_model = "gemini-2.5-flash"
rpm_limit = 15

[search]
default_limit = 10
default_type = "hybrid"
```

---

## 📐 Команда `config` — Просмотр конфигурации

**Файл:** `commands/config.py`

### Субкоманды

#### `semantic config show`

Показывает текущую конфигурацию (с маскировкой секретов).

**UX:**

```
$ semantic config show

⚙️ Current Configuration

Source: ./semantic.toml + environment variables

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Setting                    ┃ Value                         ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ database.path              │ ./semantic.db                 │
│ logging.level              │ DEBUG                         │
│ gemini.api_key             │ AIza***DACTED                 │
│ gemini.model               │ text-embedding-004            │
│ media.enabled              │ true                          │
│ media.rpm_limit            │ 15                            │
└────────────────────────────┴───────────────────────────────┘
```

#### `semantic config check`

Валидирует конфигурацию и проверяет соединения.

**UX:**

```
$ semantic config check

🔍 Checking configuration...

✅ Config file: ./semantic.toml
✅ Database: ./semantic.db (exists, 2.3 MB)
✅ API Key: GEMINI_API_KEY is set
⚠️ Batch API Key: GEMINI_BATCH_KEY not set (batch mode disabled)
✅ sqlite-vec extension: loaded
✅ Gemini API: connection successful

Summary: 4 passed, 1 warning, 0 errors
```

---

## 📐 Команда `doctor` — Диагностика

**Файл:** `commands/doctor.py`

### Сигнатура

```bash
semantic doctor [OPTIONS]
```

### Проверки

| Проверка | Что делает |
|----------|------------|
| Python version | >= 3.10 required |
| Dependencies | Все пакеты установлены |
| sqlite-vec | Extension загружается |
| Database | Файл доступен, схема корректна |
| API Keys | Ключи установлены и валидны |
| Disk space | Достаточно места для БД |
| Network | Доступ к Gemini API |

### Опции

| Опция | Тип | Описание |
|-------|-----|----------|
| `--fix` | FLAG | Попытаться исправить проблемы |
| `--verbose` | FLAG | Подробный вывод |

### UX

```
$ semantic doctor

🩺 Running diagnostics...

Environment:
  ✅ Python 3.11.5
  ✅ semantic-core 0.8.0
  ✅ Dependencies: all installed

Database:
  ✅ sqlite-vec extension loaded
  ✅ Database: ./semantic.db
  ✅ Schema version: 5 (current)
  ✅ Tables: chunks (1,234 rows), documents (45 rows)

API:
  ✅ GEMINI_API_KEY: configured
  ⚠️ GEMINI_BATCH_KEY: not configured
  ✅ Gemini API: reachable (latency: 120ms)

Storage:
  ✅ Disk space: 45 GB available
  ℹ️ Database size: 2.3 MB

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🩺 Diagnosis: Healthy (1 warning)

💡 Recommendation:
   Set GEMINI_BATCH_KEY for async embedding (cheaper for large volumes)
```

### JSON Output

```json
{
  "status": "healthy",
  "warnings": 1,
  "errors": 0,
  "checks": {
    "python_version": {"status": "ok", "value": "3.11.5"},
    "sqlite_vec": {"status": "ok"},
    "api_key": {"status": "ok"},
    "batch_key": {"status": "warning", "message": "not configured"},
    ...
  }
}
```

---

## 🔤 CLI Эмодзи для логгера

**Новые паттерны:**

| Паттерн | Эмодзи | Модуль |
|---------|--------|--------|
| `init` | ⚙️ | init.py |
| `config` | 🔧 | config.py |
| `doctor`, `diagnostic` | 🩺 | doctor.py |

**Добавить в EMOJI_MAP:**
- `init` → ⚙️
- `config` → 🔧
- `doctor`, `diagnostic` → 🩺

---

## ✅ Acceptance Criteria

### Функциональные

1. [ ] `semantic init` создаёт semantic.toml
2. [ ] `semantic init --format env` создаёт .env
3. [ ] `semantic config show` выводит конфигурацию
4. [ ] API ключи маскируются в выводе
5. [ ] `semantic config check` валидирует настройки
6. [ ] `semantic doctor` выполняет все проверки
7. [ ] Флаг `--json` работает для всех команд

### Качество

8. [ ] Интерактивный режим с валидацией ввода
9. [ ] Graceful handling отсутствующих файлов
10. [ ] Цветовая индикация статусов (✅ ⚠️ ❌)

### Тесты

11. [ ] Unit-тест генерации конфига
12. [ ] Unit-тест парсинга semantic.toml
13. [ ] Integration-тест doctor checks

---

## 📚 Документация (после реализации)

### Архитектурный сериал

1. **Episode 44:** `44_configuration_management.md` — Управление конфигурацией
   - TOML vs ENV
   - Configuration precedence (file < env < cli args)
   - Secrets handling

### Обновления

- Добавить секцию "Configuration" в README
- Полный референс semantic.toml
- Гайд по переменным окружения

### EMOJI_MAP

```python
"init": "⚙️",
"config": "🔧", 
"doctor": "🩺",
"diagnostic": "🩺",
```

---

## 🔗 Связанные документы

- **Основной план:** [Phase 8 — CLI Architecture](phase_8.md)
- **Следующая:** [Phase 8.0 — Core CLI](phase_8.0.md) (зависит от этой фазы)
- **API Keys:** [19_api_key_management.md](../../architecture/19_api_key_management.md)
- **Logging:** [Phase 7.0 — Logging Core](../phase_7/phase_7.0.md)

````
