---
title: "Custom Embedder"
description: "Как добавить OpenAI, Cohere, sentence-transformers"
tags: ["extending", "embedder", "openai", "cohere", "sentence-transformers", "mrl"]
difficulty: "intermediate"
prerequisites: ["../../concepts/10_plugin_system", "../../concepts/01_embeddings"]
---

# Custom Embedder 🧠

> Добавьте свой генератор эмбеддингов.

---

## Интерфейс BaseEmbedder 📋

```
┌─────────────────────────────────────────────┐
│            BaseEmbedder (ABC)               │
├─────────────────────────────────────────────┤
│ @abstractmethod                             │
│ embed_documents(texts: list[str])           │
│   -> list[np.ndarray]                       │
│                                             │
│ @abstractmethod                             │
│ embed_query(text: str)                      │
│   -> np.ndarray                             │
└─────────────────────────────────────────────┘
```

**Важно**: `embed_documents` для индексации, `embed_query` для поиска.
Некоторые модели используют разные task_type для каждого.

---

## Актуальные модели 📊

| Провайдер | Модель | Размерности |
|-----------|--------|-------------|
| Google | gemini-embedding-001 | 768/1536/3072 (MRL) |
| OpenAI | text-embedding-3-large | 256-3072 (MRL) |
| OpenAI | text-embedding-3-small | 512-1536 |
| Cohere | embed-v4 | 1024 |
| Local | all-MiniLM-L6-v2 | 384 |

---

## Пример: OpenAI 🟢

```python
import numpy as np
from openai import OpenAI
from semantic_core.interfaces import BaseEmbedder

class OpenAIEmbedder(BaseEmbedder):
    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-large",
        dimensions: int = 1536,
    ):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.dimensions = dimensions
    
    def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self.dimensions,
        )
        return [
            np.array(item.embedding, dtype=np.float32)
            for item in response.data
        ]
    
    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_documents([text])[0]
```

---

## Пример: Cohere 🔵

```python
import cohere
import numpy as np
from semantic_core.interfaces import BaseEmbedder

class CohereEmbedder(BaseEmbedder):
    def __init__(self, api_key: str, model: str = "embed-v4"):
        self.client = cohere.Client(api_key)
        self.model = model
    
    def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        response = self.client.embed(
            texts=texts,
            model=self.model,
            input_type="search_document",  # Для индексации
        )
        return [np.array(e, dtype=np.float32) for e in response.embeddings]
    
    def embed_query(self, text: str) -> np.ndarray:
        response = self.client.embed(
            texts=[text],
            model=self.model,
            input_type="search_query",  # Для поиска
        )
        return np.array(response.embeddings[0], dtype=np.float32)
```

---

## Пример: sentence-transformers (локальный) 🏠

```python
import numpy as np
from sentence_transformers import SentenceTransformer
from semantic_core.interfaces import BaseEmbedder

class LocalEmbedder(BaseEmbedder):
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
    
    def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return [e.astype(np.float32) for e in embeddings]
    
    def embed_query(self, text: str) -> np.ndarray:
        return self.model.encode(text, convert_to_numpy=True).astype(np.float32)
```

---

## Регистрация в SemanticCore ⚙️

```python
from semantic_core import SemanticCore

embedder = OpenAIEmbedder(api_key="sk-...", dimensions=1536)

core = SemanticCore(
    embedder=embedder,
    store=store,
    splitter=splitter,
    context_strategy=context,
)
```

---

## Windows/Linux: Qwen3 через sentence-transformers 🪟🐧

**Проблема:** LocalEmbedder использует MLX Framework (macOS only).

**Решение:** Используйте sentence-transformers с PyTorch на Windows/Linux.

```python
import numpy as np
from sentence_transformers import SentenceTransformer
from semantic_core.interfaces import BaseEmbedder

class Qwen3Embedder(BaseEmbedder):
    """Qwen3-Embedding для Windows/Linux (PyTorch backend)."""
    
    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-Embedding-0.6B",
        device: str = "cuda",  # "cuda" для GPU, "cpu" для CPU
        target_dimension: int = 1024,  # Или 768, 512 для MRL
    ):
        """
        Args:
            model_name: HuggingFace model ID
            device: "cuda", "cpu", или "cuda:0" для конкретной GPU
            target_dimension: Целевая размерность (MRL truncation)
        """
        self.model = SentenceTransformer(model_name, device=device)
        self.target_dimension = target_dimension
        
        # Оригинальная размерность модели
        self._native_dimension = self.model.get_sentence_embedding_dimension()
    
    def _truncate_mrl(self, vector: np.ndarray) -> np.ndarray:
        """MRL truncation с ре-нормализацией."""
        if self.target_dimension >= self._native_dimension:
            return vector
        
        # Усечение
        truncated = vector[:self.target_dimension]
        
        # КРИТИЧНО: Ре-нормализация для косинусного расстояния
        norm = np.linalg.norm(truncated)
        return truncated / norm if norm > 0 else truncated
    
    def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        """Embeddings для индексации документов."""
        # Qwen3 поддерживает prompt_name для asymmetric search
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            prompt_name="document",  # Для документов
            show_progress_bar=False,
        )
        
        # MRL truncation если нужно
        if self.target_dimension < self._native_dimension:
            embeddings = [self._truncate_mrl(e) for e in embeddings]
        
        return [e.astype(np.float32) for e in embeddings]
    
    def embed_query(self, text: str) -> np.ndarray:
        """Embedding для поискового запроса."""
        # Asymmetric search: prompt_name="query"
        embedding = self.model.encode(
            text,
            convert_to_numpy=True,
            prompt_name="query",  # Для запросов
            show_progress_bar=False,
        )
        
        # MRL truncation если нужно
        if self.target_dimension < self._native_dimension:
            embedding = self._truncate_mrl(embedding)
        
        return embedding.astype(np.float32)
    
    @property
    def dimension(self) -> int:
        return self.target_dimension

# Использование
embedder = Qwen3Embedder(device="cuda", target_dimension=1024)

# Или с MRL truncation для экономии RAM
embedder = Qwen3Embedder(device="cuda", target_dimension=768)

from semantic_core import SemanticCore
core = SemanticCore(embedder=embedder)
```

**Преимущества:**
- ✅ Работает на Windows/Linux
- ✅ GPU acceleration через CUDA
- ✅ Asymmetric search (prompt_name="query")
- ✅ MRL truncation встроен

**Установка:**
```bash
pip install sentence-transformers torch
# Для GPU (CUDA)
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

---

## Важно: Размерность ⚠️

**Все документы в одной БД должны иметь одинаковую размерность!**

```
❌ НЕЛЬЗЯ:
  - Document 1: OpenAI 1536 dims
  - Document 2: Gemini 768 dims
  
✅ ПРАВИЛЬНО:
  - Все документы: 1536 dims (одна модель)
```

При смене модели — переиндексируйте всё.

**MRL Truncation:**
Если используете MRL (Qwen3, OpenAI text-embedding-3), можете усекать векторы:
- 1024D → 768D: потеря <1.5%
- 768D → 512D: потеря ~2-3%

Но **ре-нормализация обязательна** (см. код выше)!

---

## Нормализация 📐

sqlite-vec использует косинусное расстояние.
Большинство моделей возвращают нормализованные векторы.

Если нет — нормализуйте:

```python
def normalize(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v)
    return v / norm if norm > 0 else v
```

---

## Частые ошибки ⚠️

| Ошибка | Причина | Решение |
|--------|---------|---------|
| Dimension mismatch | Разные модели в БД | Переиндексируйте |
| Плохое качество поиска | Не тот task_type | Разделите doc/query |
| OOM на больших batch | Много текстов | Разбейте на chunks |

---

## Следующие шаги 🔗

| Гайд | Что узнаете |
|------|-------------|
| [Custom VectorStore](custom-vector-store.md) | Свой storage backend |
| [Embeddings Concept](../../concepts/01_embeddings.md) | Теория эмбеддингов |
