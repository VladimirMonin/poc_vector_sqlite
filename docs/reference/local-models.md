# Local Models Reference

> Complete reference for LocalEmbedder models, configuration, and API

**Last Updated:** December 2025  
**Provider:** Local (MLX Framework)

---

## 📋 Models Comparison

### Quick Reference Table

| Model ID | Full Name | Dimension | Max Tokens | Backend | RAM | Speed | Quality | Languages |
|----------|-----------|-----------|------------|---------|-----|-------|---------|-----------|
| `all-minilm` | all-MiniLM-L6-v2 | 384 | 512 | mlx-embeddings | 2 GB | ⚡⚡⚡ | 🟡 | EN |
| `bge-small` | bge-small-en-v1.5 | 384 | 512 | mlx-embeddings | 2 GB | ⚡⚡⚡ | 🟢 | EN |
| `qwen3-embedding` | Qwen3-Embedding-0.6B | 1024 | 8192 | mlx-lm | 4 GB | ⚡⚡ | 🟢🟢 | Multi |

### Detailed Specifications

#### all-minilm

```python
ModelConfig(
    name="sentence-transformers/all-MiniLM-L6-v2",
    dimension=384,
    max_tokens=512,
    backend="mlx-embeddings",
    needs_query_prefix=False
)
```

**HuggingFace:** [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)

**Characteristics:**
- **Architecture:** BERT-based (encoder-only)
- **Parameters:** ~80M
- **Training:** Trained on 1B+ sentence pairs
- **Strengths:** Fast, lightweight, good for prototyping
- **Weaknesses:** English-only, basic semantic understanding
- **Use Case:** Quick prototypes, resource-constrained environments

**Benchmarks (MTEB):**
- Retrieval: 61.2
- STS: 68.9
- Classification: 69.5

#### bge-small

```python
ModelConfig(
    name="BAAI/bge-small-en-v1.5",
    dimension=384,
    max_tokens=512,
    backend="mlx-embeddings",
    needs_query_prefix=False
)
```

**HuggingFace:** [BAAI/bge-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5)

**Characteristics:**
- **Architecture:** BERT-based (encoder-only)
- **Parameters:** ~33M
- **Training:** Trained on C-MTEB and English corpus
- **Strengths:** Better quality than all-minilm, still fast
- **Weaknesses:** English-only
- **Use Case:** Production English RAG systems

**Benchmarks (MTEB):**
- Retrieval: 67.3
- STS: 72.8
- Classification: 73.9

#### qwen3-embedding

```python
ModelConfig(
    name="mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ",
    dimension=1024,
    max_tokens=8192,
    backend="mlx-lm",
    needs_query_prefix=False
)
```

**HuggingFace:** [mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ](https://huggingface.co/mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ)

**Original Model:** [Qwen/Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)

**Characteristics:**
- **Architecture:** Decoder-only LLM (GPT-like)
- **Parameters:** ~600M (4-bit quantized)
- **Training:** Pretrained on multilingual corpus, fine-tuned for embeddings
- **Strengths:** 
  - Highest quality among local models
  - Multilingual (EN, ZH, RU, JA, KO, etc.)
  - MRL support (32-1024 dimensions)
  - Long context (8192 tokens)
- **Weaknesses:** 
  - Requires more RAM
  - Slower than BERT-based models
  - Needs mlx-lm (low-level access)
- **Use Case:** Production multilingual RAG, quality-critical tasks

**Benchmarks (MTEB):**
- Retrieval: 75.1
- STS: 78.6
- Classification: 80.8

**MRL Dimensions:**
Qwen3 supports Matryoshka truncation:
- 1024D (native, full quality)
- 768D (loss <1.5%)
- 512D (loss ~2-3%)
- 256D (loss ~3-5%)
- 128D, 64D, 32D (not recommended for production)

---

## ⚙️ Configuration Reference

### semantic.toml

```toml
[defaults]
# Provider selection
embedding_provider = "local"  # Use LocalEmbedder

[providers.local]
# Model selection (required)
embedding_model = "qwen3-embedding"  # or "all-minilm", "bge-small"

# Device (optional, auto-detect if omitted)
device = "mps"  # "mps" (Apple Metal) or "cpu"

# Max tokens override (not implemented yet, tracked in phase_17_notes.md)
# max_tokens = 4000
```

### Environment Variables

```bash
# HuggingFace cache directory (default: ~/.cache/huggingface/hub)
export HF_HOME="/path/to/custom/cache"

# Disable HuggingFace telemetry
export HF_HUB_DISABLE_TELEMETRY=1

# MLX memory allocation strategy
export MLX_METAL_MEMORY_LIMIT="8GB"  # Limit Metal memory usage
```

### Python Configuration

```python
from semantic_core.config import SemanticConfig

# From file
config = SemanticConfig(config_file="semantic.toml")

# Programmatic
config = SemanticConfig(
    defaults__embedding_provider="local",
    providers_local__embedding_model="qwen3-embedding",
    providers_local__device="mps"
)

# Via dict
config = SemanticConfig(**{
    "defaults": {"embedding_provider": "local"},
    "providers": {
        "local": {
            "embedding_model": "bge-small",
            "device": "cpu"
        }
    }
})
```

---

## 🔧 API Reference

### LocalEmbedder Class

```python
from semantic_core.infrastructure.local.embeddings import LocalEmbedder
```

#### Constructor

```python
LocalEmbedder(
    model: str = "all-minilm",
    device: Optional[str] = None
)
```

**Parameters:**
- `model` (str): Model preset ID. One of: `"all-minilm"`, `"bge-small"`, `"qwen3-embedding"`
- `device` (Optional[str]): Device to use. `"mps"` (Metal), `"cpu"`, or `None` (auto-detect)

**Raises:**
- `ValueError`: If model not in preset list
- `RuntimeError`: If MLX initialization fails

**Examples:**
```python
# Auto-detect device (recommended)
embedder = LocalEmbedder("qwen3-embedding")

# Explicit device
embedder = LocalEmbedder("bge-small", device="mps")

# CPU fallback
embedder = LocalEmbedder("all-minilm", device="cpu")
```

#### Methods

##### embed_query()

```python
def embed_query(text: str) -> np.ndarray
```

Generate embedding for a single query text.

**Parameters:**
- `text` (str): Query text to embed. Cannot be empty.

**Returns:**
- `np.ndarray`: Embedding vector, shape `(dimension,)`, dtype `float32`

**Raises:**
- `ValueError`: If text is empty
- `RuntimeError`: If model loading fails

**Example:**
```python
vector = embedder.embed_query("What is machine learning?")
print(vector.shape)  # (1024,) for qwen3-embedding
print(vector.dtype)  # float32
```

**Note:** If `needs_query_prefix=True` (currently all False), adds `"query: "` prefix automatically.

##### embed_documents()

```python
def embed_documents(texts: list[str]) -> list[np.ndarray]
```

Generate embeddings for multiple documents.

**Parameters:**
- `texts` (list[str]): List of document texts. Cannot contain empty strings.

**Returns:**
- `list[np.ndarray]`: List of embedding vectors, each shape `(dimension,)`, dtype `float32`

**Raises:**
- `ValueError`: If any text is empty
- `RuntimeError`: If model loading fails

**Example:**
```python
texts = ["Document 1", "Document 2", "Document 3"]
vectors = embedder.embed_documents(texts)

print(len(vectors))         # 3
print(vectors[0].shape)     # (1024,) for qwen3-embedding
```

**Performance:**
- Processes texts in batch (faster than individual embed_query calls)
- For large lists, consider batching manually to avoid OOM

#### Properties

##### dimension

```python
@property
def dimension(self) -> int
```

Embedding vector dimensionality.

**Returns:**
- `int`: 384 (all-minilm, bge-small) or 1024 (qwen3-embedding)

**Example:**
```python
print(embedder.dimension)  # 1024
```

---

## 📦 ModelConfig Structure

```python
from semantic_core.infrastructure.local.embeddings.models import ModelConfig

@dataclass
class ModelConfig:
    """Configuration for a local embedding model."""
    
    name: str
    """Full model name/path on HuggingFace."""
    
    dimension: int
    """Output embedding dimension."""
    
    max_tokens: int
    """Maximum input sequence length in tokens."""
    
    backend: Literal["mlx-embeddings", "mlx-lm"]
    """MLX backend to use."""
    
    needs_query_prefix: bool = False
    """Whether to add 'query:' prefix for queries (asymmetric search)."""
```

### Accessing Model Configs

```python
from semantic_core.infrastructure.local.embeddings.models import MODELS

# Get config
config = MODELS["qwen3-embedding"]

print(config.name)          # mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ
print(config.dimension)     # 1024
print(config.max_tokens)    # 8192
print(config.backend)       # mlx-lm
```

---

## 🎯 Usage Patterns

### Pattern 1: Simple Usage

```python
from semantic_core import SemanticCore

core = SemanticCore()  # Loads config from semantic.toml
vector = core.embedder.embed_query("test")
```

### Pattern 2: Direct Instantiation

```python
from semantic_core.infrastructure.local.embeddings import LocalEmbedder

embedder = LocalEmbedder("qwen3-embedding")
vectors = embedder.embed_documents(["doc1", "doc2"])
```

### Pattern 3: With ComponentFactory

```python
from semantic_core.config import SemanticConfig
from semantic_core.core.factory import ComponentFactory

config = SemanticConfig(
    defaults__embedding_provider="local",
    providers_local__embedding_model="bge-small"
)

embedder = ComponentFactory.create_embedder(config)
```

### Pattern 4: Lazy Loading Control

```python
embedder = LocalEmbedder("qwen3-embedding")

# Model NOT loaded yet
print(embedder._model is None)  # True

# Explicit load
embedder._ensure_loaded()

# Model loaded now
print(embedder._model is not None)  # True

# Subsequent calls are instant
vector = embedder.embed_query("test")
```

### Pattern 5: Batching for Large Datasets

```python
def batch_embed(texts: list[str], batch_size: int = 32):
    """Embed large dataset in batches to avoid OOM."""
    embedder = LocalEmbedder("qwen3-embedding")
    
    all_vectors = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        vectors = embedder.embed_documents(batch)
        all_vectors.extend(vectors)
    
    return all_vectors

# Usage
texts = [...]  # 10,000 documents
vectors = batch_embed(texts, batch_size=32)
```

---

## ⚠️ Known Limitations

### 1. Preset Models Only

**Issue:** Cannot use arbitrary HuggingFace model IDs.

```python
# ❌ Will raise ValueError
embedder = LocalEmbedder("Qwen/Qwen3-Embedding-0.6B")

# ✅ Must use preset
embedder = LocalEmbedder("qwen3-embedding")
```

**Workaround:** Create custom embedder (see [custom-embedder.md](../guides/extending/custom-embedder.md))

### 2. max_tokens_override Not Implemented

**Issue:** `ComponentFactory` passes `max_tokens_override` but `LocalEmbedder` doesn't accept it.

**Location:** `semantic_core/core/factory.py` line 96

**Status:** Tracked in `doc/ideas/phase_17/phase_17_notes.md`

**Workaround:** Currently no override available, uses model default.

### 3. no Query Prefix Support (Yet)

**Issue:** All models have `needs_query_prefix=False`.

Qwen3 in sentence-transformers supports `prompt_name="query"` but MLX implementation doesn't use instruction tokens.

**Impact:** Possible 2-5% quality loss for asymmetric search compared to sentence-transformers implementation.

**Workaround:** For critical tasks, use Gemini or custom embedder with sentence-transformers.

### 4. macOS Only

**Issue:** MLX Framework requires Apple Silicon.

**Platform Support:**
- ✅ macOS 13.3+ (M1/M2/M3/M4/M5)
- ❌ Windows (MLX not supported)
- ❌ Linux (MLX not supported)
- ❌ Intel Mac (MLX not supported)

**Workaround:** Use sentence-transformers with PyTorch on Windows/Linux (see [custom-embedder.md](../guides/extending/custom-embedder.md))

---

## 🧪 Testing & Validation

### Unit Tests

```python
# tests/unit/infrastructure/local/test_local_embedder.py
pytest tests/unit/infrastructure/local/test_local_embedder.py -v
```

### E2E Tests

```python
# tests/integration/e2e/test_qwen3_pipeline.py
pytest tests/integration/e2e/test_qwen3_pipeline.py -v

# Extended tests (requires ~10 min)
pytest tests/integration/e2e/test_qwen3_extended_pipeline.py -v
```

### Manual Validation

```python
from semantic_core.infrastructure.local.embeddings import LocalEmbedder
import numpy as np

embedder = LocalEmbedder("qwen3-embedding")

# Test similarity
v1 = embedder.embed_query("Python programming")
v2 = embedder.embed_query("Python язык программирования")
v3 = embedder.embed_query("Apple fruit")

# Cosine similarity
def cosine_sim(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

print(f"Python EN vs RU: {cosine_sim(v1, v2):.4f}")  # High (~0.85-0.90)
print(f"Python vs Apple: {cosine_sim(v1, v3):.4f}")  # Low (~0.20-0.30)
```

---

## 📚 Additional Resources

### Documentation

- [13_local_embeddings.md](../concepts/13_local_embeddings.md) — Concepts and theory
- [local-embeddings.md](../guides/core/local-embeddings.md) — Practical guide
- [custom-embedder.md](../guides/extending/custom-embedder.md) — Extending for Windows/Linux

### External Links

- [MLX Framework](https://ml-explore.github.io/mlx/build/html/index.html) — Official Apple MLX docs
- [mlx-embeddings](https://github.com/sbarkar/mlx-embeddings) — High-level embeddings library
- [mlx-lm](https://github.com/ml-explore/mlx-examples/tree/main/llms) — Low-level LLM utilities
- [Qwen3 Model Card](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) — Official Qwen3 documentation
- [MTEB Leaderboard](https://huggingface.co/spaces/mteb/leaderboard) — Embedding benchmarks

### Research Papers

- **Matryoshka Representation Learning** (2022): [arXiv:2205.13147](https://arxiv.org/abs/2205.13147)
- **BGE Embeddings** (2023): [arXiv:2309.07597](https://arxiv.org/abs/2309.07597)
- **Qwen Technical Report** (2023): [arXiv:2309.16609](https://arxiv.org/abs/2309.16609)

---

## 🔄 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | Dec 2025 | Initial release with 3 preset models |

---

## 📝 See Also

- [configuration-options.md](configuration-options.md) — All config parameters
- [interfaces.md](interfaces.md) — BaseEmbedder interface specification
- [cli-commands.md](cli-commands.md) — CLI usage with LocalEmbedder
