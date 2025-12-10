# 🐛 Phase 13.3 — Исправление прямой загрузки медиа-файлов

**Статус:** 🔴 КРИТИЧЕСКИЙ БАГ  
**Обнаружен:** 2025-12-05 в ходе Phase 13.2 (Human-First Testing)  
**Влияние:** Прямая загрузка изображений, аудио и видео полностью сломана

---

## 1. Описание проблемы

### 1.1 Симптомы

При загрузке медиа-файлов напрямую через CLI:

```bash
semantic ingest photo.jpg -e       # enrich_media=True
semantic ingest audio.ogg -e
semantic ingest video.mp4 -e
```

**Ожидаемое поведение:**

- Vision/Audio/Video API вызывается
- В БД сохраняется описание/транскрипция
- Поиск находит содержимое медиа

**Фактическое поведение:**

- API НЕ вызывается
- В БД сохраняется ПУТЬ к файлу как текст
- Поиск находит только путь, а не содержимое

### 1.2 Доказательства из БД

```
=== STATS ===
Document media types:    Chunk types:
   audio: 3              code: 13
   image: 9              text: 29  ← ВСЁ МЕДИА = TEXT!
   video: 2              
                         image_ref: 0  ← НОЛЬ!
                         audio_ref: 0
                         video_ref: 0
```

Примеры чанков:

```
Chunk 10 (doc=6): chunk_type=text, doc_media_type=video
   Content: C:\PY\poc_vector_sqlite\tests\asests\module_init_demo.mp4  ← ПУТЬ!

Chunk 11 (doc=7): chunk_type=text, doc_media_type=audio
   Content: C:\PY\poc_vector_sqlite\tests\asests\module_init_demo.ogg  ← ПУТЬ!
```

---

## 2. Корневая причина

### 2.1 Поток данных при загрузке `.jpg` напрямую

```
1. CLI: _create_document(path)
   ├─ media_type = MediaType.IMAGE  ✓ Правильно определено
   └─ content = str(path.absolute())  ← "C:\...\photo.jpg"

2. SemanticCore.ingest(document, enrich_media=True)
   └─ SmartSplitter.split(document)
      └─ MarkdownNodeParser.parse("C:\...\photo.jpg")  
         └─ Видит простой текст → segment_type = TEXT

3. _enrich_media_chunks(chunks):
   for chunk in chunks:
       if chunk.chunk_type not in MEDIA_CHUNK_TYPES:
           continue  ← ПРОПУСКАЕТ! TEXT ≠ IMAGE_REF

4. Результат: chunk.content = путь, эмбеддинг по пути
```

### 2.2 Ключевые файлы с проблемой

| Файл | Строки | Проблема |
|------|--------|----------|
| `semantic_core/cli/commands/ingest.py` | 61-68 | `content = str(path.absolute())` для медиа |
| `semantic_core/processing/parsers/markdown_parser.py` | — | Парсит путь как текст |
| `semantic_core/processing/splitters/smart_splitter.py` | 100-125 | Только `MEDIA_CHUNK_TYPES` изолируются |
| `semantic_core/pipeline.py` | 520-527 | `if chunk.chunk_type not in MEDIA_CHUNK_TYPES: continue` |

### 2.3 Когда работает (markdown со ссылками)

```markdown
# Моя статья
![Описание](images/photo.jpg)   ← MarkdownNodeParser видит синтаксис!
```

1. Парсер находит `![](...)` → `segment_type = IMAGE_REF`
2. Сплиттер создаёт `chunk_type = IMAGE_REF`
3. `_enrich_media_chunks()` находит чанк
4. Vision API вызывается
5. **РАБОТАЕТ!**

---

## 3. Варианты решения

### 3.1 Вариант A: Проверка media_type ДО сплиттера (РЕКОМЕНДУЕТСЯ)

**Идея:** Если `document.media_type` не TEXT, обрабатываем напрямую без парсера.

**Изменения в `pipeline.py`:**

```python
def ingest(self, document: Document, ...):
    # NEW: Прямая обработка медиа-документов
    if document.media_type in (MediaType.IMAGE, MediaType.AUDIO, MediaType.VIDEO):
        return self._ingest_direct_media(document, mode, enrich_media)
    
    # Существующая логика для TEXT
    chunks = self.splitter.split(document)
    ...
```

**Новый метод `_ingest_direct_media()`:**

```python
def _ingest_direct_media(self, document: Document, mode, enrich_media):
    """Обрабатывает медиа-файлы напрямую (без парсера)."""
    media_path = Path(document.content)  # content = путь
    
    # Определяем chunk_type по media_type
    chunk_type_map = {
        MediaType.IMAGE: ChunkType.IMAGE_REF,
        MediaType.AUDIO: ChunkType.AUDIO_REF,
        MediaType.VIDEO: ChunkType.VIDEO_REF,
    }
    chunk_type = chunk_type_map[document.media_type]
    
    # Если enrich_media — вызываем анализатор сразу
    content = str(media_path)
    if enrich_media:
        result = self._analyze_media_for_chunk(chunk_type, media_path, "")
        if result:
            content = self._build_content_from_result(result)
    
    # Создаём единственный чанк
    chunk = Chunk(
        content=content,
        chunk_index=0,
        chunk_type=chunk_type,
        metadata={"_original_path": str(media_path)},
    )
    
    # Векторизация и сохранение
    ...
```

**Плюсы:**

- Минимальные изменения
- Не ломает существующую логику markdown
- Чистый роутинг по типу

**Минусы:**

- Дублирование логики сохранения

### 3.2 Вариант B: Создание MediaSplitter

**Идея:** Новый сплиттер для медиа, который сразу создаёт правильный chunk_type.

```python
class MediaSplitter(BaseSplitter):
    """Сплиттер для прямых медиа-файлов."""
    
    def split(self, document: Document) -> list[Chunk]:
        chunk_type = self._media_type_to_chunk_type(document.media_type)
        return [Chunk(
            content=document.content,  # Путь
            chunk_type=chunk_type,     # IMAGE_REF/AUDIO_REF/VIDEO_REF
            ...
        )]
```

**CLI выбирает сплиттер по media_type.**

**Плюсы:**

- SOLID: один сплиттер — одна ответственность
- Легко тестировать

**Минусы:**

- Больше классов
- CLI должен знать о сплиттерах

### 3.3 Вариант C: Фикс в SmartSplitter

**Идея:** SmartSplitter проверяет `document.media_type` перед парсингом.

```python
def split(self, document: Document) -> list[Chunk]:
    # NEW: Если документ — медиа, не парсим
    if document.media_type in (MediaType.IMAGE, MediaType.AUDIO, MediaType.VIDEO):
        return self._split_media_document(document)
    
    # Существующая логика для текста
    segments = list(self.parser.parse(document.content))
    ...
```

**Плюсы:**

- Одно место изменения
- Сплиттер становится умнее

**Минусы:**

- Смешивание ответственности (текст + медиа)
- SmartSplitter знает о MediaType

---

## 4. Рекомендуемое решение: Вариант A

### 4.1 План реализации

1. **`pipeline.py`**: Добавить проверку `document.media_type` в начале `ingest()`
2. **`pipeline.py`**: Реализовать `_ingest_direct_media()`
3. **`pipeline.py`**: Добавить `_build_content_from_result()` для формирования контента
4. **Тесты**: Добавить тесты прямой загрузки в `tests/integration/`

### 4.2 Детальная спецификация `_ingest_direct_media()`

```python
def _ingest_direct_media(
    self,
    document: Document,
    mode: IngestionMode,
    enrich_media: bool,
) -> Document:
    """Обрабатывает медиа-файл напрямую (без парсера/сплиттера).
    
    Вызывается когда document.media_type != TEXT.
    
    Args:
        document: Документ с content=путь_к_файлу
        mode: sync или async
        enrich_media: Вызывать ли Vision/Audio/Video API
        
    Returns:
        Сохранённый Document с ID
    """
    media_path = Path(document.content)
    
    # 1. Определяем chunk_type
    chunk_type_map = {
        MediaType.IMAGE: ChunkType.IMAGE_REF,
        MediaType.AUDIO: ChunkType.AUDIO_REF,
        MediaType.VIDEO: ChunkType.VIDEO_REF,
    }
    chunk_type = chunk_type_map[document.media_type]
    
    # 2. Формируем контент чанка
    if enrich_media and mode == "sync":
        # Вызываем API
        result = self._analyze_media_for_chunk(chunk_type, media_path, context_text="")
        if result:
            content = self._build_content_from_result(result)
            metadata = self._build_metadata_from_result(result, media_path)
        else:
            content = str(media_path)
            metadata = {"_original_path": str(media_path), "_media_error": "Analysis failed"}
    else:
        content = str(media_path)
        metadata = {"_original_path": str(media_path)}
    
    # 3. Создаём чанк
    chunk = Chunk(
        content=content,
        chunk_index=0,
        chunk_type=chunk_type,
        metadata=metadata,
    )
    
    # 4. Векторизация (если sync)
    if mode == "sync":
        vector_text = self.context_strategy.form_vector_text(chunk, document)
        embedding = self.embedder.embed_documents([vector_text])[0]
        chunk.embedding = embedding
    else:
        chunk.metadata["_vector_source"] = content
        chunk.metadata["_embedding_status"] = EmbeddingStatus.PENDING.value
    
    # 5. Сохраняем
    return self.store.save(document, [chunk])
```

### 4.3 Вспомогательные методы

```python
def _build_content_from_result(self, result: dict) -> str:
    """Формирует текстовый контент из результата анализа."""
    media_type = result.get("type")
    
    if media_type == "image":
        return result.get("description", "")
    elif media_type == "audio":
        return result.get("transcription") or result.get("description", "")
    elif media_type == "video":
        # Для видео: описание + транскрипция
        parts = []
        if result.get("description"):
            parts.append(result["description"])
        if result.get("transcription"):
            parts.append(f"\n\nTranscription:\n{result['transcription']}")
        return "".join(parts)
    return ""

def _build_metadata_from_result(self, result: dict, media_path: Path) -> dict:
    """Формирует metadata из результата анализа."""
    metadata = {"_original_path": str(media_path)}
    media_type = result.get("type")
    
    if media_type == "image":
        metadata["_vision_alt"] = result.get("alt_text", "")
        metadata["_vision_keywords"] = result.get("keywords", [])
        if result.get("ocr_text"):
            metadata["_vision_ocr"] = result["ocr_text"]
            
    elif media_type == "audio":
        metadata["_audio_description"] = result.get("description", "")
        metadata["_audio_keywords"] = result.get("keywords", [])
        metadata["_audio_participants"] = result.get("participants", [])
        if result.get("duration_seconds"):
            metadata["_audio_duration"] = result["duration_seconds"]
            
    elif media_type == "video":
        metadata["_video_keywords"] = result.get("keywords", [])
        if result.get("transcription"):
            metadata["_video_transcription"] = result["transcription"]
        if result.get("ocr_text"):
            metadata["_video_ocr"] = result["ocr_text"]
        if result.get("duration_seconds"):
            metadata["_video_duration"] = result["duration_seconds"]
    
    return metadata
```

---

## 5. Тест-кейсы

### 5.1 Unit-тесты

```python
class TestDirectMediaIngestion:
    """Тесты прямой загрузки медиа."""
    
    def test_image_creates_image_ref_chunk(self, core):
        """Загрузка .jpg создаёт чанк IMAGE_REF."""
        doc = Document(content="path/to/image.jpg", media_type=MediaType.IMAGE)
        result = core.ingest(doc, enrich_media=False)
        
        chunks = core.store.get_chunks(result.id)
        assert len(chunks) == 1
        assert chunks[0].chunk_type == ChunkType.IMAGE_REF
    
    def test_audio_creates_audio_ref_chunk(self, core):
        """Загрузка .ogg создаёт чанк AUDIO_REF."""
        doc = Document(content="path/to/audio.ogg", media_type=MediaType.AUDIO)
        result = core.ingest(doc, enrich_media=False)
        
        chunks = core.store.get_chunks(result.id)
        assert chunks[0].chunk_type == ChunkType.AUDIO_REF
    
    def test_video_creates_video_ref_chunk(self, core):
        """Загрузка .mp4 создаёт чанк VIDEO_REF."""
        ...
    
    def test_image_enrichment_calls_vision_api(self, core, mock_image_analyzer):
        """enrich_media=True вызывает Vision API."""
        mock_image_analyzer.analyze.return_value = MediaAnalysisResult(
            description="A cat sitting on a couch",
            keywords=["cat", "couch", "pet"],
        )
        
        doc = Document(content="path/to/cat.jpg", media_type=MediaType.IMAGE)
        result = core.ingest(doc, enrich_media=True)
        
        chunks = core.store.get_chunks(result.id)
        assert "cat sitting" in chunks[0].content
        mock_image_analyzer.analyze.assert_called_once()
```

### 5.2 Integration-тесты

```python
class TestDirectMediaSearch:
    """Тесты поиска по содержимому медиа."""
    
    def test_search_finds_image_by_description(self, core, real_image_path):
        """Поиск находит картинку по описанию от Vision API."""
        doc = Document(
            content=str(real_image_path),
            media_type=MediaType.IMAGE,
        )
        core.ingest(doc, enrich_media=True)
        
        results = core.search("cat on couch")
        assert len(results) > 0
        assert "cat" in results[0].document.content.lower()
```

---

## 6. Критерии приёмки

- [ ] `semantic ingest photo.jpg -e` → чанк типа `IMAGE_REF`
- [ ] `semantic ingest audio.ogg -e` → чанк типа `AUDIO_REF`  
- [ ] `semantic ingest video.mp4 -e` → чанк типа `VIDEO_REF`
- [ ] Vision/Audio/Video API вызывается при `enrich_media=True`
- [ ] Поиск находит медиа по содержимому (описание/транскрипция)
- [ ] Путь к файлу сохраняется в `metadata._original_path`
- [ ] Markdown с `![](...)` продолжает работать (регрессия)

---

## 7. Ссылки на код

- **CLI создание документа:** `semantic_core/cli/commands/ingest.py:55-75`
- **SmartSplitter:** `semantic_core/processing/splitters/smart_splitter.py:56-185`
- **Markdown парсер:** `semantic_core/processing/parsers/markdown_parser.py:1-100`
- **Pipeline.ingest:** `semantic_core/pipeline.py:137-207`
- **_enrich_media_chunks:** `semantic_core/pipeline.py:479-570`
- **Media Analyzers:** `semantic_core/infrastructure/gemini/`
