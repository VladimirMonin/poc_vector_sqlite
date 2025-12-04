---
title: "Custom Vector Store"
description: "Как добавить ChromaDB, Qdrant, Pinecone"
tags: ["extending", "vector-store", "chromadb", "qdrant", "pinecone"]
difficulty: "advanced"
prerequisites: ["../../concepts/10_plugin_system", "../../concepts/02_vector_search"]
---

# Custom Vector Store 💾

> Замените SQLite на ChromaDB, Qdrant или другой vector DB.

---

## Интерфейс BaseVectorStore 📋

```
┌─────────────────────────────────────────────┐
│          BaseVectorStore (ABC)              │
├─────────────────────────────────────────────┤
│ save(doc, chunks) -> Document               │
│ search(vector, text, filters, limit, mode)  │
│   -> list[SearchResult]                     │
│ search_chunks(...) -> list[ChunkResult]     │
│ delete(document_id) -> int                  │
│ delete_by_metadata(filters) -> int          │
│ bulk_update_vectors(dict) -> int            │
└─────────────────────────────────────────────┘
```

---

## Методы для реализации 📊

| Метод | Назначение | Сложность |
|-------|------------|-----------|
| `save` | Сохранить документ + чанки | Средняя |
| `search` | Поиск документов | Высокая |
| `search_chunks` | Поиск чанков | Высокая |
| `delete` | Удалить по doc_id | Простая |
| `delete_by_metadata` | Удалить по фильтрам | Средняя |
| `bulk_update_vectors` | Batch update | Средняя |

---

## Пример: ChromaDB 🎨

```python
import chromadb
from semantic_core.interfaces import BaseVectorStore
from semantic_core.domain import Document, Chunk, SearchResult

class ChromaDBStore(BaseVectorStore):
    def __init__(self, path: str = "./chroma_db"):
        self.client = chromadb.PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection(
            name="semantic_chunks",
            metadata={"hnsw:space": "cosine"},
        )
        self._doc_id_counter = 0
    
    def save(self, document: Document, chunks: list[Chunk]) -> Document:
        doc_id = self._next_doc_id()
        document.id = doc_id
        
        ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
        embeddings = [c.embedding.tolist() for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [{"doc_id": doc_id, **document.metadata} for _ in chunks]
        
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        return document
    
    def search(self, query_vector=None, limit=10, **kwargs) -> list[SearchResult]:
        results = self.collection.query(
            query_embeddings=[query_vector.tolist()],
            n_results=limit,
        )
        # Конвертируем в SearchResult...
        return self._to_search_results(results)
    
    # ... остальные методы
```

---

## Пример: Qdrant ⚡

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from semantic_core.interfaces import BaseVectorStore

class QdrantStore(BaseVectorStore):
    def __init__(self, url: str = "localhost", port: int = 6333):
        self.client = QdrantClient(url, port=port)
        self.collection = "semantic_chunks"
        self._ensure_collection()
    
    def _ensure_collection(self, dim: int = 768):
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(
                    size=dim,
                    distance=Distance.COSINE,
                ),
            )
    
    def save(self, document: Document, chunks: list[Chunk]) -> Document:
        points = [
            PointStruct(
                id=i,
                vector=chunk.embedding.tolist(),
                payload={"text": chunk.text, "doc_id": document.id},
            )
            for i, chunk in enumerate(chunks)
        ]
        self.client.upsert(
            collection_name=self.collection,
            points=points,
        )
        return document
    
    def search(self, query_vector=None, limit=10, **kwargs):
        results = self.client.search(
            collection_name=self.collection,
            query_vector=query_vector.tolist(),
            limit=limit,
        )
        return self._to_search_results(results)
```

---

## FTS fallback ⚠️

ChromaDB/Qdrant не имеют полноценного FTS.

Варианты:

1. **Игнорировать FTS** — только vector search
2. **Внешний FTS** — Elasticsearch, Meilisearch
3. **Hybrid на стороне DB** — если поддерживает

```python
def search(self, query_vector=None, query_text=None, mode="hybrid", **kwargs):
    if mode == "fts":
        raise NotImplementedError("FTS not supported, use vector mode")
    
    if mode == "hybrid":
        # Только vector, FTS недоступен
        mode = "vector"
    
    # Vector search...
```

---

## Metadata Filtering 📋

| DB | Синтаксис фильтра |
|----|-------------------|
| ChromaDB | `where={"field": "value"}` |
| Qdrant | `Filter(must=[...])` |
| Pinecone | `filter={"field": {"$eq": "value"}}` |

```python
# ChromaDB
results = collection.query(
    query_embeddings=[vector],
    where={"source_id": 42},
)

# Qdrant
from qdrant_client.models import Filter, FieldCondition, MatchValue
results = client.search(
    query_vector=vector,
    query_filter=Filter(
        must=[FieldCondition(key="source_id", match=MatchValue(value=42))]
    ),
)
```

---

## Регистрация в SemanticCore ⚙️

```python
from semantic_core import SemanticCore

store = ChromaDBStore(path="./my_chroma")

core = SemanticCore(
    embedder=embedder,
    store=store,  # Ваш store
    splitter=splitter,
    context_strategy=context,
)
```

---

## Частые ошибки ⚠️

| Ошибка | Причина | Решение |
|--------|---------|---------|
| FTS не работает | DB не поддерживает | Используйте vector mode |
| Медленный bulk | Нет batch API | Используйте upsert |
| ID конфликты | Неуникальные ID | Добавьте doc_id prefix |

---

## Следующие шаги 🔗

| Гайд | Что узнаете |
|------|-------------|
| [MCP Server](mcp-server.md) | SemanticCore как MCP сервер |
| [Vector Search](../../concepts/02_vector_search.md) | Теория векторного поиска |
