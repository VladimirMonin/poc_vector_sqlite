# Local Embeddings (MLX)

> Как работают локальные embeddings на Apple Silicon через MLX Framework

**Сложность:** 🟡 intermediate  
**Требует понимания:** Multi-Provider Architecture, Vector Search

---

## 🎯 Что это такое?

**LocalEmbedder** — это провайдер embeddings, работающий **полностью оффлайн** на вашем Mac с Apple Silicon (M1/M2/M3/M4/M5).

**Преимущества:**
- ⚡ **Скорость:** 20-50 токенов/сек на M2 Pro (без сетевых запросов)
- 🔒 **Приватность:** Данные не покидают устройство
- 💰 **Экономия:** Нет затрат на API
- 📦 **Оффлайн:** Работает без интернета

**Ограничения:**
- 🍎 **Только macOS:** MLX работает только на Apple Silicon
- 💾 **RAM:** Требуется 4-16 GB в зависимости от модели
- 🎯 **Качество:** Может уступать облачным моделям (зависит от задачи)

---

## 🧠 Доступные модели

LocalEmbedder поддерживает 3 preset-модели:

| Модель | Dimension | Max Tokens | Backend | RAM | Quality |
|--------|-----------|------------|---------|-----|---------|
| `all-minilm` | 384 | 512 | mlx-embeddings | ~2 GB | 🟡 Базовое |
| `bge-small` | 384 | 512 | mlx-embeddings | ~2 GB | 🟢 Хорошее |
| `qwen3-embedding` | 1024 | 8192 | mlx-lm | ~4 GB | 🟢🟢 Отличное |

### Рекомендации по выбору:

**all-minilm** (sentence-transformers/all-MiniLM-L6-v2):
- Самая лёгкая модель (~80M параметров)
- Подходит для прототипирования, MacBook Air 8GB
- Английский язык, базовое понимание

**bge-small** (BAAI/bge-small-en-v1.5):
- Золотая середина (~30M параметров)
- Хорошее качество для большинства задач
- Английский язык, улучшенное понимание контекста

**qwen3-embedding** (Qwen3-Embedding-0.6B, 4-bit quantized):
- Флагман среди локальных моделей (~600M параметров)
- Лучшее качество, многоязычность (включая русский)
- Поддержка **Matryoshka Representation Learning (MRL)**
- Требует больше RAM, но quality ≈ Gemini embedding-001

---

## ⚙️ Два backend: mlx-embeddings vs mlx-lm

LocalEmbedder использует **два разных backend** в зависимости от типа модели:

### mlx-embeddings (High-Level)

**Модели:** `all-minilm`, `bge-small`

```python
# Упрощенно
from mlx_embeddings import EmbeddingModel

model = EmbeddingModel.from_registry("all-MiniLM-L6-v2")
embeddings = model.encode(["text"], pool=True)
# ↑ Автоматический pooling, attention mask
```

**Характеристики:**
- Высокоуровневый API (аналог sentence-transformers)
- Автоматическая обработка attention mask
- Стандартные embedding модели (BERT-like, encoder-only)
- Проще, быстрее, меньше памяти

### mlx-lm (Low-Level)

**Модели:** `qwen3-embedding`

```python
# Упрощенно (из models.py line 127)
from mlx_lm import load

model, tokenizer = load("mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ")

# Manual forward pass через transformer layers
h = model.model.embed_tokens(input_ids)
for layer in model.model.layers:
    h = layer(h, mask=None, cache=None)
h = model.model.norm(h)

# Manual mean pooling
pooled = mx.mean(h, axis=1)
```

**Характеристики:**
- Низкоуровневый доступ к слоям модели
- Manual forward pass и pooling
- Для LLM-based embeddings (decoder-only models)
- Qwen3 — это LLM архитектура, используемая для embeddings

**Почему так?**
Qwen3-Embedding НЕ является отдельной embedding моделью. Это decoder-only LLM (как GPT), обученная генерировать качественные embeddings через hidden states. Для этого требуется прямой доступ к transformer layers, который предоставляет mlx-lm.

---

## 🪆 Matryoshka Representation Learning (MRL)

**MRL** — революционная технология, позволяющая **усекать** вектор без катастрофической потери качества.

### Как это работает?

Традиционные embeddings распределяют информацию **равномерно** по всему вектору:

```
Обычная модель: [0.12, 0.45, 0.89, ..., 0.34, 0.67]
                 ↑________________важная информация равномерно_________________↑
Усечение 1024→512: Теряем 50% информации → quality падает на 30-40%
```

**MRL модели обучаются иначе:**

```
MRL модель:     [0.89, 0.78, 0.65, ..., 0.12, 0.03]
                 ↑____важное____↑  ↑___менее важное___↑
Усечение 1024→512: Теряем детали, но суть остаётся → quality падает <5%
```

**Секрет:** Модель обучается минимизировать ошибку не только для полного вектора (1024D), но и для его **подмножеств** (64D, 128D, 256D, 512D, ...).

Это заставляет упаковывать:
- **Важное** (тема, тональность, основная семантика) → в **начало** вектора
- **Детали** (нюансы, контекст) → в **хвост** вектора

### Qwen3 MRL support

Qwen3-Embedding-0.6B поддерживает MRL с диапазоном **32-1024** dimensions:

```
Native: 1024D  (full quality)
↓
768D  (потеря <1.5%)
512D  (потеря ~2-3%)
256D  (потеря ~3-5%)
128D  (потеря ~8-10%)
64D   (потеря ~15-20%)
32D   (потеря >25%, не рекомендуется)
```

### Алгоритм truncation

**КРИТИЧНО:** При усечении вектора **обязательна ре-нормализация!**

```python
import numpy as np
from numpy.linalg import norm

# 1. Получить полный вектор
full_vec = np.array(embedder.embed_query("text"))  # 1024D

# 2. Усечь до целевой размерности
truncated = full_vec[:768]  # Берём первые 768 измерений

# 3. РЕ-НОРМАЛИЗАЦИЯ (БЕЗ ЭТОГО — МАТЕМАТИЧЕСКИ НЕКОРРЕКТНО!)
normalized = truncated / norm(truncated)
```

**Почему нужна нормализация?**

Embeddings для **cosine similarity** должны иметь L2-norm = 1 (единичная длина вектора).

При усечении L2-норма уменьшается:
```
full_vec:      norm = 1.0000
truncated:     norm = 0.8764  ← Меньше!
```

Косинусное расстояние вычисляется через **скалярное произведение нормализованных векторов**:

```
cos(v1, v2) = dot(v1, v2) / (norm(v1) * norm(v2))
            = dot(v1, v2)  # если norm = 1
```

Без ре-нормализации:
- `dot(truncated_v1, truncated_v2)` ≠ `cos(v1, v2)`
- Результаты поиска математически **некорректны**
- Ranking нарушен

---

## 🔄 Сравнение с Cloud Providers

| Характеристика | Gemini | OpenAI | Local (Qwen3) |
|---------------|--------|--------|---------------|
| **Dimension** | 768 | 1536/3072 | 1024 |
| **Max tokens** | 2048 | 8191 | 8192 |
| **Latency** | 200-500ms | 150-300ms | 20-50ms |
| **Cost** | $0.025/1M chars | $0.13/1M tokens | FREE |
| **Privacy** | ❌ Данные в cloud | ❌ Данные в cloud | ✅ Локально |
| **Offline** | ❌ Нужен интернет | ❌ Нужен интернет | ✅ Работает оффлайн |
| **Quality** | 🟢🟢🟢 Excellent | 🟢🟢🟢 Excellent | 🟢🟢 Very Good |
| **Hardware** | Любое | Любое | 🍎 macOS only |

### Когда использовать Local:

✅ **Хорошо подходит:**
- Прототипирование без API ключей
- Приватные данные (медицина, финансы)
- Высокая частота запросов (тысячи в минуту)
- Работа без интернета
- Экономия на больших объёмах

❌ **Не подходит:**
- Максимальное качество critical (юридические документы)
- Windows/Linux окружение (нужна альтернатива)
- MacBook Air 8GB + большие объёмы (OOM risk)

---

## 🖥️ Hardware Requirements

### Минимальные требования:

**Процессор:**
- Apple M1 / M2 / M3 / M4 / M5 (любой)
- MLX Framework работает **ТОЛЬКО** на Apple Silicon

**Операционная система:**
- macOS 13.3+ (Ventura) или новее
- Более старые версии могут не поддерживать MLX

**Оперативная память (по моделям):**

```
all-minilm:        2 GB  (MacBook Air 8GB ✅)
bge-small:         2 GB  (MacBook Air 8GB ✅)
qwen3-embedding:   4 GB  (MacBook Air 8GB ⚠️  tight)
                         (MacBook Pro 16GB ✅)
```

**Device detection:**
LocalEmbedder автоматически определяет доступное устройство:

```python
# semantic_core/infrastructure/local/embeddings/embedder.py
def _get_device(device_override: Optional[str]) -> str:
    if device_override:
        return device_override
    
    # Проверяем MPS (Metal Performance Shaders)
    import mlx.core as mx
    if mx.metal.is_available():
        return "mps"
    
    # Fallback на CPU (медленно!)
    logger.warning("MPS недоступен, используется CPU")
    return "cpu"
```

### Windows / Linux альтернатива

MLX не работает на Windows/Linux. Используйте **sentence-transformers** с PyTorch:

```python
from sentence_transformers import SentenceTransformer

# Qwen3 доступен на HuggingFace
model = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B")

# GPU (CUDA)
embeddings = model.encode(["text"], device="cuda")

# CPU (медленно, но работает)
embeddings = model.encode(["text"], device="cpu")
```

Для интеграции с SemanticCore создайте **кастомный embedder** (см. [extending/custom-embedder.md](../guides/extending/custom-embedder.md)).

---

## 🏗️ Архитектура интеграции

### ComponentFactory

LocalEmbedder создаётся через **ComponentFactory** (Phase 15.4):

```python
# semantic_core/core/factory.py
class ComponentFactory:
    @staticmethod
    def create_embedder(config: SemanticConfig) -> BaseEmbedder:
        provider = config.defaults.embedding_provider
        
        if provider == "local":
            from semantic_core.infrastructure.local.embeddings import LocalEmbedder
            
            return LocalEmbedder(
                model=config.providers_local.embedding_model,
                device=config.providers_local.device,
            )
        
        elif provider == "gemini":
            from semantic_core.infrastructure.gemini import GeminiEmbedder
            # ...
```

### Configuration

```toml
# semantic.toml
[defaults]
embedding_provider = "local"

[providers.local]
embedding_model = "qwen3-embedding"  # или "all-minilm", "bge-small"
device = "mps"                       # или "cpu", автодетект если не указан
```

### Lazy Loading

Модель **не загружается** при создании `LocalEmbedder()`. Загрузка происходит при **первом вызове**:

```python
embedder = LocalEmbedder("qwen3-embedding")  # Быстро
# Модель ещё не загружена в память

vector = embedder.embed_query("text")  # Первый вызов
# ↑ Здесь загружается модель (5-10 сек для Qwen3)
# Последующие вызовы будут мгновенными
```

**Зачем?**
- Ускорение старта приложения
- Экономия памяти если embedder не используется
- Возможность создать embedder для проверки конфига без загрузки модели

---

## 🔍 Query Prefix (Asymmetric Search)

**Asymmetric Search** — поиск, где запрос и документы имеют **разную природу**:

```
Query:    "Почему небо голубое?"          (вопрос)
Document: "Рэлеевское рассеяние вызывает..." (ответ)
```

Некоторые модели требуют **префикс** для query, чтобы понять контекст:

```python
# sentence-transformers API
model.encode(["text"], prompt_name="query")     # Для запросов
model.encode(["text"], prompt_name="document")  # Для документов
```

### Текущее состояние LocalEmbedder

**Все модели:** `needs_query_prefix = False`

```python
# semantic_core/infrastructure/local/embeddings/models.py
"qwen3-embedding": ModelConfig(
    name="mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ",
    dimension=1024,
    max_tokens=8192,
    backend="mlx-lm",
    needs_query_prefix=False,  # ← Не используется
)
```

**Почему?**

Через `mlx-lm` (низкоуровневый backend) мы делаем **прямой forward pass** через слои модели:

```python
# БЕЗ instruction tokens, БЕЗ prompt engineering
h = model.model.embed_tokens(input_ids)
for layer in model.model.layers:
    h = layer(h, mask=None, cache=None)
pooled = mx.mean(h, axis=1)
```

Это **базовая LLM архитектура без специальных промптов**.

В sentence-transformers реализация Qwen3 использует специальные instruction tokens для asymmetric search, но в MLX мы работаем напрямую с моделью.

**Влияние на качество:**
- Для **symmetric search** (документ-документ) — нет разницы
- Для **asymmetric search** (запрос-документ) — может быть небольшая потеря качества (~2-5%)
- Практически для большинства RAG задач разница незначительна

---

## 💡 Ключевые моменты

1. **Hardware:** LocalEmbedder = macOS only (Apple Silicon). Windows/Linux → sentence-transformers
2. **Qwen3 лучший:** 1024D, MRL support, multilingual, quality ≈ Gemini
3. **MRL truncation:** Усечение `vec[:N]` + обязательная ре-нормализация
4. **Два backend:** mlx-embeddings (high-level) для BERT-like, mlx-lm (low-level) для LLM-based
5. **Lazy loading:** Модель загружается при первом вызове (5-10 сек)
6. **Preset only:** Нельзя использовать произвольные HuggingFace model IDs

---

## 📚 Дополнительно

- [local-embeddings.md](../guides/core/local-embeddings.md) — практический гайд
- [local-models.md](../reference/local-models.md) — справочник моделей и API
- [multi_provider.md](11_multi_provider.md) — архитектура провайдеров
- [custom-embedder.md](../guides/extending/custom-embedder.md) — Windows/Linux альтернатива
