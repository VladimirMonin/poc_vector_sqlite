# Phase 12.4: Search — Chunks vs Documents Toggle + Cache Fix

**Статус:** ✅ ВЫПОЛНЕНО  
**Дата:** 2025-12-06  
**Зависимость:** Phase 12.3  
**Цель:** Добавить переключатель "Чанки / Документы" в поиске + исправить кеширование эмбеддингов

---

## 📋 Описание

Сейчас поиск возвращает **только чанки** (гранулярные результаты).

Пользователь может хотеть видеть **документы целиком** — когда один документ содержит несколько релевантных чанков, показывать его один раз.

**Дополнительно обнаружено и исправлено:**

1. **Кеширование эмбеддингов не работало** — кеш заполнялся, но `search_chunks()` всегда генерировал эмбеддинг заново
2. **RRF score отображался как 1%** — нужна нормализация для корректного отображения
3. **Autocomplete не работал** — отсутствовал атрибут `list=` на input
4. **Поиск срабатывал на каждую букву** — триггер `keyup delay:500ms` мешал autocomplete
5. **Ошибка `Document has no attribute source`** — source хранится в metadata

---

## 🎯 Решение

### 1. Переключатель результатов
Добавить radio button toggle в UI поиска:

- **Чанки** (по умолчанию) — `search_chunks()` → карточки чанков
- **Документы** — `search()` → карточки документов

### 2. Исправление кеширования
- Добавить параметр `query_vector` в `SemanticCore.search()` и `search_chunks()`
- Передавать закешированный вектор из `QueryCacheService`
- Экономия API-вызовов Gemini при повторных запросах

### 3. Нормализация RRF Score
- RRF score = `1/(k+rank)` даёт значения ~0.01-0.033
- Функция `_normalize_rrf_score()` масштабирует в 0-100%

### 4. Исправление Autocomplete
- Добавлен атрибут `list="search-suggestions"` на input
- Триггер изменён на `keyup[key=='Enter']` — поиск только по Enter

---

## 🔧 Выполненные задачи

### ✅ Core: параметр query_vector

**Файл:** `semantic_core/pipeline.py`

```python
def search_chunks(
    self,
    query: str,
    # ... другие параметры
    query_vector: Optional[list[float]] = None,  # NEW
) -> list[ChunkResult]:
    # Используем переданный вектор или генерируем новый
    if mode in ("vector", "hybrid") and query_vector is None:
        query_vector = self.embedder.embed_query(query)
```

### ✅ Service: интеграция кеша + search_documents

**Файл:** `app/services/search_service.py`

```python
@dataclass
class DocumentResultItem:
    """UI-friendly представление документа."""
    doc_id: int
    title: str
    source: Optional[str]
    score: float
    score_percent: int
    # ...

def _normalize_rrf_score(score: float, max_score: float = 0.033) -> int:
    """RRF score 0.01-0.033 → 30-100%."""
    return int(min(score / max_score, 1.0) * 100)

def search_documents(self, query, mode, limit) -> list[DocumentResultItem]:
    if self.cache and mode in ("vector", "hybrid"):
        cache_result = self.cache.get_or_embed(query)
        query_vector = cache_result.embedding  # Используем кеш!
    
    results = self.core.search(query=query, query_vector=query_vector, ...)
```

### ✅ UI: toggle + autocomplete fix

**Файл:** `app/templates/search.html`

```html
<!-- Toggle Чанки/Документы -->
<div class="btn-group btn-group-sm w-100" role="group">
    <input type="radio" name="result_type" id="result-chunks" value="chunks" checked>
    <label class="btn btn-outline-primary" for="result-chunks">Чанки</label>
    <input type="radio" name="result_type" id="result-documents" value="documents">
    <label class="btn btn-outline-primary" for="result-documents">Документы</label>
</div>

<!-- Input с autocomplete -->
<input 
    list="search-suggestions"
    hx-trigger="keyup[key=='Enter'], search"
    ...
>
```

### ✅ Template: карточка документа

**Файл:** `app/templates/partials/search_documents.html`

- Двухколоночная сетка карточек
- Заголовок, описание, score, теги
- Ссылка на детальный просмотр

### ✅ Route: обработка result_type

**Файл:** `app/routes/search.py`

```python
result_type = request.args.get("result_type", "chunks")

if result_type == "documents":
    results = service.search_documents(query, mode, limit)
    return render_template("partials/search_documents.html", ...)
else:
    results = service.search(query, chunk_types, mode, limit)
    return render_template("partials/search_results.html", ...)
```

---

## 🧪 Тесты (11 passed)

```python
def test_search_passes_cached_vector_to_core(mock_core, mock_cache):
    """Закешированный вектор передаётся в core."""
    
def test_search_documents_returns_document_items(mock_core, mock_cache):
    """search_documents возвращает DocumentResultItem."""
    
def test_search_documents_uses_cached_vector(mock_core, mock_cache):
    """search_documents использует кеш."""
```

---

## 📊 Коммиты (10)

1. `feat: Добавлен параметр query_vector в search() и search_chunks()`
2. `feat: Интеграция кеширования эмбеддингов в SearchService`
3. `feat: Добавлен переключатель Chunks/Documents в UI поиска`
4. `feat: Добавлен шаблон search_documents.html для режима документов`
5. `feat: Обработка result_type в роуте /search/results`
6. `feat: Добавлены тесты для кеширования и search_documents`
7. `bugfix: Исправлена ошибка 'Document has no attribute source'`
8. `feat: Нормализация RRF score и исправление autocomplete`
9. `feat: Поиск только по Enter + видимые логи кеша`
10. `refactor: Убраны debug print, оставлено logger.info`

---

## ✅ Результат

- **Cache HIT/MISS** виден в логах
- **Переключатель** Chunks/Documents работает
- **Autocomplete** показывает предложения из кеша
- **Score** нормализован (30-100% вместо 1%)
- **Поиск по Enter** — не мешает autocomplete
- [ ] Route обрабатывает `result_type`
- [ ] `search_documents()` реализован
- [ ] Карточка документа в template
- [ ] Тесты написаны
