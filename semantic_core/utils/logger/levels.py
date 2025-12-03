"""Кастомные уровни логирования.

Функции:
    install_trace_level()
        Регистрирует уровень TRACE (5) и патчит Logger.

Константы:
    TRACE: int
        Значение уровня TRACE (5), ниже DEBUG (10).
"""

import logging
from typing import Any

# Уровень TRACE — для детальных дампов (пейлоады, векторы, промпты)
TRACE: int = 5

_trace_installed: bool = False


def _trace_method(
    self: logging.Logger, message: str, *args: Any, **kwargs: Any
) -> None:
    """Логирование на уровне TRACE (5).

    Args:
        message: Сообщение для логирования.
        *args: Аргументы форматирования.
        **kwargs: Дополнительные параметры (exc_info, stack_info, extra).
    """
    if self.isEnabledFor(TRACE):
        self._log(TRACE, message, args, **kwargs)


def install_trace_level() -> None:
    """Регистрирует уровень TRACE и добавляет метод trace() к Logger.

    Безопасно вызывать многократно — повторные вызовы игнорируются.

    После вызова:
        - logging.TRACE == 5
        - logging.getLevelName(5) == "TRACE"
        - logger.trace("message") работает
    """
    global _trace_installed

    if _trace_installed:
        return

    # Регистрируем имя уровня
    logging.addLevelName(TRACE, "TRACE")

    # Добавляем константу в модуль logging для удобства
    logging.TRACE = TRACE  # type: ignore[attr-defined]

    # Патчим класс Logger
    logging.Logger.trace = _trace_method  # type: ignore[attr-defined]

    _trace_installed = True


# Автоматически устанавливаем при импорте модуля
install_trace_level()
