# 69. Result Type Abstraction: Чанки vs Документы

> **Эпизод о том, как один toggle изменил архитектуру сервиса**

---

## 🎬 Сценарий

Пользователь ищет "async programming". Что он хочет увидеть?

**Вариант A — Чанки:**
```
├── chunk_1: "async/await syntax in Python..."  (doc_1, score: 95%)
├── chunk_2: "asyncio event loop..."            (doc_1, score: 92%)
├── chunk_3: "concurrent.futures vs asyncio..." (doc_2, score: 88%)
└── chunk_4: "async context managers..."        (doc_1, score: 85%)
```

**Вариант B — Документы:**
```
├── doc_1: "Python Async Guide"      (3 chunks matched, score: 95%)
└── doc_2: "Concurrency Patterns"    (1 chunk matched, score: 88%)
```

Оба варианта полезны. Нужен **переключатель**.

---

## 🏗️ Архитектура решения

### Два метода в SemanticCore

```python
# search_chunks() — гранулярный поиск
chunks = core.search_chunks(query="async", limit=10)
# → list[ChunkResult] — отдельные чанки

# search() — агрегация по документам
docs = core.search(query="async", limit=10)
# → list[SearchResult] — документы с лучшим чанком
```

### Два DTO в сервисе

```python
@dataclass
class SearchResultItem:
    """UI-friendly чанк."""
    chunk_id: int
    title: str
    content: str
    score_percent: int
    chunk_type: str
    ...

@dataclass  
class DocumentResultItem:
    """UI-friendly документ."""
    doc_id: int
    title: str
    description: Optional[str]
    score_percent: int
    chunk_count: int  # сколько чанков совпало
    tags: list[str]
    ...
```

---

## 🎨 UI: Toggle Pattern

### HTML — Radio Button Group

```html
<div class="btn-group btn-group-sm w-100" role="group">
    <input type="radio" class="btn-check" 
           name="result_type" id="result-chunks" 
           value="chunks" checked>
    <label class="btn btn-outline-primary" for="result-chunks">
        📄 Чанки
    </label>
    
    <input type="radio" class="btn-check" 
           name="result_type" id="result-documents" 
           value="documents">
    <label class="btn btn-outline-primary" for="result-documents">
        📁 Документы
    </label>
</div>
```

### HTMX — Включаем в запрос

```html
<input 
    type="search"
    hx-get="/search/results"
    hx-include="#search-options, [name='result_type']"
    hx-target="#search-results"
>
```

### JavaScript — Получаем выбор

```javascript
function getResultType() {
    const selected = document.querySelector('input[name="result_type"]:checked');
    return selected ? selected.value : 'chunks';
}
```

---

## 🔧 Backend: Route Branching

```python
@bp.route("/results")
def results():
    query = request.args.get("q", "").strip()
    result_type = request.args.get("result_type", "chunks")
    mode = request.args.get("mode", "hybrid")
    limit = int(request.args.get("limit", 10))
    
    service = current_app.extensions["search_service"]
    
    if result_type == "documents":
        # Агрегация по документам
        results = service.search_documents(
            query=query, 
            mode=mode, 
            limit=limit
        )
        template = "partials/search_documents.html"
    else:
        # Гранулярные чанки
        results = service.search(
            query=query,
            mode=mode,
            limit=limit
        )
        template = "partials/search_results.html"
    
    return render_template(template, results=results, query=query)
```

---

## 📊 Score Normalization

RRF (Reciprocal Rank Fusion) даёт score в диапазоне `1/(k+rank)`:
- rank=1, k=60 → score = 0.0164
- rank=5, k=60 → score = 0.0154

**Проблема:** `0.016 × 100 = 1.6%` — не информативно.

**Решение:** нормализация к 0-100%

```python
def _normalize_rrf_score(score: float, max_score: float = 0.033) -> int:
    """
    Нормализует RRF score (обычно 0.01-0.033) в проценты 0-100.
    
    Args:
        score: RRF score от гибридного поиска
        max_score: Теоретический максимум (1/(k+1) при k=30)
    
    Returns:
        Процент 0-100, где 100 = идеальное совпадение
    """
    if score <= 0:
        return 0
    normalized = min(score / max_score, 1.0)
    return int(normalized * 100)
```

| Raw Score | Normalized |
|-----------|------------|
| 0.033     | 100%       |
| 0.020     | 60%        |
| 0.016     | 48%        |
| 0.010     | 30%        |

---

## 🖼️ Templates: Две карточки

### Чанк (существующий)

```html
<div class="card search-result-card">
    <div class="card-body">
        <span class="badge">{{ item.chunk_type }}</span>
        <span class="badge">{{ item.score_percent }}%</span>
        <h6>{{ item.title }}</h6>
        <p class="text-muted small">{{ item.content[:200] }}</p>
    </div>
</div>
```

### Документ (новый)

```html
<div class="card document-card">
    <div class="card-body">
        <div class="d-flex justify-content-between">
            <h5>📁 {{ item.title }}</h5>
            <span class="badge bg-success">{{ item.score_percent }}%</span>
        </div>
        {% if item.description %}
        <p class="text-muted">{{ item.description }}</p>
        {% endif %}
        <div class="mt-2">
            {% for tag in item.tags %}
            <span class="badge bg-secondary">{{ tag }}</span>
            {% endfor %}
        </div>
    </div>
</div>
```

---

## 🧪 Тесты

```python
class TestResultTypeToggle:
    def test_chunks_mode_returns_chunk_items(self, service):
        results = service.search("python", mode="hybrid")
        assert all(isinstance(r, SearchResultItem) for r in results)
    
    def test_documents_mode_returns_document_items(self, service):
        results = service.search_documents("python", mode="hybrid")
        assert all(isinstance(r, DocumentResultItem) for r in results)
    
    def test_score_normalization(self):
        assert _normalize_rrf_score(0.033) == 100
        assert _normalize_rrf_score(0.016) == 48
        assert _normalize_rrf_score(0.0) == 0
```

---

## 🎓 Паттерны

### 1. Result Type Pattern
Один endpoint, разные DTO — переключение через параметр.

### 2. Template Branching
Одна логика маршрутизации → разные шаблоны.

### 3. Score Normalization
Сырые значения алгоритма → человекочитаемые проценты.

---

## 🔗 Связанные эпизоды

- [04. Search Types](04_search_types.md) — типы поиска
- [05. Hybrid Search RRF](05_hybrid_search_rrf.md) — откуда RRF scores
- [57. Search Interface](57_search_interface.md) — UI поиска
- [68. Embedding Cache](68_embedding_cache_integration.md) — кеширование
