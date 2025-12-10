# 📐 Phase 15.0: Interface Contracts

**Статус:** Planning  
**Цель:** Определить контракты для всех провайдеров, расширить существующие интерфейсы

---

## 🎯 Задачи

1. Расширить `BaseEmbedder` свойствами `dimension` и `max_tokens`
2. Создать интерфейс `ITranscriber` для аудио→текст
3. Создать интерфейс `IVisionAnalyzer` для изображений
4. Унифицировать DTO результатов (`TranscriptionResult`, `VisionResult`)

---

## 1. Расширение `BaseEmbedder`

### Текущее состояние

**Файл:** `semantic_core/interfaces/embedder.py`

```python
class BaseEmbedder(ABC):
    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[np.ndarray]: ...
    
    @abstractmethod
    def embed_query(self, text: str) -> np.ndarray: ...
```

**Проблема:** SmartSplitter не знает лимитов модели.

### Целевое состояние

```python
class BaseEmbedder(ABC):
    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[np.ndarray]: ...
    
    @abstractmethod
    def embed_query(self, text: str) -> np.ndarray: ...
    
    @property
    @abstractmethod
    def dimension(self) -> int:
        """Размерность выходного вектора (768, 1024, 1536, etc.)."""
        ...
    
    @property
    @abstractmethod  
    def max_tokens(self) -> int:
        """Максимальное количество токенов на вход (512, 2048, 8192, etc.)."""
        ...
```

### Влияние на существующий код

| Файл | Изменение |
|------|-----------|
| `infrastructure/gemini/embedder.py` | Добавить `dimension`, `max_tokens` properties |
| `tests/test_phase_1_architecture.py` | Обновить тест `test_interface_segregation` (2→4 метода) |

---

## 2. Интерфейс `ITranscriber`

### Мотивация

Сейчас `GeminiAudioAnalyzer` возвращает `MediaAnalysisResult` с полями:

- `transcription: str` — сырой текст
- `description: str` — summary

Whisper возвращает другую структуру:

- `text: str` — текст
- `segments: list[Segment]` — с таймкодами!

**Нужен единый контракт.**

### Диаграмма классов

```
┌─────────────────────────────────────────┐
│           <<interface>>                  │
│           ITranscriber                   │
├─────────────────────────────────────────┤
│ + transcribe(path: Path) →              │
│       TranscriptionResult                │
│ + supported_formats: list[str]          │
└─────────────────────────────────────────┘
                    △
                    │
         ┌─────────┴─────────┐
         │                   │
┌────────────────┐  ┌────────────────────┐
│GeminiTranscriber│  │WhisperTranscriber │
│                 │  │                    │
│ - api_key       │  │ - model: WhisperModel│
│ - model         │  │ - device: str      │
└────────────────┘  └────────────────────┘
```

### DTO: TranscriptionResult

```python
@dataclass
class TranscriptionSegment:
    """Сегмент транскрипции с таймкодами."""
    text: str
    start_seconds: float
    end_seconds: float
    confidence: Optional[float] = None


@dataclass  
class TranscriptionResult:
    """Результат транскрипции от любого провайдера."""
    full_text: str
    segments: list[TranscriptionSegment]
    language: Optional[str] = None
    duration_seconds: Optional[float] = None
    
    @property
    def has_timestamps(self) -> bool:
        return len(self.segments) > 0 and self.segments[0].start_seconds is not None
```

### Контракт ITranscriber

**Файл:** `semantic_core/interfaces/transcriber.py` (NEW)

```python
class ITranscriber(ABC):
    """Интерфейс для транскрипции аудио."""
    
    @abstractmethod
    def transcribe(
        self, 
        audio_path: Path,
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        """Транскрибирует аудиофайл.
        
        Args:
            audio_path: Путь к аудиофайлу (mp3, wav, flac, etc.)
            language: Код языка (ru, en, auto)
            
        Returns:
            TranscriptionResult с текстом и сегментами.
        """
        ...
    
    @property
    def supported_formats(self) -> list[str]:
        """Поддерживаемые форматы (mp3, wav, flac, etc.)."""
        return ["mp3", "wav", "flac", "m4a", "ogg"]
```

---

## 3. Интерфейс `IVisionAnalyzer`

### Текущее состояние

`GeminiImageAnalyzer` возвращает `MediaAnalysisResult`:

- `description: str`
- `alt_text: str`
- `keywords: list[str]`
- `ocr_text: Optional[str]`

### Контракт IVisionAnalyzer

**Файл:** `semantic_core/interfaces/vision.py` (NEW)

```python
@dataclass
class VisionResult:
    """Результат анализа изображения."""
    description: str
    alt_text: str
    keywords: list[str]
    ocr_text: Optional[str] = None


class IVisionAnalyzer(ABC):
    """Интерфейс для анализа изображений."""
    
    @abstractmethod
    def analyze(
        self,
        image_path: Path,
        prompt: Optional[str] = None,
    ) -> VisionResult:
        """Анализирует изображение.
        
        Args:
            image_path: Путь к изображению.
            prompt: Кастомный промпт (опционально).
            
        Returns:
            VisionResult с описанием и метаданными.
        """
        ...
```

---

## 4. Обновление `SemanticCore`

### Текущая сигнатура (проблема)

```python
# pipeline.py
class SemanticCore:
    def __init__(
        self,
        ...
        image_analyzer: Optional["GeminiImageAnalyzer"] = None,  # ❌ Конкретный тип
        audio_analyzer: Optional["GeminiAudioAnalyzer"] = None,  # ❌ Конкретный тип
    ):
```

### Целевая сигнатура

```python
class SemanticCore:
    def __init__(
        self,
        embedder: BaseEmbedder,
        store: BaseVectorStore,
        splitter: BaseSplitter,
        context_strategy: BaseContextStrategy,
        transcriber: Optional[ITranscriber] = None,      # ✅ Интерфейс
        vision_analyzer: Optional[IVisionAnalyzer] = None,  # ✅ Интерфейс
        llm: Optional[BaseLLMProvider] = None,
        config: Optional[SemanticConfig] = None,
    ):
```

---

## 5. План реализации

| Шаг | Файл | Действие |
|-----|------|----------|
| 1 | `interfaces/embedder.py` | Добавить `dimension`, `max_tokens` abstract properties |
| 2 | `interfaces/transcriber.py` | Создать `ITranscriber`, `TranscriptionResult` |
| 3 | `interfaces/vision.py` | Создать `IVisionAnalyzer`, `VisionResult` |
| 4 | `interfaces/__init__.py` | Экспортировать новые интерфейсы |
| 5 | `infrastructure/gemini/embedder.py` | Имплементировать новые properties |
| 6 | `pipeline.py` | Заменить типы на интерфейсы |
| 7 | `tests/` | Обновить тесты интерфейсов |

---

## ✅ Критерии готовности

- [ ] `BaseEmbedder` имеет `dimension` и `max_tokens` properties
- [ ] `ITranscriber` определён с `TranscriptionResult` DTO
- [ ] `IVisionAnalyzer` определён с `VisionResult` DTO
- [ ] `GeminiEmbedder` реализует новые properties
- [ ] `SemanticCore` принимает интерфейсы вместо конкретных классов
- [ ] Все существующие тесты проходят
