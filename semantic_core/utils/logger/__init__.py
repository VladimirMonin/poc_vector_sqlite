"""Система семантического логирования с эмодзи и фильтрацией секретов.

Функции:
    get_logger(name: str) -> SemanticLogger
        Получить настроенный логгер для модуля.

    setup_logging(config: LoggingConfig | None = None) -> None
        Инициализировать систему логирования.

    dump_debug_info(config: LoggingConfig | None = None) -> str
        Собрать диагностическую информацию для баг-репортов.

    check_config(config: LoggingConfig | None = None) -> list[str]
        Валидировать конфигурацию логирования.

Классы:
    SemanticLogger
        Адаптер с поддержкой контекста (bind) и специальных методов.

    LoggingConfig
        Pydantic-модель конфигурации с поддержкой environment variables.

Константы:
    TRACE: int
        Уровень TRACE (5), ниже DEBUG.

Environment Variables:
    SEMANTIC_LOG_LEVEL: Уровень консольного вывода (DEBUG/INFO/WARNING/ERROR).
    SEMANTIC_LOG_FILE: Путь к файлу логов.
    SEMANTIC_LOG_JSON: JSON-формат для файла (true/false).
    SEMANTIC_LOG_REDACT: Маскировать API-ключи (true/false).

Example:
    >>> from semantic_core.utils.logger import get_logger, setup_logging
    >>>
    >>> # Инициализация (опционально, работает с дефолтами)
    >>> setup_logging()
    >>>
    >>> # Получение логгера
    >>> logger = get_logger(__name__)
    >>> logger.info("Hello, world!")
    >>>
    >>> # С привязкой контекста
    >>> log = logger.bind(batch_id="batch-123")
    >>> log.info("Processing batch")  # -> 📦 [batch-123] Processing batch
    >>>
    >>> # Диагностика
    >>> from semantic_core.utils.logger import dump_debug_info
    >>> print(dump_debug_info())
"""

import logging
from typing import TYPE_CHECKING

from rich.logging import RichHandler

from .config import LoggingConfig
from .filters import SensitiveDataFilter
from .formatters import ConsoleFormatter, FileFormatter, JSONFormatter
from .levels import TRACE, install_trace_level
from .logger import SemanticLogger
from .diagnostics import dump_debug_info, check_config, get_handlers_info

if TYPE_CHECKING:
    pass

# Убеждаемся, что TRACE установлен
install_trace_level()

# Глобальное состояние
_logging_configured: bool = False
_current_config: LoggingConfig | None = None

# Корневой логгер для semantic_core
ROOT_LOGGER_NAME: str = "semantic_core"


def setup_logging(config: LoggingConfig | None = None) -> None:
    """Инициализирует систему логирования.

    Настраивает:
    - RichHandler для консоли (цветной вывод)
    - FileHandler для файла (опционально)
    - SensitiveDataFilter для маскирования секретов
    - EmojiFormatter для семантических иконок

    Args:
        config: Конфигурация логирования. Если None, используются дефолты.

    Note:
        Безопасно вызывать повторно — старые хендлеры будут удалены.
    """
    global _logging_configured, _current_config

    config = config or LoggingConfig()
    _current_config = config

    # Получаем корневой логгер semantic_core
    root_logger = logging.getLogger(ROOT_LOGGER_NAME)

    # Удаляем существующие хендлеры
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Устанавливаем минимальный уровень (TRACE чтобы не фильтровать раньше хендлеров)
    root_logger.setLevel(TRACE)

    # Создаём фильтр секретов
    sensitive_filter = SensitiveDataFilter() if config.redact_secrets else None

    # === Console Handler (Rich) ===
    console_level = getattr(logging, config.level, logging.INFO)

    # Используем RichHandler для красивого вывода
    # show_level=False - мы сами добавляем эмодзи для уровней через SemanticLogger
    # markup=False - отключаем, т.к. наши [context-id] интерпретируются как стили
    console_handler = RichHandler(
        level=console_level,
        show_time=True,
        show_level=False,  # Отключаем, т.к. мы добавляем свои эмодзи
        show_path=config.show_path,
        rich_tracebacks=True,
        tracebacks_show_locals=False,
        markup=False,  # Важно! Иначе [batch-123] интерпретируется как style tag
    )

    # RichHandler использует getMessage() напрямую, поэтому эмодзи добавляются в SemanticLogger._log()
    # ConsoleFormatter не нужен - RichHandler игнорирует большинство его полей

    if sensitive_filter:
        console_handler.addFilter(sensitive_filter)

    root_logger.addHandler(console_handler)

    # === File Handler (опционально) ===
    if config.log_file:
        file_level = getattr(logging, config.file_level, TRACE)

        file_handler = logging.FileHandler(
            config.log_file,
            mode="a",
            encoding="utf-8",
        )
        file_handler.setLevel(file_level)

        file_formatter = FileFormatter(json_context=config.json_format)
        file_handler.setFormatter(file_formatter)

        if sensitive_filter:
            file_handler.addFilter(sensitive_filter)

        root_logger.addHandler(file_handler)

    # Отключаем propagation чтобы не дублировать в root logger
    root_logger.propagate = False

    _logging_configured = True


def get_logger(name: str) -> SemanticLogger:
    """Получить настроенный логгер для модуля.

    Args:
        name: Имя модуля (обычно __name__).

    Returns:
        SemanticLogger с поддержкой контекста и эмодзи.

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Document loaded", doc_id="doc-123")
        >>>
        >>> # С привязкой контекста
        >>> log = logger.bind(batch_id="batch-456")
        >>> log.info("Batch started")
    """
    global _logging_configured

    # Ленивая инициализация с дефолтами
    if not _logging_configured:
        setup_logging()

    return SemanticLogger(name)


def get_current_config() -> LoggingConfig:
    """Возвращает текущую конфигурацию логирования.

    Returns:
        Активная LoggingConfig или дефолтная если не настроено.
    """
    return _current_config or LoggingConfig()


# Публичный API
__all__ = [
    # Константы
    "TRACE",
    # Функции
    "get_logger",
    "setup_logging",
    "get_current_config",
    # Диагностика
    "dump_debug_info",
    "check_config",
    "get_handlers_info",
    # Классы
    "SemanticLogger",
    "LoggingConfig",
    # Форматтеры (для кастомизации)
    "ConsoleFormatter",
    "FileFormatter",
    "JSONFormatter",
    # Фильтры (для кастомизации)
    "SensitiveDataFilter",
]
