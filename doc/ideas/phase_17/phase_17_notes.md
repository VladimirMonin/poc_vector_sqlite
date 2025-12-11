# Phase 17 — Заметки и нюансы

> Здесь фиксируются все найденные несоответствия, баги, неясности при создании документации

---

## 🔍 Phase 17.1 — Local Embeddings

### ⚠️ Баг: max_tokens_override не реализован

**Где:** `semantic_core/core/factory.py` vs `semantic_core/infrastructure/local/embeddings/embedder.py`

**Проблема:**
```python
# factory.py line 96
return LocalEmbedder(
    model=config.providers_local.embedding_model,
    device=config.providers_local.device,
    max_tokens_override=config.providers_local.max_tokens,  # ← Передаётся
)

# embedder.py line 47
def __init__(
    self,
    model: str = "all-minilm",
    device: Optional[str] = None,  # ← НЕ ПРИНИМАЕТ max_tokens_override!
):
```

**Вопрос:** Нужно ли исправить до документации или задокументировать существующее API?

**Статус:** Зафиксировано для обсуждения.

---

### ✅ ИЗУЧЕНО: Qwen3 MRL truncation

**Контекст:**
- Qwen3-Embedding native dimension: 1024
- Текущая БД многих пользователей: 768 (Gemini embedding-001)
- Qwen3 поддерживает MRL (Matryoshka) 32-1024

**Источник исследования:** `doc/researches/Исследование Gemini Embedding v4_ Отчет.md`

**Механизм MRL (Matryoshka Representation Learning):**

Технология "упаковки" семантической информации в вектор:
- Модель обучается минимизировать ошибку для полного вектора И его подмножеств (64, 128, 256, 512 dims)
- Это заставляет упаковывать ВАЖНУЮ информацию (тема, тональность) в начальные измерения
- Тонкие нюансы (детали, контекст) — в "хвост" вектора
- Позволяет усекать вектор без катастрофической потери качества

**Алгоритм truncation (КРИТИЧНО!):**
```python
import numpy as np
from numpy.linalg import norm

# 1. Получить полный вектор
full_vec = np.array(embedder.embed_query("text"))  # 1024D

# 2. Усечь до целевой размерности
truncated = full_vec[:768]

# 3. РЕ-НОРМАЛИЗАЦИЯ (без этого — математически некорректно!)
# Эмбеддинги для cosine similarity должны иметь L2-norm = 1
normalized = truncated / norm(truncated)
```

**Почему нужна нормализация:**
- При усечении вектора его L2-норма уменьшается
- Косинусное расстояние вычисляется через скалярное произведение НОРМАЛИЗОВАННЫХ векторов
- Без нормализации: `dot(vec1, vec2) ≠ cos(vec1, vec2)` → результаты поиска некорректны

**Метрики качества (по Gemini embedding-001, 3072D → X):**
- 3072 → 768: Потеря <1-1.5% на MTEB benchmark
- 3072 → 256: Потеря ~3-4%, экономия памяти x12
- По аналогии для Qwen3: 1024 → 768 ≈ <1.5%, 1024 → 256 ≈ 3-5%

**Вывод для документации:**
1. **Основной способ** — пересоздание БД (простой, чистый, рекомендуемый)
2. **Advanced option** — MRL truncation (требует кода пользователя, нужен опыт)
3. В библиотеке **НЕ РЕАЛИЗУЕМ** автоматический truncation (решение пользователя)

**Qwen3 MRL range:** 32-1024 (по документации модели)

**Статус:** РЕШЕНО. Документировать оба способа с акцентом на пересоздание БД.

---

### ❓ Вопрос: needs_query_prefix для Qwen3

**Контекст:**
```python
# models.py line 41
"qwen3-embedding": ModelConfig(
    name="mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ",
    dimension=1024,
    max_tokens=8192,
    backend="mlx-lm",
    needs_query_prefix=False,  # ← FALSE
),
```

**Вопрос:** Qwen3 поддерживает asymmetric search через `prompt_name="query"` в sentence-transformers. Нужен ли префикс в MLX реализации?

**Находки из кода:**
- `embedder.py` line 169: реализация добавления `"query: {text}"`
- Сейчас для ВСЕХ моделей `needs_query_prefix=False`
- Тест `test_embed_query_adds_prefix_when_needed` проверяет механизм

**Источники:**
- Qwen3 blog: упоминает "instruction aware"
- sentence-transformers API: `encode(prompt_name="query")`
- HuggingFace model card: "The model supports query and document prompts"

**Гипотеза:**
Qwen3 в sentence-transformers использует:
- `model.encode(texts, prompt_name="query")` для запросов
- `model.encode(texts, prompt_name="document")` для документов

Но в MLX реализации через `mlx-lm` (низкоуровневый доступ) мы делаем прямой forward pass через слои ВООБЩЕ БЕЗ специальных промптов. Возможно именно поэтому `needs_query_prefix=False` — потому что используется базовая архитектура без instruction tokens.

**Для проверки:** Посмотреть есть ли разница в quality между:
1. MLX реализация (текущая)
2. sentence-transformers с `prompt_name="query"`

**Статус:** Требует E2E эксперимента (вне scope Phase 17.1 docs). Документировать текущее состояние (`False`).

---

### 📝 Нюанс: Кастомные модели

**Код:**
```python
# embedder.py line 68-71
if model not in MODELS:
    raise ValueError(
        f"Unknown model: {model}. "
        f"Available models: {list(MODELS.keys())}"
    )
```

**Проблема:** Нельзя использовать HuggingFace model ID напрямую (только preset keys).

**Вопрос:** Это задуманное поведение или ограничение? Документация должна объяснить почему.

**Статус:** Требует уточнения архитектурного решения.

---

### ✅ ИЗУЧЕНО: sentence-transformers vs MLX backends

**Контекст:**
- `all-minilm` и `bge-small` используют `mlx-embeddings` backend
- `qwen3-embedding` используе `mlx-lm` backend

**Из кода (`models.py` line 127):**
```python
# Qwen3-Embedding: прямой проход через слои (БЕЗ attention_mask!)
h = model.model.embed_tokens(input_ids)
for layer in model.model.layers:
    h = layer(h, mask=None, cache=None)
h = model.model.norm(h)
pooled = mx.mean(h, axis=1)  # Mean pooling
```

**Выводы:**

1. **mlx-embeddings backend:**
   - Высокоуровневый API (аналог sentence-transformers)
   - Работает с attention_mask, автоматический pooling
   - Для стандартных embedding моделей (BERT-like)
   - Используется: `all-minilm`, `bge-small`

2. **mlx-lm backend:**
   - Низкоуровневый доступ к слоям модели
   - Manual forward pass, manual pooling
   - Для LLM-based embeddings (decoder-only models)
   - Используется: `qwen3-embedding`

3. **Почему Qwen3 требует mlx-lm:**
   - Qwen3-Embedding — это НЕ отдельная embedding модель
   - Это LLM архитектура (decoder-only), используемая для embeddings
   - Нужен прямой доступ к transformer layers
   - mlx-embeddings не поддерживает такие модели

**Hardware requirements (КРИТИЧНО для документации):**

- **MLX Framework:** ТОЛЬКО Apple Silicon (M1/M2/M3/M4/M5)
- LocalEmbedder = macOS exclusive (MPS device)
- Windows/Linux: MLX не работает

**Альтернатива для Windows/Linux:**

```python
# Через sentence-transformers (PyTorch)
from sentence_transformers import SentenceTransformer

# Qwen3 ЕСТЬ на HuggingFace
model = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B")
embeddings = model.encode(["text"], device="cuda")  # или "cpu"
```

**Для документации:**
- Чётко указать: LocalEmbedder = macOS only
- Объяснить два backend с примерами моделей
- Дать альтернативный путь для Windows/Linux через кастомный embedder
- Упомянуть hardware requirements в начале секции (не в конце!)

**Статус:** РЕШЕНО. Документировать оба backend, hardware constraints, альтернативы.

---

## 📋 Чек-лист для документации

### Что ОБЯЗАТЕЛЬНО упомянуть:

- [x] **Hardware requirements** — MLX = macOS only (Apple Silicon M1+), Windows/Linux альтернатива
- [x] **Qwen3 dimension 1024** — пересоздание БД (основной) + MRL truncation (advanced)
- [x] **MRL mechanism** — алгоритм усечения с ре-нормализацией, метрики качества
- [x] **Два backend** — mlx-embeddings (high-level) vs mlx-lm (low-level для Qwen3)
- [x] **Только presets** — нельзя HuggingFace ID напрямую (architectural choice)
- [ ] **query prefix** — текущее состояние `False`, почему, альтернативы
- [ ] **max_tokens** — defaults для каждой модели (384/384/8192)
- [ ] **Lazy loading** — модель загружается при первом вызове
- [ ] **Device handling** — автодетект MPS/CPU fallback

### Что проверить в коде:

- [x] Реальные примеры использования LocalEmbedder в тестах
- [x] E2E tests: `test_qwen3_pipeline.py`, `test_qwen3_extended_pipeline.py`
- [x] Config integration: `semantic.toml` → `SemanticConfig` → `ComponentFactory`
- [x] Inspector artifacts: dimension metadata, MLX float16→numpy conversion
- [ ] Batching support: проверить как работает `embed_documents()`
- [ ] Error handling: что происходит при MPS недоступен

### Документы для создания:

1. **docs/concepts/13_local_embeddings.md** (~500-600 lines)
   - Теория: MRL, backends, hardware
   - Архитектура: ComponentFactory, LocalEmbedder, ModelConfig
   - Сравнение: Gemini vs OpenAI vs Local

2. **docs/guides/core/local-embeddings.md** (~500-600 lines)
   - Quick Start с semantic.toml
   - Пошаговая миграция с Gemini
   - Troubleshooting: dimension mismatch, hardware, memory
   - Advanced: MRL truncation script

3. **docs/reference/local-models.md** (~400-500 lines)
   - Таблица моделей: dimension, tokens, backend, RAM
   - Config reference: все параметры `[providers.local]`
   - API reference: LocalEmbedder methods

### Обновить существующие:

- **docs/concepts/11_multi_provider.md** — добавить Local provider с Qwen3
- **docs/guides/extending/custom-embedder.md** — примеры LocalEmbedder, Windows/Linux альтернатива
- [ ] Как инициализируется через ComponentFactory
- [ ] Поддержка других device кроме MPS
- [ ] Error handling при отсутствии MLX

---

## 🔗 Полезные источники

- Qwen3 Blog: https://qwenlm.github.io/blog/qwen3-embedding/
- mlx-lm GitHub: https://github.com/ml-explore/mlx-lm
- mlx-embeddings: https://github.com/ml-explore/mlx-embeddings
- sentence-transformers: https://www.sbert.net/

---

**Дата создания:** 11 декабря 2025  
**Автор:** GitHub Copilot  
**Статус:** Living document
