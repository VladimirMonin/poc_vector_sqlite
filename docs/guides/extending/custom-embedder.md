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
