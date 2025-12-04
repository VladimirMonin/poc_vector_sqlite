# Windows Hotfixes Log

Лог хотфиксов для Windows-совместимости.  
Дата начала: 2025-12-04

---

## Hotfix #1: Python version requirement

**Файл:** `pyproject.toml`  
**Проблема:** `requires-python = ">=3.14"` — Pillow и другие пакеты не имеют wheels для Python 3.14 на Windows  
**Решение:** Изменено на `requires-python = ">=3.13,<3.15"`  
**Коммит:** `1bec455`

---

## Hotfix #2: SmartSplitter missing parser

**Файл:** `semantic_core/cli/context.py`  
**Проблема:** `SmartSplitter()` вызывается без обязательного аргумента `parser`  
**Решение:** Добавить создание `MarkdownNodeParser` и передать в `SmartSplitter`  
**Коммит:** `8d2eeb4` (исправлено ранее)

---

## Обнаруженные issues (не баги, а особенности)

### Issue #1: CLI argument order
**Описание:** Typer/Click требует опции ПЕРЕД путём при использовании `callback(invoke_without_command=True)`  
**Пример:** `semantic ingest --recursive docs` ✅ vs `semantic ingest docs --recursive` ❌  
**Статус:** Документировать, не фиксить (ограничение Typer)

### Issue #2: Environment variable prefix  
**Описание:** API ключ требует префикс `SEMANTIC_` → `SEMANTIC_GEMINI_API_KEY`  
**Статус:** Документировать (by design)

---

## Pending Hotfixes (TODO)

### Hotfix #3: Document ID в логах показывает `[unknown]`

**Файл:** `semantic_core/processing/splitters/smart_splitter.py` (строка 71-73)  
**Проблема:** При обработке документов в логах всегда `[unknown]` вместо имени файла/ID  
**Причина:** `document.metadata` не содержит `doc_id` и `document.id` пустой при создании в CLI  
**Влияние:** Невозможно понять какой файл обрабатывается, сложно отлаживать ошибки  

**Текущий код:**
```python
doc_id = document.metadata.get("doc_id") or (
    str(document.id)[:8] if document.id else "unknown"
)
```

**Требуется:** CLI должен передавать `doc_id` (имя файла или путь) в `document.metadata` при создании `Document`

**Где искать:**
- `semantic_core/cli/commands/ingest.py` — создание Document
- `semantic_core/pipeline.py` — если там создаётся Document

**Статус:** 🔴 TODO

---
