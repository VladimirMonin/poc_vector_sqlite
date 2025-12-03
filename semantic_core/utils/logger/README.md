# 📊 Semantic Logger

> Dual-mode logging с эмодзи-семантикой и автоматическим маскированием секретов.

## 🎯 Быстрый старт

```python
from semantic_core.utils.logger import get_logger, setup_logging

# Инициализация (опционально — происходит автоматически)
setup_logging()

# Получение логгера
logger = get_logger(__name__)

# Базовое использование
logger.info("Document loaded")           # 📥 Document loaded
logger.debug("Parsing structure")         # 🧶 Parsing structure
logger.trace("Full payload", data={...})  # 🔬 [только в файл]
```

## 🏗️ Архитектура

```
┌─────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ get_logger()│───▶│ SemanticLogger  │───▶│  RichHandler    │
│             │    │  + bind()       │    │  (Console)      │
└─────────────┘    │  + trace_ai()   │    └─────────────────┘
                   └────────┬────────┘            │
                            │                     ▼
                   ┌────────▼────────┐    ┌─────────────────┐
                   │ SensitiveFilter │    │  FileHandler    │
                   │  (API keys)     │    │  (TRACE mode)   │
                   └─────────────────┘    └─────────────────┘
```

## 🎭 Уровни логирования

| Уровень | Значение | Назначение | Куда идёт |
|---------|----------|------------|-----------|
| TRACE | 5 | Дампы пейлоадов, векторы | Файл only |
| DEBUG | 10 | Шаги алгоритма | Файл + (опц. консоль) |
| INFO | 20 | Операции пользователя | Консоль + файл |
| WARNING | 30 | Подозрительно | Консоль + файл |
| ERROR | 40 | Операция провалена | Консоль + файл |

## 👁️ EMOJI_MAP — Визуальная семантика

Эмодзи определяется по `__name__` модуля:

| Паттерн | Эмодзи | Семантика |
|---------|--------|-----------|
| pipeline, core | 📥 | Ingestion |
| parser, markdown | 🧶 | Parsing |
| splitter | ✂️ | Splitting |
| embed, gemini | 🧠 | AI/Embeddings |
| batch, queue | 📦 | Queue |
| storage, peewee | 💾 | Database |
| search | 🔍 | Search |
| image, vision | 👁️ | Vision API |
| audio | 🎙️ | Audio API |
| video | 🎬 | Video API |
| rate, limit | 🛡️ | Protection |

**LEVEL_EMOJI** (приоритет над модульными): 💀 CRITICAL, ❌ ERROR, ⚠️ WARNING

## 🔗 Context Propagation — bind()

```python
# Создаём логгер с контекстом
log = logger.bind(batch_id="batch-001")
log.info("Starting")  # 📥 [batch-001] Starting

# Цепочка контекстов
doc_log = log.bind(doc_id="doc-42")
doc_log.info("Processing")  # 📥 [batch-001/doc-42] Processing
```

**CONTEXT_ID_KEYS**: `batch_id`, `doc_id`, `chunk_id`, `task_id`, `request_id`

## 🔐 Secret Redaction

Автоматическое маскирование в `SensitiveDataFilter`:

| Провайдер | Паттерн | Результат |
|-----------|---------|-----------|
| Google | `AIza...` | `***REDACTED***` |
| OpenAI | `sk-...` | `***REDACTED***` |
| Groq | `gsk_...` | `***REDACTED***` |

## ⚙️ Конфигурация

```python
from semantic_core.utils.logger import setup_logging, LoggingConfig

setup_logging(LoggingConfig(
    level="DEBUG",           # Уровень консоли
    file_level="TRACE",      # Уровень файла
    log_file="app.log",      # Путь к файлу (None = без файла)
    redact_secrets=True,     # Маскировать API-ключи
    console_width=120,       # Ширина консоли Rich
))
```

## 📦 Структура пакета

```
semantic_core/utils/logger/
├── __init__.py      # API: get_logger(), setup_logging()
├── levels.py        # TRACE=5, install_trace_level()
├── config.py        # LoggingConfig (Pydantic)
├── filters.py       # SensitiveDataFilter
├── formatters.py    # EMOJI_MAP, FileFormatter
└── logger.py        # SemanticLogger adapter
```

## 🎓 Специальные методы

```python
# AI-вызовы
logger.trace_ai(prompt="...", response="...", tokens=1542)

# Ошибки с контекстом
logger.error_with_context(exception, local_vars={"key": "value"})
```
