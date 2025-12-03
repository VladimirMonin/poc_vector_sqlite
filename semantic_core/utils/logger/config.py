"""Конфигурация системы логирования.

Классы:
    LoggingConfig
        Pydantic-модель для настройки логирования.
"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class LoggingConfig(BaseModel):
    """Конфигурация системы логирования.

    Attributes:
        level: Минимальный уровень для консольного вывода.
        file_level: Минимальный уровень для файлового вывода.
        log_file: Путь к файлу логов (None = только консоль).
        json_format: Использовать JSON-формат для файла.
        show_path: Показывать путь к модулю в выводе.
        redact_secrets: Маскировать API-ключи в логах.
        console_width: Ширина консольного вывода (для выравнивания).
    """

    level: Literal["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Минимальный уровень для консольного вывода"
    )

    file_level: Literal["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = (
        Field(default="TRACE", description="Минимальный уровень для файлового вывода")
    )

    log_file: Path | None = Field(
        default=None, description="Путь к файлу логов (None = только консоль)"
    )

    json_format: bool = Field(
        default=False, description="Использовать JSON-формат для файла"
    )

    show_path: bool = Field(
        default=True, description="Показывать путь к модулю в выводе"
    )

    redact_secrets: bool = Field(
        default=True, description="Маскировать API-ключи в логах"
    )

    console_width: int = Field(
        default=120,
        ge=80,
        le=300,
        description="Ширина консольного вывода (для выравнивания)",
    )

    model_config = {
        "frozen": True,
        "extra": "forbid",
    }
