# Phase 9.1: Context Management

**Статус:** 🔲 Планируется  
**Зависимости:** Phase 9.0 ✅  
**Оценка:** ~0.5 дня

---

## 🎯 Цель

Добавить управление историей чата со стратегиями ограничения.

---

## 🔧 Режимы (стратегии)

| Стратегия | Описание | Флаг CLI |
|-----------|----------|----------|
| `LastNMessages` | Хранить N последних сообщений | `--history-limit 10` |
| `TokenBudget` | Лимит по токенам | `--token-budget 50000` |
| `Unlimited` | Без ограничений (опасно!) | `--no-history-limit` |

---

## 📦 Структура

```
semantic_core/
├── interfaces/
│   └── context.py                # BaseContextStrategy
├── core/
│   ├── rag.py                    # обновлён
│   └── context/
│       ├── __init__.py
│       ├── strategies.py         # LastNMessages, TokenBudget
│       └── manager.py            # ContextManager
```

---

## 📐 Интерфейс BaseContextStrategy

```python
# semantic_core/interfaces/context.py

from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class Message:
    role: str  # "user" | "assistant"
    content: str
    tokens: int = 0

class BaseContextStrategy(ABC):
    """Стратегия управления историей."""
    
    @abstractmethod
    def should_trim(self, messages: list[Message]) -> bool:
        """Нужно ли обрезать историю?"""
        pass
    
    @abstractmethod
    def trim(self, messages: list[Message]) -> list[Message]:
        """Обрезать историю согласно стратегии."""
        pass
```

---

## 📐 Реализации стратегий

```python
# semantic_core/core/context/strategies.py

class LastNMessages(BaseContextStrategy):
    """Хранить только N последних сообщений."""
    
    def __init__(self, n: int = 10):
        self.n = n
    
    def should_trim(self, messages):
        return len(messages) > self.n
    
    def trim(self, messages):
        return messages[-self.n:]


class TokenBudget(BaseContextStrategy):
    """Лимит по общему количеству токенов."""
    
    def __init__(self, max_tokens: int = 50000):
        self.max_tokens = max_tokens
    
    def should_trim(self, messages):
        return sum(m.tokens for m in messages) > self.max_tokens
    
    def trim(self, messages):
        total = 0
        result = []
        for msg in reversed(messages):
            if total + msg.tokens > self.max_tokens:
                break
            result.insert(0, msg)
            total += msg.tokens
        return result


class Unlimited(BaseContextStrategy):
    """Без ограничений."""
    
    def should_trim(self, messages):
        return False
    
    def trim(self, messages):
        return messages
```

---

## 📐 ContextManager

```python
# semantic_core/core/context/manager.py

class ContextManager:
    """Управляет историей чата."""
    
    def __init__(self, strategy: BaseContextStrategy):
        self.strategy = strategy
        self.messages: list[Message] = []
    
    def add(self, role: str, content: str, tokens: int = 0):
        self.messages.append(Message(role=role, content=content, tokens=tokens))
        if self.strategy.should_trim(self.messages):
            self.messages = self.strategy.trim(self.messages)
    
    def get_history(self) -> list[Message]:
        return self.messages.copy()
    
    def clear(self):
        self.messages.clear()
    
    def total_tokens(self) -> int:
        return sum(m.tokens for m in self.messages)
```

---

## 📐 CLI опции

```python
@chat_cmd.callback()
def chat(
    # ... existing options ...
    history_limit: int = Option(10, "--history-limit", help="Max messages"),
    token_budget: int = Option(None, "--token-budget", help="Max tokens"),
    no_history_limit: bool = Option(False, "--no-history-limit"),
):
    # Выбор стратегии
    if no_history_limit:
        strategy = Unlimited()
    elif token_budget:
        strategy = TokenBudget(token_budget)
    else:
        strategy = LastNMessages(history_limit)
    
    context_mgr = ContextManager(strategy)
```

---

## ✅ Acceptance Criteria

- [ ] `BaseContextStrategy` интерфейс
- [ ] `LastNMessages` работает
- [ ] `TokenBudget` работает  
- [ ] `ContextManager` интегрирован в chat
- [ ] Токены считаются из `GenerationResult`
- [ ] CLI флаги работают

---

## ⏱️ Оценка

| Задача | Часы |
|--------|------|
| interfaces/context.py | 0.5 |
| strategies.py | 1 |
| manager.py | 1 |
| Интеграция в chat.py | 1 |
| Тесты | 1.5 |
| **Итого** | **~5 часов** |
