"""Тесты infrastructure/gemini/resilience.py - retry декоратор."""

import pytest
from unittest.mock import Mock, patch

from semantic_core.infrastructure.gemini.resilience import (
    retry_with_backoff,
    MediaProcessingError,
    _is_retryable,
)


class TestIsRetryable:
    """Тесты для функции _is_retryable."""

    def test_429_is_retryable(self):
        """429 (rate limit) - retry."""
        error = Exception("429 Resource Exhausted")
        assert _is_retryable(error) is True

    def test_503_is_retryable(self):
        """503 (service unavailable) - retry."""
        error = Exception("503 Service Unavailable")
        assert _is_retryable(error) is True

    def test_500_is_retryable(self):
        """500 (internal error) - retry."""
        error = Exception("500 Internal Server Error")
        assert _is_retryable(error) is True

    def test_timeout_is_retryable(self):
        """Timeout - retry."""
        error = Exception("Connection timeout")
        assert _is_retryable(error) is True

    def test_connection_error_is_retryable(self):
        """Connection error - retry."""
        error = Exception("Connection reset by peer")
        assert _is_retryable(error) is True

    def test_value_error_not_retryable(self):
        """ValueError - не retry."""
        error = ValueError("Invalid input")
        assert _is_retryable(error) is False

    def test_key_error_not_retryable(self):
        """KeyError - не retry."""
        error = KeyError("missing_key")
        assert _is_retryable(error) is False


class TestRetryWithBackoff:
    """Тесты для декоратора retry_with_backoff."""

    def test_success_first_try(self):
        """Успех с первой попытки - без retry."""
        func = Mock(return_value="success")
        decorated = retry_with_backoff(max_retries=3)(func)

        result = decorated()

        assert result == "success"
        assert func.call_count == 1

    def test_success_after_retries(self):
        """Успех после нескольких retry."""
        func = Mock(
            side_effect=[
                Exception("429 Resource Exhausted"),
                Exception("503 Unavailable"),
                "success",
            ]
        )

        with patch("time.sleep"):  # Не ждём в тестах
            decorated = retry_with_backoff(max_retries=5)(func)
            result = decorated()

        assert result == "success"
        assert func.call_count == 3

    def test_all_retries_exhausted(self):
        """Все попытки исчерпаны - MediaProcessingError."""
        func = Mock(side_effect=Exception("429 Rate limit"))

        with patch("time.sleep"):
            decorated = retry_with_backoff(max_retries=3)(func)

            with pytest.raises(MediaProcessingError) as exc_info:
                decorated()

        assert "Failed after 3 retries" in str(exc_info.value)
        assert func.call_count == 3

    def test_non_retryable_error_not_retried(self):
        """Не-retryable ошибка выбрасывается сразу."""
        func = Mock(side_effect=ValueError("bad input"))
        decorated = retry_with_backoff(max_retries=5)(func)

        with pytest.raises(ValueError):
            decorated()

        assert func.call_count == 1

    def test_exponential_backoff_timing(self):
        """Проверка экспоненциального роста задержки."""
        func = Mock(
            side_effect=[
                Exception("429"),
                Exception("429"),
                "ok",
            ]
        )

        sleep_calls = []
        with patch("time.sleep", side_effect=lambda x: sleep_calls.append(x)):
            decorated = retry_with_backoff(max_retries=5, base_delay=1.0)(func)
            decorated()

        # Первый retry: ~1 сек, второй: ~2 сек (+ jitter)
        assert len(sleep_calls) == 2
        # Проверяем что delay растёт (с учётом jitter 0-1)
        assert sleep_calls[0] >= 1.0
        assert sleep_calls[1] >= 2.0

    def test_max_delay_cap(self):
        """Задержка не превышает max_delay."""
        func = Mock(side_effect=Exception("503"))

        sleep_calls = []
        with patch("time.sleep", side_effect=lambda x: sleep_calls.append(x)):
            decorated = retry_with_backoff(
                max_retries=10, base_delay=10.0, max_delay=15.0
            )(func)

            with pytest.raises(MediaProcessingError):
                decorated()

        # Все задержки должны быть <= max_delay + jitter (1)
        for delay in sleep_calls:
            assert delay <= 16.0  # max_delay + max_jitter

    def test_preserves_function_metadata(self):
        """Декоратор сохраняет __name__ и __doc__."""

        @retry_with_backoff(max_retries=3)
        def my_function():
            """My docstring."""
            return 42

        assert my_function.__name__ == "my_function"
        assert "My docstring" in my_function.__doc__

    def test_passes_args_and_kwargs(self):
        """Аргументы корректно передаются в функцию."""
        func = Mock(return_value="ok")
        decorated = retry_with_backoff(max_retries=3)(func)

        result = decorated("arg1", "arg2", kwarg1="value1")

        assert result == "ok"
        func.assert_called_once_with("arg1", "arg2", kwarg1="value1")


class TestMediaProcessingError:
    """Тесты для исключения MediaProcessingError."""

    def test_is_exception(self):
        """MediaProcessingError - это Exception."""
        error = MediaProcessingError("Test error")
        assert isinstance(error, Exception)

    def test_message(self):
        """Сообщение сохраняется."""
        error = MediaProcessingError("Failed to process image")
        assert str(error) == "Failed to process image"

    def test_chained_exception(self):
        """Можно chain с оригинальным исключением через raise."""
        original = ValueError("Original error")

        try:
            raise MediaProcessingError("Wrapped") from original
        except MediaProcessingError as error:
            assert error.__cause__ is original
            assert str(error) == "Wrapped"
