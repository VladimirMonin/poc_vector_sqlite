# 💾 Phase 2: Storage Layer

> **Статус:** ✅ ЗАВЕРШЕНА  
> **Цель:** Реализовать хранилище с гибридным поиском, RRF и фильтрацией

---

## 📖 Содержание фазы

### 11. Storage Layer: Peewee + RRF + Фильтры
**Файл:** [11_storage_layer_phase2.md](11_storage_layer_phase2.md)

Полная реализация `PeeweeVectorStore`:
- Vector search через `sqlite-vec`
- Full-text search через FTS5
- Гибридный поиск через Reciprocal Rank Fusion (RRF)
- Фильтрация по метаданным (source, tags, date range)
- Bulk operations для production

**Ключевые компоненты:**
- `PeeweeVectorStore` — реализация интерфейса `VectorStore`
- `DocumentModel` — ORM модель для документов
- `ChunkModel` — ORM модель для чанков с векторами
- RRF алгоритм для объединения результатов

---

## 🔍 RRF Formula

```python
score_rrf = sum(1 / (k + rank_i))
```

Где `k=60` (константа сглаживания), `rank_i` — позиция в i-м списке результатов.

---

## 🔗 Связанные фазы

- **Phase 1:** [SOLID Refactoring](../phase_1_solid/) — интерфейс VectorStore
- **Phase 3:** [Integration Layer](../phase_3_integration/) — SearchProxy поверх Storage
- **Phase 4:** [Smart Parsing](../phase_4_smart_parsing/) — granular search по чанкам

---

**← [Вернуться к оглавлению](../00_overview.md)**
