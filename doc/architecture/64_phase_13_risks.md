# ⚠️ Phase 13: Риски и ограничения

> Что может сломаться в production

---

## 🚨 Критические риски

### 1. Long Video Processing — Exponential Time Growth

**Текущие данные:**

| Длительность | Размер файла | Время обработки | Frames |
|-------------|--------------|-----------------|--------|
| 30 сек | 5.3MB | **13 сек** | 5 frames |
| 30 сек | 890KB | **4.3 сек** | 5 frames |

**Экстраполяция на длинные видео:**

```
Формула: T = frame_extraction + (frames × gemini_request) + audio_analysis
```

| Видео | Frames (1fps) | Time | Риск |
|-------|---------------|------|------|
| 5 минут | 30 frames | **~90 сек** | ⚠️ Slow |
| 30 минут | 180 frames | **~9 минут** | 🔥 Timeout |
| 1 час | 360 frames | **~18 минут** | 💀 FAIL |

**Почему опасно:**

1. **Request Timeout:** HTTP timeout обычно 30-60 сек
2. **Memory Growth:** 360 frames × 1920px = **~2GB RAM**
3. **API Costs:** 360 Gemini Vision requests = **$$$**
4. **User Experience:** 18 минут ожидания = abandoned operation

**Решения:**

```python
# Option 1: Adaptive sampling
if duration > 5_minutes:
    frame_rate = 0.1  # 1 frame per 10 sec
elif duration > 30_minutes:
    frame_rate = 0.033  # 1 frame per 30 sec

# Option 2: Background processing
await queue_manager.add_task(video_path, priority="low")

# Option 3: Streaming analysis
async for frame_batch in extract_frames(video, batch_size=10):
    await analyze_batch(frame_batch)
```

---

### 2. Document-Level Search Отсутствует

**Проблема:**

```python
# ❌ Невозможно найти весь документ
results = semantic_core.search("find article about Python", mode="hybrid")
# Возвращает: chunks, а не documents

# ✅ Ожидаемое поведение
results = semantic_core.search_documents("Python guide")
# Возвращает: полный nested_headers_example.md
```

**Последствия:**

1. **RAG Context Loss:** LLM получает разрозненные chunks без document structure
2. **User Confusion:** "Я искал статью, а получил 10 фрагментов"
3. **Duplicate Content:** Один document → 5 chunks → 5 results в топе

**Текущий workaround:**

```python
# Пользователь должен вручную группировать
results = semantic_core.search("query", limit=50)
docs = group_by_document_id(results)  # ❌ Not implemented
```

**Нужно:**

```python
class SearchResult:
    document_id: int
    document_title: str  # NEW
    relevant_chunks: List[Chunk]  # Grouped
    best_score: float
```

---

### 3. FTS5 Granularity Mismatch

**Архитектурная проблема:**

```
┌──────────────┐
│ Vector Search│──> Returns CHUNK IDs
└──────────────┘
        │
        ├─ RRF Merge ─┐
        │              │
┌──────────────┐       ▼
│ FTS5 Search  │──> Returns DOCUMENT IDs ❌
└──────────────┘
```

**Пример неправильного merge:**

```python
vector_results = [
    (chunk_id=18, score=0.75),
    (chunk_id=19, score=0.72),
]

fts_results = [
    (doc_id=2, score=1.0),  # ❌ Разные entities!
]

# RRF пытается merge:
rrf_score(chunk_18) = ???  # chunk не в fts_results
rrf_score(doc_2) = ???     # doc не в vector_results
```

**Почему происходит:**

```python
# semantic_core/integrations/peewee/search_proxy.py

# FTS ищет по documents
fts_query = """
SELECT doc_id FROM documents_fts
WHERE documents_fts MATCH ?
"""

# Vector ищет по chunks
vector_query = """
SELECT chunk_id, vec_distance(embedding, ?)
FROM vec_chunks
"""

# Merge невозможен корректно ❌
```

**Решения:**

```python
# Option 1: Chunk-level FTS (нужен chunks_fts виртуальная таблица)
CREATE VIRTUAL TABLE chunks_fts USING fts5(content, chunk_id);

# Option 2: Document-level Vector (агрегировать chunk embeddings)
doc_embedding = mean([chunk1.vec, chunk2.vec, ...])

# Option 3: Two-stage search
stage1 = fts_search(query) → doc_ids
stage2 = vector_search(query, filter=doc_ids) → chunks
```

---

### 4. Duplicate Chunks — Storage Waste

**Обнаружено в аудите:**

```sql
-- Same content, different IDs
doc_id=1, content="Семантический поиск..."  -- metadata: {"type": "plain_text"}
doc_id=7, content="Семантический поиск..."  -- metadata: {"category": "text"}
```

**Статистика:**

```
127 chunks created
~15 duplicates detected (12% waste)
15 × 768 floats = 46KB wasted embeddings
15 × Gemini API calls = $0.0015 wasted
```

**Масштаб проблемы:**

| Corpus Size | Duplicate Rate | Wasted Storage | Wasted API $ |
|-------------|----------------|----------------|--------------|
| 10K chunks | 12% | 3.6MB | $0.12 |
| 100K chunks | 12% | 36MB | $1.20 |
| 1M chunks | 12% | 360MB | $12.00 |

**Причины:**

1. **Test Data Artifacts:** Тесты создают multiple documents с одинаковым content
2. **No Deduplication Strategy:** Система не проверяет duplicates при ingestion
3. **Metadata Variations:** `{"type": "text"}` vs `{"category": "text"}` → разные records

**Решения:**

```python
# Option 1: Content hash
content_hash = hashlib.sha256(chunk.content.encode()).hexdigest()
# Проверяем перед вставкой:
if Chunk.select().where(Chunk.content_hash == content_hash).exists():
    skip_or_update()

# Option 2: Unique constraint
class Chunk(Model):
    content = TextField()
    content_hash = CharField(unique=True, index=True)

# Option 3: Merge metadata
# Если content одинаковый, но metadata разная → merge в один record
```

---

## 🔧 Технические ограничения

### 1. Token Limits — Context Window

**Gemini limits:**

| Model | Max Input | Max Output | Total |
|-------|-----------|------------|-------|
| `gemini-2.5-flash-lite` | 1M tokens | 8K tokens | 1M |
| `gemini-2.5-flash` | 1M tokens | 8K tokens | 1M |
| `gemini-2.5-pro` | 2M tokens | 8K tokens | 2M |

**Проблема для RAG:**

```python
# RAG context construction
context = "\n\n".join([chunk.content for chunk in top_10_results])
# Если каждый chunk ~1000 tokens → 10K total ✅

# Но если top_50_results:
context = "\n\n".join([chunk.content for chunk in top_50_results])
# 50 × 1000 = 50K tokens ✅ Still OK

# Danger zone:
context = full_document  # 200K tokens → OK
context = all_related_docs  # 1.5M tokens → ❌ FAIL for flash-lite
```

**Mitigation:**

```python
# semantic_core/core/rag.py
def _build_context(chunks: List[Chunk], max_tokens: int = 100_000):
    total = 0
    selected = []
    for chunk in chunks:
        tokens = estimate_tokens(chunk.content)
        if total + tokens > max_tokens:
            break
        selected.append(chunk)
        total += tokens
    return selected
```

---

### 2. Rate Limiting — RPM/TPM

**Текущие limits (предполагаемые):**

```python
# infrastructure/gemini/rate_limiter.py
TokenBucket(
    rpm=15,      # Requests Per Minute
    tpm=1_000_000  # Tokens Per Minute (Flash Lite)
)
```

**Bottleneck scenarios:**

```python
# Scenario 1: Bulk ingestion
documents = load_corpus(1000_files)  # 1000 files
chunks = chunker.split_all(documents)  # 50K chunks
embeddings = [embedder.embed(c) for c in chunks]
# 50K requests ÷ 15 RPM = 3333 minutes = 55 HOURS ❌
```

**Real limits могут быть:**

| Tier | RPM | TPM | Daily Quota |
|------|-----|-----|-------------|
| Free | 15 | 32K | 1500 req |
| Paid | 1000 | 4M | Unlimited |

**Решение:**

```python
# Use Batch API for bulk
batch_manager.submit_batch(chunks, priority="low")
# Process in background, receive results in 1-24 hours
# Cost: 50% cheaper ✅
```

---

### 3. SQLite Limitations

**Known issues:**

```python
# 1. No concurrent writes
# ❌ Two processes trying to INSERT simultaneously → SQLITE_LOCKED

# 2. Vec0 index size
# Vector index = chunks × 768 floats × 4 bytes
# 100K chunks = 307MB index (in-memory during queries)

# 3. FTS5 memory
# Full-text index может быть 50-100% от corpus size
```

**Production recommendations:**

```python
# Option 1: WAL mode (better concurrency)
db.execute_sql("PRAGMA journal_mode=WAL")

# Option 2: Batch writes
with db.atomic():
    Chunk.bulk_create(chunks, batch_size=100)

# Option 3: Read replicas
# Master: writes
# Replicas: reads (search queries)
```

---

## 📉 Performance Degradation Points

### 1. Chunking Slowdown на больших файлах

**Текущие данные:**

```
Small files (2KB):  ~2 сек per file
Medium files (5KB): ~4 сек per file
Large files (50KB): ~40 сек per file (экстраполяция)
```

**Причина:**

```python
# processing/parsers/markdown_node_parser.py
def parse(content: str) -> List[Node]:
    ast = markdown_it.parse(content)  # O(n)
    nodes = traverse_ast(ast)  # O(n)
    enriched = enrich_nodes(nodes)  # O(n²) ❌
    return nodes
```

**Hotspot:** `enrich_nodes()` может быть O(n²) при большой вложенности.

---

### 2. Search Latency Growth

**Зависимость от corpus size:**

| Chunks | Vector Search | FTS5 Search | Hybrid | RRF Overhead |
|--------|---------------|-------------|--------|--------------|
| 100 | 50ms | 10ms | 60ms | +10ms |
| 1K | 100ms | 20ms | 120ms | +20ms |
| 10K | 500ms | 50ms | 600ms | +100ms |
| 100K | 2000ms | 200ms | 2500ms | +300ms |

**RRF overhead растёт** при merge большого количества results.

**Optimization:**

```python
# Limit intermediate results
vector_results = vector_search(query, limit=100)  # Not 10K
fts_results = fts_search(query, limit=100)
rrf_results = rrf_merge(vector_results, fts_results, top_k=10)
```

---

## 🛡️ Mitigation Strategies

### Priority Matrix

| Риск | Severity | Probability | Priority |
|------|----------|-------------|----------|
| Long video timeout | 🔥 High | Medium | **P0** |
| Hybrid search scores | 🔥 High | High | **P0** |
| Document-level search | ⚠️ Medium | High | **P1** |
| FTS granularity | ⚠️ Medium | Medium | **P1** |
| Duplicate chunks | 💰 Low | High | **P2** |
| Rate limiting | ⚠️ Medium | Low | **P2** |

### Recommended Fixes

**P0 (Immediate):**
1. Fix RRF score normalization
2. Add adaptive video frame sampling

**P1 (Before Production):**
3. Implement document-level search API
4. Align FTS5 to chunk-level OR switch vector to doc-level

**P2 (Nice to Have):**
5. Add content hash deduplication
6. Implement batch ingestion via Batch API

---

## 📚 Ключевые выводы

### ✅ Можно использовать в production:

- ✅ Chunking для **малых-средних файлов** (<50KB)
- ✅ Media analysis для **коротких видео** (<5 мин)
- ✅ Vector search (игнорируя hybrid)
- ✅ Rate limiting для **одиночных запросов**

### ❌ Нельзя использовать без фиксов:

- ❌ **Hybrid search** (некорректные скоры)
- ❌ **Длинные видео** (timeout risk)
- ❌ **Bulk ingestion** (RPM bottleneck)
- ❌ **Document-level retrieval** (API отсутствует)

### 🔄 Требует мониторинга:

- 📊 RRF score distribution (должны быть 0.6-0.9)
- 📊 Video processing time (должно быть <30 сек для 5 мин)
- 📊 Duplicate rate (должно быть <5%)
- 📊 Search latency (должно быть <500ms для 10K chunks)

---

**Next Step:** [Обновить 00_overview.md](#update-overview) с ссылками на главы 62-64.
