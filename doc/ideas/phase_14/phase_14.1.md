# 🏗️ Phase 14.1: Pipeline Abstraction & ProcessingStep Architecture

**Дата:** 2025-12-06  
**Статус:** Planning  
**Зависимости:** Phase 14.0 (Smart-Splitter интеграция)  
**Цель:** Рефакторинг монолитного `pipeline.py` → модульная step-based система

---

## 📋 Оглавление

1. [Мотивация и проблемы текущей архитектуры](#1-мотивация-и-проблемы-текущей-архитектуры)
2. [Целевая архитектура ProcessingStep](#2-целевая-архитектура-processingstep)
3. [План реализации](#3-план-реализации)
4. [Обновление промптов для Markdown-ответов](#4-обновление-промптов-для-markdown-ответов)
5. [E2E Testing Strategy](#5-e2e-testing-strategy)
6. [Риски и ограничения](#6-риски-и-ограничения)

---

## 1. Мотивация и проблемы текущей архитектуры

### 1.1 Текущее состояние `pipeline.py`

**Проблемные методы:**

| Метод | Строки | Проблема |
|-------|--------|----------|
| `_build_media_chunks()` | 1394-1454 | Монолитная логика: summary + transcript + OCR в одном методе |
| `_split_transcription_into_chunks()` | 1456-1482 | Дублирование логики с `_split_ocr_into_chunks()` |
| `_split_ocr_into_chunks()` | 1484-1518 | Жёсткая связанность с `self.splitter` |
| `ingest_image()` / `ingest_audio()` / `ingest_video()` | 703-1029 | Дублированная логика вызова `_build_media_chunks()` |

**Что невозможно без рефакторинга:**

❌ Добавить `SentimentStep` без изменения `_build_media_chunks()`  
❌ Переопределить промпт для OCR без форка кода  
❌ Перезапустить только транскрипцию без re-analyze всего видео  
❌ A/B тестировать разные стратегии чанкинга  
❌ Добавить кастомный шаг извлечения таймкодов

### 1.2 Целевая модель расширяемости

**Пример использования (после рефакторинга):**

```python
from semantic_core.processing.steps import SummaryStep, TranscriptionStep, OCRStep
from my_custom_steps import AdSpotDetectionStep, SentimentAnalysisStep

# Базовая конфигурация
pipeline = SemanticCore.create_with_steps([
    SummaryStep(),
    TranscriptionStep(chunk_size=1500),
    OCRStep(parser_mode="markdown"),
])

# Кастомизация для маркетинга
marketing_pipeline = SemanticCore.create_with_steps([
    SummaryStep(prompt_template="Summarize in pirate speak style"),
    TranscriptionStep(),
    AdSpotDetectionStep(),  # Извлекает таймкоды рекламных интеграций
])

# Повторный запуск одного шага
pipeline.rerun_step("summary", document_id="abc-123")
```

---

## 2. Целевая архитектура ProcessingStep

### 2.1 Интерфейс `BaseProcessingStep`

**Файл:** `semantic_core/processing/steps/base.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Any
from pathlib import Path

from semantic_core.domain import Chunk, Document


@dataclass
class MediaContext:
    """Контекст обработки медиа-файла.
    
    Immutable объект, передаваемый между шагами.
    Шаги возвращают обновлённый контекст через copy.
    """
    
    # Входные данные
    media_path: Path
    document: Document
    analysis: dict[str, Any]  # Результат от Gemini API
    
    # Накопленные чанки
    chunks: List[Chunk]
    
    # Индексация
    base_index: int
    
    def with_chunks(self, new_chunks: List[Chunk], increment_index: bool = True) -> "MediaContext":
        """Возвращает новый контекст с добавленными чанками."""
        from copy import copy
        ctx = copy(self)
        ctx.chunks = self.chunks + new_chunks
        if increment_index:
            ctx.base_index = self.base_index + len(new_chunks)
        return ctx


class BaseProcessingStep(ABC):
    """Базовый класс для шага обработки медиа."""
    
    @property
    @abstractmethod
    def step_name(self) -> str:
        """Уникальное имя шага (для логирования и re-run)."""
        pass
    
    @abstractmethod
    def process(self, context: MediaContext) -> MediaContext:
        """Обрабатывает контекст и возвращает обновлённый.
        
        Args:
            context: Текущий контекст обработки.
            
        Returns:
            Новый MediaContext с добавленными чанками.
            
        Raises:
            ProcessingStepError: При ошибках обработки (не критично для пайплайна).
        """
        pass
    
    @property
    def is_optional(self) -> bool:
        """Если True, ошибка шага не останавливает пайплайн."""
        return False
    
    def should_run(self, context: MediaContext) -> bool:
        """Проверяет, нужно ли запускать шаг для данного контекста.
        
        Пример: TranscriptionStep пропускается, если analysis["transcription"] пустой.
        """
        return True


class ProcessingStepError(Exception):
    """Исключение при ошибке обработки в шаге."""
    
    def __init__(self, step_name: str, message: str, context: Optional[MediaContext] = None):
        self.step_name = step_name
        self.context = context
        super().__init__(f"[{step_name}] {message}")
```

### 2.2 Реализация стандартных шагов

#### 2.2.1 SummaryStep

**Файл:** `semantic_core/processing/steps/summary_step.py`

```python
from pathlib import Path
from typing import Optional

from semantic_core.domain import Chunk, ChunkType
from semantic_core.processing.steps.base import BaseProcessingStep, MediaContext
from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)


class SummaryStep(BaseProcessingStep):
    """Создаёт summary chunk из результата анализа.
    
    Attributes:
        chunk_type_map: Маппинг media type → ChunkType для summary.
    """
    
    CHUNK_TYPE_MAP = {
        "image": ChunkType.IMAGE_REF,
        "audio": ChunkType.AUDIO_REF,
        "video": ChunkType.VIDEO_REF,
    }
    
    def __init__(self, include_keywords: bool = True):
        """Инициализация.
        
        Args:
            include_keywords: Включать ли keywords в metadata summary чанка.
        """
        self.include_keywords = include_keywords
    
    @property
    def step_name(self) -> str:
        return "summary"
    
    def process(self, context: MediaContext) -> MediaContext:
        """Создаёт summary chunk."""
        logger.info(f"[{self.step_name}] Creating summary chunk", path=str(context.media_path))
        
        analysis = context.analysis
        media_type = analysis.get("type", "unknown")
        
        # Формируем content (только description, без transcript/OCR)
        summary_content = self._build_summary_content(analysis)
        
        # Формируем metadata
        summary_metadata = self._build_summary_metadata(analysis, context.media_path)
        summary_metadata["role"] = "summary"
        
        # Определяем chunk_type
        chunk_type = self.CHUNK_TYPE_MAP.get(media_type, ChunkType.TEXT)
        
        # Создаём chunk
        summary_chunk = Chunk(
            content=summary_content,
            chunk_index=context.base_index,
            chunk_type=chunk_type,
            metadata=summary_metadata,
        )
        
        logger.debug(
            f"[{self.step_name}] Summary created",
            chunk_type=chunk_type.value,
            content_length=len(summary_content),
        )
        
        return context.with_chunks([summary_chunk])
    
    def _build_summary_content(self, analysis: dict) -> str:
        """Формирует текст для summary chunk (без transcript/OCR)."""
        media_type = analysis.get("type", "unknown")
        
        if media_type == "image":
            return analysis.get("description", "")
        elif media_type in ("audio", "video"):
            # Только description, transcript будет в отдельных чанках
            return analysis.get("description", "")
        
        return ""
    
    def _build_summary_metadata(self, analysis: dict, media_path: Path) -> dict:
        """Формирует metadata для summary chunk."""
        metadata = {"_original_path": str(media_path)}
        media_type = analysis.get("type", "unknown")
        
        if media_type == "image":
            metadata["_vision_alt"] = analysis.get("alt_text", "")
            if self.include_keywords:
                metadata["_vision_keywords"] = analysis.get("keywords", [])
            if analysis.get("ocr_text"):
                metadata["_vision_ocr"] = analysis["ocr_text"]
        
        elif media_type == "audio":
            metadata["_audio_description"] = analysis.get("description", "")
            if self.include_keywords:
                metadata["_audio_keywords"] = analysis.get("keywords", [])
            metadata["_audio_participants"] = analysis.get("participants", [])
            metadata["_audio_action_items"] = analysis.get("action_items", [])
            if analysis.get("duration_seconds"):
                metadata["_audio_duration"] = analysis["duration_seconds"]
        
        elif media_type == "video":
            if self.include_keywords:
                metadata["_video_keywords"] = analysis.get("keywords", [])
            if analysis.get("duration_seconds"):
                metadata["_video_duration"] = analysis["duration_seconds"]
        
        return metadata
```

#### 2.2.2 TranscriptionStep

**Файл:** `semantic_core/processing/steps/transcription_step.py`

```python
from pathlib import Path
from typing import Optional

from semantic_core.domain import Chunk, Document, MediaType
from semantic_core.interfaces.splitter import BaseSplitter
from semantic_core.processing.steps.base import BaseProcessingStep, MediaContext
from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)


class TranscriptionStep(BaseProcessingStep):
    """Разбивает транскрипцию на чанки через SmartSplitter.
    
    Attributes:
        splitter: Экземпляр BaseSplitter для чанкинга.
        chunk_size_override: Переопределение chunk_size (если None, используется из splitter).
    """
    
    def __init__(
        self,
        splitter: BaseSplitter,
        chunk_size_override: Optional[int] = None,
    ):
        """Инициализация.
        
        Args:
            splitter: Сплиттер для разбиения транскрипции.
            chunk_size_override: Специфичный размер чанка для транскрипций.
        """
        self.splitter = splitter
        self.chunk_size_override = chunk_size_override
    
    @property
    def step_name(self) -> str:
        return "transcription"
    
    def should_run(self, context: MediaContext) -> bool:
        """Запускаем только если есть transcription в analysis."""
        return bool(context.analysis.get("transcription"))
    
    def process(self, context: MediaContext) -> MediaContext:
        """Разбивает транскрипцию на чанки."""
        transcription = context.analysis["transcription"]
        
        logger.info(
            f"[{self.step_name}] Splitting transcription",
            path=str(context.media_path),
            length=len(transcription),
        )
        
        # Создаём временный Document
        temp_doc = Document(
            content=transcription,
            metadata={"source": str(context.media_path)},
            media_type=MediaType.TEXT,
        )
        
        # Режем через splitter
        # TODO: Если chunk_size_override задан, нужно временно изменить splitter.chunk_size
        split_chunks = self.splitter.split(temp_doc)
        
        # Обогащаем metadata
        transcript_chunks = []
        for idx, chunk in enumerate(split_chunks):
            meta = dict(chunk.metadata or {})
            meta.setdefault("_original_path", str(context.media_path))
            meta["role"] = "transcript"
            meta["parent_media_path"] = str(context.media_path)
            
            chunk.chunk_index = context.base_index + idx
            chunk.metadata = meta
            
            transcript_chunks.append(chunk)
        
        logger.info(
            f"[{self.step_name}] Created chunks",
            count=len(transcript_chunks),
            avg_size=sum(len(c.content) for c in transcript_chunks) // len(transcript_chunks) if transcript_chunks else 0,
        )
        
        return context.with_chunks(transcript_chunks)
```

#### 2.2.3 OCRStep

**Файл:** `semantic_core/processing/steps/ocr_step.py`

```python
from pathlib import Path
from typing import Literal, Optional

from semantic_core.domain import Chunk, Document, MediaType
from semantic_core.interfaces.splitter import BaseSplitter
from semantic_core.processing.steps.base import BaseProcessingStep, MediaContext
from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)


class OCRStep(BaseProcessingStep):
    """Разбивает OCR текст на чанки через SmartSplitter.
    
    Поддерживает Markdown-парсинг для обнаружения code blocks в видео с кодом.
    
    Attributes:
        splitter: Экземпляр BaseSplitter.
        parser_mode: "markdown" (детектит code blocks) или "plain" (просто текст).
        chunk_size_override: Переопределение chunk_size для OCR.
    """
    
    def __init__(
        self,
        splitter: BaseSplitter,
        parser_mode: Literal["markdown", "plain"] = "markdown",
        chunk_size_override: Optional[int] = None,
    ):
        """Инициализация.
        
        Args:
            splitter: Сплиттер для разбиения OCR текста.
            parser_mode: Режим парсинга ("markdown" рекомендуется для видео с кодом).
            chunk_size_override: Специфичный размер чанка для OCR.
        """
        self.splitter = splitter
        self.parser_mode = parser_mode
        self.chunk_size_override = chunk_size_override
    
    @property
    def step_name(self) -> str:
        return "ocr"
    
    def should_run(self, context: MediaContext) -> bool:
        """Запускаем только если есть ocr_text в analysis."""
        return bool(context.analysis.get("ocr_text"))
    
    def process(self, context: MediaContext) -> MediaContext:
        """Разбивает OCR текст на чанки."""
        ocr_text = context.analysis["ocr_text"]
        
        logger.info(
            f"[{self.step_name}] Splitting OCR text",
            path=str(context.media_path),
            parser_mode=self.parser_mode,
            length=len(ocr_text),
        )
        
        # Определяем media_type для Document (влияет на парсинг)
        media_type = MediaType.MARKDOWN if self.parser_mode == "markdown" else MediaType.TEXT
        
        # Создаём временный Document
        temp_doc = Document(
            content=ocr_text,
            metadata={"source": str(context.media_path)},
            media_type=media_type,
        )
        
        # Режем через splitter
        split_chunks = self.splitter.split(temp_doc)
        
        # Обогащаем metadata
        ocr_chunks = []
        for idx, chunk in enumerate(split_chunks):
            meta = dict(chunk.metadata or {})
            meta.setdefault("_original_path", str(context.media_path))
            meta["role"] = "ocr"
            meta["parent_media_path"] = str(context.media_path)
            
            chunk.chunk_index = context.base_index + idx
            chunk.metadata = meta
            
            ocr_chunks.append(chunk)
        
        # Считаем статистику code chunks (для мониторинга ложных срабатываний)
        code_chunks = [c for c in ocr_chunks if c.chunk_type.value == "code"]
        code_ratio = len(code_chunks) / len(ocr_chunks) if ocr_chunks else 0
        
        logger.info(
            f"[{self.step_name}] Created chunks",
            count=len(ocr_chunks),
            code_chunks=len(code_chunks),
            code_ratio=f"{code_ratio:.2%}",
        )
        
        # WARNING: Если code_ratio > 50%, возможны ложные срабатывания (UI text)
        if code_ratio > 0.5:
            logger.warning(
                f"[{self.step_name}] High code ratio detected (possibly UI text misdetected as code)",
                code_ratio=f"{code_ratio:.2%}",
                path=str(context.media_path),
            )
        
        return context.with_chunks(ocr_chunks)
```

### 2.3 Pipeline Executor в SemanticCore

**Модификация:** `semantic_core/pipeline.py`

```python
from typing import List, Optional
from semantic_core.processing.steps.base import (
    BaseProcessingStep,
    MediaContext,
    ProcessingStepError,
)


class SemanticCore:
    """Добавляем step-based processing."""
    
    def __init__(
        self,
        # ... существующие параметры ...
        processing_steps: Optional[List[BaseProcessingStep]] = None,
    ):
        # ... существующая инициализация ...
        
        # Инициализируем steps (если не переданы, используем дефолтные)
        self._processing_steps = processing_steps or self._create_default_steps()
    
    def _create_default_steps(self) -> List[BaseProcessingStep]:
        """Создаёт стандартный набор шагов обработки."""
        from semantic_core.processing.steps import SummaryStep, TranscriptionStep, OCRStep
        
        return [
            SummaryStep(),
            TranscriptionStep(splitter=self.splitter),
            OCRStep(splitter=self.splitter, parser_mode="markdown"),
        ]
    
    def _build_media_chunks_v2(
        self,
        document: Document,
        media_path: Path,
        chunk_type: ChunkType,
        analysis: Optional[dict],
        fallback_metadata: Optional[dict] = None,
    ) -> list[Chunk]:
        """NEW: Step-based версия _build_media_chunks().
        
        Заменит старый метод после миграции.
        """
        if analysis is None:
            # Fallback: создаём один чанк
            return [
                Chunk(
                    content=str(media_path),
                    chunk_index=0,
                    chunk_type=chunk_type,
                    metadata=dict(fallback_metadata or {}),
                )
            ]
        
        # Инициализируем контекст
        context = MediaContext(
            media_path=media_path,
            document=document,
            analysis=analysis,
            chunks=[],
            base_index=0,
        )
        
        # Прогоняем через все шаги
        for step in self._processing_steps:
            try:
                # Проверяем, нужно ли запускать шаг
                if not step.should_run(context):
                    logger.debug(
                        f"Skipping step (condition not met)",
                        step=step.step_name,
                        path=str(media_path),
                    )
                    continue
                
                # Запускаем шаг
                context = step.process(context)
                
            except ProcessingStepError as e:
                # Если шаг опциональный, логируем и продолжаем
                if step.is_optional:
                    logger.warning(
                        f"Optional step failed",
                        step=step.step_name,
                        error=str(e),
                    )
                    continue
                else:
                    # Критический шаг — прерываем пайплайн
                    logger.error(
                        f"Critical step failed",
                        step=step.step_name,
                        error=str(e),
                    )
                    raise
        
        logger.info(
            f"Media processing completed",
            path=str(media_path),
            total_chunks=len(context.chunks),
            steps_executed=len(self._processing_steps),
        )
        
        return context.chunks
    
    def register_step(self, step: BaseProcessingStep, position: Optional[int] = None) -> None:
        """Добавляет кастомный шаг в пайплайн.
        
        Args:
            step: Экземпляр ProcessingStep.
            position: Позиция в списке (None = добавить в конец).
        """
        if position is None:
            self._processing_steps.append(step)
        else:
            self._processing_steps.insert(position, step)
        
        logger.info(
            f"Registered processing step",
            step=step.step_name,
            position=position or len(self._processing_steps) - 1,
        )
    
    def rerun_step(
        self,
        step_name: str,
        document_id: str,
        delete_old_chunks: bool = True,
    ) -> int:
        """Перезапускает конкретный шаг для существующего документа.
        
        Args:
            step_name: Имя шага (например, "summary", "transcription").
            document_id: ID документа в БД.
            delete_old_chunks: Удалять ли старые чанки с этой ролью перед генерацией.
        
        Returns:
            Количество созданных чанков.
        
        Raises:
            ValueError: Если шаг с таким именем не найден.
        """
        # Находим шаг
        step = next((s for s in self._processing_steps if s.step_name == step_name), None)
        if step is None:
            raise ValueError(f"Step '{step_name}' not found in pipeline")
        
        # Загружаем документ и его задачу
        from semantic_core.infrastructure.storage.peewee.models import MediaTaskModel, ChunkModel
        
        task = MediaTaskModel.get_or_none(MediaTaskModel.result_document_id == document_id)
        if not task:
            raise ValueError(f"Document {document_id} has no associated media task")
        
        # Формируем analysis из задачи
        import json
        analysis = {
            "type": task.media_type,
            "description": task.result_description,
            "transcription": task.result_transcription,
            "keywords": json.loads(task.result_keywords) if task.result_keywords else None,
            "ocr_text": task.result_ocr_text,
            "duration_seconds": task.result_duration_seconds,
        }
        
        # Создаём контекст (без старых чанков)
        context = MediaContext(
            media_path=Path(task.file_path),
            document=self.store.get_document_by_id(document_id),
            analysis=analysis,
            chunks=[],
            base_index=0,  # TODO: Calculate actual index
        )
        
        # Удаляем старые чанки с этой ролью
        if delete_old_chunks:
            deleted = (
                ChunkModel.delete()
                .where(
                    (ChunkModel.document_id == document_id)
                    & (ChunkModel.metadata["role"].as_json() == step_name)
                )
                .execute()
            )
            logger.info(f"Deleted old chunks", step=step_name, count=deleted)
        
        # Запускаем шаг
        new_context = step.process(context)
        new_chunks = new_context.chunks
        
        # Сохраняем новые чанки
        # TODO: Implement partial chunk save in PeeweeVectorStore
        
        logger.info(
            f"Re-ran step",
            step=step_name,
            document_id=document_id,
            new_chunks=len(new_chunks),
        )
        
        return len(new_chunks)
```

---

## 3. План реализации

### 3.1 Этапы разработки

**Неделя 1: Инфраструктура**

- [ ] Создать `semantic_core/processing/steps/` пакет
- [ ] Реализовать `BaseProcessingStep` и `MediaContext`
- [ ] Добавить `ProcessingStepError` в exceptions
- [ ] Написать unit-тесты для `MediaContext.with_chunks()`

**Неделя 2: Стандартные шаги**

- [ ] Реализовать `SummaryStep`
- [ ] Реализовать `TranscriptionStep`
- [ ] Реализовать `OCRStep` с поддержкой `parser_mode`
- [ ] Написать unit-тесты для каждого шага (с моками)

**Неделя 3: Интеграция в pipeline**

- [ ] Добавить `_processing_steps` в `SemanticCore.__init__()`
- [ ] Реализовать `_build_media_chunks_v2()` через step executor
- [ ] Реализовать `register_step()` для кастомизации
- [ ] Реализовать `rerun_step()` для идемпотентности
- [ ] Написать E2E тесты (см. раздел 5)

**Неделя 4: Миграция и очистка**

- [ ] Заменить все вызовы `_build_media_chunks()` → `_build_media_chunks_v2()`
- [ ] Удалить legacy методы `_split_transcription_into_chunks()` и `_split_ocr_into_chunks()`
- [ ] Обновить документацию
- [ ] Обновить CLI для поддержки `rerun_step`

### 3.2 Dependency Injection Strategy

**Проблема:** Steps нуждаются в `splitter`, но также могут требовать `image_analyzer`, `rate_limiter` и т.д.

**Решение: Service Locator в MediaContext**

```python
@dataclass
class MediaContext:
    # ... существующие поля ...
    
    services: dict[str, Any] = field(default_factory=dict)
    
    def get_service(self, key: str, default: Any = None) -> Any:
        """Получает сервис из контекста."""
        return self.services.get(key, default)


# В SemanticCore._build_media_chunks_v2():
context = MediaContext(
    # ... 
    services={
        "splitter": self.splitter,
        "embedder": self.embedder,
        "rate_limiter": self._rate_limiter,
    },
)

# В TranscriptionStep.process():
splitter = context.get_service("splitter")
if splitter is None:
    raise ProcessingStepError(self.step_name, "Splitter service not available")
```

**Альтернатива (для простоты):** Передавать зависимости через конструктор шагов (текущий подход).

---

## 4. Обновление промптов для Markdown-ответов

### 4.1 Проблема с текущими промптами

**Текущие промпты** требуют JSON, но для транскрипций/OCR **лучше подходит Markdown**:

```python
# audio_analyzer.py:37
SYSTEM_PROMPT_TEMPLATE = """You are an audio analyst creating descriptions for semantic search indexing.
Response language: {language}

Return a JSON with:
- description: Brief summary
- transcription: Full verbatim text
- keywords: List of key terms
- participants: List of speakers
- action_items: List of tasks mentioned
"""
```

**Проблемы:**

1. **Потеря форматирования:** Транскрипции длинных лекций превращаются в «простыню текста» без параграфов
2. **Code blocks игнорируются:** OCR из видео с кодом возвращается как plain text, теряя синтаксис
3. **Невозможность вложенных списков:** Action items без иерархии

### 4.2 Целевые промпты (Markdown-first)

**Новый подход:** Разделить промпты для **метаданных** (JSON) и **контента** (Markdown).

#### AudioAnalyzer — Hybrid JSON+Markdown

```python
SYSTEM_PROMPT_TEMPLATE = """You are an audio analyst creating descriptions for semantic search indexing.
Response language: {language}

Return a JSON with the following structure:

{{
  "description": "Brief 2-3 sentence summary of the audio content",
  "keywords": ["keyword1", "keyword2", ...],
  "participants": ["Speaker1", "Speaker2", ...],
  "action_items": ["Task 1", "Task 2", ...],
  "duration_seconds": <number>,
  "transcription": "MARKDOWN_FORMATTED_TRANSCRIPT_HERE"
}}

CRITICAL INSTRUCTIONS FOR TRANSCRIPTION FIELD:
- Use Markdown formatting (paragraphs, headers, lists)
- Split long monologues into logical paragraphs (every 3-5 sentences)
- Use `## Speaker Name` headers for speaker changes
- Use `**bold**` for emphasis or key terms
- Use `> quote` for direct quotations
- For technical content, wrap code snippets in triple backticks with language:
  ```python
  def example():
      pass
  ```
- DO NOT escape newlines as \\n — use actual line breaks inside the JSON string

Example transcription format:

## Introduction

The speaker introduces the topic of semantic search and explains how embeddings work in modern NLP systems.

Key points:
- Embeddings capture semantic meaning
- Vector databases enable similarity search
- Context matters more than keywords

## Technical Deep Dive

Here's how we calculate cosine similarity:

```python
def cosine_similarity(a, b):
    return dot(a, b) / (norm(a) * norm(b))
```

This formula is fundamental to understanding vector search.
"""
```

#### VideoAnalyzer — OCR with Code Detection

```python
SYSTEM_PROMPT_TEMPLATE = """You are a video analyst creating descriptions for semantic search indexing.
Response language: {language}

Return a JSON with:

{{
  "description": "Brief summary",
  "keywords": ["keyword1", ...],
  "transcription": "MARKDOWN_FORMATTED_SPEECH_TRANSCRIPT",
  "ocr_text": "MARKDOWN_FORMATTED_VISUAL_TEXT",
  "duration_seconds": <number>
}}

CRITICAL INSTRUCTIONS FOR OCR_TEXT FIELD:
- Detect and preserve code blocks from screenshots/screencasts
- Wrap code in triple backticks with language:
  ```python
  class Example:
      pass
  ```
- Use `## Slide Title` headers for new slides
- Use bullet points for slide bullet lists:
  - Point 1
  - Point 2
- For UI text (buttons, labels), use plain text
- For diagrams/charts, describe structure in Markdown tables if possible

Example OCR output:

## Introduction to SOLID Principles

### Single Responsibility Principle

A class should have only one reason to change.

**Example:**

```python
class UserService:
    def validate(self, user): ...
    def save(self, user): ...
```

**Problem:** Mixes validation and persistence.

## Better Design

Split into two classes:

```python
class UserValidator:
    def validate(self, user): ...

class UserRepository:
    def save(self, user): ...
```
"""
```

### 4.3 Парсинг Markdown-ответов

**Challenge:** Gemini возвращает JSON с Markdown **внутри** строковых полей.

**Решение:** Используем `json.loads()` как обычно, Markdown парсится при создании `Document`:

```python
# В audio_analyzer.py:
response_json = json.loads(response.text)

# transcription уже содержит Markdown:
# "## Speaker 1\n\nHello world...\n\n```python\ndef foo(): pass\n```"

return {
    "type": "audio",
    "description": response_json["description"],
    "transcription": response_json["transcription"],  # ← Markdown string
    # ...
}

# В TranscriptionStep.process():
temp_doc = Document(
    content=analysis["transcription"],  # ← Markdown content
    media_type=MediaType.MARKDOWN,       # ← Включает MarkdownNodeParser
)
chunks = splitter.split(temp_doc)  # ← Парсит Markdown → изолирует code blocks
```

**Результат:** Code blocks из транскрипций **автоматически** детектятся и изолируются в отдельные чанки.

### 4.4 Migration Plan для промптов

**Phase 14.1.5: Промпты**

- [ ] Обновить `audio_analyzer.py:SYSTEM_PROMPT_TEMPLATE` (добавить Markdown инструкции)
- [ ] Обновить `video_analyzer.py:SYSTEM_PROMPT_TEMPLATE` (OCR code detection)
- [ ] Добавить E2E тест: отправить видео с кодом → проверить наличие CODE chunks
- [ ] Добавить E2E тест: отправить аудио лекцию → проверить параграфы в транскрипции
- [ ] Документировать формат промптов в `doc/architecture/`

**Риски:**

⚠️ **Gemini может игнорировать Markdown инструкции** (модели иногда упрямы)  
**Mitigation:** Добавить примеры в промпт (few-shot learning)

⚠️ **Парсинг JSON с Markdown может сломаться на неэкранированных кавычках**  
**Mitigation:** Использовать `response.text.strip()` + fallback на regex extraction

---

## 5. E2E Testing Strategy

### 5.1 Зачем E2E тесты?

**Unit-тесты** (текущие) проверяют изолированную логику:

```python
def test_summary_step_creates_chunk():
    step = SummaryStep()
    context = MediaContext(analysis={"type": "audio", "description": "Test"}, ...)
    result = step.process(context)
    assert len(result.chunks) == 1
```

❌ **Не проверяют:**

- Реальное сохранение в SQLite
- Позиции чанков в БД (`chunk_index`)
- Корректность эмбеддингов
- Взаимодействие шагов (base_index propagation)

**E2E тесты** проверяют **весь flow** от файла до БД:

```python
def test_video_with_code_creates_ocr_code_chunks(tmp_path, real_db):
    # Создаём тестовое видео с кодом на экране
    video_path = tmp_path / "python_tutorial.mp4"
    create_test_video_with_code(video_path)  # Helper
    
    # Индексируем через SemanticCore
    core = SemanticCore(db_path=real_db)
    doc_id = core.ingest_video(str(video_path), mode="sync")
    
    # Проверяем БД напрямую
    chunks = ChunkModel.select().where(ChunkModel.document_id == doc_id)
    
    # Assertions:
    assert chunks.count() >= 3  # summary + transcript + ocr
    
    # Проверяем summary chunk
    summary = chunks.where(ChunkModel.metadata["role"].as_json() == "summary").get()
    assert summary.chunk_index == 0
    assert summary.chunk_type == "video_ref"
    
    # Проверяем OCR code chunks
    code_chunks = chunks.where(
        (ChunkModel.metadata["role"].as_json() == "ocr")
        & (ChunkModel.chunk_type == "code")
    )
    assert code_chunks.count() >= 1  # Хотя бы один code block детектнут
    assert code_chunks[0].language == "python"
    
    # Проверяем chunk_index последовательность
    all_indexes = [c.chunk_index for c in chunks.order_by(ChunkModel.chunk_index)]
    assert all_indexes == list(range(len(all_indexes)))  # 0, 1, 2, 3, ...
    
    # Проверяем эмбеддинги
    for chunk in chunks:
        assert chunk.embedding is not None
        assert len(chunk.embedding) == 768  # Gemini embedding dimension
```

### 5.2 E2E Test Suite

**Файл:** `tests/e2e/test_media_pipeline_steps.py`

```python
import pytest
from pathlib import Path
from semantic_core import SemanticCore
from semantic_core.infrastructure.storage.peewee.models import ChunkModel, DocumentModel


@pytest.fixture
def core_with_steps(tmp_path):
    """Создаёт SemanticCore с реальной БД и step-based pipeline."""
    db_path = tmp_path / "test.db"
    core = SemanticCore(db_path=str(db_path))
    yield core
    core.close()


class TestAudioTranscriptionStep:
    """E2E тесты для TranscriptionStep с реальными аудио."""
    
    def test_long_audio_creates_multiple_transcript_chunks(self, core_with_steps, sample_audio_5min):
        """Проверяет, что 5-минутное аудио разбивается на несколько чанков."""
        doc_id = core_with_steps.ingest_audio(str(sample_audio_5min), mode="sync")
        
        chunks = list(ChunkModel.select().where(ChunkModel.document_id == doc_id))
        
        # Summary + N transcript chunks
        assert len(chunks) >= 5, "Expected at least 5 chunks for 5-min audio"
        
        # Проверяем summary
        summary = next(c for c in chunks if c.metadata.get("role") == "summary")
        assert summary.chunk_index == 0
        
        # Проверяем transcript chunks
        transcripts = [c for c in chunks if c.metadata.get("role") == "transcript"]
        assert len(transcripts) >= 4
        
        # Проверяем последовательность индексов
        for i, chunk in enumerate(transcripts):
            assert chunk.chunk_index == i + 1  # После summary
    
    def test_transcript_chunks_preserve_parent_path(self, core_with_steps, sample_audio_5min):
        """Проверяет, что все transcript чанки ссылаются на родительский файл."""
        doc_id = core_with_steps.ingest_audio(str(sample_audio_5min), mode="sync")
        
        transcripts = list(
            ChunkModel.select().where(
                (ChunkModel.document_id == doc_id)
                & (ChunkModel.metadata["role"].as_json() == "transcript")
            )
        )
        
        for chunk in transcripts:
            assert chunk.metadata["parent_media_path"] == str(sample_audio_5min)


class TestVideoOCRStep:
    """E2E тесты для OCRStep с Markdown parsing."""
    
    def test_video_with_code_screenshot_detects_code_blocks(
        self, core_with_steps, sample_video_with_code
    ):
        """Проверяет, что код на экране детектится как CODE chunks."""
        doc_id = core_with_steps.ingest_video(str(sample_video_with_code), mode="sync")
        
        code_chunks = list(
            ChunkModel.select().where(
                (ChunkModel.document_id == doc_id)
                & (ChunkModel.chunk_type == "code")
                & (ChunkModel.metadata["role"].as_json() == "ocr")
            )
        )
        
        assert len(code_chunks) >= 1, "Expected at least one CODE chunk from OCR"
        assert code_chunks[0].language in ("python", "javascript", "java")
    
    def test_video_ocr_markdown_headers_preserved(
        self, core_with_steps, sample_video_slides
    ):
        """Проверяет, что заголовки слайдов сохраняются в metadata."""
        doc_id = core_with_steps.ingest_video(str(sample_video_slides), mode="sync")
        
        ocr_chunks = list(
            ChunkModel.select().where(
                (ChunkModel.document_id == doc_id)
                & (ChunkModel.metadata["role"].as_json() == "ocr")
            )
        )
        
        # Проверяем, что хотя бы один чанк содержит header в metadata
        headers_found = any(
            chunk.metadata.get("headers") for chunk in ocr_chunks
        )
        assert headers_found, "Expected headers in OCR chunk metadata"


class TestStepIndexPropagation:
    """Проверяет корректность chunk_index при многошаговой обработке."""
    
    def test_chunk_indexes_are_sequential(self, core_with_steps, sample_video_full):
        """Проверяет, что индексы идут 0, 1, 2, 3... без пропусков."""
        doc_id = core_with_steps.ingest_video(str(sample_video_full), mode="sync")
        
        chunks = list(
            ChunkModel.select()
            .where(ChunkModel.document_id == doc_id)
            .order_by(ChunkModel.chunk_index)
        )
        
        expected_indexes = list(range(len(chunks)))
        actual_indexes = [c.chunk_index for c in chunks]
        
        assert actual_indexes == expected_indexes, "Chunk indexes must be sequential"
    
    def test_summary_always_first_transcript_second_ocr_last(
        self, core_with_steps, sample_video_full
    ):
        """Проверяет порядок шагов: summary → transcript → ocr."""
        doc_id = core_with_steps.ingest_video(str(sample_video_full), mode="sync")
        
        chunks = list(
            ChunkModel.select()
            .where(ChunkModel.document_id == doc_id)
            .order_by(ChunkModel.chunk_index)
        )
        
        roles = [c.metadata.get("role") for c in chunks]
        
        # Summary всегда первый
        assert roles[0] == "summary"
        
        # Transcript chunks идут подряд
        first_transcript_idx = roles.index("transcript")
        last_transcript_idx = len(roles) - 1 - roles[::-1].index("transcript")
        
        # OCR chunks идут после всех transcript
        if "ocr" in roles:
            first_ocr_idx = roles.index("ocr")
            assert first_ocr_idx > last_transcript_idx


class TestEmbeddings:
    """Проверяет корректность эмбеддингов."""
    
    def test_all_chunks_have_embeddings(self, core_with_steps, sample_audio_5min):
        """Проверяет, что все чанки получили эмбеддинги."""
        doc_id = core_with_steps.ingest_audio(str(sample_audio_5min), mode="sync")
        
        chunks = ChunkModel.select().where(ChunkModel.document_id == doc_id)
        
        for chunk in chunks:
            assert chunk.embedding is not None, f"Chunk {chunk.id} missing embedding"
            assert len(chunk.embedding) == 768, "Gemini embeddings are 768-dim"
    
    def test_code_chunks_embeddings_differ_from_text(
        self, core_with_steps, sample_video_with_code
    ):
        """Проверяет, что CODE и TEXT чанки имеют разные эмбеддинги."""
        import numpy as np
        
        doc_id = core_with_steps.ingest_video(str(sample_video_with_code), mode="sync")
        
        code_chunk = ChunkModel.get(
            (ChunkModel.document_id == doc_id) & (ChunkModel.chunk_type == "code")
        )
        text_chunk = ChunkModel.get(
            (ChunkModel.document_id == doc_id) & (ChunkModel.chunk_type == "text")
        )
        
        # Вычисляем cosine similarity
        code_vec = np.array(code_chunk.embedding)
        text_vec = np.array(text_chunk.embedding)
        similarity = np.dot(code_vec, text_vec) / (
            np.linalg.norm(code_vec) * np.linalg.norm(text_vec)
        )
        
        # Должны быть НЕ идентичными (similarity < 0.99)
        assert similarity < 0.99, "Code and text embeddings should differ"
```

### 5.3 Test Fixtures

**Файл:** `tests/fixtures/media_samples.py`

```python
import pytest
from pathlib import Path
import subprocess


@pytest.fixture(scope="session")
def sample_audio_5min(tmp_path_factory):
    """Создаёт 5-минутное тестовое аудио с синтезированной речью."""
    audio_path = tmp_path_factory.mktemp("media") / "sample_5min.mp3"
    
    # Генерируем через TTS (или используем pre-recorded файл)
    # Для CI: скачиваем с test assets
    download_test_asset("sample_5min.mp3", audio_path)
    
    return audio_path


@pytest.fixture(scope="session")
def sample_video_with_code(tmp_path_factory):
    """Создаёт видео с кодом на экране (Python tutorial screencast)."""
    video_path = tmp_path_factory.mktemp("media") / "python_tutorial.mp4"
    
    # Используем ffmpeg для создания видео из изображения с кодом
    create_video_from_code_image(video_path)
    
    return video_path


def create_video_from_code_image(output_path: Path):
    """Создаёт 10-секундное видео с кодом на экране."""
    # 1. Создаём PNG с кодом
    code_image = output_path.parent / "code.png"
    generate_code_screenshot(
        code="""
def calculate_similarity(a, b):
    return dot(a, b) / (norm(a) * norm(b))
""",
        output=code_image,
    )
    
    # 2. Конвертируем в видео
    subprocess.run([
        "ffmpeg", "-loop", "1", "-i", str(code_image),
        "-t", "10", "-pix_fmt", "yuv420p", str(output_path)
    ], check=True)
```

---

## 6. Риски и ограничения

### 6.1 Технические риски

| Риск | Вероятность | Влияние | Mitigation |
|------|-------------|---------|-----------|
| **Context mutation bugs** | Средняя | Высокое | Immutable dataclass + copy() |
| **Step dependency hell** | Низкая | Среднее | Service locator pattern |
| **False code detection in OCR** | Средняя | Низкое | Мониторинг code_ratio + config toggle |
| **Gemini игнорирует Markdown** | Средняя | Среднее | Few-shot examples в промпте |
| **Rerun step не обновляет embeddings** | Высокая | Критическое | TODO: Implement partial embedding update |

### 6.2 Ограничения Phase 14.1

**Что НЕ входит в эту фазу:**

❌ **Конфигурируемые промпты через TOML** — это Phase 14.3  
❌ **Плагинная система для кастомных шагов** — частично (только `register_step()`)  
❌ **Timeline extraction** (timestamps для видео) — это Phase 14.2  
❌ **Re-run с новым анализом** — текущий rerun использует старый analysis из БД  
❌ **Partial embedding update** — rerun пересоздаёт чанки, но embeddings нужно пересчитывать отдельно

### 6.3 Защита от инъекций

**Решение:** Не требуется для локального личного софта.

**Обоснование:**

- SemanticCore запускается локально, нет внешних пользователей
- Flask App (если используется) работает на localhost
- Нет публичного API endpoint

**Если потребуется в будущем (Phase 15+):**

- Валидация `step_name` через whitelist
- Pydantic валидация для `MediaContext`
- Rate limiting для `rerun_step()`

---

## 7. Success Metrics

### 7.1 Критерии завершения фазы

**Code Metrics:**

- ✅ 100% покрытие unit-тестами для `BaseProcessingStep`, `MediaContext`
- ✅ E2E тесты проходят для audio (5 min), video (с кодом), video (слайды)
- ✅ Chunk indexes последовательны (0, 1, 2...) в 100% случаев
- ✅ Code detection в OCR работает с точностью >80% (на тестовых видео)

**Performance:**

- ✅ Индексация 5-минутного аудио < 30 секунд (sync mode)
- ✅ Memory overhead от step executor < 10% (vs legacy)

**Documentation:**

- ✅ Architecture article написана (`doc/architecture/74_processing_steps.md`)
- ✅ Примеры кастомных шагов в `examples/custom_steps/`
- ✅ Migration guide для пользователей с Phase 14.0

### 7.2 Rollback Plan

**Если Phase 14.1 провалится:**

1. Откатываем к Phase 14.0 (legacy `_build_media_chunks()` остаётся рабочим)
2. Step-based методы (`_build_media_chunks_v2()`) удаляем
3. Markdown промпты откатываем к JSON-only

**Критерий провала:** E2E тесты не проходят после 2 недель отладки.

---

## 8. Next Steps

После завершения Phase 14.1:

**Phase 14.2: Aggregation & Service Layer**

- `MediaService.get_media_details(doc_id)` — сборка чанков в DTO
- Flask UI для `/media/<id>` с timeline
- Search filters по `role` (только transcript, только OCR)

**Phase 14.3: User Flexibility**

- Конфигурируемые промпты через `semantic.toml`
- `ocr_parser_mode` config field
- Per-role chunk sizing (`transcript_chunk_size`, `ocr_chunk_size`)
- Full rerun с новым анализом (не из кэша БД)

---

**End of Phase 14.1 Plan**  
**Status:** Ready for implementation  
**Estimated Duration:** 3-4 weeks  
**Team:** 1 senior engineer + 1 QA for E2E tests
