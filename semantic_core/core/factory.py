"""Component Factory для создания SemanticCore компонентов по конфигурации.

Этот модуль предоставляет фабрику для инстанцирования всех компонентов
SemanticCore на основе конфигурации. Поддерживает множество провайдеров
(Gemini, OpenAI, Local, Ollama) и graceful degradation при отсутствии зависимостей.

Classes:
    ComponentFactory
        Фабрика для создания embedder, LLM, transcriber, vision analyzer.

Functions:
    create_core
        Convenience функция для быстрого создания SemanticCore.

Example:
    >>> from semantic_core.core.factory import create_core
    >>>
    >>> # Автоматическая сборка из конфига
    >>> core = create_core()
    >>>
    >>> # С override провайдеров
    >>> core = create_core(
    ...     embedding_provider="local",
    ...     llm_provider="ollama"
    ... )
"""

from pathlib import Path
from typing import Optional

from semantic_core.config import SemanticConfig, get_config
from semantic_core.interfaces.embedder import BaseEmbedder
from semantic_core.interfaces.llm import BaseLLMProvider
from semantic_core.interfaces.transcriber import ITranscriber
from semantic_core.interfaces.vision import IVisionAnalyzer
from semantic_core.utils.logger import get_logger
from semantic_core.utils.dependencies import require_provider

logger = get_logger(__name__)


class ComponentFactory:
    """Фабрика для создания компонентов SemanticCore по конфигурации.

    Создаёт embedder, LLM provider, transcriber и vision analyzer
    на основе настроек в SemanticConfig. Поддерживает graceful degradation
    при отсутствии опциональных зависимостей.

    Methods:
        create_embedder: Создаёт embedder (Gemini/Local/OpenAI).
        create_llm: Создаёт LLM provider (Gemini/OpenAI/Ollama).
        create_transcriber: Создаёт transcriber (Gemini/Whisper).
        create_vision_analyzer: Создаёт vision analyzer (Gemini).
        create_semantic_core: Создаёт полностью собранный SemanticCore.
    """

    @staticmethod
    def create_embedder(config: SemanticConfig) -> BaseEmbedder:
        """Создаёт embedder по конфигурации.

        Args:
            config: Конфигурация с настройками провайдера.

        Returns:
            BaseEmbedder: Реализация embedder (GeminiEmbedder, LocalEmbedder, и т.д.).

        Raises:
            ValueError: Если провайдер неизвестен.
            ImportError: Если зависимости провайдера не установлены.

        Example:
            >>> config = get_config()
            >>> embedder = ComponentFactory.create_embedder(config)
        """
        provider = config.defaults.embedding_provider

        logger.info(
            f"🏭 Создание embedder", emoji="🏭", provider=provider
        )

        if provider == "gemini":
            require_provider("google", "Gemini embeddings")
            from semantic_core.infrastructure.gemini.embedder import GeminiEmbedder

            return GeminiEmbedder(
                api_key=config.providers_gemini.api_key,
                model_name=config.providers_gemini.embedding_model,
                dimension=config.providers_gemini.dimension,
            )

        elif provider == "local":
            require_provider("local_embeddings", "Local embeddings")
            from semantic_core.infrastructure.local.embeddings import LocalEmbedder

            return LocalEmbedder(
                model=config.providers_local.embedding_model,
                device=config.providers_local.device,
            )

        elif provider == "openai":
            logger.error(
                "❌ OpenAI embedder пока не реализован",
                emoji="❌",
            )
            raise NotImplementedError(
                "OpenAI embedder not yet implemented. Use 'gemini' or 'local'."
            )

        raise ValueError(
            f"Unknown embedding provider: {provider}. "
            f"Supported: gemini, local, openai"
        )

    @staticmethod
    def create_llm(config: SemanticConfig) -> BaseLLMProvider:
        """Создаёт LLM provider по конфигурации.

        Args:
            config: Конфигурация с настройками провайдера.

        Returns:
            BaseLLMProvider: Реализация LLM (GeminiLLM, OpenAILLM, и т.д.).

        Raises:
            ValueError: Если провайдер неизвестен.
            ImportError: Если зависимости провайдера не установлены.

        Example:
            >>> config = get_config()
            >>> llm = ComponentFactory.create_llm(config)
        """
        provider = config.defaults.llm_provider

        logger.info(
            f"🏭 Создание LLM provider", emoji="🏭", provider=provider
        )

        if provider == "gemini":
            require_provider("google", "Gemini LLM")
            from semantic_core.infrastructure.llm.gemini import GeminiLLMProvider

            return GeminiLLMProvider(
                api_key=config.providers_gemini.api_key,
                model=config.providers_gemini.llm_model,
            )

        elif provider == "openai":
            require_provider("openai", "OpenAI LLM")
            from semantic_core.infrastructure.openai.llm import (
                OpenAILLMProvider,
                ProviderPreset,
            )

            return OpenAILLMProvider(
                api_key=config.providers_openai.api_key,
                provider=ProviderPreset.OPENAI,
                model=config.providers_openai.llm_model,
                base_url=config.providers_openai.base_url,
            )

        elif provider == "ollama":
            require_provider("openai", "Ollama LLM (via OpenAI SDK)")
            from semantic_core.infrastructure.openai.llm import (
                OpenAILLMProvider,
                ProviderPreset,
            )

            return OpenAILLMProvider(
                api_key="not-needed",  # Ollama не требует API key
                provider=ProviderPreset.OLLAMA,
                model=config.providers_ollama.llm_model,
                base_url=config.providers_ollama.base_url,
            )

        raise ValueError(
            f"Unknown LLM provider: {provider}. "
            f"Supported: gemini, openai, ollama"
        )

    @staticmethod
    def create_transcriber(
        config: SemanticConfig,
    ) -> Optional[ITranscriber]:
        """Создаёт transcriber по конфигурации.

        Args:
            config: Конфигурация с настройками провайдера.

        Returns:
            Optional[ITranscriber]: Transcriber или None если отключено.

        Raises:
            ValueError: Если провайдер неизвестен.
            ImportError: Если зависимости провайдера не установлены.

        Example:
            >>> config = get_config()
            >>> transcriber = ComponentFactory.create_transcriber(config)
        """
        if not config.media_enabled:
            logger.info("📵 Транскрипция отключена (media_enabled=False)", emoji="📵")
            return None

        provider = config.defaults.transcription_provider

        logger.info(
            f"🏭 Создание transcriber", emoji="🏭", provider=provider
        )

        if provider == "gemini":
            # Gemini Audio Analyzer уже реализует нужные методы
            # Но пока нет ITranscriber адаптера, используем напрямую
            logger.warning(
                "⚠️ Gemini transcriber adapter not yet implemented",
                emoji="⚠️",
            )
            return None

        elif provider == "whisper":
            require_provider("local_whisper", "Whisper transcription")
            from semantic_core.infrastructure.local.whisper import (
                WhisperTranscriber,
            )

            return WhisperTranscriber(
                model_size=config.providers_local.whisper_model,
                device=config.providers_local.device
                if config.providers_local.device != "auto"
                else None,
            )

        raise ValueError(
            f"Unknown transcription provider: {provider}. "
            f"Supported: gemini, whisper"
        )

    @staticmethod
    def create_vision_analyzer(
        config: SemanticConfig,
    ) -> Optional[IVisionAnalyzer]:
        """Создаёт vision analyzer по конфигурации.

        Args:
            config: Конфигурация с настройками провайдера.

        Returns:
            Optional[IVisionAnalyzer]: Vision analyzer или None если отключено.

        Raises:
            ValueError: Если провайдер неизвестен.

        Example:
            >>> config = get_config()
            >>> vision = ComponentFactory.create_vision_analyzer(config)
        """
        if not config.media_enabled:
            logger.info("📵 Vision отключён (media_enabled=False)", emoji="📵")
            return None

        provider = config.defaults.vision_provider

        logger.info(
            f"🏭 Создание vision analyzer", emoji="🏭", provider=provider
        )

        if provider == "gemini":
            # Gemini Image Analyzer уже реализует нужные методы
            # Но пока нет IVisionAnalyzer адаптера
            logger.warning(
                "⚠️ Gemini vision adapter not yet implemented",
                emoji="⚠️",
            )
            return None

        raise ValueError(
            f"Unknown vision provider: {provider}. "
            f"Supported: gemini"
        )

    @staticmethod
    def create_semantic_core(config: SemanticConfig):
        """Создаёт полностью собранный SemanticCore.

        Args:
            config: Конфигурация для сборки компонентов.

        Returns:
            SemanticCore: Собранный экземпляр с всеми компонентами.

        Example:
            >>> from semantic_core.config import get_config
            >>> from semantic_core.core.factory import ComponentFactory
            >>>
            >>> config = get_config()
            >>> core = ComponentFactory.create_semantic_core(config)
        """
        from semantic_core.pipeline import SemanticCore

        logger.info("🏭 Создание SemanticCore", emoji="🏭")

        # Создаём компоненты
        embedder = ComponentFactory.create_embedder(config)
        llm = ComponentFactory.create_llm(config)
        transcriber = ComponentFactory.create_transcriber(config)
        vision = ComponentFactory.create_vision_analyzer(config)

        # Создаём store (пока только Peewee)
        from semantic_core.infrastructure.storage.peewee import (
            PeeweeVectorStore,
            init_peewee_database,
        )

        database = init_peewee_database(
            db_path=config.db_path,
            dimension=embedder.dimension,
        )

        store = PeeweeVectorStore(
            database=database,
            dimension=embedder.dimension,
        )

        # Собираем SemanticCore
        core = SemanticCore(
            embedder=embedder,
            store=store,
            vision_analyzer=vision,
            transcriber=transcriber,
            llm=llm,
        )

        logger.info(
            "✅ SemanticCore создан",
            emoji="✅",
            embedding_provider=config.defaults.embedding_provider,
            llm_provider=config.defaults.llm_provider,
            transcription_provider=config.defaults.transcription_provider,
        )

        return core


# === Convenience API ===


def create_core(
    db_path: Optional[Path] = None,
    embedding_provider: Optional[str] = None,
    llm_provider: Optional[str] = None,
    transcription_provider: Optional[str] = None,
    **kwargs,
):
    """Convenience функция для быстрого создания SemanticCore.

    Автоматически загружает конфигурацию из semantic.toml и env,
    применяет переданные override'ы и создаёт SemanticCore.

    Args:
        db_path: Путь к БД (опционально).
        embedding_provider: Провайдер для эмбеддингов (gemini/local/openai).
        llm_provider: Провайдер для LLM (gemini/openai/ollama).
        transcription_provider: Провайдер для транскрипции (gemini/whisper).
        **kwargs: Дополнительные параметры для SemanticConfig.

    Returns:
        SemanticCore: Собранный экземпляр.

    Example:
        >>> from semantic_core import create_core
        >>>
        >>> # Простейший вариант
        >>> core = create_core()
        >>>
        >>> # С переопределением провайдеров
        >>> core = create_core(
        ...     embedding_provider="local",
        ...     llm_provider="ollama",
        ...     db_path="custom.db"
        ... )
    """
    # Формируем override для конфига
    overrides = {}
    if db_path:
        overrides["db_path"] = db_path

    # Провайдеры
    defaults_overrides = {}
    if embedding_provider:
        defaults_overrides["embedding_provider"] = embedding_provider
    if llm_provider:
        defaults_overrides["llm_provider"] = llm_provider
    if transcription_provider:
        defaults_overrides["transcription_provider"] = transcription_provider

    if defaults_overrides:
        overrides["defaults"] = defaults_overrides

    # Объединяем с другими kwargs
    overrides.update(kwargs)

    # Загружаем конфиг
    config = get_config(**overrides)

    # Создаём SemanticCore
    return ComponentFactory.create_semantic_core(config)
