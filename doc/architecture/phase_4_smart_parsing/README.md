# 🧠 Phase 4: Smart Parsing & Granular Search

> **Статус:** ✅ ЗАВЕРШЕНА  
> **Цель:** AST-парсинг Markdown, изоляция кода, иерархический контекст

---

## 📖 Содержание фазы

### 15. Smart Parsing Architecture

**Файл:** [15_smart_parsing.md](15_smart_parsing.md)

AST-парсинг Markdown через `markdown-it-py`, `ChunkType` enum, иерархия заголовков и структурные метаданные.

**Возможности:**

- Детекция code blocks (` ```python ... ``` `)
- Извлечение breadcrumbs из заголовков
- Metadata: `language`, `heading_level`, `chunk_type`

---

### 16. Smart Splitting Strategy

**Файл:** [16_smart_splitting.md](16_smart_splitting.md)

Интеллектуальное разделение контента:

- **Изоляция кода:** отдельные chunks для code blocks
- **Группировка текста:** параграфы объединяются до `chunk_size`
- **Сохранение иерархии:** parent-child связи

**Параметры:**

- `chunk_size=1800` — для TEXT chunks
- `code_chunk_size=2000` — для CODE chunks

---

### 17. Hierarchical Context Strategy

**Файл:** [17_hierarchical_context.md](17_hierarchical_context.md)

Обогащение эмбеддингов breadcrumbs: от плоских чанков к структурному контексту.

**Пример breadcrumbs:**

```
Phase 4 > Smart Parsing > AST Architecture
```

Эмбеддинги учитывают: chunk content + parent context!

---

### 18. Granular Search & Storage Evolution

**Файл:** [18_granular_search.md](18_granular_search.md)

Поиск по индивидуальным чанкам, фильтрация по `chunk_type`/`language`, SQL оптимизация и `ChunkResult` API.

**Новые возможности:**

```python
results = storage.search(
    "SQLite transactions",
    chunk_type=ChunkType.CODE,
    language="python"
)
```

---

## 🔗 Связанные фазы

- **Phase 3:** [Integration Layer](../phase_3_integration/) — DocumentBuilder использует SmartSplitter
- **Phase 5:** [Batching](../phase_5_batching/) — async векторизация чанков
- **Phase 14:** [Media Crisis](../phase_14_media_crisis/) — SmartSplitter для OCR-текста

---

**← [Вернуться к оглавлению](../00_overview.md)**
