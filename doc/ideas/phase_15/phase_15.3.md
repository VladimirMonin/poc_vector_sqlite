# 🌐 Phase 15.3: OpenAI-Compatible LLM Adapter

**Статус:** Planning  
**Зависимости:** Phase 15.0 (BaseLLMProvider уже готов)  
**Цель:** Универсальный адаптер для любого OpenAI-compatible API

---

## 🎯 Задачи

1. Создать `OpenAILLMProvider`, реализующий `BaseLLMProvider`
2. Поддержать настраиваемый `base_url` (OpenRouter, Ollama, vLLM, LM Studio)
3. Обеспечить совместимость с RAGEngine

---

## 💡 Мотивация

**Что открывает один адаптер:**

| Провайдер | base_url | Что даёт |
|-----------|----------|----------|
| OpenAI | `https://api.openai.com/v1` | GPT-4o, GPT-4-turbo |
| OpenRouter | `https://openrouter.ai/api/v1` | Claude, Llama, Mixtral |
| Ollama | `http://localhost:11434/v1` | Локальные модели |
| vLLM | `http://localhost:8000/v1` | Быстрый inference |
| LM Studio | `http://localhost:1234/v1` | GUI для локальных |
| Azure OpenAI | `https://{name}.openai.azure.com` | Enterprise |

**Один класс → Все провайдеры.**

---

## 📊 Текущее состояние BaseLLMProvider

**Файл:** `semantic_core/interfaces/llm.py`

```python
class BaseLLMProvider(ABC):
    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        history: Optional[list[dict]] = None,
    ) -> GenerationResult:
        ...
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        ...
```

**Вывод:** Интерфейс уже готов! Нужна только реализация.

---

## 🏗️ Целевая структура

```
semantic_core/infrastructure/
├── openai/
│   ├── __init__.py
│   ├── llm.py              # OpenAILLMProvider
│   └── embedder.py         # OpenAIEmbedder (future)
```

---

## 📝 Контракт OpenAILLMProvider

```python
class OpenAILLMProvider(BaseLLMProvider):
    """OpenAI-compatible LLM через httpx или openai SDK."""
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 60.0,
        default_temperature: float = 0.7,
        default_max_tokens: int = 4096,
    ):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._default_temperature = default_temperature
        self._default_max_tokens = default_max_tokens
        self._client: Optional[httpx.Client] = None
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = None,
        max_tokens: Optional[int] = None,
        history: Optional[list[dict]] = None,
    ) -> GenerationResult:
        """Генерирует ответ через OpenAI API."""
        messages = self._build_messages(prompt, system_prompt, history)
        
        response = self._client.post(
            f"{self._base_url}/chat/completions",
            json={
                "model": self._model,
                "messages": messages,
                "temperature": temperature or self._default_temperature,
                "max_tokens": max_tokens or self._default_max_tokens,
            },
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        
        return self._parse_response(response.json())
    
    @property
    def model_name(self) -> str:
        return self._model
```

---

## 📊 Диаграмма последовательности

```
User              OpenAILLMProvider          OpenAI-Compatible API
  │                      │                           │
  │  generate(prompt)    │                           │
  │─────────────────────►│                           │
  │                      │                           │
  │                      │  POST /chat/completions   │
  │                      │──────────────────────────►│
  │                      │                           │
  │                      │  {"choices": [...]}       │
  │                      │◄──────────────────────────│
  │                      │                           │
  │                      │  [parse response]         │
  │                      │                           │
  │  GenerationResult    │                           │
  │◄─────────────────────│                           │
```

---

## 🔧 Особенности разных провайдеров

### OpenRouter

```python
# Дополнительные headers
headers = {
    "Authorization": f"Bearer {api_key}",
    "HTTP-Referer": "https://your-app.com",  # Требуется
    "X-Title": "SemanticCore",               # Опционально
}
```

### Ollama

```python
# Модель без prefix
model = "llama3.2"  # Не "openai/llama3.2"
base_url = "http://localhost:11434/v1"
```

### Azure OpenAI

```python
# Другая структура URL
base_url = f"https://{resource_name}.openai.azure.com/openai/deployments/{deployment}"
headers = {"api-key": api_key}  # Не Bearer!
```

### Решение: Provider Presets

```python
class OpenAILLMProvider:
    PRESETS = {
        "openai": ProviderPreset(
            base_url="https://api.openai.com/v1",
            auth_header="Bearer",
        ),
        "openrouter": ProviderPreset(
            base_url="https://openrouter.ai/api/v1",
            auth_header="Bearer",
            extra_headers={"HTTP-Referer": "semantic-core"},
        ),
        "ollama": ProviderPreset(
            base_url="http://localhost:11434/v1",
            auth_header=None,  # Не требуется
        ),
    }
    
    @classmethod
    def from_preset(cls, preset: str, api_key: str = None, model: str = None):
        config = cls.PRESETS[preset]
        return cls(
            api_key=api_key or "",
            model=model or "gpt-4o-mini",
            base_url=config.base_url,
            # ...
        )
```

---

## 🔗 Интеграция с RAGEngine

**Файл:** `semantic_core/core/rag.py`

```python
class RAGEngine:
    def __init__(
        self,
        semantic_core: SemanticCore,
        llm_provider: BaseLLMProvider,  # ← Уже интерфейс!
        ...
    ):
```

**Использование:**

```python
# Gemini (как сейчас)
llm = GeminiLLMProvider(api_key="...")
rag = RAGEngine(core, llm)

# OpenAI (новое)
llm = OpenAILLMProvider(api_key="sk-...", model="gpt-4o")
rag = RAGEngine(core, llm)

# Ollama (локально)
llm = OpenAILLMProvider.from_preset("ollama", model="llama3.2")
rag = RAGEngine(core, llm)
```

---

## 📦 Зависимости

```toml
# pyproject.toml
[project.optional-dependencies]
openai = [
    "httpx>=0.27.0",  # Для HTTP клиента
    # ИЛИ
    "openai>=1.0.0",  # Официальный SDK
]
```

**Рекомендация:** Использовать `httpx` — легче и достаточно для chat/completions.

---

## ✅ Критерии готовности

- [ ] `OpenAILLMProvider` реализует `BaseLLMProvider`
- [ ] Поддержка `base_url` для любого OpenAI-compatible API
- [ ] Presets для популярных провайдеров (OpenAI, OpenRouter, Ollama)
- [ ] Корректная обработка ошибок (rate limit, auth, timeout)
- [ ] Логирование запросов через `semantic_core.utils.logger`
- [ ] Unit-тесты с mock HTTP
- [ ] Интеграционный тест с RAGEngine

---

## 🔗 Связанные документы

- **Интерфейс:** `semantic_core/interfaces/llm.py` — `BaseLLMProvider`
- **Использование:** `semantic_core/core/rag.py` — `RAGEngine`
- **Текущая реализация:** `semantic_core/infrastructure/llm/gemini.py` — `GeminiLLMProvider`
