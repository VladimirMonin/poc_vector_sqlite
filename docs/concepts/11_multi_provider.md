# Multi-Provider Architecture

> Как работает мультипровайдерная архитектура SemanticCore

**Сложность:** 🟡 intermediate  
**Требует понимания:** Interfaces, Dependency Injection

---

## 🎯 Что это такое?

**Multi-Provider Architecture** позволяет использовать разные провайдеры AI для разных задач:

- **Embeddings:** Gemini / Local MLX / OpenAI
- **LLM:** Gemini / OpenAI / Ollama / vLLM
- **Transcription:** Gemini Audio API / Local Whisper
- **Vision:** Gemini Vision API / Local Qwen3-VL

**Ключевая фишка:** Меняете провайдера **через конфиг**, без изменения кода.

---

## 🏗️ Архитектура

### Интерфейсы (Contracts)

```python
# semantic_core/interfaces/embeddings.py
class BaseEmbedder(ABC):
    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        """Создать embeddings для списка текстов."""
        pass
    
    @abstractmethod
    def embed_query(self, text: str) -> np.ndarray:
        """Создать embedding для поискового запроса."""
        pass
    
    @property
    @abstractmethod
    def dimension(self) -> int:
        """Размерность вектора."""
        pass
```

### Реализации (Adapters)

```python
# semantic_core/infrastructure/gemini/embedder.py
class GeminiEmbedder(BaseEmbedder):
    def __init__(self, api_key: str, model: str = "text-embedding-004"):
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self._dimension = 768
    
    def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        response = self.client.models.embed_content(
            model=self.model,
            contents=texts
        )
        return [np.array(emb.values) for emb in response.embeddings]
    
    @property
    def dimension(self) -> int:
        return self._dimension
```

```python
# semantic_core/infrastructure/local/embeddings/embedder.py
class LocalEmbedder(BaseEmbedder):
    def __init__(self, model: str = "all-MiniLM-L6-v2", device: str = "mps"):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model, device=device)
        self._dimension = self.model.get_sentence_embedding_dimension()
    
    def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        return self.model.encode(texts, convert_to_numpy=True)
    
    @property
    def dimension(self) -> int:
        return self._dimension
```

### ComponentFactory (DI Container)

```python
# semantic_core/core/factory.py
class ComponentFactory:
    @staticmethod
    def create_embedder(config: SemanticConfig) -> BaseEmbedder:
        provider = config.defaults.embedding_provider
        
        if provider == "gemini":
            return GeminiEmbedder(
                api_key=config.providers_gemini.api_key,
                model=config.providers_gemini.embedding_model
            )
        elif provider == "local":
            return LocalEmbedder(
                model=config.providers_local.embedding_model,
                device=config.providers_local.device
            )
        elif provider == "openai":
            raise NotImplementedError("OpenAI embedder coming soon")
        else:
            raise ValueError(f"Unknown provider: {provider}")
```

---

## ⚙️ Конфигурация

### Базовая структура

```toml
# semantic.toml
[defaults]
embedding_provider = "gemini"    # Какой embedder использовать
llm_provider = "gemini"          # Какой LLM использовать
transcription_provider = "none"  # Опционально
vision_provider = "none"         # Опционально

[providers.gemini]
api_key = "${GEMINI_API_KEY}"
embedding_model = "text-embedding-004"
llm_model = "gemini-2.0-flash"

[providers.local]
device = "mps"                   # mps (Apple Silicon), cpu
embedding_model = "qwen3-embedding"  # or "all-minilm", "bge-small"
whisper_model = "base"
```

### Примеры конфигураций

#### Конфиг 1: Полностью облачный (Gemini)

```toml
[defaults]
embedding_provider = "gemini"
llm_provider = "gemini"
transcription_provider = "gemini"
vision_provider = "gemini"

[providers.gemini]
api_key = "${GEMINI_API_KEY}"
embedding_model = "text-embedding-004"
llm_model = "gemini-2.0-flash"
```

**Плюсы:**

- ✅ Лучшее качество
- ✅ Не требует GPU
- ✅ Быстрое распознавание (Gemini Audio API)

**Минусы:**

- ❌ Требует интернет
- ❌ Платный (API costs)

#### Конфиг 2: Полностью локальный (MLX)

```toml
[defaults]
embedding_provider = "local"
llm_provider = "ollama"
transcription_provider = "whisper"
vision_provider = "local"

[providers.local]
device = "mps"                    # Apple Silicon
embedding_model = "qwen3-embedding"  # 1024D, multilingual, best quality
whisper_model = "base"
vision_model = "Qwen/Qwen2.5-VL-4B"

[providers.ollama]
base_url = "http://localhost:11434"
model = "llama3.2:3b"
```

**Плюсы:**

- ✅ Работает offline
- ✅ Бесплатно
- ✅ Приватность данных
- ✅ Быстро на Apple Silicon

**Минусы:**

- ❌ Требует GPU (или медленно на CPU)
- ❌ Качество ниже облачных моделей

#### Конфиг 3: Гибридный (экономия + качество)

```toml
[defaults]
embedding_provider = "local"      # Локальные embeddings (дёшево)
llm_provider = "gemini"           # Облачный LLM (качество)
transcription_provider = "whisper"  # Локальный Whisper (бесплатно)
vision_provider = "gemini"        # Облачное Vision (качество)

[providers.gemini]
api_key = "${GEMINI_API_KEY}"
llm_model = "gemini-2.0-flash"
vision_model = "gemini-2.0-flash"

[providers.local]
device = "mps"
embedding_model = "qwen3-embedding"  # 1024D, высокое качество, оффлайн
whisper_model = "base"
```

**Плюсы:**

- ✅ Экономия на embeddings (самая частая операция)
- ✅ Качественный LLM для ответов
- ✅ Локальная транскрипция (privacy)

---

## 📊 Сравнение провайдеров

### Embeddings

| Провайдер | Модель | Размерность | Скорость | Качество | Стоимость | Языки |
|-----------|--------|-------------|----------|----------|-----------|-------|
| Gemini | `text-embedding-004` | 768 | ⚡⚡⚡ | ⭐⭐⭐⭐⭐ | $0.00001/1K tokens | Multi |
| OpenAI | `text-embedding-3-small` | 1536 | ⚡⚡⚡ | ⭐⭐⭐⭐⭐ | $0.02/1M tokens | Multi |
| Local | `qwen3-embedding` | 1024 | ⚡⚡ | ⭐⭐⭐⭐ | FREE | Multi |
| Local | `bge-small-en` | 384 | ⚡⚡⚡⚡ | ⭐⭐⭐⭐ | FREE | EN |
| Local | `all-MiniLM-L6-v2` | 384 | ⚡⚡⚡⚡ | ⭐⭐⭐ | FREE | EN |

**Заметки:**
- **Qwen3-embedding** — лучший локальный выбор: высокое качество ≈ Gemini, многоязычность (EN/RU/ZH/...), MRL support
- **Hardware:** Local провайдеры требуют macOS с Apple Silicon (M1+). Windows/Linux используют sentence-transformers
- **Подробнее:** См. [13_local_embeddings.md](13_local_embeddings.md), [local-models.md](../reference/local-models.md)

### LLM

| Провайдер | Модель | Параметры | Скорость | Качество | Стоимость |
|-----------|--------|-----------|----------|----------|-----------|
| Gemini | `gemini-2.0-flash` | ? | ⚡⚡⚡⚡ | ⭐⭐⭐⭐⭐ | $0.10/1M tokens |
| OpenAI | `gpt-4o` | ? | ⚡⚡⚡ | ⭐⭐⭐⭐⭐ | $2.50/1M tokens |
| Ollama | `llama3.2:3b` | 3B | ⚡⚡ | ⭐⭐⭐ | FREE |

### Transcription

| Провайдер | Модель | Скорость | Качество | Стоимость |
|-----------|--------|----------|----------|-----------|
| Gemini | Audio API | ⚡⚡⚡⚡ | ⭐⭐⭐⭐⭐ | $0.000025/sec |
| Whisper | `base` (74M) | ⚡⚡⚡ | ⭐⭐⭐ | FREE |
| Whisper | `large-v3-turbo` (809M) | ⚡⚡ | ⭐⭐⭐⭐ | FREE |

---

## 🔧 Использование

### Создание SemanticCore через Factory

```python
from semantic_core import SemanticConfig, get_config
from semantic_core.core.factory import ComponentFactory

# 1. Загружаем конфиг
config = get_config()  # Читает semantic.toml + .env + CLI args

# 2. Создаём провайдеров через фабрику
embedder = ComponentFactory.create_embedder(config)
llm = ComponentFactory.create_llm(config)
transcriber = ComponentFactory.create_transcriber(config)  # может быть None

# 3. Создаём SemanticCore
core = ComponentFactory.create_semantic_core(config)

# 4. Используем
doc = core.ingest("example.md")
results = core.search("query")
```

### Смена провайдера в runtime

```python
# Вариант 1: Через переменные окружения
import os
os.environ["SEMANTIC_DEFAULTS__EMBEDDING_PROVIDER"] = "local"

config = get_config()
core = ComponentFactory.create_semantic_core(config)
```

```bash
# Вариант 2: Через CLI аргументы
semantic ingest doc.md --embedding-provider local
```

---

## ⚠️ Optional Dependencies

Некоторые провайдеры требуют дополнительных зависимостей:

### Local embeddings

```bash
pip install semantic-core[local-embeddings]
# Устанавливает: sentence-transformers
```

### Whisper transcription

```bash
pip install semantic-core[whisper]
# Устанавливает: mlx-whisper (Apple), openai-whisper (CUDA/CPU)
```

### OpenAI providers

```bash
pip install semantic-core[openai]
# Устанавливает: openai>=1.0
```

### Local vision

```bash
pip install semantic-core[local-vision]
# Устанавливает: mlx-vlm
```

### Graceful degradation

Если зависимости отсутствуют, фабрика выдаёт понятную ошибку:

```python
try:
    embedder = ComponentFactory.create_embedder(config)
except ImportError as e:
    print(e)
    # ImportError: Local embeddings not available.
    # Install with: pip install semantic-core[local-embeddings]
```

---

## 📚 Связанные концепции

- [Plugin System](10_plugin_system.md) — как реализованы интерфейсы
- [Configuration](../guides/core/configuration.md) — полный справочник по semantic.toml
- [Debug Observatory](12_debug_observatory.md) — как инспектировать провайдеры

---

## 🔗 Архитектурные статьи

Детальная документация в архитектурном сериале:

- [Phase 15: Multi-Provider Architecture](../../doc/architecture/phase_15_multimodal_flexibility/README.md)
- [85: Configuration & Factory](../../doc/architecture/phase_15_multimodal_flexibility/85_configuration_factory.md)
- [86: Optional Dependencies](../../doc/architecture/phase_15_multimodal_flexibility/86_optional_dependencies.md)
