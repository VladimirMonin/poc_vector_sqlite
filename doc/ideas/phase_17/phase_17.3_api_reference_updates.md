# Phase 17.3: API Reference Updates

> Актуализация справочной документации (LocalEmbedder, ComponentFactory, interfaces)

---

## 📦 Статус

- **Фаза:** 17.3
- **Зависит от:** Phase 17.1 (Local Embeddings Docs)
- **Блокирует:** Ничего (standalone)
- **Приоритет:** ⚠️ Важный
- **Оценка:** 2-3 дня

---

## 🎯 Проблема

**Текущая ситуация:**

`docs/reference/interfaces.md` содержит **поверхностные таблицы** без деталей API:

```markdown
| Метод | Сигнатура | Описание |
|-------|-----------|----------|
| `embed_documents` | `(texts: list[str]) → list[np.ndarray]` | Векторизация документов |
```

**Чего не хватает:**

1. ❌ **Параметры конструктора** — как создавать экземпляры
2. ❌ **Properties** — `dimension`, `max_tokens`, `model_name`
3. ❌ **Raises** — какие исключения и когда
4. ❌ **Примеры кода** — как использовать на практике
5. ❌ **ComponentFactory** — вообще не задокументирован

**Последствия:**

- Пользователи не знают как создать `LocalEmbedder` вручную
- Невозможно понять signature без чтения кода
- Нет документации по ComponentFactory (критичный компонент Phase 15)

---

## 💡 Решение

Создать **детальный API Reference** с полной сигнатурой методов.

### 1. Обновить `docs/reference/interfaces.md`

**Текущая структура** (поверхностная):

```markdown
## BaseEmbedder

| Метод | Сигнатура | Описание |
|-------|-----------|----------|
| embed_documents | ... | ... |
```

**Новая структура** (детальная):

```markdown
## BaseEmbedder

### Методы

#### `embed_documents(texts: list[str]) → list[np.ndarray]`

**Назначение:** Генерирует эмбеддинги для списка документов.

**Параметры:**
- `texts` (list[str]): Список текстов для векторизации. Не должен быть пустым.

**Возвращает:**
- list[np.ndarray]: Список numpy массивов, каждый размерности `dimension`.

**Raises:**
- `ValueError`: Если `texts` пустой список.
- `RuntimeError`: Если генерация эмбеддингов не удалась (API ошибка, out of memory).

**Пример:**
```python
embedder = GeminiEmbedder(api_key="...", model="text-embedding-004")
vectors = embedder.embed_documents(["doc1", "doc2", "doc3"])
assert len(vectors) == 3
assert vectors[0].shape == (768,)
```

#### `embed_query(text: str) → np.ndarray`

**Назначение:** Генерирует эмбеддинг для поискового запроса.

**Параметры:**
- `text` (str): Текст запроса. Не должен быть пустым.

**Возвращает:**
- np.ndarray: Numpy массив размерности `dimension`.

**Raises:**
- `ValueError`: Если `text` пустая строка.
- `RuntimeError`: Если генерация эмбеддинга не удалась.

**Note:** Некоторые модели используют разные task_type для query vs documents (Cohere, BGE).

**Пример:**
```python
query_vector = embedder.embed_query("search query")
assert query_vector.shape == (768,)
```

### Properties

#### `dimension: int` (property, read-only)

Размерность выходного вектора.

**Пример:**
```python
assert embedder.dimension == 768  # Gemini text-embedding-004
```

#### `max_tokens: int` (property, read-only) [optional]

Максимальное количество токенов на вход (если применимо).

**Пример:**
```python
assert embedder.max_tokens == 8192  # Qwen3-Embedding
```

---

### Реализации

#### GeminiEmbedder

**Import:**
```python
from semantic_core.infrastructure.gemini.embedder import GeminiEmbedder
```

**Конструктор:**
```python
GeminiEmbedder(
    api_key: str,
    model_name: str = "text-embedding-004",
    dimension: int = 768
)
```

**Параметры:**
- `api_key`: Google AI API ключ.
- `model_name`: Модель (text-embedding-004, gemini-embedding-001).
- `dimension`: Размерность через MRL (768, 1536, 3072 для embedding-001).

**Пример:**
```python
embedder = GeminiEmbedder(
    api_key=os.getenv("GEMINI_API_KEY"),
    model_name="text-embedding-004",
    dimension=768
)
```

#### LocalEmbedder

**Import:**
```python
from semantic_core.infrastructure.local.embeddings import LocalEmbedder
```

**Конструктор:**
```python
LocalEmbedder(
    model: str = "all-minilm",
    device: Optional[str] = None,
    max_tokens_override: Optional[int] = None
)
```

**Параметры:**
- `model`: Preset ключ (`all-minilm`, `qwen3-embedding`, `bge-small`) или HuggingFace model ID.
- `device`: Устройство (`mps`, `cuda`, `cpu`). Auto-detect если None.
- `max_tokens_override`: Переопределить max_tokens для кастомных моделей.

**Raises:**
- `ValueError`: Если модель неизвестна.
- `ImportError`: Если MLX/sentence-transformers не установлены.

**Пример (preset):**
```python
embedder = LocalEmbedder(model="qwen3-embedding", device="mps")
assert embedder.dimension == 1024
assert embedder.max_tokens == 8192
```

**Пример (custom model):**
```python
embedder = LocalEmbedder(
    model="sentence-transformers/all-mpnet-base-v2",
    max_tokens_override=512
)
```
```

---

### 2. Создать `docs/reference/component-factory.md`

**Новый документ** для ComponentFactory API.

```markdown
# ComponentFactory API Reference

## Обзор

`ComponentFactory` — фабрика для создания SemanticCore компонентов по конфигурации.

**Import:**
```python
from semantic_core.core.factory import ComponentFactory
from semantic_core import get_config
```

---

## Методы

### `create_embedder(config: SemanticConfig) → BaseEmbedder`

Создаёт embedder на основе `config.defaults.embedding_provider`.

**Параметры:**
- `config` (SemanticConfig): Конфигурация с настройками провайдера.

**Возвращает:**
- BaseEmbedder: Экземпляр GeminiEmbedder, LocalEmbedder или OpenAIEmbedder.

**Raises:**
- `ValueError`: Если провайдер неизвестен.
- `ImportError`: Если зависимости провайдера не установлены.

**Поддерживаемые провайдеры:**
- `gemini` → `GeminiEmbedder`
- `local` → `LocalEmbedder`
- `openai` → NotImplementedError (Phase 18+)

**Пример:**
```python
config = get_config()  # Загружает semantic.toml
embedder = ComponentFactory.create_embedder(config)

# Если defaults.embedding_provider = "local"
assert isinstance(embedder, LocalEmbedder)
```

---

### `create_llm(config: SemanticConfig) → BaseLLMProvider`

Создаёт LLM provider на основе `config.defaults.llm_provider`.

**Параметры:**
- `config` (SemanticConfig): Конфигурация с настройками провайдера.

**Возвращает:**
- BaseLLMProvider: Экземпляр GeminiLLMProvider, OpenAILLMProvider или OllamaLLMProvider.

**Raises:**
- `ValueError`: Если провайдер неизвестен.
- `ImportError`: Если зависимости провайдера не установлены.

**Поддерживаемые провайдеры:**
- `gemini` → `GeminiLLMProvider`
- `openai` → `OpenAILLMProvider` (через OpenAI SDK)
- `ollama` → `OpenAILLMProvider` (с preset OLLAMA)

**Пример:**
```python
llm = ComponentFactory.create_llm(config)

# Если defaults.llm_provider = "ollama"
response = llm.generate(prompt="Explain embeddings")
print(response.text)
```

---

### `create_transcriber(config: SemanticConfig) → Optional[ITranscriber]`

Создаёт transcriber (если включён) на основе `config.defaults.transcription_provider`.

**Параметры:**
- `config` (SemanticConfig): Конфигурация с настройками провайдера.

**Возвращает:**
- ITranscriber | None: Экземпляр transcriber или None если `media_enabled=False`.

**Raises:**
- `ValueError`: Если провайдер неизвестен.
- `ImportError`: Если зависимости провайдера не установлены.

**Поддерживаемые провайдеры:**
- `gemini` → `GeminiAudioAnalyzer`
- `whisper` → `WhisperTranscriber` (MLX или openai-whisper)
- `none` → None

**Пример:**
```python
transcriber = ComponentFactory.create_transcriber(config)

if transcriber:
    result = transcriber.transcribe("audio.mp3")
    print(result.text)
```

---

### `create_vision_analyzer(config: SemanticConfig) → Optional[IVisionAnalyzer]`

Создаёт vision analyzer (если включён) на основе `config.defaults.vision_provider`.

**Параметры:**
- `config` (SemanticConfig): Конфигурация с настройками провайдера.

**Возвращает:**
- IVisionAnalyzer | None: Экземпляр vision analyzer или None если `media_enabled=False`.

**Raises:**
- `ValueError`: Если провайдер неизвестен.
- `ImportError`: Если зависимости провайдера не установлены.

**Поддерживаемые провайдеры:**
- `gemini` → `GeminiImageAnalyzer`, `GeminiVideoAnalyzer`
- `local` → `LocalVisionAnalyzer` (Qwen3-VL через MLX)
- `none` → None

**Пример:**
```python
vision = ComponentFactory.create_vision_analyzer(config)

if vision:
    result = vision.analyze("image.jpg", prompt="Describe this image")
    print(result.description)
```

---

### `create_semantic_core(config: SemanticConfig) → SemanticCore`

Создаёт полностью собранный SemanticCore со всеми компонентами.

**Параметры:**
- `config` (SemanticConfig): Конфигурация системы.

**Возвращает:**
- SemanticCore: Готовый к использованию экземпляр.

**Raises:**
- `ValueError`: Если какой-то обязательный компонент не может быть создан.
- `ImportError`: Если зависимости не установлены.

**Пример:**
```python
from semantic_core.core.factory import create_core

# Convenience функция (обёртка над create_semantic_core)
core = create_core()

# Эквивалентно:
config = get_config()
core = ComponentFactory.create_semantic_core(config)

# Использование
doc = core.ingest("example.md")
results = core.search("query")
```

---

## Convenience функция

### `create_core(...) → SemanticCore`

**Сигнатура:**
```python
def create_core(
    config_path: Optional[Path] = None,
    embedding_provider: Optional[str] = None,
    llm_provider: Optional[str] = None,
    **overrides
) → SemanticCore
```

**Параметры:**
- `config_path`: Путь к semantic.toml (опционально, auto-discover).
- `embedding_provider`: Override провайдера embeddings.
- `llm_provider`: Override провайдера LLM.
- `**overrides`: Любые другие настройки конфига.

**Пример:**
```python
# С auto-discovery конфига
core = create_core()

# С override провайдеров
core = create_core(
    embedding_provider="local",
    llm_provider="ollama"
)

# С кастомным конфигом
core = create_core(config_path=Path("custom.toml"))
```

---

## Graceful Degradation

Если зависимости провайдера отсутствуют, фабрика выдаёт понятную ошибку:

```python
try:
    embedder = ComponentFactory.create_embedder(config)
except ImportError as e:
    print(e)
    # ImportError: Local embeddings not available.
    # Install with: pip install semantic-core[local-embeddings]
```

**Проверка доступности:**

```python
from semantic_core.utils.dependencies import is_provider_available

if is_provider_available("local_embeddings"):
    embedder = ComponentFactory.create_embedder(config)
else:
    print("Local embeddings not installed")
```

---

## Связанные документы

- [Configuration Guide](../guides/core/configuration.md) — semantic.toml структура
- [Multi-Provider Architecture](../concepts/11_multi_provider.md) — концепция
- [Flask Integration](../guides/integrations/flask.md) — использование в Flask
```

---

### 3. Обновить `docs/reference/configuration-options.md`

**Добавить детали LocalEmbedder параметров:**

```markdown
### Local Provider (MLX/CPU)

#### `providers.local.embedding_model`

**Тип:** string  
**Default:** `"all-minilm"`  
**Варианты:**
- `"qwen3-embedding"` — 1024D, 8K tokens, лучшее качество
- `"all-minilm"` — 384D, 512 tokens, fastest
- `"bge-small"` — 384D, 512 tokens, quality/speed balance
- HuggingFace model ID (custom)

**Пример:**
```toml
[providers.local]
embedding_model = "qwen3-embedding"
```

#### `providers.local.device`

**Тип:** string  
**Default:** `"mps"` (Apple Silicon)  
**Варианты:**
- `"mps"` — Apple Silicon (M1/M2/M3)
- `"cuda"` — NVIDIA GPU
- `"cpu"` — CPU only (медленно)
- `"auto"` — Автоопределение

**Пример:**
```toml
device = "cuda"  # RTX 3080
```

#### `providers.local.max_tokens`

**Тип:** int | null  
**Default:** null (используется дефолт модели)  
**Назначение:** Переопределить max_tokens для кастомных моделей.

**Пример:**
```toml
embedding_model = "sentence-transformers/all-mpnet-base-v2"
max_tokens = 512  # Override
```
```

---

## 📂 Структура файлов после обновления

```
docs/reference/
├── interfaces.md                  # UPDATE: Детальный API всех интерфейсов
├── component-factory.md           # NEW: ComponentFactory API reference
├── configuration-options.md       # UPDATE: Детали providers.local
├── cli-commands.md                # Без изменений
├── chunk-types.md                 # Без изменений
├── error-codes.md                 # Без изменений
├── models.md                      # Без изменений
└── local-models.md                # Уже создан в Phase 17.1
```

---

## ✅ Acceptance Criteria

### interfaces.md

- [ ] Каждый метод содержит: Parameters, Returns, Raises, Example
- [ ] Все properties задокументированы
- [ ] Каждая реализация (GeminiEmbedder, LocalEmbedder) имеет конструктор
- [ ] Примеры кода протестированы

### component-factory.md

- [ ] Все 5 методов фабрики задокументированы
- [ ] Таблица поддерживаемых провайдеров
- [ ] Graceful degradation объяснён
- [ ] create_core() convenience функция описана

### configuration-options.md

- [ ] providers.local.* параметры детально расписаны
- [ ] Примеры TOML для каждого параметра
- [ ] Ссылки на local-models.md (список моделей)

---

## 🎯 Будущие расширения

### Phase 18+: Новые провайдеры

Когда добавится новый провайдер (например, Anthropic):

1. Добавить в `component-factory.md`:
   ```markdown
   - `anthropic` → `AnthropicLLMProvider`
   ```

2. Добавить в `configuration-options.md`:
   ```markdown
   ### Anthropic Provider
   #### providers.anthropic.api_key
   ...
   ```

**Структура документации готова к расширению.**

---

## 🚀 План реализации

### День 1: interfaces.md

1. Детализировать BaseEmbedder (2-3 часа)
2. Детализировать BaseLLMProvider (2 часа)
3. Детализировать ITranscriber, IVisionAnalyzer (2 часа)
4. Добавить реализации (GeminiEmbedder, LocalEmbedder, ...) (2 часа)

### День 2: component-factory.md

5. Создать структуру документа (1 час)
6. Описать все 5 методов фабрики (3-4 часа)
7. Добавить примеры graceful degradation (1 час)
8. Протестировать примеры кода (2 часа)

### День 3: configuration-options.md + review

9. Обновить providers.local секцию (2 часа)
10. Добавить ссылки между документами (1 час)
11. Spell check и consistency (1 час)
12. Финальный review (2 часа)

---

**Статус:** 📝 Draft | **Автор:** GitHub Copilot | **Дата:** 11 декабря 2025
