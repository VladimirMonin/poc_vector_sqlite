# 🎙️ Phase 15.1: Local Whisper Adapter

**Статус:** Planning  
**Зависимости:** Phase 15.0 (ITranscriber interface)  
**Цель:** Интегрировать Whisper из `examples/Whisper-Voice-Machine` в SemanticCore

---

## 🎯 Задачи

1. Перенести код Whisper из `examples/Whisper-Voice-Machine/` в библиотеку
2. Реализовать `WhisperTranscriber`, имплементирующий `ITranscriber`
3. Добавить auto-detection платформы (MLX vs PyTorch)
4. Унифицировать формат таймкодов

---

## 📂 Исходный код (донор)

### Структура проекта-донора

```
examples/Whisper-Voice-Machine/
├── whisper_model.py        # Factory + WhisperModel (PyTorch)
├── whisper_model_mlx.py    # WhisperModelMLX (Apple Silicon)
└── requirements.txt        # Зависимости
```

### Ключевые классы

**Файл:** `whisper_model.py` (lines 1-140)

```python
def create_whisper_model(model_size="large-v3-turbo"):
    """Factory: создаёт оптимальную модель для платформы."""
    device_type, device_name = get_device_info()
    
    if device_type == "mlx":
        from whisper_model_mlx import WhisperModelMLX
        return WhisperModelMLX(model_size=model_size, ...)
    else:
        return WhisperModel(model_size=model_size)
```

**Файл:** `whisper_model_mlx.py` (lines 40-110)

```python
class WhisperModelMLX:
    LIGHTNING_MODELS = ["tiny", "small", "base", "medium", "large", ...]
    MLX_WHISPER_MODELS = ["large-v3-turbo"]
    
    def transcribe(self, audio_path: str, language: str = "ru") -> str:
        # Возвращает только текст, без сегментов!
        result = self.whisper.transcribe(audio_path=audio_path, ...)
        return result.get("text", "").strip()
```

---

## 🔧 Проблема: Отсутствие таймкодов

### Текущее поведение донора

```python
# whisper_model_mlx.py
def transcribe(self, audio_path: str, language: str = "ru") -> str:
    result = self.whisper.transcribe(...)
    text = result.get("text", "").strip()  # ❌ Только текст!
    return text
```

### Что возвращает Whisper на самом деле

```python
result = whisper.transcribe(audio_path)
# result = {
#     "text": "Full transcription...",
#     "segments": [
#         {"start": 0.0, "end": 2.5, "text": "Hello world"},
#         {"start": 2.5, "end": 5.0, "text": "This is a test"},
#         ...
#     ],
#     "language": "en"
# }
```

### Решение: Извлекать сегменты

```python
def transcribe(self, audio_path: Path, language: str = "ru") -> TranscriptionResult:
    result = self._whisper.transcribe(str(audio_path), language=language)
    
    segments = [
        TranscriptionSegment(
            text=seg["text"],
            start_seconds=seg["start"],
            end_seconds=seg["end"],
        )
        for seg in result.get("segments", [])
    ]
    
    return TranscriptionResult(
        full_text=result["text"],
        segments=segments,
        language=result.get("language"),
    )
```

---

## 📊 Диаграмма последовательности

```
User                  WhisperTranscriber           WhisperModelMLX
  │                          │                           │
  │  transcribe(path)        │                           │
  │─────────────────────────►│                           │
  │                          │  load_model() [lazy]      │
  │                          │──────────────────────────►│
  │                          │                           │
  │                          │  transcribe(path)         │
  │                          │──────────────────────────►│
  │                          │                           │
  │                          │  {text, segments, lang}   │
  │                          │◄──────────────────────────│
  │                          │                           │
  │                          │  [convert to DTO]         │
  │                          │                           │
  │  TranscriptionResult     │                           │
  │◄─────────────────────────│                           │
```

---

## 🏗️ Целевая структура

```
semantic_core/infrastructure/local/
├── __init__.py
├── whisper/
│   ├── __init__.py
│   ├── transcriber.py      # WhisperTranscriber (реализует ITranscriber)
│   ├── models.py           # WhisperModel, WhisperModelMLX (из донора)
│   └── device.py           # get_device_info(), is_apple_silicon()
```

---

## 📝 Контракт WhisperTranscriber

```python
class WhisperTranscriber(ITranscriber):
    """Локальная транскрипция через Whisper (MLX/PyTorch)."""
    
    def __init__(
        self,
        model_size: str = "large-v3-turbo",
        device: Optional[str] = None,  # "mlx", "cuda", "mps", "cpu", None=auto
        batch_size: int = 12,
        quantization: Optional[str] = None,  # "4bit", "8bit", None
    ):
        self._model_size = model_size
        self._device = device or self._auto_detect_device()
        self._batch_size = batch_size
        self._quantization = quantization
        self._whisper: Optional[WhisperModel] = None  # Lazy load
    
    def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        """Транскрибирует аудио с таймкодами."""
        self._ensure_loaded()
        
        result = self._whisper.transcribe(
            str(audio_path),
            language=language or "ru",
        )
        
        return self._convert_to_dto(result)
    
    @property
    def supported_formats(self) -> list[str]:
        return ["mp3", "wav", "flac", "m4a", "ogg", "webm"]
```

---

## ⚙️ Auto-Detection логика

**Из донора:** `whisper_model.py` (lines 30-75)

```
┌─────────────────────────────────────────────────────────────┐
│                    Device Detection Flow                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Check env WHISPER_BACKEND                               │
│     ├── "mlx" + Apple Silicon → MLX                         │
│     └── "pytorch" → PyTorch (CUDA/MPS/CPU)                  │
│                                                              │
│  2. Auto-detection (default)                                │
│     ├── Apple Silicon?                                       │
│     │   ├── lightning_whisper_mlx installed? → MLX          │
│     │   └── torch.mps available? → MPS (fallback)           │
│     │                                                        │
│     └── Other platforms                                      │
│         ├── torch.cuda available? → CUDA                    │
│         └── else → CPU                                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 Зависимости

### Обязательные (ядро)

Нет новых — Whisper опциональный.

### Опциональные (`[local-whisper]`)

```toml
# pyproject.toml
[project.optional-dependencies]
local-whisper = [
    "lightning-whisper-mlx>=0.1.0; platform_machine == 'arm64' and sys_platform == 'darwin'",
    "mlx-whisper>=0.1.0; platform_machine == 'arm64' and sys_platform == 'darwin'",
    "transformers>=4.40.0; platform_machine != 'arm64' or sys_platform != 'darwin'",
    "torch>=2.0.0; platform_machine != 'arm64' or sys_platform != 'darwin'",
    "librosa>=0.10.0",
    "soundfile>=0.12.0",
]
```

---

## 🛡️ Graceful Degradation

```python
# semantic_core/infrastructure/local/whisper/__init__.py

try:
    from .transcriber import WhisperTranscriber
except ImportError as e:
    WhisperTranscriber = None
    _import_error = str(e)

def get_whisper_transcriber(**kwargs):
    """Фабрика с понятной ошибкой."""
    if WhisperTranscriber is None:
        raise ImportError(
            f"Whisper dependencies not installed. "
            f"Install with: pip install semantic-core[local-whisper]\n"
            f"Original error: {_import_error}"
        )
    return WhisperTranscriber(**kwargs)
```

---

## ✅ Критерии готовности

- [ ] `WhisperTranscriber` реализует `ITranscriber`
- [ ] Возвращает `TranscriptionResult` с сегментами и таймкодами
- [ ] Auto-detection платформы работает (MLX/CUDA/MPS/CPU)
- [ ] Lazy loading модели (загрузка при первом вызове)
- [ ] Graceful error при отсутствии зависимостей
- [ ] Unit-тесты с mock Whisper
- [ ] E2E тест на реальном аудио (1 минута)

---

## 🔗 Связанные документы

- **Донор:** `examples/Whisper-Voice-Machine/TECHNICAL.md`
- **Интерфейс:** [Phase 15.0](phase_15.0.md) — `ITranscriber`
- **Использование:** [Phase 14.1](../phase_14/phase_14.1.md) — `TranscriptionStep`
