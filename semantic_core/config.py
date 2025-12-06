"""Единая конфигурация Semantic Core.

Загружает настройки из (в порядке приоритета):
1. CLI аргументы (переданные как kwargs)
2. Environment variables (SEMANTIC_*, GEMINI_API_KEY)
3. semantic.toml в текущей директории
4. Default values

Классы:
    SemanticConfig
        Pydantic Settings с поддержкой TOML и env variables.

Функции:
    get_config
        Получить конфигурацию с возможными override'ами.
    find_config_file
        Найти semantic.toml в текущей или родительских директориях.

Example:
    >>> from semantic_core.config import SemanticConfig, get_config
    >>>
    >>> # Автоматическая загрузка из env + TOML
    >>> config = SemanticConfig()
    >>> print(config.db_path)
    >>>
    >>> # С CLI override'ами
    >>> config = get_config(db_path="/custom/path.db", log_level="DEBUG")
"""

from pathlib import Path
from typing import Literal, Optional, Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)


# Типы для строгой валидации
LogLevel = Literal["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
SplitterType = Literal["simple", "smart"]
ContextStrategyType = Literal["basic", "hierarchical"]
SearchType = Literal["vector", "fts", "hybrid"]


def find_config_file(start_dir: Optional[Path] = None) -> Optional[Path]:
    """Найти semantic.toml в текущей или родительских директориях.

    Args:
        start_dir: Начальная директория поиска (по умолчанию cwd).

    Returns:
        Path к semantic.toml или None если не найден.
    """
    current = start_dir or Path.cwd()

    # Ищем вверх по дереву директорий (максимум 10 уровней)
    for _ in range(10):
        config_path = current / "semantic.toml"
        if config_path.exists():
            return config_path

        parent = current.parent
        if parent == current:  # Достигли корня
            break
        current = parent

    return None


class SemanticConfig(BaseSettings):
    """Единая конфигурация Semantic Core.

    Объединяет все настройки библиотеки в один класс.
    Поддерживает загрузку из environment variables и TOML файла.

    Attributes:
        db_path: Путь к SQLite базе данных.
        gemini_api_key: API ключ для Gemini (обязательный).
        gemini_batch_key: Отдельный ключ для Batch API (опционально).
        embedding_model: Модель для эмбеддингов.
        embedding_dimension: Размерность векторов.
        splitter: Тип сплиттера (simple/smart).
        context_strategy: Стратегия контекста (basic/hierarchical).
        media_enabled: Включить обработку медиа.
        media_rpm_limit: Rate limit для Vision API.
        search_limit: Лимит результатов по умолчанию.
        search_type: Тип поиска по умолчанию.
        log_level: Уровень логирования.
        log_file: Путь к файлу логов.

    Environment Variables:
        GEMINI_API_KEY: API ключ (без префикса SEMANTIC_).
        GEMINI_BATCH_KEY: Batch API ключ.
        SEMANTIC_DB_PATH: Путь к БД.
        SEMANTIC_LOG_LEVEL: Уровень логов.
        SEMANTIC_SPLITTER: Тип сплиттера.
        ... и другие с префиксом SEMANTIC_.
    """

    # === Database ===
    db_path: Path = Field(
        default=Path("semantic.db"),
        description="Путь к SQLite базе данных",
    )

    # === Gemini API ===
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="API ключ для Google Gemini",
        validation_alias="GEMINI_API_KEY",  # Читаем напрямую из env без префикса
    )

    gemini_batch_key: Optional[str] = Field(
        default=None,
        description="Отдельный ключ для Batch API (опционально)",
        validation_alias="GEMINI_BATCH_KEY",  # Читаем напрямую из env без префикса
    )

    embedding_model: str = Field(
        default="models/gemini-embedding-001",
        description="Модель для генерации эмбеддингов",
    )

    embedding_dimension: int = Field(
        default=768,
        ge=256,
        le=3072,
        description="Размерность векторов",
    )

    llm_model: str = Field(
        default="models/gemini-2.0-flash",
        description="Модель LLM для RAG и чата",
    )

    # === Processing ===
    splitter: SplitterType = Field(
        default="smart",
        description="Тип сплиттера документов",
    )

    chunk_size: int = Field(
        default=1800,
        ge=500,
        le=8000,
        description="Размер текстового чанка в символах (рекомендуется 1800 для Gemini Embedding 2048 токенов)",
    )

    code_chunk_size: int = Field(
        default=2000,
        ge=500,
        le=10000,
        description="Размер чанка кода в символах",
    )

    context_strategy: ContextStrategyType = Field(
        default="hierarchical",
        description="Стратегия формирования контекста",
    )

    # === Media ===
    media_enabled: bool = Field(
        default=True,
        description="Включить обработку изображений/аудио/видео",
    )

    media_rpm_limit: int = Field(
        default=15,
        ge=1,
        le=100,
        description="Rate limit для Vision/Audio API (запросов/мин)",
    )

    max_output_tokens: int = Field(
        default=65_536,
        ge=1024,
        le=65_536,
        description="Максимальное количество токенов в ответе Gemini (image/audio/video analysis)",
    )

    # === Search ===
    search_limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Количество результатов по умолчанию",
    )

    search_type: SearchType = Field(
        default="hybrid",
        description="Тип поиска по умолчанию",
    )

    # === Logging ===
    log_level: LogLevel = Field(
        default="INFO",
        description="Уровень логирования",
    )

    log_file: Optional[Path] = Field(
        default=None,
        description="Путь к файлу логов (None = только консоль)",
    )

    # === Validators ===
    @field_validator("db_path", mode="before")
    @classmethod
    def validate_db_path(cls, v: Any) -> Path:
        """Преобразует строку в Path."""
        if v is None:
            return Path("semantic.db")
        return Path(v).expanduser()

    @field_validator("log_file", mode="before")
    @classmethod
    def validate_log_file(cls, v: Any) -> Optional[Path]:
        """Преобразует строку в Path."""
        if v is None or v == "":
            return None
        return Path(v).expanduser()

    @field_validator("gemini_api_key", "gemini_batch_key", mode="before")
    @classmethod
    def strip_whitespace(cls, v: Any) -> Optional[str]:
        """Убирает пробелы из ключей."""
        if v is None or v == "":
            return None
        return str(v).strip()

    @model_validator(mode="after")
    def log_config_source(self) -> "SemanticConfig":
        """Логирует источник конфигурации после загрузки."""
        logger.debug(
            "Config loaded",
            db_path=str(self.db_path),
            log_level=self.log_level,
            has_api_key=self.gemini_api_key is not None,
            has_batch_key=self.gemini_batch_key is not None,
        )
        return self

    model_config = SettingsConfigDict(
        # Префикс для env variables
        env_prefix="SEMANTIC_",
        # Gemini ключи читаются и с префиксом, и без
        # GEMINI_API_KEY -> gemini_api_key (через alias)
        # Читаем .env файл
        env_file=".env",
        env_file_encoding="utf-8",
        # Case-insensitive для env
        case_sensitive=False,
        # Разрешаем extra поля (для будущих расширений)
        extra="ignore",
        # Вложенные настройки через разделитель
        env_nested_delimiter="__",
    )

    def __init__(self, **data: Any):
        """Инициализация с поддержкой TOML файла.

        Сначала ищем semantic.toml, загружаем из него значения,
        затем env variables и переданные аргументы переопределяют их.
        """
        # Ищем TOML файл
        toml_path = find_config_file()
        toml_data: dict = {}

        if toml_path:
            toml_data = self._load_toml(toml_path)
            logger.debug("Loaded config from TOML", path=str(toml_path))

        # TOML значения имеют низший приоритет
        # kwargs (CLI args) и env variables переопределят их
        merged = {**toml_data, **data}
        super().__init__(**merged)

    @staticmethod
    def _load_toml(path: Path) -> dict:
        """Загружает и выравнивает TOML файл.

        TOML может иметь вложенные секции:
        [database]
        path = "semantic.db"

        Преобразуем в плоскую структуру:
        db_path = "semantic.db"
        """
        try:
            import tomllib
        except ImportError:
            # Python < 3.11
            try:
                import tomli as tomllib  # type: ignore
            except ImportError:
                logger.warning("TOML support requires Python 3.11+ or tomli package")
                return {}

        try:
            with open(path, "rb") as f:
                raw = tomllib.load(f)
        except Exception as e:
            logger.warning("Failed to load TOML", path=str(path), error=str(e))
            return {}

        # Маппинг секций TOML -> полей конфига
        mapping = {
            ("database", "path"): "db_path",
            ("gemini", "api_key"): "gemini_api_key",
            ("gemini", "batch_key"): "gemini_batch_key",
            ("gemini", "model"): "embedding_model",
            ("gemini", "embedding_dimension"): "embedding_dimension",
            ("processing", "splitter"): "splitter",
            ("processing", "context_strategy"): "context_strategy",
            ("media", "enabled"): "media_enabled",
            ("media", "rpm_limit"): "media_rpm_limit",
            ("search", "limit"): "search_limit",
            ("search", "type"): "search_type",
            ("logging", "level"): "log_level",
            ("logging", "file"): "log_file",
        }

        flat: dict = {}

        for (section, key), field_name in mapping.items():
            if section in raw and key in raw[section]:
                flat[field_name] = raw[section][key]

        # Также поддерживаем плоские ключи (для простоты)
        for key in [
            "db_path",
            "gemini_api_key",
            "gemini_batch_key",
            "embedding_model",
            "embedding_dimension",
            "splitter",
            "context_strategy",
            "media_enabled",
            "media_rpm_limit",
            "search_limit",
            "search_type",
            "log_level",
            "log_file",
        ]:
            if key in raw:
                flat[key] = raw[key]

        return flat

    # === Utility Methods ===

    def require_api_key(self) -> str:
        """Получить API ключ или выбросить исключение.

        Returns:
            Gemini API ключ.

        Raises:
            ValueError: Если ключ не настроен.
        """
        if not self.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY not configured. "
                "Set it via environment variable or in semantic.toml"
            )
        return self.gemini_api_key

    def require_batch_key(self) -> str:
        """Получить Batch API ключ или выбросить исключение.

        Returns:
            Gemini Batch API ключ.

        Raises:
            ValueError: Если ключ не настроен.
        """
        if not self.gemini_batch_key:
            raise ValueError(
                "GEMINI_BATCH_KEY not configured. "
                "Set it via environment variable for async batch processing."
            )
        return self.gemini_batch_key

    def to_toml_dict(self) -> dict:
        """Преобразует конфигурацию в структуру для TOML.

        Returns:
            Вложенный словарь для записи в TOML.

        Note:
            API ключи НЕ включаются (секреты хранятся в .env).
        """
        return {
            "database": {
                "path": str(self.db_path),
            },
            "gemini": {
                # api_key НЕ включаем!
                "model": self.embedding_model,
                "embedding_dimension": self.embedding_dimension,
            },
            "processing": {
                "splitter": self.splitter,
                "context_strategy": self.context_strategy,
            },
            "media": {
                "enabled": self.media_enabled,
                "rpm_limit": self.media_rpm_limit,
            },
            "search": {
                "limit": self.search_limit,
                "type": self.search_type,
            },
            "logging": {
                "level": self.log_level,
                **({"file": str(self.log_file)} if self.log_file else {}),
            },
        }


# === Global Config Accessor ===

_config: Optional[SemanticConfig] = None


def get_config(**overrides: Any) -> SemanticConfig:
    """Получить конфигурацию с возможными override'ами.

    При первом вызове создаёт конфигурацию.
    Если переданы overrides, всегда создаёт новый экземпляр.

    Args:
        **overrides: CLI аргументы для переопределения.

    Returns:
        SemanticConfig с учётом всех источников.

    Example:
        >>> config = get_config()  # Загрузка из env + TOML
        >>> config = get_config(log_level="DEBUG")  # С override'ом
    """
    global _config

    if overrides or _config is None:
        _config = SemanticConfig(**overrides)

    return _config


def reset_config() -> None:
    """Сбросить глобальный конфиг (для тестов)."""
    global _config
    _config = None


__all__ = [
    "SemanticConfig",
    "get_config",
    "reset_config",
    "find_config_file",
    "LogLevel",
    "SplitterType",
    "ContextStrategyType",
    "SearchType",
]
