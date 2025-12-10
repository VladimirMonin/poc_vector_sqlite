# 🔌 Phase 15: Provider-Agnostic Architecture

**Дата начала:** Декабрь 2025  
**Статус:** Planning  
**Зависимости:** Phase 14.0 (Smart-Splitter интеграция)

---

## 🎯 Миссия

Превратить `SemanticCore` из **Gemini-монолита** в **универсальный конструктор**, где:

- Embeddings: Gemini / OpenAI / Local (MLX, sentence-transformers)
- Transcription: Gemini Audio / Whisper (local MLX/PyTorch)  
- Vision: Gemini Vision / Local (Qwen3-VL)
- LLM: Gemini / OpenAI-compatible / Local

**Философия:** Код адаптеров вставляется в библиотеку, зависимости — опциональные.

---

## 📋 Оглавление подфаз

| Подфаза | Название | Статус | Описание |
|---------|----------|--------|----------|
| [15.0](phase_15.0.md) | Interface Contracts | 🔲 Planning | Расширение `BaseEmbedder`, создание `ITranscriber`, `IVisionAnalyzer` |
| [15.1](phase_15.1.md) | Local Whisper Adapter | 🔲 Planning | Интеграция кода из `examples/Whisper-Voice-Machine` |
| [15.2](phase_15.2.md) | Local Embeddings | 🔲 Planning | MLX embeddings из `examples/poc_apple_local_llm` |
| [15.3](phase_15.3.md) | OpenAI-Compatible LLM | 🔲 Planning | Универсальный адаптер через `base_url` |
| [15.4](phase_15.4.md) | Configuration & Factory | 🔲 Planning | Multi-provider конфиг + ComponentFactory |
| [15.5](phase_15.5.md) | Optional Dependencies | 🔲 Planning | `pip install semantic-core[local]` |

---

## 📊 Архитектурный обзор

### Текущее состояние (Phase 14)

```
SemanticCore
├── embedder: GeminiEmbedder          ← Жёсткая привязка
├── store: BaseVectorStore            ← ✅ Абстракция
├── splitter: BaseSplitter            ← ✅ Абстракция  
├── image_analyzer: GeminiImageAnalyzer   ← Жёсткая привязка
├── audio_analyzer: GeminiAudioAnalyzer   ← Жёсткая привязка
└── video_analyzer: GeminiVideoAnalyzer   ← Жёсткая привязка
```

### Целевое состояние (Phase 15)

```
SemanticCore
├── embedder: IEmbedder               ← Интерфейс + dimension/max_tokens
├── store: IVectorStore               ← ✅ Уже готово
├── splitter: ISplitter               ← ✅ Уже готово (+ связь с embedder)
├── transcriber: ITranscriber         ← НОВЫЙ интерфейс
├── vision: IVisionAnalyzer           ← НОВЫЙ интерфейс
└── llm: ILLMProvider                 ← ✅ Уже готово
```

---

## 🗺️ Ключевые референсы

### Существующий код для переиспользования

| Компонент | Источник | Что берём |
|-----------|----------|-----------|
| Whisper MLX | `examples/Whisper-Voice-Machine/whisper_model_mlx.py` | `WhisperModelMLX` класс, auto-device detection |
| Whisper PyTorch | `examples/Whisper-Voice-Machine/whisper_model.py` | `WhisperModel`, transformers pipeline |
| MLX Embeddings | `examples/poc_apple_local_llm/src/lightweight_core.py` | `_generate_embedding()`, mlx-embeddings |
| Qwen3 Embeddings | `examples/poc_apple_local_llm/EMBEDDINGS_MODELS_INVESTIGATION.md` | Результаты тестов, модель `Qwen3-Embedding-0.6B-4bit-DWQ` |

### Текущие интерфейсы (требуют расширения)

| Интерфейс | Файл | Что добавить |
|-----------|------|--------------|
| `BaseEmbedder` | `semantic_core/interfaces/embedder.py` | `dimension`, `max_tokens` properties |
| `BaseLLMProvider` | `semantic_core/interfaces/llm.py` | ✅ Готов |
| `BaseVectorStore` | `semantic_core/interfaces/vector_store.py` | ✅ Готов |

---

## 🔗 Связь с Phase 14

**Phase 14.1** вводит `MediaPipeline` и `ProcessingStep` архитектуру.  
**Phase 15** добавляет **абстракции для провайдеров** внутри этих шагов:

```
┌─────────────────────────────────────────────────────────────┐
│                     MediaPipeline (14.1)                     │
├─────────────────────────────────────────────────────────────┤
│  TranscriptionStep                                           │
│  ├── uses: ITranscriber (15.0)                              │
│  │   ├── GeminiTranscriber (google)                         │
│  │   └── WhisperTranscriber (local) ← Phase 15.1            │
│  │                                                          │
│  OCRStep                                                     │
│  ├── uses: IVisionAnalyzer (15.0)                           │
│  │   ├── GeminiVision (google)                              │
│  │   └── LocalVision (Qwen3-VL) ← Phase 15.2                │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 Итоговая структура пакета

```
semantic_core/
├── interfaces/
│   ├── embedder.py          # + dimension, max_tokens
│   ├── transcriber.py       # NEW: ITranscriber
│   ├── vision.py            # NEW: IVisionAnalyzer
│   └── ...
│
├── infrastructure/
│   ├── google/              # Gemini adapters (rename from gemini/)
│   │   ├── embedder.py
│   │   ├── transcriber.py   # Wrap GeminiAudioAnalyzer
│   │   └── vision.py        # Wrap GeminiImageAnalyzer
│   │
│   ├── local/               # NEW: Local adapters
│   │   ├── whisper.py       # From examples/Whisper-Voice-Machine
│   │   ├── embeddings.py    # From examples/poc_apple_local_llm
│   │   └── vision.py        # Qwen3-VL (future)
│   │
│   └── openai/              # NEW: OpenAI-compatible
│       ├── embedder.py
│       └── llm.py           # Universal via base_url
│
└── core/
    └── factory.py           # NEW: ComponentFactory
```

---

## ⚠️ Риски и митигации

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Размер пакета после добавления local | Высокая | Optional dependencies `[local]`, `[openai]` |
| Несовместимость размерностей векторов | Средняя | `IEmbedder.dimension` + проверка в store |
| Разный формат таймкодов Whisper vs Gemini | Средняя | Унификация в `TranscriptionResult` DTO |
| MLX не работает на Windows/Linux | Низкая | `try-import` + fallback на PyTorch |
