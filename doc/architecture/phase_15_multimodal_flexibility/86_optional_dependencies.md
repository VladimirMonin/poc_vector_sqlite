# 86. Опциональные зависимости и изящная обработка ошибок

> **Phase 15.5**: Легковесное ядро с опциональными провайдерами  
> **Коммиты**: `e7dbb8a`, `75321f2`

---

## 🎯 Проблема

После Phase 15.0–15.4 мы получили **гибкую архитектуру с поддержкой 5 провайдеров** (Google, OpenAI, Local Embeddings MLX/CPU, Local Whisper MLX/CPU). Но:

❌ **Вынужденная установка всех зависимостей**  
При `pip install semantic-core` устанавливается Google SDK, даже если пользователь хочет только OpenAI или локальные модели.

❌ **Конфликты зависимостей**  
`torch` (для локальных моделей) и `mlx` (для Apple Silicon) конфликтуют с версиями в Google SDK.

❌ **Неинформативные ошибки**  
При отсутствии зависимости пользователь получает `ModuleNotFoundError: No module named 'openai'` без подсказки как это исправить.

---

## ✅ Решение

**Концепция**: Core зависимости — минимальны. Провайдеры — опциональны.

### Архитектура зависимостей

```
[core]                     <- Всегда устанавливается
├── peewee
├── sqlite-vec
├── numpy
├── pydantic-settings
├── markdown-it-py
└── rich, typer

[google]                   <- Опционально
├── google-generativeai
└── google-genai

[openai]                   <- Опционально
├── openai
└── tiktoken

[local-embeddings-mlx]     <- Опционально (Apple Silicon)
├── mlx
└── mlx-embeddings

[local-whisper-mlx]        <- Опционально (Apple Silicon)
├── mlx
└── mlx-whisper

[local-embeddings]         <- Опционально (CPU/GPU)
├── sentence-transformers
└── torch

[local-whisper]            <- Опционально (CPU/GPU)
├── transformers
└── torch

[media]                    <- Опционально
├── Pillow
├── pydub
└── imageio

[all-google]               <- Бандл: google + media
[all-local-mlx]            <- Бандл: local-embeddings-mlx + local-whisper-mlx + media
[all-local]                <- Бандл: local-embeddings + local-whisper + media
[all]                      <- Бандл: всё
```

---

## 🔧 Реализация

### 1. Dependency Helper (`semantic_core/utils/dependencies.py`)

**Функции проверки доступности:**

```python
def check_google_available() -> tuple[bool, Optional[str]]:
    """Проверяет доступность Google SDK."""
    try:
        import google.generativeai
        import google.genai
        return True, None
    except ImportError as e:
        return False, str(e)
```

Аналогично: `check_openai_available()`, `check_local_embeddings_available()`, `check_local_whisper_available()`, `check_media_available()`.

**Функция требования зависимости с подсказкой:**

```python
def require_provider(provider: str, feature: str) -> None:
    """Требует установки провайдера, иначе выбрасывает ImportError с hint."""
    is_available, error = {
        "google": check_google_available(),
        "openai": check_openai_available(),
        # ...
    }[provider]
    
    if not is_available:
        hint = get_install_hint(provider)
        raise ImportError(
            f"{provider.title()} dependencies not installed for {feature}.\n\n"
            f"{hint}\n\n"
            f"Original error: {error}"
        )
```

**Функция подсказки установки:**

```python
def get_install_hint(provider: str) -> str:
    """Возвращает команду установки для провайдера."""
    hints = {
        "google": "pip install poc-vector-sqlite[google]",
        "openai": "pip install poc-vector-sqlite[openai]",
        "local_embeddings": (
            "pip install poc-vector-sqlite[local-embeddings-mlx]"
            if _is_apple_silicon()
            else "pip install poc-vector-sqlite[local-embeddings]"
        ),
        # ...
    }
    return hints.get(provider, f"pip install poc-vector-sqlite[{provider}]")
```

---

### 2. Graceful Errors в ComponentFactory

**До (Phase 15.4):**

```python
def create_embedder(self, config: SemanticConfig) -> BaseEmbedder:
    if config.embedder_type == "google":
        try:
            from semantic_core.infrastructure.gemini import GeminiEmbedder
            return GeminiEmbedder(...)
        except ImportError:
            raise ImportError("Google SDK not installed")  # Нет подсказки!
```

**После (Phase 15.5):**

```python
from semantic_core.utils.dependencies import require_provider

def create_embedder(self, config: SemanticConfig) -> BaseEmbedder:
    if config.embedder_type == "google":
        require_provider("google", "Google Gemini embeddings")
        from semantic_core.infrastructure.gemini import GeminiEmbedder
        return GeminiEmbedder(...)
```

Теперь при отсутствии Google SDK пользователь видит:

```
ImportError: Google dependencies not installed for Google Gemini embeddings.

Install with:
  pip install poc-vector-sqlite[google]

Original error: No module named 'google.generativeai'
```

---

### 3. CLI Warnings

**В `semantic_core/cli/app.py`:**

```python
from semantic_core.utils.dependencies import get_missing_providers

@app.callback()
def main_callback(..., verbose: bool):
    # Проверка при старте CLI
    missing = get_missing_providers()
    if missing and ctx.invoked_subcommand not in ("init", "config", "doctor", None):
        if verbose or log_level:
            typer.secho(
                f"⚠️  Optional dependencies not installed: {', '.join(missing)}",
                fg=typer.colors.YELLOW,
                err=True,
            )
            typer.secho(
                f"💡 Run 'semantic doctor' for installation hints.",
                fg=typer.colors.BLUE,
                err=True,
            )
```

**Пример вывода:**

```bash
$ semantic search "query" --verbose
⚠️  Optional dependencies not installed: openai, local_embeddings
💡 Run 'semantic doctor' for installation hints.
```

---

### 4. Doctor Command Enhancement

**Секция "Providers" в `semantic doctor --verbose`:**

```
Providers:
  ✅ Google: installed
  ⚠️ Openai: not installed
  ⚠️ Local Embeddings: not installed
  ⚠️ Local Whisper: not installed
  ✅ Media: installed

📦 Установка дополнительных провайдеров:

   ⚠️ Openai:
      pip install poc-vector-sqlite[openai]

   ⚠️ Local Embeddings:
      pip install poc-vector-sqlite[local-embeddings-mlx]  # Apple Silicon
      pip install poc-vector-sqlite[local-embeddings]       # CPU/GPU
```

---

## 📦 Структура pyproject.toml

```toml
[tool.poetry.dependencies]
python = "^3.10"
# Core (всегда)
peewee = ">=3.18.3,<4.0.0"
sqlite-vec = ">=0.1.6,<0.2.0"
numpy = ">=2.3.5,<3.0.0"
pydantic-settings = ">=2.12.0,<3.0.0"
markdown-it-py = ">=3.0.0,<4.0.0"
audioop-lts = ">=0.2.2,<0.3.0"
rich = ">=13.0.0,<14.0.0"
typer = {version = ">=0.15.0,<1.0.0", extras = ["all"]}

[tool.poetry.extras]
google = ["google-generativeai", "google-genai"]
openai = ["openai", "tiktoken"]
media = ["Pillow", "pydub", "imageio"]
local-embeddings-mlx = ["mlx", "mlx-embeddings", "mlx-lm"]
local-whisper-mlx = ["mlx", "mlx-whisper"]
local-embeddings = ["sentence-transformers", "torch"]
local-whisper = ["transformers", "torch"]

all-google = ["google-generativeai", "google-genai", "Pillow", "pydub", "imageio"]
all-local-mlx = ["mlx", "mlx-embeddings", "mlx-whisper", "Pillow", "pydub", "imageio"]
all-local = ["sentence-transformers", "transformers", "torch", "Pillow", "pydub", "imageio"]
all = [
    "google-generativeai", "google-genai",
    "openai", "tiktoken",
    "mlx", "mlx-embeddings", "mlx-whisper",
    "sentence-transformers", "transformers", "torch",
    "Pillow", "pydub", "imageio"
]
```

---

## 🧪 Тестирование

**Dependency Helpers (14 тестов):**

```python
def test_check_google_available_when_installed():
    """Google SDK установлен → (True, None)."""
    is_available, error = check_google_available()
    assert is_available is True
    assert error is None

def test_require_provider_not_installed():
    """Провайдер не установлен → ImportError с hint."""
    with patch("check_openai_available", return_value=(False, "No module...")):
        with pytest.raises(ImportError, match="dependencies not installed"):
            require_provider("openai", "Test OpenAI feature")

def test_get_install_hint_local_embeddings_mlx():
    """На Apple Silicon → рекомендует MLX."""
    with patch("_is_apple_silicon", return_value=True):
        hint = get_install_hint("local_embeddings")
        assert "local-embeddings-mlx" in hint
```

**Doctor Providers (3 теста):**

```python
def test_shows_available_providers():
    """Doctor показывает статус провайдеров."""
    result = runner.invoke(app, ["doctor"])
    assert "Providers:" in result.stdout
    assert "Google: installed" in result.stdout

def test_shows_install_hints_in_verbose_mode():
    """Doctor --verbose показывает install hints."""
    result = runner.invoke(app, ["doctor", "--verbose"])
    assert "📦 Установка дополнительных провайдеров:" in result.stdout
    assert "pip install" in result.stdout
```

---

## 📊 Результаты

| Метрика | До (Phase 15.4) | После (Phase 15.5) |
|---------|----------------|-------------------|
| **Core зависимости** | 15+ пакетов | 8 пакетов |
| **Размер установки (min)** | ~200 MB | ~50 MB |
| **Поддержка провайдеров** | Google (обязательно) | Google, OpenAI, Local (опционально) |
| **Ошибки при отсутствии зависимости** | `ModuleNotFoundError` | `ImportError` с hint |
| **CLI предупреждения** | ❌ | ✅ `--verbose` |
| **Doctor диагностика** | ❌ | ✅ Секция Providers |

---

## 🎓 Выводы

**Phase 15.5 достигнуты цели:**

1. ✅ **Легковесное ядро** — core зависимости минимальны
2. ✅ **Гибкая установка** — 11 extras для разных сценариев
3. ✅ **Изящные ошибки** — `require_provider()` с подсказками
4. ✅ **CLI предупреждения** — `--verbose` показывает missing providers
5. ✅ **Doctor диагностика** — секция Providers с install hints
6. ✅ **Тесты** — 17 unit-тестов (dependencies + doctor)

**Следующие шаги (Phase 15.6+):**

- **Multi-Provider RAG** — переключение провайдеров в `semantic chat`
- **Provider Benchmarks** — сравнение качества/скорости/стоимости
- **Auto-Fallback** — автоматический откат на локальные модели при ошибках API

---

**Коммиты:**

- `e7dbb8a` — Реструктуризация зависимостей, dependency helpers, unit-тесты
- `75321f2` — CLI warnings, Doctor enhancement, тесты для doctor providers
