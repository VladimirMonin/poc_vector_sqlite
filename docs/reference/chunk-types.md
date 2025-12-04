---
title: Типы чанков
description: Справочник ChunkType enum и рекомендации по обработке
tags: [reference, chunk, types, media]
---

# Типы чанков 🧩

Справочник `ChunkType` enum — классификация контента в чанках.

## Обзор ChunkType 📊

```python
from semantic_core.domain.chunk import ChunkType
```

| Значение     | Описание                  | Медиа? | Требует анализа? |
| :----------- | :------------------------ | :----: | :--------------: |
| `TEXT`       | Обычный текст             |   ❌   |        ❌        |
| `CODE`       | Блок кода                 |   ❌   |        ❌        |
| `TABLE`      | Таблица (Markdown/HTML)   |   ❌   |        ❌        |
| `IMAGE_REF`  | Ссылка на изображение     |   ✅   |        ✅        |
| `AUDIO_REF`  | Ссылка на аудиофайл       |   ✅   |        ✅        |
| `VIDEO_REF`  | Ссылка на видеофайл       |   ✅   |        ✅        |

## Текстовые типы 📝

### TEXT

Обычный текстовый контент — параграфы, списки, цитаты.

```python
chunk = Chunk(
    content="Semantic Core — библиотека для локального поиска.",
    chunk_type=ChunkType.TEXT,
    chunk_index=0,
)
```

### CODE

Блоки кода с указанием языка программирования.

```python
chunk = Chunk(
    content="def hello():\n    print('Hello')",
    chunk_type=ChunkType.CODE,
    language="python",  # язык программирования
    chunk_index=1,
)
```

**Поле `language`:** Заполняется при CODE типе из fence-блока Markdown.

### TABLE

Таблицы в формате Markdown или HTML.

```python
chunk = Chunk(
    content="| A | B |\n|---|---|\n| 1 | 2 |",
    chunk_type=ChunkType.TABLE,
    chunk_index=2,
)
```

## Медиа типы 🖼️

Медиа-чанки содержат путь к файлу, а не сам контент.

### IMAGE_REF

Ссылка на изображение для Vision API анализа.

```python
chunk = Chunk(
    content="assets/diagram.png",  # путь к файлу
    chunk_type=ChunkType.IMAGE_REF,
    chunk_index=3,
    metadata={
        "alt": "Диаграмма архитектуры",
        "original_path": "![Alt](assets/diagram.png)",
    },
)
```

### AUDIO_REF

Ссылка на аудиофайл для Audio API транскрипции.

```python
chunk = Chunk(
    content="media/podcast.mp3",
    chunk_type=ChunkType.AUDIO_REF,
    chunk_index=4,
    metadata={
        "duration": 1800,  # секунды
    },
)
```

### VIDEO_REF

Ссылка на видеофайл для мультимодального анализа.

```python
chunk = Chunk(
    content="media/tutorial.mp4",
    chunk_type=ChunkType.VIDEO_REF,
    chunk_index=5,
    metadata={
        "duration": 600,
        "fps": 30,
    },
)
```

## Проверка медиа-типов 🔍

```python
from semantic_core.domain.chunk import MEDIA_CHUNK_TYPES, ChunkType

chunk_type = ChunkType.IMAGE_REF

# Проверка через frozenset
if chunk_type in MEDIA_CHUNK_TYPES:
    print("Это медиа-чанк, требуется анализ")

# MEDIA_CHUNK_TYPES содержит:
# - ChunkType.IMAGE_REF
# - ChunkType.AUDIO_REF
# - ChunkType.VIDEO_REF
```

## Метаданные по типам 📋

Рекомендуемые ключи `metadata` для каждого типа:

| Тип          | Ключи metadata                                  |
| :----------- | :---------------------------------------------- |
| `TEXT`       | `headers`, `start_line`, `end_line`             |
| `CODE`       | `headers`, `start_line`, `end_line`             |
| `TABLE`      | `headers`, `rows_count`, `cols_count`           |
| `IMAGE_REF`  | `alt`, `original_path`, `width`, `height`       |
| `AUDIO_REF`  | `duration`, `format`, `sample_rate`             |
| `VIDEO_REF`  | `duration`, `fps`, `resolution`, `has_audio`    |

## Жизненный цикл медиа-чанков 🔄

```
┌──────────────────┐
│   Markdown AST   │
│   Парсинг        │
└────────┬─────────┘
         │ Обнаружен ![alt](path)
         ▼
┌──────────────────┐
│  IMAGE_REF чанк  │
│  content = path  │
└────────┬─────────┘
         │ MediaQueueProcessor
         ▼
┌──────────────────┐
│  Vision API      │
│  Анализ          │
└────────┬─────────┘
         │ Результат
         ▼
┌──────────────────┐
│  TEXT чанк       │
│  Описание        │
│  + embedding     │
└──────────────────┘
```

## Пример полного документа 📄

```python
from semantic_core.domain import Document, Chunk, ChunkType

doc = Document(
    title="README",
    source="README.md",
    content="...",
    chunks=[
        # Заголовок
        Chunk(
            content="# Semantic Core",
            chunk_type=ChunkType.TEXT,
            chunk_index=0,
            metadata={"headers": ["Semantic Core"]},
        ),
        # Код
        Chunk(
            content="pip install semantic-core",
            chunk_type=ChunkType.CODE,
            language="bash",
            chunk_index=1,
        ),
        # Изображение (до анализа)
        Chunk(
            content="docs/architecture.png",
            chunk_type=ChunkType.IMAGE_REF,
            chunk_index=2,
            metadata={"alt": "Architecture diagram"},
        ),
    ],
)
```

## См. также 🔗

- [Обработка медиа](../guides/core/media-processing.md) — работа с медиа-файлами
- [Интерфейсы](interfaces.md) — BaseSplitter создаёт чанки
- [Модели](models.md) — DTO для Document и Chunk
