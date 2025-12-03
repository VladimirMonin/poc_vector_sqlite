"""Тесты infrastructure/gemini/rate_limiter.py - Rate Limiting."""

import pytest
import time
from unittest.mock import patch

from semantic_core.infrastructure.gemini.rate_limiter import RateLimiter


class TestRateLimiterInit:
    """Тесты инициализации RateLimiter."""

    def test_default_rpm(self):
        """Значение по умолчанию - 15 RPM."""
        limiter = RateLimiter()
        assert limiter.rpm_limit == 15

    def test_custom_rpm(self):
        """Кастомный RPM."""
        limiter = RateLimiter(rpm_limit=60)
        assert limiter.rpm_limit == 60


class TestMinDelay:
    """Тесты свойства min_delay."""

    def test_15_rpm_gives_4_seconds(self):
        """15 RPM = 4 секунды между запросами."""
        limiter = RateLimiter(rpm_limit=15)
        assert limiter.min_delay == 4.0

    def test_60_rpm_gives_1_second(self):
        """60 RPM = 1 секунда между запросами."""
        limiter = RateLimiter(rpm_limit=60)
        assert limiter.min_delay == 1.0

    def test_30_rpm_gives_2_seconds(self):
        """30 RPM = 2 секунды между запросами."""
        limiter = RateLimiter(rpm_limit=30)
        assert limiter.min_delay == 2.0


class TestWait:
    """Тесты метода wait()."""

    def test_first_request_no_wait(self):
        """Первый запрос не ждёт."""
        limiter = RateLimiter(rpm_limit=60)

        with patch("time.sleep") as mock_sleep:
            wait_time = limiter.wait()

        # Первый запрос - не вызываем sleep
        mock_sleep.assert_not_called()
        assert wait_time == 0.0

    def test_second_request_immediate_waits(self):
        """Второй запрос сразу после первого - ждёт."""
        limiter = RateLimiter(rpm_limit=60)  # 1 req/sec

        limiter.wait()  # Первый запрос

        with patch("time.sleep") as mock_sleep:
            limiter.wait()  # Второй запрос

        # Должен был вызвать sleep (примерно на 1 секунду)
        mock_sleep.assert_called_once()
        sleep_time = mock_sleep.call_args[0][0]
        assert 0.9 <= sleep_time <= 1.1

    def test_request_after_delay_no_wait(self):
        """Запрос после достаточной паузы не ждёт."""
        limiter = RateLimiter(rpm_limit=60)  # 1 req/sec

        limiter.wait()  # Первый запрос

        # Симулируем прошедшее время
        limiter._last_request = time.time() - 2.0  # 2 секунды назад

        with patch("time.sleep") as mock_sleep:
            limiter.wait()  # Следующий запрос

        mock_sleep.assert_not_called()

    def test_reset_clears_timer(self):
        """reset() сбрасывает таймер."""
        limiter = RateLimiter(rpm_limit=60)

        limiter.wait()  # Первый запрос
        limiter.reset()

        with patch("time.sleep") as mock_sleep:
            limiter.wait()  # После reset - как первый

        mock_sleep.assert_not_called()


class TestThreadSafety:
    """Тесты потокобезопасности."""

    def test_lock_exists(self):
        """Лок для thread-safety."""
        limiter = RateLimiter()
        assert hasattr(limiter, "_lock")

    def test_concurrent_access(self):
        """Конкурентный доступ не ломает состояние."""
        import threading

        limiter = RateLimiter(rpm_limit=1000)  # Быстрый для тестов
        results = []
        errors = []

        def worker():
            try:
                for _ in range(10):
                    limiter.wait()
                    results.append(1)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 30  # 3 threads * 10 requests
