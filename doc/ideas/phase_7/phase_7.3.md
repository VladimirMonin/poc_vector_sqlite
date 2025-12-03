# 📋 Phase 7.3: Configuration & UX

**Статус:** 🔲 Планируется  
**Зависимости:** Phase 7.1 и 7.2 ✅ (можно начать после их завершения)

---

## ⚠️ ВАЖНО: Выполнять ПОСЛЕ Phase 7.1 и 7.2

> Phase 7.3 интегрирует логирование с остальной системой.
> Для полноценного тестирования нужны инструментированные модули из 7.1 и 7.2.

---

## ✅ ПРЕДВАРИТЕЛЬНО ВЫПОЛНЕНО

> **ВАЖНО для агента:** Следующие задачи УЖЕ ВЫПОЛНЕНЫ. НЕ нужно их делать повторно!

1. ✅ **EMOJI_MAP обновлён** — паттерны для Phase 7.3 добавлены в `formatters.py`:
   - `diagnostic`, `diagnostics` → 🩺
   - `config` → ⚙️
   
2. ✅ **Logging Core готов** — базовая конфигурация работает

**Агент НЕ должен трогать файл `semantic_core/utils/logger/formatters.py`!**

---

## 🎯 Цель

Завершить систему логирования, предоставив пользователю **удобные инструменты управления**:
- Единый конфиг через GeminiConfig/Settings
- CLI-опции для уровня логов
- Утилита dump_debug_info() для диагностики
- JSON-формат для машинного парсинга

---

## 📦 Целевые области

### 1. Configuration Integration

```
semantic_core/
├── config.py              # Если есть — интеграция с LoggingConfig
├── pipeline.py            # SemanticCore — настройка логов при инициализации
└── utils/logger/
    └── config.py          # LoggingConfig — расширение
```

### 2. CLI Support

```
semantic_core/
└── cli.py                 # Если есть CLI — добавить --log-level, --log-file
```

### 3. Debug Utilities

```
semantic_core/utils/logger/
└── diagnostics.py         # НОВЫЙ: dump_debug_info(), check_config()
```

---

## 🔍 Детальный план

---

### Часть 1: Интеграция с существующим конфигом

#### 1.1 Анализ текущего состояния

**Агент должен найти:**
- Есть ли `config.py` в корне `semantic_core/`?
- Используется ли Pydantic Settings?
- Как передаются настройки в компоненты?

**Терминальные команды для анализа:**
```bash
# Найти все конфиги
find semantic_core -name "*config*" -o -name "*settings*"

# Найти использование Pydantic
grep -r "BaseSettings\|BaseModel" semantic_core/*.py

# Найти инициализацию SemanticCore
grep -n "class SemanticCore\|def __init__" semantic_core/pipeline.py
```

#### 1.2 Варианты интеграции

**Вариант A: Отдельный LoggingConfig (если нет глобального конфига)**

```python
# semantic_core/utils/logger/config.py
class LoggingConfig(BaseModel):
    level: str = "INFO"
    file_level: str = "TRACE"
    log_file: str | None = None
    redact_secrets: bool = True
    console_width: int = 120
    json_format: bool = False  # NEW
    show_path: bool = False    # NEW
```

**Вариант B: Вложенный в GeminiConfig (если есть глобальный конфиг)**

```python
# semantic_core/config.py
class GeminiConfig(BaseSettings):
    api_key: str
    model: str = "text-embedding-004"
    
    # Logging section
    log_level: str = "INFO"
    log_file: str | None = None
    log_json: bool = False
```

#### 1.3 Автоматическая настройка при инициализации

**В `pipeline.py` (SemanticCore):**

```
При создании SemanticCore:
1. Прочитать конфигурацию логирования
2. Вызвать setup_logging() с этим конфигом
3. Создать логгер для pipeline
```

---

### Часть 2: Environment Variables

#### 2.1 Поддержка переменных окружения

| Переменная | Значение | По умолчанию |
|------------|----------|--------------|
| `SEMANTIC_LOG_LEVEL` | DEBUG/INFO/WARNING/ERROR | INFO |
| `SEMANTIC_LOG_FILE` | Путь к файлу | None |
| `SEMANTIC_LOG_JSON` | true/false | false |
| `SEMANTIC_LOG_REDACT` | true/false | true |

#### 2.2 Приоритет настроек

```
1. Явный параметр в коде (highest)
2. Environment variable
3. Config file (.env, pyproject.toml)
4. Default value (lowest)
```

---

### Часть 3: CLI Support

#### 3.1 Анализ текущего CLI

**Агент должен проверить:**
```bash
# Есть ли CLI?
find semantic_core -name "cli.py" -o -name "__main__.py"

# Используется ли click/typer/argparse?
grep -r "import click\|import typer\|import argparse" semantic_core/
```

#### 3.2 Добавление опций (если CLI существует)

| Опция | Короткая | Описание |
|-------|----------|----------|
| `--log-level` | `-l` | Уровень логов (DEBUG/INFO/WARNING/ERROR) |
| `--log-file` | `-f` | Путь к файлу логов |
| `--verbose` | `-v` | Shortcut для --log-level DEBUG |
| `--quiet` | `-q` | Shortcut для --log-level WARNING |
| `--json-logs` | | Включить JSON формат |

---

### Часть 4: Debug Utilities

#### 4.1 `dump_debug_info()` — Системный дамп

**Создать `semantic_core/utils/logger/diagnostics.py`:**

**Функция `dump_debug_info()`:**

Собирает информацию для баг-репортов:

| Секция | Что включает |
|--------|--------------|
| **System** | Python version, OS, platform |
| **Package** | semantic_core version, installed deps |
| **Config** | Текущий LoggingConfig (без API keys!) |
| **Environment** | SEMANTIC_* переменные |
| **Database** | SQLite version, vec0 version, DB path |
| **Handlers** | Активные хендлеры, уровни |

**Вывод:**
```
=== Semantic Core Debug Info ===
Generated: 2024-12-03T14:30:00

[System]
Python: 3.12.1
OS: macOS 14.1 (arm64)

[Package]
semantic_core: 0.7.0
peewee: 3.17.0
sqlite-vec: 0.1.2
rich: 13.7.0

[Config]
log_level: DEBUG
log_file: /tmp/semantic.log
redact_secrets: True

[Database]
path: /data/notes.db
sqlite: 3.45.0
vec0: loaded
fts5: loaded

[Handlers]
- RichHandler (console) level=INFO
- FileHandler (/tmp/semantic.log) level=TRACE
```

#### 4.2 `check_config()` — Валидация конфига

**Проверяет:**
- [ ] Путь к log_file существует/доступен для записи
- [ ] Уровень логов валидный
- [ ] SensitiveFilter работает (тест на fake key)

**Возвращает:** `list[str]` предупреждений

---

### Часть 5: JSON Logs

#### 5.1 Когда нужен JSON?

- Отправка в Elasticsearch/Loki
- Парсинг логов скриптами
- Интеграция с observability platforms

#### 5.2 JSON Formatter

**В `formatters.py`:**

```python
class JSONFormatter(logging.Formatter):
    """Structured JSON output for log aggregators."""
```

**Формат:**
```json
{
    "timestamp": "2024-12-03T14:30:00.123Z",
    "level": "INFO",
    "logger": "semantic_core.pipeline",
    "message": "Document processed",
    "context": {
        "doc_id": "doc-123",
        "chunk_count": 15
    },
    "latency_ms": 1250
}
```

#### 5.3 Активация

```python
setup_logging(LoggingConfig(json_format=True))
```

---

## ✅ Acceptance Criteria

### Configuration

1. [ ] LoggingConfig интегрирован с основным конфигом (если есть)
2. [ ] Environment variables работают
3. [ ] Приоритет настроек соблюдается

### CLI

4. [ ] --log-level опция работает (если есть CLI)
5. [ ] --verbose / --quiet shortcuts работают

### Debug Utilities

6. [ ] `dump_debug_info()` выводит полную информацию
7. [ ] API-ключи НЕ попадают в дамп
8. [ ] `check_config()` валидирует настройки

### JSON

9. [ ] JSON формат включается через конфиг
10. [ ] Все поля корректно сериализуются

---

## 🔧 Инструкции для агента-исполнителя

### КРИТИЧЕСКИ ВАЖНО: Анализ перед изменениями

**Агент ОБЯЗАН сначала провести разведку:**

1. **Найти существующие конфиги:**
   ```bash
   find semantic_core -name "*.py" | xargs grep -l "BaseSettings\|BaseModel\|dataclass"
   ```

2. **Понять текущую архитектуру конфигурации:**
   ```bash
   grep -rn "class.*Config\|class.*Settings" semantic_core/
   ```

3. **Найти точки инициализации:**
   ```bash
   grep -n "__init__\|setup\|configure" semantic_core/pipeline.py
   ```

4. **Проверить наличие CLI:**
   ```bash
   ls -la semantic_core/cli.py semantic_core/__main__.py 2>/dev/null
   ```

### Порядок работы

1. **Разведка** — анализ существующей структуры
2. **Расширение LoggingConfig** — добавить json_format, show_path
3. **Environment Variables** — добавить поддержку
4. **Создать diagnostics.py** — dump_debug_info(), check_config()
5. **JSON Formatter** — добавить в formatters.py
6. **Интеграция с pipeline.py** — автоматический setup_logging()
7. **CLI опции** — если CLI существует
8. **Тесты** — unit тесты на новую функциональность

### Чеклист для каждого компонента

**LoggingConfig:**
- [ ] Добавлены новые поля
- [ ] Добавлена валидация
- [ ] Есть docstring с описанием полей

**Environment Variables:**
- [ ] Все переменные документированы
- [ ] Приоритет работает правильно
- [ ] Есть тест на override

**diagnostics.py:**
- [ ] dump_debug_info() не выводит секреты
- [ ] Все секции заполняются
- [ ] check_config() возвращает warnings

**JSON Formatter:**
- [ ] Все поля сериализуются
- [ ] timestamp в ISO формате
- [ ] context включает bind() данные

---

## 📊 Ожидаемый результат

После Phase 7.3 пользователь сможет:

```python
# Явная настройка
from semantic_core import SemanticCore

core = SemanticCore(
    log_level="DEBUG",
    log_file="/tmp/debug.log"
)

# Через environment
# SEMANTIC_LOG_LEVEL=DEBUG python script.py

# CLI
# python -m semantic_core index --log-level DEBUG --log-file out.log

# Диагностика
from semantic_core.utils.logger import dump_debug_info
print(dump_debug_info())
```

---

## 🔗 Связанные документы

- **Предыдущая:** [Phase 7.2 — Infrastructure Layer](phase_7.2.md)
- **Архитектура:** [Semantic Logging](../../architecture/35_semantic_logging.md)
- **README:** [Logger Package](../../../semantic_core/utils/logger/README.md)
