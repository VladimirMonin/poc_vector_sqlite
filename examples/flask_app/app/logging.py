"""Интеграция SemanticLogger с Flask.

Настраивает логирование и middleware для HTTP запросов.

Эмодзи-маппинг:
    🌐 — HTTP запросы
    🔥 — Ошибки
    ⚡ — Быстрые операции
    📊 — Метрики
"""

import time
from typing import Callable

from flask import Flask, request, g

from semantic_core.utils.logger import setup_logging, LoggingConfig, get_logger

logger = get_logger("flask_app")


def init_logging(app: Flask) -> None:
    """Инициализировать логирование для Flask приложения.

    Настраивает SemanticLogger и регистрирует middleware.

    Args:
        app: Flask приложение.
    """
    from semantic_core.config import get_config

    config = get_config()

    # Настройка SemanticLogger
    log_config = LoggingConfig(
        level=config.log_level,
        log_file=config.log_file,
    )
    setup_logging(log_config)

    logger.info("🚀 Flask app logging initialized")

    # Регистрация middleware
    _register_request_logging(app)


def _register_request_logging(app: Flask) -> None:
    """Зарегистрировать before/after request хуки для логирования.

    Args:
        app: Flask приложение.
    """

    @app.before_request
    def log_request_start() -> None:
        """Логировать начало запроса и засечь время."""
        g.request_start_time = time.perf_counter()

    @app.after_request
    def log_request_end(response):
        """Логировать завершение запроса с временем выполнения."""
        duration_ms = (time.perf_counter() - g.request_start_time) * 1000

        # Эмодзи по статусу
        if response.status_code >= 500:
            emoji = "🔥"
        elif response.status_code >= 400:
            emoji = "⚠️"
        elif duration_ms < 100:
            emoji = "⚡"
        else:
            emoji = "🌐"

        logger.info(
            f"{emoji} [{request.method}] {request.path} → {response.status_code} ({duration_ms:.1f}ms)"
        )

        return response
