"""Форматтеры логирования с семантическими эмодзи.

Классы:
    EmojiFormatter
        Форматтер с эмодзи для визуальной идентификации модулей.

    ConsoleFormatter
        Компактный форматтер для консольного вывода.

    FileFormatter
        Подробный форматтер для файлового вывода.
"""

import json
import logging
from datetime import datetime
from typing import Any

from .levels import TRACE

# Маппинг паттернов имени модуля на эмодзи
# ВАЖНО: Этот маппинг уже содержит все паттерны для Phase 7.1, 7.2, 7.3
# Агентам НЕ нужно его модифицировать!
EMOJI_MAP: dict[str, str] = {
    # Pipeline & Orchestration
    "pipeline": "📥",
    "core": "📥",
    # Text Processing (Phase 7.1)
    "parser": "🧶",
    "parsers": "🧶",
    "markdown": "🧶",
    "splitter": "✂️",
    "splitters": "✂️",
    "context": "🧬",
    "hierarchy": "🧬",
    "hierarchical": "🧬",
    "enricher": "🖼️",
    "enrichers": "🖼️",
    "asset": "🖼️",
    "assets": "🖼️",
    # Media Analysis (Phase 7.2)
    "image": "👁️",
    "images": "👁️",
    "vision": "👁️",
    "audio": "🎙️",
    "video": "🎬",
    "media": "🎞️",
    "frame": "🎞️",
    "frames": "🎞️",
    "optimize": "⚡",
    "optimization": "⚡",
    # AI & Embeddings (Phase 7.2)
    "embed": "🧠",
    "embedder": "🧠",
    "embeddings": "🧠",
    "gemini": "🧠",
    "api": "🌐",
    # Batching & Queues (Phase 7.2)
    "batch": "📦",
    "batching": "📦",
    "queue": "📦",
    # Storage & Database (Phase 7.2)
    "storage": "💾",
    "adapter": "💾",
    "peewee": "💾",
    "database": "🗄️",
    "engine": "🗄️",
    "model": "🗄️",
    "models": "🗄️",
    # Search
    "search": "🔍",
    # Security & Rate Limiting (Phase 7.2)
    "rate": "🛡️",
    "limit": "🛡️",
    "limiter": "🛡️",
    "auth": "🛡️",
    "resilience": "🛡️",
    "retry": "🔄",
    # File & Token utilities (Phase 7.2)
    "file": "📁",
    "files": "📁",
    "token": "🔢",
    "tokens": "🔢",
    # Diagnostics (Phase 7.3)
    "diagnostic": "🩺",
    "diagnostics": "🩺",
    "config": "⚙️",
    # CLI (Phase 8.1)
    "cli": "🖥️",
    "worker": "👷",
    "commands": "🖥️",
}

# Эмодзи для уровней логирования
LEVEL_EMOJI: dict[int, str] = {
    logging.CRITICAL: "💀",
    logging.ERROR: "❌",
    logging.WARNING: "⚠️",
    logging.INFO: "",  # Для INFO используем эмодзи модуля
    logging.DEBUG: "🔧",
    TRACE: "🔬",
}

# Fallback эмодзи для неизвестных модулей
FALLBACK_EMOJI: str = "📌"

# Ключи контекста для отображения в префиксе
CONTEXT_ID_KEYS: tuple[str, ...] = (
    "batch_id",
    "doc_id",
    "chunk_id",
    "task_id",
    "request_id",
)


def get_module_emoji(logger_name: str) -> str:
    """Определяет эмодзи по имени логгера.

    Args:
        logger_name: Полное имя логгера (например, semantic_core.pipeline).

    Returns:
        Эмодзи для модуля или FALLBACK_EMOJI.
    """
    # Разбиваем имя на компоненты
    parts = logger_name.lower().split(".")

    # Ищем совпадение с конца (более специфичные модули)
    for part in reversed(parts):
        if part in EMOJI_MAP:
            return EMOJI_MAP[part]

    # Fallback
    return FALLBACK_EMOJI


def format_context_prefix(record: logging.LogRecord) -> str:
    """Формирует префикс с Context ID.

    Args:
        record: Запись лога.

    Returns:
        Строка вида "[batch-123/doc-abc]" или пустая строка.
    """
    context_ids: list[str] = []

    for key in CONTEXT_ID_KEYS:
        value = getattr(record, key, None)
        if value:
            context_ids.append(str(value))

    if context_ids:
        return f"[{'/'.join(context_ids)}] "
    return ""


def format_extra_context(record: logging.LogRecord) -> dict[str, Any]:
    """Извлекает дополнительный контекст из записи.

    Args:
        record: Запись лога.

    Returns:
        Словарь с контекстом (без стандартных полей LogRecord).
    """
    # Стандартные поля LogRecord, которые не нужно включать
    standard_fields = {
        "name",
        "msg",
        "args",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "exc_info",
        "exc_text",
        "thread",
        "threadName",
        "taskName",
        "message",
    }

    # Поля контекста уже отображены в префиксе
    context_fields = set(CONTEXT_ID_KEYS)

    extra: dict[str, Any] = {}
    for key, value in record.__dict__.items():
        if key not in standard_fields and key not in context_fields:
            if not key.startswith("_"):
                extra[key] = value

    return extra


class ConsoleFormatter(logging.Formatter):
    """Компактный форматтер для консольного вывода.

    Формат: [HH:MM:SS] 📥 [context-id] Message              module.py:42
    """

    def __init__(self, show_path: bool = True, width: int = 120) -> None:
        """Инициализирует форматтер.

        Args:
            show_path: Показывать путь к файлу.
            width: Ширина вывода для выравнивания.
        """
        super().__init__()
        self.show_path = show_path
        self.width = width

    def format(self, record: logging.LogRecord) -> str:
        """Форматирует запись для консоли.

        Args:
            record: Запись лога.

        Returns:
            Отформатированная строка.
        """
        # Время
        time_str = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")

        # Эмодзи (уровень имеет приоритет для ERROR/WARNING)
        level_emoji = LEVEL_EMOJI.get(record.levelno, "")
        module_emoji = get_module_emoji(record.name)
        emoji = level_emoji or module_emoji

        # Контекст
        context_prefix = format_context_prefix(record)

        # Сообщение
        message = record.getMessage()

        # Основная часть
        main_part = f"[{time_str}] {emoji} {context_prefix}{message}"

        # Путь к файлу (выровнен вправо)
        if self.show_path:
            path_part = f"{record.filename}:{record.lineno}"
            # Вычисляем отступ для выравнивания
            padding = self.width - len(main_part) - len(path_part)
            if padding > 0:
                return f"{main_part}{' ' * padding}{path_part}"
            return f"{main_part}  {path_part}"

        return main_part


class FileFormatter(logging.Formatter):
    """Подробный форматтер для файлового вывода.

    Формат: 2025-12-03 14:20:02 | MODULE | LEVEL | 📥 [context] Message | {"extra": "data"}
    """

    def __init__(self, json_context: bool = False) -> None:
        """Инициализирует форматтер.

        Args:
            json_context: Выводить контекст как JSON.
        """
        super().__init__()
        self.json_context = json_context

    def format(self, record: logging.LogRecord) -> str:
        """Форматирует запись для файла.

        Args:
            record: Запись лога.

        Returns:
            Отформатированная строка.
        """
        # Время ISO формат
        time_str = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")

        # Модуль (последняя часть имени логгера)
        module = record.name.split(".")[-1].upper()

        # Уровень
        level = record.levelname

        # Эмодзи
        emoji = get_module_emoji(record.name)

        # Контекст ID
        context_prefix = format_context_prefix(record)

        # Сообщение
        message = record.getMessage()

        # Дополнительный контекст
        extra = format_extra_context(record)

        # Основная часть
        parts = [time_str, module, level, f"{emoji} {context_prefix}{message}"]

        # Добавляем extra если есть
        if extra:
            if self.json_context:
                parts.append(json.dumps(extra, ensure_ascii=False, default=str))
            else:
                extra_str = " ".join(f"{k}={v}" for k, v in extra.items())
                parts.append(extra_str)

        result = " | ".join(parts)

        # Добавляем traceback если есть
        if record.exc_info:
            result += "\n" + self.formatException(record.exc_info)

        return result


class JSONFormatter(logging.Formatter):
    """JSON-форматтер для логов.

    Формирует структурированный JSON для интеграции с log aggregators
    (Elasticsearch, Loki, CloudWatch, etc.).

    Формат:
        {
            "timestamp": "2024-12-03T14:30:00.123Z",
            "level": "INFO",
            "logger": "semantic_core.pipeline",
            "message": "Document processed",
            "context": {"doc_id": "doc-123"},
            "extra": {"chunk_count": 15},
            "location": {"file": "pipeline.py", "line": 42, "function": "ingest"}
        }
    """

    def __init__(self, include_location: bool = True) -> None:
        """Инициализирует форматтер.

        Args:
            include_location: Включать информацию о месте в коде.
        """
        super().__init__()
        self.include_location = include_location

    def format(self, record: logging.LogRecord) -> str:
        """Форматирует запись как JSON.

        Args:
            record: Запись лога.

        Returns:
            JSON-строка.
        """
        # Базовые поля
        data: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Context IDs (batch_id, doc_id, etc.)
        context: dict[str, Any] = {}
        for key in CONTEXT_ID_KEYS:
            value = getattr(record, key, None)
            if value is not None:
                context[key] = value
        if context:
            data["context"] = context

        # Extra fields
        extra = format_extra_context(record)
        if extra:
            data["extra"] = extra

        # Location info
        if self.include_location:
            data["location"] = {
                "file": record.filename,
                "line": record.lineno,
                "function": record.funcName,
            }

        # Exception info
        if record.exc_info:
            data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info),
            }

        return json.dumps(data, ensure_ascii=False, default=str)


# Алиас для обратной совместимости
EmojiFormatter = ConsoleFormatter
