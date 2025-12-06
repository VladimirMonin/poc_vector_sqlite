# ⚙️ Phase 14.3: User Flexibility & Configuration

**Дата:** 2025-12-06  
**Статус:** In Progress  
**Зависимости:** Phase 14.1 (ProcessingStep), Phase 14.2 (MediaService)  
**Цель:** Сделать систему гибкой через конфигурацию без изменения кода

**Архитектурные принципы:**

- ✅ **SRP:** `MediaService.reprocess_document()` вместо `SemanticCore.reanalyze()`
- ✅ **Single Source of Truth:** `Document.metadata["source"]` вместо `MediaTaskModel.file_path`
- ✅ **Template Injection:** Placeholders вместо string concatenation

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

**КРИТИЧНО:** Используем **template injection** вместо конкатенации!

```python
class GeminiAudioAnalyzer:
    # DEFAULT_SYSTEM_PROMPT с placeholders
    DEFAULT_SYSTEM_PROMPT = """You are an audio analyst creating descriptions for semantic search indexing.
Response language: {language}

{custom_instructions}

Return a JSON with the following structure:
{{
  "description": "Brief 2-3 sentence summary...",
  ...
}}

CRITICAL INSTRUCTIONS FOR TRANSCRIPTION FIELD:
- Use Markdown formatting...
"""
    
    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.5-flash",
        custom_instructions: Optional[str] = None,  # ← NEW
        output_language: str = "Russian",
    ):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.output_language = output_language
        
        # Формируем итоговый промпт через template injection
        self.system_prompt = self._build_system_prompt(
            custom_instructions=custom_instructions,
            language=output_language,
        )
    
    def _build_system_prompt(
        self,
        custom_instructions: Optional[str],
        language: str,
    ) -> str:
        """Формирует системный промпт через template injection.
        
        Безопасно вставляет custom_instructions ПЕРЕД описанием JSON-схемы.
        """
        # Формируем блок инструкций
        instructions_block = ""
        if custom_instructions:
            instructions_block = f"""
ADDITIONAL INSTRUCTIONS:
{custom_instructions}
"""
        
        # Template injection — безопасно!
        return self.DEFAULT_SYSTEM_PROMPT.format(
            language=language,
            custom_instructions=instructions_block,
        )
    
    def analyze(self, audio_path: Path) -> dict:
        # Используем self.system_prompt
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[...],
            config=types.GenerateContentConfig(
                system_instruction=self.system_prompt,
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
                custom_instructions=self.config.media.prompts.audio_summary_instructions,
                output_language=self.config.media.analysis.language,
            )
            
            self.video_analyzer = GeminiVideoAnalyzer(
                api_key=self.config.gemini.api_key,
                custom_instructions=self.config.media.prompts.video_ocr_instructions,
                output_language=self.config.media.analysis.language,
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

### 4.1 Проблема текущего подхода

**Архитектурная ошибка:** `MediaTaskModel` как источник правды для reanalyze.

```python
# ПЛОХО — MediaTaskModel временная сущность
task = MediaTaskModel.get(result_document_id=document_id)
media_path = Path(task.file_path)  # ← Что если task удалён?
```

**Проблема:** `MediaTask` — это **Queue Item** (очередь). Если чистить старые tasks:

```sql
DELETE FROM media_tasks WHERE processed_at < NOW() - INTERVAL '30 days';
```

→ **Потеряем возможность reanalyze** (нет пути к файлу)!

**Решение:** `Document.metadata["source"]` УЖЕ содержит путь к медиа:

```python
# semantic_core/pipeline.py line 680, 709, 838...
metadata = {"source": str(path)}  # ← Single Source of Truth!
```

### 4.2 Решение — MediaService.reprocess_document()

**КРИТИЧНО:** Логика в `MediaService`, НЕ в `SemanticCore` (SRP)!

**Новый метод:** `semantic_core/services/media_service.py`

```python
class MediaService:
    def __init__(
        self,
        store: BaseVectorStore,
        embedder: BaseEmbedder,
        splitter: BaseSplitter,
        media_pipeline: MediaPipeline,
    ):
        self.store = store
        self.embedder = embedder
        self.splitter = splitter
        self.media_pipeline = media_pipeline
    
    def reprocess_document(
        self,
        document_id: str,
        new_analysis: dict,
        delete_old_chunks: bool = True,
    ) -> str:
        """Пересоздаёт чанки для медиа-документа с новым анализом.
        
        Args:
            document_id: ID документа для обновления.
            new_analysis: Новый результат от analyzer.analyze().
            delete_old_chunks: Удалять ли старые чанки перед созданием новых.
        
        Returns:
            ID обновлённого документа.
        
        Raises:
            ValueError: Если документ не найден или не является медиа.
            FileNotFoundError: Если медиа-файл не существует.
        """
        # 1. Загружаем Document из БД
        doc_model = DocumentModel.get_by_id(document_id)
        
        # 2. Проверяем, что это медиа
        if doc_model.media_type not in ("image", "audio", "video"):
            raise ValueError(f"Document {document_id} is not a media file")
        
        # 3. Извлекаем путь из Document.metadata (Single Source of Truth!)
        metadata = json.loads(doc_model.metadata)
        media_path = Path(metadata["source"])
        
        # 4. Проверяем существование файла
        if not media_path.exists():
            raise FileNotFoundError(f"Media file not found: {media_path}")
        
        logger.info(
            "Reprocessing media document",
            document_id=document_id,
            media_path=str(media_path),
        )
        
        # 5. Удаляем старые чанки
        if delete_old_chunks:
            deleted = (
                ChunkModel.delete()
                .where(ChunkModel.document == document_id)
                .execute()
            )
            logger.info("Deleted old chunks", count=deleted)
        
        # 6. Создаём domain Document
        document = Document(
            content=str(media_path),
            metadata=metadata,
            media_type=MediaType(doc_model.media_type),
            id=document_id,
        )
        
        # 7. Создаём новые чанки через MediaPipeline
        context = MediaContext(
            media_path=media_path,
            document=document,
            analysis=new_analysis,
        )
        
        final_context = self.media_pipeline.build_chunks(context)
        new_chunks = final_context.chunks
        
        # 8. Векторизация
        chunk_texts = [chunk.content for chunk in new_chunks]
        embeddings = self.embedder.embed_documents(chunk_texts)
        
        for chunk, embedding in zip(new_chunks, embeddings):
            chunk.embedding = embedding
        
        # 9. Сохранение в БД
        self.store.save(document, new_chunks)
        
        logger.info(
            "Reprocessing complete",
            document_id=document_id,
            new_chunks_count=len(new_chunks),
        )
        
        return document_id
```

**SemanticCore — тонкий proxy:**

```python
class SemanticCore:
    def __init__(self, ...):
        # Инициализируем MediaService
        self.media_service = MediaService(
            store=self.store,
            embedder=self.embedder,
            splitter=self.splitter,
            media_pipeline=self._create_media_pipeline(),
        )
    
    def reanalyze(
        self,
        document_id: str,
        analyzer_type: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        delete_old_chunks: bool = True,
    ) -> str:
        """Пересоздаёт analysis для существующего медиа-файла.
        
        Thin proxy для MediaService.reprocess_document().
        
        Args:
            document_id: ID документа для re-analysis.
            analyzer_type: Тип analyzer ("audio" | "video" | "image").
            custom_instructions: Дополнительные инструкции для промпта.
            delete_old_chunks: Удалять ли старые чанки.
        
        Returns:
            ID обновлённого документа.
        """
        # 1. Загружаем документ для определения типа
        doc_model = DocumentModel.get_by_id(document_id)
        metadata = json.loads(doc_model.metadata)
        media_path = Path(metadata["source"])
        media_type = doc_model.media_type
        
        # 2. Выбираем analyzer
        analyzer = self._get_analyzer_for_type(
            media_type,
            override_type=analyzer_type,
            custom_instructions=custom_instructions,
        )
        
        # 3. Запускаем новый анализ
        logger.info("Running new analysis", media_path=str(media_path))
        new_analysis = analyzer.analyze(media_path)
        
        # 4. Делегируем MediaService
        return self.media_service.reprocess_document(
            document_id=document_id,
            new_analysis=new_analysis,
            delete_old_chunks=delete_old_chunks,
        )
    
    def _get_analyzer_for_type(
        self,
        media_type: str,
        override_type: Optional[str] = None,
        custom_instructions: Optional[str] = None,
    ):
        """Возвращает analyzer с учётом override."""
        target_type = override_type or media_type
        
        if target_type == "audio":
            # Создаём временный analyzer с custom instructions
            if custom_instructions:
                return GeminiAudioAnalyzer(
                    api_key=self.config.gemini.api_key,
                    custom_instructions=custom_instructions,
                )
            return self.audio_analyzer
        
        elif target_type == "video":
            if custom_instructions:
                return GeminiVideoAnalyzer(
                    api_key=self.config.gemini.api_key,
                    custom_instructions=custom_instructions,
                )
            return self.video_analyzer
        
        # ... аналогично для image
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

**Phase 14.3.1: Configuration Infrastructure** ✅ CRITICAL

- [ ] Расширить `SemanticConfig` с `MediaPromptsConfig`, `MediaChunkSizesConfig`, `MediaProcessingConfig`
- [ ] Обновить `AudioAnalyzer`, `VideoAnalyzer` для custom instructions через template injection
- [ ] Unit-тесты: загрузка промптов из TOML, template placeholders

**Phase 14.3.2: Per-role Chunk Sizing**

- [ ] Модифицировать `TranscriptionStep`, `OCRStep` для dynamic chunk size
- [ ] Обновить `SemanticCore._create_default_steps()` с конфигом
- [ ] E2E тест: OCR chunks = 3000 токенов, transcript = 1000

**Phase 14.3.3: MediaService.reprocess_document()** ✅ CRITICAL

- [ ] Реализовать `MediaService.reprocess_document()`
- [ ] `SemanticCore.reanalyze()` как thin proxy
- [ ] Использовать `Document.metadata["source"]` (Single Source of Truth)
- [ ] Unit-тесты: reprocess с новым анализом, обработка ошибок

**Phase 14.3.4: CLI Integration**

- [ ] Создать CLI команду `semantic reanalyze`
- [ ] Поддержка `--custom-instructions`, `--keep-old`
- [ ] E2E тест: reanalyze → новые чанки с обновлённым summary

**Phase 14.3.5: Total E2E Testing**
- [ ] Полный E2E тест: загрузка медиа → кастомный промпт → per-role chunk sizing → reanalyze -> проверка чанков и векторов (из БД)
Важно. На вход реальные данные из Ассетов. Если нужны более объемные данные, обязательно скажи. Мы используем раельный .env ключ - он там есть.
Берем реальные файлы и проверяем реальную БД. Никаких подмен, моков, ускорений. ПОЛНЫЕ ПРВОЕРКИ во всех вариантах. Чтобы потом не тратить дни на ручное тесрирование.

**Phase 14.4: Polish & Documentation**

- [ ] Обновить документацию с примерами TOML конфигов
- [ ] Написать статью 82: "User Flexibility через Configuration"
- [ ] Migration guide для существующих пользователей

### 6.2 Архитектурные гарантии

**Code Smells Prevention:**

1. ✅ **SRP:** `MediaService.reprocess_document()` вместо `SemanticCore.reanalyze()`
2. ✅ **Template Injection:** `{custom_instructions}` placeholder вместо `+` конкатенации
3. ✅ **Single Source of Truth:** `Document.metadata["source"]` вместо `MediaTaskModel.file_path`

**MediaTaskModel может чиститься:**

```sql
-- Безопасно! Reanalyze использует Document.metadata
DELETE FROM media_tasks WHERE processed_at < NOW() - INTERVAL '30 days';
```

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
- ✅ `MediaService.reprocess_document()` пересоздаёт чанки с новым анализом
- ✅ `Document.metadata["source"]` — Single Source of Truth (не MediaTaskModel)

**User Experience:**

- ✅ Пользователь может кастомизировать без правки кода
- ✅ CLI команда `semantic reanalyze` работает
- ✅ Документация с 5+ примерами конфигов

**Architecture:**

- ✅ `SemanticCore` остаётся тонким фасадом (SRP)
- ✅ Template injection вместо string concatenation (безопасность)
- ✅ MediaTaskModel можно чистить без последствий

**Performance:**

- ✅ Reanalyze 10-минутного видео < 60 секунд
- ✅ Загрузка конфига не добавляет overhead (< 10ms)

---

**End of Phase 14.3 Plan (REVISED)**  
**Estimated Duration:** 1-2 weeks  
**Critical Path:** MediaService.reprocess_document() + Template Injection
