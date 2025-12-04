"""SemanticCore интеграция с Flask.

Инициализирует SemanticCore и сохраняет в app.extensions.
Предоставляет хелперы для доступа к ядру из request context.

Usage:
    from flask import current_app
    core = current_app.extensions['semantic_core']
    results = core.search("query")
"""

from pathlib import Path
from typing import TYPE_CHECKING

from flask import Flask, current_app

if TYPE_CHECKING:
    from semantic_core.pipeline import SemanticCore
    from semantic_core.config import SemanticConfig
    from app.services.cache_service import QueryCacheService


def get_semantic_core() -> "SemanticCore":
    """Получить SemanticCore из контекста приложения.

    Returns:
        Инициализированный SemanticCore.

    Raises:
        RuntimeError: Если вызвано вне контекста приложения.
    """
    return current_app.extensions["semantic_core"]


def get_semantic_config() -> "SemanticConfig":
    """Получить SemanticConfig из контекста приложения.

    Returns:
        Загруженный SemanticConfig.
    """
    return current_app.extensions["semantic_config"]


def get_query_cache() -> "QueryCacheService":
    """Получить QueryCacheService из контекста приложения.

    Returns:
        Инициализированный QueryCacheService (или None без API key).
    """
    return current_app.extensions["query_cache"]


def init_semantic_core(app: Flask) -> None:
    """Инициализировать SemanticCore и сохранить в app.extensions.

    Загружает конфигурацию через SemanticConfig (env + semantic.toml).
    Создаёт все компоненты ядра (embedder, store, splitter).

    Args:
        app: Flask приложение.
    """
    from semantic_core.config import get_config
    from semantic_core.pipeline import SemanticCore
    from semantic_core.infrastructure.gemini import GeminiEmbedder
    from semantic_core.infrastructure.storage.peewee import (
        PeeweeVectorStore,
        init_peewee_database,
    )
    from semantic_core.processing.splitters import SmartSplitter
    from semantic_core.processing.parsers import MarkdownNodeParser
    from semantic_core.processing.context import HierarchicalContextStrategy
    from semantic_core.utils.logger import get_logger

    logger = get_logger("flask_app.extensions")

    # Загрузка конфигурации
    config = get_config()
    logger.info(f"📦 Загрузка конфигурации: db_path={config.db_path}")

    # Database
    db = init_peewee_database(config.db_path, config.embedding_dimension)
    logger.info(f"🗄️ База данных инициализирована: {config.db_path}")

    # Embedder
    try:
        api_key = config.require_api_key()
        embedder = GeminiEmbedder(
            api_key=api_key,
            model_name=config.embedding_model,
            dimension=config.embedding_dimension,
        )
        logger.info(f"🤖 Embedder: {config.embedding_model}")
    except ValueError as e:
        logger.warning(f"⚠️ API ключ не настроен: {e}. Поиск будет ограничен.")
        embedder = None  # type: ignore

    # Store
    store = PeeweeVectorStore(database=db)

    # Splitter
    parser = MarkdownNodeParser()
    splitter = SmartSplitter(parser=parser)

    # Context Strategy
    context_strategy = HierarchicalContextStrategy()

    # SemanticCore (если есть embedder)
    if embedder:
        core = SemanticCore(
            embedder=embedder,
            store=store,
            splitter=splitter,
            context_strategy=context_strategy,
        )
        logger.info("✅ SemanticCore инициализирован")
    else:
        core = None  # type: ignore
        logger.warning("⚠️ SemanticCore не создан (нет API ключа)")

    # Query Cache Service (если есть embedder)
    query_cache = None
    if embedder:
        from app.services.cache_service import QueryCacheService

        query_cache = QueryCacheService(embedder=embedder, database=db)
        logger.info("💾 QueryCacheService инициализирован")

    # Сохраняем в extensions
    app.extensions["semantic_core"] = core
    app.extensions["semantic_config"] = config
    app.extensions["semantic_store"] = store
    app.extensions["query_cache"] = query_cache

    # Chat Service (если есть core)
    chat_service = None
    if core:
        from semantic_core.infrastructure.llm import GeminiLLMProvider
        from app.services.chat_service import ChatService

        try:
            llm = GeminiLLMProvider(
                api_key=api_key,
                model=config.llm_model,
            )
            chat_service = ChatService(
                core=core,
                llm=llm,
                database=db,
                cache=query_cache,
                context_chunks=5,
            )
            logger.info(f"💬 ChatService инициализирован, model={config.llm_model}")
        except Exception as e:
            logger.warning(f"⚠️ ChatService не создан: {e}")

    app.extensions["chat_service"] = chat_service
