---
title: "Interfaces Reference"
description: "Все интерфейсы (ABC) для расширения SemanticCore"
tags: ["reference", "interfaces", "api"]
---

# Interfaces Reference 📐

> Контракты для расширения системы.

---

## Обзор интерфейсов 📋

| Интерфейс | Модуль | Назначение |
|-----------|--------|------------|
| `BaseEmbedder` | interfaces.embedder | Генерация эмбеддингов |
| `BaseVectorStore` | interfaces.vector_store | Хранение и поиск |
| `BaseLLMProvider` | interfaces.llm | Генерация текста (LLM) |
| `BaseSplitter` | interfaces.splitter | Нарезка на чанки |
| `BaseContextStrategy` | interfaces.context | Формирование контекста |
| `DocumentParser` | interfaces.parser | Парсинг документов |
| `BaseChatHistoryStrategy` | interfaces.chat_history | Управление историей |

---

## BaseEmbedder 🧠

**Модуль:** `semantic_core.interfaces.embedder`

Интерфейс для генерации векторных представлений текста.

### Properties

| Property | Type | Описание |
|----------|------|----------|
| `dimension` | `int` | Размерность векторов (384, 768, 1024, 1536) |
| `max_tokens` | `int` | Максимальное количество токенов |
| `model_name` | `str` | Название модели |

### Methods

#### `embed_documents(texts: list[str]) → list[np.ndarray]`

Генерирует embeddings для batch документов.

**Parameters:**
- `texts` — список текстов для векторизации

**Returns:**
- Список numpy arrays с векторами (shape: `[len(texts), dimension]`)

**Raises:**
- `ValueError` — если texts пустой
- `RuntimeError` — если API/model недоступны

**Example:**
```python
embedder = GeminiEmbedder(api_key="key", dimension=768)
vectors = embedder.embed_documents([
    "First document",
    "Second document"
])
# vectors: [array([...]), array([...])]
```

#### `embed_query(text: str) → np.ndarray`

Генерирует embedding для одного запроса.

**Parameters:**
- `text` — текст запроса

**Returns:**
- Numpy array с вектором (shape: `[dimension,]`)

**Raises:**
- `ValueError` — если text пустой
- `RuntimeError` — если API/model недоступны

**Example:**
```python
vector = embedder.embed_query("What is semantic search?")
# vector: array([0.1, 0.2, ..., 0.9])  # 768 elements
```

### Реализации

| Класс | Provider | Dimension | Max Tokens |
|-------|----------|-----------|------------|
| `GeminiEmbedder` | Google Gemini | 768 | 2048 |
| `LocalEmbedder` | MLX (macOS) | 384-1024 | 512-8192 |
| `OpenAIEmbedder` | OpenAI | 1536 | 8191 |

**См. также:**
- [Custom Embedder Guide](../guides/extending/custom-embedder.md)
- [Local Embeddings Guide](../guides/core/local-embeddings.md)

---

## BaseVectorStore 💾

| Метод | Сигнатура | Описание |
|-------|-----------|----------|
| `save` | `(doc, chunks) → Document` | Сохранить документ |
| `search` | `(vector, text, ...) → list[SearchResult]` | Поиск документов |
| `search_chunks` | `(...) → list[ChunkResult]` | Поиск чанков |
| `delete` | `(doc_id) → int` | Удалить документ |
| `delete_by_metadata` | `(filters) → int` | Удалить по фильтрам |
| `bulk_update_vectors` | `(dict) → int` | Batch update векторов |

**Реализации**: `PeeweeVectorStore`

**Гайд**: [Custom VectorStore](../guides/extending/custom-vector-store.md)

---

## BaseLLMProvider 🤖

**Модуль:** `semantic_core.interfaces.llm`

Интерфейс для генерации текста через Large Language Models.

### Properties

| Property | Type | Описание |
|----------|------|----------|
| `model_name` | `str` | Название модели (например, "gemini-2.0-flash") |

### Methods

#### `generate(prompt: str, *, system_prompt: str | None = None, temperature: float = 0.7, max_tokens: int = 1024, history: list[dict] | None = None) → GenerationResult`

Генерирует ответ на промпт.

**Parameters:**
- `prompt` — текст запроса
- `system_prompt` — системный промпт (опционально)
- `temperature` — креативность (0.0-2.0), default 0.7
- `max_tokens` — максимальная длина ответа
- `history` — история диалога в формате `[{"role": "user", "content": "..."}, ...]`

**Returns:**
- `GenerationResult` с полями:
  - `text: str` — сгенерированный текст
  - `model: str` — использованная модель
  - `input_tokens: int` — количество токенов в промпте
  - `output_tokens: int` — количество токенов в ответе
  - `finish_reason: str` — причина остановки ("stop", "length", "error")

**Raises:**
- `ValueError` — если prompt пустой
- `RuntimeError` — если API недоступен

**Example:**
```python
from semantic_core.infrastructure.llm import GeminiLLMProvider

llm = GeminiLLMProvider(api_key="key", model="gemini-2.0-flash")

result = llm.generate(
    prompt="Что такое семантический поиск?",
    system_prompt="Ты эксперт по поисковым системам",
    temperature=0.7,
    max_tokens=500
)

print(result.text)  # Ответ модели
print(f"Tokens: {result.input_tokens} in, {result.output_tokens} out")
```

### Реализации

| Класс | Provider | Models | Context Window |
|-------|----------|--------|----------------|
| `GeminiLLMProvider` | Google Gemini | `gemini-2.0-flash-exp`, `gemini-1.5-pro` | 1M tokens |
| `OpenAILLMProvider` | OpenAI | `gpt-4o`, `gpt-4o-mini` | 128K tokens |
| `OllamaLLMProvider` | Ollama (local) | `llama3`, `mistral`, etc. | Varies |

**См. также:**
- [Custom LLM Provider Guide](../guides/extending/custom-llm-provider.md)
- [RAG Engine](../concepts/09_rag.md)

---

## BaseSplitter ✂️

| Метод | Сигнатура | Описание |
|-------|-----------|----------|
| `split` | `(document: Document) → list[Chunk]` | Разбить на чанки |

**Реализации**: `SimpleSplitter`, `SmartSplitter`

**Концепт**: [Chunking](../concepts/04_chunking.md)

---

## BaseContextStrategy 📝

| Метод | Сигнатура | Описание |
|-------|-----------|----------|
| `form_vector_text` | `(chunk, document) → str` | Сформировать текст для эмбеддинга |

**Реализации**: `BasicContextStrategy`, `HierarchicalContextStrategy`

**Концепт**: [Smart Parsing](../concepts/05_smart_parsing.md)

---

## DocumentParser 📄

**Protocol** (duck typing, не ABC):

| Метод | Сигнатура | Описание |
|-------|-----------|----------|
| `parse` | `(content: str) → list[ParsingSegment]` | Парсинг в сегменты |

**DTO**: `ParsingSegment(text, segment_type, metadata, level, ...)`

**Реализации**: `MarkdownNodeParser`

---

## BaseChatHistoryStrategy 💬

| Метод | Сигнатура | Описание |
|-------|-----------|----------|
| `should_trim` | `(messages) → bool` | Нужна ли обрезка |
| `trim` | `(messages) → list[ChatMessage]` | Обрезать историю |

**DTO**: `ChatMessage(role, content, tokens)`

**Реализации**: `LastNMessages`, `TokenBudget`, `Unlimited`, `AdaptiveWithCompression`

---

## DTOs (Data Transfer Objects) 📦

| DTO | Поля | Используется |
|-----|------|--------------|
| `Document` | content, metadata, media_type | Весь pipeline |
| `Chunk` | text, chunk_type, embedding, ... | Splitter → Store |
| `SearchResult` | document, score, match_type | Store → API |
| `ChunkResult` | content, score, chunk_type, ... | Granular search |
| `GenerationResult` | text, model, tokens | LLM → RAG |
| `ChatMessage` | role, content, tokens | Chat history |
| `ParsingSegment` | text, segment_type, level | Parser → Splitter |

---

## Связанные темы 🔗

| Ресурс | Описание |
|--------|----------|
| [Plugin System](../concepts/10_plugin_system.md) | Архитектура расширений |
| [Extending Guides](../guides/extending/) | Гайды по реализации |
