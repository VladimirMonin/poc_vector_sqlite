# Task 11.11: Windows Compatibility Documentation

## 📋 Описание задачи

Документирование особенностей запуска Semantic Core на Windows.  
Обнаружено при тестировании на Windows 10/11 с Python 3.13/3.14.

---

## 🐛 Обнаруженные проблемы

### 1. Python 3.14 — пакеты не собираются

**Проблема:** Pillow, imageio и другие пакеты с C-расширениями не имеют pre-built wheels для Python 3.14 на Windows.

**Ошибка:**

```
Pillow 10.4.0 does not support Python 3.14 and does not provide prebuilt Windows binaries.
RequiredDependencyException: zlib
```

**Решение:** Использовать Python 3.13.x на Windows.

**Что исправить:**

- `pyproject.toml` — изменено `requires-python = ">=3.14"` → `">=3.13,<3.15"`
- Добавить в документацию предупреждение о версии Python

---

### 2. CLI: Порядок аргументов и опций

**Проблема:** Typer + Click баг при использовании `callback(invoke_without_command=True)` с `Path` аргументом в sub-Typer.

**НЕ работает (опции после аргумента):**

```bash
semantic ingest docs --recursive      # ❌ Missing argument 'PATH'
semantic ingest ./docs -r -m sync     # ❌ Missing argument 'PATH'
```

**Работает (опции ПЕРЕД аргументом):**

```bash
semantic ingest --recursive docs      # ✅
semantic ingest -r -m sync ./docs     # ✅
semantic ingest --dry-run docs        # ✅
```

**Причина:** Click/Typer парсит аргументы позиционно, и при `invoke_without_command=True` в sub-Typer опции после `Path` аргумента интерпретируются как подкоманды.

**Что исправить:**

- Все примеры в документации CLI
- README.md в секции Quick Start
- Docstrings в `ingest.py`, `search.py`

---

### 3. PowerShell vs Bash синтаксис

**Проблема:** Примеры с `export` не работают в PowerShell.

**Bash (macOS/Linux):**

```bash
export SEMANTIC_DB_PATH="project_docs.db"
export GEMINI_API_KEY="your-key"
semantic ingest --recursive docs
```

**PowerShell (Windows):**

```powershell
$env:SEMANTIC_DB_PATH = "project_docs.db"
$env:GEMINI_API_KEY = "your-key"
semantic ingest --recursive docs
```

**Что исправить:**

- Добавить PowerShell эквиваленты во все гайды
- Секция "Platform-Specific Commands" в Quick Start

---

### 4. Пути с обратными слэшами

**Проблема:** Windows использует `\`, Unix — `/`.

**Рекомендация:** В документации использовать универсальный формат:

```bash
semantic ingest docs                  # Относительный путь (работает везде)
semantic ingest ./docs                # Unix-style (работает в PowerShell)
semantic ingest .\docs                # Windows-style
```

---

## 📝 Документы для обновления

### Высокий приоритет

| Документ | Секция | Изменение |
|----------|--------|-----------|
| `docs/README.md` | Quick Start | Добавить Windows-специфичные команды |
| `docs/guides/installation.md` | Requirements | Python 3.13+ (не 3.14 на Windows) |
| `docs/guides/cli-usage.md` | Commands | Порядок опций ПЕРЕД аргументами |
| `README.md` (корень) | Getting Started | PowerShell примеры |

### Средний приоритет

| Документ | Секция | Изменение |
|----------|--------|-----------|
| `doc/architecture/41_cli_architecture.md` | Usage | Уточнить порядок аргументов |
| `doc/architecture/42_cli_commands.md` | Examples | Исправить примеры |
| `semantic_core/cli/commands/ingest.py` | Docstring | Обновить примеры в docstring |
| `semantic_core/cli/commands/search.py` | Docstring | Обновить примеры в docstring |

### Низкий приоритет

| Документ | Секция | Изменение |
|----------|--------|-----------|
| `docs/concepts/configuration.md` | Environment | PowerShell синтаксис |
| Все гайды с примерами команд | — | Dual-platform примеры |

---

## 📄 Шаблон для документации

### Recommended: Platform-Agnostic Section

```markdown
## 🖥️ Platform Notes

### Windows (PowerShell)

```powershell
# Set environment variables
$env:GEMINI_API_KEY = "your-api-key"
$env:SEMANTIC_DB_PATH = "semantic.db"

# Run commands (options BEFORE path!)
semantic ingest --recursive docs
semantic search "query"
```

### macOS / Linux (Bash)

```bash
# Set environment variables  
export GEMINI_API_KEY="your-api-key"
export SEMANTIC_DB_PATH="semantic.db"

# Run commands
semantic ingest docs --recursive
semantic search "query"
```

> ⚠️ **Windows Users:** Place CLI options (`--recursive`, `--dry-run`)
> BEFORE the path argument due to a Click/Typer parsing limitation.

```

---

## ✅ Критерии завершения

- [ ] `pyproject.toml` обновлён (Python >=3.13,<3.15) — **DONE**
- [ ] README.md содержит Windows Quick Start
- [ ] `docs/guides/installation.md` предупреждает о Python 3.14
- [ ] Все CLI примеры показывают правильный порядок аргументов
- [ ] PowerShell эквиваленты для всех `export` команд
- [ ] Тесты CLI проходят на Windows — **DONE** (49 passed)

---

## 🔗 Связанные материалы

- Typer Issue: https://github.com/fastapi/typer/issues/351
- Click documentation on argument order
- Python 3.14 wheel availability tracker
