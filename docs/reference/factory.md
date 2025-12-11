---
title: "ComponentFactory Reference"
description: "API документация ComponentFactory для создания провайдеров"
tags: ["reference", "factory", "multi-provider"]
---

# ComponentFactory Reference 🏭

> Фабрика для создания всех компонентов SemanticCore через unified конфигурацию

---

## Обзор

`ComponentFactory` — центральный класс Phase 15 Multi-Provider Architecture. Создаёт embedders, LLM, vision, transcription провайдеры на основе `SemanticConfig`.

**Ключевые преимущества:**
- ✅ Единая точка создания всех компонентов
- ✅ Автоматический выбор провайдера из конфигурации
- ✅ Graceful degradation (fallback при ошибках)
- ✅ Type-safe (TypeVar для правильных типов)

**Модуль:** `semantic_core.core.factory`

---

## Class Methods

### `create_embedder(config: SemanticConfig) → BaseEmbedder`

Создаёт embedder на основе `config.defaults.embedding_provider`.

**Parameters:**
- `config` — экземпляр `SemanticConfig`

**Returns:**
- `BaseEmbedder` (GeminiEmbedder, LocalEmbedder, или OpenAIEmbedder)

**Raises:**
- `ValueError` — если provider неизвестен или не настроен
- `ImportError` — если зависимости провайдера не установлены (например, MLX для Local)
- `RuntimeError` — если провайдер не может быть инициализирован (например, MPS недоступен)

**Supported Providers:**
- `"gemini"` → `GeminiEmbedder` (требует `GEMINI_API_KEY`)
- `"local"` → `LocalEmbedder` (требует MLX, macOS Apple Silicon)
- `"openai"` → `OpenAIEmbedder` (требует `OPENAI_API_KEY`)

**Example:**
```python
from semantic_core import get_config
from semantic_core.core.factory import ComponentFactory

# Загрузить конфигурацию (semantic.toml + env)
config = get_config()

# Создать embedder
embedder = ComponentFactory.create_embedder(config)

print(f"Provider: {config.defaults.embedding_provider}")
print(f"Dimension: {embedder.dimension}")
print(f"Model: {embedder.model_name}")

# Использовать
vector = embedder.embed_query("semantic search")
```

**Configuration:**
```toml
[defaults]
embedding_provider = "local"

[providers.local]
embedding_model = "qwen3-embedding"  # 1024D
device = "mps"
```

---

### `create_llm(config: SemanticConfig) → BaseLLMProvider | None`

Создаёт LLM provider на основе `config.defaults.llm_provider`.

**Parameters:**
- `config` — экземпляр `SemanticConfig`

**Returns:**
- `BaseLLMProvider` (GeminiLLMProvider, OpenAILLMProvider, OllamaLLMProvider) или `None` если provider="none"

**Raises:**
- `ValueError` — если provider неизвестен
- `ImportError` — если зависимости не установлены
- `RuntimeError` — если API недоступен

**Supported Providers:**
- `"gemini"` → `GeminiLLMProvider`
- `"openai"` → `OpenAILLMProvider`
- `"ollama"` → `OllamaLLMProvider` (local)
- `"none"` → `None` (без LLM)

**Example:**
```python
llm = ComponentFactory.create_llm(config)

if llm:
    result = llm.generate("Explain semantic search")
    print(result.text)
else:
    print("LLM not configured")
```

**Configuration:**
```toml
[defaults]
llm_provider = "gemini"

[providers.gemini]
api_key = "${GEMINI_API_KEY}"
llm_model = "gemini-2.0-flash-exp"
temperature = 0.7
max_output_tokens = 2048
```

---

### `create_vision(config: SemanticConfig) → BaseVisionAnalyzer | None`

Создаёт vision analyzer на основе `config.defaults.vision_provider`.

**Parameters:**
- `config` — экземпляр `SemanticConfig`

**Returns:**
- `BaseVisionAnalyzer` (GeminiImageAnalyzer, LocalVisionAnalyzer) или `None` если provider="none"

**Raises:**
- `ValueError` — если provider неизвестен
- `ImportError` — если зависимости не установлены
- `RuntimeError` — если API/model недоступны

**Supported Providers:**
- `"gemini"` → `GeminiImageAnalyzer`
- `"local"` → `LocalVisionAnalyzer` (Qwen3-VL через MLX)
- `"none"` → `None`

**Example:**
```python
vision = ComponentFactory.create_vision(config)

if vision:
    result = vision.analyze_image("path/to/image.jpg")
    print(result.description)
```

**Configuration:**
```toml
[defaults]
vision_provider = "gemini"

[providers.gemini]
api_key = "${GEMINI_API_KEY}"

[multimodal]
output_language = "ru"
max_output_tokens = 2048
```

---

### `create_transcriber(config: SemanticConfig) → BaseTranscriber | None`

Создаёт transcriber на основе `config.defaults.transcription_provider`.

**Parameters:**
- `config` — экземпляр `SemanticConfig`

**Returns:**
- `BaseTranscriber` (GeminiAudioAnalyzer, LocalWhisperTranscriber) или `None` если provider="none"

**Raises:**
- `ValueError` — если provider неизвестен
- `ImportError` — если зависимости не установлены
- `RuntimeError` — если model недоступен

**Supported Providers:**
- `"gemini"` → `GeminiAudioAnalyzer`
- `"whisper"` → `LocalWhisperTranscriber` (Whisper через MLX)
- `"none"` → `None`

**Example:**
```python
transcriber = ComponentFactory.create_transcriber(config)

if transcriber:
    result = transcriber.transcribe("audio.mp3")
    print(result.text)
```

**Configuration:**
```toml
[defaults]
transcription_provider = "whisper"

[providers.local]
whisper_model = "base"  # tiny, base, small, medium, large
device = "mps"
```

---

### `create_semantic_core(config: SemanticConfig) → SemanticCore`

Создаёт полный `SemanticCore` со всеми компонентами (embedder, store, LLM, vision, transcriber).

**Parameters:**
- `config` — экземпляр `SemanticConfig`

**Returns:**
- `SemanticCore` с инициализированными компонентами

**Raises:**
- `RuntimeError` — если критичные компоненты (embedder, store) не могут быть созданы

**Example:**
```python
from semantic_core import get_config
from semantic_core.core.factory import ComponentFactory

# One-liner для создания полного pipeline
config = get_config()
core = ComponentFactory.create_semantic_core(config)

# Готово к использованию
results = core.search("query")
```

**Внутренняя логика:**
```python
def create_semantic_core(config: SemanticConfig) -> SemanticCore:
    embedder = ComponentFactory.create_embedder(config)  # Required
    store = PeeweeVectorStore(config.db_path, embedder.dimension)  # Required
    
    # Optional components (graceful degradation)
    llm = ComponentFactory.create_llm(config)  # May be None
    vision = ComponentFactory.create_vision(config)  # May be None
    transcriber = ComponentFactory.create_transcriber(config)  # May be None
    
    return SemanticCore(
        embedder=embedder,
        store=store,
        llm=llm,
        vision_analyzer=vision,
        transcriber=transcriber
    )
```

---

## Error Handling

ComponentFactory использует graceful degradation:

### Critical Components (Exception)

Если **embedder** не может быть создан — выбрасывается exception:
```python
try:
    embedder = ComponentFactory.create_embedder(config)
except ImportError as e:
    print(f"MLX not installed: {e}")
    # Install: pip install semantic-core[local]
except ValueError as e:
    print(f"Unknown provider: {e}")
    # Check semantic.toml [defaults]embedding_provider
```

### Optional Components (None)

Если **LLM/Vision/Transcriber** не могут быть созданы — возвращается `None`:
```python
llm = ComponentFactory.create_llm(config)  # May return None

if llm is None:
    print("LLM not available, RAG will not work")
else:
    # Use RAG
    rag = RAGEngine(semantic_core=core)
    answer = rag.answer("question")
```

---

## Provider Detection

ComponentFactory автоматически выбирает провайдера из конфигурации:

```python
# semantic.toml
[defaults]
embedding_provider = "local"  # ← ComponentFactory читает отсюда
```

```python
# Python
config = get_config()
embedder = ComponentFactory.create_embedder(config)
# → Создаст LocalEmbedder с настройками из [providers.local]
```

**Приоритет:**
1. Environment variables (`SEMANTIC_DEFAULTS__EMBEDDING_PROVIDER=gemini`)
2. `semantic.toml` файл
3. Defaults в коде (fallback)

---

## Type Safety

ComponentFactory использует TypeVar для правильных типов:

```python
from typing import TypeVar

T = TypeVar('T', bound=BaseEmbedder)

def create_embedder(config: SemanticConfig) -> T:
    # Return type is exactly what you expect
    ...
```

**Benefits:**
- IDE autocomplete работает корректно
- Type checkers (mypy, pyright) не ругаются
- Clear API для пользователей

---

## Best Practices

### 1. Use create_semantic_core() для простых случаев

```python
# ✅ Good — one-liner
core = ComponentFactory.create_semantic_core(get_config())
```

```python
# ❌ Bad — manual assembly
embedder = ComponentFactory.create_embedder(config)
store = PeeweeVectorStore(config.db_path, embedder.dimension)
llm = ComponentFactory.create_llm(config)
core = SemanticCore(embedder, store, llm=llm)
```

### 2. Handle Optional Components

```python
# ✅ Good — проверяем None
core = ComponentFactory.create_semantic_core(config)

if core.llm:
    rag = RAGEngine(semantic_core=core)
    answer = rag.answer("question")
else:
    print("RAG unavailable — LLM not configured")
```

### 3. Configuration через semantic.toml

```python
# ✅ Good — централизованная конфигурация
config = get_config()  # Читает semantic.toml
embedder = ComponentFactory.create_embedder(config)
```

```python
# ❌ Bad — hardcoded
embedder = GeminiEmbedder(api_key="...", dimension=768)
```

---

## Configuration Examples

### Cloud Mode (Gemini)

```toml
[defaults]
embedding_provider = "gemini"
llm_provider = "gemini"
vision_provider = "gemini"

[providers.gemini]
api_key = "${GEMINI_API_KEY}"
embedding_model = "text-embedding-004"
dimension = 768
llm_model = "gemini-2.0-flash-exp"
```

### Local Mode (macOS)

```toml
[defaults]
embedding_provider = "local"
llm_provider = "gemini"  # LLM остаётся cloud
transcription_provider = "whisper"
vision_provider = "local"

[providers.local]
embedding_model = "qwen3-embedding"  # 1024D
whisper_model = "base"
device = "mps"

[providers.gemini]
api_key = "${GEMINI_API_KEY}"
llm_model = "gemini-2.0-flash-exp"
```

### Hybrid Mode (Экономия)

```toml
[defaults]
embedding_provider = "local"   # FREE, offline
llm_provider = "gemini"        # Quality
transcription_provider = "none"
vision_provider = "none"

[providers.local]
embedding_model = "qwen3-embedding"
device = "mps"

[providers.gemini]
api_key = "${GEMINI_API_KEY}"
llm_model = "gemini-2.0-flash-exp"
```

---

## См. также

- [Multi-Provider Architecture](../concepts/11_multi_provider.md) — обзор архитектуры
- [Local Embeddings Guide](../guides/core/local-embeddings.md) — настройка локальных моделей
- [Flask Integration](../guides/frameworks/flask.md) — использование ComponentFactory в Flask
- [Configuration Reference](configuration-options.md) — все параметры semantic.toml
