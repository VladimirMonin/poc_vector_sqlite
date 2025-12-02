# 🗺️ Phase 6.1: Тестирование Image + Queue Infrastructure

**Цель:** Покрыть тестами ключевые пути Phase 6.0 (sync/async, retry, rate limiting).

**Принцип от архитектора:** Меньше моков, больше реальных тестов. Хотя бы 1-2 E2E с Gemini.

---

## 📂 Структура тестов

```text
tests/
├── conftest.py                        # Фикстуры для медиа
├── fixtures/
│   └── images/                        # Тестовые картинки
│       └── red_square.png             # Синтетическая (создаётся в setup)
├── unit/
│   ├── domain/
│   │   └── test_media_dto.py          # DTO валидация
│   └── infrastructure/
│       ├── media/
│       │   ├── test_file_utils.py     # MIME detection
│       │   └── test_tokens.py         # Token calculation
│       └── gemini/
│           ├── test_resilience.py     # Retry decorator
│           └── test_rate_limiter.py   # Rate limiting
├── integration/
│   └── media/
│       ├── test_queue_processor.py    # Queue + Mock Analyzer
│       └── test_pipeline_image.py     # Pipeline sync/async
└── e2e/
    └── gemini/
        └── test_real_image.py         # 🔥 Реальный Gemini API
```

---

## 🛠️ 1. Фикстуры (`conftest.py`)

```python
import pytest
import json
from pathlib import Path
from PIL import Image
from unittest.mock import MagicMock
from datetime import datetime

# === Пути ===

@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"

@pytest.fixture
def images_dir(fixtures_dir) -> Path:
    path = fixtures_dir / "images"
    path.mkdir(parents=True, exist_ok=True)
    return path

# === Синтетические изображения ===

@pytest.fixture
def red_square_path(images_dir) -> Path:
    """Создаёт красный квадрат 200x200."""
    path = images_dir / "red_square.png"
    if not path.exists():
        img = Image.new("RGB", (200, 200), color="red")
        img.save(path)
    return path

@pytest.fixture
def large_image_path(images_dir) -> Path:
    """Создаёт большую картинку 3000x2000."""
    path = images_dir / "large_blue.png"
    if not path.exists():
        img = Image.new("RGB", (3000, 2000), color="blue")
        img.save(path)
    return path

# === Mock Analyzer ===

@pytest.fixture
def mock_analysis_result():
    """Фабрика результатов анализа."""
    from semantic_core.domain.media import MediaAnalysisResult
    
    def _create(
        description="A test image description",
        alt_text="Test image",
        keywords=None,
    ):
        return MediaAnalysisResult(
            description=description,
            alt_text=alt_text,
            keywords=keywords or ["test"],
        )
    return _create

@pytest.fixture
def mock_image_analyzer(mock_analysis_result):
    """Mock GeminiImageAnalyzer."""
    analyzer = MagicMock()
    analyzer.analyze.return_value = mock_analysis_result()
    return analyzer

# === In-Memory DB с MediaTaskModel ===

@pytest.fixture
def media_db(tmp_path):
    """БД с таблицей MediaTaskModel."""
    from peewee import SqliteDatabase
    from semantic_core.infrastructure.storage.peewee.models import (
        BaseModel, MediaTaskModel, ChunkModel, DocumentModel
    )
    
    db_path = tmp_path / "test_media.db"
    db = SqliteDatabase(str(db_path))
    
    # Привязываем модели
    BaseModel._meta.database = db
    
    db.connect()
    db.create_tables([DocumentModel, ChunkModel, MediaTaskModel])
    
    yield db
    
    db.close()

# === Маркеры ===

def pytest_configure(config):
    config.addinivalue_line(
        "markers", 
        "real_api: tests that call real Gemini API"
    )
```

---

## 🧪 2. Unit: DTO (`test_media_dto.py`)

```python
"""Тесты domain/media.py"""

import pytest
from pathlib import Path
from semantic_core.domain.media import (
    MediaType, TaskStatus, MediaResource, MediaRequest, MediaAnalysisResult
)

class TestMediaType:
    def test_values(self):
        assert MediaType.IMAGE.value == "image"
        assert MediaType.AUDIO.value == "audio"

class TestMediaResource:
    def test_create(self, tmp_path):
        path = tmp_path / "test.jpg"
        path.touch()
        
        resource = MediaResource(
            path=path,
            media_type=MediaType.IMAGE,
            mime_type="image/jpeg",
        )
        
        assert resource.path == path
        assert resource.metadata == {}

class TestMediaAnalysisResult:
    def test_minimal(self):
        result = MediaAnalysisResult(description="A cat")
        assert result.description == "A cat"
        assert result.keywords == []
    
    def test_full(self):
        result = MediaAnalysisResult(
            description="A fluffy cat",
            alt_text="Cat photo",
            keywords=["cat", "fluffy"],
            ocr_text="Meow",
        )
        assert "cat" in result.keywords
```

---

## 🧪 3. Unit: Token Calculator (`test_tokens.py`)

```python
"""Тесты infrastructure/media/utils/tokens.py"""

import pytest
from PIL import Image
from semantic_core.infrastructure.media.utils.tokens import (
    calculate_image_tokens, estimate_cost
)

class TestCalculateTokens:
    def test_small_image_258_tokens(self):
        """<= 384x384 → 258 токенов."""
        img = Image.new("RGB", (300, 300))
        assert calculate_image_tokens(img) == 258
    
    def test_medium_image_tiling(self):
        """800x600 → тайлинг."""
        img = Image.new("RGB", (800, 600))
        tokens = calculate_image_tokens(img)
        # min_dim=600, crop_unit=400, tiles=2x2=4, tokens=4*258=1032
        assert tokens == 1032
    
    def test_large_1080p(self):
        """1920x1080 → много тайлов."""
        img = Image.new("RGB", (1920, 1080))
        tokens = calculate_image_tokens(img)
        assert tokens > 1000

class TestEstimateCost:
    def test_flash_model(self):
        result = estimate_cost(1000, "gemini-2.5-flash")
        assert "estimated_input_cost_usd" in result
        assert result["tokens"] == 1000
```

---

## 🧪 4. Unit: Retry Decorator (`test_resilience.py`)

```python
"""Тесты infrastructure/gemini/resilience.py"""

import pytest
from unittest.mock import Mock, patch
from semantic_core.infrastructure.gemini.resilience import (
    retry_with_backoff, MediaProcessingError
)

class TestRetryWithBackoff:
    def test_success_first_try(self):
        func = Mock(return_value="ok")
        decorated = retry_with_backoff(max_retries=3)(func)
        
        assert decorated() == "ok"
        assert func.call_count == 1
    
    def test_success_after_retries(self):
        func = Mock(side_effect=[
            Exception("429 Resource Exhausted"),
            Exception("503"),
            "ok"
        ])
        
        with patch("time.sleep"):
            decorated = retry_with_backoff(max_retries=3)(func)
            assert decorated() == "ok"
        
        assert func.call_count == 3
    
    def test_all_retries_fail(self):
        func = Mock(side_effect=Exception("429"))
        
        with patch("time.sleep"):
            decorated = retry_with_backoff(max_retries=3)(func)
            
            with pytest.raises(MediaProcessingError):
                decorated()
        
        assert func.call_count == 3
    
    def test_non_retryable_not_retried(self):
        func = Mock(side_effect=ValueError("bad input"))
        decorated = retry_with_backoff(max_retries=3)(func)
        
        with pytest.raises(ValueError):
            decorated()
        
        assert func.call_count == 1
```

---

## 🧪 5. Unit: Rate Limiter (`test_rate_limiter.py`)

```python
"""Тесты infrastructure/gemini/rate_limiter.py"""

import pytest
import time
from unittest.mock import patch
from semantic_core.infrastructure.gemini.rate_limiter import RateLimiter

class TestRateLimiter:
    def test_min_delay_calculation(self):
        limiter = RateLimiter(rpm_limit=15)
        assert limiter.min_delay == 4.0  # 60/15
    
    def test_first_request_no_wait(self):
        limiter = RateLimiter(rpm_limit=60)  # 1 req/sec
        
        sleep_calls = []
        with patch("time.sleep", lambda x: sleep_calls.append(x)):
            limiter.wait()
        
        # Первый запрос не ждёт
        assert len(sleep_calls) == 0
    
    def test_second_request_waits(self):
        limiter = RateLimiter(rpm_limit=60)
        
        limiter.wait()  # Первый
        
        sleep_calls = []
        with patch("time.sleep", lambda x: sleep_calls.append(x)):
            with patch("time.time", return_value=limiter._last_request + 0.5):
                limiter._lock.acquire()
                limiter._lock.release()
                # Симулируем что прошло 0.5 сек
        
        # Должен ждать ~0.5 сек до следующего
```

---

## 🔗 6. Integration: Queue Processor (`test_queue_processor.py`)

```python
"""Интеграционные тесты MediaQueueProcessor."""

import pytest
from semantic_core.core.media_queue import MediaQueueProcessor
from semantic_core.infrastructure.gemini.rate_limiter import RateLimiter
from semantic_core.infrastructure.storage.peewee.models import MediaTaskModel

class TestMediaQueueProcessor:
    @pytest.fixture
    def processor(self, media_db, mock_image_analyzer):
        """Processor с мок-анализатором."""
        return MediaQueueProcessor(
            db=media_db,
            analyzer=mock_image_analyzer,
            rate_limiter=RateLimiter(rpm_limit=60),
            pipeline=None,  # Упрощённо
        )
    
    def test_empty_queue_returns_false(self, processor):
        """Пустая очередь → False."""
        assert processor.process_one() is False
    
    def test_process_pending_task(self, processor, red_square_path, media_db):
        """Обработка pending задачи."""
        # Создаём задачу
        MediaTaskModel.create(
            id="test-1",
            media_path=str(red_square_path),
            media_type="image",
            mime_type="image/png",
            status="pending",
        )
        
        # Обрабатываем
        result = processor.process_one()
        
        assert result is True
        
        # Проверяем статус
        task = MediaTaskModel.get_by_id("test-1")
        assert task.status == "completed"
        assert task.result_description is not None
    
    def test_process_batch(self, processor, red_square_path, media_db):
        """Обработка пачки задач."""
        # Создаём 5 задач
        for i in range(5):
            MediaTaskModel.create(
                id=f"batch-{i}",
                media_path=str(red_square_path),
                media_type="image",
                mime_type="image/png",
                status="pending",
            )
        
        # Обрабатываем максимум 3
        processed = processor.process_batch(max_tasks=3)
        
        assert processed == 3
        
        # Осталось 2 pending
        pending = MediaTaskModel.select().where(
            MediaTaskModel.status == "pending"
        ).count()
        assert pending == 2
```

---

## 🔗 7. Integration: Pipeline (`test_pipeline_image.py`)

```python
"""Интеграционные тесты IngestionPipeline для изображений."""

import pytest
from semantic_core.pipeline import IngestionPipeline
from semantic_core.infrastructure.storage.peewee.models import MediaTaskModel

class TestPipelineImageIngestion:
    @pytest.fixture
    def pipeline(self, media_db, mock_image_analyzer, test_vector_store):
        """Pipeline с моками."""
        return IngestionPipeline(
            vector_store=test_vector_store,
            image_analyzer=mock_image_analyzer,
        )
    
    def test_ingest_image_sync(self, pipeline, red_square_path):
        """Sync mode возвращает chunk_id."""
        chunk_id = pipeline.ingest_image(
            path=str(red_square_path),
            mode="sync",
        )
        
        assert chunk_id is not None
        assert isinstance(chunk_id, str)
    
    def test_ingest_image_async(self, pipeline, red_square_path):
        """Async mode возвращает task_id."""
        task_id = pipeline.ingest_image(
            path=str(red_square_path),
            mode="async",
        )
        
        assert task_id is not None
        
        # Задача в БД
        task = MediaTaskModel.get_by_id(task_id)
        assert task.status == "pending"
    
    def test_ingest_with_context(self, pipeline, red_square_path):
        """Контекст передаётся в анализатор."""
        pipeline.ingest_image(
            path=str(red_square_path),
            context_text="Section: Paris Photos",
            mode="sync",
        )
        
        # Проверяем, что анализатор получил контекст
        call_args = pipeline.image_analyzer.analyze.call_args
        request = call_args[0][0]
        assert "Paris" in request.context_text
```

---

## 🌐 8. E2E: Real Gemini API (`test_real_image.py`)

```python
"""E2E тесты с реальным Gemini API.

⚠️ Тратят токены! Запуск: pytest -m real_api
"""

import pytest
import os
from PIL import Image
from semantic_core.infrastructure.gemini.image_analyzer import GeminiImageAnalyzer
from semantic_core.domain.media import MediaResource, MediaRequest, MediaType

@pytest.mark.real_api
class TestRealGeminiImage:
    
    @pytest.fixture
    def api_key(self):
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            pytest.skip("GEMINI_API_KEY not set")
        return key
    
    @pytest.fixture
    def analyzer(self, api_key):
        return GeminiImageAnalyzer(api_key=api_key)
    
    def test_analyze_red_square(self, analyzer, red_square_path):
        """Gemini описывает красный квадрат."""
        resource = MediaResource(
            path=red_square_path,
            media_type=MediaType.IMAGE,
            mime_type="image/png",
        )
        request = MediaRequest(resource=resource)
        
        result = analyzer.analyze(request)
        
        # Проверяем структуру
        assert result.description
        assert len(result.description) > 10
        
        # Должен упомянуть "red" или "square"
        text = result.description.lower()
        assert "red" in text or "square" in text
        
        print(f"\n🎨 Gemini says: {result.description}")
    
    def test_analyze_with_context(self, analyzer, red_square_path):
        """Контекст влияет на описание."""
        resource = MediaResource(
            path=red_square_path,
            media_type=MediaType.IMAGE,
            mime_type="image/png",
        )
        request = MediaRequest(
            resource=resource,
            context_text="This is a logo for a tech company",
        )
        
        result = analyzer.analyze(request)
        
        # Контекст должен повлиять
        print(f"\n💼 With context: {result.description}")
        assert result.description
```

---

## 🏃 Запуск тестов

```bash
# Все тесты кроме real_api (быстро, бесплатно)
pytest tests/ -m "not real_api" -v

# Только unit
pytest tests/unit/ -v

# Только integration
pytest tests/integration/ -v

# E2E с реальным API (нужен ключ)
export GEMINI_API_KEY="your-key"
pytest tests/e2e/ -m real_api -v --tb=short
```

---

## ✅ Definition of Done (Phase 6.1)

1. **Unit-тесты зелёные:** DTO, tokens, resilience, rate_limiter
2. **Integration-тесты зелёные:** Queue processor, Pipeline
3. **E2E работает:** Реальный Gemini возвращает описание картинки
4. **Покрытие:** Happy path + основные error cases
