"""
Конфигурация проекта на основе Pydantic Settings.

Автоматически загружает переменные окружения из .env файла
и выполняет валидацию настроек.
"""

from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Основные настройки приложения.

    Attributes:
        gemini_api_key: API ключ для Google Gemini (обязательный)
        sqlite_db_path: Путь к файлу SQLite базы данных
        embedding_model: Модель для генерации эмбеддингов
        embedding_dimension: Размерность векторов (768 для MRL)
    """

    gemini_api_key: str = Field(..., description="API ключ для Google Gemini AI Studio")

    sqlite_db_path: Path = Field(
        default=Path("./vector_store.db"), description="Путь к файлу базы данных SQLite"
    )

    embedding_model: str = Field(
        default="models/gemini-embedding-001", description="Модель Gemini для эмбеддингов"
    )

    embedding_dimension: int = Field(
        default=768, description="Размерность векторов (768 для MRL режима)"
    )

    @field_validator("sqlite_db_path", mode="before")
    @classmethod
    def resolve_db_path(cls, v) -> Path:
        """Преобразует строку в Path и резолвит относительный путь."""
        path = Path(v)
        # Если путь относительный, делаем его абсолютным относительно корня проекта
        if not path.is_absolute():
            return path.resolve()
        return path

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )


# Глобальный экземпляр настроек (ленивая инициализация)
settings = Settings()
