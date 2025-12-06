# 🖥 Phase 8: CLI & Configuration

> **Статус:** ✅ ЗАВЕРШЕНА  
> **Цель:** Production-ready CLI и единая конфигурация через TOML + env

---

## 📖 Содержание фазы

### 40. Unified Configuration
**Файл:** [40_unified_configuration.md](40_unified_configuration.md)

`SemanticConfig`: Pydantic Settings с TOML + env, единый источник правды.

**Приоритет:**
1. Environment variables (`SEMANTIC_*`)
2. TOML файл (`semantic.toml`)
3. Default values

---

### 41. CLI Architecture
**Файл:** [41_cli_architecture.md](41_cli_architecture.md)

Typer + Rich: быстрый `--help`, lazy initialization, красивый вывод.

**Фичи:**
- Автогенерация help из docstrings
- Progress bars с Rich
- Emoji в командах
- Lazy DI (SemanticCore создаётся по требованию)

---

### 42. CLI Commands
**Файл:** [42_cli_commands.md](42_cli_commands.md)

`ingest`, `search`, `docs` — три основные команды для повседневной работы.

**Примеры:**
```bash
semantic ingest notes/
semantic search "SOLID principles"
semantic docs chunking
```

---

### 43. Queue & Worker Commands
**Файл:** [43_queue_worker_commands.md](43_queue_worker_commands.md)

`queue status`/`flush`/`retry`, `worker run-once`/`start` — операционные команды для async-обработки.

---

## 🔗 Связанные фазы

- **Phase 5:** [Batching](../phase_5_batching/) — CLI для queue/worker
- **Phase 7:** [Observability](../phase_7_observability/) — Rich console для логов
- **Phase 9:** [RAG](../phase_9_rag/) — CLI команда `chat`

---

**← [Вернуться к оглавлению](../00_overview.md)**
