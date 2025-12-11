# Phase 17.1: Local Embeddings Documentation

> Актуализация документации локальных моделей embeddings (Qwen3, BGE, MiniLM)

---

## 📦 Статус

- **Фаза:** 17.1
- **Зависит от:** Phase 15.0-15.5 (реализация), Phase 17.0 (аудит)
- **Блокирует:** 17.3 (API Reference)
- **Приоритет:** 🔥 Критический
- **Оценка:** 2-3 дня

---

## 🎯 Проблема

**Текущая ситуация:**

1. `LocalEmbedder` реализован с поддержкой Qwen3-Embedding-0.6B (`"qwen3-embedding"` preset)
2. Код содержит 3 предустановленных модели: `all-minilm`, `qwen3-embedding`, `bge-small`
3. **Документация НЕ УПОМИНАЕТ** Qwen3 вообще

**Разрыв между кодом и доками:**

| Аспект | В коде | В документации |
|--------|--------|----------------|
| Qwen3-Embedding | ✅ Реализован | ❌ Не упомянут |
| Размерность 1024D | ✅ Есть | ❌ Нет в таблицах |
| MRL truncation | ✅ Поддержка через MLX | ❌ Не объяснено |
| Backend mlx-lm | ✅ Используется для Qwen3 | ❌ Не задокументирован |
| prompt_name | ✅ needs_query_prefix в коде | ❌ Не объяснено |

**Последствия:**

- Пользователи не знают про Qwen3 (лучшую локальную модель)
- Непонятно как решать dimension mismatch (1024 vs 768)
- Нет гайда по выбору модели для своего hardware

---

## 💡 Решение

Создать **3 новых документа** и обновить **2 существующих**.

### Новые документы

#### 1. `docs/concepts/13_local_embeddings.md`

**Назначение:** Концептуальное объяснение локальных моделей.

**Структура:**

```markdown
# Local Embeddings — Локальные модели

## Что это такое?
- MLX vs sentence-transformers
- CPU/GPU/MPS acceleration
- Offline работа

## Преимущества и недостатки
- ✅ Бесплатно, приватность, offline
- ❌ Требует GPU, качество ниже облака

## Архитектура
- mlx-embeddings backend (MiniLM, BGE)
- mlx-lm backend (Qwen3)
- Почему два бэкенда?

## Выбор модели по hardware
- Apple Silicon: Qwen3-Embedding-0.6B (1024D)
- CUDA GPU: BGE-small (384D), Qwen3
- CPU only: all-MiniLM-L6-v2 (384D)

## MRL и размерности
- Qwen3: native 1024D, truncate 32-1024
- Как обрезать под существующую БД
```

#### 2. `docs/guides/core/local-embeddings.md`

**Назначение:** Практический гайд по настройке.

**Структура:**

```markdown
# Local Embeddings Setup

## Установка зависимостей
pip install semantic-core[local-embeddings]

## Конфигурация semantic.toml
[defaults]
embedding_provider = "local"

[providers.local]
embedding_model = "qwen3-embedding"  # NEW!
device = "mps"  # Apple Silicon
max_tokens = 8192

## Предустановленные модели
| Model | Dimension | Max Tokens | Backend | Hardware |
|-------|-----------|------------|---------|----------|
| qwen3-embedding | 1024 | 8192 | mlx-lm | Apple Silicon |
| all-minilm | 384 | 512 | mlx-embeddings | CPU/GPU |
| bge-small | 384 | 512 | mlx-embeddings | CPU/GPU |

## Кастомные модели (HuggingFace)
embedding_model = "sentence-transformers/all-mpnet-base-v2"

## Решение dimension mismatch
### Проблема: БД 768D, модель 1024D

### Решение 1: Пересоздать БД
semantic reset --confirm
semantic ingest ./docs/

### Решение 2: MRL truncation
# Qwen3 поддерживает обрезку через MLX
# Настройка в config (будет в Phase 17.4)

## Benchmark производительности
MacBook M3 Pro:
- Qwen3: ~50 docs/sec
- MiniLM: ~80 docs/sec

RTX 3080:
- BGE-small: ~120 docs/sec
```

#### 3. `docs/reference/local-models.md`

**Назначение:** Справочник всех локальных моделей.

**Структура:**

```markdown
# Local Models Reference

## Embedding Models

### qwen3-embedding
- **HuggingFace:** mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ
- **Dimension:** 1024 (native), 32-1024 (MRL)
- **Max Tokens:** 8192
- **Parameters:** 600M (4-bit quantized)
- **Backend:** mlx-lm
- **Hardware:** Apple Silicon (MPS)
- **Languages:** 100+ (multilingual)
- **Use Case:** Best quality for local, supports long context

### all-minilm
- **HuggingFace:** mlx-community/all-MiniLM-L6-v2-4bit
- **Dimension:** 384
- **Max Tokens:** 512
- **Parameters:** 22M
- **Backend:** mlx-embeddings
- **Hardware:** CPU/GPU/MPS
- **Languages:** English primary
- **Use Case:** Fast, lightweight, good for demos

### bge-small
- **HuggingFace:** mlx-community/bge-small-en-v1.5-4bit
- **Dimension:** 384
- **Max Tokens:** 512
- **Parameters:** 33M
- **Backend:** mlx-embeddings
- **Hardware:** CPU/GPU/MPS
- **Languages:** English
- **Use Case:** Good quality/speed balance

## Vision Models (Phase 15.1)

### Qwen3-VL
- **HuggingFace:** Qwen/Qwen2.5-VL-4B
- **Use Case:** Image/Video analysis
- **Hardware:** Apple Silicon

## Audio Models (Phase 15.2)

### Whisper Base
- **Parameters:** 74M
- **Use Case:** Fast transcription
- **Hardware:** CPU/GPU/MPS

### Whisper Large-v3-turbo
- **Parameters:** 809M
- **Use Case:** High quality transcription
- **Hardware:** GPU recommended

## Comparison Matrix

| Model | Type | Dimension | Speed | Quality | Memory | Hardware |
|-------|------|-----------|-------|---------|--------|----------|
| qwen3-embedding | Embed | 1024 | ⚡⚡⚡ | ⭐⭐⭐⭐⭐ | ~500MB | MPS |
| all-minilm | Embed | 384 | ⚡⚡⚡⚡⚡ | ⭐⭐⭐ | ~90MB | Any |
| bge-small | Embed | 384 | ⚡⚡⚡⚡ | ⭐⭐⭐⭐ | ~130MB | Any |
| whisper-base | Audio | - | ⚡⚡⚡⚡ | ⭐⭐⭐ | ~140MB | Any |
| whisper-large-v3 | Audio | - | ⚡⚡ | ⭐⭐⭐⭐⭐ | ~1.5GB | GPU |
```

---

### Обновления существующих документов

#### 4. `docs/concepts/11_multi_provider.md` (UPDATE)

**Добавить секцию "Local Embeddings Models":**

```markdown
## 📊 Сравнение провайдеров

### Embeddings

| Провайдер | Модель | Размерность | Скорость | Качество | Стоимость |
|-----------|--------|-------------|----------|----------|-----------|
| Gemini | `text-embedding-004` | 768 | ⚡⚡⚡ | ⭐⭐⭐⭐⭐ | $0.00001/1K tokens |
| **Local** | **`qwen3-embedding`** | **1024** | **⚡⚡⚡** | **⭐⭐⭐⭐⭐** | **FREE** | <!-- NEW -->
| Local | `all-MiniLM-L6-v2` | 384 | ⚡⚡⚡⚡ | ⭐⭐⭐ | FREE |
| Local | `bge-small-en` | 384 | ⚡⚡⚡⚡ | ⭐⭐⭐⭐ | FREE |
```

**Обновить пример конфигурации:**

```toml
[providers.local]
device = "mps"
embedding_model = "qwen3-embedding"  # ← БЫЛО: all-MiniLM-L6-v2
whisper_model = "base"
```

#### 5. `docs/guides/extending/custom-embedder.md` (UPDATE)

**Добавить раздел "Using LocalEmbedder":**

```markdown
## Пример: LocalEmbedder (MLX) 🏠

```python
from semantic_core.infrastructure.local.embeddings import LocalEmbedder

# Предустановленная модель
embedder = LocalEmbedder(
    model="qwen3-embedding",  # Лучшая локальная модель
    device="mps",             # Apple Silicon
    max_tokens_override=8192  # Опционально
)

# Кастомная модель
embedder = LocalEmbedder(
    model="sentence-transformers/all-mpnet-base-v2"
)

# Использование
vectors = embedder.embed_documents(["doc1", "doc2"])
query_vec = embedder.embed_query("search query")

print(f"Dimension: {embedder.dimension}")      # 1024
print(f"Max tokens: {embedder.max_tokens}")    # 8192
```

**Доступные модели:**
- `qwen3-embedding` (1024D, 8K tokens)
- `all-minilm` (384D, 512 tokens)
- `bge-small` (384D, 512 tokens)
- Любая модель из HuggingFace sentence-transformers
```

---

## 📂 Структура файлов после обновления

```
docs/
├── concepts/
│   ├── 11_multi_provider.md          # UPDATE: добавить Qwen3 в таблицы
│   └── 13_local_embeddings.md        # NEW: концепция локальных моделей
│
├── guides/
│   ├── core/
│   │   └── local-embeddings.md       # NEW: практический гайд
│   └── extending/
│       └── custom-embedder.md        # UPDATE: пример LocalEmbedder
│
└── reference/
    └── local-models.md                # NEW: справочник моделей
```

---

## ✅ Acceptance Criteria

### 1. Qwen3 упомянут везде

- [ ] Таблица в `11_multi_provider.md` содержит `qwen3-embedding`
- [ ] Примеры конфигов используют Qwen3 (не MiniLM)
- [ ] README.md упоминает Qwen3 как рекомендованную локальную модель

### 2. Понятно как выбрать модель

- [ ] Таблица comparison с hardware requirements
- [ ] Benchmark данные (speed, quality, memory)
- [ ] Рекомендации для разных сценариев

### 3. Решена проблема dimension mismatch

- [ ] Объяснён MRL truncation
- [ ] Два способа решения (пересоздать БД или truncate)
- [ ] Примеры конфигурации

### 4. API Reference полный

- [ ] `LocalEmbedder.__init__()` параметры
- [ ] `ModelConfig` структура
- [ ] Все 3 preset модели
- [ ] Backend различия (mlx-embeddings vs mlx-lm)

---

## 🎨 Стиль документации

Следовать гайду: `doc/architecture/00_documentation_style_guide.md`

**Ключевые принципы:**

1. **Минимум кода, максимум объяснений**
   - Не дублировать код из репозитория
   - Фокус на концептах и паттернах

2. **Таблицы для сравнения**
   - Модели, провайдеры, hardware
   - Чёткие критерии выбора

3. **Практические примеры**
   - Реальные use case
   - Типичные ошибки и их решения

4. **Связанные ресурсы**
   - Ссылки на другие документы
   - Ссылки на архитектурный сериал

---

## 🔗 Связанные задачи

| Задача | Зависимость | Статус |
|--------|-------------|--------|
| Phase 17.0 | Аудит документации | ✅ Done |
| **Phase 17.1** | **Local Embeddings Docs** | **🚧 Current** |
| Phase 17.2 | Flask Integration Guide | ⏳ Pending |
| Phase 17.3 | API Reference Updates | ⏳ Blocked by 17.1 |
| Phase 17.4 | Configuration Reference | ⏳ Blocked by 17.1 |

---

## 📊 Метрики успеха

- **Полнота:** Qwen3 упомянут в 5+ местах (concepts, guides, reference, README)
- **Кларити:** Новый пользователь может выбрать модель за 5 минут
- **Актуальность:** Docs == Code (нет разрыва)
- **Расширяемость:** Легко добавить новую модель в будущем

---

## 🚀 План реализации

### День 1: Создание новых документов

1. `docs/concepts/13_local_embeddings.md` (2-3 часа)
2. `docs/guides/core/local-embeddings.md` (2-3 часа)

### День 2: Справочник и обновления

3. `docs/reference/local-models.md` (2-3 часа)
4. Обновить `11_multi_provider.md` (1 час)
5. Обновить `custom-embedder.md` (1 час)

### День 3: Проверка и интеграция

6. Обновить `docs/README.md` со ссылками
7. Проверить все ссылки (internal consistency)
8. Прогнать через spell checker
9. Review структуры и completeness

---

## 🎯 Будущие расширения (out of scope)

Эти задачи **НЕ** входят в Phase 17.1, но должны быть учтены в структуре:

### Phase 18+: Новые локальные модели

Когда появятся новые модели (например, BGE-M3, E5-mistral), достаточно:

1. Добавить preset в `semantic_core/infrastructure/local/embeddings/models.py`
2. Добавить строку в `docs/reference/local-models.md`
3. Обновить comparison таблицу в `11_multi_provider.md`

**Структура документации готова к расширению.**

### Phase 19+: Django Integration

Когда появится Django интеграция, создать:

- `docs/guides/integrations/django.md` (аналог `flask.md` из 17.2)
- Обновить `docs/guides/integrations/architecture.md` (добавить Django пример)

**Паттерн интеграций уже заложен в Phase 17.2.**

---

**Статус:** 📝 Draft | **Автор:** GitHub Copilot | **Дата:** 11 декабря 2025
