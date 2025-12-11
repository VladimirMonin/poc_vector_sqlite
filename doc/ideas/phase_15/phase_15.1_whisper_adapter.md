# Phase 15.1: Whisper Adapter — Локальная Транскрипция

**Статус:** TODO  
**Ответственный:** Agent 1  
**Длительность:** 4-5 дней  
**Зависимости:** Phase 15.0 (Interface Contracts) ✅

---

## 🎯 Цель

Реализовать `WhisperTranscriber` — провайдер локальной транскрипции аудио, альтернативу `GeminiAudioAnalyzer`. Использует модели Whisper (OpenAI) через библиотеки `openai-whisper` или `faster-whisper`.

**Экономия:** ~90% стоимости vs Gemini Audio API для длинных аудио.

---

## 📦 Что Нужно Реализовать

### 1. **Основной Класс: `WhisperTranscriber`**

**Файл:** `semantic_core/infrastructure/whisper/transcriber.py`

```python
from semantic_core.interfaces import ITranscriber, TranscriptionResult, TranscriptionSegment
from typing import Optional, Literal
import whisper  # или faster_whisper

class WhisperTranscriber(ITranscriber):
    """
    Локальная транскрипция через Whisper.
    
    Attributes:
        model_name: tiny/base/small/medium/large/turbo
        device: cpu/cuda
        language: ru/en/auto (None = auto-detect)
    """
    
    def __init__(
        self,
        model_name: str = "base",
        device: Literal["cpu", "cuda"] = "cpu",
        language: Optional[str] = None
    ):
        # Загрузить модель Whisper
        # Логирование через semantic logger
        pass
    
    def transcribe(
        self,
        audio_path: str,
        include_timestamps: bool = True
    ) -> TranscriptionResult:
        """
        Транскрибировать аудио файл.
        
        Returns:
            TranscriptionResult с полным текстом и сегментами (если timestamps=True)
        """
        pass
```

**Требования:**

- ✅ Реализует интерфейс `ITranscriber` из `semantic_core/interfaces/transcriber.py`
- ✅ Возвращает `TranscriptionResult` с корректной структурой
- ✅ Поддерживает `include_timestamps=True` → заполняет `segments: list[TranscriptionSegment]`
- ✅ Обрабатывает ошибки: файл не найден, неподдерживаемый формат, CUDA недоступна
- ✅ Логирование через `semantic_core.utils.logger` (bind model_name, device)

---

### 2. **Выбор Библиотеки**

**Опции:**

| Библиотека | Плюсы | Минусы |
|------------|-------|--------|
| `openai-whisper` | Официальная, простая | Медленная на CPU |
| `faster-whisper` | 4x быстрее, меньше RAM | Требует `ctranslate2` |

**Рекомендация:** Начать с `openai-whisper` (проще), потом можно добавить `faster-whisper` как опцию.

---

### 3. **Конфигурация (опционально)**

Добавить в `semantic_core/config.py`:

```python
class WhisperConfig(BaseModel):
    model_name: str = "base"  # tiny/base/small/medium/large
    device: str = "cpu"       # cpu/cuda
    language: Optional[str] = None  # auto-detect
```

---

## ✅ Checklist Самопроверки

Перед отправкой на Code Review убедись:

### **Код:**

- [ ] `WhisperTranscriber` реализует `ITranscriber` (все методы)
- [ ] `transcribe()` возвращает `TranscriptionResult` с правильными полями
- [ ] Поддержка `include_timestamps=True/False`
- [ ] Обработка ошибок с информативными сообщениями
- [ ] Логирование: старт транскрипции, завершение, ошибки (с эмодзи 🎤)
- [ ] Код следует стилю проекта (docstrings, type hints)

### **Производительность:**

- [ ] Модель загружается один раз (кэшируется)
- [ ] Поддержка GPU (`device='cuda'`) если доступна
- [ ] Нет утечек памяти при batch обработке

### **Документация:**

- [ ] Docstrings для класса и методов
- [ ] Примеры использования в комментариях
- [ ] Описание параметров моделей (tiny vs large - качество/скорость)

---

## 🧪 Список Тестов

### **Unit Tests** (`tests/unit/infrastructure/whisper/test_whisper_transcriber.py`)

```python
import pytest
from semantic_core.infrastructure.whisper import WhisperTranscriber
from semantic_core.interfaces import TranscriptionResult

class TestWhisperTranscriber:
    """Unit тесты для WhisperTranscriber"""
    
    def test_transcriber_initialization(self):
        """Проверка инициализации с разными параметрами"""
        # model_name, device, language
        transcriber = WhisperTranscriber(model_name="tiny", device="cpu")
        assert transcriber.model_name == "tiny"
        assert transcriber.device == "cpu"
    
    def test_transcribe_returns_transcription_result(self):
        """Проверка возвращаемого типа"""
        transcriber = WhisperTranscriber(model_name="tiny")
        result = transcriber.transcribe("tests/fixtures/audio/sample.mp3")
        assert isinstance(result, TranscriptionResult)
        assert result.text  # Не пустой текст
        assert result.language  # Определён язык
    
    def test_transcribe_with_timestamps(self):
        """Проверка заполнения segments при timestamps=True"""
        transcriber = WhisperTranscriber(model_name="tiny")
        result = transcriber.transcribe(
            "tests/fixtures/audio/sample.mp3",
            include_timestamps=True
        )
        assert result.segments  # Не пустой список
        assert len(result.segments) > 0
        
        # Проверка структуры сегмента
        segment = result.segments[0]
        assert segment.start >= 0
        assert segment.end > segment.start
        assert segment.text
    
    def test_transcribe_without_timestamps(self):
        """Проверка что segments пустой при timestamps=False"""
        transcriber = WhisperTranscriber(model_name="tiny")
        result = transcriber.transcribe(
            "tests/fixtures/audio/sample.mp3",
            include_timestamps=False
        )
        assert result.segments == []  # Пустой
    
    def test_device_selection_cpu(self):
        """Проверка работы на CPU"""
        transcriber = WhisperTranscriber(device="cpu")
        result = transcriber.transcribe("tests/fixtures/audio/sample.mp3")
        assert result.text
    
    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_device_selection_cuda(self):
        """Проверка работы на GPU (если доступен)"""
        transcriber = WhisperTranscriber(device="cuda")
        result = transcriber.transcribe("tests/fixtures/audio/sample.mp3")
        assert result.text
    
    def test_model_loading_different_sizes(self):
        """Проверка загрузки разных моделей"""
        for model_name in ["tiny", "base", "small"]:
            transcriber = WhisperTranscriber(model_name=model_name)
            assert transcriber.model_name == model_name
    
    def test_error_handling_file_not_found(self):
        """Проверка обработки несуществующего файла"""
        transcriber = WhisperTranscriber(model_name="tiny")
        with pytest.raises(FileNotFoundError):
            transcriber.transcribe("nonexistent.mp3")
    
    def test_error_handling_invalid_format(self):
        """Проверка обработки неподдерживаемого формата"""
        transcriber = WhisperTranscriber(model_name="tiny")
        with pytest.raises(ValueError):
            transcriber.transcribe("tests/fixtures/images/test.jpg")  # Не аудио
    
    def test_interface_compliance(self):
        """Проверка соответствия интерфейсу ITranscriber"""
        from semantic_core.interfaces import ITranscriber
        transcriber = WhisperTranscriber()
        assert isinstance(transcriber, ITranscriber)
        assert hasattr(transcriber, "transcribe")
    
    def test_language_detection_auto(self):
        """Проверка автоопределения языка"""
        transcriber = WhisperTranscriber(language=None)  # Auto
        result = transcriber.transcribe("tests/fixtures/audio/russian_speech.mp3")
        assert result.language == "ru"
    
    def test_language_forced(self):
        """Проверка принудительной установки языка"""
        transcriber = WhisperTranscriber(language="en")
        result = transcriber.transcribe("tests/fixtures/audio/sample.mp3")
        assert result.language == "en"
    
    def test_model_caching(self):
        """Проверка что модель загружается один раз"""
        transcriber = WhisperTranscriber(model_name="tiny")
        
        # Первая транскрипция
        result1 = transcriber.transcribe("tests/fixtures/audio/sample1.mp3")
        
        # Вторая транскрипция - модель НЕ должна загружаться повторно
        result2 = transcriber.transcribe("tests/fixtures/audio/sample2.mp3")
        
        assert result1.text
        assert result2.text
```

---

## 📊 Acceptance Criteria

**Phase 15.1 считается завершённой, если:**

1. ✅ Все unit тесты проходят (минимум 12 тестов)
2. ✅ `WhisperTranscriber` корректно реализует `ITranscriber`
3. ✅ Транскрипция работает на CPU и GPU (если доступен)
4. ✅ Поддержка моделей: tiny, base, small, medium, large
5. ✅ Обработка ошибок с понятными сообщениями
6. ✅ Логирование через semantic logger
7. ✅ Код следует стилю проекта (docstrings, type hints)

---

## 📝 Дополнительные Задачи (Опционально)

Если останется время:

- [ ] Поддержка `faster-whisper` как альтернативной имплементации
- [ ] Benchmark: сравнение скорости tiny/base/small/medium/large
- [ ] Benchmark: сравнение качества (WER - Word Error Rate) с Gemini
- [ ] Поддержка `batch_transcribe()` для множества файлов
- [ ] Кэширование результатов транскрипции (SQLite cache)

---

## 🚀 Начало Работы

1. Создай ветку: `git checkout -b phase_15.1_whisper`
2. Установи зависимости: `pip install openai-whisper`
3. Изучи интерфейс: `semantic_core/interfaces/transcriber.py`
4. Посмотри пример: `semantic_core/infrastructure/gemini/audio_analyzer.py` (как Gemini это делает)
5. Создай файл: `semantic_core/infrastructure/whisper/transcriber.py`
6. Напиши тесты: `tests/unit/infrastructure/whisper/test_whisper_transcriber.py`
7. Запусти тесты: `pytest tests/unit/infrastructure/whisper/ -v`
8. Сделай коммиты (формат: `phase 15.1 feat: ...`)

---

## 📚 Полезные Ссылки

- **Whisper GitHub:** <https://github.com/openai/whisper>
- **Faster Whisper:** <https://github.com/guillaumekln/faster-whisper>
- **Whisper Model Card:** <https://github.com/openai/whisper/blob/main/model-card.md>
- **Context7 (для документации):** `/openai/whisper`

---

**Удачи! 🚀**  
_Координатор Phase 15_
