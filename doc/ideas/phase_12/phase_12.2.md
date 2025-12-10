# Phase 12.2: UI Cosmetics & Quick Fixes

**Статус:** 📋 СПЕЦИФИКАЦИЯ  
**Дата:** 2025-12-05  
**Зависимость:** Phase 12.1 (частичные исправления)  
**Цель:** Косметические исправления UI — тема, кнопки, бейджи, фильтры

---

## 📋 Обзор проблем (Косметика)

| # | Проблема | Файлы | Сложность |
|---|----------|-------|-----------|
| 1 | Нет чекбокса "Видео" в фильтрах поиска | `search_service.py` | 🟢 EASY |
| 2 | Кнопки "О приложении" и "Сменить тему" слиплись | `base.html` | 🟢 EASY |
| 3 | Кнопки "Обновить" и "Удалить" слиплись | `document_detail.html` | 🟢 EASY |
| 4 | Бейдж типа поиска не читаемый в светлой теме | `search_results.html` | 🟢 EASY |
| 5 | Score показан как 0.706, хочется % | `search_results.html`, `search_service.py` | 🟢 EASY |
| 6 | Документы в списке не кликабельны | `documents.html` | 🟢 EASY |
| 7 | MD контент белый в тёмной теме | `document_detail.html`, CSS | 🟢 EASY |
| 8 | Плеер аудио/видео в детальном view | `document_detail.html` | 🟡 MEDIUM |

---

## 🔧 Задачи (Косметика — Quick Fixes)

### 1. 🟢 Добавить чекбокс "Видео" в фильтры поиска

**Проблема:** В `get_available_types()` нет video, в `CHUNK_TYPE_FILTER_MAP` нет маппинга.

**Файл:** `app/services/search_service.py`

**Изменения:**

```python
# Добавить в CHUNK_TYPE_FILTER_MAP:
"video": "video_ref",

# Добавить в get_available_types():
{"id": "video", "label": "Видео", "icon": "bi-camera-video"},
```

---

### 2. 🟢 Разделить кнопки "О приложении" и "Сменить тему"

**Проблема:** Кнопки слиплись в navbar.

**Файл:** `app/templates/base.html`

**Изменения:** Добавить `me-2` класс между кнопками.

---

### 3. 🟢 Разделить кнопки "Обновить" и "Удалить"

**Проблема:** Кнопки слиплись в document_detail.

**Файл:** `app/templates/document_detail.html`

**Изменения:** Добавить `me-2` класс или gap в btn-group.

---

### 4. 🟢 Исправить бейдж типа поиска в светлой теме

**Проблема:** `bg-outline-secondary` не читаемый.

**Файл:** `app/templates/partials/search_results.html`

**Изменения:** Заменить на `bg-light text-dark border` или использовать `bg-secondary-subtle`.

---

### 5. 🟢 Показывать Score как проценты

**Проблема:** Score `0.706` непонятен пользователю.

**Файлы:**

- `app/services/search_service.py` — добавить `score_percent` в `SearchResultItem`
- `app/templates/partials/search_results.html` — отображать `{{ result.score_percent }}%`

**Формула:** `score_percent = round(score * 100)`

---

### 6. 🟢 Сделать документы кликабельными в списке

**Проблема:** В `documents.html` название документа не ссылка.

**Файл:** `app/templates/documents.html`

**Изменения:** Обернуть title в `<a href="{{ url_for('ingest.document_detail', doc_id=doc.id) }}">`.

---

### 7. 🟢 Исправить стили MD в тёмной теме

**Проблема:** Блок `<pre>` с контентом белый в тёмной теме.

**Файл:** `app/templates/document_detail.html`

**Изменения:** Заменить `bg-light` на `bg-body-secondary` или убрать явный bg.

---

### 8. 🟡 Добавить плеер для аудио/видео

**Проблема:** Нет возможности воспроизвести медиа в детальном view.

**Файл:** `app/templates/document_detail.html`

**Изменения:**

```html
{% if media_type == 'audio' %}
<audio controls class="w-100">
    <source src="{{ url_for('static', filename='uploads/' ~ meta.get('filename', '')) }}">
</audio>
{% elif media_type == 'video' %}
<video controls class="w-100" style="max-height: 400px;">
    <source src="{{ url_for('static', filename='uploads/' ~ meta.get('filename', '')) }}">
</video>
{% endif %}
```

---

## 📋 Дополнительные улучшения (если успеем)

### 9. 🟡 Переключатель Rendered/Raw для MD

**Проблема:** Хочется видеть отрендеренный Markdown, но с возможностью посмотреть сырой.

**Решение:** Добавить tabs или toggle button.

**Файлы:**

- `app/templates/document_detail.html` — tabs для Document content
- `app/utils/markdown.py` — уже есть `render_markdown()`

---

## 🔧 Старые задачи (перенесены в Phase 12.3+)

Следующие задачи требуют больше работы и вынесены в отдельные фазы:

| Задача | Новая фаза |
|--------|------------|
| Fix Chat Interface | **Phase 12.3** |
| Search: Chunks vs Documents toggle | **Phase 12.4** |
| Media Gallery Page | **Phase 12.5** |
| Search: Similarity threshold slider | **Phase 12.6** |
| FTS Index population check | **Phase 12.7** |
| Queue Monitor Page | **Phase 12.8** |

---

## 📊 Чеклист реализации

| # | Задача | Файлы | Статус |
|---|--------|-------|--------|
| 1 | Video checkbox filter | `search_service.py` | 🔧 TODO |
| 2 | Navbar buttons spacing | `base.html` | 🔧 TODO |
| 3 | Document detail buttons spacing | `document_detail.html` | 🔧 TODO |
| 4 | Match type badge fix | `search_results.html` | 🔧 TODO |
| 5 | Score as percent | `search_service.py`, `search_results.html` | 🔧 TODO |
| 6 | Clickable documents list | `documents.html` | 🔧 TODO |
| 7 | Dark theme MD styles | `document_detail.html` | 🔧 TODO |
| 8 | Audio/Video player | `document_detail.html` | 🔧 TODO |
| 9 | MD Rendered/Raw toggle | `document_detail.html` | 🟡 OPTIONAL |

---

## 🔄 Порядок реализации

1. **Video checkbox** — быстрый фикс в search_service.py
2. **Button spacing** — CSS классы в шаблонах
3. **Badge fix** — CSS классы в search_results.html
4. **Score percent** — добавить поле в SearchResultItem
5. **Clickable docs** — добавить `<a>` в documents.html
6. **Dark theme** — заменить bg-light на bg-body-secondary
7. **Audio/Video player** — добавить HTML5 теги
8. **MD toggle** — опционально, если успеем

---

## 📝 Примечания

- Phase 13.1 уже исправила FTS для чанков (`chunks_fts` таблица)
- Flask использует `vector_store.db` (из `.env`), CLI использует `semantic.db` (из `semantic.toml`)
- Нужно проверить синхронизацию FTS индекса при старте
