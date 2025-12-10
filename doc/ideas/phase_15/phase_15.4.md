# ⚙️ Phase 15.4: Configuration & Factory

**Статус:** Planning  
**Зависимости:** Phase 15.0-15.3 (все адаптеры)  
**Цель:** Единая конфигурация и фабрика для сборки компонентов

---

## 🎯 Задачи

1. Расширить `SemanticConfig` секциями `[providers.*]`
2. Создать `ComponentFactory` для инстанцирования компонентов по конфигу
3. Обеспечить graceful degradation при отсутствии провайдера

---

## 📊 Текущее состояние конфига

**Файл:** `semantic_core/config.py` (lines 200-270)

```python
class SemanticConfig(BaseSettings):
    # Только Gemini!
    gemini_api_key: Optional[str] = None
    gemini_batch_key: Optional[str] = None
    embedding_model: str = "models/gemini-embedding-001"
    llm_model: str = "models/gemini-2.0-flash"
```

**Проблема:** Нет секций для других провайдеров.

---

## 🏗️ Целевая структура конфига

### TOML формат

```toml
# semantic.toml

# === Default Providers ===
[defaults]
embedding_provider = "gemini"      # или "local", "openai"
llm_provider = "gemini"            # или "openai", "ollama"
transcription_provider = "gemini"  # или "whisper"
vision_provider = "gemini"         # или "local" (future)

# === Google Gemini ===
[providers.gemini]
api_key = "${GEMINI_API_KEY}"      # Читаем из env
embedding_model = "models/gemini-embedding-001"
llm_model = "models/gemini-2.0-flash"
dimension = 768
max_tokens = 2048

# === OpenAI / OpenRouter ===
[providers.openai]
api_key = "${OPENAI_API_KEY}"
base_url = "https://api.openai.com/v1"  # Или OpenRouter URL
embedding_model = "text-embedding-3-small"
llm_model = "gpt-4o-mini"
dimension = 1536
max_tokens = 8191

# === Local (MLX / PyTorch) ===
[providers.local]
embedding_model = "qwen3-embedding"  # Ключ из LocalEmbedder.MODELS
whisper_model = "large-v3-turbo"
device = "auto"  # "mlx", "cuda", "mps", "cpu"

# === Ollama ===
[providers.ollama]
base_url = "http://localhost:11434/v1"
llm_model = "llama3.2"
```

---

## 📝 Pydantic модели

```python
# config.py

class ProviderConfig(BaseModel):
    """Базовая конфигурация провайдера."""
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class GeminiProviderConfig(ProviderConfig):
    """Конфигурация Google Gemini."""
    embedding_model: str = "models/gemini-embedding-001"
    llm_model: str = "models/gemini-2.0-flash"
    dimension: int = 768
    max_tokens: int = 2048


class OpenAIProviderConfig(ProviderConfig):
    """Конфигурация OpenAI-compatible API."""
    base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
    llm_model: str = "gpt-4o-mini"
    dimension: int = 1536
    max_tokens: int = 8191


class LocalProviderConfig(BaseModel):
    """Конфигурация локальных моделей."""
    embedding_model: str = "all-minilm"
    whisper_model: str = "large-v3-turbo"
    device: str = "auto"


class DefaultsConfig(BaseModel):
    """Выбор провайдеров по умолчанию."""
    embedding_provider: str = "gemini"
    llm_provider: str = "gemini"
    transcription_provider: str = "gemini"
    vision_provider: str = "gemini"


class SemanticConfig(BaseSettings):
    # ... существующие поля ...
    
    # Новые секции
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    
    providers: dict[str, ProviderConfig] = Field(default_factory=lambda: {
        "gemini": GeminiProviderConfig(),
        "openai": OpenAIProviderConfig(),
        "local": LocalProviderConfig(),
    })
```

---

## 🏭 ComponentFactory

**Файл:** `semantic_core/core/factory.py` (NEW)

```
┌─────────────────────────────────────────────────────────────┐
│                    ComponentFactory                          │
├─────────────────────────────────────────────────────────────┤
│ + create_embedder(config) → BaseEmbedder                    │
│ + create_llm(config) → BaseLLMProvider                      │
│ + create_transcriber(config) → ITranscriber                 │
│ + create_vision(config) → IVisionAnalyzer                   │
│ + create_semantic_core(config) → SemanticCore               │
└─────────────────────────────────────────────────────────────┘
```

### Логика фабрики

```python
class ComponentFactory:
    """Фабрика компонентов по конфигурации."""
    
    @staticmethod
    def create_embedder(config: SemanticConfig) -> BaseEmbedder:
        """Создаёт embedder по настройкам."""
        provider = config.defaults.embedding_provider
        provider_config = config.providers.get(provider)
        
        if provider == "gemini":
            from semantic_core.infrastructure.gemini import GeminiEmbedder
            return GeminiEmbedder(
                api_key=provider_config.api_key,
                model_name=provider_config.embedding_model,
                dimension=provider_config.dimension,
            )
        
        elif provider == "local":
            from semantic_core.infrastructure.local import LocalEmbedder
            return LocalEmbedder(
                model=provider_config.embedding_model,
                device=provider_config.device,
            )
        
        elif provider == "openai":
            from semantic_core.infrastructure.openai import OpenAIEmbedder
            return OpenAIEmbedder(
                api_key=provider_config.api_key,
                model=provider_config.embedding_model,
                base_url=provider_config.base_url,
            )
        
        raise ValueError(f"Unknown embedding provider: {provider}")
    
    @staticmethod
    def create_transcriber(config: SemanticConfig) -> Optional[ITranscriber]:
        """Создаёт transcriber по настройкам."""
        provider = config.defaults.transcription_provider
        
        if provider == "gemini":
            # Wrap GeminiAudioAnalyzer в ITranscriber адаптер
            from semantic_core.infrastructure.gemini import GeminiTranscriber
            return GeminiTranscriber(api_key=config.providers["gemini"].api_key)
        
        elif provider == "whisper":
            try:
                from semantic_core.infrastructure.local import WhisperTranscriber
                local_config = config.providers.get("local", LocalProviderConfig())
                return WhisperTranscriber(
                    model_size=local_config.whisper_model,
                    device=local_config.device,
                )
            except ImportError:
                raise ImportError(
                    "Whisper not installed. "
                    "Install with: pip install semantic-core[local-whisper]"
                )
        
        return None  # Транскрипция отключена
```

---

## 📊 Диаграмма последовательности

```
User                    ComponentFactory              Adapters
  │                            │                          │
  │  create_semantic_core()    │                          │
  │───────────────────────────►│                          │
  │                            │                          │
  │                            │  read config.defaults    │
  │                            │                          │
  │                            │  create_embedder()       │
  │                            │─────────────────────────►│
  │                            │  GeminiEmbedder          │
  │                            │◄─────────────────────────│
  │                            │                          │
  │                            │  create_transcriber()    │
  │                            │─────────────────────────►│
  │                            │  WhisperTranscriber      │
  │                            │◄─────────────────────────│
  │                            │                          │
  │                            │  create_llm()            │
  │                            │─────────────────────────►│
  │                            │  OpenAILLMProvider       │
  │                            │◄─────────────────────────│
  │                            │                          │
  │  SemanticCore (assembled)  │                          │
  │◄───────────────────────────│                          │
```

---

## 🎯 Convenience API

```python
# Самый простой способ создать SemanticCore
from semantic_core import create_core

# Автоматически читает semantic.toml и env
core = create_core()

# С override
core = create_core(
    embedding_provider="local",
    llm_provider="ollama",
)

# Полный контроль
from semantic_core.core.factory import ComponentFactory
from semantic_core.config import get_config

config = get_config(db_path="custom.db")
core = ComponentFactory.create_semantic_core(config)
```

---

## 🛡️ Graceful Degradation

```python
def create_transcriber(config: SemanticConfig) -> Optional[ITranscriber]:
    provider = config.defaults.transcription_provider
    
    if provider == "whisper":
        try:
            from semantic_core.infrastructure.local import WhisperTranscriber
            return WhisperTranscriber(...)
        except ImportError as e:
            logger.warning(
                "Whisper not available, falling back to Gemini",
                error=str(e),
            )
            # Fallback
            if config.providers.get("gemini", {}).get("api_key"):
                return GeminiTranscriber(...)
            
            logger.error("No transcription provider available")
            return None
```

---

## ✅ Критерии готовности

- [ ] `SemanticConfig` поддерживает `[providers.*]` секции
- [ ] `ComponentFactory` создаёт все компоненты по конфигу
- [ ] `create_core()` convenience function работает
- [ ] Graceful fallback при отсутствии провайдера
- [ ] Валидация конфига (Pydantic)
- [ ] Unit-тесты для фабрики
- [ ] Документация по конфигурации

---

## 🔗 Связанные документы

- **Текущий конфиг:** `semantic_core/config.py`
- **Адаптеры:** [Phase 15.1](phase_15.1.md), [Phase 15.2](phase_15.2.md), [Phase 15.3](phase_15.3.md)
