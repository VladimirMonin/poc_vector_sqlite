---
title: Production Configuration
description: Настройка Semantic Core для продакшн окружения
tags: [deployment, production, configuration, sqlite]
---

# Production Configuration 🏭

Детальная настройка для продакшн окружения.

## semantic.toml для продакшна 📄

```toml
# semantic.toml — production preset

[database]
path = "/var/lib/semantic/semantic.db"  # Абсолютный путь

[gemini]
# api_key через GEMINI_API_KEY env — не в файле!
model = "models/gemini-embedding-001"
embedding_dimension = 768  # Или 1536 для лучшего качества

[processing]
splitter = "smart"
context_strategy = "hierarchical"

[media]
enabled = true
rpm_limit = 12  # 80% от Free tier (15 RPM)

[search]
limit = 10
type = "hybrid"

[logging]
level = "INFO"  # Не DEBUG в продакшне
# file = "/var/log/semantic/app.log"  # Опционально
```

## Environment Variables 🔑

| Variable | Prod значение | Описание |
|:---------|:--------------|:---------|
| `GEMINI_API_KEY` | Из secrets manager | **Обязательно** |
| `SEMANTIC_LOG_LEVEL` | `INFO` | Меньше шума |
| `SEMANTIC_DB_PATH` | Абсолютный путь | Предсказуемость |

```bash
# Пример для systemd
Environment="GEMINI_API_KEY=AIza..."
Environment="SEMANTIC_LOG_LEVEL=INFO"
Environment="SEMANTIC_DB_PATH=/var/lib/semantic/semantic.db"
```

## SQLite в продакшне 💾

### Обязательные PRAGMA

```sql
-- Выполнить при первом подключении
PRAGMA journal_mode = WAL;      -- Write-Ahead Logging
PRAGMA synchronous = NORMAL;    -- Баланс скорость/надёжность
PRAGMA cache_size = -64000;     -- 64MB кэш
PRAGMA temp_store = MEMORY;     -- Temp tables в RAM
PRAGMA mmap_size = 268435456;   -- 256MB memory-mapped I/O
```

### Почему WAL? 📊

| Режим | Concurrent Reads | Concurrent Writes | Когда |
|:------|:-----------------|:------------------|:------|
| DELETE (default) | ❌ | ❌ | Development |
| **WAL** | ✅ | ❌ | **Production** |

WAL позволяет читать во время записи — критично для поиска.

### Регулярное обслуживание

```bash
# Еженедельный VACUUM (cron)
0 3 * * 0 sqlite3 /var/lib/semantic/semantic.db 'VACUUM;'

# Ежедневный ANALYZE для оптимизатора
0 4 * * * sqlite3 /var/lib/semantic/semantic.db 'ANALYZE;'
```

## Rate Limiting ⏱️

| Tier | API RPM | Рекомендуемый `rpm_limit` |
|:-----|:--------|:--------------------------|
| Free | 15 | 12 (80%) |
| Pay-as-you-go | 1000 | 800 (80%) |

**Формула:** `rpm_limit = API_LIMIT * 0.8`

Запас 20% для:

- Burst нагрузки
- Retry после ошибок
- Других сервисов на том же ключе

## Retry & Backoff 🔄

Встроенная стратегия:

```
Попытка 1: сразу
Попытка 2: через 1 сек
Попытка 3: через 2 сек
Попытка 4: через 4 сек
Попытка 5: через 8 сек (max)
```

**Retryable ошибки:**

- `429` — Rate limit
- `503` — Service unavailable
- `500` — Internal server error
- Timeout, connection reset

## Логирование 📝

### Уровни для продакшна

| Уровень | Когда использовать |
|:--------|:-------------------|
| `INFO` | **Стандарт** — старты, важные события |
| `WARNING` | Проблемы без потери функциональности |
| `ERROR` | Ошибки требующие внимания |

### Что НЕ логировать

- API ключи (автоматически redacted)
- Полный контент документов
- Embeddings (слишком большие)

## Бэкапы 💽

```bash
#!/bin/bash
# backup.sh — ежедневный бэкап

DB_PATH="/var/lib/semantic/semantic.db"
BACKUP_DIR="/var/backups/semantic"
DATE=$(date +%Y%m%d)

# SQLite online backup
sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/semantic_$DATE.db'"

# Ротация — хранить 7 дней
find "$BACKUP_DIR" -name "*.db" -mtime +7 -delete
```

## Мониторинг 📊

### Ключевые метрики

| Метрика | Источник | Alert |
|:--------|:---------|:------|
| Размер БД | `stat semantic.db` | > 1GB |
| Latency p99 | Логи | > 5s |
| Queue size | `semantic queue status` | > 500 |
| Error rate | Логи grep ERROR | > 1% |

### Health check

```python
# Простой health check
from semantic_core.config import get_config

def health_check():
    try:
        config = get_config()
        # Проверяем что БД доступна
        return {"status": "ok", "db": str(config.db_path)}
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

## См. также 🔗

- [Checklist](checklist.md) — быстрая проверка перед деплоем
- [Configuration Options](../../reference/configuration-options.md) — все параметры
- [Rate Limiting](../../../doc/architecture/28_rate_limiting.md) — детали алгоритма
