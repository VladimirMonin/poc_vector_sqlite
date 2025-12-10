# 🔬 Phase 16: Debug Observatory & Multi-Provider Inspection

**Дата начала:** Январь 2026  
**Статус:** Planning  
**Зависимости:** Phase 15 (Provider-Agnostic Architecture)

---

## 🎯 Миссия

Создать **рентгеновский аппарат** для SemanticCore — инструмент визуализации и отладки pipeline с поддержкой:

- **Любых комбинаций провайдеров** (локальный чанкинг + облачное распознавание)
- **Пошаговой инспекции** с сохранением артефактов
- **Сравнения конфигураций** (какой провайдер даёт лучший результат?)
- **Golden-file тестирования** для регрессий

**Философия:** "Просветить" любой конфиг без изменения кода, увидеть промежуточные состояния каждого компонента.

---

## 📋 Оглавление подфаз

| Подфаза | Название | Статус | Описание |
|---------|----------|--------|----------|
| [16.0](phase_16.0.md) | Inspector Core Refactoring | 🔲 Planning | Перенос `PipelineInspector` из tests → core, provider-aware |
| [16.1](phase_16.1.md) | CLI Inspect Command | 🔲 Planning | `semantic inspect <file>` с Rich TUI |
| [16.2](phase_16.2.md) | Multi-Provider Snapshots | 🔲 Planning | Сохранение артефактов для разных конфигов |
| [16.3](phase_16.3.md) | Comparison Engine | 🔲 Planning | Diff между снимками (baseline vs current) |
| [16.4](phase_16.4.md) | Interactive Mode | 🔲 Planning | Step-by-step с паузами и preview |
| [16.5](phase_16.5.md) | Golden File Testing | 🔲 Planning | Автотесты с эталонными снимками |

---

## 📊 Архитектурный обзор

### Текущее состояние (Phase 15)

```
SemanticCore (multi-provider ready)
├── embedder: IEmbedder               ← Gemini / Local / OpenAI
├── transcriber: ITranscriber         ← Gemini / Whisper
├── vision: IVisionAnalyzer           ← Gemini / Local Vision
├── llm: ILLMProvider                 ← Gemini / OpenAI-compatible
└── splitter: ISplitter               ← SmartSplitter

PipelineInspector (в tests/e2e/audit/conftest.py)
└── Hardcoded для Gemini провайдеров
```

### Целевое состояние (Phase 16)

```
SemanticCore
└── (без изменений, использует Phase 15 архитектуру)

DebugObservatory (новая подсистема)
├── InspectorCore
│   ├── ProviderInspector              ← Перехватывает вызовы любых провайдеров
│   ├── PipelineRecorder               ← Записывает шаги с метаданными
│   └── SnapshotManager                ← Сохраняет/загружает артефакты
│
├── CLI Commands
│   ├── inspect                        ← semantic inspect <file>
│   ├── compare                        ← semantic compare <snap1> <snap2>
│   └── golden                         ← semantic golden create/update/test
│
└── Reporters
    ├── ConsoleReporter (Rich TUI)     ← Красивый вывод в терминал
    ├── MarkdownReporter               ← Отчёты как в Phase 13
    ├── JsonReporter                   ← Полные дампы для программ
    └── DiffReporter                   ← Сравнение снимков
```

---

## 🔗 Связь с Phase 15

**Phase 15** создала multi-provider архитектуру:
```toml
[providers.embedder]
type = "gemini"  # или "local-mlx" или "openai"

[providers.transcriber]  
type = "whisper"  # или "gemini"
```

**Phase 16** добавляет инспекцию:
```bash
# Инспектируем с текущим конфигом
semantic inspect audio.mp3

# Инспектируем с кастомным конфигом
semantic inspect audio.mp3 --config alt_config.toml

# Сравниваем результаты
semantic compare \
  snapshots/gemini_config/ \
  snapshots/whisper_config/
```

---

## 🎬 Примеры использования

### Use Case 1: Отладка нового провайдера

**Ситуация:** Внедрили локальный Whisper, хотим проверить качество.

```bash
# 1. Baseline с Gemini
semantic inspect audio.mp3 \
  --config gemini_config.toml \
  --save-snapshot snapshots/gemini/

# 2. Новый провайдер
semantic inspect audio.mp3 \
  --config whisper_config.toml \
  --save-snapshot snapshots/whisper/

# 3. Сравнение
semantic compare \
  snapshots/gemini/audio_mp3.json \
  snapshots/whisper/audio_mp3.json
```

**Вывод:**
```
╭──────────────────────────────────────────────────────╮
│  📊 Provider Comparison Report                       │
╰──────────────────────────────────────────────────────╯

Config A: gemini_config.toml (Gemini Audio API)
Config B: whisper_config.toml (Whisper MLX base)

┌─ Transcription Quality ─────────────────────────────┐
│ • Text length: 5432 chars vs 5398 chars (-0.6%)    │
│ • Word count: 892 vs 887 (-0.6%)                   │
│ • Processing time: 8.3s vs 12.7s (+53%)            │
│ • Model: gemini-1.5-flash vs whisper-base          │
└─────────────────────────────────────────────────────┘

┌─ Chunking Differences ──────────────────────────────┐
│ • Chunk count: 11 vs 13 (+2)                       │
│ • Avg chunk size: 494 chars vs 415 chars           │
│ • Reason: Whisper segments → natural pauses       │
└─────────────────────────────────────────────────────┘

┌─ Content Comparison ────────────────────────────────┐
│ Gemini chunk #3:                                    │
│ "...artificial intelligence and machine learning    │
│  have revolutionized the way we process data..."    │
│                                                     │
│ Whisper chunk #3:                                   │
│ "...artificial intelligence and machine learning    │
│  have revolutionised the way we process data..."    │
│                              ^^^                    │
│ ⚠️ UK vs US spelling difference                    │
└─────────────────────────────────────────────────────┘

✅ Recommendation: Whisper gives more natural chunks
⚠️ Trade-off: +53% slower processing
```

---

### Use Case 2: Гибридная конфигурация

**Ситуация:** Хотим использовать локальные embeddings (MLX) + облачное распознавание (Gemini).

```toml
# hybrid_config.toml
[providers.embedder]
type = "local-mlx"
model = "Qwen/Qwen3-Embedding-0.6B-4bit-MLX"

[providers.transcriber]
type = "gemini"
model = "gemini-1.5-flash"

[providers.llm]
type = "ollama"
model = "llama3.2"
base_url = "http://localhost:11434"
```

```bash
semantic inspect audio.mp3 --config hybrid_config.toml --interactive
```

**Интерактивный вывод:**
```
╭───────────────────────────────────────────────────╮
│  🔍 Interactive Inspection Mode                   │
│  File: audio.mp3                                  │
│  Config: hybrid_config.toml                       │
╰───────────────────────────────────────────────────╯

[1/6] Transcription (Gemini Audio API)...
⏳ Uploading file to Gemini...
⏳ Processing with gemini-1.5-flash...
✅ Done (8.2s)

┌─ Transcription Preview ──────────────────────────┐
│ Length: 5432 chars                                │
│ Words: 892                                        │
│ Language: en (confidence: 0.98)                   │
│                                                   │
│ First 500 chars:                                  │
│ "Welcome to this lecture on semantic search.     │
│  Today we'll explore how embeddings work and..."  │
└───────────────────────────────────────────────────┘

Press ENTER to continue, 's' to save, 'q' to quit...
> ENTER

[2/6] Splitting (SmartSplitter)...
✅ Done (5ms) - 11 chunks created

┌─ Chunk Distribution ─────────────────────────────┐
│ Chunk #1: 487 chars (text)                       │
│ Chunk #2: 523 chars (text)                       │
│ Chunk #3: 445 chars (text)                       │
│ ... (8 more)                                     │
└───────────────────────────────────────────────────┘

Press ENTER to continue...

[3/6] Context Formation...
✅ Done (3ms)

[4/6] Embedding (Local MLX - Qwen3-Embedding-0.6B)...
⏳ Loading model from cache...
⏳ Encoding 11 texts...
✅ Done (0.8s) - 11 vectors (768D each)

┌─ Embedding Stats ────────────────────────────────┐
│ Model: Qwen/Qwen3-Embedding-0.6B-4bit-MLX        │
│ Device: Apple M2 GPU                              │
│ Throughput: 13.75 texts/sec                       │
│ Memory: 412 MB                                    │
│                                                   │
│ Chunk #1 embedding preview:                       │
│ [-0.0234, 0.1123, -0.0891, 0.0445, ...]         │
│                                                   │
│ ✅ All vectors normalized (L2 norm = 1.0)        │
└───────────────────────────────────────────────────┘

Press ENTER to continue...

[5/6] Saving to database...
✅ Done (42ms) - Document ID: 156

[6/6] Generating summary (Ollama - llama3.2)...
⏳ Connecting to http://localhost:11434...
⏳ Generating response...
✅ Done (2.1s)

╭───────────────────────────────────────────────────╮
│  ✅ Processing Complete                           │
│  Total time: 11.3s                                │
│                                                   │
│  Providers used:                                  │
│  • Transcriber: Gemini (cloud, 8.2s)             │
│  • Embedder: Qwen3-MLX (local, 0.8s)             │
│  • LLM: Ollama (local, 2.1s)                     │
│                                                   │
│  Cost breakdown:                                  │
│  • Gemini API: $0.0012 (audio processing)        │
│  • Local compute: $0 (MLX + Ollama)              │
│  • Total: $0.0012                                │
╰───────────────────────────────────────────────────╯
```

---

### Use Case 3: A/B тестирование провайдеров

**Ситуация:** Выбираем лучший embedder для проекта.

```bash
# Создаём golden-file с эталонным поиском
semantic golden create \
  --query "machine learning algorithms" \
  --expected-docs "ml_intro.md,neural_networks.md" \
  --min-score 0.7 \
  --output golden/search_ml.json

# Тестируем Gemini embeddings
semantic golden test golden/search_ml.json \
  --config gemini_embeddings.toml

# Тестируем Local MLX embeddings  
semantic golden test golden/search_ml.json \
  --config mlx_embeddings.toml

# Тестируем OpenAI embeddings
semantic golden test golden/search_ml.json \
  --config openai_embeddings.toml
```

**Вывод:**
```
╭───────────────────────────────────────────────────╮
│  🧪 Golden File Test Results                      │
│  Test: golden/search_ml.json                      │
╰───────────────────────────────────────────────────╯

Query: "machine learning algorithms"
Expected: ml_intro.md (rank 1-2), neural_networks.md (rank 1-2)

┌─ Config: gemini_embeddings.toml ─────────────────┐
│ Provider: GeminiEmbedder (embedding-001)          │
│ Results:                                          │
│   1. ml_intro.md (score: 0.87) ✅                │
│   2. neural_networks.md (score: 0.82) ✅         │
│   3. deep_learning.md (score: 0.74)              │
│ Status: ✅ PASSED                                 │
│ Time: 1.2s                                        │
└───────────────────────────────────────────────────┘

┌─ Config: mlx_embeddings.toml ────────────────────┐
│ Provider: MLXEmbedder (Qwen3-0.6B)                │
│ Results:                                          │
│   1. neural_networks.md (score: 0.91) ✅         │
│   2. ml_intro.md (score: 0.89) ✅                │
│   3. transformers.md (score: 0.76)               │
│ Status: ✅ PASSED (better scores!)                │
│ Time: 0.3s (4x faster!)                          │
└───────────────────────────────────────────────────┘

┌─ Config: openai_embeddings.toml ─────────────────┐
│ Provider: OpenAIEmbedder (text-embedding-3-small) │
│ Results:                                          │
│   1. ml_intro.md (score: 0.85) ✅                │
│   2. deep_learning.md (score: 0.79)              │
│   3. neural_networks.md (score: 0.76) ⚠️         │
│ Status: ⚠️ PARTIAL (rank drift)                  │
│ Time: 0.9s                                        │
└───────────────────────────────────────────────────┘

🏆 Winner: mlx_embeddings.toml
   ✅ Better relevance scores
   ✅ 4x faster than Gemini
   ✅ Free (local compute)
   ✅ Offline-capable
```

---

## 🛠️ Технические детали

### Provider-Aware Inspector

**Ключевое отличие от Phase 13:**

Phase 13 Inspector был hardcoded под Gemini:
```python
# Phase 13 (старый код)
class PipelineInspector:
    def ingest_with_inspection(self, doc):
        # Жёстко завязан на GeminiEmbedder
        embeddings = self.core.embedder.embed_documents(...)  
        # Не знает о других провайдерах
```

Phase 16 Inspector работает с любыми провайдерами:
```python
# Phase 16 (новый код)
class ProviderInspector:
    def ingest_with_inspection(self, doc):
        # 1. Определяем типы провайдеров
        provider_info = {
            "embedder": {
                "type": type(self.core.embedder).__name__,
                "model": getattr(self.core.embedder, "model", "unknown"),
                "dimension": self.core.embedder.dimension,
                "max_tokens": self.core.embedder.max_tokens,
            },
            "transcriber": {
                "type": type(self.core.transcriber).__name__,
                "model": getattr(self.core.transcriber, "model", "unknown"),
            } if hasattr(self.core, "transcriber") else None,
        }
        
        # 2. Записываем метаданные провайдеров
        snapshot = InspectionSnapshot(
            config_hash=hash_config(self.core.config),
            providers=provider_info,
            timestamp=datetime.now(),
        )
        
        # 3. Перехватываем вызовы с контекстом провайдера
        with self.recorder.record_step("embedding", provider_info["embedder"]):
            embeddings = self.core.embedder.embed_documents(texts)
        
        # 4. Сохраняем артефакты с метками провайдера
        snapshot.add_embedding_data(
            provider="GeminiEmbedder",  # или "MLXEmbedder"
            model="embedding-001",       # или "Qwen3-0.6B"
            vectors=embeddings,
            timings=self.recorder.get_timings("embedding"),
        )
```

### Snapshot Structure

```json
{
  "snapshot_version": "1.0",
  "created_at": "2026-01-15T14:30:00Z",
  "config_hash": "a3f2b1c9",
  "config_file": "hybrid_config.toml",
  
  "providers": {
    "embedder": {
      "type": "MLXEmbedder",
      "model": "Qwen/Qwen3-Embedding-0.6B-4bit-MLX",
      "dimension": 768,
      "max_tokens": 8192,
      "device": "Apple M2 GPU"
    },
    "transcriber": {
      "type": "GeminiTranscriber",
      "model": "gemini-1.5-flash",
      "api_version": "v1beta"
    },
    "llm": {
      "type": "OllamaProvider",
      "model": "llama3.2",
      "base_url": "http://localhost:11434"
    }
  },
  
  "processing_steps": [
    {
      "step": "transcription",
      "provider": "GeminiTranscriber",
      "duration_ms": 8234,
      "input": {
        "file": "audio.mp3",
        "size_bytes": 2458392
      },
      "output": {
        "text_length": 5432,
        "word_count": 892,
        "language": "en"
      }
    },
    {
      "step": "splitting",
      "splitter": "SmartSplitter",
      "duration_ms": 5,
      "config": {
        "chunk_size": 512,
        "overlap": 50
      },
      "output": {
        "chunk_count": 11
      }
    },
    {
      "step": "embedding",
      "provider": "MLXEmbedder",
      "duration_ms": 823,
      "input": {
        "text_count": 11,
        "total_tokens": 4521
      },
      "output": {
        "vector_count": 11,
        "dimension": 768,
        "throughput_texts_per_sec": 13.37
      }
    }
  ],
  
  "chunks": [
    {
      "chunk_id": 1,
      "content": "Welcome to this lecture...",
      "context_text": "Document: audio.mp3\n\nWelcome...",
      "embedding": [-0.0234, 0.1123, ...],  // Full 768D
      "provider_metadata": {
        "embedder": "MLXEmbedder",
        "model": "Qwen3-0.6B"
      }
    }
  ],
  
  "total_duration_ms": 11289,
  "total_cost_usd": 0.0012
}
```

---

## 🎯 Ключевые фичи

### 1. Multi-Config Inspection

```bash
# Batch-инспекция с разными конфигами
semantic inspect audio.mp3 \
  --configs configs/*.toml \
  --output-dir snapshots/
  
# Результат:
snapshots/
├── gemini_full/audio_mp3.json       # Все Gemini
├── hybrid_mlx/audio_mp3.json        # MLX embeddings + Gemini transcription
├── local_only/audio_mp3.json        # Whisper + MLX + Ollama
└── openai_compat/audio_mp3.json     # OpenAI-compatible
```

### 2. Provider Performance Matrix

```bash
semantic compare --matrix snapshots/*/*.json
```

**Вывод:**
```
╭────────────────────────────────────────────────────────────╮
│  📊 Multi-Provider Performance Matrix                      │
╰────────────────────────────────────────────────────────────╯

File: audio.mp3 (2.3 MB, 3:45 duration)

                    │ Gemini  │ Hybrid  │ Local   │ OpenAI  │
                    │ Full    │ MLX     │ Only    │ Compat  │
────────────────────┼─────────┼─────────┼─────────┼─────────┤
Transcription       │ 8.2s    │ 8.2s    │ 12.7s   │ N/A     │
Provider            │ Gemini  │ Gemini  │ Whisper │ -       │
────────────────────┼─────────┼─────────┼─────────┼─────────┤
Embedding           │ 1.2s    │ 0.8s    │ 0.8s    │ 1.1s    │
Provider            │ Gemini  │ Qwen3   │ Qwen3   │ OpenAI  │
Dimension           │ 768     │ 768     │ 768     │ 1536    │
────────────────────┼─────────┼─────────┼─────────┼─────────┤
Chunks              │ 11      │ 11      │ 13      │ 11      │
Avg Chunk Size      │ 494     │ 494     │ 418     │ 494     │
────────────────────┼─────────┼─────────┼─────────┼─────────┤
Total Time          │ 9.8s    │ 9.4s    │ 13.9s   │ 9.7s    │
Cost (USD)          │ $0.0024 │ $0.0012 │ $0      │ $0.0018 │
────────────────────┼─────────┼─────────┼─────────┼─────────┤
Offline Capable     │ ❌      │ ⚠️ Part │ ✅      │ ❌      │
────────────────────┴─────────┴─────────┴─────────┴─────────┘

🏆 Best Performance: Hybrid MLX (9.4s, $0.0012)
🏆 Best Offline: Local Only (works without internet)
🏆 Best Quality: OpenAI Compat (1536D embeddings)
```

### 3. Regression Detection

```bash
# Создаём baseline
semantic inspect corpus/ \
  --config production.toml \
  --save-snapshot baselines/v1.0/

# После обновления конфига
semantic inspect corpus/ \
  --config production_v2.toml \
  --save-snapshot current/

# Автоматическая проверка регрессий
semantic compare --regression \
  baselines/v1.0/ \
  current/
```

**Вывод:**
```
╭────────────────────────────────────────────────────╮
│  🔍 Regression Analysis                            │
╰────────────────────────────────────────────────────╯

Comparing 127 documents:
  Baseline: baselines/v1.0/ (GeminiEmbedder)
  Current:  current/ (MLXEmbedder)

┌─ Chunk Count Changes ────────────────────────────┐
│ • Same: 98 docs (77%)                            │
│ • Increased: 23 docs (+1-3 chunks)               │
│ • Decreased: 6 docs (-1-2 chunks)                │
│ ⚠️ Max change: research.md (15 → 19 chunks)     │
└───────────────────────────────────────────────────┘

┌─ Embedding Drift ────────────────────────────────┐
│ • Avg cosine similarity: 0.76 (24% drift)        │
│ • High drift (>30%): 12 docs                     │
│ • Medium drift (10-30%): 87 docs                 │
│ • Low drift (<10%): 28 docs                      │
│                                                   │
│ ⚠️ CRITICAL: Different embedding dimensions!    │
│    Baseline: 768D (Gemini)                       │
│    Current:  768D (Qwen3) ✅ Compatible          │
└───────────────────────────────────────────────────┘

┌─ Search Quality Impact ──────────────────────────┐
│ Running 14 test queries...                       │
│ • Same results: 9 queries (64%)                  │
│ • Rank changes: 4 queries (ranking shifted)      │
│ • Missing results: 1 query (!)                   │
│                                                   │
│ 🔴 FAILED: "machine learning basics"            │
│    Expected: ml_intro.md (rank 1)                │
│    Got: neural_nets.md (rank 1)                  │
│    ml_intro.md moved to rank 3                   │
└───────────────────────────────────────────────────┘

🚨 REGRESSION DETECTED
   - 1 query returns wrong top result
   - Recommendation: Review MLXEmbedder config
```

---

## 📦 Итоговая структура

```
semantic_core/
├── core/
│   └── observatory/              # NEW: Debug Observatory
│       ├── inspector.py          # ProviderInspector
│       ├── recorder.py           # PipelineRecorder
│       ├── snapshot.py           # SnapshotManager
│       └── reporters/
│           ├── console.py        # Rich TUI
│           ├── markdown.py       # MD отчёты
│           ├── json.py           # JSON дампы
│           └── diff.py           # Comparison
│
├── cli/
│   └── commands/
│       ├── inspect_cmd.py        # NEW: semantic inspect
│       ├── compare_cmd.py        # NEW: semantic compare
│       └── golden_cmd.py         # NEW: semantic golden
│
└── tests/
    ├── e2e/audit/                # Существующие E2E тесты
    └── golden/                   # NEW: Golden-file тесты
        ├── search_quality/
        ├── chunking_stability/
        └── provider_compatibility/
```

---

## ⚠️ Риски и митигации

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Snapshot несовместимы между версиями | Средняя | Версионирование формата (`snapshot_version`) |
| Сравнение векторов разной размерности | Высокая | Автоопределение + warning перед сравнением |
| Golden-тесты медленные (реальные API) | Высокая | Мокирование провайдеров для CI, real API опционально |
| Слишком большие JSON снимки | Средняя | Опция `--compress` (gzip) для хранения |

---

## 🎓 Обучающие материалы

После реализации Phase 16 пользователь сможет:

1. **Экспериментировать без страха:** Любой конфиг можно "просветить" и откатить
2. **A/B тестировать провайдеры:** Объективное сравнение качества и скорости
3. **Отлаживать проблемы:** Пошаговая визуализация с точным указанием провайдера
4. **Предотвращать регрессии:** Golden-файлы как контракт качества
5. **Оптимизировать затраты:** Видеть стоимость каждого компонента

---

## 🚀 Roadmap подфаз

```
16.0 (Inspector Core)     2-3 дня   Foundation
    ↓
16.1 (CLI Inspect)        3-4 дня   User interface
    ↓
16.2 (Multi-Provider)     2-3 дня   Snapshot system
    ↓
16.3 (Comparison)         3-4 дня   Diff engine
    ↓
16.4 (Interactive)        2 дня     UX polish
    ↓
16.5 (Golden Files)       2-3 дня   Testing framework
    ↓
TOTAL: ~15-20 дней
```

---

## 🎯 Success Criteria

Phase 16 считается завершённой когда:

- ✅ `semantic inspect` работает с любым Phase 15 конфигом
- ✅ Можно сравнить снимки разных провайдеров
- ✅ Golden-файлы используются в CI для проверки регрессий
- ✅ Документация содержит примеры A/B тестирования
- ✅ Все E2E тесты из Phase 13 мигрированы на новый Inspector
