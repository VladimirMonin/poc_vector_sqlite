"""Resilience паттерны для API-вызовов.

Классы:
    MediaProcessingError
        Исключение после исчерпания retry-попыток.

Функции:
    retry_with_backoff
        Декоратор с exponential backoff + jitter.
"""

import random
import time
from functools import wraps
from typing import Callable, TypeVar

from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)

# Типы для дженерика
F = TypeVar("F", bound=Callable)


class MediaProcessingError(Exception):
    """Ошибка обработки медиа после исчерпания retry-попыток."""

    pass


# Ошибки, которые имеет смысл ретраить
RETRYABLE_PATTERNS = (
    "429",  # Rate limit
    "503",  # Service unavailable
    "500",  # Internal server error
    "timeout",
    "connection",
    "reset",
)


def _is_retryable(error: Exception) -> bool:
    """Определяет, стоит ли повторять запрос после ошибки.

    Args:
        error: Исключение.

    Returns:
        True если ошибка временная и стоит повторить.
    """
    error_str = str(error).lower()
    is_retryable = any(pattern in error_str for pattern in RETRYABLE_PATTERNS)
    logger.trace(
        "Error classification",
        error_type=type(error).__name__,
        is_retryable=is_retryable,
        error_preview=error_str[:100],
    )
    return is_retryable


def retry_with_backoff(
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
) -> Callable[[F], F]:
    """Декоратор с exponential backoff и jitter.

    Args:
        max_retries: Максимальное количество попыток.
        base_delay: Начальная задержка в секундах.
        max_delay: Максимальная задержка в секундах.

    Returns:
        Декоратор.

    Raises:
        MediaProcessingError: После исчерпания всех попыток.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            func_name = getattr(func, "__name__", repr(func))

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # Не ретраим если ошибка не временная
                    if not _is_retryable(e):
                        logger.warning(
                            "Non-retryable error, failing immediately",
                            func=func_name,
                            error_type=type(e).__name__,
                        )
                        raise

                    # Последняя попытка — бросаем обёрнутое исключение
                    if attempt == max_retries - 1:
                        logger.error(
                            "All retry attempts exhausted",
                            func=func_name,
                            attempts=max_retries,
                            error_type=type(e).__name__,
                        )
                        raise MediaProcessingError(
                            f"Failed after {max_retries} retries: {e}"
                        ) from e

                    # Exponential backoff с jitter
                    delay = min(base_delay * (2**attempt), max_delay)
                    jitter = random.uniform(0, 1)
                    total_delay = delay + jitter

                    logger.warning(
                        "Retry attempt",
                        func=func_name,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay_ms=round(total_delay * 1000, 1),
                        error_type=type(e).__name__,
                    )
                    time.sleep(total_delay)

            # Недостижимо, но для типизации
            logger.error(
                "Unexpected retry loop exit",
                func=func_name,
                attempts=max_retries,
            )
            raise MediaProcessingError(
                f"Failed after {max_retries} retries"
            ) from last_exception

        return wrapper  # type: ignore

    return decorator
