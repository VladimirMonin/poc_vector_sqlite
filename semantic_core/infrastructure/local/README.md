# 🔌 Local Embeddings: Два провайдера

Phase 15.2 предоставляет **два** локальных embedder провайдера:

---

## 📊 Сравнение провайдеров

| Критерий | LocalEmbedder (MLX) | SentenceTransformerEmbedder |
|----------|---------------------|---------------------------|
| **Платформа** | Apple Silicon only (M1/M2/M3) | Любая (Linux/Windows/macOS) |
| **Backend** | MLX (Apple ML framework) | PyTorch/sentence-transformers |
| **Установка** | `pip install .[local-embeddings-mlx]` | `pip install .[local-embeddings]` |
| **Размер зависимостей** | ~500 MB (MLX) | ~2 GB (PyTorch) |
| **GPU Support** | Автоматически (Apple Neural Engine) | CUDA/ROCm/MPS |
| **Скорость на M-чипах** | 🚀🚀🚀 Очень быстро | 🚀🚀 Быстро |
| **Модели** | all-MiniLM, Qwen3-Embedding, bge-small | Любые sentence-transformers |

---

## 🎯 Когда использовать

### LocalEmbedder (MLX)

**Используй если:**
- ✅ У тебя Apple Silicon (M1/M2/M3)
- ✅ Нужна максимальная скорость на Mac
- ✅ Хочешь минимум зависимостей
- ✅ Работаешь с русским/китайским (Qwen3-Embedding)

**Не используй если:**
- ❌ Linux или Windows
- ❌ Intel Mac

### SentenceTransformerEmbedder

**Используй если:**
- ✅ Кросс-платформенность важна
- ✅ Есть NVIDIA GPU (CUDA)
- ✅ Нужен широкий выбор моделей (HuggingFace)
- ✅ Intel Mac / Linux / Windows

---

## 🚀 Быстрый старт

### LocalEmbedder (MLX)

```python
from semantic_core.infrastructure.local import LocalEmbedder

# Только для Apple Silicon
embedder = LocalEmbedder("qwen3-embedding")  # 1024 dim, 8192 tokens

vector = embedder.embed_query("Hello world")
print(vector.shape)  # (1024,)
```

**Установка:**
```bash
# Только на macOS с Apple Silicon
pip install semantic-core[local-embeddings-mlx]
```

### SentenceTransformerEmbedder

```python
from semantic_core.infrastructure.local import SentenceTransformerEmbedder

# Работает везде
embedder = SentenceTransformerEmbedder(
    "paraphrase-multilingual-mpnet-base-v2",
    device="cuda"  # или "cpu" или "mps"
)

vector = embedder.embed_query("Привет мир")
print(vector.shape)  # (768,)
```

**Установка:**
```bash
# Любая платформа
pip install semantic-core[local-embeddings]
```

---

## 🔌 Использование с SemanticCore

Оба embedder взаимозаменяемы:

```python
from semantic_core import SemanticCore
from semantic_core.infrastructure.local import (
    LocalEmbedder,          # MLX
    SentenceTransformerEmbedder  # PyTorch
)

# Вариант 1: MLX (Apple Silicon)
embedder = LocalEmbedder("qwen3-embedding")

# Вариант 2: Sentence Transformers (универсальный)
embedder = SentenceTransformerEmbedder("all-mpnet-base-v2", device="cuda")

# Инициализация SemanticCore
core = SemanticCore(
    db_path="my_data.db",
    embedder=embedder,  # Любой из двух
)
```

---

## 📋 Доступные модели

### LocalEmbedder (MLX)

| Модель | Dimension | Max Tokens | Размер |
|--------|-----------|------------|--------|
| `all-minilm` | 384 | 512 | 150 MB |
| `qwen3-embedding` | 1024 | 8192 | 335 MB |
| `bge-small` | 384 | 512 | 19 MB |

### SentenceTransformerEmbedder

| Модель | Dimension | Max Tokens | Качество |
|--------|-----------|------------|----------|
| `all-MiniLM-L6-v2` | 384 | 256 | ⭐⭐⭐ |
| `all-mpnet-base-v2` | 768 | 384 | ⭐⭐⭐⭐ |
| `paraphrase-multilingual-mpnet-base-v2` | 768 | 128 | ⭐⭐⭐⭐ |
| `sentence-transformers/LaBSE` | 768 | 256 | ⭐⭐⭐⭐⭐ |

Плюс любые другие с https://huggingface.co/models?library=sentence-transformers

---

## 🧪 Тестирование

```bash
# LocalEmbedder (MLX) - unit тесты
pytest tests/unit/infrastructure/local/test_local_embedder.py -v

# SentenceTransformerEmbedder - unit тесты  
pytest tests/unit/infrastructure/local/test_sentence_transformer_embedder.py -v

# Интеграционные тесты (с реальными моделями)
pytest tests/integration/local/ -v -m integration
```

---

## 💡 Рекомендации

**Для production на Apple Silicon:**
```python
LocalEmbedder("qwen3-embedding")  # Лучшее качество + длинный контекст
```

**Для production кросс-платформа:**
```python
SentenceTransformerEmbedder(
    "paraphrase-multilingual-mpnet-base-v2",
    device="cuda"  # если есть GPU
)
```

**Для быстрого POC:**
```python
# MLX (если Mac M1/M2/M3)
LocalEmbedder("all-minilm")

# Или универсальный
SentenceTransformerEmbedder("all-MiniLM-L6-v2")
```

---

## 🔗 Ссылки

- **MLX Embeddings README:** `embeddings/README.md`
- **SentenceTransformers Docs:** https://www.sbert.net/
- **Phase 15.2 Plan:** `doc/ideas/phase_15/phase_15.2_local_embeddings.md`
- **BaseEmbedder Interface:** `semantic_core/interfaces/embedder.py`
