# Отчёт Phase 6.2: Реализация Audio/Video анализаторов

> **Статус:** ✅ Завершена  
> **Период:** ~2 дня разработки  
> **Коммитов:** 7 атомарных коммитов (совместно с тестами)

---

## 1. Цель фазы

Создать полноценную инфраструктуру для мультимодального анализа медиа-контента:
- Транскрипция и анализ аудио через Gemini API
- Мультимодальный анализ видео (кадры + аудио)
- Утилиты для оптимизации и извлечения медиа-данных
- Роутинг задач по типу медиа в `MediaQueueProcessor`

---

## 2. Архитектурные решения

### 2.1 Выбор моделей

| Тип медиа | Модель | Обоснование |
|-----------|--------|-------------|
| Аудио | `gemini-2.5-flash-lite` | Дешевле на 75%, достаточно для транскрипции |
| Видео | `gemini-2.5-pro` | Требуется мультимодальный reasoning (кадры + аудио одновременно) |
| Изображения | `gemini-2.5-flash` | Баланс цена/качество для одиночных изображений |

### 2.2 Агрессивная оптимизация аудио

Ключевое решение: **32 kbps mono OGG**

```
Исходный файл (CD quality):   44100 Hz × 16 bit × stereo = 1411 kbps
Оптимизированный:             16000 Hz × mono × OGG 32kbps = 32 kbps

Соотношение сжатия: 44x
Результат: ~83 минуты аудио в лимите 20MB Gemini
```

Обоснование:
- Gemini не различает стерео (внутренне конвертирует в mono)
- Для speech recognition 16kHz достаточно (телефонное качество)
- OGG/Vorbis лучше MP3 по качеству на низких битрейтах

### 2.3 Оптимизация видео-кадров

Пресеты качества (max_dimension):

| Preset | Пиксели | Использование |
|--------|---------|---------------|
| `fhd` | 1024 | UI туториалы с текстом |
| `hd` | 768 | Общие видео (default) |
| `balanced` | 512 | Длинные сессии, экономия |
| `economy` | 384 | Максимальная экономия |

**Важно:** "FHD" намеренно занижен до 1024px вместо реальных 1920px. При 1920px токены взлетают экспоненциально, а качество анализа не улучшается пропорционально.

### 2.4 Режимы извлечения кадров

Три режима для разных сценариев:

| Режим | Параметр | Логика |
|-------|----------|--------|
| `total` | `frame_count=N` | Равномерно N кадров по всему видео |
| `fps` | `fps=1.0` | 1 кадр/сек (или другое значение) |
| `interval` | `interval_seconds=5.0` | Кадр каждые N секунд |

Для анализа контента лучше `total` — покрывает всё видео независимо от длительности.
Для детального анализа анимации — `fps`.

---

## 3. Структура кода

```
semantic_core/infrastructure/
├── gemini/
│   ├── audio_analyzer.py    # GeminiAudioAnalyzer
│   └── video_analyzer.py    # GeminiVideoAnalyzer (multimodal)
├── media/
│   └── utils/
│       ├── audio.py         # pydub-based utilities
│       └── video.py         # imageio[pyav]-based utilities
└── queue_processor.py       # MediaQueueProcessor (роутинг)
```

### 3.1 Зависимости

```toml
# pyproject.toml
dependencies = [
    "pydub>=0.25",         # Аудио-обработка
    "imageio[pyav]>=2.36", # Извлечение кадров из видео
    "audioop-lts>=0.2",    # Python 3.13+ compatibility для pydub
]
```

**Python 3.13+ проблема:** Модуль `audioop` удалён из stdlib. Решение — backport-пакет `audioop-lts`.

---

## 4. API анализаторов

### 4.1 GeminiAudioAnalyzer

```python
analyzer = GeminiAudioAnalyzer(api_key=key, model="gemini-2.5-flash-lite")
result = analyzer.analyze(MediaRequest(...))

# Возвращает MediaAnalysisResult:
# - transcription: str (полная транскрипция)
# - description: str (краткое описание контента)
# - keywords: list[str] (извлечённые ключевые слова)
# - duration_seconds: float
# - token_count: int
```

### 4.2 GeminiVideoAnalyzer

```python
analyzer = GeminiVideoAnalyzer(api_key=key, model="gemini-2.5-pro")
config = VideoAnalysisConfig(
    frame_count=5,
    frame_mode="total",
    frame_quality="hd",
    include_audio=True,  # Multimodal!
)
result = analyzer.analyze(MediaRequest(...), config)

# Результат включает:
# - description: визуальное описание
# - transcription: аудио-транскрипция (если include_audio=True)
# - keywords: combined keywords
# - ocr_text: текст с экрана (если есть)
```

---

## 5. Решённые технические проблемы

### 5.1 usage_metadata — Pydantic вместо dict

**Проблема:** При тестировании получили ошибку:
```
AttributeError: 'GenerateContentResponseUsageMetadata' object has no attribute 'get'
```

**Причина:** Google GenAI SDK возвращает Pydantic-модель, а код ожидал dict.

**Было:**
```python
token_count = response.usage_metadata.get("total_token_count")
```

**Стало:**
```python
token_count = getattr(response.usage_metadata, "total_token_count", None)
```

**Затронутые файлы:** `audio_analyzer.py`, `video_analyzer.py`, `image_analyzer.py`

### 5.2 IMAGE_REF не детектировался в Markdown

**Проблема:** Тест `test_image_segment_detected` падал — парсер не создавал `IMAGE_REF` сегменты.

**Причина:** Неверная логика проверки. Код проверял `inline_token.content.strip()`, но у изображения `content` содержит полный markdown `![alt](path)`, а не пустую строку.

**Было:**
```python
if images and not inline_token.content.strip():
    # Только изображение
```

**Стало:**
```python
# Считаем не-image детей
text_nodes = [c for c in children if c.type == "text" and c.content.strip()]
if images and not text_nodes:
    # Только изображение (без сопровождающего текста)
```

### 5.3 IMAGE_REF терялся в SmartSplitter

**Проблема:** Даже когда парсер корректно создавал `IMAGE_REF` сегмент, он терялся в SmartSplitter.

**Причина:** `IMAGE_REF` обрабатывался веткой `else` (как TEXT) и попадал в `text_buffer`, где смешивался с текстом.

**Решение:** Добавлена отдельная ветка для `IMAGE_REF` (аналогично `CODE`):

```python
elif segment.segment_type == ChunkType.IMAGE_REF:
    # Flush text buffer first
    if text_buffer:
        text_chunks = self._flush_text_buffer(...)
        chunks.extend(text_chunks)
        text_buffer.clear()
    
    # Create dedicated chunk for media reference
    chunks.append(Chunk(
        content=segment.content,
        chunk_type=ChunkType.IMAGE_REF,
        metadata={...}
    ))
```

### 5.4 Переменная окружения API ключа

**Проблема:** Тесты пропускались с сообщением "GOOGLE_API_KEY not set".

**Причина:** В `.env` ключ называется `GEMINI_API_KEY`, а тесты ожидают `GOOGLE_API_KEY`.

**Решение:** Экспорт с правильным именем:
```bash
export GOOGLE_API_KEY=$(grep GEMINI_API_KEY .env | cut -d= -f2)
```

---

## 6. Отклонения от плана

### 6.1 Что было запланировано, но изменилось

| Планировалось | Реализовано | Причина |
|---------------|-------------|---------|
| Схемы в отдельном файле `media.py` | Схемы в `domain/media.py` | Унификация с другими DTO |
| Класс `AudioOptimizer` | Функции в `audio.py` | Stateless операции не требуют класса |
| Класс `VideoFrameExtractor` | Функции в `video.py` | Аналогично |

### 6.2 Что добавилось

- **DependencyError** — кастомное исключение с инструкциями по установке ffmpeg
- **Quality presets** — именованные пресеты вместо числовых значений
- **frames_to_bytes()** — конвертация PIL.Image в bytes для API

---

## 7. Метрики реализации

| Метрика | Значение |
|---------|----------|
| Новых файлов | 4 (audio_analyzer, video_analyzer, audio.py, video.py) |
| Изменённых файлов | 3 (image_analyzer, markdown_parser, smart_splitter) |
| Строк кода (prod) | ~650 |
| Исправленных багов | 3 |

---

## 8. Зависимости системы

### 8.1 FFmpeg (обязательно)

FFmpeg требуется для:
- `pydub` — аудио конвертация
- `imageio[pyav]` — видео декодирование

Установка:
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
apt install ffmpeg
```

### 8.2 Проверка при запуске

Все утилиты вызывают `ensure_ffmpeg()` в начале работы:

```python
def ensure_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise DependencyError(
            "ffmpeg not found. Install: brew install ffmpeg (macOS) "
            "or apt install ffmpeg (Linux)"
        )
```

---

## 9. Definition of Done

- [x] `GeminiAudioAnalyzer` работает с реальным API
- [x] `GeminiVideoAnalyzer` анализирует кадры + аудио
- [x] Утилиты оптимизации аудио (32kbps OGG)
- [x] Утилиты извлечения кадров (3 режима)
- [x] `MediaQueueProcessor` роутит по MIME-type
- [x] Все баги исправлены
- [x] Код следует SOLID принципам
- [x] Docstrings в Google-стиле
