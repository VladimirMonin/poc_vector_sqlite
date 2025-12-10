"""Конфигурация Flask приложения через Pydantic Settings.

Загружает настройки из (в порядке приоритета):
1. Environment variables
2. .env файл (если есть)
3. Default values

Classes:
    FlaskAppConfig: Настройки Flask приложения.

Functions:
    get_flask_config: Получить конфигурацию (singleton).
"""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FlaskAppConfig(BaseSettings):
    """Настройки Flask приложения.

    Загружает из environment variables и .env файла.
    Использует SemanticConfig для настроек ядра.

    Attributes:
        secret_key: Секретный ключ Flask (обязателен в проде).
        debug: Режим отладки.
        host: Хост для запуска.
        port: Порт для запуска.
        upload_folder: Папка для загруженных файлов.
        max_content_length: Максимальный размер загрузки (байты).

    Environment Variables:
        FLASK_SECRET_KEY: Секретный ключ.
        FLASK_DEBUG: Режим отладки (true/false).
        FLASK_HOST: Хост.
        FLASK_PORT: Порт.
        FLASK_UPLOAD_FOLDER: Папка загрузок.
        FLASK_MAX_CONTENT_LENGTH: Максимальный размер.
    """

    model_config = SettingsConfigDict(
        env_prefix="FLASK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Flask настройки
    secret_key: str = Field(
        default="dev-secret-key-change-in-production",
        description="Секретный ключ Flask",
    )
    debug: bool = Field(default=True, description="Режим отладки")
    host: str = Field(default="127.0.0.1", description="Хост для запуска")
    port: int = Field(default=5000, description="Порт для запуска")

    # Upload настройки
    upload_folder: Path = Field(
        default=Path("uploads"),
        description="Папка для загруженных файлов",
    )
    max_content_length: int = Field(
        default=50 * 1024 * 1024,  # 50MB
        description="Максимальный размер загрузки в байтах",
    )

    def to_flask_config(self) -> dict:
        """Преобразовать в словарь для Flask app.config.

        Returns:
            Словарь настроек для Flask.
        """
        return {
            "SECRET_KEY": self.secret_key,
            "DEBUG": self.debug,
            "UPLOAD_FOLDER": str(self.upload_folder),
            "MAX_CONTENT_LENGTH": self.max_content_length,
        }


# Singleton
_flask_config: Optional[FlaskAppConfig] = None


def get_flask_config(**overrides) -> FlaskAppConfig:
    """Получить конфигурацию Flask приложения.

    Args:
        **overrides: Переопределения настроек.

    Returns:
        FlaskAppConfig с загруженными настройками.
    """
    global _flask_config

    if overrides:
        # С override'ами — создаём новый экземпляр
        return FlaskAppConfig(**overrides)

    if _flask_config is None:
        _flask_config = FlaskAppConfig()

    return _flask_config


def reset_flask_config() -> None:
    """Сбросить кэшированную конфигурацию (для тестов)."""
    global _flask_config
    _flask_config = None
