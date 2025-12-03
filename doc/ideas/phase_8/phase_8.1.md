````markdown
# 📋 Phase 8.1: Operations CLI — Worker & Queue

**Статус:** 🔲 Планируется  
**Зависимости:** Phase 8.0 (Core CLI) ✅

---

## 🎯 Цель

Добавить команды для управления фоновыми процессами и очередями:
- **queue** — мониторинг и управление очередью задач
- **worker** — запуск и контроль воркеров обработки

---

## 📦 Новые модули

```text
semantic_core/cli/commands/
├── queue.py              # semantic queue status/flush/retry
└── worker.py             # semantic worker start/run-once
```

---

## 📐 Группа `queue` — Управление очередью

**Файл:** `commands/queue.py`

### Команды

#### `semantic queue status`

Показывает текущее состояние очередей.

**Источники данных:**

| Метод | Что показывает |
|-------|----------------|
| `BatchManager.get_queue_stats()` | Text Embeddings: pending, processing, ready, failed |
| `MediaQueueProcessor.get_pending_count()` | Media: pending |
| `MediaTaskModel.select().where(status=...)` | Media: по статусам |

**UX:**

```
$ semantic queue status

📦 Queue Status

Text Embeddings (Batch API):
┏━━━━━━━━━━━━━┳━━━━━━━┓
┃ Status      ┃ Count ┃
┡━━━━━━━━━━━━━╇━━━━━━━┩
│ 🔵 Pending  │   42  │
│ 🟡 Process. │   10  │
│ 🟢 Ready    │ 1,234 │
│ 🔴 Failed   │    2  │
└─────────────┴───────┘

Media Analysis (Local Queue):
┏━━━━━━━━━━━━━┳━━━━━━━┓
┃ Status      ┃ Count ┃
┡━━━━━━━━━━━━━╇━━━━━━━┩
│ 🔵 Pending  │    5  │
│ 🟡 Process. │    1  │
│ 🟢 Completed│   89  │
│ 🔴 Failed   │    0  │
└─────────────┴───────┘

💡 Tip: Run 'semantic worker run-once' to process pending tasks
```

**JSON Output:**

```json
{
  "text_embeddings": {
    "pending": 42,
    "processing": 10,
    "ready": 1234,
    "failed": 2
  },
  "media": {
    "pending": 5,
    "processing": 1,
    "completed": 89,
    "failed": 0
  }
}
```

---

#### `semantic queue flush`

Принудительно отправляет pending text chunks в Batch API.

**Логика:**

```python
batch_id = batch_manager.flush_queue(force=True)
if batch_id:
    console.print(f"✅ Created batch: {batch_id[:8]}...")
else:
    console.print("ℹ️ No pending chunks to flush")
```

**Опции:**

| Опция | Тип | Описание |
|-------|-----|----------|
| `--min-size` | INT | Минимальный размер батча (default: 0, игнорируется с force) |

**UX:**

```
$ semantic queue flush

📦 Flushing text embedding queue...
✅ Created batch: abc12345... (42 chunks)
   Google Job ID: projects/xxx/locations/us-central1/...
```

---

#### `semantic queue retry`

Перезапускает failed задачи.

**Логика:**

1. Найти все чанки с `embedding_status=FAILED`
2. Сбросить статус на `PENDING`, очистить `batch_job` FK
3. Аналогично для `MediaTaskModel` с `status=FAILED`

**UX:**

```
$ semantic queue retry

🔄 Retrying failed tasks...
   Text chunks: 2 → PENDING
   Media tasks: 0 → PENDING
✅ Ready for reprocessing
```

**Опции:**

| Опция | Тип | Описание |
|-------|-----|----------|
| `--type` | text/media/all | Какие задачи ретраить (default: all) |

---

## 📐 Группа `worker` — Управление воркерами

**Файл:** `commands/worker.py`

### Команды

#### `semantic worker run-once`

Обрабатывает очередь один раз и выходит.

**Логика:**

```python
# 1. Sync batch statuses (скачать готовые результаты)
statuses = batch_manager.sync_status()
log_batch_results(statuses)

# 2. Process media queue
processed = core.process_media_queue(max_tasks=max_tasks)
console.print(f"✅ Processed {processed} media tasks")

# 3. Show remaining
remaining = queue_processor.get_pending_count()
console.print(f"📦 Remaining: {remaining} tasks")
```

**Опции:**

| Опция | Тип | Описание |
|-------|-----|----------|
| `--max-tasks` | INT | Лимит задач за один проход (default: 50) |

**UX:**

```
$ semantic worker run-once --max-tasks 10

👷 Running one-time processing...

Batch Sync:
   abc12345: COMPLETED (42 chunks)
   def67890: PROCESSING

Media Queue:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 10/10

✅ Processed 10 media tasks
📦 Remaining: 5 tasks in queue
```

---

#### `semantic worker start`

Запускает бесконечный цикл обработки.

**Логика:**

```python
import signal

running = True

def handle_sigint(sig, frame):
    nonlocal running
    console.print("\n⏹️ Graceful shutdown requested...")
    running = False

signal.signal(signal.SIGINT, handle_sigint)

while running:
    # 1. Sync batches
    batch_manager.sync_status()
    
    # 2. Process media
    processed = core.process_media_queue(max_tasks=batch_size)
    
    if processed == 0:
        # No work, sleep
        time.sleep(poll_interval)
    else:
        log.info(f"Processed {processed} tasks")

console.print("✅ Worker stopped gracefully")
```

**Опции:**

| Опция | Тип | Описание |
|-------|-----|----------|
| `--batch-size` | INT | Задач за итерацию (default: 10) |
| `--poll-interval` | FLOAT | Секунды между проверками (default: 5.0) |

**UX:**

```
$ semantic worker start --poll-interval 10

👷 Starting worker (batch=10, poll=10s)
   Press Ctrl+C for graceful shutdown

[14:20:01] 📦 Synced 2 batches: 1 COMPLETED, 1 PROCESSING
[14:20:02] 🎬 Processed 5 media tasks
[14:20:12] 💤 No pending tasks, sleeping...
[14:20:22] 👁️ Processed 3 image tasks
^C
⏹️ Graceful shutdown requested...
✅ Worker stopped. Processed 8 tasks total.
```

---

## 🔤 CLI Эмодзи для логгера

**Предложение расширить EMOJI_MAP:**

| Паттерн | Эмодзи | Модуль |
|---------|--------|--------|
| `cli` | 🖥️ | Общий CLI |
| `worker` | 👷 | worker.py |
| `queue` (CLI) | 📦 | Уже есть |
| `retry` | 🔄 | Повтор задач |

**Решение:** Добавить в EMOJI_MAP при реализации Phase 8.1:
- `cli` → 🖥️
- `worker` → 👷

---

## ✅ Acceptance Criteria

### Функциональные

1. [ ] `semantic queue status` показывает статистику обеих очередей
2. [ ] `semantic queue flush` отправляет pending чанки в Batch API
3. [ ] `semantic queue retry` сбрасывает failed задачи
4. [ ] `semantic worker run-once` обрабатывает очередь один раз
5. [ ] `semantic worker start` работает в бесконечном цикле
6. [ ] Ctrl+C вызывает graceful shutdown

### Качество

7. [ ] Флаг `--json` работает для queue status
8. [ ] Worker логирует свои действия через `get_logger()`
9. [ ] Ошибки API не крашат worker (логируются и продолжаем)

### Тесты

10. [ ] Unit-тесты для queue commands (mock BatchManager)
11. [ ] Integration-тест worker с Ctrl+C (signal handling)

---

## 📚 Документация (после реализации)

### Архитектурный сериал

1. **Episode 41:** `41_worker_architecture.md` — Архитектура воркера
   - Signal handling (SIGINT, SIGTERM)
   - Polling strategy
   - Graceful shutdown pattern

### Обновления

- Добавить секцию "Background Processing" в README
- Пример systemd unit для `semantic worker start`
- Пример cron для `semantic worker run-once`

### EMOJI_MAP

Добавить в `formatters.py`:
```python
"cli": "🖥️",
"worker": "👷",
```

---

## 🔗 Связанные документы

- **Предыдущая:** [Phase 8.0 — Core CLI](phase_8.0.md)
- **Следующая:** [Phase 8.2 — RAG Chat](phase_8.2.md)
- **BatchManager:** [Phase 5.0 — Batch API](../phase_5/phase_5.0.md)
- **MediaQueue:** [Phase 6.0 — Media Queue](../phase_6/phase_6.0.md)

````
