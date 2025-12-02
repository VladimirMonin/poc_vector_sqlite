# 🗺️ Phase 6.2: Audio & Video Analysis (Extended)

**Цель:** Расширить медиа-инфраструктуру из Phase 6.0 для поддержки аудио и видео.

**Предусловие:** Phase 6.0 (Images + Queue) и Phase 6.1 (Tests) завершены.

**Принцип:** Переиспользуем максимум из 6.0 — те же DTO, очередь, rate limiter, resilience.

---

## 📐 Архитектура (Расширение 6.0)

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  ingest_media() │────▶│  MediaTaskModel │────▶│ QueueProcessor  │
│  auto-detect    │     │   (SQLite)      │     │ + RateLimiter   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                         │
                        ┌────────────────────────────────┼────────────────────────────────┐
                        ▼                                ▼                                ▼
               ┌─────────────────┐              ┌─────────────────┐              ┌─────────────────┐
               │ ImageAnalyzer   │              │ AudioAnalyzer   │              │ VideoAnalyzer   │
               │ gemini-2.5-flash│              │ gemini-2.5-flash│              │ gemini-2.5-pro  │
               └─────────────────┘              └─────────────────┘              └─────────────────┘
```

**Новое в 6.2:**

- `GeminiAudioAnalyzer` — транскрипция + анализ аудио
- `GeminiVideoAnalyzer` — мультимодальный анализ (кадры + аудио)
- `AudioExtractor` — извлечение аудио-дорожки из видео
- `FrameExtractor` — извлечение кадров из видео
- `MediaRouter` — маршрутизация по типу медиа

---

## 📦 1. Обновление DTO (`domain/media.py`)

**Добавляем поля для audio/video:**

```python
@dataclass
class MediaAnalysisResult:
    """Результат анализа (расширен для audio/video)."""
    
    # Общие
    description: str
    alt_text: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    
    # Изображения
    ocr_text: Optional[str] = None
    
    # Аудио/Видео (NEW)
    transcription: Optional[str] = None
    participants: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)
    duration_seconds: Optional[float] = None
    
    # Статистика
    tokens_used: Optional[int] = None


@dataclass
class VideoAnalysisConfig:
    """Конфигурация анализа видео."""
    
    # Режим извлечения кадров
    frame_mode: Literal["fps", "total", "interval"] = "total"
    
    # Параметры режимов
    fps: float = 1.0              # Для mode="fps"
    frame_count: int = 10         # Для mode="total"
    interval_seconds: float = 5.0 # Для mode="interval"
    
    # Качество кадров
    frame_quality: Literal["hd", "fhd", "balanced"] = "hd"
    
    # Лимиты
    max_frames: int = 50
    include_audio: bool = True
```

---

## 📦 2. Обновление Config (`domain/config.py`)

```python
@dataclass
class MediaConfig:
    """Конфигурация для обработки медиа."""
    
    # Модели Gemini
    image_model: str = "gemini-2.5-flash"
    audio_model: str = "gemini-2.5-flash"     # Обновлено
    video_model: str = "gemini-2.5-pro"       # Для сложного контента
    
    # Rate Limiting (разные лимиты для разных типов)
    image_rpm: int = 15
    audio_rpm: int = 10   # Аудио тяжелее
    video_rpm: int = 5    # Видео самое тяжёлое
    
    # Оптимизация
    max_image_dimension: int = 1920
    max_audio_duration_sec: int = 600   # 10 минут
    max_video_duration_sec: int = 300   # 5 минут
    
    # Аудио
    audio_format: str = "ogg"
    audio_sample_rate: int = 16000
    audio_mono: bool = True
    
    # Видео
    video_frame_mode: str = "total"
    video_frame_count: int = 10
```

---

## 🛠️ 3. Утилиты Аудио (`infrastructure/media/utils/audio.py`)

**Донор:** `doc/code_assets/audio_extractor.py`

```python
"""Утилиты для работы с аудио."""

from pydub import AudioSegment
from pathlib import Path
from typing import Optional

SUPPORTED_AUDIO_TYPES = [
    "audio/mpeg", "audio/mp3", "audio/wav", 
    "audio/ogg", "audio/flac", "audio/aac"
]

def extract_audio_from_video(
    video_path: str,
    output_path: Optional[str] = None,
    format: str = "ogg",
    sample_rate: int = 16000,
    mono: bool = True,
) -> str:
    """
    Извлекает аудио-дорожку из видео.
    
    Args:
        video_path: Путь к видео
        output_path: Путь для сохранения (auto если None)
        format: Формат выхода (ogg, mp3, wav)
        sample_rate: Частота дискретизации
        mono: Конвертировать в моно
        
    Returns:
        Путь к аудио-файлу
    """
    video = AudioSegment.from_file(video_path)
    
    if mono:
        video = video.set_channels(1)
    
    video = video.set_frame_rate(sample_rate)
    
    if output_path is None:
        output_path = str(Path(video_path).with_suffix(f".{format}"))
    
    video.export(output_path, format=format)
    
    return output_path


def get_audio_duration(path: str) -> float:
    """Возвращает длительность аудио в секундах."""
    audio = AudioSegment.from_file(path)
    return len(audio) / 1000.0


def is_audio_valid(path: str, max_duration: int = 600) -> bool:
    """Проверяет валидность аудио."""
    try:
        duration = get_audio_duration(path)
        return duration <= max_duration
    except Exception:
        return False
```

---

## 🛠️ 4. Утилиты Видео (`infrastructure/media/utils/video.py`)

**Донор:** `doc/code_assets/media_frame_extractor.py`

```python
"""Утилиты для работы с видео."""

import imageio.v3 as iio
from PIL import Image
from pathlib import Path
from typing import List, Literal

SUPPORTED_VIDEO_TYPES = [
    "video/mp4", "video/webm", "video/quicktime",
    "video/x-msvideo", "video/x-matroska"
]

QUALITY_PRESETS = {
    "fhd": 1920,   # 1080p
    "hd": 1280,    # 720p
    "balanced": 960,
}


def extract_frames(
    video_path: str,
    mode: Literal["fps", "total", "interval"] = "total",
    fps: float = 1.0,
    frame_count: int = 10,
    interval_seconds: float = 5.0,
    quality: str = "hd",
    max_frames: int = 50,
) -> List[Image.Image]:
    """
    Извлекает кадры из видео.
    
    Modes:
        fps: Извлекать N кадров в секунду
        total: Извлечь ровно N равномерно распределённых кадров
        interval: Извлекать кадр каждые N секунд
    
    Returns:
        Список PIL.Image
    """
    # Получаем метаданные
    meta = iio.immeta(video_path)
    duration = meta.get("duration", 0)
    video_fps = meta.get("fps", 30)
    total_frames = int(duration * video_fps)
    
    # Вычисляем индексы кадров
    if mode == "fps":
        step = int(video_fps / fps)
        indices = list(range(0, total_frames, step))
    elif mode == "total":
        indices = [int(i * total_frames / frame_count) for i in range(frame_count)]
    elif mode == "interval":
        step = int(interval_seconds * video_fps)
        indices = list(range(0, total_frames, step))
    else:
        raise ValueError(f"Unknown mode: {mode}")
    
    # Лимитируем
    indices = indices[:max_frames]
    
    # Извлекаем
    frames = []
    max_dim = QUALITY_PRESETS.get(quality, 1280)
    
    for idx in indices:
        frame = iio.imread(video_path, index=idx, plugin="pyav")
        img = Image.fromarray(frame)
        
        # Ресайз
        img = _resize_frame(img, max_dim)
        frames.append(img)
    
    return frames


def get_video_duration(path: str) -> float:
    """Возвращает длительность видео в секундах."""
    meta = iio.immeta(path)
    return meta.get("duration", 0)


def _resize_frame(img: Image.Image, max_dim: int) -> Image.Image:
    """Ресайз кадра с сохранением пропорций."""
    width, height = img.size
    if max(width, height) <= max_dim:
        return img
    
    ratio = max_dim / max(width, height)
    new_size = (int(width * ratio), int(height * ratio))
    return img.resize(new_size, Image.Resampling.LANCZOS)
```

---

## ⚡ 5. Audio Analyzer (`infrastructure/gemini/audio_analyzer.py`)

```python
"""Анализатор аудио через Gemini."""

import base64
from pathlib import Path
from google import genai
from google.genai import types

from semantic_core.domain.media import MediaRequest, MediaAnalysisResult
from semantic_core.infrastructure.gemini.resilience import retry_with_backoff

AUDIO_SYSTEM_PROMPT = """You are an audio analyst for semantic search indexing.
Analyze the audio and provide:
1. Full transcription
2. Summary/description
3. Participants (if identifiable)
4. Keywords for search
5. Action items (if applicable)

Output JSON: {transcription, description, participants, keywords, action_items}"""


class GeminiAudioAnalyzer:
    """Анализатор аудио через Gemini."""
    
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
        """Анализирует аудио-файл."""
        
        # 1. Читаем аудио
        audio_path = request.resource.path
        audio_bytes = Path(audio_path).read_bytes()
        
        # 2. Собираем промпт
        prompt_parts = []
        if request.context_text:
            prompt_parts.append(f"Context: {request.context_text}")
        if request.user_prompt:
            prompt_parts.append(request.user_prompt)
        else:
            prompt_parts.append("Transcribe and analyze this audio.")
        
        prompt = "\n".join(prompt_parts)
        
        # 3. Inline audio (до 20MB)
        audio_part = types.Part.from_bytes(
            data=audio_bytes,
            mime_type=request.resource.mime_type,
        )
        
        # 4. Вызываем API
        response = self.client.models.generate_content(
            model=self.model,
            contents=[prompt, audio_part],
            config=types.GenerateContentConfig(
                system_instruction=AUDIO_SYSTEM_PROMPT,
                temperature=0.3,
                response_mime_type="application/json",
            ),
        )
        
        # 5. Парсим результат
        import json
        data = json.loads(response.text)
        
        return MediaAnalysisResult(
            description=data.get("description", ""),
            transcription=data.get("transcription"),
            participants=data.get("participants", []),
            keywords=data.get("keywords", []),
            action_items=data.get("action_items", []),
        )
```

---

## ⚡ 6. Video Analyzer (`infrastructure/gemini/video_analyzer.py`)

**Донор:** `doc/code_assets/video_analyzer.py`

```python
"""Мультимодальный анализатор видео через Gemini."""

import json
from pathlib import Path
from typing import List, Optional
from PIL import Image
from google import genai
from google.genai import types

from semantic_core.domain.media import (
    MediaRequest, MediaAnalysisResult, VideoAnalysisConfig
)
from semantic_core.infrastructure.gemini.resilience import retry_with_backoff
from semantic_core.infrastructure.media.utils.video import extract_frames
from semantic_core.infrastructure.media.utils.audio import extract_audio_from_video

VIDEO_SYSTEM_PROMPT = """You are a video analyst for semantic search indexing.
You receive video frames and optionally audio transcription.
Analyze the content and provide:
1. Description of what happens in the video
2. Key visual elements and text (OCR)
3. Audio summary (if provided)
4. Keywords for search
5. Participants (if identifiable)

Output JSON: {description, ocr_text, transcription, keywords, participants}"""


class GeminiVideoAnalyzer:
    """Мультимодальный анализатор видео."""
    
    # Лимит inline контента
    MAX_INLINE_SIZE = 20 * 1024 * 1024  # 20MB
    
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-pro",
        audio_analyzer: Optional["GeminiAudioAnalyzer"] = None,
    ):
        self.api_key = api_key
        self.model = model
        self.audio_analyzer = audio_analyzer
        self._client = None
    
    @property
    def client(self):
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client
    
    @retry_with_backoff(max_retries=5)
    def analyze(
        self,
        request: MediaRequest,
        config: Optional[VideoAnalysisConfig] = None,
    ) -> MediaAnalysisResult:
        """Анализирует видео (кадры + опционально аудио)."""
        
        config = config or VideoAnalysisConfig()
        video_path = str(request.resource.path)
        
        # 1. Извлекаем кадры
        frames = extract_frames(
            video_path,
            mode=config.frame_mode,
            fps=config.fps,
            frame_count=config.frame_count,
            interval_seconds=config.interval_seconds,
            quality=config.frame_quality,
            max_frames=config.max_frames,
        )
        
        # 2. Извлекаем аудио (опционально)
        audio_transcription = None
        if config.include_audio and self.audio_analyzer:
            try:
                audio_path = extract_audio_from_video(video_path)
                # Создаём запрос для аудио
                from semantic_core.domain.media import MediaResource, MediaType
                audio_resource = MediaResource(
                    path=Path(audio_path),
                    media_type=MediaType.AUDIO,
                    mime_type="audio/ogg",
                )
                audio_request = MediaRequest(resource=audio_resource)
                audio_result = self.audio_analyzer.analyze(audio_request)
                audio_transcription = audio_result.transcription
            except Exception as e:
                # Продолжаем без аудио
                pass
        
        # 3. Собираем промпт
        prompt_parts = []
        if request.context_text:
            prompt_parts.append(f"Context: {request.context_text}")
        if audio_transcription:
            prompt_parts.append(f"Audio transcription:\n{audio_transcription}")
        if request.user_prompt:
            prompt_parts.append(request.user_prompt)
        else:
            prompt_parts.append(f"Analyze these {len(frames)} frames from a video.")
        
        prompt = "\n".join(prompt_parts)
        
        # 4. Собираем контент (prompt + frames)
        contents = [prompt] + frames
        
        # 5. Вызываем API
        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=VIDEO_SYSTEM_PROMPT,
                temperature=0.4,
                response_mime_type="application/json",
            ),
        )
        
        # 6. Парсим результат
        data = json.loads(response.text)
        
        return MediaAnalysisResult(
            description=data.get("description", ""),
            ocr_text=data.get("ocr_text"),
            transcription=audio_transcription or data.get("transcription"),
            keywords=data.get("keywords", []),
            participants=data.get("participants", []),
        )
```

---

## 🔀 7. Media Router (`infrastructure/gemini/media_router.py`)

```python
"""Маршрутизатор для разных типов медиа."""

from typing import Protocol, Optional
from semantic_core.domain.media import (
    MediaType, MediaRequest, MediaAnalysisResult, VideoAnalysisConfig
)


class MediaAnalyzerProtocol(Protocol):
    """Протокол для анализаторов."""
    def analyze(self, request: MediaRequest) -> MediaAnalysisResult: ...


class MediaRouter:
    """Маршрутизирует запросы к нужному анализатору."""
    
    def __init__(
        self,
        image_analyzer: Optional[MediaAnalyzerProtocol] = None,
        audio_analyzer: Optional[MediaAnalyzerProtocol] = None,
        video_analyzer: Optional[MediaAnalyzerProtocol] = None,
    ):
        self._analyzers = {
            MediaType.IMAGE: image_analyzer,
            MediaType.AUDIO: audio_analyzer,
            MediaType.VIDEO: video_analyzer,
        }
    
    def analyze(
        self,
        request: MediaRequest,
        video_config: Optional[VideoAnalysisConfig] = None,
    ) -> MediaAnalysisResult:
        """Анализирует медиа через подходящий анализатор."""
        
        media_type = request.resource.media_type
        analyzer = self._analyzers.get(media_type)
        
        if analyzer is None:
            raise ValueError(f"No analyzer for {media_type}")
        
        # Видео может принимать дополнительный конфиг
        if media_type == MediaType.VIDEO and video_config:
            return analyzer.analyze(request, config=video_config)
        
        return analyzer.analyze(request)
    
    def supports(self, media_type: MediaType) -> bool:
        """Проверяет, поддерживается ли тип."""
        return self._analyzers.get(media_type) is not None
```

---

## 🔄 8. Обновление Queue Processor

**Добавляем поддержку audio/video:**

```python
class MediaQueueProcessor:
    """Обработчик очереди медиа-задач."""
    
    def __init__(
        self,
        db,
        router: MediaRouter,           # Вместо одного analyzer
        rate_limiters: dict,            # {MediaType: RateLimiter}
        pipeline,
    ):
        self.db = db
        self.router = router
        self.rate_limiters = rate_limiters
        self.pipeline = pipeline
    
    def process_one(self) -> bool:
        """Обрабатывает одну задачу."""
        task = self._get_pending_task()
        if not task:
            return False
        
        media_type = MediaType(task.media_type)
        
        # Используем rate limiter для этого типа
        limiter = self.rate_limiters.get(media_type)
        if limiter:
            limiter.wait()
        
        self._update_status(task.id, "processing")
        
        try:
            request = self._to_request(task)
            result = self.router.analyze(request)
            
            chunk_id = self._create_chunk(task, result)
            self._save_result(task.id, result, chunk_id)
            return True
            
        except Exception as e:
            self._update_status(task.id, "failed", error=str(e))
            return True
```

---

## 🔄 9. Обновление Pipeline

```python
class IngestionPipeline:
    
    def ingest_media(
        self,
        path: str,
        user_prompt: Optional[str] = None,
        context_text: Optional[str] = None,
        mode: Literal["sync", "async"] = "sync",
    ) -> Optional[str]:
        """
        Универсальный метод для любого медиа.
        Автоматически определяет тип.
        
        Returns:
            sync: chunk_id
            async: task_id
        """
        media_type = get_media_type(path)
        
        # Валидация по типу
        if media_type == MediaType.IMAGE:
            if not is_image_valid(path):
                raise ValueError(f"Invalid image: {path}")
        elif media_type == MediaType.AUDIO:
            if not is_audio_valid(path, self.media_config.max_audio_duration_sec):
                raise ValueError(f"Invalid audio: {path}")
        elif media_type == MediaType.VIDEO:
            duration = get_video_duration(path)
            if duration > self.media_config.max_video_duration_sec:
                raise ValueError(f"Video too long: {duration}s")
        
        # Создаём задачу
        task_id = self._create_media_task(path, user_prompt, context_text)
        
        if mode == "sync":
            self._ensure_queue_processor()
            success = self._media_queue.process_task(task_id)
            if not success:
                raise RuntimeError(f"Failed to process {path}")
            
            task = MediaTaskModel.get_by_id(task_id)
            return task.result_chunk_id
        
        return task_id
    
    # Алиасы для удобства
    def ingest_image(self, path: str, **kwargs):
        return self.ingest_media(path, **kwargs)
    
    def ingest_audio(self, path: str, **kwargs):
        return self.ingest_media(path, **kwargs)
    
    def ingest_video(self, path: str, **kwargs):
        return self.ingest_media(path, **kwargs)
```

---

## 📂 Структура файлов Phase 6.2

```text
semantic_core/
├── domain/
│   ├── config.py                      # UPDATE: audio/video settings
│   └── media.py                       # UPDATE: VideoAnalysisConfig, extended result
├── infrastructure/
│   ├── gemini/
│   │   ├── image_analyzer.py          # (from 6.0)
│   │   ├── audio_analyzer.py          # NEW
│   │   ├── video_analyzer.py          # NEW
│   │   ├── media_router.py            # NEW
│   │   ├── resilience.py              # (from 6.0)
│   │   └── rate_limiter.py            # (from 6.0)
│   └── media/
│       └── utils/
│           ├── files.py               # UPDATE: audio/video MIME
│           ├── tokens.py              # (from 6.0)
│           ├── images.py              # (from 6.0)
│           ├── audio.py               # NEW
│           └── video.py               # NEW
├── core/
│   └── media_queue.py                 # UPDATE: MediaRouter support
└── pipeline.py                        # UPDATE: ingest_media()
```

---

## 🔗 Новые зависимости

```toml
[project.optional-dependencies]
media = [
    "Pillow>=10.0.0",       # Images
    "pydub>=0.25.0",        # Audio extraction
    "imageio[pyav]>=2.31",  # Video frames
]
```

---

## 🧪 Тесты для Phase 6.2

Добавить в `tests/`:

```text
tests/
├── unit/
│   └── infrastructure/
│       ├── media/
│       │   ├── test_audio_utils.py    # extract, duration
│       │   └── test_video_utils.py    # frames, duration
│       └── gemini/
│           ├── test_audio_analyzer.py
│           ├── test_video_analyzer.py
│           └── test_media_router.py
├── integration/
│   └── media/
│       └── test_pipeline_media.py     # all types
└── e2e/
    └── gemini/
        ├── test_real_audio.py
        └── test_real_video.py
```

---

## ✅ Definition of Done (Phase 6.2)

1. **Аудио работает:**

   ```python
   chunk_id = pipeline.ingest_audio("podcast.mp3", mode="sync")
   results = store.search("machine learning")  # Находит по транскрипции!
   ```

2. **Видео работает:**

   ```python
   chunk_id = pipeline.ingest_video("lecture.mp4", mode="sync")
   results = store.search("neural networks")  # Находит!
   ```

3. **Универсальный метод:**

   ```python
   # Автоопределение типа
   pipeline.ingest_media("photo.jpg")   # → image
   pipeline.ingest_media("song.mp3")    # → audio
   pipeline.ingest_media("clip.mp4")    # → video
   ```

4. **MediaRouter работает:** Правильно маршрутизирует по типу.

5. **Rate limiting раздельный:** Image 15 RPM, Audio 10 RPM, Video 5 RPM.

---

## 🚀 Порядок реализации

1. **Утилиты:** `audio.py`, `video.py`
2. **Анализаторы:** `GeminiAudioAnalyzer`, `GeminiVideoAnalyzer`
3. **Роутер:** `MediaRouter`
4. **Обновление Queue:** поддержка разных типов
5. **Обновление Pipeline:** `ingest_media()`
6. **Тесты:** unit → integration → E2E

---

## 📝 Примечания

- **Gemini 2.5 Pro для видео** — нужен для качественного мультимодального анализа
- **Аудио через pydub** — зависит от ffmpeg (указать в README)
- **Видео через imageio[pyav]** — чистый Python, без внешних зависимостей
- **Кеширование кадров** — можно добавить в будущем для повторного анализа
