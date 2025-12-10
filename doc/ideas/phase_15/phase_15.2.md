# 🧮 Phase 15.2: Local Embeddings

**Статус:** Planning  
**Зависимости:** Phase 15.0 (BaseEmbedder расширение)  
**Цель:** Интегрировать MLX embeddings из `examples/poc_apple_local_llm`

---

## 🎯 Задачи

1. Перенести код embeddings из `examples/poc_apple_local_llm/`
2. Реализовать `LocalEmbedder`, имплементирующий `BaseEmbedder`
3. Поддержать несколько моделей (all-MiniLM, Qwen3-Embedding)
4. Обеспечить совместимость с существующим `SmartSplitter`

---

## 📂 Исходный код (донор)

### Ключевой файл

**Файл:** `examples/poc_apple_local_llm/src/lightweight_core.py` (lines 50-130)

```python
class LightweightCore:
    def _get_embedding_model(self):
        """Ленивая загрузка модели эмбеддингов."""
        if self._embedding_model is None:
            from mlx_embeddings.utils import load
            self._embedding_model, self._tokenizer = load(
                "mlx-community/all-MiniLM-L6-v2-4bit"
            )
        return self._embedding_model, self._tokenizer

    def _generate_embedding(self, text: str) -> np.ndarray:
        model, tokenizer = self._get_embedding_model()
        
        inputs = tokenizer.batch_encode_plus(
            [text],
            return_tensors="mlx",
            padding=True,
            truncation=True,
            max_length=512,
        )
        
        outputs = model(inputs["input_ids"], attention_mask=inputs["attention_mask"])
        embeddings = outputs.text_embeds
        
        return np.array(embeddings[0])
```

### Исследование моделей

**Файл:** `examples/poc_apple_local_llm/EMBEDDINGS_MODELS_INVESTIGATION.md`

| Модель | Размерность | Языки | Размер | Max Tokens |
|--------|-------------|-------|--------|------------|
| `all-MiniLM-L6-v2-4bit` | 384 | 50+ | ~150 MB | 512 |
| `bge-small-en-v1.5-4bit` | 384 | EN only | 18.9 MB | 512 |
| **`Qwen3-Embedding-0.6B-4bit-DWQ`** | 1024 | 100+ | 335 MB | 8192 |

**Вывод из исследования:**
> ✅ Qwen3-Embedding-0.6B — **идеальна для проекта**: мультиязычность (RU/EN/ZH), длинный контекст (8192), высокая размерность (1024), чистый MLX без PyTorch.

---

## 🔧 Проблема: Разные размерности

### Gemini vs Local

| Модель | Размерность | Max Tokens |
|--------|-------------|------------|
| Gemini Embedding 001 | 768 | 2048 |
| all-MiniLM | 384 | 512 |
| Qwen3-Embedding | 1024 | 8192 |

**Последствия:**

- Нельзя смешивать векторы разных моделей в одной БД
- `SmartSplitter` должен знать `max_tokens` модели

### Решение: Properties в BaseEmbedder

```python
class LocalEmbedder(BaseEmbedder):
    @property
    def dimension(self) -> int:
        return self._dimension  # 384 / 768 / 1024
    
    @property
    def max_tokens(self) -> int:
        return self._max_tokens  # 512 / 2048 / 8192
```

---

## 📊 Диаграмма классов

```
┌─────────────────────────────────────────────────────────────┐
│                     BaseEmbedder (ABC)                       │
├─────────────────────────────────────────────────────────────┤
│ + embed_documents(texts) → list[ndarray]                     │
│ + embed_query(text) → ndarray                                │
│ + dimension: int                                             │
│ + max_tokens: int                                            │
└─────────────────────────────────────────────────────────────┘
                              △
            ┌─────────────────┼─────────────────┐
            │                 │                 │
┌───────────────────┐ ┌───────────────┐ ┌───────────────────┐
│  GeminiEmbedder   │ │ LocalEmbedder │ │  OpenAIEmbedder   │
├───────────────────┤ ├───────────────┤ ├───────────────────┤
│ - api_key         │ │ - model_name  │ │ - api_key         │
│ - model_name      │ │ - device      │ │ - model           │
│                   │ │ - tokenizer   │ │ - base_url        │
│ dimension=768     │ │ dimension=var │ │ dimension=1536    │
│ max_tokens=2048   │ │ max_tokens=var│ │ max_tokens=8191   │
└───────────────────┘ └───────────────┘ └───────────────────┘
```

---

## 🏗️ Целевая структура

```
semantic_core/infrastructure/local/
├── embeddings/
│   ├── __init__.py
│   ├── embedder.py         # LocalEmbedder
│   ├── models.py           # Конфигурации моделей
│   └── tokenizers.py       # Унификация токенизаторов
```

---

## 📝 Контракт LocalEmbedder

```python
class LocalEmbedder(BaseEmbedder):
    """Локальные embeddings через MLX или sentence-transformers."""
    
    # Предустановленные модели
    MODELS = {
        "all-minilm": ModelConfig(
            name="mlx-community/all-MiniLM-L6-v2-4bit",
            dimension=384,
            max_tokens=512,
            backend="mlx-embeddings",
        ),
        "qwen3-embedding": ModelConfig(
            name="mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ",
            dimension=1024,
            max_tokens=8192,
            backend="mlx-lm",  # ⚠️ Другой загрузчик!
        ),
        "bge-small": ModelConfig(
            name="mlx-community/bge-small-en-v1.5-4bit",
            dimension=384,
            max_tokens=512,
            backend="mlx-embeddings",
        ),
    }
    
    def __init__(
        self,
        model: str = "all-minilm",  # Ключ из MODELS или полный путь HF
        device: Optional[str] = None,
    ):
        if model in self.MODELS:
            self._config = self.MODELS[model]
        else:
            # Кастомная модель — пользователь указывает параметры
            raise ValueError(f"Unknown model: {model}. Use one of: {list(self.MODELS.keys())}")
        
        self._model = None  # Lazy load
        self._tokenizer = None
    
    def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        self._ensure_loaded()
        # Батчевая обработка
        embeddings = []
        for text in texts:
            emb = self._embed_single(text)
            embeddings.append(emb)
        return embeddings
    
    def embed_query(self, text: str) -> np.ndarray:
        self._ensure_loaded()
        # Для некоторых моделей нужен префикс "query:"
        if self._config.needs_query_prefix:
            text = f"query: {text}"
        return self._embed_single(text)
    
    @property
    def dimension(self) -> int:
        return self._config.dimension
    
    @property
    def max_tokens(self) -> int:
        return self._config.max_tokens
```

---

## ⚠️ Особенности Qwen3-Embedding

Из исследования (`EMBEDDINGS_MODELS_INVESTIGATION.md`):

> ✅ **БЕЗ PyTorch зависимостей** — загружается через `mlx-lm`

```python
# Qwen3 загружается иначе!
from mlx_lm import load

model, tokenizer = load("mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ")
```

**Решение:** Абстрагировать загрузку в `models.py`:

```python
def load_model(config: ModelConfig):
    if config.backend == "mlx-embeddings":
        from mlx_embeddings.utils import load
        return load(config.name)
    elif config.backend == "mlx-lm":
        from mlx_lm import load
        return load(config.name)
    else:
        raise ValueError(f"Unknown backend: {config.backend}")
```

---

## 🔗 Связь со SmartSplitter

### Текущая проблема

```python
# SmartSplitter.__init__
def __init__(self, parser, chunk_size=1800, ...):
    self.chunk_size = chunk_size  # Hardcoded!
```

### Решение Phase 15.0

```python
# SmartSplitter теперь знает про embedder
def __init__(self, parser, embedder: BaseEmbedder = None, ...):
    if embedder:
        # Автоподстройка под модель
        self.chunk_size = self._calculate_chunk_size(embedder.max_tokens)
    else:
        self.chunk_size = 1800  # Default для Gemini
```

---

## 📦 Зависимости

```toml
# pyproject.toml
[project.optional-dependencies]
local-embeddings = [
    "mlx>=0.10.0; platform_machine == 'arm64' and sys_platform == 'darwin'",
    "mlx-embeddings>=0.1.0; platform_machine == 'arm64' and sys_platform == 'darwin'",
    "mlx-lm>=0.10.0; platform_machine == 'arm64' and sys_platform == 'darwin'",
]

local-embeddings-torch = [
    "sentence-transformers>=2.0.0",
    "torch>=2.0.0",
]
```

---

## ✅ Критерии готовности

- [ ] `LocalEmbedder` реализует `BaseEmbedder` с `dimension`/`max_tokens`
- [ ] Поддержка минимум 2 моделей (all-MiniLM, Qwen3-Embedding)
- [ ] Lazy loading моделей
- [ ] Graceful error при отсутствии MLX
- [ ] Unit-тесты с mock модели
- [ ] Интеграционный тест на реальной модели

---

## 🔗 Связанные документы

- **Донор:** `examples/poc_apple_local_llm/EMBEDDINGS_MODELS_INVESTIGATION.md`
- **Интерфейс:** [Phase 15.0](phase_15.0.md) — `BaseEmbedder` расширение
- **Использование:** `SmartSplitter` — динамический `chunk_size`
