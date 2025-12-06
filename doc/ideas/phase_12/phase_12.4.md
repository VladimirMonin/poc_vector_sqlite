# Phase 12.4: Search — Chunks vs Documents Toggle + Cache Fix

**Статус:** ✅ ВЫПОЛНЕНО  
**Дата:** 2025-12-06  
**Зависимость:** Phase 12.3  
**Цель:** Добавить переключатель "Чанки / Документы" в поиске + исправить кеширование

---

## 📋 Описание

Сейчас поиск возвращает **только чанки** (гранулярные результаты).

Пользователь может хотеть видеть **документы целиком** — когда один документ содержит несколько релевантных чанков, показывать его один раз.

**Дополнительно обнаружено:** кеширование эмбеддингов не работало — кеш заполнялся, но `search_chunks()` всегда генерировал эмбеддинг заново.

---

## 🎯 Решение

### Переключатель результатов
Добавить radio button или toggle в UI поиска:

- **Чанки** (по умолчанию) — `search_chunks()` → карточки чанков
- **Документы** — `search()` → карточки документов (с агрегацией)

### Исправление кеширования
- Добавить параметр `query_vector` в `SemanticCore.search()` и `search_chunks()`
- Передавать закешированный вектор из `QueryCacheService`
- Экономия API-вызовов при повторных запросах

---

## 🔧 Задачи

### 1. UI — добавить переключатель

**Файл:** `app/templates/search.html`

```html
<h6 class="text-muted small text-uppercase mb-2">Результаты</h6>
<div class="btn-group btn-group-sm w-100" role="group">
    <input type="radio" class="btn-check" name="result_type" id="result-chunks" value="chunks" checked>
    <label class="btn btn-outline-primary" for="result-chunks">Чанки</label>
    
    <input type="radio" class="btn-check" name="result_type" id="result-docs" value="documents">
    <label class="btn btn-outline-primary" for="result-docs">Документы</label>
</div>
```

**HTMX:** Добавить `#result-type-group` в `hx-include`.

---

### 2. Backend — обработать параметр

**Файл:** `app/routes/search.py:results()`

```python
result_type = request.args.get("result_type", "chunks")

if result_type == "documents":
    results = service.search_documents(query=query, mode=mode, limit=limit)
else:
    results = service.search(query=query, mode=mode, limit=limit)
```

---

### 3. Service — метод search_documents()

**Файл:** `app/services/search_service.py`

```python
def search_documents(self, query: str, mode: str, limit: int) -> list[DocumentResultItem]:
    """Поиск с агрегацией по документам.
    
    Использует core.search() вместо search_chunks().
    """
    results = self.core.search(query=query, mode=mode, limit=limit)
    return [_search_result_to_doc_item(r) for r in results]
```

---

### 4. Template — карточка документа

**Файл:** `app/templates/partials/search_results.html`

Добавить условный рендеринг:

```html
{% if result_type == 'documents' %}
    <!-- Карточка документа -->
{% else %}
    <!-- Карточка чанка (текущее) -->
{% endif %}
```

---

## 🧪 Тесты

```python
def test_search_chunks_mode(client):
    response = client.get("/search/results?q=python&result_type=chunks")
    assert b"chunk" in response.data

def test_search_documents_mode(client):
    response = client.get("/search/results?q=python&result_type=documents")
    assert b"document" in response.data
```

---

## 📊 Чеклист

- [ ] Radio buttons в search.html
- [ ] HTMX include обновлён
- [ ] Route обрабатывает `result_type`
- [ ] `search_documents()` реализован
- [ ] Карточка документа в template
- [ ] Тесты написаны
