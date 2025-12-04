---
title: "Custom LLM Provider"
description: "Как добавить OpenAI, Anthropic, Ollama и другие LLM"
tags: ["extending", "llm", "openai", "anthropic", "ollama"]
difficulty: "intermediate"
prerequisites: ["../../concepts/10_plugin_system"]
---

# Custom LLM Provider 🤖

> Добавьте свой LLM провайдер, реализовав один метод.

---

## Интерфейс BaseLLMProvider 📋

```
┌─────────────────────────────────────────────┐
│           BaseLLMProvider (ABC)             │
├─────────────────────────────────────────────┤
│ @abstractmethod                             │
│ generate(                                   │
│   prompt: str,                              │
│   system_prompt: str | None,                │
│   temperature: float = 0.7,                 │
│   max_tokens: int | None,                   │
│   history: list[dict] | None                │
│ ) -> GenerationResult                       │
│                                             │
│ @property @abstractmethod                   │
│ model_name: str                             │
└─────────────────────────────────────────────┘
```

---

## GenerationResult DTO 📦

| Поле | Тип | Описание |
|------|-----|----------|
| `text` | str | Сгенерированный текст |
| `model` | str | Название модели |
| `input_tokens` | int? | Токены промпта |
| `output_tokens` | int? | Токены ответа |
| `finish_reason` | str? | Причина остановки |

---

## Пример: OpenAI 🟢

```python
from openai import OpenAI
from semantic_core.interfaces import BaseLLMProvider, GenerationResult

class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.client = OpenAI(api_key=api_key)
        self._model = model
    
    @property
    def model_name(self) -> str:
        return self._model
    
    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        history: list[dict] | None = None,
    ) -> GenerationResult:
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})
        
        response = self.client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        choice = response.choices[0]
        return GenerationResult(
            text=choice.message.content,
            model=response.model,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            finish_reason=choice.finish_reason,
        )
```

---

## Пример: Anthropic 🟣

```python
from anthropic import Anthropic
from semantic_core.interfaces import BaseLLMProvider, GenerationResult

class AnthropicProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        self.client = Anthropic(api_key=api_key)
        self._model = model
    
    @property
    def model_name(self) -> str:
        return self._model
    
    def generate(self, prompt: str, **kwargs) -> GenerationResult:
        messages = []
        if kwargs.get("history"):
            messages.extend(kwargs["history"])
        messages.append({"role": "user", "content": prompt})
        
        response = self.client.messages.create(
            model=self._model,
            system=kwargs.get("system_prompt", ""),
            messages=messages,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 4096),
        )
        
        return GenerationResult(
            text=response.content[0].text,
            model=self._model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
```

---

## Пример: Ollama (локальный) 🏠

```python
import ollama
from semantic_core.interfaces import BaseLLMProvider, GenerationResult

class OllamaProvider(BaseLLMProvider):
    def __init__(self, model: str = "llama3.3"):
        self._model = model
    
    @property
    def model_name(self) -> str:
        return self._model
    
    def generate(self, prompt: str, **kwargs) -> GenerationResult:
        messages = []
        if kwargs.get("system_prompt"):
            messages.append({"role": "system", "content": kwargs["system_prompt"]})
        if kwargs.get("history"):
            messages.extend(kwargs["history"])
        messages.append({"role": "user", "content": prompt})
        
        response = ollama.chat(
            model=self._model,
            messages=messages,
        )
        
        return GenerationResult(
            text=response["message"]["content"],
            model=self._model,
        )
```

---

## Регистрация в RAGEngine ⚙️

```python
from semantic_core import SemanticCore
from semantic_core.core.rag import RAGEngine

core = SemanticCore.from_config()
llm = OpenAIProvider(api_key="sk-...")

rag = RAGEngine(core=core, llm=llm)
result = rag.ask("Вопрос")
```

---

## Mapping параметров 📊

| Semantic Core | OpenAI | Anthropic | Ollama |
|---------------|--------|-----------|--------|
| `prompt` | messages[-1] | messages[-1] | messages[-1] |
| `system_prompt` | messages[0] role=system | system | messages[0] |
| `temperature` | temperature | temperature | — (в options) |
| `max_tokens` | max_tokens | max_tokens | — |
| `history` | messages[1:-1] | messages[:-1] | messages[1:-1] |

---

## Частые ошибки ⚠️

| Ошибка | Причина | Решение |
|--------|---------|---------|
| Пустой history | Не обработан None | `if history: ...` |
| Token overflow | Нет max_tokens | Передавайте лимит |
| Timeout | Медленная модель | Увеличьте timeout |

---

## Следующие шаги 🔗

| Гайд | Что узнаете |
|------|-------------|
| [Custom Embedder](custom-embedder.md) | Свой генератор эмбеддингов |
| [Plugin System](../../concepts/10_plugin_system.md) | Архитектура интерфейсов |
