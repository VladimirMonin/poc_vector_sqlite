# 54. Python Truthiness Trap: Когда пустой объект — не None

> **Эпизод 54** — Коварный баг, который молча ломает логику через `__len__()`

---

## 🎯 О чём этот эпизод

Представьте: вы написали менеджер истории чата. Создали красивый класс с методами `add_user()`, `add_assistant()`, `get_history()`. Всё работает в тестах. Но в продакшене:

- `/history` говорит "История отключена"
- `/tokens` говорит "История отключена"
- История не накапливается вообще

При этом `--no-history` флаг **не передавался**! Объект `history_manager` существует!

**Что за чертовщина?**

---

## 🔍 Расследование: симптомы

Пользователь запускает чат, задаёт 3-4 вопроса, потом:

```bash
> /history

⚠️ История отключена. Используйте --no-history для явного отключения.

> /tokens

⚠️ История отключена. Используйте --no-history для явного отключения.
```

Но в welcome-сообщении было:

```
📚 История: включена (лимит: 10 сообщений)
```

**WTF?!**

---

## 🐛 Корень проблемы: `__len__()` и truthiness

Открываем `ChatHistoryManager`:

```python
class ChatHistoryManager:
    def __init__(self, strategy):
        self._messages: list[ChatMessage] = []
        self._strategy = strategy
    
    def __len__(self) -> int:
        return len(self._messages)  # ← ВИНОВНИК!
```

А теперь смотрим на код слэш-команды:

```python
class TokensCommand(BaseSlashCommand):
    def execute(self, ctx: ChatContext, args: str) -> SlashResult:
        if not ctx.history_manager:  # ← ЛОВУШКА!
            return SlashResult(message="⚠️ История отключена...")
```

---

## 🧪 Эксперимент: как Python оценивает объекты

```python
>>> class MyContainer:
...     def __init__(self):
...         self._items = []
...     def __len__(self):
...         return len(self._items)

>>> obj = MyContainer()
>>> obj is None
False          # Объект существует!

>>> bool(obj)
False          # НО! Python считает его "пустым"

>>> not obj
True           # И `not obj` — True!
```

**Python Data Model (PEP 285):**

```
bool(x) вызывает:
1. x.__bool__() если определён
2. x.__len__() если определён → True если != 0
3. True по умолчанию
```

Наш `ChatHistoryManager` имеет `__len__()`, который возвращает `0` для пустой истории.
Поэтому `bool(history_manager)` = `False`.

---

## 📊 Визуализация проблемы

```
                    history_manager = ChatHistoryManager()
                              │
                              ▼
                    len(self._messages) = 0
                              │
                              ▼
                    __len__() returns 0
                              │
                              ▼
                    bool(history_manager) = False
                              │
                              ▼
            ┌─────────────────┴─────────────────┐
            │                                    │
            ▼                                    ▼
    if not history_manager:              if history_manager is None:
            │                                    │
            ▼                                    ▼
    TRUE! (баг)                          FALSE (правильно)
```

---

## 🔧 Где был баг: 6 мест!

### 1. Slash-команды (basic.py)

**TokensCommand:**
```python
# ❌ БЫЛО
if not ctx.history_manager:
    return SlashResult(message="⚠️ История отключена...")

# ✅ СТАЛО  
if ctx.history_manager is None:
    return SlashResult(message="⚠️ История отключена...")
```

**HistoryCommand:**
```python
# ❌ БЫЛО
if not ctx.history_manager:
    ...

# ✅ СТАЛО
if ctx.history_manager is None:
    ...
```

**CompressCommand:**
```python
# ❌ БЫЛО
if not ctx.history_manager:
    ...

# ✅ СТАЛО
if ctx.history_manager is None:
    ...
```

### 2. REPL loop (chat.py)

**Получение истории для RAG (строка 322):**
```python
# ❌ БЫЛО
history = history_manager.get_history() if history_manager else None

# ✅ СТАЛО
history = history_manager.get_history() if history_manager is not None else None
```

**Сохранение в историю (строка 350):**
```python
# ❌ БЫЛО
if history_manager:
    history_manager.add_user(query, tokens=input_tokens // 2)
    history_manager.add_assistant(result.answer, tokens=output_tokens)

# ✅ СТАЛО
if history_manager is not None:
    history_manager.add_user(query, tokens=input_tokens // 2)
    history_manager.add_assistant(result.answer, tokens=output_tokens)
```

**Отображение статистики (строка 386):**
```python
# ❌ БЫЛО
if history_manager:
    msg_count = len(history_manager)
    ...

# ✅ СТАЛО
if history_manager is not None:
    msg_count = len(history_manager)
    ...
```

---

## 📏 Правило: Explicit is Better than Implicit

**Zen of Python, PEP 20:**

> Explicit is better than implicit.

Когда проверяете "объект существует?":

| Паттерн | Когда использовать |
|---------|-------------------|
| `if obj is None:` | Объект может быть None или существовать |
| `if obj is not None:` | Объект может быть None или существовать |
| `if not obj:` | Только для bool/int/str или когда нужна "пустота" |
| `if obj:` | Только для bool/int/str или когда нужна "непустота" |

**Опасные кейсы:**

```python
# Все эти объекты "falsy", но существуют!
empty_list = []
empty_dict = {}
empty_set = set()
zero = 0
empty_string = ""
custom_container = MyContainer()  # с __len__() = 0
```

---

## 🧪 E2E тесты: ловим баг до продакшена

После исправления добавили E2E тесты с реальным Gemini API:

```python
class TestChatE2E:
    """E2E тесты чата с реальным API."""
    
    def test_history_accumulates_messages(self, cli_runner):
        """История накапливает сообщения между вопросами."""
        result = cli_runner.invoke(
            app,
            ["chat"],
            input="Что такое Python?\nКакие его особенности?\n/history\n/quit\n",
        )
        
        # После двух вопросов история должна содержать сообщения
        assert "История пуста" not in result.output or \
               ("2 сообщ" in result.output or "2 messages" in result.output)
    
    def test_tokens_command_works(self, cli_runner):
        """Команда /tokens показывает статистику."""
        result = cli_runner.invoke(
            app,
            ["chat"],
            input="/tokens\n/quit\n",
        )
        
        # Не должно быть сообщения об отключённой истории
        assert "История отключена" not in result.output
        assert "Сообщений в истории" in result.output
```

**14 E2E тестов** теперь гарантируют, что:
- `/tokens` работает
- `/history` работает
- `/compress` работает
- История накапливается между вопросами

---

## 🎓 Урок: контейнеры и `__len__()`

Если ваш класс:
- Хранит коллекцию элементов
- Имеет метод `__len__()`
- Может быть "пустым"

То **везде** используйте `is None` / `is not None` для проверки существования!

```python
# Создаём "контейнерный" класс
class MessageQueue:
    def __init__(self):
        self._queue = []
    
    def __len__(self):
        return len(self._queue)
    
    def __bool__(self):
        # Можно переопределить явно!
        return True  # Всегда "truthy"

# Теперь безопасно:
queue = MessageQueue()
bool(queue)  # True, даже если пуста
```

Но лучше — **всегда явная проверка `is None`**.

---

## 📋 Чеклист для Code Review

При ревью кода с Optional-типами спрашивайте:

- [ ] Есть `if obj:` или `if not obj:` с Optional?
- [ ] У объекта есть `__len__()` или `__bool__()`?
- [ ] Нужна проверка существования или непустоты?
- [ ] Используется `is None` / `is not None` для Optional?

---

## 🔗 Связанные концепции

| Эпизод | Тема | Связь |
|--------|------|-------|
| [47. Chat History Management](47_chat_history_management.md) | ChatHistoryManager | Класс с `__len__()` |
| [49. Slash Commands](49_slash_commands.md) | Команды чата | Где был баг |
| [46. RAG Chat CLI](46_rag_chat_cli.md) | REPL loop | Где был баг |

---

## 💡 Итог

**Проблема:** Python считает объект с `__len__() == 0` "falsy"

**Симптом:** Все проверки `if history_manager:` возвращают `False` для пустой истории

**Решение:** Заменить на `if history_manager is not None:`

**Профилактика:** E2E тесты с реальным использованием

> "Если что-то выглядит как None, крякает как None, но `is not None` — это Python."

---

**← [53. Windows Compatibility](53_windows_compatibility.md)** | **[К оглавлению](00_overview.md)** 
