"""Rate Limiter для API-вызовов.

Классы:
    RateLimiter
        Token Bucket Rate Limiter для контроля RPM.
"""

import threading
import time

from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Token Bucket Rate Limiter.

    Гарантирует, что между запросами проходит минимальный интервал,
    рассчитанный из rpm_limit.

    Потокобезопасный.

    Attributes:
        rpm_limit: Максимальное количество запросов в минуту.

    Пример использования:
        >>> limiter = RateLimiter(rpm_limit=15)
        >>> for image in images:
        ...     limiter.wait()  # Блокирует если нужно
        ...     process_image(image)
    """

    def __init__(self, rpm_limit: int = 15):
        """Инициализация Rate Limiter.

        Args:
            rpm_limit: Requests Per Minute (по умолчанию 15).
        """
        self.rpm_limit = rpm_limit
        self._lock = threading.Lock()
        self._last_request: float = 0.0
        logger.debug(
            "Rate limiter initialized",
            rpm_limit=rpm_limit,
            min_delay_ms=round(self.min_delay * 1000, 1),
        )

    @property
    def min_delay(self) -> float:
        """Минимальная задержка между запросами в секундах."""
        return 60.0 / self.rpm_limit

    def wait(self) -> float:
        """Ждёт если нужно для соблюдения rate limit.

        Returns:
            Время ожидания в секундах (0 если не ждали).
        """
        with self._lock:
            now = time.time()
            elapsed = now - self._last_request

            wait_time = 0.0
            if elapsed < self.min_delay and self._last_request > 0:
                wait_time = self.min_delay - elapsed
                logger.debug(
                    "Rate limit throttle",
                    wait_ms=round(wait_time * 1000, 1),
                    min_delay_ms=round(self.min_delay * 1000, 1),
                )
                time.sleep(wait_time)

            self._last_request = time.time()
            logger.trace(
                "Request allowed",
                wait_ms=round(wait_time * 1000, 1),
            )
            return wait_time

    def reset(self) -> None:
        """Сбрасывает таймер (для тестов)."""
        with self._lock:
            self._last_request = 0.0
            logger.debug("Rate limiter reset")
