## 🗺️ Phase 6.4: Markdown Asset Enrichment (The Missing Link)

> **Цель:** Автоматический анализ изображений из Markdown через Gemini Vision с передачей контекста.

---

### 🎯 Ключевые решения (уточнено)

| Вопрос | Решение | Обоснование |
|--------|---------|-------------|
| `enrich_media` по умолчанию | **False** | Явное включение, экономия токенов, быстрый `ingest()` |
| Режимы обработки | `sync` / `async` (Local Queue) | Google Batch требует GCS — пока избегаем |
| Типы медиа | **Только IMAGE_REF** | `![alt](src)` — 90% кейсов. Аудио/видео в MD отложены |
| Кеширование Vision | **Нет** | Контекст уникален для каждого документа |

---

### 📌 Текущее состояние (подтверждено кодом)

| Компонент | Статус | Что делает |
|-----------|--------|------------|
| `MarkdownNodeParser` | ✅ | Парсит `![alt](path)` → `IMAGE_REF` с `headers`, `alt`, `title` |
| `SmartSplitter` | ✅ | Создаёт `Chunk(type=IMAGE_REF, metadata={headers, alt, title})` |
| `HierarchicalContextStrategy` | ⚠️ | Формирует текст `Section: ... Type: Image Reference Source: {path}` — **но изображение НЕ анализируется!** |
| `SemanticCore.ingest()` | ❌ | **НЕ вызывает** `ingest_image()` для IMAGE_REF чанков |
| `ingest_image()` | ✅ | Умеет принимать `context_text` и отправлять в Vision API |

---

### 📦 1. Новый компонент: `MarkdownAssetEnricher`

**Файл:** `semantic_core/processing/enrichers/markdown_assets.py`

```python
@dataclass
class MediaContext:
    breadcrumbs: str          # "Setup > Nginx Configuration"
    surrounding_text: str     # "[Before]: ...настройте nginx...\n[After]: ...это конфигурация..."
    role: str = "Illustration embedded in document"

class MarkdownAssetEnricher:
    def __init__(self, context_window: int = 200):
        self.context_window = context_window
    
    def get_context(self, media_chunk: Chunk, all_chunks: list[Chunk]) -> MediaContext:
        """Извлекает контекст: headers + текст ДО/ПОСЛЕ картинки."""
```

**Алгоритм `get_context()`:**

1. Берёт `headers` из `chunk.metadata` → breadcrumbs
2. Находит предыдущий TEXT-чанк → последние N символов
3. Находит следующий TEXT-чанк → первые N символов
4. Добавляет `alt` текст
5. Возвращает `MediaContext`

---

### ⚙️ 2. Модификация `SemanticCore.ingest()`

**Новый параметр:**

```python
def ingest(
    self,
    document: Document,
    mode: IngestionMode = "sync",
    enrich_media: bool = False,  # NEW — явное включение
) -> Document:
```

**Новый приватный метод `_enrich_media_chunks()`:**

```python
def _enrich_media_chunks(self, chunks: list[Chunk], document: Document, mode: str) -> list[Chunk]:
    """Для каждого IMAGE_REF:
    1. Резолвит путь (относительно документа)
    2. Извлекает контекст через MarkdownAssetEnricher
    3. Вызывает ingest_image() / создаёт задачу
    4. Обновляет chunk.content = description от Vision
    """
```

---

### 🛠️ 3. Вспомогательные методы

| Метод | Назначение |
|-------|------------|
| `_get_document_directory(doc)` | Получает директорию документа из `doc.source` или `doc.metadata["source"]` |
| `_resolve_image_path(ref, doc_dir)` | Резолвит путь: абсолютный → относительно doc → относительно CWD |
| `_format_context_for_vision(ctx)` | Форматирует `MediaContext` в строку для промпта |
| `_analyze_image_sync(path, ctx)` | Вызывает `image_analyzer.analyze()` с rate limiting |

**Резолв путей (важно!):**

```python
def _resolve_image_path(self, image_ref: str, doc_dir: Optional[Path]) -> Optional[Path]:
    # Пропускаем URL
    if image_ref.startswith(("http://", "https://", "data:")):
        return None
    
    # 1. Абсолютный путь?
    # 2. Относительно директории документа?
    # 3. Относительно CWD?
    # Возвращает Path или None
```

---

### 📊 4. Обновление `HierarchicalContextStrategy`

**Сейчас (IMAGE_REF):**

```python
parts.append("Type: Image Reference")
parts.append(f"Description: {alt_text}")      # alt из markdown
parts.append(f"Source: {chunk.content}")      # путь к файлу
```

**После обогащения (chunk.content = описание от Vision):**

```python
parts.append("Type: Image")
parts.append(f"Description: {chunk.content}")  # "ER-диаграмма с таблицами..."
if chunk.metadata.get("_vision_ocr"):
    parts.append(f"Visible text: {ocr}")
parts.append(f"Source: {chunk.metadata.get('_original_path', '')}")
```

---

### 🛡️ 5. Обработка ошибок (без исключений!)

| Ситуация | Поведение |
|----------|-----------|
| Файл не найден | `chunk.metadata["_media_error"] = "File not found"` → продолжаем |
| Vision API ошибка | `chunk.metadata["_media_error"] = str(e)` → продолжаем |
| Внешний URL (http://) | Пропускаем, не роняем |
| `image_analyzer` не настроен | Пропускаем обогащение, возвращаем чанки как есть |

---

### 📂 6. Структура файлов

```
semantic_core/processing/enrichers/      # NEW
├── __init__.py
└── markdown_assets.py                   # MarkdownAssetEnricher, MediaContext

semantic_core/processing/context/
└── hierarchical_strategy.py             # UPDATE: логика для обогащённых IMAGE_REF

semantic_core/pipeline.py                # UPDATE: _enrich_media_chunks()
```

---

### 🧪 7. Тесты

**Unit (`tests/unit/test_markdown_asset_enricher.py`):**

- `test_get_context_with_neighbors` — текст ДО и ПОСЛЕ включён
- `test_get_context_first_chunk` — первый чанк, нет предыдущего
- `test_get_context_code_neighbor_skipped` — сосед-код пропускается
- `test_breadcrumbs_from_headers`
- `test_alt_included_in_context`

**Integration (`tests/integration/test_ingest_with_images.py`):**

- `test_ingest_document_with_image_sync` — Vision вызывается, description в content
- `test_ingest_document_with_image_async` — задача создаётся
- `test_ingest_missing_image_graceful` — битая ссылка не роняет
- `test_search_finds_image_by_description` — поиск находит по описанию

---

### 📋 8. Порядок реализации

1. **`MarkdownAssetEnricher`** + `MediaContext` — чистая логика
2. **`_resolve_image_path()`** — резолв путей
3. **`_enrich_media_chunks()`** — основная логика в pipeline
4. **Обновить `HierarchicalContextStrategy`** — формат для обогащённых IMAGE_REF
5. **Unit-тесты enricher**
6. **Integration-тесты pipeline**
7. **E2E с реальным API** (опционально)

---

### ✅ Definition of Done

- [ ] `MarkdownAssetEnricher` извлекает контекст (surrounding text + headers)
- [ ] `SemanticCore.ingest()` обрабатывает IMAGE_REF чанки через Vision API
- [ ] Битые ссылки НЕ роняют процесс
- [ ] Результат анализа сохраняется с вектором
- [ ] sync/async режимы работают
- [ ] Тесты проходят

---
