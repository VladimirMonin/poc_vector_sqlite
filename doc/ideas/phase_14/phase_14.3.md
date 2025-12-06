# ⚙️ Phase 14.3: User Flexibility & Configuration

**Дата:** 2025-12-06  
**Статус:** Planning  
**Зависимости:** Phase 14.1 (ProcessingStep), Phase 14.2 (MediaService)  
**Цель:** Сделать систему гибкой через конфигурацию без изменения кода

---

## 📋 Оглавление

1. [Мотивация — почему нужна гибкость](#1-мотивация--почему-нужна-гибкость)
2. [Конфигурируемые промпты через TOML](#2-конфигурируемые-промпты-через-toml)
3. [Per-role chunk sizing](#3-per-role-chunk-sizing)
4. [Full rerun с новым анализом](#4-full-rerun-с-новым-анализом)
5. [OCR parser mode в конфиге](#5-ocr-parser-mode-в-конфиге)
6. [План реализации](#6-план-реализации)

---

## 1. Мотивация — почему нужна гибкость

### 1.1 Текущие ограничения (после Phase 14.1-14.2)

**Проблемы для пользователя:**

❌ **Промпты захардкожены** — нельзя изменить стиль анализа без правки кода  
❌ **Chunk size единый** — transcript и OCR используют одинаковый размер (1800 токенов)  
❌ **Rerun использует старый analysis** — нельзя пересоздать summary с новым промптом  
❌ **Parser mode статичен** — OCRStep всегда "markdown", нельзя переключить на "plain"

**Сценарии, которые невозможны:**

1. **Кастомизация для домена:**

   ```
   Пользователь хочет анализировать медицинские лекции.
   Нужен промпт: "Extract medical terms, dosages, and diagnoses"
   ```

2. **Эксперименты с chunk sizing:**

   ```
   OCR из слайдов → большие чанки (3000 токенов, чтобы не резать код)
   Transcript разговора → маленькие чанки (1000 токенов для точности)
   ```

3. **Улучшение существующих документов:**

   ```
   Gemini выпустил новую модель gemini-3.0-pro.
   Пользователь хочет пересоздать summary для всех видео с новым промптом.
   ```

### 1.2 Целевой user experience

**После Phase 14.3:**

```toml
# semantic.toml

[media.prompts]
audio_summary = """
You are analyzing a medical lecture. 
Extract: diagnoses, medications, dosages, contraindications.
"""

video_ocr = """
This is a coding tutorial video.
Preserve ALL code blocks verbatim with syntax highlighting hints.
"""

[media.chunk_sizes]
transcript = 1000  # Маленькие для точности
ocr = 3000         # Большие чтобы не резать слайды

[media.processing]
ocr_parser_mode = "markdown"  # "markdown" | "plain"
enable_timecodes = true
```

**Команда CLI:**

```bash
# Пересоздать summary с новым промптом
semantic reanalyze video_123 --prompt-override audio_summary

# Rerun только OCR шаг с новым parser mode
semantic rerun-step video_123 ocr --parser-mode plain
```

---

## 2. Конфигурируемые промпты через TOML

### 2.1 Структура конфигурации

**Расширение:** `semantic_core/config.py`

```python
from pydantic import BaseModel, Field
from typing import Optional, Dict

class MediaPromptsConfig(BaseModel):
    """Конфигурация промптов для analyzers."""
    
    # Audio analyzer prompts
    audio_system_prompt: Optional[str] = Field(
        default=None,
        description="Custom system prompt for audio analysis. Overrides default.",
    )
    
    audio_summary_instructions: Optional[str] = Field(
        default=None,
        description="Additional instructions for audio summary generation.",
    )
    
    # Video analyzer prompts
    video_system_prompt: Optional[str] = None
    video_ocr_instructions: Optional[str] = None
    
    # Image analyzer prompts
    image_system_prompt: Optional[str] = None
    image_alt_text_instructions: Optional[str] = None


class MediaChunkSizesConfig(BaseModel):
    """Конфигурация размеров чанков по ролям."""
    
    transcript_chunk_size: int = Field(
        default=1800,
        ge=500,
        le=5000,
        description="Chunk size for transcript text (tokens).",
    )
    
    ocr_chunk_size: int = Field(
        default=2000,
        ge=500,
        le=5000,
        description="Chunk size for OCR text (tokens).",
    )
    
    code_chunk_size: int = Field(
        default=2000,
        ge=500,
        le=5000,
        description="Chunk size for code blocks extracted from OCR.",
    )


class MediaProcessingConfig(BaseModel):
    """Конфигурация обработки медиа."""
    
    ocr_parser_mode: str = Field(
        default="markdown",
        pattern="^(markdown|plain)$",
        description="Parser mode for OCR text: 'markdown' (detects code blocks) or 'plain'.",
    )
    
    enable_timecodes: bool = Field(
        default=True,
        description="Enable timecode extraction from Gemini responses ([MM:SS] format).",
    )
    
    strict_timecode_ordering: bool = Field(
        default=False,
        description="Enforce ascending order for timecodes (warn if violated).",
    )
    
    max_timeline_items: int = Field(
        default=100,
        ge=10,
        le=500,
        description="Maximum number of timeline items to generate.",
    )


class MediaConfig(BaseModel):
    """Полная конфигурация медиа-обработки."""
    
    prompts: MediaPromptsConfig = Field(default_factory=MediaPromptsConfig)
    chunk_sizes: MediaChunkSizesConfig = Field(default_factory=MediaChunkSizesConfig)
    processing: MediaProcessingConfig = Field(default_factory=MediaProcessingConfig)


class SemanticConfig(BaseSettings):
    # ... существующие поля ...
    
    media: MediaConfig = Field(default_factory=MediaConfig)
```

### 2.2 Загрузка промптов в Analyzers

**Модификация:** `semantic_core/infrastructure/gemini/audio_analyzer.py`

```python
class GeminiAudioAnalyzer:
    # DEFAULT_SYSTEM_PROMPT — fallback
    DEFAULT_SYSTEM_PROMPT = """You are an audio analyst..."""
    
    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.5-flash",
        custom_system_prompt: Optional[str] = None,  # ← NEW
        summary_instructions: Optional[str] = None,  # ← NEW
    ):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        
        # Формируем итоговый промпт
        self.system_prompt = self._build_system_prompt(
            custom_system_prompt,
            summary_instructions,
        )
    
    def _build_system_prompt(
        self,
        custom_prompt: Optional[str],
        additional_instructions: Optional[str],
    ) -> str:
        """Формирует системный промпт из конфига."""
        if custom_prompt:
            # Полная замена дефолтного промпта
            base_prompt = custom_prompt
        else:
            base_prompt = self.DEFAULT_SYSTEM_PROMPT
        
        if additional_instructions:
            # Добавляем инструкции к базовому промпту
            return f"{base_prompt}\n\nADDITIONAL INSTRUCTIONS:\n{additional_instructions}"
        
        return base_prompt
    
    def analyze(self, audio_path: Path, language: str = "en") -> dict:
        # Используем self.system_prompt вместо SYSTEM_PROMPT_TEMPLATE
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[...],
            config=types.GenerateContentConfig(
                system_instruction=self.system_prompt.format(language=language),
                response_schema=AudioAnalysisResult,
            ),
        )
        ...
```

**Инициализация в SemanticCore:**

```python
class SemanticCore:
    def __init__(self, config_path: Optional[str] = None, ...):
        # Загружаем конфиг
        self.config = SemanticConfig.from_toml(config_path or "semantic.toml")
        
        # Создаём analyzers с кастомными промптами
        if self.config.gemini.api_key:
            self.audio_analyzer = GeminiAudioAnalyzer(
                api_key=self.config.gemini.api_key,
                custom_system_prompt=self.config.media.prompts.audio_system_prompt,
                summary_instructions=self.config.media.prompts.audio_summary_instructions,
            )
            
            self.video_analyzer = GeminiVideoAnalyzer(
                api_key=self.config.gemini.api_key,
                custom_system_prompt=self.config.media.prompts.video_system_prompt,
                ocr_instructions=self.config.media.prompts.video_ocr_instructions,
            )
```

---

## 3. Per-role chunk sizing

### 3.1 Динамический chunk size в Steps

**Модификация:** `semantic_core/processing/steps/transcription_step.py`

```python
class TranscriptionStep(BaseProcessingStep):
    def __init__(
        self,
        splitter: BaseSplitter,
        default_chunk_size: int = 1800,  # ← Из конфига
        enable_timecodes: bool = True,
    ):
        self.splitter = splitter
        self.default_chunk_size = default_chunk_size
        self.enable_timecodes = enable_timecodes
    
    def process(self, context: MediaPipelineContext) -> MediaPipelineContext:
        # Временно меняем chunk_size у splitter
        original_chunk_size = self.splitter.chunk_size
        self.splitter.chunk_size = self.default_chunk_size
        
        try:
            # Разбиваем транскрипцию
            split_chunks = self.splitter.split(temp_doc)
            ...
        finally:
            # Восстанавливаем оригинальный размер
            self.splitter.chunk_size = original_chunk_size
        
        return context.with_chunks(transcript_chunks)
```

**Инициализация в SemanticCore:**

```python
def _create_default_steps(self) -> List[BaseProcessingStep]:
    return [
        SummaryStep(),
        TranscriptionStep(
            splitter=self.splitter,
            default_chunk_size=self.config.media.chunk_sizes.transcript_chunk_size,
            enable_timecodes=self.config.media.processing.enable_timecodes,
        ),
        OCRStep(
            splitter=self.splitter,
            parser_mode=self.config.media.processing.ocr_parser_mode,
            default_chunk_size=self.config.media.chunk_sizes.ocr_chunk_size,
        ),
    ]
```

### 3.2 Пример конфигурации

**semantic.toml:**

```toml
[media.chunk_sizes]
transcript_chunk_size = 1000  # Маленькие для точности search
ocr_chunk_size = 3000         # Большие чтобы не резать слайды
code_chunk_size = 2500        # Средние для code blocks
```

---

## 4. Full rerun с новым анализом

### 4.1 Проблема текущего rerun_step()

**Текущая реализация (Phase 14.1):**

```python
def rerun_step(self, step_name: str, document_id: str):
    # Загружаем СТАРЫЙ analysis из БД (MediaTaskModel)
    task = MediaTaskModel.get_or_none(result_document_id=document_id)
    analysis = {
        "description": task.result_description,  # ← ИЗ КЭША
        "transcription": task.result_transcription,
    }
    
    # Запускаем шаг с тем же анализом
    context = MediaPipelineContext(analysis=analysis, ...)
    new_context = step.process(context)
```

**Проблема:** Нельзя пересоздать summary с новым промптом (используется старое description).

### 4.2 Решение — reanalyze()

**Новый метод:** `semantic_core/pipeline.py`

```python
def reanalyze(
    self,
    document_id: str,
    analyzer_override: Optional[str] = None,
    prompt_override: Optional[str] = None,
    delete_old_chunks: bool = True,
) -> str:
    """Пересоздаёт analysis для существующего медиа-файла.
    
    Args:
        document_id: ID документа для re-analysis.
        analyzer_override: Имя analyzer'а для override ("audio" | "video" | "image").
        prompt_override: Ключ из config.media.prompts (например, "audio_summary").
        delete_old_chunks: Удалять ли старые чанки перед созданием новых.
    
    Returns:
        Новый document_id (или тот же, если перезаписываем).
    
    Raises:
        ValueError: Если документ не найден или не является медиа.
    """
    # Находим задачу
    task = MediaTaskModel.get_or_none(MediaTaskModel.result_document_id == document_id)
    if not task:
        raise ValueError(f"Media task not found for document {document_id}")
    
    media_path = Path(task.file_path)
    media_type = task.media_type
    
    logger.info(
        "Re-analyzing media file",
        document_id=document_id,
        media_path=str(media_path),
        prompt_override=prompt_override,
    )
    
    # Выбираем analyzer
    analyzer = self._get_analyzer(media_type, analyzer_override)
    
    # Применяем prompt override (если указан)
    if prompt_override:
        self._apply_prompt_override(analyzer, prompt_override)
    
    # Запускаем анализ заново
    new_analysis = analyzer.analyze(media_path)
    
    # Удаляем старые чанки
    if delete_old_chunks:
        deleted = (
            ChunkModel.delete()
            .where(ChunkModel.document_id == document_id)
            .execute()
        )
        logger.info(f"Deleted old chunks", count=deleted)
    
    # Создаём новые чанки через MediaPipeline
    doc = self.store.get_document_by_id(document_id)
    chunks = self._media_pipeline.build_chunks(
        analysis=new_analysis,
        document=doc,
        media_path=media_path,
    )
    
    # Сохраняем в БД
    self.store.update_chunks(document_id, chunks)
    
    # Обновляем задачу
    task.result_description = new_analysis.get("description")
    task.result_transcription = new_analysis.get("transcription")
    task.result_ocr_text = new_analysis.get("ocr_text")
    task.save()
    
    logger.info(
        "Re-analysis complete",
        document_id=document_id,
        new_chunks=len(chunks),
    )
    
    return document_id

def _apply_prompt_override(self, analyzer, prompt_key: str):
    """Применяет prompt override к analyzer."""
    prompts_config = self.config.media.prompts
    
    if prompt_key == "audio_summary":
        analyzer.system_prompt = prompts_config.audio_summary_instructions
    elif prompt_key == "video_ocr":
        analyzer.ocr_instructions = prompts_config.video_ocr_instructions
    # ... другие варианты
```

### 4.3 CLI команда

**Файл:** `semantic_core/cli/commands/reanalyze.py`

```python
import typer
from semantic_core import SemanticCore

app = typer.Typer(name="reanalyze", help="Re-analyze media with new prompts")


@app.command()
def media(
    document_id: str = typer.Argument(..., help="Document ID to re-analyze"),
    prompt_override: str = typer.Option(
        None,
        "--prompt",
        help="Prompt override key from semantic.toml (e.g., 'audio_summary')",
    ),
    keep_old_chunks: bool = typer.Option(
        False,
        "--keep-old",
        help="Keep old chunks (default: delete before re-analysis)",
    ),
):
    """Re-analyze media file with new prompt configuration."""
    core = SemanticCore()
    
    try:
        new_doc_id = core.reanalyze(
            document_id=document_id,
            prompt_override=prompt_override,
            delete_old_chunks=not keep_old_chunks,
        )
        
        typer.echo(f"✅ Re-analysis complete: {new_doc_id}")
    except ValueError as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)
```

**Использование:**

```bash
# Re-analyze с промптом из конфига
semantic reanalyze video_123 --prompt audio_summary

# Re-analyze и сохранить старые чанки
semantic reanalyze video_123 --keep-old
```

---

## 5. OCR parser mode в конфиге

### 5.1 Динамическое переключение parser mode

**Модификация:** `semantic_core/processing/steps/ocr_step.py`

```python
class OCRStep(BaseProcessingStep):
    def __init__(
        self,
        splitter: BaseSplitter,
        parser_mode: str = "markdown",  # ← Из конфига
        default_chunk_size: int = 2000,
    ):
        self.splitter = splitter
        self.parser_mode = parser_mode
        self.default_chunk_size = default_chunk_size
    
    def process(self, context: MediaPipelineContext) -> MediaPipelineContext:
        # Определяем media_type для Document на основе parser_mode
        if self.parser_mode == "markdown":
            media_type = MediaType.TEXT  # SmartSplitter auto-detect Markdown
        else:
            media_type = MediaType.TEXT
        
        temp_doc = Document(
            content=ocr_text,
            media_type=media_type,
        )
        
        # SmartSplitter автоматически использует MarkdownNodeParser для TEXT
        split_chunks = self.splitter.split(temp_doc)
        ...
```

### 5.2 Конфигурация

**semantic.toml:**

```toml
[media.processing]
ocr_parser_mode = "markdown"  # "markdown" детектит code blocks | "plain" просто текст
```

---

## 6. План реализации

### 6.1 Этапы разработки

**Week 1: Configuration Infrastructure**

- [ ] Расширить `SemanticConfig` с `MediaConfig`
- [ ] Добавить `MediaPromptsConfig`, `MediaChunkSizesConfig`, `MediaProcessingConfig`
- [ ] Обновить `AudioAnalyzer`, `VideoAnalyzer`, `ImageAnalyzer` для custom prompts
- [ ] Unit-тесты: загрузка промптов из TOML

**Week 2: Per-role Chunk Sizing**

- [ ] Модифицировать `TranscriptionStep`, `OCRStep` для dynamic chunk size
- [ ] Обновить `SemanticCore._create_default_steps()` с конфигом
- [ ] E2E тест: OCR chunks = 3000 токенов, transcript = 1000

**Week 3: Reanalyze Feature**

- [ ] Реализовать `SemanticCore.reanalyze()`
- [ ] Добавить `_apply_prompt_override()` helper
- [ ] Создать CLI команду `semantic reanalyze`
- [ ] E2E тест: reanalyze → новые чанки с обновлённым summary

**Week 4: Polish & Documentation**

- [ ] Обновить документацию с примерами TOML конфигов
- [ ] Добавить migration guide для существующих пользователей
- [ ] Написать статью 76: "User Flexibility через Configuration"
- [ ] Обновить Flask UI для отображения custom prompts (опционально)

### 6.2 Примеры конфигураций

**Пример 1: Медицинские лекции**

```toml
[media.prompts]
audio_summary_instructions = """
Extract the following from medical lectures:
- Diagnoses mentioned
- Medications and dosages
- Contraindications
- Key medical terms
Format as structured list.
"""

[media.chunk_sizes]
transcript_chunk_size = 1200  # Точность для медицинских терминов
```

**Пример 2: Coding tutorials**

```toml
[media.prompts]
video_ocr_instructions = """
This is a programming tutorial video.
CRITICAL: Preserve ALL code blocks verbatim.
Include syntax highlighting hints (language name).
"""

[media.chunk_sizes]
ocr_chunk_size = 3500      # Большие чанки чтобы не резать функции
code_chunk_size = 3000

[media.processing]
ocr_parser_mode = "markdown"  # Обязательно для code detection
```

**Пример 3: Лёгкий режим (без code detection)**

```toml
[media.processing]
ocr_parser_mode = "plain"      # Отключить Markdown парсинг
enable_timecodes = false       # Отключить timecode extraction

[media.chunk_sizes]
transcript_chunk_size = 2000   # Крупнее для экономии
ocr_chunk_size = 2500
```

### 6.3 Success Metrics

**Configuration:**

- ✅ Все промпты можно переопределить через TOML
- ✅ Chunk sizes работают независимо для transcript/OCR/code
- ✅ `reanalyze()` пересоздаёт чанки с новым анализом

**User Experience:**

- ✅ Пользователь может кастомизировать без правки кода
- ✅ CLI команда `semantic reanalyze` работает
- ✅ Документация с 5+ примерами конфигов

**Performance:**

- ✅ Reanalyze 10-минутного видео < 60 секунд
- ✅ Загрузка конфига не добавляет overhead (< 10ms)

---

**End of Phase 14.3 Plan**  
**Estimated Duration:** 1-2 weeks  
**Team:** 1 engineer
