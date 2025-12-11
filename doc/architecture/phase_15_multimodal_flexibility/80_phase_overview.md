# Phase 15: Multi-Provider Architecture — Обзор

> **Phase 15.0-15.5** | Превращение SemanticCore из Gemini-монолита в мультипровайдерную платформу

---

## 📦 Коммиты

- `cc31553` — phase 15.4 feat: Configuration & Factory
- `8f2bcfe` — phase 15.5 feat: Optional Dependencies & Error Handling
- Другие коммиты разбросаны по подфазам (см. отдельные статьи)

---

## 🎯 Миссия фазы

**Проблема:**

До Phase 15 `SemanticCore` был **жёстко привязан к Gemini API**:

```python
class SemanticConfig:
    gemini_api_key: str
    gemini_embedding_model: str = "models/gemini-embedding-001"
    gemini_llm_model: str = "models/gemini-2.0-flash"
```

**Последствия:**

- ❌ Vendor lock-in — нельзя переключиться на другие провайдеры
- ❌ Дублирование кода — для каждого провайдера отдельные if-else
- ❌ Плохая тестируемость — сложно мокать создание компонентов
- ❌ Дорого — все операции через облачный API

**Решение (Phase 15):**

Создать **провайдеро-агностичную архитектуру** через интерфейсы и фабрики:

```python
# Конфигурация
[defaults]
embedding_provider = "local"      # Локальный embedder (бесплатно)
llm_provider = "gemini"           # Облачный LLM (качество)
transcription_provider = "whisper" # Локальная транскрипция

# Компоненты создаются через фабрику
embedder = ComponentFactory.create_embedder(config)  # → LocalEmbedder
llm = ComponentFactory.create_llm(config)            # → GeminiLLMProvider
```

**Преимущества:**

- ✅ **Гибкость** — меняем провайдера через конфиг, без изменения кода
- ✅ **Экономия** — используем локальные модели где возможно
- ✅ **Privacy** — локальная обработка приватных данных
- ✅ **Offline** — работа без интернета (local-only конфиг)
- ✅ **Тестируемость** — легко создавать моки через фабрику

---

## 📊 Что изменилось

### До (Phase 14)

```python
class SemanticCore:
    def __init__(self, config: SemanticConfig):
        # Жёсткая привязка к Gemini
        self.embedder = GeminiEmbedder(config.gemini_api_key)
        self.image_analyzer = GeminiImageAnalyzer(config.gemini_api_key)
        self.audio_analyzer = GeminiAudioAnalyzer(config.gemini_api_key)
```

### После (Phase 15)

```python
class SemanticCore:
    def __init__(
        self,
        embedder: BaseEmbedder,          # ← Интерфейс, не реализация!
        llm: BaseLLMProvider,
        transcriber: Optional[ITranscriber] = None,
        vision_analyzer: Optional[IVisionAnalyzer] = None,
        # ...
    ):
        self.embedder = embedder
        self.llm = llm
        self.transcriber = transcriber
        self.vision_analyzer = vision_analyzer

# Создание через фабрику
core = ComponentFactory.create_semantic_core(config)
```

---

## 🏗️ Архитектура Phase 15

### Структура подфаз

| Подфаза | Задача | Статья |
|---------|--------|--------|
| **15.0** | Interface Contracts | 80_phase_overview.md (эта статья) |
| **15.1** | Gemini Vision & Audio интерфейсы | 82_vision_audio_analysis.md |
| **15.2** | Local Whisper транскрипция | 83_whisper_local_transcription.md |
| **15.3** | OpenAI & Ollama LLM Provider | 84_openai_llm_provider.md |
| **15.4** | Configuration & ComponentFactory | 85_configuration_factory.md |
| **15.5** | Optional Dependencies | 86_optional_dependencies.md |

### Ключевые компоненты

```
semantic_core/
├── interfaces/              # Контракты провайдеров
│   ├── embeddings.py       # BaseEmbedder
│   ├── llm.py              # BaseLLMProvider
│   ├── transcription.py    # ITranscriber (NEW)
│   └── vision.py           # IVisionAnalyzer (NEW)
│
├── infrastructure/
│   ├── gemini/            # Gemini провайдеры
│   │   ├── embedder.py
│   │   ├── llm_provider.py
│   │   ├── image_analyzer.py (NEW - IVisionAnalyzer)
│   │   └── audio_analyzer.py (NEW - ITranscriber)
│   │
│   ├── local/             # Local провайдеры
│   │   ├── embeddings/
│   │   │   └── embedder.py (NEW - BaseEmbedder via MLX)
│   │   └── whisper/
│   │       └── transcriber.py (NEW - ITranscriber via Whisper)
│   │
│   └── openai/            # OpenAI/Ollama провайдеры
│       └── llm.py (NEW - BaseLLMProvider unified SDK)
│
├── core/
│   └── factory.py (NEW)   # ComponentFactory — DI container
│
└── config.py              # Провайдер-специфичные Pydantic модели
```

---

## 🔑 Ключевые паттерны

### 1️⃣ **Interface Segregation** (Phase 15.0-15.1)

Создали чёткие контракты для каждого типа провайдера:

```python
# Embeddings
class BaseEmbedder(ABC):
    @abstractmethod
    def embed_documents(texts) -> list[ndarray]: ...
    
    @property
    @abstractmethod
    def dimension(self) -> int: ...  # NEW in Phase 15

# Transcription (NEW)
class ITranscriber(ABC):
    @abstractmethod
    def transcribe(audio_path) -> TranscriptionResult: ...

# Vision (NEW)
class IVisionAnalyzer(ABC):
    @abstractmethod
    def analyze(image_path, prompt) -> VisionResult: ...
```

### 2️⃣ **Adapter Pattern** (Phase 15.1-15.3)

Обернули специфичные API в единые интерфейсы:

```
GeminiImageAnalyzer  → IVisionAnalyzer
GeminiAudioAnalyzer  → ITranscriber
WhisperTranscriber   → ITranscriber
OpenAILLMProvider    → BaseLLMProvider
```

### 3️⃣ **Factory Method** (Phase 15.4)

`ComponentFactory` создаёт провайдеров на основе конфига:

```python
@staticmethod
def create_embedder(config: SemanticConfig) -> BaseEmbedder:
    if config.defaults.embedding_provider == "gemini":
        return GeminiEmbedder(...)
    elif config.defaults.embedding_provider == "local":
        return LocalEmbedder(...)
    # ...
```

### 4️⃣ **Dependency Injection** (Phase 15.4)

`SemanticCore` не создаёт компоненты сам → получает через конструктор:

```python
# ❌ БЫЛО:
class SemanticCore:
    def __init__(self, config):
        self.embedder = GeminiEmbedder(config.api_key)

# ✅ СТАЛО:
class SemanticCore:
    def __init__(self, embedder: BaseEmbedder):
        self.embedder = embedder
```

### 5️⃣ **Strategy Pattern**

`DefaultsConfig` определяет стратегии выбора провайдеров:

```toml
[defaults]
embedding_provider = "local"    # Strategy: LocalEmbedder
llm_provider = "ollama"         # Strategy: OpenAILLMProvider (Ollama preset)
```

### 6️⃣ **Optional Dependencies** (Phase 15.5)

Graceful degradation при отсутствии зависимостей:

```python
try:
    from mlx_embeddings import EmbeddingModel
except ImportError:
    raise ImportError(
        "Local embeddings not available. "
        "Install with: pip install semantic-core[local-embeddings]"
    )
```

---

## 📦 Поддерживаемые провайдеры

### Embeddings

| Провайдер | Модель | Размерность | Стоимость | Скорость |
|-----------|--------|-------------|-----------|----------|
| **Gemini** | `text-embedding-004` | 768 (MRL: 768/1536/3072) | $0.00001/1K tokens | ⚡⚡⚡ |
| **Local** | `all-MiniLM-L6-v2` | 384 | FREE | ⚡⚡⚡⚡ |
| **Local** | `bge-small-en` | 384 | FREE | ⚡⚡⚡⚡ |
| **OpenAI** | `text-embedding-3-large` | 3072 | $0.00013/1K tokens | ⚡⚡⚡ |

### LLM

| Провайдер | Модель | Стоимость | Использование |
|-----------|--------|-----------|---------------|
| **Gemini** | `gemini-2.0-flash` | $0.10/1M tokens | RAG, summarization |
| **OpenAI** | `gpt-4o` | $2.50/1M tokens | High quality |
| **Ollama** | `llama3.2:3b` | FREE | Local chat |

### Transcription

| Провайдер | Модель | Стоимость | Таймкоды |
|-----------|--------|-----------|----------|
| **Gemini** | Audio API | $0.000025/sec | ❌ |
| **Whisper** | `base` (74M) | FREE | ✅ |
| **Whisper** | `large-v3-turbo` (809M) | FREE | ✅ |

### Vision

| Провайдер | Модель | Стоимость | OCR |
|-----------|--------|-----------|-----|
| **Gemini** | Vision API | $0.00025/image | ✅ |
| **Local** | `Qwen2.5-VL-4B` | FREE | ✅ |

---

## 🎓 Что узнали

### ✅ Wins

1. **Полная замена провайдера через конфиг** — без изменения кода
2. **Единые интерфейсы** — легко добавить нового провайдера
3. **Graceful degradation** — отсутствие optional dependencies не ломает систему
4. **Обратная совместимость** — legacy конфиги работают через Pydantic validators
5. **Экономия** — можно использовать бесплатные локальные модели

### ⚠️ Challenges

1. **Lazy imports** сложно тестировать в unit-тестах (нужен integration)
2. **OpenAI Embedder** пока не реализован (NotImplementedError)
3. **Error handling** при отсутствии зависимостей требует улучшения
4. **Documentation debt** — нужно обновить docs/guides для мультипровайдеров (→ Phase 16)

---

## 📊 Статистика

### Code changes

| Подфаза | Files Changed | Lines Added | Key Modules |
|---------|--------------|-------------|-------------|
| 15.0-15.1 | 4 | ~300 | `interfaces/{transcription,vision}.py` |
| 15.2 | 3 | ~400 | `local/whisper/transcriber.py` |
| 15.3 | 2 | ~250 | `openai/llm.py` |
| 15.4 | 5 | ~960 | `config.py`, `core/factory.py` |
| 15.5 | 3 | ~150 | `utils/dependencies.py` |

### Tests

- **Unit tests:** 11 passed, 8 skipped (lazy imports)
- **Integration tests:** 6 passed (factory, local embedder)

---

## 🔮 Следующие шаги

### Phase 16: Debug Observatory

- **Inspect command** — `semantic inspect file.md` для визуализации pipeline
- **Multi-provider snapshots** — сравнение разных конфигов
- **Golden file testing** — regression тесты с эталонными снимками

### Недостающие провайдеры

- **OpenAI Embedder** — `text-embedding-3-large` (Phase 15.3 extension)
- **Local Vision (CPU)** — Qwen3-VL на CPU (сейчас только MLX)
- **Azure OpenAI** — preset для Azure API

---

## 📚 Читать в порядке

1. **[80_phase_overview.md](./80_phase_overview.md)** — эта статья
2. **[82_vision_audio_analysis.md](./82_vision_audio_analysis.md)** — Gemini Vision/Audio адаптеры
3. **[83_whisper_local_transcription.md](./83_whisper_local_transcription.md)** — Local Whisper
4. **[84_openai_llm_provider.md](./84_openai_llm_provider.md)** — OpenAI & Ollama LLM
5. **[85_configuration_factory.md](./85_configuration_factory.md)** — Configuration & Factory
6. **[86_optional_dependencies.md](./86_optional_dependencies.md)** — Optional Dependencies

---

**Статус:** ✅ Phase 15.0-15.5 Complete  
**Дата:** 2025-01-12  
**Автор:** AI Agent (Copilot)
