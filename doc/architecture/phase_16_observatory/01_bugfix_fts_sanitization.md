# 🐛 Критический баг: FTS5 Query Sanitization

> Как обнаружили и исправили баг, существовавший с Phase 2

**Коммит:** `aced5f8` — bugfix: Исправлена sanitization FTS5 запросов со спецсимволами

---

## 🎯 Проблема

При создании E2E теста для Observatory с запросом **"What is Python programming language?"** тест упал с ошибкой:

```
FAILED tests/e2e/audit/test_inspector_gemini.py::test_inspector_search_with_gemini
peewee.OperationalError: fts5: syntax error near "?"
```

**Что случилось?**

Hybrid search в E2E тесте вызвал FTS5 поиск, который **сломался на вопросительном знаке** в запросе.

---

## 🔍 Исследование

### Шаг 1: Воспроизведение проблемы

```python
import sqlite3

conn = sqlite3.connect(':memory:')
conn.execute('CREATE VIRTUAL TABLE test USING fts5(content)')
conn.execute('INSERT INTO test VALUES (?)', ('Python programming language',))

# ❌ Падает с syntax error
cursor = conn.execute('SELECT * FROM test WHERE test MATCH ?', ('What is Python?',))
# fts5: syntax error near "?"

# ✅ Работает с кавычками
cursor = conn.execute('SELECT * FROM test WHERE test MATCH ?', ('"What is Python?"',))
# Успешно! Но результатов 0 (phrase match не находит совпадений)
```

**Вывод:** FTS5 **НЕ ПРИНИМАЕТ** специальные символы в запросах без экранирования.

### Шаг 2: Проверка других символов

```python
test_cases = [
    ('Python', 'Simple word'),                    # ✅ Работает
    ('Python (lang)', 'Parentheses'),            # ❌ syntax error near "Python"
    ('What is Python?', 'Question mark'),        # ❌ syntax error near "?"
    ('"Python programming"', 'Quoted phrase'),   # ✅ Работает
    ('Python*', 'Wildcard'),                     # ✅ Работает
    ('Python OR language', 'OR operator'),       # ✅ Работает
]
```

**Проблемные символы:**
- `()` — круглые скобки (группировка в FTS5)
- `?` — вопросительный знак (неизвестный оператор)
- Другие пунктуационные знаки

### Шаг 3: Изучение документации

**Из SQLite FTS5 документации:**

> FTS5 special operators: `()` for grouping, `*` for prefix match, `-` for NOT, `"..."` for phrase match

**Из StackOverflow** (https://stackoverflow.com/questions/65612489/):

> You can't have parameters in string literals; there's no interpolation.  
> If you want to match a phrase with special chars, **wrap it in double quotes**.

**FTS5 escaping rules:**
- Внутренние кавычки экранируются как `""`
- Круглые скобки работают только внутри phrase match `"..."`
- Вопросительные знаки должны быть в phrase match

---

## 🏗️ Старая реализация (СЛОМАНА)

```python
# semantic_core/infrastructure/storage/peewee/adapter.py
def _sanitize_fts_query(query: str) -> str:
    """Экранирует запрос для FTS5.

    Стратегия:
    - Токены с дефисами (не в начале) оборачиваем в кавычки
    - Токены с квадратными скобками оборачиваем в кавычки
    """
    tokens = query.split()
    result = []

    for token in tokens:
        needs_quoting = False

        # Дефис внутри токена (не в начале)
        if "-" in token and not token.startswith("-"):
            needs_quoting = True

        # Квадратные скобки
        if "[" in token or "]" in token:
            needs_quoting = True

        if needs_quoting:
            token = token.strip('"')
            result.append(f'"{token}"')
        else:
            result.append(token)

    return " ".join(result)
```

**Проблемы:**

❌ **НЕ обрабатывает круглые скобки `()`**
```python
_sanitize_fts_query("Python (language)")
# Вернёт: "Python (language)"
# FTS5: syntax error near "Python" ❌
```

❌ **НЕ обрабатывает вопросительные знаки `?`**
```python
_sanitize_fts_query("What is Python?")
# Вернёт: "What is Python?"
# FTS5: syntax error near "?" ❌
```

✅ **Обрабатывает дефисы** (это работало)
```python
_sanitize_fts_query("machine-learning")
# Вернёт: '"machine-learning"' ✅
```

---

## ✅ Новая реализация (ИСПРАВЛЕНО)

```python
def _sanitize_fts_query(query: str) -> str:
    """Экранирует запрос для FTS5.

    Стратегия:
    1. Если query уже в кавычках — не трогаем
    2. Если есть круглые скобки () или ? — оборачиваем ВСЁ в кавычки (phrase match)
    3. Если есть дефисы/квадратные скобки внутри токенов — оборачиваем токен
    4. Иначе возвращаем как есть (для поддержки OR/AND/NOT/*)
    """
    # 1. Если уже в кавычках — не трогаем
    if query.startswith('"') and query.endswith('"'):
        return query

    # 2. Проверяем наличие проблемных символов
    has_parens = "(" in query or ")" in query
    has_question = "?" in query
    has_special = has_parens or has_question

    # 3. Если есть проблемные символы — оборачиваем ВСЁ в кавычки
    if has_special:
        # Экранируем внутренние кавычки (FTS5 uses "")
        escaped = query.replace('"', '""')
        return f'"{escaped}"'

    # 4. Иначе обрабатываем токены по отдельности
    tokens = query.split()
    result = []

    for token in tokens:
        # Пропускаем логические операторы
        if token.upper() in ("OR", "AND", "NOT"):
            result.append(token)
            continue

        needs_quoting = False

        # Дефис внутри токена (не в начале для NOT)
        if "-" in token and not token.startswith("-"):
            needs_quoting = True

        # Квадратные скобки
        if "[" in token or "]" in token:
            needs_quoting = True

        if needs_quoting:
            token = token.strip('"')
            result.append(f'"{token}"')
        else:
            result.append(token)

    return " ".join(result)
```

**Ключевые улучшения:**

✅ **Обрабатывает круглые скобки**
```python
_sanitize_fts_query("Python (language)")
# Вернёт: '"Python (language)"' ✅
# FTS5: работает как phrase match
```

✅ **Обрабатывает вопросительные знаки**
```python
_sanitize_fts_query("What is Python?")
# Вернёт: '"What is Python?"' ✅
# FTS5: работает как phrase match
```

✅ **Сохраняет логические операторы**
```python
_sanitize_fts_query("Python OR language")
# Вернёт: 'Python OR language' ✅
# FTS5: OR работает как оператор
```

✅ **Экранирует внутренние кавычки**
```python
_sanitize_fts_query('Quote (in text): "hello"')
# Вернёт: '"Quote (in text): ""hello"""' ✅
# FTS5: двойные кавычки экранируют внутренние
```

---

## 🧪 Тестирование

### Unit Tests

Создан файл `tests/unit/infrastructure/storage/test_fts_sanitization.py` с **22 тестами**:

```python
class TestSanitizeFtsQuery:
    """Тесты для _sanitize_fts_query функции."""

    def test_simple_word(self):
        """Простое слово без спецсимволов."""
        assert _sanitize_fts_query("Python") == "Python"

    def test_parentheses_wraps_in_quotes(self):
        """Круглые скобки оборачивают весь запрос."""
        assert _sanitize_fts_query("Python (language)") == '"Python (language)"'

    def test_question_mark_wraps_in_quotes(self):
        """Вопросительный знак оборачивает весь запрос."""
        assert _sanitize_fts_query("What is Python?") == '"What is Python?"'

    def test_hyphen_inside_token(self):
        """Дефис внутри токена оборачивает токен."""
        assert _sanitize_fts_query("machine-learning") == '"machine-learning"'

    def test_or_operator_preserved(self):
        """OR оператор сохраняется."""
        assert _sanitize_fts_query("Python OR language") == "Python OR language"

    def test_wildcard_preserved(self):
        """Wildcard * сохраняется."""
        assert _sanitize_fts_query("Python*") == "Python*"

    # ... ещё 16 тестов
```

**Результаты:**
```bash
pytest tests/unit/infrastructure/storage/test_fts_sanitization.py -v
# ======================== 22 passed, 1 warning in 0.02s =========================
```

### Integration Tests

Проверка с реальным SQLite:

```python
import sqlite3

conn = sqlite3.connect(':memory:')
conn.execute('CREATE VIRTUAL TABLE test USING fts5(content)')
conn.execute('INSERT INTO test VALUES (?)', ('Python programming language',))

# Тестируем sanitization
test_cases = [
    'Python',
    'Python (language)',
    'What is Python?',
    'machine-learning',
    'Python OR language',
]

for query in test_cases:
    sanitized = _sanitize_fts_query(query)
    try:
        cursor = conn.execute('SELECT * FROM test WHERE test MATCH ?', (sanitized,))
        print(f'✅ {query:30} → {sanitized}')
    except Exception as e:
        print(f'❌ {query:30} → ERROR: {e}')
```

**Результат:**
```
✅ Python                         → Python
✅ Python (language)              → "Python (language)"
✅ What is Python?                → "What is Python?"
✅ machine-learning               → "machine-learning"
✅ Python OR language             → Python OR language
```

### Regression Tests

Все существующие FTS тесты проходят:

```bash
# Phase 2 tests
pytest tests/test_phase_2_storage.py::TestFTSSearch -v
# ======================== 2 passed, 1 warning ========================

# Integration tests
pytest tests/integration/search/test_fts_chunk_level.py -v
# ======================== 3 passed, 1 warning ========================

# E2E tests (Observatory)
pytest tests/e2e/audit/test_inspector_gemini.py::test_inspector_search_with_gemini -v
# ======================== 1 passed, 1 warning ========================
```

---

## 📊 Почему баг не обнаружили раньше?

### 1. Тесты использовали простые запросы

**Существующие тесты Phase 2:**
```python
def test_fts_search_basic(self, store_with_data):
    results = store_with_data.search(
        query_text="Python",  # ← Простое слово
        mode="fts",
    )
```

**Никто не тестировал:**
- Запросы с круглыми скобками
- Запросы с вопросительными знаками
- Естественные вопросы пользователей

### 2. Ручное тестирование не покрывало edge cases

**Типичные ручные запросы:**
- `"machine learning"` ✅ Работало (дефис экранировался)
- `"Python programming"` ✅ Работало (простые слова)
- `"vector search"` ✅ Работало

**Не тестировали:**
- `"What is Python?"` ❌
- `"Python (programming language)"` ❌
- `"How to use arrays[0]?"` ❌

### 3. ComponentFactory никогда не тестировался

**Критично:** Unit-тест `test_create_semantic_core_success` был **skipped**:

```python
def test_create_semantic_core_success(self, ...):
    pytest.skip("Requires integration test - lazy imports and real database")
```

Поэтому никто не запускал полный pipeline через `create_core()` в тестах.

E2E тесты Observatory были **первыми**, кто использовал `create_core()` и реальные запросы!

---

## 🎯 Выводы

### Что узнали

1. **FTS5 syntax очень строгий** — малейший спецсимвол ломает запрос
2. **Phrase match `"..."` — универсальное решение** для проблемных символов
3. **Duck typing с graceful degradation** работает для provider-agnostic кода
4. **E2E тесты находят реальные баги** которые unit-тесты пропускают

### Lessons Learned

**✅ DO:**
- Тестировать edge cases (спецсимволы, пунктуация)
- Писать E2E тесты с реальными сценариями
- Не skip'ать integration тесты (даже если они "сложные")
- Документировать проблемные области (FTS5 syntax)

**❌ DON'T:**
- Полагаться только на простые unit-тесты
- Skip'ать тесты "на потом"
- Игнорировать edge cases в пользовательских запросах

---

## 🔗 Связанные материалы

- [SQLite FTS5 Documentation](https://sqlite.org/fts5.html#full_text_query_syntax)
- [StackOverflow: FTS5 special characters](https://stackoverflow.com/questions/65612489/)
- [Phase 2: Storage Layer](../phase_2_storage/README.md) — где был создан `_sanitize_fts_query`
- [Phase 16: Observatory](README.md) — как обнаружили баг

---

**← [Назад к Phase 16](README.md)**
