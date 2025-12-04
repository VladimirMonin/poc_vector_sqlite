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
