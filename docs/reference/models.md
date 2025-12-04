---
title: Модели данных (DTO)
description: Справочник Data Transfer Objects в Semantic Core
tags: [reference, dto, models, dataclass]
---

# Модели данных (DTO) 📦

Справочник Data Transfer Objects — чистые dataclass без привязки к ORM.

## Обзор моделей 📊

| Модуль                | Класс                 | Назначение                    |
| :-------------------- | :-------------------- | :---------------------------- |
| `domain.document`     | `Document`            | Родительский документ         |
| `domain.document`     | `MediaType`           | Тип контента документа        |
| `domain.chunk`        | `Chunk`               | Фрагмент документа            |
| `domain.chunk`        | `ChunkType`           | Тип контента чанка            |
| `domain.search_result`| `SearchResult`        | Результат поиска (документ)   |
| `domain.search_result`| `ChunkResult`         | Результат поиска (чанк)       |
| `domain.search_result`| `MatchType`           | Тип совпадения                |
| `domain.media`        | `MediaAnalysisResult` | Результат анализа медиа       |
| `domain.media`        | `TaskStatus`          | Статус задачи                 |
| `interfaces.llm`      | `GenerationResult`    | Результат LLM генерации       |
| `interfaces.chat`     | `ChatMessage`         | Сообщение в чате              |
| `core.rag`            | `RAGResult`           | Результат RAG-запроса         |

## Document 📄

```python
from semantic_core.domain import Document, MediaType

doc = Document(
    content="# Title\nText...",
    metadata={"title": "Doc", "author": "User"},
    media_type=MediaType.TEXT,
)
```

| Поле         | Тип              | Описание                  |
| :----------- | :--------------- | :------------------------ |
| `content`    | `str`            | Текст или путь к файлу    |
| `metadata`   | `dict[str, Any]` | Метаданные                |
| `media_type` | `MediaType`      | TEXT/IMAGE/VIDEO/AUDIO    |
| `id`         | `int \| None`    | ID после сохранения       |
| `created_at` | `datetime`       | Дата создания             |

## Chunk 🧩

```python
from semantic_core.domain import Chunk, ChunkType

chunk = Chunk(
    content="Текст фрагмента",
    chunk_index=0,
    chunk_type=ChunkType.TEXT,
    metadata={"headers": ["H1", "H2"]},
)
```

| Поле            | Тип              | Описание                  |
| :-------------- | :--------------- | :------------------------ |
| `content`       | `str`            | Текст фрагмента           |
| `chunk_index`   | `int`            | Индекс в документе        |
| `chunk_type`    | `ChunkType`      | TEXT/CODE/TABLE/...       |
| `language`      | `str \| None`    | Язык (для CODE)           |
| `embedding`     | `ndarray \| None`| Вектор                    |
| `parent_doc_id` | `int \| None`    | ID родителя               |
| `metadata`      | `dict[str, Any]` | headers, start_line...    |

## SearchResult 🔍

```python
from semantic_core.domain import SearchResult, MatchType

result = SearchResult(
    document=doc,
    score=0.85,
    match_type=MatchType.HYBRID,
)
```

| Поле         | Тип           | Описание              |
| :----------- | :------------ | :-------------------- |
| `document`   | `Document`    | Найденный документ    |
| `score`      | `float`       | Релевантность         |
| `match_type` | `MatchType`   | VECTOR/FTS/HYBRID     |
| `chunk_id`   | `int \| None` | ID совпавшего чанка   |
| `highlight`  | `str \| None` | Подсветка (FTS)       |

## ChunkResult 🎯

```python
from semantic_core.domain import ChunkResult

result = ChunkResult(
    chunk=chunk,
    score=0.92,
    match_type=MatchType.VECTOR,
    parent_doc_id=1,
    parent_doc_title="README",
)
```

| Поле               | Тип              | Описание              |
| :----------------- | :--------------- | :-------------------- |
| `chunk`            | `Chunk`          | Найденный чанк        |
| `score`            | `float`          | Релевантность         |
| `match_type`       | `MatchType`      | VECTOR/FTS/HYBRID     |
| `parent_doc_id`    | `int`            | ID документа          |
| `parent_doc_title` | `str \| None`    | Заголовок документа   |
| `parent_metadata`  | `dict \| None`   | Метаданные документа  |

**Properties:** `chunk_id`, `chunk_index`, `chunk_type`, `language`, `content`

## MediaAnalysisResult 🎬

```python
from semantic_core.domain.media import MediaAnalysisResult

result = MediaAnalysisResult(
    description="Диаграмма архитектуры системы",
    alt_text="Architecture diagram",
    keywords=["architecture", "diagram"],
    transcription="...",  # для аудио/видео
)
```

| Поле               | Тип           | Описание                |
| :----------------- | :------------ | :---------------------- |
| `description`      | `str`         | Полное описание         |
| `alt_text`         | `str \| None` | Alt-текст               |
| `keywords`         | `list[str]`   | Ключевые слова          |
| `ocr_text`         | `str \| None` | OCR (изображения)       |
| `transcription`    | `str \| None` | Транскрипция            |
| `participants`     | `list[str]`   | Спикеры                 |
| `action_items`     | `list[str]`   | Задачи из контента      |
| `duration_seconds` | `float\|None` | Длительность            |
| `tokens_used`      | `int \| None` | Использовано токенов    |

## GenerationResult 🤖

```python
from semantic_core.interfaces.llm import GenerationResult

result = GenerationResult(
    text="Ответ модели...",
    model="gemini-2.5-flash",
    input_tokens=100,
    output_tokens=50,
)
```

| Поле            | Тип           | Описание              |
| :-------------- | :------------ | :-------------------- |
| `text`          | `str`         | Сгенерированный текст |
| `model`         | `str`         | Модель                |
| `input_tokens`  | `int \| None` | Входные токены        |
| `output_tokens` | `int \| None` | Выходные токены       |
| `finish_reason` | `str \| None` | Причина остановки     |

**Property:** `total_tokens` — сумма input + output

## ChatMessage 💬

```python
from semantic_core.interfaces.chat_history import ChatMessage

msg = ChatMessage(
    role="user",
    content="Что такое эмбеддинги?",
    tokens=10,
)
```

| Поле      | Тип                              | Описание          |
| :-------- | :------------------------------- | :---------------- |
| `role`    | `user \| assistant \| system`    | Роль отправителя  |
| `content` | `str`                            | Текст сообщения   |
| `tokens`  | `int`                            | Количество токенов|

## RAGResult 📚

```python
from semantic_core.core.rag import RAGResult

result = RAGResult(
    answer="Эмбеддинги — это...",
    sources=[chunk_result1, chunk_result2],
    generation=gen_result,
    query="Что такое эмбеддинги?",
)
```

| Поле         | Тип                    | Описание                |
| :----------- | :--------------------- | :---------------------- |
| `answer`     | `str`                  | Ответ LLM               |
| `sources`    | `list[ChunkResult]`    | Найденные источники     |
| `generation` | `GenerationResult`     | Метаданные генерации    |
| `query`      | `str`                  | Исходный запрос         |
| `full_docs`  | `bool`                 | Полные документы?       |

**Properties:** `has_sources`, `total_tokens`

## См. также 🔗

- [Типы чанков](chunk-types.md) — подробнее о ChunkType
- [Интерфейсы](interfaces.md) — абстрактные классы
