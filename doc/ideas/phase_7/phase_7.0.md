# 🗺️ Phase 7: Semantic Logging & Observability

**Цель:** Внедрить систему структурированного, семантического логирования, которая обеспечивает "прозрачность" работы библиотеки как для человека (через CLI с эмодзи), так и для AI-агентов (через детальные Trace-логи).

**Принципы:**

* **Visual Semantics:** Использование эмодзи для мгновенной визуальной идентификации слоя и типа операции.
* **Dual Mode:**
  * *Console (Human):* Кратко, красиво, информативно (INFO+).
  * *File (AI/Debug):* Полный дамп контекста, структур данных и промптов (TRACE).
* **Zero-Config:** Работает из коробки с разумными дефолтами, не требует сложной настройки от пользователя.
* **Security:** Автоматическое удаление секретов (API-ключей) из логов.

-----

## 📦 7.0 Infrastructure: Logging Core

Реализация фундаментальной логики логгера, форматтеров и уровней.

### 0\. Зависимости

**Добавить в `pyproject.toml`:**

```toml
[project.dependencies]
# ... существующие зависимости ...
"rich (>=13.0.0,<14.0.0)"  # Цветной вывод, RichHandler, Tracebacks
```

> **Примечание:** `rich` — единственная новая зависимость. Стандартный `logging` из Python stdlib покрывает остальное.

### 1\. Новый модуль `semantic_core/utils/logger/`

**Структура пакета:**

```text
semantic_core/utils/
├── __init__.py           # Пустой, маркер пакета
└── logger/
    ├── __init__.py       # Публичный API: get_logger, setup_logging, TRACE
    ├── levels.py         # Регистрация TRACE (5), патчинг Logger
    ├── logger.py         # SemanticLogger adapter
    ├── formatters.py     # EmojiFormatter, EMOJI_MAP
    ├── filters.py        # SensitiveDataFilter
    └── config.py         # LoggingConfig (Pydantic)
```

### 2\. Модуль `levels.py` — Кастомный уровень TRACE

**А. Регистрация уровня:**

```python
import logging

TRACE = 5  # Ниже DEBUG (10)
logging.addLevelName(TRACE, "TRACE")
```

**Б. Патчинг Logger для метода `trace()`:**

```python
def _trace(self, message, *args, **kwargs):
    """Логирование на уровне TRACE (5)."""
    if self.isEnabledFor(TRACE):
        self._log(TRACE, message, args, **kwargs)

logging.Logger.trace = _trace
```

**В. Иерархия уровней после патчинга:**

| Уровень | Значение | Назначение |
| :--- | :---: | :--- |
| `TRACE` | 5 | Дампы пейлоадов, векторов, промптов |
| `DEBUG` | 10 | Технические детали (вход в функцию, аргументы) |
| `INFO` | 20 | Бизнес-события (документ загружен, батч отправлен) |
| `WARNING` | 30 | Предупреждения (fallback, deprecation) |
| `ERROR` | 40 | Ошибки, требующие внимания |
| `CRITICAL` | 50 | Фатальные сбои |

### 3\. Модуль `logger.py` — SemanticLogger Adapter

**Класс `SemanticLogger`** — обёртка над стандартным `logging.Logger`:

```python
class SemanticLogger:
    """Адаптер для структурированного логирования с контекстом."""
    
    def __init__(self, name: str): ...
    
    # Основные методы
    def trace(self, msg: str, **context) -> None: ...
    def debug(self, msg: str, **context) -> None: ...
    def info(self, msg: str, **context) -> None: ...
    def warning(self, msg: str, **context) -> None: ...
    def error(self, msg: str, **context) -> None: ...
    
    # Привязка контекста (Context Binding)
    def bind(self, **context) -> "SemanticLogger":
        """Создать дочерний логгер с привязанным контекстом.
        
        Пример:
            logger = get_logger(__name__).bind(batch_id="batch-123")
            logger.info("Batch processed")  # -> 📦 [batch-123] Batch processed
        """
    
    # Специализированные методы
    def trace_ai(self, prompt: str, response: str, **metadata) -> None:
        """Логирование LLM-взаимодействия (prompt/response/tokens/model)."""
    
    def error_with_context(self, exc: Exception, **context) -> None:
        """Логирование исключения с захватом контекста."""
```

**Контекст (`**context`)** добавляется в `extra` поле LogRecord для структурированного вывода.

### 3.1\. Проброс Context ID через пайплайн

**Проблема:**

```
❌ Плохо:  📦 Batch processed           (Какой?)
✅ Хорошо: 📦 [batch-123] Batch processed
```

**Решение — метод `bind()`:**

Позволяет создать "дочерний" логгер с привязанным контекстом, который будет автоматически добавляться ко всем сообщениям:

```python
# В BatchManager
def process_batch(self, batch_id: str):
    log = self.logger.bind(batch_id=batch_id)
    log.info("Starting batch processing")      # -> 📦 [batch-123] Starting...
    log.debug("Loaded 50 chunks")              # -> 📦 [batch-123] Loaded 50 chunks
    log.info("Batch completed", duration=2.5)  # -> 📦 [batch-123] Batch completed

# В Pipeline
def ingest_document(self, doc_path: str):
    doc_id = generate_doc_id(doc_path)
    log = self.logger.bind(doc_id=doc_id)
    log.info("Processing document", path=doc_path)  # -> 📥 [doc-abc] Processing...
```

**Поддерживаемые Context ID:**

| Ключ | Где используется | Пример значения |
| :--- | :--- | :--- |
| `batch_id` | BatchManager, batching.py | `batch-a1b2c3` |
| `doc_id` | Pipeline, parsers | `doc-xyz789` |
| `chunk_id` | Splitters, context | `chunk-42` |
| `task_id` | MediaQueueProcessor | `task-img-001` |
| `request_id` | GeminiEmbedder, API calls | `req-f4e5d6` |

**Формат вывода с контекстом:**

* **Console:** `[14:20:01] 📦 [batch-123] Batch processed`
* **File:** `2025-12-03 14:20:01 | BATCH | INFO | batch_id=batch-123 | Batch processed`

**Реализация в `EmojiFormatter`:**

```python
def format(self, record: logging.LogRecord) -> str:
    # Извлекаем context_id из extra
    context_ids = []
    for key in ("batch_id", "doc_id", "chunk_id", "task_id", "request_id"):
        if hasattr(record, key) and getattr(record, key):
            context_ids.append(f"{getattr(record, key)}")
    
    context_prefix = f"[{'/'.join(context_ids)}] " if context_ids else ""
    # -> [batch-123] или [doc-abc/chunk-42]
```

### 4\. Модуль `formatters.py` — EmojiFormatter

**А. Таблица семантических эмодзи (EMOJI_MAP):**

| Паттерн имени модуля | Эмодзи | Контекст |
| :--- | :---: | :--- |
| `pipeline` | 📥 | Ingestion, маршрутизация |
| `parser`, `parsers` | 🧶 | Парсинг Markdown AST |
| `splitter`, `splitters` | ✂️ | Нарезка на чанки |
| `context`, `enricher` | 🧬 | Обогащение контекстом |
| `image`, `vision` | 👁️ | Анализ изображений |
| `audio` | 🎙️ | Транскрипция аудио |
| `video` | 🎬 | Анализ видео |
| `embed`, `embedder` | 🧠 | Векторизация (Gemini API) |
| `batch`, `queue` | 📦 | Очереди и батчи |
| `storage`, `adapter`, `peewee` | 💾 | Операции с БД |
| `search` | 🔍 | Поиск (Vector/Hybrid) |
| `rate`, `limit`, `auth` | 🛡️ | Rate limits, безопасность |
| `media` | 🎞️ | Общие медиа-операции |
| `database` | 🗄️ | Миграции, схема |
| *fallback* | 📌 | Неизвестный модуль |

**Б. Эмодзи для уровней (перед сообщением):**

| Уровень | Эмодзи |
| :--- | :---: |
| `ERROR` | ❌ |
| `WARNING` | ⚠️ |
| `SUCCESS` (кастомный тег) | ✅ |

**В. Класс `EmojiFormatter(logging.Formatter)`:**

* Определяет эмодзи по `record.name` (имя логгера → модуль)
* Два режима форматирования:
  * **Console (compact):** `[HH:MM:SS] 📥 Message                    module.py:42`
  * **File (verbose):** `2025-12-03 14:20:02 | PIPELINE | INFO | 📥 Message | {"key": "value"}`

### 5\. Модуль `filters.py` — SensitiveDataFilter

**Класс `SensitiveDataFilter(logging.Filter)`:**

```python
SENSITIVE_PATTERNS = [
    r"AIza[0-9A-Za-z_-]{35}",      # Google API Key
    r"sk-[0-9a-zA-Z]{48}",         # OpenAI API Key
    r"gsk_[0-9a-zA-Z]{52}",        # Groq API Key
    r"[0-9a-f]{8}-[0-9a-f]{4}-.*", # UUID (partial, для session tokens)
]
REDACTED = "***REDACTED***"
```

* Применяется ко всем хендлерам
* Работает на уровне `record.msg` и `record.args`
* Не затрагивает структуру логов, только маскирует значения

### 6\. Модуль `config.py` — LoggingConfig

**Pydantic-модель для конфигурации:**

```python
from pydantic import BaseModel
from pathlib import Path

class LoggingConfig(BaseModel):
    """Конфигурация системы логирования."""
    
    level: str = "INFO"           # Минимальный уровень для консоли
    file_level: str = "TRACE"     # Минимальный уровень для файла
    log_file: Path | None = None  # Путь к файлу (None = только консоль)
    json_format: bool = False     # JSON вместо текста для файла
    show_path: bool = True        # Показывать путь к модулю
    redact_secrets: bool = True   # Фильтрация API-ключей
```

### 7\. Публичный API (`__init__.py`)

```python
from semantic_core.utils.logger.levels import TRACE
from semantic_core.utils.logger.logger import SemanticLogger
from semantic_core.utils.logger.config import LoggingConfig

def get_logger(name: str) -> SemanticLogger:
    """Получить настроенный логгер для модуля."""
    ...

def setup_logging(config: LoggingConfig | None = None) -> None:
    """Инициализировать систему логирования."""
    ...

__all__ = ["TRACE", "get_logger", "setup_logging", "SemanticLogger", "LoggingConfig"]
```

### 8\. Текущее состояние проекта (для миграции)

**Файлы с существующим логированием:**

| Файл | Текущее состояние | Действие |
| :--- | :--- | :--- |
| `pipeline.py` | ✅ `logging.getLogger(__name__)` | Заменить на `get_logger()` |
| `batch_manager.py` | ⚠️ `print()` statements | Заменить на логгер |
| `database.py` | ⚠️ `print("[Migration]...")` | Заменить на логгер |
| `infrastructure/gemini/batching.py` | ⚠️ `print()` для статусов | Заменить на логгер |

**Остальные модули** (20+) не имеют логирования — добавляем с нуля в Phase 7.1-7.2.

### 9\. Acceptance Criteria (Definition of Done)

* [ ] Пакет `semantic_core/utils/logger/` создан и импортируется без ошибок
* [ ] `TRACE` уровень зарегистрирован, `logger.trace()` работает
* [ ] `EmojiFormatter` корректно добавляет эмодзи для всех модулей из EMOJI_MAP
* [ ] `SensitiveDataFilter` маскирует API-ключи в логах
* [ ] `setup_logging()` настраивает Console + File хендлеры
* [ ] Unit-тесты покрывают: levels, formatters, filters, config
* [ ] `rich` добавлен в зависимости `pyproject.toml`

-----

## 📦 7.1 Instrumentation: Processing Layer

Внедрение логов в логическое ядро обработки текста и медиа.

**Цель:** Видеть, как документ превращается в векторы.

1. **`pipeline.py` (`IngestionPipeline`):**

      * `INFO 📥`: Старт обработки документа (путь, размер).
      * `INFO 🔀`: Решение роутера (Sync/Async, Text/Media).
      * `SUCCESS ✅`: Документ полностью обработан (время, кол-во чанков).

2. **`parsers/markdown_parser.py`:**

      * `DEBUG 🧶`: Структура документа (найденные заголовки H1-H3).
      * `TRACE`: Полное дерево токенов (для отладки парсера).
      * `INFO 🖼️`: Обнаружены ссылки на медиа (кол-во, типы).

3. **`splitters/smart_splitter.py`:**

      * `DEBUG ✂️`: Статистика нарезки (размер чанка, оверлеп).
      * `TRACE`: Дамп содержимого чанка (первые 50 символов).

4. **`context/hierarchical_strategy.py`:**

      * `TRACE 🧬`: Сгенерированный "инструктивный" текст для вектора (Title + Breadcrumbs + Content). Это критично для понимания качества поиска.

-----

## 📦 7.2 Instrumentation: Infrastructure Layer

Внедрение логов в слои взаимодействия с внешним миром (API, БД).

**Цель:** Диагностика сетевых проблем, стоимости и производительности.

1. **`google/gemini_client.py` & `embedder.py`:**

      * `INFO 🧠`: Отправка запроса (модель, кол-во токенов).
      * `DEBUG 🛡️`: Срабатывание Rate Limiter (пауза).
      * `WARNING 🛡️`: Retry при ошибке 429/503.
      * `TRACE`: Полный JSON запрос и ответ (сырой).

2. **`storage/peewee/adapter.py`:**

      * `INFO 💾`: Массовая вставка (bulk insert) — кол-во записей.
      * `DEBUG 🔍`: Сгенерированный SQL для гибридного поиска (RRF).
      * `TRACE`: Дамп векторов (хеш или первые 3 измерения, не весь blob).

3. **`media/utils/*` (ffmpeg, pillow):**

      * `INFO 🎬`: Начало конвертации/извлечения кадров.
      * `DEBUG`: Параметры ffmpeg (битрейт, кодек).
      * `WARNING ⚠️`: Файл не найден или битый формат.

4. **`batching/batch_manager.py`:**

      * `INFO 📦`: Создание батча (ID, кол-во задач).
      * `INFO 🔄`: Синхронизация статуса (Polling).
      * `SUCCESS ✅`: Батч завершен, результаты скачаны.
      * `ERROR ❌`: Частичный сбой батча (список ID ошибок).

-----

## 📦 7.3 Configuration & UX

Настройка того, как пользователь управляет логами.

1. **Функция `setup_logging(config)`:**

      * Аргументы: `level` (str), `json_format` (bool), `log_file` (path).
      * Настройка `RichHandler` для консоли (цветной вывод, форматирование таблиц).
      * Настройка `FileHandler` для файла (подробный режим).

2. **Интеграция с `GeminiConfig`:**

      * Добавить поле `log_level` в конфиг.
      * Автоматическая инициализация логгера при старте `SemanticCore`.

3. **Утилита `dump_debug_info()`:**

      * Метод, который собирает последние N строк логов, версию библиотеки, конфигурацию (без ключей) и сохраняет в `debug_report.txt` для передачи Агенту или в поддержку.

-----

### Пример итогового вывода в консоли (Rich)

```text
[14:20:01] 📥 Ingesting: 'architecture.md' (Size: 12KB)           pipeline.py:45
[14:20:01] 🧶 Parsed Markdown: 3 Headers, 2 Code Blocks, 1 Image  markdown_parser.py:88
[14:20:02] ✂️ Created 15 Chunks (Strategy: Smart)                 smart_splitter.py:120
[14:20:02] 👁️ Found Image Ref: 'diagram.png'. Queuing analysis... markdown_assets.py:50
[14:20:03] 📦 Async Mode: 15 text chunks -> Batch Queue           pipeline.py:200
[14:20:03] ✅ Ingestion Complete. 16 tasks pending.               pipeline.py:210
```

### Пример файла (TRACE)

```text
2025-12-03 14:20:02 | SPLITTER | TRACE | Chunk #4 Context Payload:
{
  "headers": ["System Design", "Database"],
  "content": "We use SQLite for local storage...",
  "vector_text": "Document: Architecture\nSection: System Design > Database\nContent: We use SQLite..."
}
```
