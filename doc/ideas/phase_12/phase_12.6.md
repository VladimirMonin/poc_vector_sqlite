# Phase 12.6: Search — Similarity Threshold Slider

**Статус:** 📋 СПЕЦИФИКАЦИЯ  
**Дата:** 2025-12-05  
**Зависимость:** Phase 12.5  
**Цель:** Добавить slider для фильтрации результатов по минимальному score

---

## 📋 Описание

Сейчас поиск возвращает все результаты до limit. Пользователь хочет **отсечь мусор** — результаты с низким score.

---

## 🎯 Решение

Добавить range slider в UI поиска:

- Диапазон: 0% — 100% (или 0.0 — 1.0)
- Default: 0% (показывать всё)
- Фильтрация на стороне сервера

---

## 🔧 Задачи

### 1. UI — добавить slider

**Файл:** `app/templates/search.html`

```html
<h6 class="text-muted small text-uppercase mb-2">Мин. релевантность</h6>
<div class="d-flex align-items-center">
    <input type="range" 
           class="form-range" 
           id="min-score" 
           name="min_score"
           min="0" max="100" value="0" step="5">
    <span id="min-score-value" class="ms-2 badge bg-secondary">0%</span>
</div>

<script>
document.getElementById('min-score').addEventListener('input', function() {
    document.getElementById('min-score-value').textContent = this.value + '%';
});
</script>
```

**HTMX:** Добавить `#min-score` в `hx-include`.

---

### 2. Backend — применить фильтр

**Файл:** `app/routes/search.py:results()`

```python
min_score = request.args.get("min_score", 0, type=int)
min_score_float = min_score / 100.0  # 50% → 0.5

results = service.search(
    query=query,
    mode=mode,
    limit=limit,
    min_score=min_score_float,
)
```

---

### 3. Service — фильтрация

**Файл:** `app/services/search_service.py`

```python
def search(
    self,
    query: str,
    ...,
    min_score: float = 0.0,
) -> list[SearchResultItem]:
    """Поиск с фильтрацией по минимальному score."""
    
    chunk_results = self.core.search_chunks(query=query, mode=mode, limit=limit * 2)
    
    # Фильтруем по min_score
    if min_score > 0:
        chunk_results = [r for r in chunk_results if r.score >= min_score]
    
    # Обрезаем до limit
    chunk_results = chunk_results[:limit]
    
    return [_chunk_result_to_item(r) for r in chunk_results]
```

---

## 💡 Альтернатива: передать в core

Можно добавить параметр `min_score` в `PeeweeVectorStore._vector_search()`:

```sql
WHERE vec_distance_cosine(...) <= (1 - ?)  -- min_score
```

Но это требует изменений в ядре. Для Flask MVP проще фильтровать в сервисе.

---

## 🧪 Тесты

```python
def test_search_min_score_filter(client):
    # Без фильтра
    response = client.get("/search/results?q=python&min_score=0")
    count_all = response.data.count(b"card")
    
    # С высоким порогом
    response = client.get("/search/results?q=python&min_score=80")
    count_filtered = response.data.count(b"card")
    
    assert count_filtered <= count_all
```

---

## 📊 Чеклист

- [ ] Range slider в search.html
- [ ] JavaScript для отображения значения
- [ ] HTMX include обновлён
- [ ] Route обрабатывает `min_score`
- [ ] Service фильтрует результаты
- [ ] Тесты написаны
