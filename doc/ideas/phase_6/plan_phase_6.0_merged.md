# 🗺️ Phase 6.0: Image Analysis + Async Queue (Merged)

**Цель:** Реализовать полный flow обработки изображений с поддержкой async mode с самого начала.

**Принцип от архитектора:** Не "сначала sync, потом переписываем на async", а сразу закладываем очередь.

**Доноры кода:** `doc/code_assets/` (см. `guide.md`)

---

## 📐 Архитектура (Упрощённая)

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  ingest_image() │────▶│  MediaTaskModel │────▶│ QueueProcessor  │
│  mode=sync/async│     │   (SQLite)      │     │ + RateLimiter   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │ GeminiAnalyzer  │
                                               │ + @retry        │
                                               └─────────────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │  ChunkModel     │
                                               │  (vectorized)   │
                                               └─────────────────┘
```

**Sync mode:** Задача создаётся → сразу обрабатывается → результат возвращается.
**Async mode:** Задача создаётся → возвращается `task_id` → обработка позже.

---

## 📦 1. Конфигурация (`semantic_core/domain/config.py`)

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class MediaConfig:
    """Конфигурация для обработки медиа."""
    
    # Модели Gemini
    image_model: str = "gemini-2.5-flash"
    audio_model: str = "gemini-2.5-flash-lite"  # Для Phase 6.2
    video_model: str = "gemini-2.5-pro"         # Для Phase 6.2
    
    # Rate Limiting
    rpm_limit: int = 15  # Requests Per Minute (консервативно для Free Tier)
    
    # Оптимизация изображений
    max_image_dimension: int = 1920
    image_format: str = "webp"
    image_quality: int = 80
```

---

## 📦 2. DTO Медиа (`semantic_core/domain/media.py`)

```python
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from pathlib import Path

class MediaType(Enum):
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"

class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class MediaResource:
    """Контейнер для медиа-файла."""
    path: Path
    media_type: MediaType
    mime_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MediaRequest:
    """Запрос на анализ медиа."""
    resource: MediaResource
    user_prompt: Optional[str] = None
    context_text: Optional[str] = None  # Из метаданных чанка (заголовки)

@dataclass
class MediaAnalysisResult:
    """Результат анализа."""
    description: str
    alt_text: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    ocr_text: Optional[str] = None
    tokens_used: Optional[int] = None
```

---

## 📦 3. Модель задачи в БД (`infrastructure/storage/peewee/models.py`)

**Добавить к существующим моделям:**

```python
class MediaTaskModel(BaseModel):
    """Задача на обработку медиа."""
    
    id = CharField(primary_key=True)  # UUID
    
    # Медиа
    media_path = CharField()
    media_type = CharField()  # image, audio, video
    mime_type = CharField()
    
    # Контекст (простой — из метаданных чанка)
    user_prompt = TextField(null=True)
    context_text = TextField(null=True)  # Заголовки секции
    
    # Статус
    status = CharField(default="pending")
    error_message = TextField(null=True)
    
    # Результат
    result_description = TextField(null=True)
    result_alt_text = TextField(null=True)
    result_keywords = TextField(null=True)  # JSON array
    result_ocr_text = TextField(null=True)
    
    # Связь с результирующим чанком
    result_chunk_id = CharField(null=True)
    
    # Метаданные
    created_at = DateTimeField(default=datetime.now)
    processed_at = DateTimeField(null=True)
    
    class Meta:
        table_name = "media_tasks"
```

---

## 🛠️ 4. Утилиты (`infrastructure/media/utils/`)

### 4.1 Валидация файлов (`files.py`)

**Донор:** `doc/code_assets/file_utils.py`

```python
SUPPORTED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"]

def get_file_mime_type(path: str) -> str:
    """Определяет MIME-тип файла."""
    ...

def is_image_valid(path: str) -> bool:
    """Проверяет, поддерживается ли формат."""
    ...

def get_media_type(path: str) -> MediaType:
    """Определяет тип медиа по MIME."""
    ...
```

### 4.2 Расчёт токенов (`tokens.py`)

**Донор:** `doc/code_assets/image_tokens.py`

```python
def calculate_image_tokens(image: Image.Image) -> int:
    """
    Расчёт токенов по алгоритму Gemini.
    
    <= 384x384: 258 токенов
    > 384px: тайлинг (crop_unit = min_dim / 1.5)
    """
    ...

def estimate_cost(tokens: int, model: str) -> dict:
    """Оценка стоимости."""
    ...
```

### 4.3 Оптимизация изображений (`images.py`)

```python
def resize_image(image: Image.Image, max_dimension: int) -> Image.Image:
    """Ресайз с сохранением пропорций."""
    ...

def optimize_for_api(path: str, config: MediaConfig) -> tuple[bytes, str]:
    """Оптимизирует изображение для API. Returns (bytes, mime_type)."""
    ...
```

---

## ⚡ 5. Gemini Image Analyzer (`infrastructure/gemini/image_analyzer.py`)

**Доноры:** `doc/code_assets/image_analyzer.py`, `doc/code_assets/gemini_client.py`

```python
from google import genai
from google.genai import types

SYSTEM_PROMPT = """You are an image analyst creating descriptions for semantic search.
Describe: subject, objects, text (OCR), colors, mood.
Output JSON: {alt_text, description, keywords, ocr_text}"""

class GeminiImageAnalyzer:
    """Анализатор изображений через Gemini Vision API."""
    
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model
        self._client = None
    
    @property
    def client(self):
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client
    
    @retry_with_backoff(max_retries=5)
    def analyze(self, request: MediaRequest) -> MediaAnalysisResult:
        """Анализирует изображение."""
        
        # 1. Загружаем и оптимизируем
        image = Image.open(request.resource.path)
        
        # 2. Собираем промпт
        prompt_parts = []
        if request.context_text:
            prompt_parts.append(f"Context: {request.context_text}")
        if request.user_prompt:
            prompt_parts.append(request.user_prompt)
        else:
            prompt_parts.append("Analyze this image for search indexing.")
        
        prompt = "\n".join(prompt_parts)
        
        # 3. Вызываем API
        response = self.client.models.generate_content(
            model=self.model,
            contents=[prompt, image],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.4,
                response_mime_type="application/json",
                response_schema=ImageAnalysisSchema,
            ),
        )
        
        # 4. Парсим результат
        data = json.loads(response.text)
        return MediaAnalysisResult(
            description=data["description"],
            alt_text=data.get("alt_text"),
            keywords=data.get("keywords", []),
            ocr_text=data.get("ocr_text"),
        )
```

---

## 🛡️ 6. Resilience (`infrastructure/gemini/resilience.py`)

```python
import time
import random
from functools import wraps

class MediaProcessingError(Exception):
    """Ошибка после всех retry."""
    pass

def retry_with_backoff(max_retries=5, base_delay=1.0):
    """Декоратор с exponential backoff + jitter."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if not _is_retryable(e):
                        raise
                    if attempt == max_retries - 1:
                        raise MediaProcessingError(f"Failed after {max_retries} retries") from e
                    
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    time.sleep(delay)
            
        return wrapper
    return decorator

def _is_retryable(error) -> bool:
    """429, 503, 500, сетевые ошибки."""
    error_str = str(error).lower()
    return any(code in error_str for code in ["429", "503", "500", "timeout", "connection"])
```

---

## ⚡ 7. Rate Limiter (`infrastructure/gemini/rate_limiter.py`)

**Донор:** `doc/code_assets/queue_processor.py`

```python
import time
import threading

class RateLimiter:
    """Token Bucket Rate Limiter."""
    
    def __init__(self, rpm_limit: int = 15):
        self.rpm_limit = rpm_limit
        self._lock = threading.Lock()
        self._last_request = 0.0
    
    @property
    def min_delay(self) -> float:
        return 60.0 / self.rpm_limit
    
    def wait(self):
        """Ждёт если нужно."""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_request
            if elapsed < self.min_delay:
                time.sleep(self.min_delay - elapsed)
            self._last_request = time.time()
```

---

## 🔄 8. Media Queue Processor (`core/media_queue.py`)

```python
class MediaQueueProcessor:
    """Обработчик очереди медиа-задач."""
    
    def __init__(
        self,
        db,
        analyzer: GeminiImageAnalyzer,
        rate_limiter: RateLimiter,
        pipeline,  # Для создания чанков
    ):
        self.db = db
        self.analyzer = analyzer
        self.rate_limiter = rate_limiter
        self.pipeline = pipeline
    
    def process_one(self) -> bool:
        """Обрабатывает одну задачу."""
        task = self._get_pending_task()
        if not task:
            return False
        
        self._update_status(task.id, "processing")
        
        try:
            self.rate_limiter.wait()
            
            request = self._to_request(task)
            result = self.analyzer.analyze(request)
            
            # Создаём чанк с описанием
            chunk_id = self._create_chunk(task, result)
            
            self._save_result(task.id, result, chunk_id)
            return True
            
        except Exception as e:
            self._update_status(task.id, "failed", error=str(e))
            return True
    
    def process_batch(self, max_tasks: int = 10) -> int:
        """Обрабатывает пачку задач."""
        processed = 0
        for _ in range(max_tasks):
            if not self.process_one():
                break
            processed += 1
        return processed
    
    def _create_chunk(self, task, result) -> str:
        """Создаёт индексируемый чанк из результата."""
        from semantic_core.domain.document import Document
        
        doc = Document(
            source=task.media_path,
            content=result.description,
            doc_type=MediaType.IMAGE,
            metadata={
                "alt_text": result.alt_text,
                "keywords": result.keywords,
                "ocr_text": result.ocr_text,
            }
        )
        
        # Используем существующий pipeline для векторизации
        chunk_ids = self.pipeline.ingest(doc, mode="sync")
        return chunk_ids[0] if chunk_ids else None
```

---

## 🔄 9. Интеграция с Pipeline (`pipeline.py`)

```python
class IngestionPipeline:
    def __init__(
        self,
        # ... существующее ...
        image_analyzer: Optional[GeminiImageAnalyzer] = None,
        media_config: Optional[MediaConfig] = None,
    ):
        self.image_analyzer = image_analyzer
        self.media_config = media_config or MediaConfig()
        self._rate_limiter = RateLimiter(self.media_config.rpm_limit)
        self._media_queue = None  # Lazy init
    
    def ingest_image(
        self,
        path: str,
        user_prompt: Optional[str] = None,
        context_text: Optional[str] = None,
        mode: Literal["sync", "async"] = "sync",
    ) -> Optional[str]:
        """
        Индексирует изображение.
        
        Args:
            path: Путь к файлу
            user_prompt: Кастомный промпт
            context_text: Контекст (заголовки из метаданных чанка)
            mode: sync — сразу, async — в очередь
            
        Returns:
            sync: chunk_id
            async: task_id
        """
        # Валидация
        if not is_image_valid(path):
            raise ValueError(f"Unsupported image: {path}")
        
        # Создаём задачу в БД
        task_id = self._create_media_task(path, user_prompt, context_text)
        
        if mode == "sync":
            # Обрабатываем сразу
            self._ensure_queue_processor()
            success = self._media_queue.process_task(task_id)
            if not success:
                raise RuntimeError(f"Failed to process {path}")
            
            # Возвращаем chunk_id
            task = MediaTaskModel.get_by_id(task_id)
            return task.result_chunk_id
        
        else:  # async
            # Просто возвращаем task_id
            return task_id
    
    def process_media_queue(self, max_tasks: int = 10) -> int:
        """Обрабатывает очередь медиа."""
        self._ensure_queue_processor()
        return self._media_queue.process_batch(max_tasks)
    
    def _create_media_task(self, path, prompt, context) -> str:
        """Создаёт задачу в БД."""
        import uuid
        
        task_id = str(uuid.uuid4())
        media_type = get_media_type(path)
        mime_type = get_file_mime_type(path)
        
        MediaTaskModel.create(
            id=task_id,
            media_path=path,
            media_type=media_type.value,
            mime_type=mime_type,
            user_prompt=prompt,
            context_text=context,
            status="pending",
        )
        
        return task_id
```

---

## 🔗 10. Интеграция с IMAGE_REF из Markdown

**Упрощённый подход (по рекомендации архитектора):**

Не пишем сложный `Enricher`. Просто в `IngestionPipeline.ingest()` ловим чанки типа `IMAGE_REF`:

```python
def ingest(self, document: Document, mode="sync") -> List[str]:
    """Индексирует документ."""
    
    # Парсим
    chunks = self.parser.parse(document.content)
    
    chunk_ids = []
    
    for chunk in chunks:
        if chunk.chunk_type == ChunkType.IMAGE_REF:
            # Это изображение из Markdown
            image_path = self._resolve_image_path(document.source, chunk)
            
            # Берём контекст из СУЩЕСТВУЮЩИХ метаданных чанка
            # (заголовки уже есть благодаря Phase 4!)
            context = self._extract_simple_context(chunk)
            
            # Индексируем картинку
            result_id = self.ingest_image(
                path=image_path,
                context_text=context,
                mode=mode,
            )
            chunk_ids.append(result_id)
        
        else:
            # Обычный текстовый чанк
            chunk_ids.append(self._save_chunk(chunk, mode))
    
    return chunk_ids

def _extract_simple_context(self, chunk: Chunk) -> str:
    """Извлекает контекст из метаданных чанка (уже есть!)."""
    parts = []
    
    # Заголовок секции (из Phase 4 HierarchicalContext)
    if chunk.metadata.get("section_title"):
        parts.append(f"Section: {chunk.metadata['section_title']}")
    
    # Alt-text
    if chunk.content:
        parts.append(f"Caption: {chunk.content}")
    
    return "\n".join(parts)
```

**Почему это работает:** Phase 4 уже записывает контекст (заголовки) в метаданные каждого чанка. Нам не нужно заново "искать текст вокруг картинки" — он уже там!

---

## 📂 Структура файлов Phase 6.0 (Merged)

```text
semantic_core/
├── domain/
│   ├── config.py                   # UPDATE: + MediaConfig
│   └── media.py                    # NEW: MediaType, MediaResource, MediaRequest, MediaAnalysisResult
├── core/
│   └── media_queue.py              # NEW: MediaQueueProcessor
├── infrastructure/
│   ├── gemini/
│   │   ├── image_analyzer.py       # NEW: GeminiImageAnalyzer
│   │   ├── resilience.py           # NEW: retry_with_backoff
│   │   └── rate_limiter.py         # NEW: RateLimiter
│   ├── media/
│   │   └── utils/
│   │       ├── __init__.py         # NEW
│   │       ├── files.py            # NEW: MIME validation
│   │       ├── tokens.py           # NEW: token calculation
│   │       └── images.py           # NEW: resize, optimize
│   └── storage/
│       └── peewee/
│           └── models.py           # UPDATE: + MediaTaskModel
└── pipeline.py                     # UPDATE: ingest_image(), IMAGE_REF handling
```

---

## ✅ Definition of Done (Phase 6.0)

1. **Sync mode работает:**

   ```python
   chunk_id = pipeline.ingest_image("cat.jpg", mode="sync")
   results = store.search("cat")  # Находит!
   ```

2. **Async mode работает:**

   ```python
   task_id = pipeline.ingest_image("dog.jpg", mode="async")
   # Позже:
   pipeline.process_media_queue()
   results = store.search("dog")  # Находит!
   ```

3. **Markdown с картинками работает:**

   ```python
   doc = Document(source="travel.md", content="... ![Eiffel](photo.jpg) ...")
   pipeline.ingest(doc)
   results = store.search("Paris tower")  # Находит фото!
   ```

4. **Rate Limiting работает:** Нет 429 ошибок при пачке картинок.

5. **Retry работает:** 503 ошибки не роняют систему.

---

## 🔗 Зависимости

```toml
[project.optional-dependencies]
media = [
    "Pillow>=10.0.0",
]
```

---

## 🚀 Следующие шаги

После Phase 6.0:

- **Phase 6.1:** Тесты (unit + 1-2 E2E с реальным API)
- **Phase 6.2:** Audio/Video (подключаем `pydub`, `imageio`)

**Отложено:**

- Сложный `MarkdownAssetEnricher` — не нужен, контекст берём из метаданных
- GCS Batch API для медиа — Local Queue достаточно
