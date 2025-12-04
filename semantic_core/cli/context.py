"""CLI Context — контейнер зависимостей для команд.

Предоставляет ленивую инициализацию компонентов,
чтобы --help работал мгновенно.

Classes:
    CLIContext: Контейнер с ленивой загрузкой SemanticCore и BatchManager.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from rich.console import Console

from semantic_core.config import SemanticConfig, get_config
from semantic_core.cli.console import console as default_console

if TYPE_CHECKING:
    from semantic_core.pipeline import SemanticCore
    from semantic_core.batch_manager import BatchManager


@dataclass
class CLIContext:
    """Контейнер зависимостей для CLI команд.

    Использует SemanticConfig для загрузки настроек.
    Все компоненты создаются лениво для быстрого --help.

    Attributes:
        db_path: Override пути к БД из CLI.
        log_level: Override уровня логирования из CLI.
        json_output: Режим JSON вывода (для скриптов).
        verbose: Подробный вывод.
        console: Rich Console для вывода.

    Example:
        >>> ctx = CLIContext(log_level="DEBUG")
        >>> config = ctx.get_config()
        >>> core = ctx.get_core()  # Ленивая инициализация
    """

    # CLI overrides (приоритет над config)
    db_path: Optional[Path] = None
    log_level: Optional[str] = None
    json_output: bool = False
    verbose: bool = False
    console: Console = field(default_factory=lambda: default_console)

    # Ленивая инициализация
    _config: Optional[SemanticConfig] = field(default=None, init=False, repr=False)
    _core: Optional["SemanticCore"] = field(default=None, init=False, repr=False)
    _batch_manager: Optional["BatchManager"] = field(
        default=None, init=False, repr=False
    )
    _logging_configured: bool = field(default=False, init=False, repr=False)

    def get_config(self) -> SemanticConfig:
        """Загрузить конфигурацию (с учётом CLI overrides).

        Returns:
            SemanticConfig с примененными override'ами.
        """
        if self._config is None:
            # CLI аргументы имеют приоритет
            overrides = {}
            if self.db_path:
                overrides["db_path"] = self.db_path
            if self.log_level:
                overrides["log_level"] = self.log_level

            self._config = get_config(**overrides)
        return self._config

    def get_core(self) -> "SemanticCore":
        """Получить или создать экземпляр SemanticCore.

        Returns:
            Настроенный SemanticCore.

        Raises:
            ValueError: Если GEMINI_API_KEY не настроен.
        """
        if self._core is None:
            config = self.get_config()
            self._ensure_logging(config)
            self._core = self._build_core(config)
        return self._core

    def get_batch_manager(self) -> "BatchManager":
        """Получить BatchManager (для queue команд).

        Returns:
            Настроенный BatchManager.

        Raises:
            ValueError: Если GEMINI_BATCH_KEY не настроен.
        """
        if self._batch_manager is None:
            config = self.get_config()
            self._batch_manager = self._build_batch_manager(config)
        return self._batch_manager

    def _ensure_logging(self, config: SemanticConfig) -> None:
        """Настройка логирования из конфига (один раз)."""
        if self._logging_configured:
            return

        from semantic_core.utils.logger import setup_logging, LoggingConfig

        # Verbose mode повышает уровень до INFO
        level = config.log_level
        if self.verbose and level in ("WARNING", "ERROR", "CRITICAL"):
            level = "INFO"

        log_config = LoggingConfig(
            level=level,
            log_file=config.log_file,
        )
        setup_logging(log_config)
        self._logging_configured = True

    def _build_core(self, config: SemanticConfig) -> "SemanticCore":
        """Сборка SemanticCore из конфига.

        Args:
            config: Загруженная конфигурация.

        Returns:
            Настроенный SemanticCore.
        """
        from semantic_core.pipeline import SemanticCore
        from semantic_core.infrastructure.gemini import GeminiEmbedder
        from semantic_core.infrastructure.storage.peewee import (
            PeeweeVectorStore,
            init_peewee_database,
        )
        from semantic_core.processing.splitters import SmartSplitter
        from semantic_core.processing.parsers import MarkdownNodeParser
        from semantic_core.processing.context import HierarchicalContextStrategy

        # Database
        db = init_peewee_database(config.db_path, config.embedding_dimension)

        # Embedder (требует API key)
        api_key = config.require_api_key()
        embedder = GeminiEmbedder(
            api_key=api_key,
            model_name=config.embedding_model,
            dimension=config.embedding_dimension,
        )

        # Store
        store = PeeweeVectorStore(database=db)

        # Parser and Splitter
        parser = MarkdownNodeParser()
        splitter = SmartSplitter(parser=parser)

        # Context Strategy
        context_strategy = HierarchicalContextStrategy()

        return SemanticCore(
            embedder=embedder,
            store=store,
            splitter=splitter,
            context_strategy=context_strategy,
        )

    def _build_batch_manager(self, config: SemanticConfig) -> "BatchManager":
        """Сборка BatchManager из конфига.

        Args:
            config: Загруженная конфигурация.

        Returns:
            Настроенный BatchManager.
        """
        from semantic_core.batch_manager import BatchManager
        from semantic_core.domain import GoogleKeyring

        keyring = GoogleKeyring(
            default=config.require_api_key(),
            batch=config.require_batch_key(),
        )

        # Используем store из core если уже создан
        if self._core:
            store = self._core.store
        else:
            # Создаём отдельное соединение
            from semantic_core.infrastructure.storage.peewee import (
                PeeweeVectorStore,
                init_peewee_database,
            )

            db = init_peewee_database(config.db_path, config.embedding_dimension)
            store = PeeweeVectorStore(database=db)

        return BatchManager(
            keyring=keyring,
            vector_store=store,
            model_name=config.embedding_model,
            dimension=config.embedding_dimension,
        )


__all__ = ["CLIContext"]
