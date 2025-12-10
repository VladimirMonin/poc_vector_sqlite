# 💰 Phase 5: Async Batching & Cost Optimization

> **Статус:** ✅ ЗАВЕРШЕНА  
> **Цель:** Асинхронная векторизация, batch API, 50% экономия на эмбеддингах

---

## 📖 Содержание фазы

### 19. API Key Management: Разделение биллинга

**Файл:** [19_api_key_management.md](19_api_key_management.md)

`GoogleKeyring` и изоляция затрат между синхронной и асинхронной векторизацией.

---

### 20. Async Processing: От блокировки к очереди

**Файл:** [20_async_processing.md](20_async_processing.md)

Режим `mode='async'`, статусы чанков (`PENDING`/`READY`/`FAILED`) и неблокирующая загрузка.

---

### 21. Google Batch API: 50% экономия

**Файл:** [21_batch_api_economics.md](21_batch_api_economics.md)

Почему batch processing дешевле в 2 раза, trade-offs и JSONL формат.

**Экономика:**

- Regular API: `$0.00002 / 1K tokens`
- Batch API: `$0.00001 / 1K tokens` (50% скидка!)

---

### 22. BatchManager: Локальная оркестрация

**Файл:** [22_batch_manager.md](22_batch_manager.md)

SQLite как очередь задач, `flush_queue()`/`sync_status()` и жизненный цикл батч-заданий.

---

### 23. Schema Evolution: Миграция без downtime

**Файл:** [23_schema_evolution.md](23_schema_evolution.md)

Автоматическое добавление колонок через `ALTER TABLE` и backward compatibility.

---

### 24. Production Optimizations: От прототипа к масштабу

**Файл:** [24_production_optimizations.md](24_production_optimizations.md)

Partial failures handling, производительность `bulk_update_vectors()` и готовность к миллионам чанков.

---

## 🔗 Связанные фазы

- **Phase 4:** [Smart Parsing](../phase_4_smart_parsing/) — чанки для batch векторизации
- **Phase 8:** [CLI](../phase_8_cli/) — команды `queue` и `worker`
- **Phase 10:** [Batch API Integration](../phase_10_batch_api/) — реальный Batch API клиент

---

**← [Вернуться к оглавлению](../00_overview.md)**
