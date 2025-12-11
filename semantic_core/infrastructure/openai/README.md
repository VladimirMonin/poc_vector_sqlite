# OpenAI LLM Provider

Провайдер для генерации ответов через OpenAI API (GPT-4o, GPT-4o-mini, GPT-3.5-turbo).

## 📦 Установка

```bash
pip install openai tiktoken
```

Или используйте optional dependency:

```bash
pip install -e ".[openai]"
```

## 🚀 Быстрый старт

```python
from semantic_core.infrastructure.openai import OpenAILLMProvider

# Создание провайдера
provider = OpenAILLMProvider(
    api_key="sk-...",  # Или используйте OPENAI_API_KEY env
    model="gpt-4o-mini",
    temperature=0.7,
)

# Генерация ответа
result = provider.generate("Что такое RAG?")
print(result.text)
print(f"Tokens: {result.input_tokens} in, {result.output_tokens} out")
```

## 🔧 Возможности

### 1. Генерация с системным промптом

```python
result = provider.generate(
    prompt="Объясни векторный поиск",
    system_prompt="Ты эксперт по поисковым системам",
    temperature=0.3,
)
```

### 2. Streaming генерация

```python
for chunk in provider.generate_stream("Напиши код"):
    print(chunk, end="", flush=True)
```

### 3. История чата

```python
history = [
    {"role": "user", "content": "Привет!"},
    {"role": "assistant", "content": "Здравствуй!"},
]

result = provider.generate("Как дела?", history=history)
```

### 4. Подсчёт токенов

```python
tokens = provider.count_tokens("Сколько здесь токенов?")
print(f"Tokens: {tokens}")
```

## 🤖 Поддерживаемые модели

| Модель | Context | Стоимость (1M tokens) | Качество | Скорость |
|--------|---------|----------------------|----------|----------|
| `gpt-4o` | 128k | $2.50 / $10.00 | ⭐⭐⭐⭐⭐ | 🚀🚀 |
| `gpt-4o-mini` | 128k | $0.15 / $0.60 | ⭐⭐⭐⭐ | 🚀🚀🚀 |
| `gpt-3.5-turbo` | 16k | $0.50 / $1.50 | ⭐⭐⭐ | 🚀🚀🚀 |

**Рекомендация:** `gpt-4o-mini` - лучший баланс цена/качество.

## 🔗 Интеграция с RAGEngine

```python
from semantic_core import SemanticCore
from semantic_core.core.rag import RAGEngine
from semantic_core.infrastructure.openai import OpenAILLMProvider

# Создаём компоненты
core = SemanticCore(db_path="semantic.db", api_key="gemini-key")
llm = OpenAILLMProvider(api_key="sk-...", model="gpt-4o-mini")

# Создаём RAG Engine
rag = RAGEngine(
    semantic_core=core,
    llm_provider=llm,
    context_strategy="hierarchical",
)

# Задаём вопрос
result = rag.ask("Что такое векторный поиск?")
print(result.answer)
```

## ⚙️ Конфигурация

### Параметры инициализации

- `api_key` (Optional[str]): API ключ OpenAI (или используйте `OPENAI_API_KEY` env)
- `model` (str): Модель для использования (default: `gpt-4o-mini`)
- `temperature` (float): Температура генерации 0.0-2.0 (default: 0.7)
- `max_tokens` (int): Максимум токенов в ответе (default: 2000)
- `timeout` (float): Таймаут запроса в секундах (default: 30.0)
- `max_retries` (int): Количество повторов при ошибках (default: 3)

### Параметры generate()

- `prompt` (str): Текст запроса
- `system_prompt` (Optional[str]): Системный промпт
- `temperature` (float): Переопределить temperature
- `max_tokens` (Optional[int]): Переопределить max_tokens
- `history` (Optional[list[dict]]): История чата

## 🛡️ Обработка ошибок

```python
from openai import RateLimitError, APIError

try:
    result = provider.generate("Test")
except RateLimitError:
    print("Rate limit exceeded")
except APIError as e:
    print(f"API error: {e}")
except RuntimeError as e:
    print(f"Runtime error: {e}")
```

Провайдер автоматически:
- Повторяет запросы при временных ошибках (max_retries)
- Логирует все ошибки через semantic logger
- Передаёт специфичные исключения OpenAI

## 📊 Логирование

Все операции логируются через `semantic_core.utils.logger`:

```
[DEBUG] OpenAILLMProvider initialized model=gpt-4o-mini
[DEBUG] Generating response prompt_length=50
[INFO] Response generated latency_ms=1234.56 tokens_in=10 tokens_out=5
[TRACE_AI] prompt="What is RAG?" response="RAG is..." tokens_in=10 tokens_out=5
```

## 🧪 Тестирование

```bash
# Unit тесты
pytest tests/unit/infrastructure/llm/test_openai_llm.py -v

# Все тесты LLM провайдеров
pytest tests/unit/infrastructure/llm/ -v
```

## 📚 Примеры

См. полные примеры в `examples/openai_llm_examples.py`:
- Базовая генерация
- Системные промпты
- Streaming
- История чата
- Интеграция с RAG
- Подсчёт токенов
- Сравнение моделей

## 🔗 Ссылки

- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [OpenAI Python SDK](https://github.com/openai/openai-python)
- [Tiktoken](https://github.com/openai/tiktoken)
- [Pricing](https://openai.com/api/pricing/)
