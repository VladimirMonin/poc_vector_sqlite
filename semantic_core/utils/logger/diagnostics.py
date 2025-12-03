"""Диагностические утилиты для системы логирования.

Функции:
    dump_debug_info()
        Собирает информацию о системе для баг-репортов.

    check_config()
        Валидирует конфигурацию логирования.

    get_handlers_info()
        Возвращает информацию об активных хендлерах.
"""

from __future__ import annotations

import logging
import os
import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import LoggingConfig
from .filters import SensitiveDataFilter


def get_package_versions() -> dict[str, str]:
    """Получает версии установленных пакетов.

    Returns:
        Словарь {package_name: version}.
    """
    versions: dict[str, str] = {}

    # semantic_core (из pyproject.toml или __version__)
    try:
        from semantic_core import __version__  # type: ignore[attr-defined]

        versions["semantic_core"] = __version__
    except (ImportError, AttributeError):
        versions["semantic_core"] = "unknown"

    # Основные зависимости
    packages = ["peewee", "pydantic", "rich"]

    for package in packages:
        try:
            mod = __import__(package)
            versions[package] = getattr(mod, "__version__", "unknown")
        except ImportError:
            versions[package] = "not installed"

    # sqlite-vec
    try:
        import sqlite_vec

        versions["sqlite-vec"] = getattr(sqlite_vec, "__version__", "installed")
    except ImportError:
        versions["sqlite-vec"] = "not installed"

    # pydantic-settings
    try:
        import pydantic_settings

        versions["pydantic-settings"] = getattr(
            pydantic_settings, "__version__", "installed"
        )
    except ImportError:
        versions["pydantic-settings"] = "not installed"

    return versions


def get_sqlite_info() -> dict[str, str]:
    """Получает информацию о SQLite.

    Returns:
        Словарь с версиями SQLite и расширений.
    """
    import sqlite3

    info: dict[str, str] = {}

    # Версия SQLite
    info["sqlite_version"] = sqlite3.sqlite_version
    info["sqlite_version_info"] = ".".join(map(str, sqlite3.sqlite_version_info))

    # Проверяем vec0 расширение
    try:
        conn = sqlite3.connect(":memory:")
        import sqlite_vec

        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        # Проверяем что расширение работает
        cursor = conn.execute("SELECT vec_version()")
        vec_version = cursor.fetchone()[0]
        info["vec0"] = f"loaded (v{vec_version})"
        conn.close()
    except Exception as e:
        info["vec0"] = f"error: {e}"

    # Проверяем fts5
    try:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE VIRTUAL TABLE test USING fts5(content)")
        info["fts5"] = "available"
        conn.close()
    except Exception:
        info["fts5"] = "not available"

    return info


def get_handlers_info() -> list[dict[str, Any]]:
    """Получает информацию об активных хендлерах логирования.

    Returns:
        Список словарей с информацией о хендлерах.
    """
    root_logger = logging.getLogger("semantic_core")
    handlers_info: list[dict[str, Any]] = []

    for handler in root_logger.handlers:
        handler_info: dict[str, Any] = {
            "type": type(handler).__name__,
            "level": logging.getLevelName(handler.level),
        }

        # FileHandler — добавляем путь
        if isinstance(handler, logging.FileHandler):
            handler_info["file"] = handler.baseFilename

        # Форматтер
        if handler.formatter:
            handler_info["formatter"] = type(handler.formatter).__name__

        # Фильтры
        filters = [type(f).__name__ for f in handler.filters]
        if filters:
            handler_info["filters"] = filters

        handlers_info.append(handler_info)

    return handlers_info


def get_environment_vars() -> dict[str, str]:
    """Получает значения SEMANTIC_* переменных окружения.

    Returns:
        Словарь с переменными (без секретов).
    """
    prefix = "SEMANTIC_"
    env_vars: dict[str, str] = {}

    for key, value in os.environ.items():
        if key.startswith(prefix):
            # Не показываем значения, которые могут быть секретами
            if any(secret in key.upper() for secret in ["KEY", "SECRET", "TOKEN"]):
                env_vars[key] = "***SET***"
            else:
                env_vars[key] = value

    return env_vars


def dump_debug_info(config: LoggingConfig | None = None) -> str:
    """Собирает полную диагностическую информацию.

    Формирует текстовый отчёт для баг-репортов, включающий:
    - Информацию о системе (Python, OS)
    - Версии пакетов
    - Конфигурацию логирования (без секретов)
    - Переменные окружения SEMANTIC_*
    - Информацию о SQLite и расширениях
    - Активные хендлеры логирования

    Args:
        config: Конфигурация логирования (если None, берётся текущая).

    Returns:
        Отформатированный текстовый отчёт.

    Example:
        >>> from semantic_core.utils.logger.diagnostics import dump_debug_info
        >>> print(dump_debug_info())
        === Semantic Core Debug Info ===
        Generated: 2024-12-03T14:30:00
        ...
    """
    if config is None:
        from . import get_current_config

        config = get_current_config()

    lines: list[str] = []

    # Заголовок
    lines.append("=" * 40)
    lines.append("Semantic Core Debug Info")
    lines.append("=" * 40)
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append("")

    # System
    lines.append("[System]")
    lines.append(f"Python: {sys.version.split()[0]}")
    lines.append(f"Platform: {platform.platform()}")
    lines.append(f"Architecture: {platform.machine()}")
    lines.append(f"OS: {platform.system()} {platform.release()}")
    lines.append("")

    # Package Versions
    lines.append("[Packages]")
    versions = get_package_versions()
    for package, version in sorted(versions.items()):
        lines.append(f"{package}: {version}")
    lines.append("")

    # Config (без секретов)
    lines.append("[Logging Config]")
    lines.append(f"level: {config.level}")
    lines.append(f"file_level: {config.file_level}")
    lines.append(f"log_file: {config.log_file or 'None (console only)'}")
    lines.append(f"json_format: {config.json_format}")
    lines.append(f"show_path: {config.show_path}")
    lines.append(f"redact_secrets: {config.redact_secrets}")
    lines.append(f"console_width: {config.console_width}")
    lines.append("")

    # Environment Variables
    lines.append("[Environment Variables]")
    env_vars = get_environment_vars()
    if env_vars:
        for key, value in sorted(env_vars.items()):
            lines.append(f"{key}: {value}")
    else:
        lines.append("No SEMANTIC_* variables set")
    lines.append("")

    # SQLite Info
    lines.append("[SQLite]")
    sqlite_info = get_sqlite_info()
    for key, value in sqlite_info.items():
        lines.append(f"{key}: {value}")
    lines.append("")

    # Handlers
    lines.append("[Active Handlers]")
    handlers = get_handlers_info()
    if handlers:
        for i, h in enumerate(handlers, 1):
            handler_str = f"{i}. {h['type']} (level={h['level']})"
            if "file" in h:
                handler_str += f" → {h['file']}"
            lines.append(handler_str)
            if "filters" in h:
                lines.append(f"   Filters: {', '.join(h['filters'])}")
    else:
        lines.append("No handlers configured")

    lines.append("")
    lines.append("=" * 40)

    return "\n".join(lines)


def check_config(config: LoggingConfig | None = None) -> list[str]:
    """Валидирует конфигурацию логирования.

    Проверяет:
    - Доступность файла для записи (если указан log_file)
    - Корректность уровня логирования
    - Работу SensitiveDataFilter

    Args:
        config: Конфигурация для проверки (если None, берётся текущая).

    Returns:
        Список предупреждений (пустой если всё OK).

    Example:
        >>> from semantic_core.utils.logger.diagnostics import check_config
        >>> warnings = check_config()
        >>> if warnings:
        ...     for w in warnings:
        ...         print(f"⚠️ {w}")
    """
    if config is None:
        from . import get_current_config

        config = get_current_config()

    warnings: list[str] = []

    # Проверяем путь к файлу
    if config.log_file:
        log_path = Path(config.log_file)

        # Проверяем существование директории
        if not log_path.parent.exists():
            warnings.append(
                f"Log directory does not exist: {log_path.parent}. "
                "It will be created on first write."
            )
        # Проверяем права на запись
        elif log_path.exists() and not os.access(log_path, os.W_OK):
            warnings.append(f"Log file is not writable: {log_path}")
        elif not log_path.exists():
            # Проверяем можем ли создать файл
            if not os.access(log_path.parent, os.W_OK):
                warnings.append(
                    f"Cannot create log file, directory not writable: {log_path.parent}"
                )

    # Проверяем уровни
    valid_levels = {"TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if config.level not in valid_levels:
        warnings.append(f"Invalid console level: {config.level}")
    if config.file_level not in valid_levels:
        warnings.append(f"Invalid file level: {config.file_level}")

    # Проверяем SensitiveDataFilter
    if config.redact_secrets:
        try:
            filter_ = SensitiveDataFilter()
            test_key = "AIzaSyD-test123456789012345678901234"
            result = filter_._redact_string(test_key)
            if test_key in result:
                warnings.append("SensitiveDataFilter is not redacting Google API keys")
        except Exception as e:
            warnings.append(f"SensitiveDataFilter error: {e}")

    # Проверяем console_width
    if config.console_width < 80:
        warnings.append(
            f"Console width {config.console_width} is very narrow, "
            "may cause formatting issues"
        )

    return warnings
