# 🔧 Episode 40: Unified Configuration

> Как объединить все настройки в один источник правды

---

## 🎯 Проблема: Разрозненные настройки

В предыдущих фазах настройки разбросаны по разным местам:

```python
# 😰 До: настройки везде
embedder = GeminiEmbedder(
    api_key=os.getenv("GEMINI_API_KEY"),
    model="text-embedding-004"
)

splitter = SmartSplitter(chunk_size=1500, overlap=200)

core = SemanticCore(
    db_path="semantic.db",
    embedder=embedder,
    splitter=splitter
)
```

**Проблемы:**

- Дублирование настроек в разных файлах
- Нет единого места для изменения
- Сложно передавать настройки между компонентами
- Нет валидации типов

---

## 💡 Решение: SemanticConfig

**Pydantic BaseSettings** объединяет все настройки:

```python
from semantic_core.config import SemanticConfig, get_config

# 😊 После: один источник правды
config = get_config()

core = SemanticCore(config=config)
```

Все компоненты получают настройки из одного места!

---

## 🏗 Архитектура конфигурации

```
┌─────────────────────────────────────────────────────────────────┐
│                     Приоритет источников                        │
│                                                                 │
│   ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐  │
│   │   CLI   │ >>> │   ENV   │ >>> │  TOML   │ >>> │ Default │  │
│   │ kwargs  │     │ vars    │     │  file   │     │ values  │  │
│   └─────────┘     └─────────┘     └─────────┘     └─────────┘  │
│                                                                 │
│   get_config(     SEMANTIC_*     semantic.toml   In code       │
│     log_level=    GEMINI_*                                      │
│     "DEBUG"                                                     │
│   )                                                             │
└─────────────────────────────────────────────────────────────────┘
```

**Приоритет:** CLI > Environment > TOML > Defaults

---

## 📄 Формат semantic.toml

```toml
# semantic.toml — конфигурация проекта

[database]
path = "semantic.db"

[gemini]
# api_key и batch_key в .env — не храним секреты в коде!
model = "gemini-embedding-001"
embedding_dimension = 768

[processing]
splitter = "smart"          # simple | smart
context_strategy = "hierarchical"  # basic | hierarchical

[media]
enabled = true
rpm_limit = 15  # Rate limit для Vision API

[search]
limit = 10
type = "hybrid"  # vector | fts | hybrid

[logging]
level = "INFO"
# file = "semantic.log"  # опционально
```

---

## 🔍 Поиск конфигурации

`find_config_file()` ищет `semantic.toml` вверх по дереву директорий:

```
project/
├── src/
│   └── scripts/
│       └── analyze.py  ← Запуск отсюда
├── semantic.toml  ← Найдёт здесь
└── .env
```

**Алгоритм:**

1. Проверить текущую директорию
2. Если не найден — перейти в родительскую
3. Повторять до 10 уровней
4. Если не найден — использовать defaults

---

## 🌍 Переменные окружения

**С префиксом SEMANTIC_:**

```bash
export SEMANTIC_DB_PATH="production.db"
export SEMANTIC_LOG_LEVEL="WARNING"
export SEMANTIC_SPLITTER="simple"
```

**Специальные (без префикса):**

```bash
export GEMINI_API_KEY="AIza..."
export GEMINI_BATCH_KEY="AIza..."  # Для async
```

---

## 🔧 Использование в коде

### Получение конфигурации

```python
from semantic_core.config import get_config, reset_config

# Синглтон — всегда одна и та же конфигурация
config1 = get_config()
config2 = get_config()
assert config1 is config2  # True!

# С override'ами — создаёт новый экземпляр
config3 = get_config(log_level="DEBUG")
assert config1 is not config3

# Сброс для тестов
reset_config()
```

### Доступ к настройкам

```python
config = get_config()

# Прямой доступ
print(config.db_path)          # Path('semantic.db')
print(config.gemini_api_key)   # 'AIza...' или None
print(config.splitter)         # 'smart'
print(config.log_level)        # 'INFO'

# Обязательные поля
try:
    key = config.require_api_key()
except ValueError:
    print("GEMINI_API_KEY not set!")
```

### Экспорт в TOML

```python
config = get_config()
toml_dict = config.to_toml_dict()

# Секреты НЕ включаются!
print(toml_dict)
# {
#     'database': {'path': 'semantic.db'},
#     'gemini': {'model': 'text-embedding-004'},
#     ...
# }
```

---

## 🛡 Валидация типов

Pydantic автоматически валидирует все поля:

```python
from semantic_core.config import SemanticConfig

# ✅ Корректные значения
config = SemanticConfig(
    db_path="custom.db",
    log_level="DEBUG",
    splitter="smart"
)

# ❌ Ошибка валидации
config = SemanticConfig(
    log_level="INVALID"  # ValidationError!
)
# pydantic.ValidationError: 1 validation error for SemanticConfig
# log_level
#   Input should be 'TRACE', 'DEBUG', 'INFO', 'WARNING', 'ERROR' or 'CRITICAL'
```

---

## 🔗 Интеграция с компонентами

**До рефакторинга:**

```python
# 😰 Каждый компонент настраивается отдельно
embedder = GeminiEmbedder(api_key=API_KEY, model=MODEL)
storage = PeeweeVectorStore(db_path=DB_PATH)
splitter = SmartSplitter(chunk_size=SIZE, overlap=OVERLAP)
```

**После рефакторинга (Phase 8.0+):**

```python
# 😊 Компоненты читают настройки из config
from semantic_core.config import get_config

config = get_config()

embedder = GeminiEmbedder.from_config(config)
storage = PeeweeVectorStore.from_config(config)
splitter = SmartSplitter.from_config(config)
batch_client = GeminiBatchClient.from_config(config)  # Phase 10.1
batch_manager = BatchManager.from_config(db, config)  # Phase 10.1
```

---

## 💡 Best Practices

### 1. Используй semantic.toml для проектных настроек

```toml
# semantic.toml — коммитится в репозиторий
[search]
limit = 20
type = "hybrid"
```

### 2. Секреты в .env или окружении

```bash
# .env — НЕ коммитится!
GEMINI_API_KEY=AIza...
```

### 3. CLI override'ы для одноразовых запусков

```bash
# Временно увеличить лимит
semantic search --limit 100 "query"
```

### 4. reset_config() в тестах

```python
@pytest.fixture(autouse=True)
def clean_config():
    reset_config()
    yield
    reset_config()
```

---

## 📊 Преимущества подхода

| Аспект | До | После |
|--------|----|----|
| Настройки | Разбросаны | В одном файле |
| Валидация | Ручная | Автоматическая (Pydantic) |
| Типизация | Нет | Строгая |
| Приоритеты | Неявные | Чёткие (CLI > env > TOML) |
| Тестирование | Сложно | reset_config() |

---

## 🎯 Итог

**SemanticConfig** — единый источник правды для всех настроек:

1. **Загружает** из TOML, env variables, CLI args
2. **Валидирует** типы через Pydantic
3. **Предоставляет** удобный доступ к настройкам
4. **Защищает** секреты от попадания в логи

**Следующий шаг:** [Episode 41: CLI Architecture](41_cli_architecture.md) — как устроено CLI-приложение

---

**← [Назад к Episode 39](39_diagnostics_debugging.md)** | **[Далее к Episode 41 →](41_cli_architecture.md)**
