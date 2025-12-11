# 📦 Phase 15.5: Optional Dependencies

**Статус:** Planning  
**Зависимости:** Phase 15.1-15.4 (все адаптеры)  
**Цель:** Организовать зависимости так, чтобы ядро оставалось лёгким

---

## 🎯 Задачи

1. Разбить зависимости на extras в `pyproject.toml`
2. Обеспечить понятные ошибки при отсутствии зависимостей
3. Документировать варианты установки

---

## 📊 Текущее состояние

**Файл:** `pyproject.toml`

```toml
[project]
dependencies = [
    "peewee>=3.18.3",
    "sqlite-vec>=0.1.6",
    "google-generativeai>=0.8.5",  # ← Всегда ставится!
    "google-genai>=1.0.0",         # ← Всегда ставится!
    "numpy>=2.3.5",
    "pydantic-settings>=2.12.0",
    # ...
]

[project.optional-dependencies]
media = [
    "Pillow>=10.0.0",
    "pydub>=0.25.0",
    "imageio[pyav]>=2.35.0",
]
```

**Проблема:** Google SDK устанавливается всегда, даже если пользователь хочет только локальные модели.

---

## 🏗️ Целевая структура зависимостей

### Ядро (Core) — минимум

```toml
[project]
dependencies = [
    # Database
    "peewee>=3.18.3",
    "sqlite-vec>=0.1.6",
    
    # Core utilities
    "numpy>=2.3.5",
    "pydantic-settings>=2.12.0",
    "markdown-it-py>=3.0.0",
    "rich>=13.0.0",
    "typer[all]>=0.15.0",
]
```

**Размер:** ~50 MB (без AI моделей)

### Extras

```toml
[project.optional-dependencies]

# === Cloud Providers ===
google = [
    "google-generativeai>=0.8.5",
    "google-genai>=1.0.0",
]

openai = [
    "httpx>=0.27.0",
    # ИЛИ "openai>=1.0.0",
]

# === Local AI (Apple Silicon) ===
local-whisper-mlx = [
    "lightning-whisper-mlx>=0.1.0; platform_machine == 'arm64' and sys_platform == 'darwin'",
    "mlx-whisper>=0.1.0; platform_machine == 'arm64' and sys_platform == 'darwin'",
]

local-embeddings-mlx = [
    "mlx>=0.10.0; platform_machine == 'arm64' and sys_platform == 'darwin'",
    "mlx-embeddings>=0.1.0; platform_machine == 'arm64' and sys_platform == 'darwin'",
    "mlx-lm>=0.10.0; platform_machine == 'arm64' and sys_platform == 'darwin'",
]

# === Local AI (Cross-platform) ===
local-whisper = [
    "transformers>=4.40.0",
    "torch>=2.0.0",
    "librosa>=0.10.0",
    "soundfile>=0.12.0",
]

local-embeddings = [
    "sentence-transformers>=2.0.0",
    "torch>=2.0.0",
]

# === Media Processing ===
media = [
    "Pillow>=10.0.0",
    "pydub>=0.25.0",
    "imageio[pyav]>=2.35.0",
]

# === Bundles (convenience) ===
all-google = [
    "semantic-core[google,media]",
]

all-local-mlx = [
    "semantic-core[local-whisper-mlx,local-embeddings-mlx,media]",
]

all-local = [
    "semantic-core[local-whisper,local-embeddings,media]",
]

dev = [
    "pytest>=9.0.0",
    "pytest-cov>=4.0.0",
]
```

---

## 📝 Варианты установки

### 1. Только Google (текущее поведение)

```bash
pip install semantic-core[google]
```

**Что ставится:** Core + Google SDK + Media  
**Размер:** ~200 MB

### 2. Только локальные модели (Apple Silicon)

```bash
pip install semantic-core[all-local-mlx]
```

**Что ставится:** Core + MLX Whisper + MLX Embeddings + Media  
**Размер:** ~500 MB (без моделей)

### 3. Только локальные модели (Windows/Linux)

```bash
pip install semantic-core[all-local]
```

**Что ставится:** Core + PyTorch + Transformers + Media  
**Размер:** ~2 GB (PyTorch)

### 4. Гибрид (Google LLM + Local Whisper)

```bash
pip install semantic-core[google,local-whisper-mlx]
```

### 5. Минимальная установка (только индексация)

```bash
pip install semantic-core[google]
# Без media — только текстовые документы
```

---

## 🛡️ Graceful Import Errors

### Паттерн: Try-Import с понятным сообщением

```python
# semantic_core/infrastructure/local/whisper/__init__.py

_WHISPER_AVAILABLE = False
_IMPORT_ERROR = None

try:
    from .transcriber import WhisperTranscriber
    _WHISPER_AVAILABLE = True
except ImportError as e:
    _IMPORT_ERROR = str(e)
    WhisperTranscriber = None


def get_whisper_transcriber(**kwargs) -> "WhisperTranscriber":
    """Создаёт WhisperTranscriber с понятной ошибкой."""
    if not _WHISPER_AVAILABLE:
        platform_hint = (
            "pip install semantic-core[local-whisper-mlx]"
            if _is_apple_silicon()
            else "pip install semantic-core[local-whisper]"
        )
        raise ImportError(
            f"Whisper dependencies not installed.\n\n"
            f"Install with:\n  {platform_hint}\n\n"
            f"Original error: {_IMPORT_ERROR}"
        )
    return WhisperTranscriber(**kwargs)
```

### Паттерн: Lazy Import в Factory

```python
# core/factory.py

def create_embedder(config: SemanticConfig) -> BaseEmbedder:
    provider = config.defaults.embedding_provider
    
    if provider == "gemini":
        # Импорт только при использовании
        try:
            from semantic_core.infrastructure.gemini import GeminiEmbedder
        except ImportError:
            raise ImportError(
                "Google SDK not installed. "
                "Install with: pip install semantic-core[google]"
            )
        return GeminiEmbedder(...)
    
    elif provider == "local":
        try:
            from semantic_core.infrastructure.local import LocalEmbedder
        except ImportError:
            raise ImportError(
                "Local embeddings not installed. "
                "Install with: pip install semantic-core[local-embeddings-mlx]"
            )
        return LocalEmbedder(...)
```

---

## 📊 Диаграмма зависимостей

```
                    semantic-core (core)
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
      [google]        [local-*]       [openai]
           │               │               │
           ▼               ▼               ▼
    google-genai      mlx/torch        httpx
    generativeai      transformers     openai
           │               │               │
           └───────────────┼───────────────┘
                           │
                           ▼
                       [media]
                           │
                           ▼
                   Pillow, pydub, imageio
```

---

## 📖 Документация

### README.md секция

```markdown
## Installation

### Quick Start (Google Cloud)

pip install semantic-core[google]

### Privacy-First (Local Models)

# Apple Silicon (M1/M2/M3/M4)
pip install semantic-core[all-local-mlx]

# Windows/Linux with NVIDIA GPU
pip install semantic-core[all-local]

### Minimal (Text Only)

pip install semantic-core
# Requires manual adapter installation
```

---

## ⚠️ Миграция существующих пользователей

### Breaking Change

```diff
# До Phase 15
- pip install semantic-core

# После Phase 15
+ pip install semantic-core[google]  # Явно указываем провайдер
```

### Deprecation Warning

```python
# В __init__.py
import warnings

# Проверяем, установлен ли хотя бы один провайдер
if not _has_any_embedder():
    warnings.warn(
        "No embedding provider installed. "
        "Install with: pip install semantic-core[google] or semantic-core[local-embeddings-mlx]",
        UserWarning,
    )
```

---

## ✅ Критерии готовности

- [ ] `pyproject.toml` разбит на extras
- [ ] Ядро не зависит от AI SDK
- [ ] Понятные ошибки при отсутствии зависимостей
- [ ] Документация по вариантам установки
- [ ] Тесты проходят с каждым набором extras
- [ ] CI pipeline тестирует все комбинации

---

## 🔗 Связанные документы

- **Текущие зависимости:** `pyproject.toml`
- **Адаптеры:** [Phase 15.1](phase_15.1.md) (Whisper), [Phase 15.2](phase_15.2.md) (Embeddings)
- **Фабрика:** [Phase 15.4](phase_15.4.md) (ComponentFactory)
