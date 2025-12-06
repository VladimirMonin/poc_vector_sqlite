# 🏁 Phase 13: Total Visual Check

> **Статус:** ✅ ЗАВЕРШЕНА  
> **Цель:** E2E аудит всех систем, обнаружение и устранение архитектурных проблем

---

## 📖 Содержание фазы

### 62. Концептуальный обзор Phase 13: Total Visual Check
**Файл:** [62_phase_13_overview.md](62_phase_13_overview.md)

Методология E2E аудита: зачем, как работает, 3 критических сценария (chunking, media, search).

---

### 63. Детальные результаты аудита
**Файл:** [63_phase_13_results.md](63_phase_13_results.md)

Что работает отлично (chunking, media API, rate limiting), что требует внимания (hybrid scores, duplicates, FTS).

---

### 64. Риски и ограничения
**Файл:** [64_phase_13_risks.md](64_phase_13_risks.md)

Long video timeout, document-level search gap, FTS granularity mismatch, duplicate chunks waste.

---

### 65. FTS Refactoring: Chunk-Level Search
**Файл:** [65_fts_chunk_level_refactoring.md](65_fts_chunk_level_refactoring.md)

Починка RRF: перевод FTS с документов на чанки, автомиграция и RRF boost.

---

### 66. Direct Media Ingestion
**Файл:** [66_direct_media_ingestion.md](66_direct_media_ingestion.md)

Развилка на входе: медиа-файлы идут напрямую в Gemini API, минуя `SmartSplitter`.

---

### 67. Context Window: Гений или Дед с деменцией
**Файл:** [67_context_window.md](67_context_window.md)

Расширение контекста соседними чанками: `context_window`, `MatchType.CONTEXT` и полный документ при большом window.

---

### 68. Embedding Cache Integration
**Файл:** [68_embedding_cache_integration.md](68_embedding_cache_integration.md)

Замыкаем цепь: передача `query_vector` через слои, реальная экономия API-вызовов.

---

### 69. Result Type Abstraction
**Файл:** [69_result_type_abstraction.md](69_result_type_abstraction.md)

Чанки vs Документы: toggle в UI, два DTO, нормализация RRF score.

---

### 70. Search Score Normalization
**Файл:** [70_search_score_normalization.md](70_search_score_normalization.md)

Математика релевантности: линейная формула, RRF адаптация и `min_score` фильтр.

---

## 🔗 Связанные фазы

- **Phase 2:** [Storage](../phase_2_storage/) — FTS refactoring
- **Phase 6:** [Multimodal](../phase_6_multimodal/) — media ingestion audit
- **Phase 12:** [Flask](../phase_12_flask/) — embedding cache для query cache

---

**← [Вернуться к оглавлению](../00_overview.md)**
