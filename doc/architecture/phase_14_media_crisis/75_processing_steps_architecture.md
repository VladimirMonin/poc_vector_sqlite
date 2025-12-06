# 75. Processing Steps Architecture — Модульная система обработки медиа

**Дата:** 2025-12-06  
**Фаза:** Phase 14.1.0 — Core Architecture  
**Статус:** ✅ Завершено  
**Предыдущая статья:** [74. Media Smart-Splitter Integration](74_media_smart_splitter_integration.md)  
**Следующая статья:** Phase 14.1.1 — Smart Steps Implementation

---

## 📋 Оглавление

1. [Мотивация — Проблемы монолитного pipeline](#1-мотивация--проблемы-монолитного-pipeline)
2. [Целевая архитектура](#2-целевая-архитектура)
3. [MediaContext — Immutable контейнер данных](#3-mediacontext--immutable-контейнер-данных)
4. [BaseProcessingStep — Абстракция для шагов](#4-baseprocessingstep--абстракция-для-шагов)
5. [MediaPipeline — Executor для координации шагов](#5-mediapipeline--executor-для-координации-шагов)
6. [Тестирование — 25 unit-тестов](#6-тестирование--25-unit-тестов)
7. [Примеры использования](#7-примеры-использования)
8. [Следующие шаги](#8-следующие-шаги)

---

## 1. Мотивация — Проблемы монолитного pipeline

### 1.1 Текущее состояние `pipeline.py`

До Phase 14.1.0 вся логика обработки медиа была в монолитном методе `_build_media_chunks()`:

```python
# semantic_core/pipeline.py (строки 1394-1454)
def _build_media_chunks(
    self,
    document: Document,
    media_path: Path,
    chunk_type: ChunkType,
    analysis: Optional[dict],
    fallback_metadata: Optional[dict] = None,
) -> list[Chunk]:
    """60 строк смешанной логики для summary + transcript + OCR."""
    
    # Summary chunk
    summary_content = self._build_content_from_analysis(analysis, media_type)
    summary_metadata = self._build_metadata_from_analysis(analysis, media_path)
    summary_chunk = Chunk(...)
    chunks.append(summary_chunk)
    
    # Transcription chunks (if exists)
    if transcription:
        transcript_chunks = self._split_transcription_into_chunks(...)
        chunks.extend(transcript_chunks)
    
    # OCR chunks (if exists)
    if ocr_text:
        ocr_chunks = self._split_ocr_into_chunks(...)
        chunks.extend(ocr_chunks)
    
    return chunks
```

**Проблемы:**

❌ **Невозможно добавить новый шаг** без изменения этого метода  
❌ **Дублирование логики** `_split_transcription_into_chunks()` vs `_split_ocr_into_chunks()`  
❌ **Жёсткая связанность** с `self.splitter`, нельзя переопределить splitter для конкретного шага  
❌ **Нет переиспользования** — каждый media type дублирует вызов `_build_media_chunks()`  
❌ **Невозможно перезапустить один шаг** — нужно re-analyze весь файл

### 1.2 Целевая модель расширяемости

**После рефакторинга (Phase 14.1.1+):**

```python
# Базовая конфигурация
pipeline = SemanticCore.create_with_steps([
    SummaryStep(),
    TranscriptionStep(chunk_size=1500),
    OCRStep(parser_mode="markdown"),
])

# Кастомизация для маркетинга
marketing_pipeline = SemanticCore.create_with_steps([
    SummaryStep(prompt_template="Summarize in pirate speak"),
    TranscriptionStep(),
    AdSpotDetectionStep(),  # Кастомный шаг
])

# Повторный запуск одного шага
pipeline.rerun_step("summary", document_id="abc-123")
```

---

## 2. Целевая архитектура

### 2.1 Компоненты системы

```
┌─────────────────────────────────────────────────────────────┐
│                      SemanticCore                            │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │              MediaPipeline                          │     │
│  │                                                     │     │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐      │     │
│  │  │ Summary   │→ │Transcript │→ │    OCR    │      │     │
│  │  │   Step    │  │   Step    │  │   Step    │      │     │
│  │  └───────────┘  └───────────┘  └───────────┘      │     │
│  │                                                     │     │
│  │              MediaContext (immutable)               │     │
│  │  ┌──────────────────────────────────────────────┐  │     │
│  │  │ media_path, analysis, chunks[], base_index   │  │     │
│  │  │ services: {splitter, embedder, ...}          │  │     │
│  │  └──────────────────────────────────────────────┘  │     │
│  └────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

**Поток данных:**

1. `SemanticCore.ingest_video()` создаёт начальный `MediaContext`
2. `MediaPipeline.build_chunks(context)` выполняет шаги по порядку
3. Каждый шаг получает context, обрабатывает, возвращает новый context
4. Финальный context содержит все чанки от всех шагов
5. SemanticCore сохраняет чанки в БД через `VectorStore`

---

## 3. MediaContext — Immutable контейнер данных

### 3.1 Дизайн

**Файл:** `semantic_core/core/media_context.py`

```python
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from semantic_core.domain import Chunk, Document


@dataclass(frozen=True)
class MediaContext:
    """Immutable контекст обработки медиа-файла.
    
    Передаётся между шагами processing pipeline. Каждый шаг возвращает
    обновлённый контекст через метод with_chunks().
    """
    
    media_path: Path
    document: Document
    analysis: dict[str, Any]
    chunks: list[Chunk] = field(default_factory=list)
    base_index: int = 0
    services: dict[str, Any] = field(default_factory=dict)
    user_instructions: str | None = None
    
    def with_chunks(
        self,
        new_chunks: list[Chunk],
        increment_index: bool = True,
    ) -> "MediaContext":
        """Возвращает новый контекст с добавленными чанками."""
        updated_chunks = self.chunks + new_chunks
        new_base_index = self.base_index + len(new_chunks) if increment_index else self.base_index
        
        return replace(
            self,
            chunks=updated_chunks,
            base_index=new_base_index,
        )
    
    def get_service(self, key: str, default: Any = None) -> Any:
        """Получает сервис из Service Locator."""
        return self.services.get(key, default)
```

### 3.2 Ключевые решения

**Frozen Dataclass:**

✅ **Immutability** — нельзя изменить поля напрямую (`context.base_index = 10` → FrozenInstanceError)  
✅ **Thread-safe** — безопасно читать из нескольких потоков  
✅ **Explicit copying** — изменения через `with_chunks()` создают новый объект

**Service Locator Pattern:**

```python
context = MediaContext(
    # ...
    services={
        "splitter": SmartSplitter(),
        "embedder": GeminiEmbedder(),
        "rate_limiter": rate_limiter,
    },
)

# В TranscriptionStep.process():
splitter = context.get_service("splitter")
```

**Альтернативы (отклонены):**

❌ **Mutable dict** — опасно, state может измениться неожиданно  
❌ **Dependency Injection в каждый step** — многословно, боilerplate  
❌ **Global state** — нарушает принципы SOLID

---

## 4. BaseProcessingStep — Абстракция для шагов

### 4.1 Интерфейс

**Файл:** `semantic_core/processing/steps/base.py`

```python
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from semantic_core.core.media_context import MediaContext


class ProcessingStepError(Exception):
    """Исключение при ошибке обработки в processing step."""
    
    def __init__(
        self,
        step_name: str,
        message: str,
        context: "MediaContext | None" = None,
    ):
        self.step_name = step_name
        self.context = context
        super().__init__(f"[{step_name}] {message}")


class BaseProcessingStep(ABC):
    """Базовый класс для шага обработки медиа-файла."""
    
    @property
    @abstractmethod
    def step_name(self) -> str:
        """Уникальное имя шага (для логирования и rerun)."""
        pass
    
    @abstractmethod
    def process(self, context: "MediaContext") -> "MediaContext":
        """Обрабатывает контекст и возвращает обновлённый.
        
        Должен быть чистой функцией:
        - Не модифицировать входной context
        - Не иметь side effects (кроме логирования)
        - Возвращать новый MediaContext через context.with_chunks()
        """
        pass
    
    @property
    def is_optional(self) -> bool:
        """Флаг опциональности шага.
        
        Если True:
        - Ошибка в process() логируется, но не останавливает pipeline
        - Pipeline продолжает выполнение следующих шагов
        """
        return False
    
    def should_run(self, context: "MediaContext") -> bool:
        """Проверяет, нужно ли запускать шаг для данного контекста.
        
        Example:
            def should_run(self, context: MediaContext) -> bool:
                # Запускаем только если есть transcription
                return bool(context.analysis.get("transcription"))
        """
        return True
```

### 4.2 Ключевые методы

| Метод | Назначение | Обязательный? |
|-------|-----------|---------------|
| `step_name` | Уникальный идентификатор (lowercase) | ✅ Да |
| `process()` | Основная логика обработки | ✅ Да |
| `should_run()` | Условие запуска (например, "только если есть transcript") | ❌ Нет (default=True) |
| `is_optional` | Пропускать ли pipeline при ошибке | ❌ Нет (default=False) |

**Пример реализации:**

```python
class SummaryStep(BaseProcessingStep):
    @property
    def step_name(self) -> str:
        return "summary"
    
    def process(self, context: MediaContext) -> MediaContext:
        analysis = context.analysis
        
        # Формируем summary chunk
        summary_chunk = Chunk(
            content=analysis.get("description", ""),
            chunk_index=context.base_index,
            chunk_type=ChunkType.VIDEO_REF,
            metadata={"role": "summary"},
        )
        
        return context.with_chunks([summary_chunk])
```

---

## 5. MediaPipeline — Executor для координации шагов

### 5.1 Алгоритм выполнения

**Файл:** `semantic_core/core/media_pipeline.py`

```python
class MediaPipeline:
    """Executor для step-based media processing pipeline."""
    
    def __init__(self, steps: list[BaseProcessingStep]):
        self.steps = steps
    
    def build_chunks(self, context: MediaContext) -> MediaContext:
        """Выполняет все шаги и возвращает финальный контекст."""
        current_context = context
        
        for step in self.steps:
            # 1. Проверяем, нужно ли запускать шаг
            if not step.should_run(current_context):
                logger.debug(f"Skipping step {step.step_name}")
                continue
            
            # 2. Выполняем шаг
            try:
                new_context = step.process(current_context)
                current_context = new_context
            
            except ProcessingStepError as e:
                # 3. Обрабатываем ошибки
                if step.is_optional:
                    logger.warning(f"Optional step {step.step_name} failed")
                else:
                    logger.error(f"Critical step {step.step_name} failed")
                    raise
        
        return current_context
```

### 5.2 Error Handling Strategy

**Опциональный шаг (is_optional=True):**

```python
class OptionalOCRStep(BaseProcessingStep):
    @property
    def is_optional(self) -> bool:
        return True  # OCR может провалиться, это не критично
    
    def process(self, context: MediaContext) -> MediaContext:
        # Если Gemini API упал, pipeline продолжится
        ocr_text = gemini_api.extract_ocr(...)  # Может выбросить APIError
        ...
```

**Логирование:**

```
⚠️  [ocr] Optional step failed (continuing)
    error: Gemini API rate limit exceeded
    path: /path/to/video.mp4
```

**Критичный шаг (is_optional=False):**

```python
class SummaryStep(BaseProcessingStep):
    @property
    def is_optional(self) -> bool:
        return False  # Summary обязателен
    
    def process(self, context: MediaContext) -> MediaContext:
        # Если провалился, весь pipeline останавливается
        ...
```

**Логирование:**

```
🔥 [summary] Critical step failed (stopping)
    error: Analysis dict missing 'description' key
    executed_steps: []
    path: /path/to/audio.mp3
```

### 5.3 Dynamic Step Registration

```python
pipeline = MediaPipeline([SummaryStep()])

# Добавить в конец
pipeline.register_step(TranscriptionStep(splitter), position=None)

# Вставить на позицию 1 (между summary и transcript)
pipeline.register_step(SentimentStep(), position=1)

# Финальный порядок:
# 0: SummaryStep
# 1: SentimentStep (custom)
# 2: TranscriptionStep
```

---

## 6. Тестирование — 25 unit-тестов

### 6.1 MediaContext Tests (13 тестов)

**Файл:** `tests/unit/core/test_media_context.py`

**Покрытие:**

```python
class TestMediaContextImmutability:
    def test_cannot_modify_fields_directly():
        """Проверяет frozen dataclass."""
        context = MediaContext(...)
        
        with pytest.raises(Exception):  # FrozenInstanceError
            context.base_index = 10
    
    def test_with_chunks_creates_new_object():
        """Проверяет, что оригинал не меняется."""
        original = MediaContext(chunks=[], base_index=0)
        updated = original.with_chunks([chunk])
        
        assert updated is not original
        assert len(original.chunks) == 0  # Не изменился

class TestWithChunks:
    def test_increments_base_index_by_default():
        """Проверяет автоинкремент."""
        context = MediaContext(base_index=0)
        updated = context.with_chunks([chunk1, chunk2, chunk3])
        
        assert updated.base_index == 3

class TestServiceLocator:
    def test_get_service_returns_value():
        """Проверяет Service Locator."""
        context = MediaContext(services={"splitter": mock_splitter})
        
        assert context.get_service("splitter") is mock_splitter
```

**Результаты:**

```
tests/unit/core/test_media_context.py::TestMediaContextImmutability::test_cannot_modify_fields_directly PASSED
tests/unit/core/test_media_context.py::TestMediaContextImmutability::test_with_chunks_creates_new_object PASSED
tests/unit/core/test_media_context.py::TestWithChunks::test_adds_chunks_to_list PASSED
tests/unit/core/test_media_context.py::TestWithChunks::test_increments_base_index_by_default PASSED
tests/unit/core/test_media_context.py::TestWithChunks::test_increment_index_false_preserves_base_index PASSED
tests/unit/core/test_media_context.py::TestWithChunks::test_preserves_existing_chunks PASSED
tests/unit/core/test_media_context.py::TestServiceLocator::test_get_service_returns_value PASSED
tests/unit/core/test_media_context.py::TestServiceLocator::test_get_service_returns_default_if_not_found PASSED
tests/unit/core/test_media_context.py::TestServiceLocator::test_get_service_returns_none_if_not_found_and_no_default PASSED
tests/unit/core/test_media_context.py::TestUserInstructions::test_user_instructions_optional PASSED
tests/unit/core/test_media_context.py::TestUserInstructions::test_user_instructions_can_be_set PASSED
tests/unit/core/test_media_context.py::TestUserInstructions::test_user_instructions_preserved_in_with_chunks PASSED
tests/unit/core/test_media_context.py::TestMediaContextIntegration::test_sequential_chunk_addition PASSED

========================================== 13 passed in 0.05s ==========================================
```

### 6.2 MediaPipeline Tests (12 тестов)

**Файл:** `tests/unit/core/test_media_pipeline.py`

**Покрытие:**

```python
class MockStep(BaseProcessingStep):
    """Mock для тестирования pipeline без реальных зависимостей."""
    
    def __init__(
        self,
        name: str,
        add_chunks: int = 1,
        should_run_result: bool = True,
        raise_error: bool = False,
    ):
        self._name = name
        self.process_called = False  # Для отслеживания вызовов

class TestMediaPipelineExecution:
    def test_executes_all_steps_in_order():
        """Проверяет выполнение всех шагов."""
        step1 = MockStep("step1", add_chunks=1)
        step2 = MockStep("step2", add_chunks=2)
        
        pipeline = MediaPipeline([step1, step2])
        result = pipeline.build_chunks(context)
        
        assert step1.process_called
        assert step2.process_called
        assert len(result.chunks) == 3  # 1 + 2

class TestErrorHandling:
    def test_optional_step_error_continues_pipeline():
        """Проверяет обработку ошибок в optional steps."""
        step1 = MockStep("step1")
        step2 = MockStep("step2", raise_error=True, is_optional=True)
        step3 = MockStep("step3")
        
        pipeline = MediaPipeline([step1, step2, step3])
        result = pipeline.build_chunks(context)  # Не должно упасть
        
        assert len(result.chunks) == 2  # step2 пропущен
```

**Результаты:**

```
tests/unit/core/test_media_pipeline.py::TestMediaPipelineExecution::test_executes_all_steps_in_order PASSED
tests/unit/core/test_media_pipeline.py::TestMediaPipelineExecution::test_skips_steps_with_should_run_false PASSED
tests/unit/core/test_media_pipeline.py::TestMediaPipelineExecution::test_preserves_context_immutability PASSED
tests/unit/core/test_media_pipeline.py::TestErrorHandling::test_optional_step_error_continues_pipeline PASSED
tests/unit/core/test_media_pipeline.py::TestErrorHandling::test_critical_step_error_stops_pipeline PASSED
tests/unit/core/test_media_pipeline.py::TestErrorHandling::test_unexpected_error_wrapped_in_processing_step_error PASSED
tests/unit/core/test_media_pipeline.py::TestRegisterStep::test_register_step_appends_by_default PASSED
tests/unit/core/test_media_pipeline.py::TestRegisterStep::test_register_step_at_position PASSED
tests/unit/core/test_media_pipeline.py::TestLogging::test_logs_pipeline_start_and_completion PASSED
tests/unit/core/test_media_pipeline.py::TestLogging::test_logs_step_execution PASSED
tests/unit/core/test_media_pipeline.py::TestLogging::test_logs_optional_step_failure PASSED
tests/unit/core/test_media_pipeline.py::TestIntegration::test_realistic_pipeline_with_summary_transcript_ocr PASSED

========================================== 12 passed in 0.08s ==========================================
```

---

## 7. Примеры использования

### 7.1 Базовый сценарий (будущий код)

```python
from semantic_core.core.media_pipeline import MediaPipeline
from semantic_core.core.media_context import MediaContext
from semantic_core.processing.steps import (
    SummaryStep,
    TranscriptionStep,
    OCRStep,
)

# Создаём pipeline
pipeline = MediaPipeline([
    SummaryStep(),
    TranscriptionStep(splitter=SmartSplitter()),
    OCRStep(splitter=SmartSplitter(), parser_mode="markdown"),
])

# Создаём контекст
context = MediaContext(
    media_path=Path("video.mp4"),
    document=Document(...),
    analysis={"type": "video", "description": "..."},
    chunks=[],
    base_index=0,
    services={"splitter": SmartSplitter()},
)

# Выполняем обработку
final_context = pipeline.build_chunks(context)

# Получаем чанки для сохранения в БД
chunks = final_context.chunks  # [summary, transcript1, transcript2, ocr1, ...]
```

### 7.2 Кастомный шаг

```python
class SentimentAnalysisStep(BaseProcessingStep):
    """Анализирует sentiment транскрипции через LLM."""
    
    def __init__(self, llm_provider: LLMProvider):
        self.llm_provider = llm_provider
    
    @property
    def step_name(self) -> str:
        return "sentiment"
    
    def should_run(self, context: MediaContext) -> bool:
        # Только для audio/video с транскрипцией
        return context.analysis.get("transcription") is not None
    
    def process(self, context: MediaContext) -> MediaContext:
        transcription = context.analysis["transcription"]
        
        # Анализируем через LLM
        sentiment = self.llm_provider.analyze_sentiment(transcription)
        
        # Создаём metadata chunk
        sentiment_chunk = Chunk(
            content="",
            chunk_index=context.base_index,
            metadata={
                "role": "metadata",
                "sentiment": sentiment,  # "positive", "negative", "neutral"
            },
        )
        
        return context.with_chunks([sentiment_chunk])

# Использование
pipeline = MediaPipeline([
    SummaryStep(),
    TranscriptionStep(splitter),
    SentimentAnalysisStep(llm_provider=gemini_llm),  # Кастомный шаг
    OCRStep(splitter),
])
```

---

## 8. Следующие шаги

### 8.1 Phase 14.1.1: Smart Steps (Week 2)

**Задачи:**

- [ ] Реализовать `SummaryStep` (извлечь логику из `_build_content_from_analysis()`)
- [ ] Реализовать `TranscriptionStep` с Constructor Injection `splitter`
- [ ] Реализовать `OCRStep` с поддержкой `parser_mode="markdown"`
- [ ] Unit-тесты для каждого шага (с моками analyzers/splitters)

**Ожидаемые файлы:**

```
semantic_core/processing/steps/
├── __init__.py
├── base.py               # ✅ Готово (Phase 14.1.0)
├── summary_step.py       # ⏳ Phase 14.1.1
├── transcription_step.py # ⏳ Phase 14.1.1
└── ocr_step.py           # ⏳ Phase 14.1.1
```

### 8.2 Phase 14.1.2: Advanced Features (Week 2-3)

**Задачи:**

- [ ] `TimecodeParser` — извлечение `[MM:SS]` из транскрипций
- [ ] `user_instructions` поле в `MediaContext` (для кастомных промптов)
- [ ] Интеграция `TimecodeParser` в `TranscriptionStep`
- [ ] **ОПЦИОНАЛЬНО:** `RetryParser` для legacy analyzers (если не мигрируем на `response_schema`)

### 8.3 Phase 14.1.3: Integration (Week 3)

**Задачи:**

- [ ] Добавить `MediaPipeline` в `SemanticCore.__init__()`
- [ ] Обновить `ingest_audio/video/image()` с параметром `user_prompt`
- [ ] **CRITICAL:** Мигрировать analyzers на Pydantic `response_schema`
- [ ] Обновить промпты с инструкциями для таймкодов `[MM:SS]`

---

## 📊 Метрики завершения Phase 14.1.0

**Code Metrics:**

- ✅ **3 новых модуля:** `media_context.py`, `media_pipeline.py`, `steps/base.py`
- ✅ **25 unit-тестов:** 100% passing (13 MediaContext + 12 MediaPipeline)
- ✅ **0 flake8 warnings** (clean code)

**Architecture Principles:**

- ✅ **SOLID:** Single Responsibility (каждый шаг делает одно дело)
- ✅ **Immutability:** Frozen dataclass для безопасности
- ✅ **Dependency Injection:** Service Locator для опциональных зависимостей
- ✅ **Open/Closed:** Легко добавлять новые шаги без изменения pipeline

**Готовность к следующей фазе:**

- ✅ Фундамент step-based архитектуры завершён
- ✅ Все тесты проходят
- ✅ Документация написана (эта статья)
- ✅ Можно переходить к реализации конкретных шагов (Phase 14.1.1)

---

**Конец статьи 75**  
**Следующая статья:** Phase 14.1.1 — SummaryStep, TranscriptionStep, OCRStep Implementation
