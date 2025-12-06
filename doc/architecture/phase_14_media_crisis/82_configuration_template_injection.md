---
phase: 14.3.1
title: "Configuration & Template Injection"
created: 2025-12-06
topics: [configuration, pydantic, template-injection, security]
commits: [d270238]
---

# 82. Configuration & Template Injection

**Commits:** `d270238`

## Проблема

После Phase 14.1-14.2 система умеет обрабатывать медиа, но **негибкая**:

```python
# Захардкоженные значения в коде
class GeminiAudioAnalyzer:
    SYSTEM_PROMPT = """You are an audio analyst..."""  # Нельзя изменить
    
class TranscriptionStep:
    def process(self, context):
        chunks = self.splitter.split(text)  # chunk_size=1800, всегда
```

**Проблемы для пользователя:**

❌ **Промпты статичны** — нельзя кастомизировать под предметную область  
❌ **Chunk size единый** — transcript и OCR используют одинаковый размер  
❌ **Parser mode захардкожен** — OCR всегда Markdown, нельзя переключить на plain text

**Реальные сценарии:**

1. **Медицинские лекции**: Нужен промпт с инструкциями "Extract diagnoses, medications, dosages"
2. **Coding tutorials**: OCR должен использовать большие чанки (3000 токенов), чтобы не резать код
3. **Podcast transcription**: Нужны маленькие чанки (1000 токенов) для точного поиска

---

## Решение: MediaConfig + Template Injection

### Архитектурный подход

**Принципы:**

1. **Configuration as Code**: Pydantic models с валидацией (`ge`, `le`, `pattern`)
2. **Template Injection**: Placeholders (`{custom_instructions}`) вместо string concatenation
3. **TOML Support**: Расширение `SemanticConfig._load_toml()` для nested sections

**Структура:**

```
MediaConfig (composition root)
├── MediaPromptsConfig (custom_instructions для analyzers)
├── MediaChunkSizesConfig (per-role chunk sizing)
└── MediaProcessingConfig (ocr_parser_mode, timecode settings)
```

---

## MediaConfig Models

### 1. MediaPromptsConfig

**Назначение**: Кастомные инструкции для Gemini analyzers.

**Поля:**

| Поле | Тип | Default | Описание |
|------|-----|---------|----------|
| `audio_instructions` | `Optional[str]` | `None` | Доп. промпт для аудио |
| `image_instructions` | `Optional[str]` | `None` | Доп. промпт для изображений |
| `video_instructions` | `Optional[str]` | `None` | Доп. промпт для видео |

**TOML Example:**

```toml
[media.prompts]
audio_instructions = """
Extract medical terms, diagnoses, and dosages.
Focus on contraindications and side effects.
"""
```

---

### 2. MediaChunkSizesConfig

**Назначение**: Динамические размеры чанков по ролям.

**Поля:**

| Поле | Тип | Default | Constraint | Описание |
|------|-----|---------|-----------|----------|
| `summary_chunk_size` | `int` | `1500` | `ge=500, le=5000` | Размер summary chunk |
| `transcript_chunk_size` | `int` | `2000` | `ge=500, le=8000` | Размер transcript chunks |
| `ocr_text_chunk_size` | `int` | `1800` | `ge=500, le=5000` | Размер OCR text chunks |
| `ocr_code_chunk_size` | `int` | `2000` | `ge=500, le=5000` | Размер OCR code chunks |

**Валидация**: Pydantic Field с `ge`/`le` constraints предотвращает некорректные значения.

**TOML Example:**

```toml
[media.chunk_sizes]
transcript_chunk_size = 1000  # Маленькие для точности
ocr_code_chunk_size = 3000    # Большие чтобы не резать код
```

---

### 3. MediaProcessingConfig

**Назначение**: Настройки обработки медиа.

**Поля:**

| Поле | Тип | Default | Constraint | Описание |
|------|-----|---------|-----------|----------|
| `ocr_parser_mode` | `str` | `"markdown"` | `pattern="^(markdown\|plain)$"` | Parser mode для OCR |
| `enable_timecodes` | `bool` | `True` | - | Включить парсинг таймкодов |
| `strict_timecode_ordering` | `bool` | `False` | - | Проверять порядок таймкодов |
| `max_timeline_items` | `int` | `100` | `ge=10, le=500` | Макс. элементов в timeline |

**Pattern Validation**: `pattern="^(markdown|plain)$"` — только допустимые значения.

**TOML Example:**

```toml
[media.processing]
ocr_parser_mode = "plain"
enable_timecodes = true
max_timeline_items = 200
```

---

## Template Injection Pattern

### Проблема конкатенации

❌ **ПЛОХО** — String concatenation:

```python
class GeminiAudioAnalyzer:
    def __init__(self, custom_instructions: str):
        # ОПАСНО: Инъекция может сломать JSON schema
        self.system_prompt = (
            f"You are an audio analyst.\n"
            f"{custom_instructions}\n"  # ← Может содержать "}}}" и сломать JSON
            f"Return a JSON with structure: {{...}}"
        )
```

**Риски:**

1. **JSON Corruption**: Custom instructions могут содержать `}}}` и сломать response schema
2. **Порядок нарушен**: Инструкции могут быть вставлены ПОСЛЕ schema description
3. **Unicode Issues**: Escape sequences (\\n, \\t) могут неправильно обрабатываться

---

### Решение: Placeholders

✅ **ХОРОШО** — Template Injection через `.format()`:

```python
class GeminiAudioAnalyzer:
    DEFAULT_SYSTEM_PROMPT = """You are an audio analyst...
Response language: {language}

{custom_instructions}

Return a JSON with the following structure:
{{
  "description": "...",
  ...
}}
"""
    
    def _build_system_prompt(self) -> str:
        instructions = ""
        if self.custom_instructions:
            instructions = f"CUSTOM INSTRUCTIONS:\n{self.custom_instructions}\n"
        
        return DEFAULT_SYSTEM_PROMPT.format(
            language=self.output_language,
            custom_instructions=instructions,
        )
```

**Гарантии:**

✅ **Placeholder ПЕРЕД schema** — custom instructions всегда вставляются в правильное место  
✅ **Double braces** — `{{...}}` в шаблоне не ломаются от `.format()`  
✅ **Safe escaping** — Unicode символы обрабатываются корректно

---

## TOML Integration

### Расширение SemanticConfig

**Nested Parsing:**

```python
class SemanticConfig(BaseSettings):
    media: MediaConfig = Field(default_factory=MediaConfig)
    
    def _load_toml(self, toml_path: Path) -> None:
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
        
        # Парсинг nested media sections
        if "media" in data:
            media_dict = {}
            
            if "prompts" in data["media"]:
                media_dict["prompts"] = data["media"]["prompts"]
            
            if "chunk_sizes" in data["media"]:
                media_dict["chunk_sizes"] = data["media"]["chunk_sizes"]
            
            if "processing" in data["media"]:
                media_dict["processing"] = data["media"]["processing"]
            
            self.media = MediaConfig(**media_dict)
```

**Backward Compatibility:** `default_factory=MediaConfig` — существующий код работает без изменений.

---

## Примеры использования

### 1. Custom prompts для медицинских лекций

**semantic.toml:**

```toml
[media.prompts]
audio_instructions = """
Extract medical terminology:
- Diagnoses (ICD-10 codes if mentioned)
- Medications with dosages
- Contraindications and side effects
"""
```

**Результат:**

```python
analyzer = GeminiAudioAnalyzer(
    custom_instructions=config.media.prompts.audio_instructions,
)
# system_prompt содержит medical instructions ПЕРЕД JSON schema
```

---

### 2. Per-role chunk sizing

**semantic.toml:**

```toml
[media.chunk_sizes]
transcript_chunk_size = 1000  # Маленькие для точного поиска
ocr_code_chunk_size = 3000    # Большие чтобы не резать code blocks
```

**Использование в Steps** (Phase 14.3.2):

```python
TranscriptionStep(
    splitter=splitter,
    default_chunk_size=config.media.chunk_sizes.transcript_chunk_size,
)
```

---

### 3. OCR parser mode switching

**semantic.toml:**

```toml
[media.processing]
ocr_parser_mode = "plain"  # Отключить Markdown парсинг для raw text
```

**Использование в OCRStep:**

```python
OCRStep(
    splitter=splitter,
    parser_mode=config.media.processing.ocr_parser_mode,
)
```

---

## Тестирование

### Unit Tests: 38 tests

**Структура тестов:**

```
tests/unit/
├── test_config.py (19 tests)
│   ├── TestMediaPromptsConfig (3 tests)
│   ├── TestMediaChunkSizesConfig (4 tests)
│   ├── TestMediaProcessingConfig (4 tests)
│   ├── TestMediaConfig (3 tests)
│   └── TestSemanticConfigMediaIntegration (5 tests)
│
└── infrastructure/gemini/
    └── test_template_injection.py (19 tests)
        ├── TestAudioAnalyzerTemplateInjection (6 tests)
        ├── TestImageAnalyzerTemplateInjection (3 tests)
        ├── TestVideoAnalyzerTemplateInjection (3 tests)
        ├── TestTemplateInjectionEdgeCases (4 tests)
        └── TestAnalyzerInitializationLogging (3 tests)
```

**Ключевые тесты:**

1. **Validation Tests**: `ge=500`, `le=8000`, `pattern="^(markdown|plain)$"`
2. **TOML Loading**: Nested sections parsing с backup/restore
3. **Template Injection**: Placeholder escaping, JSON schema order, unicode handling
4. **Edge Cases**: Empty strings, special characters (`{`, `}`, `<`, `>`), long instructions

**Результат:** 38/38 PASSED ✅

---

## Архитектурные гарантии

| Гарантия | Решение |
|----------|---------|
| **Безопасность промптов** | Template Injection через `.format()` |
| **Валидация конфигурации** | Pydantic Field constraints (`ge`, `le`, `pattern`) |
| **Backward compatibility** | `default_factory=MediaConfig` |
| **TOML поддержка** | Extended `_load_toml()` с nested parsing |
| **Типобезопасность** | Pydantic BaseModel с type hints |

---

## Следующий шаг

**Phase 14.3.2:** Per-role Chunk Sizing — использование `config.media.chunk_sizes` в TranscriptionStep и OCRStep.
