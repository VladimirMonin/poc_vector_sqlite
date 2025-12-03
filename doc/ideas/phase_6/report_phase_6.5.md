# 📋 Отчёт Phase 6.5: Audio & Video in Markdown

**Дата:** 2025-12-03  
**Статус:** ✅ Завершено  
**Ветка:** `phase_6`

---

## 🎯 Цель фазы

Научить библиотеку автоматически обнаруживать ссылки на аудио и видео файлы внутри Markdown-документов (`[Link](file.mp3)`) и обрабатывать их как медиа-контент, сохраняя контекст документа.

---

## 📦 Реализованные изменения

### 1. Domain Layer (`semantic_core/domain/chunk.py`)

**Добавлено:**
- `ChunkType.AUDIO_REF` = "audio_ref"
- `ChunkType.VIDEO_REF` = "video_ref"
- `MEDIA_CHUNK_TYPES` — frozenset для удобной проверки медиа-типов

```python
MEDIA_CHUNK_TYPES = frozenset({
    ChunkType.IMAGE_REF,
    ChunkType.AUDIO_REF,
    ChunkType.VIDEO_REF,
})
```

**Экспорт:** Обновлён `domain/__init__.py`.

---

### 2. Markdown Parser (`semantic_core/processing/parsers/markdown_parser.py`)

**Добавлено:**
- Константы расширений:
  - `AUDIO_EXTENSIONS`: `.mp3`, `.wav`, `.ogg`, `.flac`, `.aac`, `.aiff`
  - `VIDEO_EXTENSIONS`: `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`
  - `IMAGE_EXTENSIONS`: `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.svg`, `.bmp`

- `_get_media_type_by_extension()` — определение типа по расширению файла

- `_process_inline_children()` — обработка inline-токенов:
  - `image` токены: проверка расширения (может быть VIDEO!)
  - `link_open` → `text` → `link_close`: накопление текста ссылки

**Логика:**
```
[Audio](file.mp3)  → AUDIO_REF с alt="Audio"
[Video](demo.mp4)  → VIDEO_REF с alt="Video"
![Preview](vid.mp4) → VIDEO_REF (не IMAGE_REF!)
```

---

### 3. Smart Splitter (`semantic_core/processing/splitters/smart_splitter.py`)

**Изменения:**
- Импорт `MEDIA_CHUNK_TYPES`
- Условие изоляции медиа-чанков:

```python
elif segment.segment_type in MEDIA_CHUNK_TYPES:
    # flush buffer + create chunk
    chunk_type=segment.segment_type  # передаём напрямую
```

Все медиа-чанки (IMAGE/AUDIO/VIDEO_REF) изолируются одинаково.

---

### 4. Markdown Asset Enricher (`semantic_core/processing/enrichers/markdown_assets.py`)

**Изменения в `MediaContext`:**
- Добавлено поле `media_type: str` (image/audio/video)
- `format_for_api()` — универсальный метод (вместо только vision)
- `format_for_vision()` — алиас для обратной совместимости

**Изменения в `MarkdownAssetEnricher`:**
- `get_context()` определяет `media_type` и `role` по chunk_type
- `_get_media_type_name()` — маппинг ChunkType → название
- `_get_default_role()` — дефолтные роли:
  - IMAGE_REF: "Illustration embedded in document"
  - AUDIO_REF: "Audio recording embedded in document"
  - VIDEO_REF: "Video embedded in document"

---

### 5. Hierarchical Context Strategy (`semantic_core/processing/context/hierarchical_strategy.py`)

**Добавлены ветки для:**

**AUDIO_REF (обогащённый):**
```
Section: Header > Subheader
Type: Audio
Transcription: <content>
Speakers: speaker1, speaker2
Action items: item1; item2
Keywords: kw1, kw2
Duration: 120.5s
Source: path/to/file.mp3
```

**AUDIO_REF (необогащённый):**
```
Section: Header > Subheader
Type: Audio Reference
Description: <alt text>
Source: path/to/file.mp3
```

**VIDEO_REF (обогащённый):**
```
Section: Header > Subheader
Type: Video
Description: <content>
Audio transcription: <transcription>
Visible text: <ocr>
Keywords: kw1, kw2
Duration: 60.0s
Source: path/to/file.mp4
```

**VIDEO_REF (необогащённый):**
```
Section: Header > Subheader
Type: Video Reference
Description: <alt text>
Source: path/to/file.mp4
```

---

### 6. Pipeline (`semantic_core/pipeline.py`)

**Конструктор SemanticCore:**
```python
def __init__(
    self,
    ...
    image_analyzer: Optional["GeminiImageAnalyzer"] = None,
    audio_analyzer: Optional["GeminiAudioAnalyzer"] = None,  # NEW
    video_analyzer: Optional["GeminiVideoAnalyzer"] = None,  # NEW
    ...
)
```

**Новые методы:**
- `_has_analyzer_for_type()` — проверка наличия анализатора
- `_resolve_media_path()` — универсальный резолв пути (ранее `_resolve_image_path`)
- `_analyze_media_for_chunk()` — роутинг на нужный анализатор
- `_apply_analysis_result()` — применение результата к чанку
- `_get_mime_type()` — определение MIME-типа по расширению

**Метаданные обогащённых чанков:**

| Тип | Метаданные |
|-----|------------|
| IMAGE_REF | `_vision_alt`, `_vision_keywords`, `_vision_ocr` |
| AUDIO_REF | `_audio_description`, `_audio_keywords`, `_audio_participants`, `_audio_action_items`, `_audio_duration` |
| VIDEO_REF | `_video_transcription`, `_video_keywords`, `_video_ocr`, `_video_duration` |

**Содержимое чанка после обогащения:**
- IMAGE_REF: `content = description`
- AUDIO_REF: `content = transcription` (или description если нет транскрипции)
- VIDEO_REF: `content = description` (транскрипция в metadata)

---

## 📊 Коммиты

1. `docs: Обновлён план Phase 6.5 после анализа кода`
2. `feat: Добавлены AUDIO_REF и VIDEO_REF в ChunkType`
3. `feat: Детекция аудио/видео ссылок в Markdown парсере`
4. `feat: SmartSplitter поддерживает AUDIO_REF и VIDEO_REF`
5. `feat: MarkdownAssetEnricher поддерживает AUDIO_REF и VIDEO_REF`
6. `feat: HierarchicalContextStrategy поддерживает AUDIO_REF и VIDEO_REF`
7. `feat: SemanticCore поддерживает audio_analyzer и video_analyzer`

---

## 🔍 Технические решения

### Почему `.m4a` исключён?

Gemini API официально НЕ поддерживает `audio/x-m4a`. Файлы `.m4a` требуют конвертации в OGG через `optimize_audio_to_bytes()`. Чтобы не усложнять парсер, расширение исключено из списка.

### Почему видео в image синтаксисе?

`![Preview](demo.mp4)` — валидный Markdown. Такие ссылки теперь корректно определяются как `VIDEO_REF` (по расширению), а не `IMAGE_REF`.

### Роутинг анализаторов

Используется простая проверка `_has_analyzer_for_type()`. Если анализатор не настроен — чанк пропускается с логом. Это позволяет использовать библиотеку только с image_analyzer, не ломая существующий код.

---

## ⚠️ Ограничения

1. **Тесты отложены** — unit/integration тесты не написаны
2. **Async mode** — создаёт задачи, но не проверялось E2E
3. **VideoAnalysisConfig** — пока hardcoded, нужно сделать настраиваемым
4. **URL-ссылки** — пропускаются (только локальные файлы)

---

## 📈 Готовность

| Компонент | Статус |
|-----------|--------|
| ChunkType enum | ✅ |
| Markdown Parser | ✅ |
| Smart Splitter | ✅ |
| Asset Enricher | ✅ |
| Context Strategy | ✅ |
| Pipeline integration | ✅ |
| Unit tests | ⏸️ |
| Integration tests | ⏸️ |

**Фаза 6.5 завершена.** Система готова к обработке аудио и видео ссылок в Markdown-документах.
