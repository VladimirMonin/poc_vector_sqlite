# 🧮 Local Embeddings via MLX

Production-ready локальные embeddings для Apple Silicon без внешних API.

---

## 🎯 Возможности

- **Zero API Costs:** Полностью локальная работа без API ключей
- **Apple Silicon Optimized:** MLX оптимизация для M1/M2/M3
- **Multilingual:** Поддержка 100+ языков (включая RU/EN/ZH)
- **Plug-and-Play:** Полная совместимость с `BaseEmbedder`
- **Lazy Loading:** Модели загружаются только при использовании

---

## 📦 Установка

```bash
# Базовая установка (только для Apple Silicon)
pip install semantic-core[local-embeddings]

# Проверка установки
python -c "import mlx; import mlx_embeddings; print('✅ MLX ready')"
```

**Требования:**

- macOS с Apple Silicon (M1/M2/M3)
- Python >=3.13
- ~500MB свободного места для моделей

---

## 🚀 Быстрый старт

```python
from semantic_core.infrastructure.local.embeddings import LocalEmbedder

# Инициализация (модель загрузится при первом использовании)
embedder = LocalEmbedder("all-minilm")  # 384 dim, 512 tokens

# Генерация embedding
vector = embedder.embed_query("Hello world")
print(vector.shape)  # (384,)

# Батчевая обработка
vectors = embedder.embed_documents([
    "First document",
    "Second document",
    "Third document"
])
```

---

## 🎛️ Доступные модели

| Модель | Размерность | Max Tokens | Размер | Языки | Backend |
|--------|-------------|------------|--------|-------|---------|
| `all-minilm` | 384 | 512 | ~150 MB | 50+ | mlx-embeddings |
| `qwen3-embedding` | 1024 | 8192 | ~335 MB | 100+ | mlx-lm |
| `bge-small` | 384 | 512 | ~19 MB | EN only | mlx-embeddings |

### Рекомендации

**Для быстрого POC:**

```python
embedder = LocalEmbedder("all-minilm")  # Легковесная, универсальная
```

**Для production с длинными документами:**

```python
embedder = LocalEmbedder("qwen3-embedding")  # Высокая размерность, длинный контекст
```

**Для английских текстов:**

```python
embedder = LocalEmbedder("bge-small")  # Самая маленькая модель
```

---

## 🔌 Интеграция с SemanticCore

### Использование с SemanticCore

```python
from semantic_core import SemanticCore
from semantic_core.infrastructure.local.embeddings import LocalEmbedder

# Создание локального embedder
embedder = LocalEmbedder("qwen3-embedding")

# Инициализация SemanticCore с локальными embeddings
core = SemanticCore(
    db_path="my_data.db",
    embedder=embedder,  # Замена Gemini на локальный
)

# Дальнейшая работа как обычно
core.ingest_document("path/to/document.md")
results = core.search("my query")
```

### Автоподстройка SmartSplitter

`SmartSplitter` автоматически адаптируется под `max_tokens` модели:

```python
from semantic_core.processing.splitters import SmartSplitter
from semantic_core.infrastructure.local.embeddings import LocalEmbedder

embedder = LocalEmbedder("qwen3-embedding")  # max_tokens=8192

splitter = SmartSplitter(
    parser=my_parser,
    embedder=embedder  # Автоматически chunk_size ~7000
)
```

---

## 🧪 Тестирование

### Unit-тесты (с mock)

```bash
pytest tests/unit/infrastructure/local/test_local_embedder.py -v
```

### Интеграционные тесты (с реальными моделями)

```bash
# Требует установленные MLX зависимости и Apple Silicon
pytest tests/integration/local/test_local_embedder_integration.py -v -m integration

# Только быстрые тесты (без Qwen3)
pytest tests/integration/local/test_local_embedder_integration.py -v -m "integration and not slow"
```

---

## 📊 Производительность

### Сравнение моделей (Apple M2)

| Модель | Загрузка | Embedding (1 текст) | RAM |
|--------|----------|---------------------|-----|
| all-minilm | ~0.5s | ~50ms | ~450 MB |
| qwen3-embedding | ~1.1s | ~80ms | ~642 MB |
| bge-small | ~0.5s | ~45ms | ~400 MB |

### Gemini vs Local

| Критерий | Gemini Embedding | LocalEmbedder |
|----------|------------------|---------------|
| Стоимость | $0.025 / 1M tokens | Бесплатно ✅ |
| Latency | 200-500ms (API) | 50-100ms (local) ✅ |
| Offline | ❌ Нет | ✅ Да |
| Max Tokens | 2048 | 8192 (Qwen3) ✅ |
| Размерность | 768 | 384-1024 |

---

## ⚙️ Конфигурация

### Кастомные модели

Если нужна другая MLX модель:

```python
# 1. Добавьте конфигурацию в models.py
from semantic_core.infrastructure.local.embeddings.models import MODELS, ModelConfig

MODELS["my-custom-model"] = ModelConfig(
    name="mlx-community/my-custom-model",
    dimension=512,
    max_tokens=1024,
    backend="mlx-embeddings",
    needs_query_prefix=False,
)

# 2. Используйте как обычно
embedder = LocalEmbedder("my-custom-model")
```

### Свойства модели

```python
embedder = LocalEmbedder("qwen3-embedding")

print(embedder.dimension)    # 1024
print(embedder.max_tokens)   # 8192

# Доступ к конфигурации
print(embedder._config.name)      # mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ
print(embedder._config.backend)   # mlx-lm
```

---

## 🔧 Устранение неполадок

### ImportError: No module named 'mlx'

```bash
# Проверьте платформу
python -c "import platform; print(platform.machine())"
# Должно быть: arm64

# Установите MLX
pip install mlx mlx-embeddings mlx-lm
```

### ModuleNotFoundError: No module named 'mlx_embeddings'

```bash
# Переустановите с правильными extras
pip install -e ".[local-embeddings]"
```

### RuntimeError: Failed to load model

```bash
# Очистите кеш HuggingFace
rm -rf ~/.cache/huggingface/

# Попробуйте снова
python -c "from semantic_core.infrastructure.local.embeddings import LocalEmbedder; LocalEmbedder('all-minilm').embed_query('test')"
```

---

## 📚 Примеры

### Семантическая близость

```python
from semantic_core.infrastructure.local.embeddings import LocalEmbedder
import numpy as np

embedder = LocalEmbedder("all-minilm")

# Генерация embeddings
vec1 = embedder.embed_query("cat")
vec2 = embedder.embed_query("kitten")
vec3 = embedder.embed_query("database")

# Косинусная близость
def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

print(cosine_similarity(vec1, vec2))  # ~0.7 (высокая близость)
print(cosine_similarity(vec1, vec3))  # ~0.1 (низкая близость)
```

### Мультиязычный поиск

```python
embedder = LocalEmbedder("qwen3-embedding")  # Лучшая мультиязычность

# Запрос на русском
query_vec = embedder.embed_query("кошка")

# Документы на разных языках
docs_vecs = embedder.embed_documents([
    "cat",           # EN
    "кот",           # RU
    "猫",            # ZH
    "database",      # Не связано
])

# Поиск ближайших
from numpy.linalg import norm
similarities = [
    np.dot(query_vec, doc_vec) / (norm(query_vec) * norm(doc_vec))
    for doc_vec in docs_vecs
]

print(similarities)  # RU/ZH будут иметь высокую близость
```

---

## 🔗 Связанные документы

- **API Reference:** `semantic_core/interfaces/embedder.py` (BaseEmbedder)
- **Donorский код:** `examples/poc_apple_local_llm/src/lightweight_core.py`
- **Исследование моделей:** `examples/poc_apple_local_llm/EMBEDDINGS_MODELS_INVESTIGATION.md`
- **Phase 15.0:** BaseEmbedder расширение (dimension/max_tokens)
- **Phase 15.2 Plan:** `doc/ideas/phase_15/phase_15.2.md`

---

## ⚠️ Ограничения

1. **Только Apple Silicon:** MLX работает только на M1/M2/M3
2. **Размер моделей:** Требуется ~500MB для всех моделей
3. **Нет GPU fallback:** Если MLX недоступен, используйте GeminiEmbedder
4. **Качество:** Локальные модели могут уступать cloud API на сложных задачах

---

## 🛣️ Roadmap

- [ ] Поддержка sentence-transformers как fallback для non-Apple platforms
- [ ] Автоматический выбор модели по языку документа
- [ ] Кеширование embeddings на диске
- [ ] Batch optimization для больших корпусов
