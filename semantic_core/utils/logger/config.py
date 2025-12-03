"""Конфигурация системы логирования.

Классы:
    LoggingConfig
        Pydantic-модель для настройки логирования с поддержкой env variables.

Environment Variables:
    SEMANTIC_LOG_LEVEL: Уровень логирования (DEBUG/INFO/WARNING/ERROR).
    SEMANTIC_LOG_FILE: Путь к файлу логов.
    SEMANTIC_LOG_JSON: Включить JSON-формат (true/false).
    SEMANTIC_LOG_REDACT: Маскировать API-ключи (true/false).
"""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Допустимые уровни логирования
LogLevel = Literal["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class LoggingConfig(BaseSettings):
    """Конфигурация системы логирования.

    Поддерживает загрузку из environment variables с префиксом SEMANTIC_LOG_.

    Приоритет настроек (от высшего к низшему):
        1. Явный параметр в коде
        2. Environment variable
        3. Default value

    Attributes:
        level: Минимальный уровень для консольного вывода.
        file_level: Минимальный уровень для файлового вывода.
        log_file: Путь к файлу логов (None = только консоль).
        json_format: Использовать JSON-формат для файла.
        show_path: Показывать путь к модулю в выводе.
        redact_secrets: Маскировать API-ключи в логах.
        console_width: Ширина консольного вывода (для выравнивания).

    Environment Variables:
        SEMANTIC_LOG_LEVEL: Уровень консольного вывода.
        SEMANTIC_LOG_FILE_LEVEL: Уровень файлового вывода.
        SEMANTIC_LOG_FILE: Путь к файлу логов.
        SEMANTIC_LOG_JSON: JSON-формат (true/false).
        SEMANTIC_LOG_SHOW_PATH: Показывать путь (true/false).
        SEMANTIC_LOG_REDACT: Маскировать секреты (true/false).
        SEMANTIC_LOG_WIDTH: Ширина консоли.

    Example:
        >>> # Через код
        >>> config = LoggingConfig(level="DEBUG", log_file="/tmp/app.log")
        >>>
        >>> # Через environment
        >>> # export SEMANTIC_LOG_LEVEL=DEBUG
        >>> # export SEMANTIC_LOG_FILE=/tmp/app.log
        >>> config = LoggingConfig()  # Прочитает из env
    """

    level: LogLevel = Field(
        default="INFO",
        description="Минимальный уровень для консольного вывода",
    )

    file_level: LogLevel = Field(
        default="TRACE",
        description="Минимальный уровень для файлового вывода",
    )

    log_file: Path | None = Field(
        default=None,
        alias="file",
        description="Путь к файлу логов (None = только консоль)",
    )

    json_format: bool = Field(
        default=False,
        alias="json",
        description="Использовать JSON-формат для файла",
    )

    show_path: bool = Field(
        default=True,
        description="Показывать путь к модулю в выводе",
    )

    redact_secrets: bool = Field(
        default=True,
        alias="redact",
        description="Маскировать API-ключи в логах",
    )

    console_width: int = Field(
        default=120,
        ge=80,
        le=300,
        alias="width",
        description="Ширина консольного вывода (для выравнивания)",
    )

    model_config = SettingsConfigDict(
        env_prefix="SEMANTIC_LOG_",
        env_file=None,  # Не читаем .env автоматически
        extra="forbid",
        frozen=True,
        populate_by_name=True,  # Позволяет использовать и alias, и field name
    )
