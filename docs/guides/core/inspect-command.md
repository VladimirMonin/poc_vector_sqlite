# Inspect Command Guide

> Как использовать `semantic inspect` для отладки pipeline

**Аудитория:** Разработчики, DevOps  
**Требования:** Установленный semantic-core

---

## 🎯 Зачем нужна эта команда?

`semantic inspect` позволяет "просветить" процесс обработки документов:

- **Видеть чанки** — как документ разбивается на куски
- **Видеть embeddings** — какие векторы генерируются
- **Видеть метаданные провайдеров** — модели, размерности, параметры
- **Измерять производительность** — сколько времени занимает каждый шаг
- **Сравнивать конфигурации** — какой провайдер лучше?

---

## 🚀 Быстрый старт

### Базовая инспекция

```bash
semantic inspect docs/example.md
```

**Вывод в терминал (Rich TUI):**

```
📥 Loading document: docs/example.md (5.2 KB)
🔧 Creating SemanticCore (provider: gemini)
🧠 Embedding 3 chunks...
💾 Saving document to database...
✅ Inspection complete (1549ms)

╭─────────────────────── Provider Metadata ──────────────────────╮
│ Type:      GeminiEmbedder                                      │
│ Model:     text-embedding-004                                  │
│ Dimension: 768                                                 │
│ Max Tokens: 2048                                               │
╰────────────────────────────────────────────────────────────────╯

╭─────────────────────── Chunks (3) ─────────────────────────────╮
│ #1: # Introduction to Python                                  │
│     Size: 487 chars | Headers: ['Introduction']               │
│     Embedding: [0.123, -0.456, 0.789, ...]                    │
│                                                                │
│ #2: Python is a high-level programming language...            │
│     Size: 512 chars | Headers: ['Introduction', 'Overview']   │
│     Embedding: [0.789, 0.234, -0.123, ...]                    │
│                                                                │
│ #3: ```python...                                               │
│     Size: 345 chars | Headers: ['Examples', 'Code']           │
│     Embedding: [-0.123, 0.567, 0.234, ...]                    │
╰────────────────────────────────────────────────────────────────╯

📊 Processing Steps (4):
  1. splitting      → 45ms
  2. embedding      → 1450ms
  3. saving         → 54ms
  4. completed      → 0ms
```

### С сохранением артефактов

```bash
semantic inspect docs/example.md --save
```

**Создаёт:**

```
inspection_artifacts/
└── session_2025-12-10_14-30-15/
    ├── example_md_inspection.json    # Полный snapshot
    ├── input_example.md              # Копия входного файла
    └── report.md                     # Markdown отчёт (опционально)
```

---

## 📋 Все опции команды

```bash
semantic inspect <file_path> [OPTIONS]
```

### Основные опции

| Опция | Описание | Пример |
|-------|----------|--------|
| `--save` | Сохранить артефакты | `--save` |
| `--artifacts-dir <path>` | Путь для артефактов | `--artifacts-dir ./snapshots` |
| `--format <fmt>` | Формат вывода: console / markdown / json | `--format markdown` |
| `--output <path>` | Файл для вывода (для json/markdown) | `--output report.json` |
| `--config <path>` | Кастомный конфиг | `--config alt.toml` |

### Опции поиска

| Опция | Описание | Пример |
|-------|----------|--------|
| `--search <query>` | Выполнить поиск после индексации | `--search "Python"` |
| `--search-mode <mode>` | Режим поиска: vector / fts / hybrid | `--search-mode hybrid` |
| `--limit <n>` | Лимит результатов поиска | `--limit 5` |

---

## 🎯 Примеры использования

### Пример 1: Проверка чанкинга Markdown

**Задача:** Проверить, правильно ли разбивается сложный Markdown с кодом и таблицами.

```bash
semantic inspect docs/complex.md --format markdown --output chunking_report.md
```

**Смотрим отчёт:**

```markdown
# 🔍 Inspection Report

**File:** `docs/complex.md`
**Size:** 15.8 KB
**Chunks:** 12

## 📦 Chunks

### Chunk #1: Header + Intro
**Headers:** `['Overview']`
**Content:**
```
# Complex Document

This document contains various types of content...
```

### Chunk #2: Code Block
**Headers:** `['Examples', 'Python Code']`
**Content:**
```python
def hello():
    print("Hello, World!")
```
```

### Пример 2: Сравнение провайдеров (Gemini vs Local)

**Задача:** Понять, отличаются ли embeddings между Gemini и локальным embedder.

```bash
# 1. Gemini baseline
semantic inspect example.md \
  --config configs/gemini.toml \
  --save --artifacts-dir snapshots/gemini/

# 2. Local embedder
semantic inspect example.md \
  --config configs/local.toml \
  --save --artifacts-dir snapshots/local/

# 3. Сравнение (пока вручную, CLI команда в разработке)
diff snapshots/gemini/example_md_inspection.json \
     snapshots/local/example_md_inspection.json
```

**Что искать в diff:**
- `embedder_metadata.provider_type`: `GeminiEmbedder` vs `LocalEmbedder`
- `embedder_metadata.dimension`: `768` vs `384` (разные размерности!)
- `chunks[].embedding_preview`: разные векторы (нормально)

### Пример 3: Отладка similarity

**Задача:** Все результаты поиска имеют similarity ~0.55, хотим понять почему.

```bash
semantic inspect docs/python_guide.md \
  --search "Python type hints" \
  --format markdown \
  --output similarity_debug.md
```

**В отчёте будет:**

```markdown
## 🔎 Search Results

**Query:** `Python type hints`
**Mode:** hybrid (vector + fts)
**Limit:** 10

### Result #1 (similarity: 0.547)
**Chunk ID:** 42
**Headers:** `['Type System', 'Type Hints']`
**Content Preview:**
```
Type hints in Python allow you to annotate...
```

**Query Embedding:**
```
[0.234, -0.567, 0.123, ...]
```

**Chunk Embedding:**
```
[0.221, -0.534, 0.118, ...]
```

**Cosine Similarity:** 0.547
**Why it matched:** FTS matched "type hints" (3 words)
```

**Insight:** Similarity ~0.55 нормальна для семантического поиска! Это не "низкая" similarity.

### Пример 4: Инспекция медиа

**Задача:** Проверить, как распознаётся аудио через Whisper.

```bash
# Локальный Whisper
semantic inspect audio/interview.mp3 \
  --config configs/whisper.toml \
  --save

# Gemini Audio API (для сравнения)
semantic inspect audio/interview.mp3 \
  --config configs/gemini.toml \
  --save
```

**В консоли увидим:**

```
📥 Loading media: audio/interview.mp3 (8.5 MB)
🔧 Creating SemanticCore (transcriber: whisper)
🎤 Transcribing audio (Whisper base)...
✅ Transcription complete (32.4s)

╭─────────────────────── Transcriber Metadata ───────────────────╮
│ Type:      WhisperTranscriber                                  │
│ Model:     base                                                │
│ Device:    mps (Apple Silicon)                                │
│ Language:  auto-detect                                         │
╰────────────────────────────────────────────────────────────────╯

📝 Transcription:
"Hello and welcome to this interview. Today we're discussing..."
(2,345 words, 15.8 min duration)
```

---

## 🔧 Работа с артефактами

### Структура сохранённых данных

```
inspection_artifacts/
└── session_2025-12-10_14-30-15/
    ├── example_md_inspection.json    # Полный snapshot
    ├── input_example.md              # Копия входного файла
    └── report.md                     # Опционально
```

### Формат JSON snapshot

```json
{
  "file_path": "docs/example.md",
  "file_content": "# Introduction\n\n...",
  "processing_timestamp": "2025-12-10T14:30:15",
  "embedder_metadata": {
    "provider_type": "GeminiEmbedder",
    "model_name": "text-embedding-004",
    "dimension": 768,
    "max_tokens": 2048
  },
  "chunks": [
    {
      "chunk_id": 1,
      "content": "# Introduction\n\nPython is...",
      "context_text": "Document: example.md\n# Introduction\n\nPython is...",
      "headers": ["Introduction"],
      "language": "markdown",
      "start_line": 1,
      "end_line": 15,
      "char_count": 487,
      "embedding_preview": [0.123, -0.456, 0.789, ...],
      "embedding_dimension": 768
    }
  ],
  "searches": [],
  "steps": [
    {"name": "splitting", "duration_ms": 45},
    {"name": "embedding", "duration_ms": 1450},
    {"name": "saving", "duration_ms": 54}
  ],
  "total_duration_ms": 1549
}
```

### Программная работа со snapshot

```python
from semantic_core.core.observatory import SnapshotManager

# Загрузить snapshot
manager = SnapshotManager()
snapshot = manager.load_snapshot("inspection_artifacts/session_XXX/example_md_inspection.json")

# Анализировать
print(f"Chunks: {len(snapshot.chunks)}")
print(f"Embedder: {snapshot.embedder_metadata.provider_type}")

# Проверить embedding качество
import numpy as np
for chunk in snapshot.chunks:
    embedding = np.array(chunk.embedding_preview)
    norm = np.linalg.norm(embedding)
    print(f"Chunk {chunk.chunk_id}: norm={norm:.3f}")
```

---

## ⚠️ Важные детали

### Overhead инспекции

Инспекция добавляет ~5-10% overhead:
- Копирование данных
- Сохранение промежуточных состояний
- Подсчёт времени

**Рекомендация:** Не используйте `--save` в production pipeline.

### Размер артефактов

Snapshot может быть большим, если много чанков:
- ~5 KB на чанк (с embedding preview)
- ~100 чанков → ~500 KB
- + копия входного файла

**Рекомендация:** Используйте `--artifacts-dir` на диске с достаточным местом.

### Provider compatibility

Инспектор работает с любыми провайдерами через duck typing:

```python
# Если провайдер имеет атрибуты — они будут захвачены
embedder.model         → ✅ Captured
embedder.dimension     → ✅ Captured
embedder.custom_param  → ❌ Ignored (не в ProviderMetadata)
```

**Graceful degradation:** Отсутствующие атрибуты → `None` в snapshot.

---

## 🎓 Продвинутые сценарии

### Сценарий 1: CI/CD проверки

**Задача:** Проверять качество embeddings в CI.

```yaml
# .github/workflows/embedding_quality.yml
name: Embedding Quality Check

on: [push]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install semantic-core
        run: pip install semantic-core
      
      - name: Inspect test file
        run: |
          semantic inspect tests/fixtures/test_doc.md \
            --save \
            --artifacts-dir ./snapshots
      
      - name: Compare with golden
        run: python scripts/compare_snapshots.py \
          ./snapshots/test_doc_inspection.json \
          ./tests/golden/test_doc_golden.json
```

### Сценарий 2: Мониторинг дрейфа embeddings

**Задача:** Отслеживать, не изменились ли embeddings после обновления модели.

```python
import json
import numpy as np
from pathlib import Path

def compute_embedding_drift(old_snapshot_path, new_snapshot_path):
    """Вычислить drift между двумя snapshots."""
    
    with open(old_snapshot_path) as f:
        old = json.load(f)
    
    with open(new_snapshot_path) as f:
        new = json.load(f)
    
    drifts = []
    for old_chunk, new_chunk in zip(old['chunks'], new['chunks']):
        old_emb = np.array(old_chunk['embedding_preview'])
        new_emb = np.array(new_chunk['embedding_preview'])
        
        # Cosine distance
        drift = 1 - np.dot(old_emb, new_emb) / (
            np.linalg.norm(old_emb) * np.linalg.norm(new_emb)
        )
        drifts.append(drift)
    
    avg_drift = np.mean(drifts)
    max_drift = np.max(drifts)
    
    print(f"Average drift: {avg_drift:.4f}")
    print(f"Max drift: {max_drift:.4f}")
    
    if avg_drift > 0.1:
        print("⚠️  WARNING: High embedding drift detected!")
    
    return avg_drift, max_drift
```

---

## 📚 Связанные темы

- [Debug Observatory Concept](../../concepts/12_debug_observatory.md)
- [Multi-Provider Architecture](../../concepts/11_multi_provider.md)
- [Configuration Guide](configuration.md)

---

## 🔜 Что дальше?

В Phase 16.1-16.5 появятся:
- `semantic compare` — сравнение snapshots
- `semantic golden create` — создание golden-файлов
- `semantic golden test` — автотесты с golden-файлами
- Interactive mode — step-by-step инспекция

**Статус:** Phase 16.0 реализован, остальное в roadmap.
