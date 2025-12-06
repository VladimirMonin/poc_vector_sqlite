# 🕐 #78: TimecodeParser — Парсинг таймкодов из транскрипций

> **Commits**: `fd4e26b` (TimecodeParser utility), `15c3960` (TranscriptionStep integration)  
> **Phase**: 14.1.2 Advanced Features (TimecodeParser)  
> **Tests**: 27 + 7 = 34 тестов | 202 total Phase 14.1  
> **Files**: `semantic_core/utils/timecode_parser.py`, `semantic_core/processing/steps/transcription.py`

---

## 📌 Зачем нужен TimecodeParser?

**Проблема**: Gemini Audio Analyzer возвращает транскрипцию с таймкодами вида:

```text
[00:05] Приветствую вас на канале!
[00:15] Сегодня поговорим о векторном поиске.
[01:30] SQLite-vec — это расширение...
```

**Задача**: Извлечь временные метки для семантического поиска типа:
- *"найди момент, где говорится про SQLite-vec"*
- *"что обсуждалось в интервале 1:20-2:00?"*

**Решение**: 
1. **TimecodeParser** — utility для парсинга `[MM:SS]`/`[HH:MM:SS]`
2. **TranscriptionStep** — интеграция парсера в pipeline через `enable_timecodes` флаг
3. **Metadata enrichment** — каждый chunk получает `start_seconds` и `timecode_original`

---

## 🏗 Архитектура TimecodeParser

### 🔍 Класс TimecodeParser

```text
TimecodeParser
├── __init__(max_duration_seconds, strict_ordering)
├── parse(text: str) → TimecodeInfo | None        # Первый таймкод
├── parse_all(text: str) → list[TimecodeInfo]     # Все таймкоды
└── inherit_timecode(...) → int                    # Для чанков без метки
```

**TimecodeInfo** (frozen dataclass):
- `original: str` — исходный таймкод `"[05:30]"`
- `hours: int` — часы (0 для `[MM:SS]`)
- `minutes: int` — минуты
- `seconds: int` — секунды
- **Calculated**: `seconds = hours*3600 + minutes*60 + seconds`

---

## 🔍 Форматы таймкодов

### Regex паттерны

```python
# [MM:SS] — короткий формат (до 99 минут)
PATTERN_MMSS = r"\[(\d{1,2}):(\d{2})\]"

# [HH:MM:SS] — полный формат (часы)
PATTERN_HHMMSS = r"\[(\d{1,2}):(\d{2}):(\d{2})\]"
```

**Приоритет**: `[HH:MM:SS]` > `[MM:SS]` (сначала ищем длинный формат).

**Примеры**:
- `"[05:30]"` → 330 секунд (5 минут 30 секунд)
- `"[01:15:45]"` → 4545 секунд (1 час 15 минут 45 секунд)
- `"[00:00]"` → 0 секунд (начало файла)

---

## ⚙️ Валидация таймкодов

### 1. Max Duration Validation

**Зачем**: Gemini иногда галлюцинирует несуществующие таймкоды.

```python
# Файл длится 10 минут (600 секунд)
parser = TimecodeParser(max_duration_seconds=600)

parser.parse("[05:30]")  # ✅ OK — 330s < 600s
parser.parse("[20:00]")  # ❌ None — 1200s > 600s (превышает длительность)
```

**Логика**: Если таймкод больше `analysis.duration_seconds` → отбрасываем.

---

### 2. Strict Ordering (Optional)

**Зачем**: Gemini редко, но нарушает порядок: `[01:00] → [00:45] → [01:10]`.

**Default**: `strict_ordering=False` (не проверяем).

**Если включить**:

```python
parser = TimecodeParser(max_duration_seconds=600, strict_ordering=True)

parser.parse_all("[00:10] text [00:20] text [00:15]")  
# ❌ ValueError: "[00:15] appears after [00:20]"
```

**Recommendation**: Оставлять `False`, т.к. Gemini достаточно точен, а false positives дороже.

---

## 🔄 Timecode Inheritance

**Проблема**: TranscriptionStep разбивает длинный текст на chunks. Не все чанки содержат `[MM:SS]`.

```text
Chunk 1: "[00:05] Введение в тему..."
Chunk 2: "Продолжение темы..."           # ❌ Нет таймкода!
Chunk 3: "[01:30] Следующий раздел..."
```

**Решение**: Наследуем таймкод от последнего известного + равномерная дельта.

---

### Формула наследования

```python
delta = total_duration_seconds / total_chunks
inherited_seconds = last_known_timecode + delta
```

**Пример** (файл 10 минут = 600 секунд, 5 чанков):

```text
delta = 600 / 5 = 120 секунд (2 минуты на чанк)

Chunk 1: [00:00] явно указан     → 0s
Chunk 2: нет таймкода            → 0 + 120 = 120s (inherit)
Chunk 3: [05:30] явно указан     → 330s
Chunk 4: нет таймкода            → 330 + 120 = 450s (inherit)
Chunk 5: нет таймкода            → 450 + 120 = 570s (inherit)
```

**Edge case**: Если у первого чанка нет таймкода → `start_seconds = 0`.

---

## 🔗 Интеграция в TranscriptionStep

### Enable Timecodes Flag

```python
class TranscriptionStep(BaseProcessingStep):
    def __init__(
        self,
        splitter: BaseSplitter,
        enable_timecodes: bool = True,  # ✅ По умолчанию включено
    ):
        ...
```

**Зачем флаг**:
- `True` (default): Автоматический парсинг `[MM:SS]` из транскрипций.
- `False`: Для тестирования или если таймкоды не нужны.

---

### Process() с Timecode Parsing

```mermaid
flowchart TD
    A[TranscriptionStep.process] --> B{enable_timecodes?}
    B -->|False| C[Обычный сплит без парсинга]
    B -->|True| D[Инициализация TimecodeParser]
    
    D --> E[Цикл по чанкам]
    E --> F{Есть таймкод?}
    
    F -->|Да| G[parse: TimecodeInfo]
    G --> H[meta[start_seconds] = info.seconds]
    H --> I[meta[timecode_original] = info.original]
    I --> J[last_timecode = info.seconds]
    
    F -->|Нет| K[inherit_timecode]
    K --> L[meta[start_seconds] = inherited]
    
    J --> M[Следующий чанк]
    L --> M
    M --> E
```

**Ключевая логика**:

```python
# 1. Инициализация парсера (если enable_timecodes)
timecode_parser = None
if self._enable_timecodes:
    max_duration = ctx.analysis.get("duration_seconds", 0)
    timecode_parser = TimecodeParser(max_duration_seconds=max_duration)

# 2. Цикл обогащения метаданных
for i, chunk in enumerate(chunks):
    if timecode_parser:
        # Пробуем распарсить таймкод
        timecode_info = timecode_parser.parse(chunk.content)
        
        if timecode_info:
            # ✅ Нашли таймкод в тексте
            meta["start_seconds"] = timecode_info.seconds
            meta["timecode_original"] = timecode_info.original
            last_timecode = timecode_info.seconds
        else:
            # ❌ Наследуем от последнего
            meta["start_seconds"] = timecode_parser.inherit_timecode(
                chunk_position=i,
                total_chunks=len(chunks),
                last_timecode=last_timecode,
            )
```

---

## 📊 Metadata Enrichment

### До интеграции (Phase 14.1.1)

```python
{
    "role": "transcription",
    "parent_media_path": "/path/to/audio.mp3",
}
```

### После интеграции (Phase 14.1.2)

```python
{
    "role": "transcription",
    "parent_media_path": "/path/to/audio.mp3",
    "start_seconds": 330,                # ✅ Всегда есть (parse или inherit)
    "timecode_original": "[05:30]",      # ✅ Если был распарсен
}
```

**Используется для**:
- Семантический поиск: *"найди фрагмент про SQLite-vec в минуте 1-2"*
- Навигация: кликабельные ссылки `[05:30]` в UI
- Сортировка: хронологический порядок чанков

---

## 🧪 Тестовое покрытие

### TimecodeParser (27 тестов)

| Test Class                    | Tests | Проверяет                                  |
| ----------------------------- | ----- | ------------------------------------------ |
| TestTimecodeParserBasic       | 6     | parse() с разными форматами, приоритет     |
| TestTimecodeParserParseAll    | 4     | parse_all() для всех таймкодов в тексте    |
| TestTimecodeParserValidation  | 5     | max_duration, strict_ordering              |
| TestTimecodeParserInheritance | 5     | inherit_timecode() с разными сценариями    |
| TestTimecodeParserEdgeCases   | 5     | Single digit, duplicates, mid-text         |
| TestTimecodeInfo              | 2     | Frozen dataclass, default hours            |

**Время выполнения**: ~0.07s

---

### TranscriptionStep Timecodes (7 тестов)

| Test                                     | Проверяет                              |
| ---------------------------------------- | -------------------------------------- |
| test_timecodes_enabled_by_default        | enable_timecodes=True по умолчанию     |
| test_timecodes_can_be_disabled           | enable_timecodes=False отключает парсинг |
| test_parses_timecode_from_content        | `"[05:30]"` → start_seconds=330        |
| test_inherits_timecode_when_missing      | Наследование от last_timecode + delta  |
| test_first_chunk_without_timecode_is_zero | Первый чанк без таймкода → 0 секунд    |
| test_timecodes_disabled_no_parsing       | Когда False, нет start_seconds в meta  |
| test_timecode_validation_with_max_duration | [20:00] отбрасывается если duration=600 |

**Итого**: 18 тестов TranscriptionStep (11 старых + 7 timecode).

---

## 🎯 Использование в Production

### 1. По умолчанию (timecodes включены)

```python
from semantic_core.processing.steps import TranscriptionStep

step = TranscriptionStep(splitter=my_splitter)  # enable_timecodes=True

# Автоматически парсит [MM:SS] из транскрипции
ctx = step.process(ctx)

# Результат в metadata:
chunk.metadata["start_seconds"]       # 330
chunk.metadata["timecode_original"]  # "[05:30]"
```

---

### 2. Отключение timecode parsing

```python
# Для текстов без таймкодов (не Gemini Audio)
step = TranscriptionStep(
    splitter=my_splitter,
    enable_timecodes=False,  # ❌ Отключено
)

ctx = step.process(ctx)

# metadata НЕ содержит start_seconds, timecode_original
```

---

### 3. Кастомная валидация

```python
# Если нужен strict_ordering (редко)
from semantic_core.utils.timecode_parser import TimecodeParser

parser = TimecodeParser(
    max_duration_seconds=600,
    strict_ordering=True,  # ⚠️ Выбросит ValueError при нарушении порядка
)

# Передать в TranscriptionStep нельзя (внутри создаётся свой парсер)
# Эта опция для прямого использования TimecodeParser вне pipeline
```

---

## 🧩 Nüances и Edge Cases

### 1. Первый чанк без таймкода = 0

```python
# Файл начинается с текста без метки
text = "Введение без метки. [01:00] Первая секция."
chunks = splitter.split(text)  # 2 чанка

# Chunk 1: "Введение без метки."
# → start_seconds = 0 (первый чанк без таймкода всегда 0)

# Chunk 2: "[01:00] Первая секция."
# → start_seconds = 60 (распарсен)
```

---

### 2. Дельта рассчитывается один раз

```text
delta = total_duration / total_chunks  # Фиксированная дельта

# НЕ пересчитывается при нахождении нового таймкода!
# Это упрощение, достаточное для практики.
```

**Альтернатива** (не реализована): Пересчитывать дельту между явными таймкодами.

```text
[00:00] chunk1
       chunk2  → inherited = (60 - 0) / 2 = 30s
[01:00] chunk3
       chunk4  → inherited = (120 - 60) / 2 + 60 = 90s
[02:00] chunk5
```

Текущий подход проще и работает для 95% кейсов.

---

### 3. Timecode в середине чанка

```python
text = "Текст без метки, затем [05:30] продолжение темы..."

# parse() найдёт [05:30] даже если он в середине
# start_seconds = 330 для всего чанка
```

**Trade-off**: Чанк считается начинающимся с первого найденного таймкода, даже если до него есть текст.

---

### 4. Несколько таймкодов в одном чанке

```python
text = "[05:30] Тема 1. [06:00] Тема 2."

# parse() вернёт ПЕРВЫЙ таймкод: [05:30]
# parse_all() вернёт ОБА: [[05:30], [06:00]]
```

**Текущий подход**: TranscriptionStep использует `parse()` (первый таймкод).

**Рекомендация**: Splitter должен разбивать по таймкодам (будущий SmartTimecodeAwareSplitter).

---

## 🔮 Будущие улучшения

### Phase 14.1.3: Analyzer Prompts

**Сейчас**: Gemini может возвращать таймкоды, но мы не просим об этом явно.

**Улучшение**: Добавить в промпты analyzers:

```python
# В audio_analyzer.py
system_instruction = f"""
Analyze audio and return JSON with:
- transcription (with timecodes in [MM:SS] format)
- description
- keywords

Example transcription:
[00:05] Intro to the topic.
[00:30] Main discussion begins.
[01:15] Conclusion.
"""
```

---

### Phase 14.2: Smart Timecode-Aware Splitter

**Идея**: Разбивать транскрипцию ПО таймкодам, а не по длине.

```python
class TimecodeAwareSplitter(BaseSplitter):
    def split(self, text: str) -> list[str]:
        # Найти все [MM:SS]
        timecodes = parser.parse_all(text)
        
        # Разбить текст на блоки между таймкодами
        chunks = []
        for i, tc in enumerate(timecodes):
            start = tc.original
            end = timecodes[i+1].original if i+1 < len(timecodes) else None
            chunk_text = extract_between(text, start, end)
            chunks.append(chunk_text)
        
        return chunks
```

**Выгода**: Семантически целостные чанки (один таймкод = одна тема).

---

## ✅ Резюме

| Компонент              | Назначение                                    | Tests |
| ---------------------- | --------------------------------------------- | ----- |
| **TimecodeParser**     | Парсинг `[MM:SS]`/`[HH:MM:SS]`, валидация    | 27    |
| **TimecodeInfo**       | Frozen dataclass с hours, minutes, seconds    | 2     |
| **TranscriptionStep**  | Интеграция через `enable_timecodes` флаг      | 7 new |
| **Metadata enrichment** | `start_seconds`, `timecode_original`         | -     |

**Commit flow**:
1. `fd4e26b` — TimecodeParser utility (27 тестов)
2. `15c3960` — TranscriptionStep integration (7 новых тестов, фикс RAG)

**Phase 14.1.2 Progress**: TimecodeParser ✅ DONE | Next: FrameDescriptionStep (Phase 14.1.2) → Analyzer migration (Phase 14.1.3).
