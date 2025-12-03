"""Фильтры логирования для безопасности.

Классы:
    SensitiveDataFilter
        Фильтр для маскирования API-ключей и секретов в логах.
"""

import logging
import re
from typing import Pattern

# Паттерны для обнаружения секретов
SENSITIVE_PATTERNS: list[Pattern[str]] = [
    re.compile(r"AIza[0-9A-Za-z_-]{35}"),  # Google API Key
    re.compile(r"sk-[0-9a-zA-Z]{20,}"),  # OpenAI API Key (переменная длина)
    re.compile(r"sk-proj-[0-9a-zA-Z_-]{20,}"),  # OpenAI Project Key
    re.compile(r"gsk_[0-9a-zA-Z]{50,}"),  # Groq API Key
    re.compile(r"xai-[0-9a-zA-Z]{20,}"),  # xAI/Grok API Key
    re.compile(r"key-[0-9a-zA-Z]{32,}"),  # Generic API Key
    re.compile(r"(?i)bearer\s+[a-zA-Z0-9_-]{20,}"),  # Bearer tokens
]

REDACTED: str = "***REDACTED***"


class SensitiveDataFilter(logging.Filter):
    """Фильтр для маскирования секретных данных в логах.

    Заменяет паттерны API-ключей на ***REDACTED*** в:
    - record.msg (сообщение)
    - record.args (аргументы форматирования)

    Attributes:
        patterns: Список скомпилированных regex-паттернов для поиска.
        redacted: Строка замены для найденных секретов.
    """

    def __init__(
        self,
        patterns: list[Pattern[str]] | None = None,
        redacted: str = REDACTED,
        name: str = "",
    ) -> None:
        """Инициализирует фильтр.

        Args:
            patterns: Кастомные паттерны (по умолчанию SENSITIVE_PATTERNS).
            redacted: Строка замены (по умолчанию "***REDACTED***").
            name: Имя фильтра для logging.Filter.
        """
        super().__init__(name)
        self.patterns = patterns or SENSITIVE_PATTERNS
        self.redacted = redacted

    def _redact_string(self, text: str) -> str:
        """Маскирует все секреты в строке.

        Args:
            text: Исходная строка.

        Returns:
            Строка с замаскированными секретами.
        """
        result = text
        for pattern in self.patterns:
            result = pattern.sub(self.redacted, result)
        return result

    def _redact_value(self, value: object) -> object:
        """Рекурсивно маскирует секреты в значении.

        Args:
            value: Значение любого типа.

        Returns:
            Значение с замаскированными секретами (для строк).
        """
        if isinstance(value, str):
            return self._redact_string(value)
        elif isinstance(value, dict):
            return {k: self._redact_value(v) for k, v in value.items()}
        elif isinstance(value, (list, tuple)):
            redacted_items = [self._redact_value(item) for item in value]
            return type(value)(redacted_items)
        return value

    def filter(self, record: logging.LogRecord) -> bool:
        """Фильтрует запись, маскируя секреты.

        Args:
            record: Запись лога.

        Returns:
            True всегда (запись не отфильтровывается, только модифицируется).
        """
        # Маскируем сообщение
        if isinstance(record.msg, str):
            record.msg = self._redact_string(record.msg)

        # Маскируем аргументы форматирования
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._redact_value(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._redact_value(arg) for arg in record.args)

        return True
