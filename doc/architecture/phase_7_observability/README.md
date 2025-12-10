# 📊 Phase 7: Observability Layer

> **Статус:** ✅ ЗАВЕРШЕНА  
> **Цель:** Семантическое логирование для разработчика и AI-агентов

---

## 📖 Содержание фазы

### 35. Semantic Logging Architecture

**Файл:** [35_semantic_logging.md](35_semantic_logging.md)

Dual-mode logging:

- **Console (INFO+):** для разработчика с цветами
- **File (TRACE):** для AI-агентов со всеми деталями

---

### 36. Visual Semantics in Logs

**Файл:** [36_visual_semantics_logs.md](36_visual_semantics_logs.md)

`EMOJI_MAP`: мгновенная идентификация модуля и уровня через эмодзи.

**Примеры:**

- 📦 Storage operations
- 🧠 Embeddings & AI
- 🔍 Search operations
- 🎬 Media processing

---

### 37. Context Propagation with bind()

**Файл:** [37_context_propagation.md](37_context_propagation.md)

Проброс `batch_id`, `doc_id` через весь pipeline без thread-local storage.

```python
logger = logger.bind(doc_id=doc.id, batch_id=batch.id)
```

---

### 38. Secret Redaction in Logs

**Файл:** [38_secret_redaction.md](38_secret_redaction.md)

`SensitiveDataFilter`: автоматическое маскирование API-ключей.

**До:**

```
API key: AIzaSyDc3...
```

**После:**

```
API key: AIza****
```

---

### 39. Diagnostics & Debugging

**Файл:** [39_diagnostics_debugging.md](39_diagnostics_debugging.md)

`dump_debug_info()`, `check_config()`, `trace_ai()` и `error_with_context()`.

---

## 🔗 Связанные фазы

- **Phase 5:** [Batching](../phase_5_batching/) — логи batch-заданий
- **Phase 6:** [Multimodal](../phase_6_multimodal/) — логи media обработки
- **Phase 8:** [CLI](../phase_8_cli/) — Rich console для CLI

---

**← [Вернуться к оглавлению](../00_overview.md)**
