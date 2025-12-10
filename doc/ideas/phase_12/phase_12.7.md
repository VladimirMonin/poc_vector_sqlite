# Phase 12.7: FTS Index Synchronization

**Статус:** 📋 СПЕЦИФИКАЦИЯ  
**Дата:** 2025-12-05  
**Зависимость:** Phase 12.6  
**Цель:** Убедиться что FTS индекс синхронизирован и полнотекстовый поиск работает

---

## 📋 Описание проблемы

Полнотекстовый поиск (FTS) не находит документы. Например, поиск "год" не находит "Поздравляю с наступающим Новым годом".

**Возможные причины:**

1. `chunks_fts` таблица пуста
2. Триггеры не сработали для старых документов
3. Flask использует другую БД чем CLI

---

## 🔍 Диагностика

### 1. Проверить количество записей

```sql
SELECT COUNT(*) FROM chunks;      -- должно быть > 0
SELECT COUNT(*) FROM chunks_fts;  -- должно быть = chunks
```

### 2. Проверить содержимое FTS

```sql
SELECT rowid, content FROM chunks_fts LIMIT 5;
```

### 3. Проверить MATCH

```sql
SELECT * FROM chunks_fts WHERE chunks_fts MATCH 'год';
```

---

## 🔧 Задачи

### 1. Добавить проверку при старте Flask

**Файл:** `app/extensions.py`

```python
def _ensure_fts_populated(db):
    """Проверить и заполнить FTS индекс если нужно."""
    cursor = db.execute_sql("SELECT COUNT(*) FROM chunks")
    chunks_count = cursor.fetchone()[0]
    
    cursor = db.execute_sql("SELECT COUNT(*) FROM chunks_fts")
    fts_count = cursor.fetchone()[0]
    
    if chunks_count > 0 and fts_count == 0:
        logger.warning(f"⚠️ FTS index empty, populating {chunks_count} chunks...")
        db.execute_sql("""
            INSERT INTO chunks_fts(rowid, content)
            SELECT id, content FROM chunks
        """)
        logger.info(f"✅ FTS index populated: {chunks_count} chunks")
    elif chunks_count != fts_count:
        logger.warning(f"⚠️ FTS mismatch: chunks={chunks_count}, fts={fts_count}, rebuilding...")
        db.execute_sql("DELETE FROM chunks_fts")
        db.execute_sql("""
            INSERT INTO chunks_fts(rowid, content)
            SELECT id, content FROM chunks
        """)
        logger.info(f"✅ FTS index rebuilt: {chunks_count} chunks")
```

Вызвать после `init_peewee_database()`.

---

### 2. Проверить путь к БД

**Проблема:** Flask может использовать `vector_store.db` (из `.env`), а CLI — `semantic.db` (из `semantic.toml`).

**Файлы:**

- `.env` — `SQLITE_DB_PATH=./vector_store.db`
- `semantic.toml` — `[database] path = "./semantic.db"`
- `semantic_core/config.py` — приоритет env → toml

**Решение:** Унифицировать путь или добавить warning в Flask.

---

### 3. Добавить команду rebuild-fts

**Файл:** CLI `semantic_core/cli/commands/`

```bash
semantic db rebuild-fts
```

---

## 🧪 Тесты

```python
def test_fts_search_works(client, db_with_data):
    """FTS поиск находит документы по ключевым словам."""
    response = client.get("/search/results?q=год&mode=fts")
    assert b"Поздравляю" in response.data or response.status_code == 200
```

---

## 📊 Чеклист

- [ ] Диагностика: проверить counts
- [ ] `_ensure_fts_populated()` добавлен
- [ ] Путь к БД унифицирован
- [ ] Ребилд FTS работает
- [ ] Поиск "год" находит документы
