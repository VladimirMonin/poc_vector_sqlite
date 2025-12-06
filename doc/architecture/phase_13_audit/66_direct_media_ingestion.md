# 66. Direct Media Ingestion: Исправляем маршрутизацию

> **Эпизод 66**: Как прямая загрузка медиа-файлов ломала весь pipeline — и как мы это починили

---

## 🎬 Предыстория

После Phase 13.2 (ручное тестирование) обнаружилась критическая проблема: при загрузке медиа-файлов напрямую (не через Markdown) API Gemini Vision/Audio/Video **никогда не вызывался**.

```
📊 До фикса (БД):
Документы: audio=3, image=9, video=2  ✅ (типы верные)
Чанки:     code=13, text=29            ❌ (ни одного media chunk!)
           image_ref=0, audio_ref=0, video_ref=0
```

Проблема: 14 медиа-файлов загружены, но 0 чанков типа `*_ref`.

---

## 🔍 Расследование

### Как работал pipeline до фикса

```
                      ┌──────────────────┐
     cat.jpg ───────▶ │ SemanticCore     │
                      │  .ingest()       │
                      └────────┬─────────┘
                               │
                               ▼
                      ┌──────────────────┐
                      │ SmartSplitter    │
                      │  .split(doc)     │
                      └────────┬─────────┘
                               │
          doc.content = "C:/path/cat.jpg"  ← строка пути!
                               │
                               ▼
          chunk_type = TEXT  ← потому что это текст
                               │
                               ▼
                      ┌──────────────────┐
                      │ _enrich_media_   │
                      │   chunks()       │
                      └────────┬─────────┘
                               │
          if chunk.chunk_type in [IMAGE_REF, AUDIO_REF, VIDEO_REF]:
              # НИКОГДА НЕ ВЫПОЛНЯЕТСЯ!
              # chunk_type = TEXT, не IMAGE_REF
```

### Root Cause

1. CLI создаёт `Document(media_type=IMAGE, content=path)` ✅
2. `SmartSplitter.split()` парсит `content` как текст
3. Поскольку путь — это строка, создаётся чанк `chunk_type=TEXT`
4. `_enrich_media_chunks()` проверяет `chunk_type`, видит `TEXT` → skip
5. Vision API **никогда не вызывается**

---

## 💡 Решение: Direct Media Path

Добавляем новый маршрут **ДО** SmartSplitter:

```python
def ingest(self, document: Document, ...) -> Document:
    # 🆕 Прямой путь для медиа-файлов
    if document.media_type in (MediaType.IMAGE, MediaType.AUDIO, MediaType.VIDEO):
        return self._ingest_direct_media(document, mode, enrich_media)
    
    # Обычный путь через парсер/сплиттер
    chunks = self.splitter.split(document)
    ...
```

### Новый метод: `_ingest_direct_media()`

```python
def _ingest_direct_media(
    self, 
    document: Document, 
    mode: str, 
    enrich_media: bool
) -> Document:
    """Прямой путь для медиа-файлов: один файл = один чанк."""
    
    # 1. Маппинг MediaType → ChunkType
    chunk_type_map = {
        MediaType.IMAGE: ChunkType.IMAGE_REF,
        MediaType.AUDIO: ChunkType.AUDIO_REF,
        MediaType.VIDEO: ChunkType.VIDEO_REF,
    }
    chunk_type = chunk_type_map[document.media_type]
    
    # 2. Путь к файлу
    media_path = Path(document.content)
    
    # 3. Анализ через Gemini API (если enrich_media=True)
    content = str(media_path)
    metadata = {}
    if enrich_media:
        result = self._analyze_media_for_chunk(
            chunk_type, media_path, context_text=""
        )
        if result:
            content = self._build_content_from_analysis(result)
            metadata = self._build_metadata_from_analysis(result)
    
    # 4. Создание чанка правильного типа
    chunk = Chunk(
        id=f"chunk-0",
        content=content,
        chunk_type=chunk_type,  # ← IMAGE_REF, не TEXT!
        metadata=metadata,
        position=0,
    )
    
    # 5. Embedding + Save
    vector_text = self.context_strategy.form_vector_text(chunk, document)
    embeddings = self.embedder.embed_documents([vector_text])
    chunk.embedding = embeddings[0]
    
    return self.store.save(document, [chunk])
```

---

## 🧩 Архитектурное решение

### До фикса: единый путь

```
┌─────────────┐     ┌───────────┐     ┌─────────────┐
│  Document   │────▶│ Splitter  │────▶│  Enricher   │
│ (любой тип) │     │           │     │ (по типу)   │
└─────────────┘     └───────────┘     └─────────────┘
                         ▲
                         │
              Текстовый путь тоже!
              path = "cat.jpg" → TEXT
```

### После фикса: развилка на входе

```
┌─────────────┐
│  Document   │
│ media_type? │
└──────┬──────┘
       │
   ┌───┴───┐
   │       │
   ▼       ▼
 TEXT    MEDIA (IMAGE/AUDIO/VIDEO)
   │       │
   ▼       ▼
┌──────┐  ┌──────────────────────┐
│Split │  │ _ingest_direct_media │
│Parse │  │ - ChunkType mapping  │
│Enrich│  │ - Gemini API call    │
└──────┘  │ - Single chunk       │
          └──────────────────────┘
```

---

## 📦 Результат анализа медиа

### Image (Vision API)

```python
# Gemini анализирует изображение
content = "This image features a detailed close-up of a tabby cat's 
face, with its bright green eyes sharply in focus. The warm, golden 
light of sunset illuminates the cat's fur and whiskers..."
```

### Audio (Audio API)

```python
# Gemini транскрибирует аудио
content = "Поздравляю с наступающим Новым годом. Желаю в новом году 
здоровья, самое главное, успехов во всех начинаниях, чтобы задуманные 
планы сбывались, мечты воплощались. С наступающим Новым годом."
```

### Video (Multimodal: Frames + Audio)

```python
# Gemini анализирует кадры + транскрибирует аудио + OCR кода
content = """The video displays Python code for a VectorDatabase class 
that extends SQLite with vector search capabilities...

Transcription:
Проверим модуль инициализации базы данных с поддержкой sqlite-vec...

import sqlite3
from pathlib import Path
class VectorDatabase(SqliteExtDatabase):
    ...
"""
```

---

## ✅ Верификация

```bash
# До фикса
CHUNKS: [('code', 13), ('text', 29)]

# После фикса
CHUNKS: [
    ('audio_ref', 3),   # ✅ 3 аудио файла
    ('code', 13),       # Из Markdown
    ('image_ref', 9),   # ✅ 9 изображений  
    ('text', 15),       # Из Markdown (меньше, т.к. медиа ушло)
    ('video_ref', 2)    # ✅ 2 видео файла
]
```

### Тест поиска

```bash
semantic search "VectorDatabase класс"

# Результат:
┃ 1 │ 0.016 │ module_init_demo.mp4 │ ...
```

Видео найдено по запросу, потому что транскрипция содержит код `VectorDatabase`!

---

## 🎓 Уроки

### 1. Разные типы требуют разных путей

Текстовый контент и медиа-файлы имеют **принципиально разные** пути обработки. Попытка провести их через один pipeline ломает логику.

### 2. Проверяй тип на входе

```python
# ❌ Плохо: проверка типа чанка в конце
def _enrich_media_chunks(self, chunks):
    for chunk in chunks:
        if chunk.chunk_type in [IMAGE_REF, ...]:  # Уже поздно!
            ...

# ✅ Хорошо: проверка типа документа на входе
def ingest(self, document):
    if document.media_type in [IMAGE, AUDIO, VIDEO]:  # Сразу развилка
        return self._ingest_direct_media(document)
```

### 3. БД — источник правды

Тестирование через SQLite напрямую выявило баг, который не видно в логах:

```python
# Быстрая проверка
SELECT chunk_type, COUNT(*) FROM chunks GROUP BY chunk_type;
# Сразу видно: 0 media chunks = проблема
```

---

## 📊 Диаграмма изменений

```
┌─────────────────────────────────────────────────────────────┐
│                    pipeline.py                              │
├─────────────────────────────────────────────────────────────┤
│ BEFORE:                                                     │
│   ingest() → splitter.split() → _enrich_media_chunks()     │
│                     ↓                                       │
│          path as text → TEXT chunk → skip enrichment       │
├─────────────────────────────────────────────────────────────┤
│ AFTER:                                                      │
│   ingest()                                                  │
│      │                                                      │
│      ├── if media_type in [IMAGE, AUDIO, VIDEO]:           │
│      │       → _ingest_direct_media()                      │
│      │           → chunk_type = IMAGE_REF/AUDIO_REF/VIDEO_REF│
│      │           → Gemini API call                         │
│      │           → rich content in chunk                   │
│      │                                                      │
│      └── else (text):                                       │
│              → splitter.split()                            │
│              → _enrich_media_chunks() (for markdown refs)  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔗 Связанные документы

- [33. Markdown-Media Integration](33_markdown_media_integration.md) — обогащение IMAGE_REF **внутри** Markdown
- [26. Gemini Vision Integration](26_gemini_vision_integration.md) — Vision API детали
- [30. Audio Analysis](30_audio_analysis_architecture.md) — Audio API детали
- [31. Video Multimodal](31_video_multimodal_analysis.md) — Video API детали

---

**Коммит:** `b6c3968` — feat: Add direct media ingestion support (Phase 13.3)

---

**← [К оглавлению](00_overview.md)**
