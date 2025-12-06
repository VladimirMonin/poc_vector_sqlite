
[Image of reusable software component diagram]

Вот детальный, технический план для **Фазы 13.1**. Он написан так, чтобы ты мог скормить его Агенту, и тот однозначно понял задачу.

Здесь мы устраняем фундаментальный архитектурный баг: **Mismatch гранулярности** (Vector ищет абзацы, FTS ищет файлы).

---

# 🛠️ Phase 13.1: FTS Refactoring (Chunk-Level Search)

**Цель:** Перевести полнотекстовый поиск (FTS) с уровня Документов на уровень Чанков.
**Зачем:** Чтобы Гибридный поиск (RRF) работал корректно. Сейчас он пытается слить ранги "файлов" и "абзацев", что математически невозможно и дает плохой результат.

---

## 🧠 Архитектурное изменение

### Было (Проблема)

**Файл:** `semantic_core/infrastructure/storage/peewee/adapter.py`

**Vector Search (строка 314-390):**

```python
def _vector_search(...):
    sql = """
        SELECT c.id as chunk_id, c.document_id, vec_distance_cosine(cv.embedding, ?) as distance
        FROM chunks_vec cv
        JOIN chunks c ON c.id = cv.id
        JOIN documents d ON d.id = c.document_id
        ...
    """
    # Возвращает: SearchResult(chunk_id=42, document=..., score=0.75)
```

### 1. Обновление Схемы БД (`infrastructure/storage/peewee/models.py`)

**Текущее состояние:**

- Файл содержит `DocumentModel`, `ChunkModel`, `BatchJobModel`, `MediaTaskModel`
- Нет FTS моделей (они создаются через raw SQL в `adapter.py`)

**Задача:**
Добавить класс `ChunkFTS` после `ChunkModel` (строка ~180).

```python
class ChunkFTS(BaseModel):
    """Virtual Table для полнотекстового поиска по чанкам.
    
    Использует FTS5 для быстрого поиска текста внутри чанков.
    rowid в этой таблице соответствует id в таблице chunks.
    
#### А. Метод `ensure_schema_compatibility()` (Создание таблиц)

**Текущий код (строка 137-176):**
```python
# Создаёт documents_fts через триггеры
cursor.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts
    USING fts5(content, content='documents', content_rowid='id')
""")
# Триггеры на INSERT/UPDATE/DELETE для автосинхронизации
```

**Изменение:**

1. **Удалить** создание `documents_fts` и все триггеры (строки 137-176).
2. **Добавить** создание `chunks_fts`:

```python
cursor.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
    USING fts5(
        content,           -- текст чанка
        metadata_text,     -- метаданные в текстовом виде
        content='chunks',  -- связь с таблицей chunks
        content_rowid='id' -- rowid = chunks.id
    )
""")
```

3. **Добавить триггеры** для автосинхронизации `chunks` ↔ `chunks_fts`:

```python
# INSERT trigger
CREATE TRIGGER IF NOT EXISTS chunks_fts_insert
AFTER INSERT ON chunks
BEGIN
    INSERT INTO chunks_fts(rowid, content, metadata_text)
    VALUES (new.id, new.content, new.metadata);
END;

# UPDATE trigger
CREATE TRIGGER IF NOT EXISTS chunks_fts_update
AFTER UPDATE ON chunks
BEGIN
    UPDATE chunks_fts
    SET content = new.content, metadata_text = new.metadata
    WHERE rowid = old.id;
END;

# DELETE trigger
CREATE TRIGGER IF NOT EXISTS chunks_fts_delete
AFTER DELETE ON chunks
BEGIN
    DELETE FROM chunks_fts WHERE rowid = old.id;
END;
```

**Важно:** Триггеры обеспечат автоматическую синхронизацию. Не нужно вручную писать в FTS при `save()`.
    class Meta:
        table_name = "chunks_fts"
        # FTS5 создаётся через SQL в adapter.py
        # Здесь только декларация для ORM

```

**Примечание:** Peewee не поддерживает FTS5 напрямую через ORM. Фактическое создание таблицы будет через `CREATE VIRTUAL TABLE` в `adapter.py:ensure_schema_compatibility()`.
    # Возвращает: SearchResult(document=..., score=0.20)
    # ⚠️ БЕЗ chunk_id!
```

**Hybrid Search (строка 465-580):**

```python
def _hybrid_search(...):
    sql = """
        WITH vector_results AS (
            SELECT c.document_id as doc_id, ROW_NUMBER() OVER (...) as rank
            FROM chunks_vec cv
            JOIN chunks c ON c.id = cv.id
            LIMIT 100
        ),
        fts_results AS (
            SELECT main.id as doc_id, ROW_NUMBER() OVER (...) as rank
            FROM documents_fts fts  # ← АГРЕГАЦИЯ ПО ДОКУМЕНТАМ!
            JOIN documents main ON main.id = fts.rowid
            LIMIT 100
        ),
#### Б. Метод `_fts_search()` (Поиск)

**Текущий код (строка 391-464):**
```python
def _fts_search(self, query_text: str, filters: Optional[dict], limit: int):
    sanitized_query = _sanitize_fts_query(query_text)
    
    sql = f"""
#### В. Метод `_hybrid_search()` (Слияние)

**Текущий код (строка 465-580):**
```python
def _hybrid_search(self, query_vector, query_text, filters, limit, k=60):
    sql = f"""
        WITH vector_results AS (
            SELECT 
                c.document_id as doc_id,  # ← АГРЕГАЦИЯ ПО ДОКУМЕНТАМ!
                ROW_NUMBER() OVER (ORDER BY vec_distance_cosine(cv.embedding, ?)) as rank
            FROM chunks_vec cv
            JOIN chunks c ON c.id = cv.id
            JOIN documents main ON main.id = c.document_id
            {where_clause}
            LIMIT 100
        ),
        fts_results AS (
            SELECT 
                main.id as doc_id,  # ← ДОКУМЕНТЫ!
                ROW_NUMBER() OVER (ORDER BY fts.rank) as rank
            FROM documents_fts fts
            JOIN documents main ON main.id = fts.rowid
            WHERE documents_fts MATCH ?
            {where_clause}
            LIMIT 100
        ),
        rrf_scores AS (
            SELECT 
                COALESCE(v.doc_id, f.doc_id) as doc_id,
                (COALESCE(1.0/(? + v.rank), 0.0) + COALESCE(1.0/(? + f.rank), 0.0)) as rrf_score
            FROM vector_results v
            FULL OUTER JOIN fts_results f ON v.doc_id = f.doc_id
        )
        SELECT doc_id, rrf_score FROM rrf_scores ORDER BY rrf_score DESC LIMIT ?
    """
    
    # Возвращает SearchResult с document, БЕЗ chunk_id
```

**Изменение:**

```python
def _hybrid_search(self, query_vector, query_text, filters, limit, k=60):
    sanitized_query = _sanitize_fts_query(query_text)
    blob = query_vector.tobytes()
    
    # Формируем WHERE для фильтров
    where_conditions = []
    where_params = []
    if filters:
        for key, value in filters.items():
            where_conditions.append(f"json_extract(d.metadata, '$.{key}') = ?")
            where_params.append(value)
    where_clause = f"AND {' AND '.join(where_conditions)}" if where_conditions else ""
    
    sql = f"""
        WITH vector_results AS (
            SELECT 
                cv.id as chunk_id,  # ← ЧАНКИ, НЕ ДОКУМЕНТЫ!
                ROW_NUMBER() OVER (ORDER BY vec_distance_cosine(cv.embedding, ?)) as rank
            FROM chunks_vec cv
            JOIN chunks c ON c.id = cv.id
            JOIN documents d ON d.id = c.document_id
            WHERE 1=1 {where_clause}
            LIMIT 100
        ),
        fts_results AS (
            SELECT 
                fts.rowid as chunk_id,  # ← ЧАНКИ!
                ROW_NUMBER() OVER (ORDER BY fts.rank) as rank
            FROM chunks_fts fts
            JOIN chunks c ON c.id = fts.rowid
            JOIN documents d ON d.id = c.document_id
            WHERE chunks_fts MATCH ?
            {f"AND {' AND '.join(where_conditions)}" if where_conditions else ""}
            LIMIT 100
        ),
        rrf_scores AS (
            SELECT 
                COALESCE(v.chunk_id, f.chunk_id) as chunk_id,  # ← СЛИЯНИЕ ПО chunk_id!
                (COALESCE(1.0/(? + v.rank), 0.0) + COALESCE(1.0/(? + f.rank), 0.0)) as rrf_score
            FROM vector_results v
            FULL OUTER JOIN fts_results f ON v.chunk_id = f.chunk_id
        )
        SELECT chunk_id, rrf_score FROM rrf_scores ORDER BY rrf_score DESC LIMIT ?
    """
    
    params = [blob] + where_params + [sanitized_query] + where_params + [k, k, limit]
    cursor = self.db.execute_sql(sql, params)
    results = []
    
    for row in cursor.fetchall():
        chunk_id, rrf_score = row
        
        # Загружаем чанк и документ
        chunk_model = ChunkModel.get_by_id(chunk_id)
        doc_model = DocumentModel.get_by_id(chunk_model.document_id)
        
        chunk = self._model_to_chunk(chunk_model)
        document = self._model_to_document(doc_model)
        
        results.append(ChunkResult(  # ← ChunkResult!
            chunk=chunk,
            document=document,
            score=rrf_score,
            match_type=MatchType.HYBRID,
        ))
    return results
```

**Ключевые изменения:**

1. Vector CTE: `cv.id as chunk_id` (было: `c.document_id as doc_id`)
2. FTS CTE: `FROM chunks_fts` (было: `FROM documents_fts`)
3. RRF JOIN: `ON v.chunk_id = f.chunk_id` (было: `ON v.doc_id = f.doc_id`)
4. **Теперь RRF видит пересечения!** Если оба метода нашли `chunk_42`, score будет `1/(60+rank_vec) + 1/(60+rank_fts)`
    """

    for row in cursor.fetchall():
        doc_id, rank = row
        doc_model = DocumentModel.get_by_id(doc_id)
        document = self._model_to_document(doc_model)

        results.append(SearchResult(
            document=document,
            score=abs(rank),
            match_type=MatchType.FTS,
        ))
    return results

```

**Изменение:**
```python
def _fts_search(self, query_text: str, filters: Optional[dict], limit: int):
    sanitized_query = _sanitize_fts_query(query_text)
    
    # Формируем WHERE для фильтров по метаданным документа
    where_conditions = []
    where_params = []
    if filters:
        for key, value in filters.items():
            where_conditions.append(f"json_extract(d.metadata, '$.{key}') = ?")
            where_params.append(value)
    where_clause = f"AND {' AND '.join(where_conditions)}" if where_conditions else ""
    
    sql = f"""
        SELECT 
            c.id as chunk_id,
            fts.rank
        FROM chunks_fts fts
        JOIN chunks c ON c.id = fts.rowid
        JOIN documents d ON d.id = c.document_id
        WHERE chunks_fts MATCH ?
        {where_clause}
        ORDER BY fts.rank
        LIMIT ?
    """
    
    params = [sanitized_query] + where_params + [limit]
    cursor = self.db.execute_sql(sql, params)
    results = []
    
    for row in cursor.fetchall():
        chunk_id, rank = row
        
        # Загружаем чанк и документ
        chunk_model = ChunkModel.get_by_id(chunk_id)
        doc_model = DocumentModel.get_by_id(chunk_model.document_id)
        
        chunk = self._model_to_chunk(chunk_model)
        document = self._model_to_document(doc_model)
        
        results.append(ChunkResult(  # ← Теперь ChunkResult!
            chunk=chunk,
            document=document,
            score=abs(rank),
            match_type=MatchType.FTS,
        ))
    return results
```

**Ключевые изменения:**

1. `FROM chunks_fts` вместо `documents_fts`
2. `JOIN chunks c ON c.id = fts.rowid` (связь через rowid)
3. Возвращаем `ChunkResult` вместо `SearchResult`

   # ⚠️ ПРОБЛЕМА: Схлопывает 10 релевантных чанков в 1 doc_id

   # ⚠️ FTS видит весь документ (1000 слов), а вектор — абзац (50 слов)

   # ⚠️ RRF не видит пересечений на уровне чанков

```

**Результат тестирования (Phase 13):**
```

Query: "гибридный поиск RRF"
Vector Score: 0.75 (нашёл chunk_42)
FTS Score: 0.20 (нашёл весь document_5, содержащий 50 чанков)
Hybrid Score: 0.016 ← ПРОВАЛ!

```

**Причина:** Vector возвращает `chunk_id=42`, FTS возвращает `doc_id=5`. RRF не может сопоставить — это разные сущности.

---

### Станет (Решение)

* **Vector Index:** Таблица `chunks_vec` (без изменений).
* **FTS Index:** Новая таблица **`chunks_fts`** (вместо `documents_fts`).
* **Результат:** Оба поиска возвращают `chunk_id`. RRF видит пересечения и бустит релевантные чанки.

**Ожидаемый результат после фикса:**
```

Query: "гибридный поиск RRF"
Vector Score: 0.75 (chunk_42)
FTS Score: 0.85 (chunk_42) ← ТОТ ЖЕ ЧАНК!
Hybrid Score: 0.85+ ← БУСТ от RRF!

```

---

## 📋 План реализации

### 1. Обновление Схемы БД (`infrastructure/storage/peewee/models.py`)

Необходимо добавить модель для FTS индекса чанков.

**Задача:**
Добавить класс `ChunkFTS` (Virtual Table using FTS5).

* **Поля:**
  * `content`: Текст чанка (для поиска).
  * `meta_blob`: Текстовое представление метаданных (чтобы искать по заголовкам/путям).
* **Опции:** Использовать `FTS5Model`, токенайзер `porter` или `trigram` (если есть, иначе стандартный).

### 2. Обновление Адаптера (`infrastructure/storage/peewee/adapter.py`)

Нужно изменить логику записи и поиска.

#### А. Метод `save()` (Запись)

Сейчас он пишет в `documents_fts`.
**Изменение:**

1. При сохранении списка чанков, массово писать их текст в `chunks_fts`.
2. `rowid` в FTS таблице должен совпадать с `id` в таблице `chunks`.

#### Б. Метод `_fts_search()` (Поиск)

Сейчас он делает `SELECT ... FROM documents_fts`.
**Изменение:**

1. Переписать запрос на `SELECT rowid, rank FROM chunks_fts WHERE chunks_fts MATCH ?`.
2. Возвращать список `ChunkResult`, подгружая данные из основной таблицы `chunks` по `rowid`.

#### В. Метод `_hybrid_search()` (Слияние)

Сейчас он пытается мапить DocID на ChunkID (или игнорирует это).
**Изменение:**

1. Упростить логику. Теперь у нас два списка `ChunkID` (от вектора и от FTS).
2. Алгоритм RRF остается тем же, но теперь он будет реально находить пересечения ID.

---

## 🧪 3. Миграция и Совместимость

**Проблема:** Старая база содержит `documents_fts`, новая логика требует `chunks_fts`.

**Стратегия миграции:**

### Вариант А: Пересоздание базы (Dev-режим)
```bash
# Удалить старую базу
rm semantic.db

# Переиндексировать
## 🔍 4. Критерии Приемки (Verification)

### Тест 1: Запрос с точным термином (FTS должен найти)

**Запрос:** `"Reciprocal Rank Fusion"`

**До фикса:**
```python
results = core.search("Reciprocal Rank Fusion", mode="hybrid", limit=5)

# Ожидаемый результат:
---

## 📋 Чек-лист реализации

### Этап 1: Схема БД
- [ ] Добавить класс `ChunkFTS` в `models.py` (строка ~180)
- [ ] Удалить создание `documents_fts` из `ensure_schema_compatibility()` (строка 137-176)
- [ ] Добавить создание `chunks_fts` через `CREATE VIRTUAL TABLE`
- [ ] Добавить триггеры INSERT/UPDATE/DELETE для автосинхронизации

### Этап 2: Адаптер (Поиск)
- [ ] Переписать `_fts_search()`: FROM chunks_fts, return ChunkResult (строка 391-464)
- [ ] Переписать `_hybrid_search()`: JOIN по chunk_id, return ChunkResult (строка 465-580)
- [ ] Проверить экранирование FTS через `_sanitize_fts_query()` (строка 35)

### Этап 3: Миграция
- [ ] Добавить автомиграцию в `ensure_schema_compatibility()` (массовая вставка)
- [ ] Добавить проверку в `semantic doctor` (пустая chunks_fts при полной chunks)

### Этап 4: Тесты
- [ ] Запустить `tests/integration/search/test_fts_chunk_level.py`
- [ ] Проверить метрику: `hybrid_score > vector_score`
- [ ] Проверить отсутствие регрессии по времени выполнения

### Этап 5: Документация
- [ ] Обновить `doc/architecture/18_granular_search.md` (упомянуть chunks_fts)
- [ ] Добавить миграционную заметку в `CHANGELOG.md`

---

## 🎯 Финальная проверка

**Команда:**
```bash
# 1. Пересоздать базу
rm semantic.db

# 2. Индексировать тестовые данные
semantic ingest doc/architecture/05_hybrid_search_rrf.md

# 3. Поиск по точному термину
semantic search "Reciprocal Rank Fusion" --mode hybrid --limit 5

# 4. Проверить score
# Ожидаемый результат:
# ┌─────────┬─────────────────────────────────┬───────┬──────────┐
# │ Rank    │ Content (first 50 chars)        │ Score │ Type     │
# ├─────────┼─────────────────────────────────┼───────┼──────────┤
# │ 1       │ Reciprocal Rank Fusion — алго...│ 0.92  │ HYBRID   │
# │ 2       │ Формула RRF: score = 1/(k+ran...│ 0.78  │ VECTOR   │
# └─────────┴─────────────────────────────────┴───────┴──────────┘

# Критерий успеха: HYBRID score > VECTOR score
```

**Python API:**

```python
from semantic_core import SemanticCore

core = SemanticCore()
results = core.search("Reciprocal Rank Fusion", mode="hybrid", limit=5)

# Проверка типов
assert all(isinstance(r, ChunkResult) for r in results)
assert all(r.chunk.id is not None for r in results)

# Проверка буста
hybrid_score = results[0].score
vector_results = core.search("Reciprocal Rank Fusion", mode="vector", limit=5)
vector_score = vector_results[0].score

assert hybrid_score > vector_score, "Hybrid должен бустить найденные оба методами чанки"
print(f"✅ Буст работает: {hybrid_score:.2f} > {vector_score:.2f}")
```

# Vector: chunk_42 (score=0.75)

# FTS: chunk_42 (score=0.85) ← ТОТ ЖЕ ЧАНК

# Hybrid: chunk_42 (score=0.92+) ← БУСТ от RRF: 1/(60+1) + 1/(60+1)

```

**Критерий успеха:** `hybrid_score > vector_score`

---

### Тест 2: Запрос с несколькими терминами

**Запрос:** `"гибридный поиск sqlite-vec"`

**Ожидаемое поведение:**
1. Vector находит 3 чанка с близкой семантикой (0.72, 0.68, 0.65)
2. FTS находит 2 чанка с точным совпадением "sqlite-vec" (rank=-2.5, -3.1)
3. Hybrid бустит чанки, найденные обоими методами

**Проверка:**
```python
# Чанк, найденный ОБОИМИ методами, должен быть на 1 месте
assert results[0].match_type == MatchType.HYBRID
assert results[0].score > results[1].score  # Буст от RRF
```

---

### Тест 3: Производительность (регрессия не допустима)

**Метрика:** Время выполнения гибридного поиска.

**До фикса:**

```
Hybrid search (100 chunks): ~45ms
```

**После фикса:**

```
Hybrid search (100 chunks): ~40ms
# Может быть БЫСТРЕЕ, т.к. FTS теперь ищет по меньшим текстам (чанки, а не документы)
```

**Критерий:** Время не должно вырасти > 20%.

---

### Тест 4: Корректность структуры результатов

**Проверка типов:**

```python
results = core.search("test", mode="fts", limit=5)

# До фикса:
assert isinstance(results[0], SearchResult)
assert results[0].chunk_id is None  # ❌

# После фикса:
assert isinstance(results[0], ChunkResult)  # ✅
assert results[0].chunk.id is not None  # ✅
assert results[0].document.id is not None  # ✅
```

---

### Автоматический тест (pytest)

**Файл:** `tests/integration/search/test_fts_chunk_level.py`

```python
def test_hybrid_search_chunk_level_boost(semantic_core):
    """Проверяет, что гибридный поиск бустит чанки, найденные обоими методами."""
    
    # Индексируем документ с уникальным термином
    doc = Document(
        content="# RRF Algorithm\n\nReciprocal Rank Fusion is a method...",
        metadata={"source": "test.md"}
    )
    semantic_core.ingest(doc)
    
    # Поиск по точному термину
    vector_results = semantic_core.search("Reciprocal Rank Fusion", mode="vector", limit=5)
    fts_results = semantic_core.search("Reciprocal Rank Fusion", mode="fts", limit=5)
    hybrid_results = semantic_core.search("Reciprocal Rank Fusion", mode="hybrid", limit=5)
    
    # Проверка: Vector и FTS нашли один и тот же чанк
    assert vector_results[0].chunk.id == fts_results[0].chunk.id
    
    # Проверка: Hybrid score выше, чем у каждого по отдельности
    assert hybrid_results[0].score > vector_results[0].score
    assert hybrid_results[0].score > fts_results[0].score
    
    # Проверка: Hybrid нашёл тот же чанк
    assert hybrid_results[0].chunk.id == vector_results[0].chunk.id
```

    """Проверяет наличие chunks_fts таблицы."""
    cursor = db.execute_sql("SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_fts'")
    if not cursor.fetchone():
        console.print("[yellow]⚠️  Таблица chunks_fts не найдена[/yellow]")
        console.print("[dim]Рекомендация: Запустите `semantic ingest --reindex` для миграции[/dim]")
        return False
    
    # Проверка: есть chunks, но пустая chunks_fts?
    chunks_count = ChunkModel.select().count()
    fts_count = db.execute_sql("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
    
    if chunks_count > 0 and fts_count == 0:
        console.print("[red]❌ chunks_fts пустая, но chunks содержит {chunks_count} записей[/red]")
        console.print("[dim]Триггеры не сработали. Выполните reindex.[/dim]")
        return False
    
    console.print(f"[green]✅ FTS индекс синхронизирован ({fts_count} чанков)[/green]")
    return True

```

### Вариант В: Автоматическая миграция в `ensure_schema_compatibility()`

**Файл:** `semantic_core/infrastructure/storage/peewee/adapter.py`

**Добавить после создания `chunks_fts` (строка ~176):**
```python
# Проверка: если chunks_fts пуста, но chunks полна — триггер ретроактивно
cursor.execute("SELECT COUNT(*) FROM chunks")
chunks_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM chunks_fts")
fts_count = cursor.fetchone()[0]

if chunks_count > 0 and fts_count == 0:
    logger.warning(
        "FTS index is empty, populating from existing chunks",
        chunks_count=chunks_count,
    )
    # Массовая вставка
    cursor.execute("""
        INSERT INTO chunks_fts(rowid, content, metadata_text)
        SELECT id, content, metadata FROM chunks
    """)
    logger.info("FTS index populated", fts_count=chunks_count)
```

**Рекомендация:** Использовать Вариант В (автомиграция) + Вариант Б (проверка в doctor).

---

## 🔍 4. Критерии Приемки (Verification)

После реализации нужно прогнать **тот же самый тест**, который мы делали в Фазе 13.

**Ожидаемый результат в `03_search_quality.md`:**

1. Запрос: `"[FTS] RRF гибридный поиск"` (или специфичный термин).
2. **Vector Score:** ~0.75 (как было).
3. **Hybrid Score:** Должен стать **ВЫШЕ**, чем Vector Score (например, 0.8+), или хотя бы не 0.016.
    - *Почему:* Потому что FTS теперь тоже найдет этот чанк, и `1/k + 1/k` даст буст.

---

### Инструкция для Агента

> "Выполни Фазу 13.1.
>
> 1. Создай модель `ChunkFTS` в `models.py`.
> 2. В `PeeweeVectorStore` обнови методы `save` (запись в FTS) и `_fts_search` (чтение из FTS чанков).
> 3. Убедись, что FTS запрос экранируется (используй фикс из Фазы 13).
> 4. Запусти `test_search_audit.py` и покажи, что Hybrid Score вырос."
