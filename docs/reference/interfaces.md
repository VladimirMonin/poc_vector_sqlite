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

| Метод | Сигнатура | Описание |
|-------|-----------|----------|
| `embed_documents` | `(texts: list[str]) → list[np.ndarray]` | Векторизация документов |
| `embed_query` | `(text: str) → np.ndarray` | Векторизация запроса |

**Реализации**: `GeminiEmbedder`

**Гайд**: [Custom Embedder](../guides/extending/custom-embedder.md)

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

| Метод | Сигнатура | Описание |
|-------|-----------|----------|
| `generate` | `(prompt, system_prompt, temperature, max_tokens, history) → GenerationResult` | Генерация ответа |
| `model_name` | `@property → str` | Название модели |

**DTO**: `GenerationResult(text, model, input_tokens, output_tokens, finish_reason)`

**Реализации**: `GeminiLLMProvider`

**Гайд**: [Custom LLM Provider](../guides/extending/custom-llm-provider.md)

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
