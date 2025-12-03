"""Тесты для модуля логирования semantic_core.utils.logger.

Покрытие:
- levels.py: регистрация TRACE, патчинг Logger
- config.py: LoggingConfig валидация
- filters.py: SensitiveDataFilter маскирование ключей
- formatters.py: EMOJI_MAP, get_module_emoji, CONTEXT_ID_KEYS
- logger.py: SemanticLogger, bind(), trace_ai(), error_with_context()
"""

import logging
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from semantic_core.utils.logger import (
    TRACE,
    LoggingConfig,
    SemanticLogger,
    get_logger,
    setup_logging,
)
from semantic_core.utils.logger.filters import (
    REDACTED,
    SENSITIVE_PATTERNS,
    SensitiveDataFilter,
)
from semantic_core.utils.logger.formatters import (
    CONTEXT_ID_KEYS,
    EMOJI_MAP,
    FALLBACK_EMOJI,
    FileFormatter,
    get_module_emoji,
)
from semantic_core.utils.logger.levels import install_trace_level


class TestLevels:
    """Тесты для levels.py."""

    def test_trace_level_value(self):
        """TRACE должен быть равен 5."""
        assert TRACE == 5

    def test_trace_level_registered(self):
        """TRACE должен быть зарегистрирован в logging."""
        assert logging.getLevelName(TRACE) == "TRACE"
        assert logging.getLevelName("TRACE") == TRACE

    def test_logger_has_trace_method(self):
        """Logger должен иметь метод trace()."""
        logger = logging.getLogger("test.trace")
        assert hasattr(logger, "trace")
        assert callable(logger.trace)

    def test_install_trace_level_idempotent(self):
        """Повторные вызовы install_trace_level() безопасны."""
        # Не должен бросать исключений
        install_trace_level()
        install_trace_level()
        install_trace_level()
        assert logging.getLevelName(TRACE) == "TRACE"


class TestLoggingConfig:
    """Тесты для config.py."""

    def test_default_values(self):
        """Дефолтные значения конфигурации."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.file_level == "TRACE"
        assert config.log_file is None
        assert config.json_format is False
        assert config.show_path is True
        assert config.redact_secrets is True
        assert config.console_width == 120

    def test_custom_values(self):
        """Кастомные значения конфигурации."""
        config = LoggingConfig(
            level="DEBUG",
            file_level="WARNING",
            log_file=Path("/tmp/test.log"),
            json_format=True,
            show_path=False,
            redact_secrets=False,
            console_width=200,
        )
        assert config.level == "DEBUG"
        assert config.file_level == "WARNING"
        assert config.log_file == Path("/tmp/test.log")
        assert config.json_format is True
        assert config.show_path is False
        assert config.redact_secrets is False
        assert config.console_width == 200

    def test_frozen_config(self):
        """Конфиг должен быть immutable."""
        config = LoggingConfig()
        with pytest.raises(Exception):  # ValidationError или AttributeError
            config.level = "DEBUG"

    def test_invalid_level_rejected(self):
        """Невалидные уровни должны отклоняться."""
        with pytest.raises(Exception):
            LoggingConfig(level="INVALID")


class TestSensitiveDataFilter:
    """Тесты для filters.py."""

    def test_google_api_key_redacted(self):
        """Google API ключи должны маскироваться."""
        filter_ = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Key: AIzaSyD-abcdefghijklmnopqrstuvwxyz12345",
            args=(),
            exc_info=None,
        )
        filter_.filter(record)
        assert "AIzaSyD" not in record.msg
        assert REDACTED in record.msg

    def test_openai_api_key_redacted(self):
        """OpenAI API ключи должны маскироваться."""
        filter_ = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Key: sk-abcdefghijklmnopqrstuvwxyz123456789012345678",
            args=(),
            exc_info=None,
        )
        filter_.filter(record)
        assert "sk-" not in record.msg
        assert REDACTED in record.msg

    def test_args_redacted(self):
        """Аргументы форматирования тоже маскируются."""
        filter_ = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Key: %s",
            args=("AIzaSyD-abcdefghijklmnopqrstuvwxyz12345",),
            exc_info=None,
        )
        filter_.filter(record)
        assert REDACTED in record.args[0]

    def test_filter_always_returns_true(self):
        """Фильтр не блокирует записи, только модифицирует."""
        filter_ = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Safe message",
            args=(),
            exc_info=None,
        )
        assert filter_.filter(record) is True

    def test_safe_message_unchanged(self):
        """Безопасные сообщения не изменяются."""
        filter_ = SensitiveDataFilter()
        original_msg = "This is a safe message without secrets"
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=original_msg,
            args=(),
            exc_info=None,
        )
        filter_.filter(record)
        assert record.msg == original_msg


class TestFormatters:
    """Тесты для formatters.py."""

    def test_emoji_map_has_required_keys(self):
        """EMOJI_MAP должен содержать основные модули."""
        required = ["pipeline", "parser", "splitter", "embedder", "storage", "search"]
        for key in required:
            assert key in EMOJI_MAP, f"Missing key: {key}"

    def test_get_module_emoji_exact_match(self):
        """get_module_emoji находит точное совпадение."""
        assert get_module_emoji("semantic_core.pipeline") == "📥"
        assert get_module_emoji("semantic_core.infrastructure.storage") == "💾"

    def test_get_module_emoji_partial_match(self):
        """get_module_emoji находит частичное совпадение."""
        assert (
            get_module_emoji("semantic_core.processing.parsers.markdown_parser") == "🧶"
        )
        assert get_module_emoji("my.custom.embedder.module") == "🧠"

    def test_get_module_emoji_fallback(self):
        """get_module_emoji возвращает fallback для неизвестных модулей."""
        assert get_module_emoji("unknown.module.name") == FALLBACK_EMOJI
        assert get_module_emoji("") == FALLBACK_EMOJI

    def test_context_id_keys_defined(self):
        """CONTEXT_ID_KEYS должен содержать основные ключи."""
        assert "batch_id" in CONTEXT_ID_KEYS
        assert "doc_id" in CONTEXT_ID_KEYS
        assert "chunk_id" in CONTEXT_ID_KEYS


class TestSemanticLogger:
    """Тесты для logger.py."""

    def test_basic_logging(self):
        """Базовое логирование работает."""
        logger = SemanticLogger("test.module")
        # Не должно бросать исключений
        logger.info("Test message")
        logger.debug("Debug message")
        logger.warning("Warning message")
        logger.error("Error message")

    def test_trace_logging(self):
        """Уровень TRACE работает."""
        logger = SemanticLogger("test.module")
        logger.trace("Trace message")

    def test_bind_creates_new_logger(self):
        """bind() создаёт новый логгер с контекстом."""
        logger = SemanticLogger("test.module")
        bound = logger.bind(batch_id="batch-123")

        assert bound is not logger
        assert bound._context == {"batch_id": "batch-123"}
        assert logger._context == {}

    def test_bind_merges_context(self):
        """Вложенный bind() объединяет контекст."""
        logger = SemanticLogger("test.module")
        bound1 = logger.bind(batch_id="batch-123")
        bound2 = bound1.bind(chunk_id="chunk-42")

        assert bound2._context == {"batch_id": "batch-123", "chunk_id": "chunk-42"}

    def test_bind_preserves_name(self):
        """bind() сохраняет имя логгера."""
        logger = SemanticLogger("test.module")
        bound = logger.bind(batch_id="batch-123")

        assert bound.name == logger.name

    def test_trace_ai_method(self):
        """trace_ai() логирует AI-взаимодействие."""
        logger = SemanticLogger("test.ai")
        # Не должно бросать исключений
        logger.trace_ai(
            prompt="Test prompt",
            response="Test response",
            model="gemini-1.5",
            tokens_in=100,
            tokens_out=50,
            duration_ms=150.5,
        )

    def test_error_with_context_method(self):
        """error_with_context() логирует исключение."""
        logger = SemanticLogger("test.error")
        try:
            raise ValueError("Test error")
        except ValueError as e:
            # Не должно бросать исключений
            logger.error_with_context(e, custom_key="value")


class TestSetupLogging:
    """Тесты для __init__.py."""

    def test_setup_logging_default(self):
        """setup_logging() работает с дефолтами."""
        setup_logging()
        # Проверяем, что логгер semantic_core настроен
        root = logging.getLogger("semantic_core")
        assert len(root.handlers) >= 1

    def test_setup_logging_with_config(self):
        """setup_logging() принимает кастомный конфиг."""
        config = LoggingConfig(level="DEBUG")
        setup_logging(config)

    def test_get_logger_returns_semantic_logger(self):
        """get_logger() возвращает SemanticLogger."""
        logger = get_logger("test.module")
        assert isinstance(logger, SemanticLogger)

    def test_get_logger_lazy_init(self):
        """get_logger() делает ленивую инициализацию."""
        # Должен работать даже без явного setup_logging()
        logger = get_logger("test.lazy")
        logger.info("Test message")


class TestFileFormatter:
    """Тесты для FileFormatter."""

    def test_file_formatter_basic(self):
        """FileFormatter форматирует записи."""
        formatter = FileFormatter()
        record = logging.LogRecord(
            name="semantic_core.pipeline",
            level=logging.INFO,
            pathname="pipeline.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)

        assert "PIPELINE" in result
        assert "INFO" in result
        assert "Test message" in result

    def test_file_formatter_json_context(self):
        """FileFormatter может выводить контекст как JSON."""
        formatter = FileFormatter(json_context=True)
        record = logging.LogRecord(
            name="semantic_core.pipeline",
            level=logging.INFO,
            pathname="pipeline.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.custom_key = "custom_value"
        result = formatter.format(record)

        assert "custom_key" in result or "custom_value" in result
