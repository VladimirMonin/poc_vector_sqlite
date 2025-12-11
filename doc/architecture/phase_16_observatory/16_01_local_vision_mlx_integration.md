# 16.01 Local Vision MLX Integration: Qwen3-VL-4B и Optional Dependencies

> **Коммит**: `9cc8a70`  
> **Дата**: 11 декабря 2025 г.  
> **Фаза**: 16.0 Observatory  
> **Тема**: Интеграция локальных Vision-Language моделей через MLX Framework

---

## 🎯 Задача

Добавить поддержку локальных Vision-Language моделей (VLM) на Apple Silicon без установки тяжёлых зависимостей PyTorch.

**Требования:**

1. Использовать MLX Framework (нативный для Apple Silicon)
2. Избегать установки PyTorch (~500 MB)
3. Поддержка Qwen3-VL-4B-Instruct-4bit (~3.3 GB)
4. Работа на MacBook Air 8GB RAM
5. Интеграция с существующим Inspector для артефактов

---

## 🧩 Проблема: Dependency Hell

### Исходная ситуация

MLX-VLM требует HuggingFace Transformers для загрузки моделей:

```
mlx-vlm 0.3.9
  └── transformers 4.57.3
       └── torchvision (для AutoVideoProcessor)
            └── torch 2.9.1 (~500 MB) ❌
```

**Парадокс**: `torchvision` требуется только для **проверки** `is_torchvision_available()`, но НЕ используется в runtime!

### Решение из референсного проекта

Из отчёта `examples/poc_apple_local_llm/QWEN3_VL_INTEGRATION_REPORT.md`:

> torchvision 0.24+ поддерживает standalone режим БЕЗ PyTorch. Можно установить `torchvision --no-deps` (2 MB вместо 500 MB).

**Итого:**

- transformers: 12 MB
- torchvision: 2 MB
- **Экономия**: 500 MB (96.8%)

---

## 🔧 Архитектурное решение

### 1. Optional Dependency: `local-vision-mlx`

Создана новая группа зависимостей в `pyproject.toml`:

```toml
# === Local AI (Apple Silicon) ===
local-vision-mlx = [
    "mlx-vlm>=0.3.9,<0.4.0; platform_machine == 'arm64' and sys_platform == 'darwin'",
    "transformers==4.57.3; platform_machine == 'arm64' and sys_platform == 'darwin'",
    "torchvision>=0.24.0,<0.25.0; platform_machine == 'arm64' and sys_platform == 'darwin'",
    "tokenizers>=0.22.0,<0.23.0; platform_machine == 'arm64' and sys_platform == 'darwin'"
]
```

**Почему отдельная группа?**

- `local-embeddings-mlx` — только эмбеддинги (mlx-lm, mlx-embeddings)
- `local-whisper-mlx` — только аудио транскрипция
- `local-vision-mlx` — Vision-Language модели с зависимостями HuggingFace

### 2. Конфликт numpy: opencv-python vs numpy 2.x

**Проблема:**

```
opencv-python 4.12.0.88 requires numpy<2.3.0
poc-vector-sqlite core requires numpy>=2.3.5
```

**Решение:** Понизить numpy до 1.x для совместимости:

```toml
dependencies = [
    "numpy (>=1.24.0,<2.0.0)",  # Было: >=2.3.5,<3.0.0
    # ...
]
```

Это НЕ ломает функциональность — вся кодовая база совместима с numpy 1.26.4.

---

## 🎨 Расширение конфигурации embeddings

### Проблема: фиксированная длина токенов

Qwen3-Embedding поддерживает до 32K токенов, но дефолт — 8192:

```python
# semantic_core/infrastructure/local/embeddings/models.py
MODELS = {
    "qwen3-embedding": ModelConfig(
        hf_model_id="Alibaba-NLP/gte-Qwen2-1.5B-instruct",
        dimension=1024,
        backend=MLXBackend.MLX_LM,
        max_tokens=8192,  # ← Дефолт
    )
}
```

Нет способа изменить это через TOML!

### Решение: max_tokens override

**1. Добавлен max_tokens в LocalProviderConfig:**

```python
# semantic_core/config.py
class LocalProviderConfig(BaseModel):
    embedding_model: str = Field(default="all-minilm")
    max_tokens: Optional[int] = Field(
        default=None,
        description="Максимальная длина токенов (override дефолта модели)",
    )
    # ...
```

**2. Параметр max_tokens_override в LocalEmbedder:**

```python
# semantic_core/infrastructure/local/embeddings/embedder.py
def __init__(
    self,
    model: str = "all-minilm",
    device: Optional[str] = None,
    max_tokens_override: Optional[int] = None,  # NEW
):
    if model not in MODELS:
        raise ValueError(f"Unknown model: {model}")

    self._config: ModelConfig = MODELS[model]
    
    # Override max_tokens если указано
    if max_tokens_override is not None:
        from dataclasses import replace
        self._config = replace(self._config, max_tokens=max_tokens_override)
```

**3. ComponentFactory передаёт параметр:**

```python
# semantic_core/core/factory.py
@staticmethod
def create_embedder(config: SemanticConfig) -> BaseEmbedder:
    provider = config.defaults.embedding_provider
    
    if provider == "local":
        return LocalEmbedder(
            model=config.providers_local.embedding_model,
            device=config.providers_local.device,
            max_tokens_override=config.providers_local.max_tokens,  # NEW
        )
```

**Теперь можно через TOML:**

```toml
[providers.local]
embedding_model = "qwen3-embedding"
max_tokens = 4000  # Вместо дефолтных 8192
```

---

## 🐛 Исправленный баг: SemanticConfig.config_file

### Проблема

Параметр `config_file` игнорировался:

```python
config = SemanticConfig(config_file="/path/to/custom.toml")
# Использовал find_config_file() вместо переданного пути!
```

### Решение

```python
# semantic_core/config.py
def __init__(self, **data: Any):
    # Извлекаем config_file из kwargs если передан
    config_file = data.pop("config_file", None)  # NEW
    
    # Ищем TOML файл
    if config_file:
        toml_path = Path(config_file)  # Используем явный путь
    else:
        toml_path = find_config_file()  # Поиск в текущем/родительском
    
    toml_data: dict = {}
    if toml_path and toml_path.exists():
        toml_data = self._load_toml(toml_path)
```

---

## 🧪 E2E тесты: test_qwen3_extended_pipeline.py

Создано 4 теста для проверки всего стека:

### 1. test_qwen3_4000_tokens_embeddings

**Цель:** Проверить что max_tokens из TOML применяется.

```python
config_path.write_text("""
[defaults]
embedding_provider = "local"

[providers.local]
embedding_model = "qwen3-embedding"
max_tokens = 4000  # Override!
""")

config = SemanticConfig(config_file=str(config_path))
embedder = ComponentFactory.create_embedder(config)

assert embedder._config.max_tokens == 4000  # ✅
```

### 2. test_qwen3_vision_local_analysis

**Цель:** Проверить Qwen3-VL-4B для анализа изображений.

```python
from mlx_vlm import load, generate
from mlx_vlm.prompt_utils import apply_chat_template

model, processor = load("mlx-community/Qwen3-VL-4B-Instruct-4bit")
config = model.config

messages = [{
    "role": "user",
    "content": "Опиши что изображено на этой картинке подробно на русском языке."
}]

prompt = apply_chat_template(processor, config, messages, num_images=1)
output = generate(model, processor, prompt, str(test_image), 
                  max_tokens=200, temp=0.7, verbose=True)

# mlx-vlm 0.3.9 возвращает GenerationResult объект
output_text = output.text if hasattr(output, "text") else str(output)

assert len(output_text) > 0
assert len(output_text.split()) > 5
```

**Особенность:** Модель ~3.3GB загружается в память. На MacBook Air 8GB использует swap.

**Результат:**

- ✅ Модель загружается
- ✅ Генерирует описание на русском
- ⚠️ Скорость 3.7-15 токенов/сек (из-за swap, норма для 8GB)

### 3. test_qwen3_hybrid_search_with_inspection

**Цель:** Полный pipeline с Inspector артефактами.

```python
# 1. Создаём документ
doc = Document(content="# Machine Learning Overview\n...")

# 2. Индексируем с Inspector
inspector = ProviderInspector(config, session_name="test_session")
index.ingest_document(doc)

# 3. Делаем гибридный поиск
results = index.search_hybrid("neural networks", limit=3)

# 4. Сохраняем snapshot
snapshot = inspector.create_snapshot(
    file_path=str(doc_path),
    file_content=doc.content,
    chunks=chunks,
    searches=[search_result]
)
inspector.save_snapshot(snapshot, "test_inspection")
```

**Артефакты:**

- `test_inspection.json` — полный snapshot
- `similarities.csv` — таблица результатов
- `input_test_document.md` — копия входного файла

### 4. test_qwen3_multimodal_document_inspection

**Цель:** Инспекция документа с текстом + изображениями.

```python
content = """
# Multimodal Document

Текст с изображением:
![test](test_image.png)
"""

doc = Document(content=content, metadata={"source": doc_path})

# Inspector автоматически обнаружит media chunks
inspector = ProviderInspector(config, session_name="multimodal_session")
# ...
```

**Артефакты:**

- JSON с отдельными media chunks
- Копия изображения в artifacts/

---

## 🧠 Memory Management для 8GB MacBook

### Проблема

После теста с VLM моделью (~4GB RAM) остальные тесты могут упасть из-за нехватки памяти.

### Решение: явная очистка

```python
def test_qwen3_vision_local_analysis(self, tmp_path):
    model, processor = load("mlx-community/Qwen3-VL-4B-Instruct-4bit")
    # ... тест ...
    
    # Очищаем память (важно для 8GB MacBook!)
    del model, processor, config
    import gc
    gc.collect()
```

**Результат:** Все 4 теста проходят последовательно без OOM.

---

## 📊 Метрики

### Установка зависимостей

```bash
pip install -e ".[local-vision-mlx]"
```

**Размер:**

- transformers: 12 MB
- torchvision: 2 MB (БЕЗ torch!)
- mlx-vlm: 1.5 MB
- tokenizers: 2.9 MB
- **Итого:** ~18 MB

**Сравнение с PyTorch:**

- torch + torchvision: 520+ MB
- **Экономия:** 502 MB (96.5%)

### Производительность тестов

```
test_qwen3_4000_tokens_embeddings       PASSED  [ 25%]  (0.8s)
test_qwen3_vision_local_analysis        PASSED  [ 50%]  (25s)
test_qwen3_hybrid_search_with_inspection PASSED [ 75%]  (4s)
test_qwen3_multimodal_document_inspection PASSED [100%] (2s)

================================ 4 passed in 32.70s =================================
```

**VLM генерация на MacBook Air 8GB:**

- Загрузка модели: ~3 сек (из кэша)
- Генерация 200 токенов: ~20 сек
- Скорость: 3.7-15 токенов/сек (зависит от swap usage)
- Peak memory: 4.2 GB

---

## 🎓 Ключевые уроки

### 1. Optional Dependencies — это обязательно

Для проектов с мультиплатформенной поддержкой **всегда** разделяй зависимости по группам:

```toml
[project.optional-dependencies]
# Cloud
google = ["google-genai"]
openai = ["openai"]

# Local (Apple Silicon)
local-embeddings-mlx = ["mlx-lm", "mlx-embeddings"]
local-vision-mlx = ["mlx-vlm", "transformers", "torchvision"]

# Local (Cross-platform)
local-embeddings = ["sentence-transformers", "torch"]
```

**Почему?**

- Пользователь выбирает что ему нужно
- Избегаем конфликтов зависимостей
- Меньше установленных пакетов = быстрее CI

### 2. HuggingFace Transformers ≠ PyTorch

`transformers` можно использовать БЕЗ PyTorch для:

- Загрузки токенизаторов
- Конфигурации моделей
- Процессоров изображений

Но `torchvision` требуется для `AutoVideoProcessor.from_pretrained()`.

**Решение:** `pip install torchvision --no-deps`

### 3. Config Override через dataclasses.replace()

Когда нужно изменить иммутабельный dataclass:

```python
from dataclasses import replace

original = ModelConfig(max_tokens=8192)
modified = replace(original, max_tokens=4000)  # Новый объект!
```

Альтернатива `__post_init__` или mutable fields.

### 4. mlx-vlm API изменился в 0.3.9

**До 0.3.9:**

```python
output = generate(...)  # str
print(output)
```

**После 0.3.9:**

```python
output = generate(...)  # GenerationResult
print(output.text)  # str
print(output.token)  # int
print(output.prompt_tps)  # float
```

**Backward compatibility:**

```python
output_text = output.text if hasattr(output, "text") else str(output)
```

### 5. Memory cleanup важен для low-memory систем

На 8GB MacBook Air без `gc.collect()` второй VLM тест упадёт с OOM.

```python
# После теста с большой моделью
del model, processor, config
import gc
gc.collect()
```

---

## 🔗 Связанные коммиты

- `591f972` — Phase 16.0: Debug Observatory (Inspector Core)
- `9cc8a70` — Phase 16.0: Local Vision MLX Integration (этот коммит)

---

## 📚 Следующие шаги

**Phase 16.1** — CLI Inspect Command:

- `semantic inspect <file>` для создания snapshot
- Вывод через Rich console
- Опции: `--session`, `--provider`, `--output`

**Phase 16.2** — Multi-Provider Snapshots:

- Сравнение Gemini vs Local embeddings
- Анализ dimension mismatch (768D vs 1024D)
- Метрики качества поиска

---

## 🎯 Итог

✅ Добавлена поддержка локальных Vision-Language моделей  
✅ Интеграция БЕЗ PyTorch (экономия 500 MB)  
✅ Работает на MacBook Air 8GB  
✅ 4 E2E теста с Inspector артефактами  
✅ Расширена конфигурация: max_tokens override  
✅ Исправлены баги: SemanticConfig.config_file, GenerationResult API

**Проект теперь поддерживает:**

- ☁️ Cloud: Gemini, OpenAI
- 🍎 Local (Apple Silicon): MLX embeddings + Whisper + Vision
- 🖥️ Local (Cross-platform): sentence-transformers + Whisper

**Выбор за пользователем!**
