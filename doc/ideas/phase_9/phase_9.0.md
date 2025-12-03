# Phase 9.0: Core RAG Engine

**Статус:** 🔲 Планируется  
**Оценка:** ~1.5 дня

---

## 🎯 Цель

Базовый RAG чат без истории — один вопрос → поиск → ответ.

---

## 📦 Структура файлов

```
semantic_core/
├── interfaces/
│   └── llm.py                    # BaseLLMProvider, GenerationResult
├── infrastructure/
│   └── llm/
│       ├── __init__.py
│       └── gemini.py             # GeminiLLMProvider
├── core/
│   └── rag.py                    # RAGEngine
└── cli/commands/
    └── chat.py                   # semantic chat (базовый REPL)
```

---

## 📐 Интерфейс BaseLLMProvider

```python
# semantic_core/interfaces/llm.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class GenerationResult:
    """Результат генерации от LLM."""
    text: str
    model: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    finish_reason: Optional[str] = None

class BaseLLMProvider(ABC):
    """Интерфейс для провайдеров LLM."""
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> GenerationResult:
        pass
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        pass
```

---

## 📐 GeminiLLMProvider

```python
# semantic_core/infrastructure/llm/gemini.py

class GeminiLLMProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self._client = genai.Client(api_key=api_key)
        self._model = model
    
    def generate(self, prompt, system_prompt=None, temperature=0.7, max_tokens=None):
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                system_instruction=system_prompt,
            ),
        )
        return GenerationResult(
            text=response.text,
            model=self._model,
            input_tokens=response.usage_metadata.prompt_token_count,
            output_tokens=response.usage_metadata.candidates_token_count,
        )
```

---

## 📐 RAGEngine

```python
# semantic_core/core/rag.py

@dataclass
class RAGResult:
    answer: str
    sources: list[SearchResult]
    generation: GenerationResult

class RAGEngine:
    DEFAULT_SYSTEM_PROMPT = """Answer based ONLY on the provided context.
If context doesn't have the answer, say so. Format in Markdown."""
    
    def __init__(self, core: SemanticCore, llm: BaseLLMProvider, context_chunks: int = 5):
        self.core = core
        self.llm = llm
        self.context_chunks = context_chunks
    
    def ask(self, query: str, search_mode: str = "hybrid") -> RAGResult:
        # 1. Retrieval
        sources = self.core.search(query, limit=self.context_chunks, mode=search_mode)
        # 2. Build context
        context = self._build_context(sources)
        # 3. Generate
        generation = self.llm.generate(
            prompt=f"CONTEXT:\n{context}\n\nQUESTION:\n{query}",
            system_prompt=self.DEFAULT_SYSTEM_PROMPT,
        )
        return RAGResult(answer=generation.text, sources=sources, generation=generation)
```

---

## 📐 CLI: semantic chat

```python
# semantic_core/cli/commands/chat.py

@chat_cmd.callback(invoke_without_command=True)
def chat(
    model: str = Option("gemini-2.0-flash", "--model", "-m"),
    context_chunks: int = Option(5, "--context", "-c"),
    search_mode: str = Option("hybrid", "--search", "-s", help="vector/fts/hybrid"),
):
    """Интерактивный RAG чат."""
    # ... инициализация ...
    
    while True:
        query = Prompt.ask("[bold blue]You[/]")
        if query in ("exit", "quit"): break
        
        result = rag.ask(query, search_mode=search_mode)
        console.print(Markdown(result.answer))
        _show_sources(result.sources)
```

---

## ✅ Acceptance Criteria

- [ ] `BaseLLMProvider` интерфейс
- [ ] `GeminiLLMProvider` с токенами в ответе
- [ ] `RAGEngine.ask()` работает
- [ ] `semantic chat` запускает REPL
- [ ] Поддержка `--search vector|fts|hybrid`
- [ ] Тесты: mock LLM, build_context

---

## ⏱️ Оценка

| Задача | Часы |
|--------|------|
| interfaces/llm.py | 0.5 |
| infrastructure/llm/gemini.py | 1.5 |
| core/rag.py | 2 |
| cli/commands/chat.py | 3 |
| Тесты | 2 |
| EMOJI_MAP | 0.5 |
| **Итого** | **~10 часов** |
