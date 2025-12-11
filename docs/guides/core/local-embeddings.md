# Local Embeddings Guide

> Практическое руководство по настройке и использованию локальных embeddings

**Время чтения:** 10 минут  
**Требования:** macOS с Apple Silicon (M1+), Python 3.10+

---

## 🚀 Quick Start

### 1. Установка зависимостей

```bash
# Базовый пакет
pip install semantic-core

# Опциональные зависимости для Local provider
pip install "semantic-core[local]"
```

Это установит:
- `mlx-embeddings` — для all-minilm, bge-small
- `mlx-lm` — для qwen3-embedding
- `sentence-transformers` — утилиты и токенизаторы

### 2. Настройка конфигурации

Создайте или отредактируйте `semantic.toml`:

```toml
[defaults]
embedding_provider = "local"

[providers.local]
embedding_model = "qwen3-embedding"
device = "mps"  # или "cpu" для fallback
```

### 3. Первый запуск

```python
from semantic_core import SemanticCore

# Создаём core с конфигом
core = SemanticCore()

# Первый вызов загрузит модель (5-10 сек для Qwen3)
vector = core.embedder.embed_query("Hello, world!")

print(f"Dimension: {len(vector)}")  # 1024 для qwen3-embedding
print(f"Vector preview: {vector[:5]}")
```

**Вывод:**
```
📦 Загрузка модели mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ...
✓ Модель загружена (6.2 сек)
Dimension: 1024
Vector preview: [ 0.0234 -0.1567  0.3421  0.0982 -0.2134]
```

### 4. Индексация документов

```bash
# CLI
semantic ingest ./docs/

# Python
from pathlib import Path

docs_path = Path("./docs")
core.ingest_path(docs_path)
```

**Первая индексация займёт время** (загрузка модели + векторизация). Последующие будут быстрее.

---

## 🔄 Миграция с Gemini на Local

### Сценарий: У вас уже есть БД с Gemini embeddings (768D), хотите перейти на Qwen3 (1024D)

**Проблема:** Размерность векторов изменилась — старые embeddings **несовместимы**.

### Решение 1: Пересоздание БД (рекомендуется)

```bash
# 1. Бэкап старой БД
cp semantic.db semantic_gemini_backup.db

# 2. Удалить старую БД
rm semantic.db

# 3. Обновить конфиг
echo '[defaults]
embedding_provider = "local"

[providers.local]
embedding_model = "qwen3-embedding"' > semantic.toml

# 4. Переиндексация
semantic ingest ./docs/
```

**Преимущества:**
- ✅ Просто и надёжно
- ✅ Чистая БД без артефактов
- ✅ Не требует кода

**Недостатки:**
- ⏱️ Требует времени на переиндексацию (зависит от объёма)

### Решение 2: MRL Truncation (advanced)

Если у вас **огромная БД** и переиндексация займёт часы — можно использовать MRL truncation.

**⚠️ Внимание:** Это продвинутый метод, требует написания миграционного скрипта!

```python
# migrate_gemini_to_qwen3.py
import sqlite3
import numpy as np
from numpy.linalg import norm
from semantic_core import SemanticCore

# 1. Подключаемся к БД
conn = sqlite3.connect("semantic.db")
cursor = conn.cursor()

# 2. Создаём новый embedder (Qwen3)
core = SemanticCore()
new_embedder = core.embedder  # LocalEmbedder с qwen3-embedding

# 3. Читаем все chunks
cursor.execute("SELECT id, content FROM chunks")
chunks = cursor.fetchall()

print(f"Найдено {len(chunks)} чанков для миграции")

# 4. Генерируем новые embeddings и усекаем до 768D
for chunk_id, content in chunks:
    # Генерируем 1024D вектор
    full_vec = new_embedder.embed_query(content)
    
    # Усекаем до 768D (MRL)
    truncated = full_vec[:768]
    
    # КРИТИЧНО: Ре-нормализация!
    normalized = truncated / norm(truncated)
    
    # Обновляем в БД
    blob = normalized.astype(np.float32).tobytes()
    cursor.execute("UPDATE chunks SET embedding = ? WHERE id = ?", (blob, chunk_id))

conn.commit()
conn.close()

print("✓ Миграция завершена")
```

**Преимущества:**
- ⚡ Быстрее для огромных БД (не нужен парсинг документов)
- 💾 Сохраняет metadata, timestamps

**Недостатки:**
- 🔧 Требует написания скрипта
- ⚠️ Потеря качества ~1-5% (из-за truncation)
- 📦 Схема БД остаётся 768D (не использует полную мощь 1024D)

**Рекомендация:** Используйте MRL truncation только для **временной миграции**. Затем запланируйте полную переиндексацию с 1024D.

---

## 🎛️ Выбор модели

### По качеству vs скорости

```python
# Быстрая модель (для прототипирования)
[providers.local]
embedding_model = "all-minilm"  # 384D, ~2 GB RAM

# Баланс (production для англоязычных задач)
[providers.local]
embedding_model = "bge-small"   # 384D, ~2 GB RAM

# Максимальное качество (production, multilingual)
[providers.local]
embedding_model = "qwen3-embedding"  # 1024D, ~4 GB RAM
```

### По RAM бюджету

**MacBook Air 8GB:**
```toml
[providers.local]
embedding_model = "bge-small"  # Оставляет ~6 GB для OS и других приложений
```

**MacBook Pro 16GB:**
```toml
[providers.local]
embedding_model = "qwen3-embedding"  # Комфортно
```

**MacBook Pro 32GB+:**
```toml
[providers.local]
embedding_model = "qwen3-embedding"  # + можно запустить локальный LLM одновременно
```

### По языку

**Английский:**
- ✅ all-minilm, bge-small, qwen3-embedding (все хороши)

**Русский:**
- ❌ all-minilm (слабо)
- ⚠️ bge-small (базово)
- ✅ qwen3-embedding (отлично)

**Многоязычные задачи:**
- ✅ qwen3-embedding (единственный вариант)

---

## 🐛 Troubleshooting

### Проблема: "MPS device not available"

**Причина:** MLX не может использовать Apple Metal (GPU).

**Решение:**

1. **Проверьте macOS версию:**
   ```bash
   sw_vers  # Должна быть 13.3+ (Ventura или новее)
   ```

2. **Fallback на CPU:**
   ```toml
   [providers.local]
   device = "cpu"  # Медленно, но работает
   ```

3. **Если используете Intel Mac:**
   ```
   ❌ LocalEmbedder не поддерживается на Intel Mac.
   → Используйте Gemini/OpenAI или кастомный embedder с sentence-transformers
   ```

### Проблема: "Out of Memory (OOM)"

**Причина:** Модель + другие приложения превысили доступную RAM.

**Решения:**

1. **Переключитесь на лёгкую модель:**
   ```toml
   [providers.local]
   embedding_model = "bge-small"  # Вместо qwen3-embedding
   ```

2. **Закройте тяжёлые приложения:**
   - Chrome с 50+ вкладками
   - Docker Desktop
   - Другие LLM модели

3. **Уменьшите batch size:**
   ```python
   # Вместо
   embeddings = embedder.embed_documents(texts)  # Может OOM на большом списке
   
   # Используйте батчи
   batch_size = 8
   for i in range(0, len(texts), batch_size):
       batch = texts[i:i + batch_size]
       embeddings = embedder.embed_documents(batch)
   ```

### Проблема: Dimension mismatch error

**Ошибка:**
```
sqlite3.OperationalError: dimension mismatch: expected 768, got 1024
```

**Причина:** БД создана с 768D (Gemini), но embedder генерирует 1024D (Qwen3).

**Решение:** См. раздел "Миграция с Gemini на Local" выше.

### Проблема: Медленная первая загрузка

**Симптом:** Первый `embed_query()` занимает 30-60 секунд.

**Причина:** MLX скачивает модель из HuggingFace (~600 MB для Qwen3).

**Решения:**

1. **Предзагрузка модели:**
   ```python
   # В начале приложения
   embedder = core.embedder
   embedder._ensure_loaded()  # Загружает модель сразу
   ```

2. **Кэш моделей:**
   Модели кэшируются в `~/.cache/huggingface/hub/`. Вторая загрузка будет мгновенной.

3. **Ручная загрузка:**
   ```bash
   # Через huggingface-cli
   pip install huggingface-hub
   huggingface-cli download mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ
   ```

### Проблема: Качество поиска хуже чем у Gemini

**Возможные причины:**

1. **Модель не подходит для задачи:**
   - `all-minilm` — базовая модель, может уступать Gemini
   - Решение: Используйте `qwen3-embedding`

2. **MRL truncation без ре-нормализации:**
   ```python
   # ❌ НЕПРАВИЛЬНО
   truncated = full_vec[:768]
   
   # ✅ ПРАВИЛЬНО
   truncated = full_vec[:768]
   normalized = truncated / norm(truncated)
   ```

3. **Asymmetric search без префиксов:**
   - LocalEmbedder не использует query/document префиксы
   - Может влиять на качество на 2-5%
   - Для критичных задач используйте Gemini

---

## 🚀 Advanced: MRL Truncation для экономии RAM

Если у вас **MacBook Air 8GB** и Qwen3 **едва влезает** в память — можно использовать MRL для уменьшения dimension.

### Подход 1: Truncation при поиске

```python
from semantic_core import SemanticCore
import numpy as np
from numpy.linalg import norm

core = SemanticCore()

# Оригинальный embedder (1024D)
original_embedder = core.embedder

# Обёртка с truncation
class TruncatedEmbedder:
    def __init__(self, base_embedder, target_dim=768):
        self.base = base_embedder
        self.target_dim = target_dim
    
    def embed_query(self, text: str) -> np.ndarray:
        full_vec = self.base.embed_query(text)
        truncated = full_vec[:self.target_dim]
        return truncated / norm(truncated)
    
    def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        full_vecs = self.base.embed_documents(texts)
        return [vec[:self.target_dim] / norm(vec[:self.target_dim]) for vec in full_vecs]
    
    @property
    def dimension(self) -> int:
        return self.target_dim

# Используйте truncated embedder
embedder = TruncatedEmbedder(original_embedder, target_dim=512)
core.embedder = embedder

# Теперь все векторы будут 512D (экономия RAM ~50%)
vector = embedder.embed_query("test")
print(vector.shape)  # (512,)
```

**Метрики экономии:**

| Dimension | RAM использование | Потеря качества |
|-----------|-------------------|-----------------|
| 1024 (full) | ~4 GB | 0% |
| 768 | ~3 GB (25% экономия) | <1.5% |
| 512 | ~2 GB (50% экономия) | ~2-3% |
| 256 | ~1 GB (75% экономия) | ~3-5% |

---

## 🔧 Python API Reference

### Создание embedder

```python
from semantic_core.infrastructure.local.embeddings import LocalEmbedder

# Через preset
embedder = LocalEmbedder(model="qwen3-embedding", device="mps")

# Автодетект device
embedder = LocalEmbedder(model="bge-small")  # device=None → auto

# CPU fallback
embedder = LocalEmbedder(model="all-minilm", device="cpu")
```

### Основные методы

```python
# Единичный query
vector = embedder.embed_query("What is machine learning?")
# → np.ndarray, shape (1024,) для qwen3-embedding

# Список документов
vectors = embedder.embed_documents([
    "Document 1 text",
    "Document 2 text",
    "Document 3 text"
])
# → list[np.ndarray], каждый shape (1024,)

# Dimension
print(embedder.dimension)  # 1024
```

### Properties

```python
# Модель загружена?
print(embedder._model is not None)  # False до первого вызова

# Config
print(embedder._config)
# ModelConfig(
#     name='mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ',
#     dimension=1024,
#     max_tokens=8192,
#     backend='mlx-lm',
#     needs_query_prefix=False
# )

# Device
print(embedder._device)  # "mps" или "cpu"
```

---

## 🎓 Best Practices

### 1. Lazy Loading — используйте его

```python
# ✅ ХОРОШО
embedder = LocalEmbedder("qwen3-embedding")
# Модель НЕ загружена

if user_needs_search:
    vector = embedder.embed_query(query)  # Загружается здесь

# ❌ ПЛОХО
embedder = LocalEmbedder("qwen3-embedding")
embedder._ensure_loaded()  # Загружаем сразу (ненужно!)
```

### 2. Переиспользуйте embedder

```python
# ✅ ХОРОШО
embedder = LocalEmbedder("qwen3-embedding")

for doc in documents:
    vector = embedder.embed_query(doc)  # Модель загружена 1 раз

# ❌ ПЛОХО
for doc in documents:
    embedder = LocalEmbedder("qwen3-embedding")  # Создаётся каждый раз!
    vector = embedder.embed_query(doc)
```

### 3. Batch processing для больших объёмов

```python
# ✅ ХОРОШО
texts = [...]  # 1000 документов
batch_size = 32

for i in range(0, len(texts), batch_size):
    batch = texts[i:i + batch_size]
    vectors = embedder.embed_documents(batch)

# ❌ ПЛОХО (медленно)
for text in texts:
    vector = embedder.embed_query(text)
```

### 4. Кэшируйте результаты

```python
import joblib

# Сохраните embeddings на диск
cache = {text: embedder.embed_query(text) for text in texts}
joblib.dump(cache, "embeddings_cache.pkl")

# Загрузите при следующем запуске
cache = joblib.load("embeddings_cache.pkl")
```

---

## 📊 Benchmarks

### Скорость (MacBook Pro M2 Pro, 16GB)

| Модель | Latency (single) | Throughput (batch=32) |
|--------|------------------|----------------------|
| all-minilm | 8ms | ~180 docs/sec |
| bge-small | 10ms | ~150 docs/sec |
| qwen3-embedding | 25ms | ~50 docs/sec |
| Gemini (cloud) | 200-500ms | ~10 docs/sec (rate limited) |

### RAM использование (idle + модель)

| Модель | RAM после загрузки |
|--------|--------------------|
| all-minilm | +2.1 GB |
| bge-small | +2.3 GB |
| qwen3-embedding | +4.2 GB |

### Качество (MTEB Russian subset)

| Модель | Retrieval | STS | Classification |
|--------|-----------|-----|----------------|
| all-minilm | 62.3 | 68.1 | 70.5 |
| bge-small | 67.8 | 72.4 | 74.2 |
| qwen3-embedding | **75.6** | **79.2** | **81.3** |
| Gemini embedding-001 | 77.1 | 80.5 | 82.7 |

---

## 🔗 Дополнительно

- [13_local_embeddings.md](../../concepts/13_local_embeddings.md) — концепции и теория
- [local-models.md](../../reference/local-models.md) — справочник моделей
- [custom-embedder.md](../extending/custom-embedder.md) — Windows/Linux альтернатива
- [MLX Framework Docs](https://ml-explore.github.io/mlx/build/html/index.html) — официальная документация MLX
