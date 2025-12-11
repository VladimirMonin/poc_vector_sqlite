# Phase 17.5 — Flask Multi-Provider Integration

> Рефакторинг Flask App для поддержки Local/Gemini/OpenAI embeddings через ComponentFactory

**Статус:** 📋 Planned  
**Зависимости:** Phase 17.1 (Local Embeddings Docs), Phase 15.4 (ComponentFactory)  
**Оценка:** 2-3 дня

---

## 🎯 Цель

Заменить hardcoded Gemini провайдеры в Flask App на ComponentFactory, чтобы поддерживать динамический выбор провайдера (Local/Gemini/OpenAI) через semantic.toml.

**Проблема:**

- `examples/flask_app/app/extensions.py` вручную создаёт `GeminiEmbedder`, `GeminiImageAnalyzer`, `GeminiAudioAnalyzer`
- Нет semantic.toml конфигурации
- Нет поддержки Local embeddings (Qwen3)
- Невозможно переключить провайдера без изменения кода

**Решение:**

- Использовать ComponentFactory для создания всех провайдеров
- Создать semantic.toml с настройками для Gemini и Local
- Добавить graceful degradation при ошибках инициализации
- Логировать выбранный провайдер и dimension при старте

---

## 📋 Задачи

### 1. Рефакторинг extensions.py

**Что делаем:**

- Удаляем все прямые импорты `GeminiEmbedder`, `GeminiImageAnalyzer`, etc.
- Заменяем на `ComponentFactory.create_embedder(config)`, `ComponentFactory.create_vision(config)`
- Добавляем try-except блоки с graceful degradation (если провайдер недоступен — работаем без него)
- Логируем выбранный provider и dimension при инициализации
- Проверяем dimension mismatch между embedder и БД

**Файлы:**

- `examples/flask_app/app/extensions.py` (строки ~95-133)

---

### 2. Создание semantic.toml

**Что делаем:**

- Создаём `examples/flask_app/semantic.toml` с секциями:
  - `[defaults]` — выбор провайдеров (embedding_provider, vision_provider, llm_provider)
  - `[providers.gemini]` — api_key, model_name, dimension=768
  - `[providers.local]` — embedding_model="qwen3-embedding", device="mps", dimension=1024
  - `[storage]` — db_path="instance/semantic.db"
  - `[processing]` — chunk_size, code_chunk_size

**Варианты конфигурации:**

- **Cloud Mode:** `embedding_provider = "gemini"` — для продакшена с API
- **Local Mode:** `embedding_provider = "local"` — для демо на macOS без интернета
- **Hybrid Mode:** embeddings локально, LLM через Gemini — экономия + качество

⚠️ **ВАЖНО:** При переключении провайдера нужно пересоздать БД (dimension change)

**Файлы:**

- `examples/flask_app/semantic.toml` (новый файл)

---

### 3. Обновление .env.example

**Что делаем:**

- Добавляем комментарии про `GEMINI_API_KEY` (для Cloud режима)
- Добавляем комментарии про Local режима (не требует env переменных)
- Добавляем опциональные overrides через env: `SEMANTIC_DEFAULTS__EMBEDDING_PROVIDER=local`
- Объясняем что semantic.toml — основной способ конфигурации

**Файлы:**

- `examples/flask_app/.env.example` (обновить)

---

### 4. Graceful Degradation

**Сценарии обработки ошибок:**

| Проблема | Что происходит | Решение |
|----------|----------------|---------|
| Нет GEMINI_API_KEY | Cloud mode не может запуститься | Fallback на Local (если macOS) или показать ошибку установки ключа |
| MPS недоступен | Intel Mac или Windows, MLX не работает | Fallback на CPU (медленно) + warning в логах |
| MLX не установлен | ImportError при создании LocalEmbedder | Показать ошибку "Install semantic-core[local]" |
| Dimension mismatch | БД создана с 768D, embedder возвращает 1024D | Показать ошибку + ссылка на migration guide |
| Vision не инициализировалась | Ошибка API или нет ключа | vision_analyzer = None, Flask работает без Vision |

**Подход:**

- Embedder — критичный компонент (без него Flask не запустится)
- Vision/Audio/Video — опциональные (graceful degradation, можно работать без них)
- При любой ошибке — читаемое сообщение в логах с эмодзи

---

## 📝 Чеклист

### Код

- [ ] **extensions.py:**
  - [ ] Заменить manual создание провайдеров на ComponentFactory
  - [ ] Добавить try-except блоки с graceful degradation
  - [ ] Добавить проверку dimension mismatch
  - [ ] Обновить логирование (показывать provider + dimension)

- [ ] **semantic.toml:**
  - [ ] Создать базовый конфиг (Gemini default)
  - [ ] Добавить комментарии про Local mode
  - [ ] Добавить примеры 3 режимов (Cloud, Local, Hybrid)

- [ ] **.env.example:**
  - [ ] Добавить GEMINI_API_KEY с комментариями
  - [ ] Добавить секцию про Local (не требует env)
  - [ ] Добавить optional overrides через SEMANTIC_*

### Документация

- [ ] **README.md:**
  - [ ] Секция "Provider Configuration" с примерами semantic.toml
  - [ ] Quick Start для Cloud и Local режимов
  - [ ] Ссылка на migration guide при dimension change

---

## 🧪 Тестирование

**Manual:**

- Запустить с Gemini (cloud) → проверить embedder=768D
- Запустить с Local (macOS) → проверить embedder=1024D
- Создать БД с Gemini → переключить на Local → проверить ошибку dimension mismatch
- Убрать GEMINI_API_KEY → проверить fallback или ошибку

**Unit:**

- `test_init_with_gemini()` — Flask запускается с Gemini
- `test_init_with_local()` — Flask запускается с Local
- `test_dimension_mismatch_error()` — ValueError при несовпадении dimension
- `test_graceful_degradation()` — Vision/Audio optional, работает без них

---

## 🎯 Результат

**Должно работать:**

- Flask App запускается с Gemini (cloud, 768D)
- Flask App запускается с Local Qwen3 (macOS, 1024D)
- Dimension mismatch показывает читаемую ошибку с ссылкой на guide
- MPS fallback на CPU с warning в логах
- Vision/Audio/Video опциональны (graceful degradation)

**Документация:**

- README с примерами semantic.toml для 3 режимов
- Troubleshooting секция для типичных ошибок

---

## 📚 Связанные фазы

- **Phase 17.1:** Документация Local Embeddings (готова)
- **Phase 15.4:** ComponentFactory (реализован)
- **Phase 17.6:** Settings UI (следующая)
- **Phase 17.7:** Testing & Demo (финал)

---

## ⚠️ Ограничения

- VideoAnalyzer пока не в ComponentFactory (TODO для Phase 18)
- OpenAI embedder не реализован (будет в Phase 18)
- Dimension migration требует ручного пересоздания БД
- Windows/Linux требуют кастомный embedder (sentence-transformers)

**Текущее состояние (Hardcoded):**

```python
# examples/flask_app/app/extensions.py lines 95-133
try:
    api_key = config.require_api_key()
    embedder = GeminiEmbedder(  # ← Hardcoded!
        api_key=api_key,
        model_name=config.embedding_model,
        dimension=config.embedding_dimension,
    )
    
    image_analyzer = GeminiImageAnalyzer(  # ← Hardcoded!
        api_key=api_key,
        max_output_tokens=config.max_output_tokens,
        output_language=config.output_language,
    )
    
    audio_analyzer = GeminiAudioAnalyzer(...)  # ← Hardcoded!
    video_analyzer = GeminiVideoAnalyzer(...)  # ← Hardcoded!
```

**Целевое состояние (ComponentFactory):**

```python
# examples/flask_app/app/extensions.py (новый код)
from semantic_core.core.factory import ComponentFactory

# Embedder (Gemini/Local/OpenAI через конфиг)
embedder = ComponentFactory.create_embedder(config)
logger.info(f"🤖 Embedder: {config.defaults.embedding_provider} / {embedder.dimension}D")

# Vision (Gemini/Local)
try:
    vision_analyzer = ComponentFactory.create_vision(config)
    logger.info(f"🖼️ Vision: {config.defaults.vision_provider}")
except Exception as e:
    vision_analyzer = None
    logger.warning(f"⚠️ Vision не инициализирован: {e}")

# Transcription (Gemini Audio/Local Whisper)
try:
    transcriber = ComponentFactory.create_transcriber(config)
    logger.info(f"🎵 Transcriber: {config.defaults.transcription_provider}")
except Exception as e:
    transcriber = None
    logger.warning(f"⚠️ Transcriber не инициализирован: {e}")

# Video (пока специальная обработка, TODO: в ComponentFactory)
video_analyzer = None
if vision_analyzer and transcriber:
    from semantic_core.infrastructure.gemini.video_analyzer import GeminiVideoAnalyzer
    video_analyzer = GeminiVideoAnalyzer(...)
```

**Изменения:**

- ❌ Удалить: `from semantic_core.infrastructure.gemini import Gemini*`
- ✅ Добавить: `from semantic_core.core.factory import ComponentFactory`
- ✅ Добавить: Try-except с graceful degradation
- ✅ Добавить: Логирование provider + dimension

---

### 2. Создание semantic.toml для Flask App

**Файл:** `examples/flask_app/semantic.toml`

**Содержание (базовая конфигурация):**

```toml
# ========================================
# SemanticCore Configuration для Flask App
# ========================================

[defaults]
# Provider selection
embedding_provider = "gemini"    # "gemini", "local", "openai"
vision_provider = "gemini"       # "gemini", "local"
llm_provider = "gemini"          # "gemini", "openai", "ollama"
transcription_provider = "none"  # "gemini", "whisper", "none"

# ========================================
# Gemini Provider (Cloud)
# ========================================
[providers.gemini]
api_key = "${GEMINI_API_KEY}"
embedding_model = "text-embedding-004"
dimension = 768
llm_model = "gemini-2.0-flash-exp"

# ========================================
# Local Provider (macOS Apple Silicon)
# ========================================
[providers.local]
embedding_model = "qwen3-embedding"  # 1024D, multilingual, MRL
device = "mps"                       # "mps" (Metal) or "cpu"
# dimension будет определена автоматически (1024 для qwen3)

# ========================================
# Storage
# ========================================
[storage]
db_path = "instance/semantic.db"

# ========================================
# Processing
# ========================================
[processing]
chunk_size = 1000
code_chunk_size = 1500

# ========================================
# Multimodal
# ========================================
[multimodal]
output_language = "ru"
max_output_tokens = 2048
```

**Варианты конфигурации:**

```toml
# === Вариант 1: Cloud Gemini (Production) ===
[defaults]
embedding_provider = "gemini"
vision_provider = "gemini"

[providers.gemini]
api_key = "${GEMINI_API_KEY}"
dimension = 768

# === Вариант 2: Local Qwen3 (Demo, Offline) ===
[defaults]
embedding_provider = "local"
vision_provider = "local"

[providers.local]
embedding_model = "qwen3-embedding"  # 1024D
device = "mps"

# ⚠️ ВАЖНО: При переключении провайдера пересоздать БД!
# rm instance/semantic.db
# flask ingest ./docs

# === Вариант 3: Hybrid (экономия) ===
[defaults]
embedding_provider = "local"   # Бесплатно, оффлайн
llm_provider = "gemini"        # Качество для RAG ответов

[providers.local]
embedding_model = "qwen3-embedding"

[providers.gemini]
api_key = "${GEMINI_API_KEY}"
llm_model = "gemini-2.0-flash-exp"
```

---

### 3. Обновление .env.example

**Файл:** `examples/flask_app/.env.example`

```bash
# ========================================
# Flask App Settings
# ========================================
FLASK_SECRET_KEY=dev-secret-key-change-in-production
FLASK_DEBUG=true
FLASK_HOST=127.0.0.1
FLASK_PORT=5000

# ========================================
# Gemini API (для Cloud Provider)
# ========================================
GEMINI_API_KEY=your-gemini-api-key-here

# ========================================
# OpenAI API (опционально)
# ========================================
# OPENAI_API_KEY=your-openai-api-key-here

# ========================================
# Local Provider (macOS только)
# ========================================
# Нет дополнительных env переменных
# Настройки в semantic.toml

# ========================================
# Semantic Config Override (опционально)
# ========================================
# SEMANTIC_DEFAULTS__EMBEDDING_PROVIDER=local
# SEMANTIC_DB_PATH=instance/semantic.db
```

---

### 4. Обработка ошибок и Graceful Degradation

**Сценарии:**

| Ошибка | Причина | Решение |
|--------|---------|---------|
| `GEMINI_API_KEY` отсутствует | Не настроен env | Fallback на Local (если macOS) или показать ошибку |
| MPS недоступен | Intel Mac или Windows | Fallback на CPU (медленно) с предупреждением |
| LocalEmbedder import failed | MLX не установлен | Показать ошибку "Install semantic-core[local]" |
| Dimension mismatch | БД 768D, embedder 1024D | Показать ошибку с ссылкой на гайд миграции |

**Реализация:**

```python
# extensions.py
def init_semantic_core(app: Flask) -> None:
    logger = get_logger("flask_app.extensions")
    config = get_config()
    
    # Database
    db = init_peewee_database(config.db_path, config.embedding_dimension)
    
    # Embedder через ComponentFactory
    embedder = None
    try:
        embedder = ComponentFactory.create_embedder(config)
        logger.info(f"✅ Embedder: {config.defaults.embedding_provider} ({embedder.dimension}D)")
        
        # Проверка dimension mismatch
        if embedder.dimension != config.embedding_dimension:
            logger.error(
                f"🔴 Dimension mismatch! "
                f"Embedder={embedder.dimension}D, DB={config.embedding_dimension}D. "
                f"См. docs/guides/core/local-embeddings.md#migration"
            )
            raise ValueError("Dimension mismatch")
    
    except ImportError as e:
        logger.error(f"🔴 LocalEmbedder не установлен: {e}")
        logger.info(f"💡 Install: pip install 'semantic-core[local]'")
        embedder = None
    
    except RuntimeError as e:
        if "MPS" in str(e):
            logger.warning(f"⚠️ MPS недоступен, fallback на CPU")
            # Retry с CPU
            config.providers_local.device = "cpu"
            embedder = ComponentFactory.create_embedder(config)
        else:
            raise
    
    # Создать SemanticCore только если embedder успешно создан
    if embedder:
        core = SemanticCore(embedder=embedder, store=store, ...)
    else:
        core = None
        logger.warning("⚠️ SemanticCore отключен (нет embedder)")
    
    app.extensions["semantic_core"] = core
```

---

## 📝 Implementation Checklist

### Code Changes

- [ ] **extensions.py:**
  - [ ] Заменить `GeminiEmbedder` на `ComponentFactory.create_embedder()`
  - [ ] Заменить `GeminiImageAnalyzer` на `ComponentFactory.create_vision()`
  - [ ] Добавить try-except с graceful degradation
  - [ ] Добавить проверку dimension mismatch
  - [ ] Обновить логирование (показывать provider)

- [ ] **config.py:**
  - [ ] Проверить что SemanticConfig загружается через get_config()
  - [ ] Убедиться что `embedding_dimension` синхронизирован с embedder

- [ ] **semantic.toml:**
  - [ ] Создать базовый конфиг с Gemini (default)
  - [ ] Добавить комментарии для Local варианта
  - [ ] Добавить комментарии про dimension mismatch

- [ ] **.env.example:**
  - [ ] Обновить с новыми env переменными
  - [ ] Добавить секцию про Local provider

### Documentation

- [ ] **README.md:**
  - [ ] Добавить секцию "Provider Configuration"
  - [ ] Добавить примеры запуска (Gemini vs Local)
  - [ ] Добавить ссылку на docs/guides/core/local-embeddings.md

- [ ] **Новый файл: PROVIDERS.md**
  - [ ] Описать все поддерживаемые провайдеры
  - [ ] Таблица сравнения (качество, скорость, hardware)
  - [ ] Troubleshooting секция

---

## 🧪 Testing

### Manual Testing

```bash
# Test 1: Gemini (Cloud)
cd examples/flask_app
echo '[defaults]
embedding_provider = "gemini"

[providers.gemini]
api_key = "${GEMINI_API_KEY}"
dimension = 768' > semantic.toml

GEMINI_API_KEY=your-key python run.py
# → Должен запуститься с Gemini, 768D

# Test 2: Local (macOS)
echo '[defaults]
embedding_provider = "local"

[providers.local]
embedding_model = "qwen3-embedding"' > semantic.toml

python run.py
# → Должен запуститься с Qwen3, 1024D

# Test 3: Dimension Mismatch (Error)
# БД с 768D, embedder с 1024D
rm instance/semantic.db
# Создать БД с 768D через Gemini
GEMINI_API_KEY=key python -c "from app import create_app; app = create_app()"

# Переключить на Local 1024D
echo '[defaults]
embedding_provider = "local"' > semantic.toml

python run.py
# → Должна быть ошибка "Dimension mismatch"
```

### Unit Tests

```python
# tests/test_extensions.py
import pytest
from app import create_app

def test_init_with_gemini():
    """Инициализация с Gemini provider."""
    app = create_app()
    
    core = app.extensions['semantic_core']
    assert core is not None
    assert core.embedder.dimension == 768

def test_init_with_local():
    """Инициализация с Local provider."""
    app = create_app(config_overrides={
        "defaults__embedding_provider": "local",
        "providers_local__embedding_model": "qwen3-embedding"
    })
    
    core = app.extensions['semantic_core']
    assert core is not None
    assert core.embedder.dimension == 1024

def test_dimension_mismatch_error():
    """Должна быть ошибка при dimension mismatch."""
    # БД уже создана с 768D
    with pytest.raises(ValueError, match="Dimension mismatch"):
        app = create_app(config_overrides={
            "defaults__embedding_provider": "local"  # 1024D
        })
```

---

## 🎯 Success Criteria

- ✅ Flask App запускается с `embedding_provider = "gemini"`
- ✅ Flask App запускается с `embedding_provider = "local"` на macOS
- ✅ Показывается читаемая ошибка при dimension mismatch
- ✅ Graceful degradation если MPS недоступен (CPU fallback)
- ✅ Логи показывают выбранный provider и dimension
- ✅ README обновлён с примерами конфигурации

---

## 📚 Related

- **Phase 17.1:** Local Embeddings Documentation
- **Phase 15.4:** ComponentFactory Implementation
- **Phase 17.6:** Settings UI для выбора провайдера
- **Phase 17.7:** Testing & Demo Stand

---

## 🚧 Known Limitations

1. **VideoAnalyzer** пока не в ComponentFactory (специальная обработка)
2. **OpenAI provider** требует Phase 15.5 (OpenAI Embedder)
3. **Dimension migration** требует ручного пересоздания БД
4. **Windows/Linux** требует кастомный embedder (sentence-transformers)

---

## 💡 Future Enhancements (Out of Scope)

- [ ] Автоматическая миграция БД при dimension change
- [ ] UI для выбора провайдера (→ Phase 17.6)
- [ ] Prometheus metrics для provider performance
- [ ] A/B testing разных провайдеров
