---
title: "CLI Commands Reference"
description: "Все команды Semantic Core CLI с флагами и примерами"
tags: ["reference", "cli", "commands"]
---

# CLI Commands Reference 🖥️

> Полный справочник команд CLI.

---

## Глобальные опции 🌐

| Флаг | Короткая | Описание |
|------|----------|----------|
| `--db-path` | `-d` | Путь к SQLite базе |
| `--log-level` | `-l` | TRACE/DEBUG/INFO/WARNING/ERROR |
| `--json` | `-j` | JSON вывод |
| `--verbose` | `-v` | Подробный вывод |
| `--version` | | Показать версию |
| `--help` | | Справка |

---

## Команды 📋

| Команда | Описание |
|---------|----------|
| `init` | Инициализация проекта |
| `ingest` | Индексация документов |
| `search` | Поиск по базе |
| `chat` | Интерактивный RAG-чат |
| `docs` | Встроенная документация |
| `config` | Управление конфигурацией |
| `doctor` | Диагностика системы |
| `queue` | Управление очередями |
| `worker` | Управление воркерами |

---

## init 🚀

**Синтаксис**: `semantic init [OPTIONS]`

Инициализация проекта и проверка окружения.

| Флаг | Описание |
|------|----------|
| `--db-path` | Путь к БД (default: semantic.db) |

```bash
semantic init
semantic init --db-path ./data/my.db
```

---

## ingest 📥

**Синтаксис**: `semantic ingest [OPTIONS] PATH`

| Флаг | Короткая | Тип | Описание |
|------|----------|-----|----------|
| `--recursive` | `-r` | flag | Рекурсивная обработка |
| `--pattern` | `-p` | str | Glob-паттерн (*.md) |
| `--no-media` | | flag | Пропустить медиа |
| `--batch` | `-b` | flag | Batch API режим |

```bash
semantic ingest README.md
semantic ingest ./docs/ -r -p "*.md"
semantic ingest ./docs/ --batch --recursive
```

---

## search 🔍

**Синтаксис**: `semantic search [OPTIONS] QUERY`

| Флаг | Короткая | Тип | Default | Описание |
|------|----------|-----|---------|----------|
| `--limit` | `-l` | int | 10 | Количество результатов |
| `--type` | `-t` | str | hybrid | vector/fts/hybrid |
| `--threshold` | `-T` | float | 0.0 | Минимальный score |
| `--k` | `-k` | int | 60 | RRF параметр k |

```bash
semantic search "как работает RRF"
semantic search "query" -l 20 -t vector
semantic search "точный термин" -t fts -T 0.5
```

---

## chat 💬

**Синтаксис**: `semantic chat [OPTIONS]`

| Флаг | Короткая | Тип | Default | Описание |
|------|----------|-----|---------|----------|
| `--model` | `-m` | str | gemini-2.5-flash-lite | LLM модель |
| `--context` | `-c` | int | 5 | Чанков контекста |
| `--search` | `-s` | str | hybrid | Режим поиска |
| `--temperature` | `-t` | float | 0.7 | Температура |
| `--full-docs` | | flag | false | Полные документы |
| `--history-limit` | `-H` | int | 10 | Лимит сообщений |
| `--token-budget` | | int | - | Лимит токенов |
| `--no-history` | | flag | false | Без истории |

```bash
semantic chat
semantic chat --model gemini-2.5-pro -c 10
semantic chat --no-history --search vector
```

---

## docs 📚

**Синтаксис**: `semantic docs [TOPIC]`

Встроенная документация.

```bash
semantic docs              # Список топиков
semantic docs search       # О поиске
semantic docs config       # О конфигурации
```

---

## config ⚙️

**Синтаксис**: `semantic config COMMAND`

| Подкоманда | Описание |
|------------|----------|
| `show` | Показать текущую конфигурацию |

```bash
semantic config show
semantic config show --json
```

---

## doctor 🩺

**Синтаксис**: `semantic doctor`

Диагностика системы: sqlite-vec, API, БД.

```bash
semantic doctor
```

---

## queue 📦

**Синтаксис**: `semantic queue COMMAND`

| Подкоманда | Описание |
|------------|----------|
| `status` | Статус очередей |
| `flush` | Отправить pending в Batch API |
| `retry` | Перезапустить failed задачи |

```bash
semantic queue status
semantic queue flush --type text
semantic queue retry --limit 100
```

---

## worker 👷

**Синтаксис**: `semantic worker COMMAND`

| Подкоманда | Описание |
|------------|----------|
| `run-once` | Одноразовая обработка |
| `start` | Бесконечный цикл |

| Флаг | Описание |
|------|----------|
| `--max-tasks` | Лимит задач за цикл |
| `--interval` | Интервал между циклами (сек) |

```bash
semantic worker run-once --max-tasks 50
semantic worker start --interval 60
```

---

## Связанные темы 🔗

| Ресурс | Описание |
|--------|----------|
| [CLI Usage Guide](../guides/core/cli-usage.md) | Подробный гайд |
| [Configuration](../guides/core/configuration.md) | Настройка |
