# 🎬 Multi-Chunk Media Architecture: От монолита к потоку

> **Phase 14.0 Implementation:** Как превратить 1 медиафайл в дерево семантических чанков

---

## 📋 Содержание

1. [Проблема монолитного чанка](#проблема-монолитного-чанка)
2. [Новая архитектура](#новая-архитектура)
3. [Реализация](#реализация)
4. [Конфигурируемость](#конфигурируемость)
5. [Примеры](#примеры)

---

## Проблема монолитного чанка

### Старая модель (до Phase 14.0)

```
Audio File (3 min)
    ↓
Gemini API → {description, transcription}
    ↓
CREATE CHUNK:
  - content = description + transcription  (6000 chars)
  - chunk_type = AUDIO_REF
  - chunk_index = 0
    ↓
SAVE TO DB → 1 row in chunks table
```

**Проблемы:**

1. **Embedding truncation**: 6000 символов → только первые ~2000 попадают в вектор
2. **Search granularity**: Невозможно найти фразу из конца транскрипции
3. **UI performance**: 6000 символов текста в одной карточке
4. **No structure**: Нет разделения на "о чём файл" vs "что сказано"

---

## Новая архитектура

### Multi-Chunk Model (Phase 14.0+)

```
Audio File (3 min)
    ↓
Gemini API → {description, transcription}
    ↓
BUILD CHUNKS:
  1. Summary chunk:
     - content = description (500 chars)
     - chunk_type = AUDIO_REF
     - chunk_index = 0
     - metadata.role = "summary"
  
  2. Split transcription:
     transcription (5500 chars) → SmartSplitter
       ↓
     [chunk1, chunk2, chunk3, chunk4]
     
  3. Transcript chunks:
     - content = chunk1.content (1800 chars)
     - chunk_type = TEXT
     - chunk_index = 1
     - metadata.role = "transcript"
     
     - content = chunk2.content (1800 chars)
     - chunk_type = TEXT
     - chunk_index = 2
     - metadata.role = "transcript"
     
     [...]
    ↓
SAVE TO DB → 5 rows in chunks table
```

---

## Реализация

### Компоненты системы

#### 1. `_build_media_chunks()` — Оркестратор

**Файл:** `semantic_core/pipeline.py`

```python
def _build_media_chunks(
    self,
    document: Document,
    media_path: Path,
    chunk_type: ChunkType,
    analysis: Optional[dict],
    fallback_metadata: Optional[dict] = None,
) -> list[Chunk]:
    """Формирует список чанков для медиа: summary + transcript."""
    
    base_metadata = dict(fallback_metadata or {})

    # Если анализа нет — возвращаем fallback чанк с путём
    if analysis is None:
        return [
            Chunk(
                content=str(media_path),
                chunk_index=0,
                chunk_type=chunk_type,
                metadata=base_metadata,
            )
        ]

    # 1. Создаём summary chunk
    summary_content = self._build_content_from_analysis(analysis)
    summary_metadata = self._build_metadata_from_analysis(analysis, media_path)
    summary_metadata.update(base_metadata)
    summary_metadata["role"] = "summary"

    chunks: list[Chunk] = [
        Chunk(
            content=summary_content,
            chunk_index=0,
            chunk_type=chunk_type,
            metadata=summary_metadata,
        )
    ]

    # 2. Если есть транскрипция — режем на чанки
    transcription = analysis.get("transcription")
    if transcription:
        transcript_chunks = self._split_transcription_into_chunks(
            transcription=transcription,
            base_index=len(chunks),
            media_path=media_path,
        )
        chunks.extend(transcript_chunks)

    return chunks
```

**Ключевые моменты:**

- ✅ **Fallback**: Если анализ провалился — создаём чанк с путём (не теряем файл!)
- ✅ **Role separation**: summary chunk ≠ transcript chunks (разная семантика)
- ✅ **Index continuity**: transcript chunks начинаются с `base_index=1`

#### 2. `_split_transcription_into_chunks()` — Резка текста

```python
def _split_transcription_into_chunks(
    self,
    transcription: str,
    base_index: int,
    media_path: Path,
) -> list[Chunk]:
    """Режет транскрипцию на чанки через splitter."""

    # Создаём виртуальный документ для сплиттера
    temp_doc = Document(
        content=transcription,
        metadata={"source": str(media_path)},
        media_type=MediaType.TEXT,
    )
    
    # Режем через SmartSplitter (учёт параграфов, предложений)
    split_chunks = self.splitter.split(temp_doc)

    # Обогащаем метаданные
    transcript_chunks: list[Chunk] = []
    for idx, chunk in enumerate(split_chunks):
        meta = dict(chunk.metadata or {})
        meta.setdefault("_original_path", str(media_path))
        meta["role"] = "transcript"
        meta["parent_media_path"] = str(media_path)

        chunk.chunk_index = base_index + idx
        chunk.metadata = meta

        transcript_chunks.append(chunk)

    return transcript_chunks
```

**Почему через SmartSplitter?**

- ✅ **Intelligent splitting**: Разрезает по предложениям, а не по символам
- ✅ **Reuse logic**: Та же логика что для Markdown текста
- ✅ **Configurable**: `chunk_size` читается из конфига

#### 3. `_build_content_from_analysis()` — Summary extraction

```python
def _build_content_from_analysis(self, result: dict) -> str:
    """Формирует контент для SUMMARY чанка.
    
    Для audio/video возвращает ТОЛЬКО description (без transcription).
    Transcription будет в отдельных чанках.
    """
    media_type = result.get("type", "unknown")

    if media_type == "image":
        return result.get("description", "")

    elif media_type == "audio":
        return result.get("description", "")

    elif media_type == "video":
        return result.get("description", "")

    return ""
```

**Критично:** Раньше здесь был `description + transcription` → дублирование! Теперь summary = только краткое описание.

---

## Конфигурируемость

### SemanticConfig расширения (Phase 14.0)

**Файл:** `semantic_core/config.py`

```python
class SemanticConfig(BaseSettings):
    # === Processing ===
    chunk_size: int = Field(
        default=1800,
        ge=500,
        le=8000,
        description="Размер текстового чанка в символах",
    )

    code_chunk_size: int = Field(
        default=2000,
        ge=500,
        le=10000,
        description="Размер чанка кода в символах",
    )

    # === Media ===
    max_output_tokens: int = Field(
        default=65_536,
        ge=1024,
        le=65_536,
        description="Лимит токенов для Gemini (image/audio/video)",
    )
```

### semantic.toml

```toml
[processing]
chunk_size = 1800            # Размер текстового чанка
code_chunk_size = 2000       # Размер чанка кода

[media]
max_output_tokens = 65536    # Лимит output для анализа
```

### Интеграция в компоненты

**CLI:** `semantic_core/cli/context.py`

```python
# SmartSplitter читает из config
splitter = SmartSplitter(
    parser=parser,
    chunk_size=config.chunk_size,
    code_chunk_size=config.code_chunk_size,
)

# Media analyzers читают max_output_tokens
image_analyzer = GeminiImageAnalyzer(
    api_key=api_key,
    max_output_tokens=config.max_output_tokens,
)
audio_analyzer = GeminiAudioAnalyzer(
    api_key=api_key,
    max_output_tokens=config.max_output_tokens,
)
video_analyzer = GeminiVideoAnalyzer(
    api_key=api_key,
    max_output_tokens=config.max_output_tokens,
)
```

**Flask App:** `examples/flask_app/app/extensions.py` — аналогично

---

## Примеры

### Пример 1: 3-минутное аудио

**Input:**
```python
core.ingest_audio("new_year_greeting.mp3", mode="sync")
```

**Gemini API Response:**
```json
{
  "description": "New Year greeting from Santa Claus in Russian",
  "transcription": "Привет! Я Дед Мороз... [5500 символов]...",
  "keywords": ["новый год", "санта", "поздравление"],
  "duration_seconds": 180
}
```

**Созданные чанки:**

```python
# Chunk 0: Summary (AUDIO_REF)
Chunk(
    content="New Year greeting from Santa Claus in Russian",
    chunk_type=ChunkType.AUDIO_REF,
    chunk_index=0,
    metadata={
        "role": "summary",
        "duration_seconds": 180,
        "keywords": ["новый год", "санта", "поздравление"],
        "source": "new_year_greeting.mp3",
    }
)

# Chunk 1: Transcript part 1 (TEXT)
Chunk(
    content="Привет! Я Дед Мороз. Сегодня я хочу... [1800 chars]",
    chunk_type=ChunkType.TEXT,
    chunk_index=1,
    metadata={
        "role": "transcript",
        "parent_media_path": "new_year_greeting.mp3",
    }
)

# Chunk 2: Transcript part 2 (TEXT)
Chunk(
    content="...поздравить всех с Новым Годом... [1800 chars]",
    chunk_type=ChunkType.TEXT,
    chunk_index=2,
    metadata={
        "role": "transcript",
        "parent_media_path": "new_year_greeting.mp3",
    }
)

# Chunk 3: Transcript part 3 (TEXT)
Chunk(
    content="...желаю счастья, здоровья и успехов! [1900 chars]",
    chunk_type=ChunkType.TEXT,
    chunk_index=3,
    metadata={
        "role": "transcript",
        "parent_media_path": "new_year_greeting.mp3",
    }
)
```

**SQL Result:**
```sql
SELECT id, chunk_index, chunk_type, LENGTH(content), metadata->>'role'
FROM chunks
WHERE document_id = 42;

-- id | chunk_index | chunk_type | length | role
-- 100 | 0          | audio_ref  | 45     | summary
-- 101 | 1          | text       | 1800   | transcript
-- 102 | 2          | text       | 1800   | transcript
-- 103 | 3          | text       | 1900   | transcript
```

### Пример 2: Изображение (без транскрипции)

**Input:**
```python
core.ingest_image("architecture_diagram.png", mode="sync")
```

**Gemini API Response:**
```json
{
  "description": "Software architecture diagram showing...",
  "ocr_text": "Client → API → Database",
  "keywords": ["architecture", "API", "database"],
  "transcription": null  # ← НЕТ ТРАНСКРИПЦИИ
}
```

**Созданные чанки:**

```python
# Chunk 0: Summary (IMAGE_REF) — ЕДИНСТВЕННЫЙ ЧАНК
Chunk(
    content="Software architecture diagram showing...",
    chunk_type=ChunkType.IMAGE_REF,
    chunk_index=0,
    metadata={
        "role": "summary",
        "ocr_text": "Client → API → Database",
        "keywords": ["architecture", "API", "database"],
    }
)
```

**SQL Result:**
```sql
SELECT id, chunk_index, chunk_type, LENGTH(content)
FROM chunks
WHERE document_id = 43;

-- id | chunk_index | chunk_type | length
-- 104 | 0          | image_ref  | 250
```

---

## Метрики улучшения

### Storage efficiency

**До Phase 14.0:**
```
1 audio file → 1 chunk (2000 chars) → 1 embedding
```

**После Phase 14.0:**
```
1 audio file → 4 chunks (5500 chars total) → 4 embeddings
```

**Trade-off:**
- ➕ **100% coverage**: Весь контент в БД
- ➕ **Granular search**: Находятся фразы из любой части
- ➖ **4x embeddings**: Больше API-вызовов (но async batch компенсирует)
- ➖ **+3 rows**: Увеличение размера БД (но marginal — TEXT индексируется в FTS)

### Search precision

**Запрос:** "поздравления с новым годом"

**До:**
```sql
-- Поиск только по summary chunk
SELECT * FROM chunks_vec
WHERE distance < 0.5
AND chunk_type = 'audio_ref'
LIMIT 10;

-- Результат: 1 match (summary упоминает "новый год")
-- Проблема: Фраза "поздравляю с Новым Годом" в середине транскрипции НЕ НАЙДЕНА
```

**После:**
```sql
-- Поиск по всем чанкам (summary + transcripts)
SELECT * FROM chunks_vec
WHERE distance < 0.5
LIMIT 10;

-- Результат: 3 matches
--   - summary chunk (distance=0.3)
--   - transcript chunk 1 (distance=0.45)
--   - transcript chunk 3 (distance=0.25) ← ТОЧНОЕ СОВПАДЕНИЕ ФРАЗЫ
```

---

## Backward Compatibility

### Старые документы

**Что происходит с чанками, созданными до Phase 14.0?**

✅ **Продолжают работать!** Система gracefully деградирует:

```python
# Старый чанк (Phase 6-13):
Chunk(
    content="Description + transcription...",
    chunk_type=ChunkType.AUDIO_REF,
    metadata={}  # ← НЕТ ПОЛЯ "role"
)

# Поиск работает:
results = core.search_chunks("поздравление")
# → Находит старый чанк по полному контенту
```

**Нет breaking changes** — новая архитектура расширяет, а не заменяет старую.

### Миграция (опционально)

Если нужно переиндексировать старые файлы:

```python
# Flask App: кнопка "Reindex" на каждом документе
# → DELETE старые чанки
# → ingest_audio() заново
# → Создаются multi-chunk структуры
```

---

## Уроки архитектуры

### Что сделали правильно

1. **Separation of Concerns**: `_build_media_chunks()` не знает про Gemini API
2. **Reuse**: SmartSplitter работает и для Markdown, и для транскрипций
3. **Config-driven**: chunk_size легко менять без правки кода
4. **Metadata richness**: `role="summary"` vs `role="transcript"` → семантическая разница

### Что можно улучшить

1. **Timestamp mapping**: Сейчас transcript chunks не привязаны к временным отметкам видео
2. **Hierarchical structure**: Нет parent_id между summary и transcript chunks
3. **Deduplication**: Если description дублирует начало transcription → лишний embedding

---

**← [Назад: Media Content Truncation Crisis](71_media_content_truncation_crisis.md)** | **[Назад к каталогу](00_overview.md)**
