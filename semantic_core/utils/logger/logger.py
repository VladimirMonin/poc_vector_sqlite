"""Семантический логгер с поддержкой контекста.

Классы:
    SemanticLogger
        Адаптер над logging.Logger с поддержкой контекста и специальных методов.
"""

from __future__ import annotations

import logging
import sys
import traceback
from typing import Any

from .levels import TRACE
from .formatters import CONTEXT_ID_KEYS, get_module_emoji, LEVEL_EMOJI


class SemanticLogger:
    """Адаптер для структурированного логирования с контекстом.

    Предоставляет:
    - Стандартные методы логирования (trace, debug, info, warning, error)
    - Метод bind() для привязки контекста (batch_id, doc_id, etc.)
    - Специализированные методы trace_ai() и error_with_context()

    Attributes:
        name: Имя логгера.
        _logger: Обёрнутый logging.Logger.
        _context: Привязанный контекст для всех сообщений.

    Example:
        >>> logger = SemanticLogger("semantic_core.pipeline")
        >>> log = logger.bind(batch_id="batch-123")
        >>> log.info("Processing started")  # -> 📥 [batch-123] Processing started
    """

    def __init__(self, name: str, context: dict[str, Any] | None = None) -> None:
        """Инициализирует логгер.

        Args:
            name: Имя логгера (обычно __name__).
            context: Начальный контекст для привязки.
        """
        self.name = name
        self._logger = logging.getLogger(name)
        self._context: dict[str, Any] = context or {}

    def bind(self, **context: Any) -> SemanticLogger:
        """Создаёт новый логгер с дополнительным контекстом.

        Args:
            **context: Ключи контекста для привязки (batch_id, doc_id, etc.).

        Returns:
            Новый SemanticLogger с объединённым контекстом.

        Example:
            >>> logger = get_logger(__name__)
            >>> batch_log = logger.bind(batch_id="batch-123")
            >>> chunk_log = batch_log.bind(chunk_id="chunk-42")
            >>> chunk_log.info("Processing")  # -> [batch-123/chunk-42] Processing
        """
        merged_context = {**self._context, **context}
        return SemanticLogger(self.name, merged_context)

    def _log(self, level: int, msg: str, **context: Any) -> None:
        """Внутренний метод логирования.

        Args:
            level: Уровень логирования.
            msg: Сообщение.
            **context: Дополнительный контекст для этого сообщения.
        """
        # Объединяем привязанный контекст с контекстом сообщения
        extra = {**self._context, **context}

        # Формируем префикс контекста для сообщения
        # Context IDs вставляются в сообщение, т.к. RichHandler не использует наш форматтер
        context_ids: list[str] = []
        for key in CONTEXT_ID_KEYS:
            value = extra.get(key)
            if value:
                context_ids.append(str(value))

        context_prefix = f"[{'/'.join(context_ids)}] " if context_ids else ""

        # Добавляем эмодзи модуля (уровень имеет приоритет для ERROR/WARNING/DEBUG)
        level_emoji = LEVEL_EMOJI.get(level, "")
        module_emoji = get_module_emoji(self.name)
        emoji = level_emoji or module_emoji

        # Итоговое сообщение: emoji [context] message
        formatted_msg = f"{emoji} {context_prefix}{msg}"

        self._logger.log(level, formatted_msg, extra=extra)

    def trace(self, msg: str, **context: Any) -> None:
        """Логирование на уровне TRACE (5).

        Используется для дампов пейлоадов, векторов, промптов.

        Args:
            msg: Сообщение.
            **context: Дополнительный контекст.
        """
        self._log(TRACE, msg, **context)

    def debug(self, msg: str, **context: Any) -> None:
        """Логирование на уровне DEBUG (10).

        Используется для технических деталей потока.

        Args:
            msg: Сообщение.
            **context: Дополнительный контекст.
        """
        self._log(logging.DEBUG, msg, **context)

    def info(self, msg: str, **context: Any) -> None:
        """Логирование на уровне INFO (20).

        Используется для бизнес-событий.

        Args:
            msg: Сообщение.
            **context: Дополнительный контекст.
        """
        self._log(logging.INFO, msg, **context)

    def warning(self, msg: str, **context: Any) -> None:
        """Логирование на уровне WARNING (30).

        Используется для предупреждений.

        Args:
            msg: Сообщение.
            **context: Дополнительный контекст.
        """
        self._log(logging.WARNING, msg, **context)

    def error(self, msg: str, **context: Any) -> None:
        """Логирование на уровне ERROR (40).

        Используется для ошибок.

        Args:
            msg: Сообщение.
            **context: Дополнительный контекст.
        """
        self._log(logging.ERROR, msg, **context)

    def critical(self, msg: str, **context: Any) -> None:
        """Логирование на уровне CRITICAL (50).

        Используется для фатальных ошибок.

        Args:
            msg: Сообщение.
            **context: Дополнительный контекст.
        """
        self._log(logging.CRITICAL, msg, **context)

    def trace_ai(
        self,
        prompt: str,
        response: str | None = None,
        *,
        model: str | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        duration_ms: float | None = None,
        **metadata: Any,
    ) -> None:
        """Логирование взаимодействия с LLM.

        Специализированный метод для трассировки AI-вызовов.

        Args:
            prompt: Отправленный промпт.
            response: Полученный ответ (может быть None при ошибке).
            model: Название модели.
            tokens_in: Количество входных токенов.
            tokens_out: Количество выходных токенов.
            duration_ms: Время выполнения в миллисекундах.
            **metadata: Дополнительные метаданные.
        """
        # Формируем контекст
        ai_context = {
            "ai_prompt": prompt[:500] + "..." if len(prompt) > 500 else prompt,
            **metadata,
        }

        if response is not None:
            ai_context["ai_response"] = (
                response[:500] + "..." if len(response) > 500 else response
            )

        if model:
            ai_context["model"] = model
        if tokens_in is not None:
            ai_context["tokens_in"] = tokens_in
        if tokens_out is not None:
            ai_context["tokens_out"] = tokens_out
        if duration_ms is not None:
            ai_context["duration_ms"] = round(duration_ms, 2)

        # Формируем сообщение
        msg_parts = ["AI call"]
        if model:
            msg_parts.append(f"model={model}")
        if tokens_in is not None or tokens_out is not None:
            tokens_str = f"{tokens_in or '?'}/{tokens_out or '?'}"
            msg_parts.append(f"tokens={tokens_str}")
        if duration_ms is not None:
            msg_parts.append(f"time={duration_ms:.0f}ms")

        self.trace(" ".join(msg_parts), **ai_context)

    def error_with_context(
        self,
        exc: Exception,
        msg: str | None = None,
        *,
        include_traceback: bool = True,
        include_locals: bool = False,
        **context: Any,
    ) -> None:
        """Логирование исключения с расширенным контекстом.

        Args:
            exc: Исключение.
            msg: Дополнительное сообщение (по умолчанию str(exc)).
            include_traceback: Включить traceback в контекст.
            include_locals: Включить локальные переменные (осторожно с секретами!).
            **context: Дополнительный контекст.
        """
        error_context = {
            "exception_type": type(exc).__name__,
            "exception_msg": str(exc),
            **context,
        }

        if include_traceback:
            error_context["traceback"] = traceback.format_exc()

        if include_locals:
            # Получаем локальные переменные из фрейма, где возникло исключение
            _, _, tb = sys.exc_info()
            if tb is not None:
                # Идём к последнему фрейму
                while tb.tb_next:
                    tb = tb.tb_next
                local_vars = tb.tb_frame.f_locals
                # Фильтруем приватные переменные и большие объекты
                safe_locals = {
                    k: repr(v)[:200]
                    for k, v in local_vars.items()
                    if not k.startswith("_") and not callable(v)
                }
                error_context["locals"] = safe_locals

        message = msg or str(exc)
        self.error(message, **error_context)

    def is_enabled_for(self, level: int) -> bool:
        """Проверяет, включён ли данный уровень логирования.

        Args:
            level: Уровень для проверки.

        Returns:
            True если уровень включён.
        """
        return self._logger.isEnabledFor(level)

    @property
    def level(self) -> int:
        """Возвращает эффективный уровень логгера."""
        return self._logger.getEffectiveLevel()
