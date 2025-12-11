"""Unit-тесты для _sanitize_fts_query.

Проверяем экранирование спецсимволов FTS5:
- Круглые скобки ()
- Вопросительные знаки ?
- Дефисы -
- Квадратные скобки []
- Логические операторы OR/AND/NOT
- Wildcard *
"""

import pytest
from semantic_core.infrastructure.storage.peewee.adapter import _sanitize_fts_query


class TestSanitizeFtsQuery:
    """Тесты для _sanitize_fts_query функции."""

    def test_simple_word(self):
        """Простое слово без спецсимволов."""
        assert _sanitize_fts_query("Python") == "Python"

    def test_multiple_words(self):
        """Несколько слов без спецсимволов."""
        assert _sanitize_fts_query("Python programming") == "Python programming"

    def test_parentheses_wraps_in_quotes(self):
        """Круглые скобки оборачивают весь запрос в кавычки."""
        result = _sanitize_fts_query("Python (language)")
        assert result == '"Python (language)"'

    def test_question_mark_wraps_in_quotes(self):
        """Вопросительный знак оборачивает весь запрос в кавычки."""
        result = _sanitize_fts_query("What is Python?")
        assert result == '"What is Python?"'

    def test_hyphen_inside_token(self):
        """Дефис внутри токена оборачивает токен в кавычки."""
        result = _sanitize_fts_query("machine-learning")
        assert result == '"machine-learning"'

    def test_hyphen_at_start_not_operator(self):
        """Дефис в начале токена (NOT оператор) НЕ обрачивается."""
        result = _sanitize_fts_query("-Python")
        assert result == "-Python"

    def test_square_brackets(self):
        """Квадратные скобки оборачивают токен."""
        result = _sanitize_fts_query("array[0]")
        assert result == '"array[0]"'

    def test_or_operator_preserved(self):
        """OR оператор сохраняется."""
        result = _sanitize_fts_query("Python OR language")
        assert result == "Python OR language"

    def test_and_operator_preserved(self):
        """AND оператор сохраняется."""
        result = _sanitize_fts_query("Python AND language")
        assert result == "Python AND language"

    def test_not_operator_preserved(self):
        """NOT оператор сохраняется."""
        result = _sanitize_fts_query("Python NOT Java")
        assert result == "Python NOT Java"

    def test_wildcard_preserved(self):
        """Wildcard * сохраняется."""
        result = _sanitize_fts_query("Python*")
        assert result == "Python*"

    def test_already_quoted(self):
        """Уже обёрнутый запрос не трогаем."""
        result = _sanitize_fts_query('"already quoted"')
        assert result == '"already quoted"'

    def test_double_quotes_with_parens(self):
        """Внутренние кавычки экранируются когда есть скобки."""
        result = _sanitize_fts_query('Quote (in parens): "hello"')
        # FTS5 uses "" for escaping
        assert result == '"Quote (in parens): ""hello"""'

    def test_complex_query_with_operators(self):
        """Сложный запрос с операторами."""
        result = _sanitize_fts_query("Python AND machine-learning OR data-science")
        assert result == 'Python AND "machine-learning" OR "data-science"'

    def test_mixed_special_chars(self):
        """Смешанные спецсимволы (скобки + вопросы) оборачивают весь запрос."""
        result = _sanitize_fts_query("What is Python (lang)?")
        assert result == '"What is Python (lang)?"'


class TestSanitizeFtsQueryEdgeCases:
    """Граничные случаи и edge cases."""

    def test_empty_string(self):
        """Пустая строка."""
        assert _sanitize_fts_query("") == ""

    def test_only_spaces(self):
        """Только пробелы."""
        assert _sanitize_fts_query("   ") == ""

    def test_operators_lowercase(self):
        """Операторы в нижнем регистре тоже должны работать."""
        result = _sanitize_fts_query("python or language")
        assert result == "python or language"

    def test_operators_mixed_case(self):
        """Операторы в смешанном регистре."""
        result = _sanitize_fts_query("Python Or Language")
        assert result == "Python Or Language"

    def test_hyphen_with_operators(self):
        """Дефис с операторами."""
        result = _sanitize_fts_query("machine-learning AND deep-learning")
        assert result == '"machine-learning" AND "deep-learning"'

    def test_multiple_parentheses(self):
        """Несколько пар скобок."""
        result = _sanitize_fts_query("(Python) OR (Java)")
        assert result == '"(Python) OR (Java)"'

    def test_nested_quotes_in_parens(self):
        """Вложенные кавычки внутри скобок."""
        result = _sanitize_fts_query('(Quote: "test")')
        assert result == '"(Quote: ""test"")"'
