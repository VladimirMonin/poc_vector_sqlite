# 🔌 Phase 15: Provider-Agnostic Architecture

> **Статус:** 🚧 В ПРОЦЕССЕ  
> **Дата начала:** 10.12.2025  
> **Цель:** Превратить SemanticCore из Gemini-монолита в универсальный конструктор с поддержкой множества AI-провайдеров

**Результат:** Модульная архитектура с абстрактными интерфейсами, позволяющая легко добавлять новые провайдеры (Whisper, Local Embeddings, OpenAI, Anthropic, и т.д.).

---

## 🎯 Философия фазы

До Phase 15 SemanticCore был жёстко привязан к Google Gemini:

- `GeminiEmbedder` - единственный источник эмбеддингов
- `GeminiImageAnalyzer` - единственный анализатор изображений
- `GeminiAudioAnalyzer` - единственный транскрибер
- Нет возможности использовать локальные модели или альтернативных провайдеров

**Phase 15 делает SemanticCore провайдеро-агностичным:**

- ✅ Абстрактные интерфейсы вместо конкретных классов
- ✅ Dependency Injection для всех AI-компонентов
- ✅ Лёгкое добавление новых провайдеров через наследование
- ✅ Конфигурация через TOML + фабрики
- ✅ Optional dependencies (используй что нужно)

---

## 📋 Подфазы (6 частей)

### Phase 15.0: Interface Contracts ✅ ЗАВЕРШЕНО

**Файл:** [81_interface_contracts.md](81_interface_contracts.md)  
**Статус:** ✅ ЗАВЕРШЕНО (10.12.2025)

Создание базовых контрактов для всех AI-провайдеров:

- Расширение `BaseEmbedder` свойствами `dimension` и `max_tokens`
- Новый интерфейс `ITranscriber` для audio → text
- Новый интерфейс `IVisionAnalyzer` для image → analysis
- DTOs: `TranscriptionResult`, `VisionResult`
- Обратная совместимость в `SemanticCore`

**Коммиты:**

- `phase 15.0 feat: Extend BaseEmbedder with dimension and max_tokens properties`
- `phase 15.0 feat: Create ITranscriber and IVisionAnalyzer interfaces`
- `phase 15.0 refactor: Update SemanticCore to use new interfaces with backward compatibility`
- `phase 15.0 test: Update tests for new BaseEmbedder interface`
- `phase 15.0 docs: Add Phase 15.0 architecture documentation with diagrams`

---

### Phase 15.1: Whisper Adapter (запланировано)

**Статус:** 📅 ЗАПЛАНИРОВАНО  
**Оценка:** 4-5 дней

Интеграция OpenAI Whisper для локальной транскрипции:

- `WhisperTranscriber` реализует `ITranscriber`
- Поддержка моделей: tiny, base, small, medium, large
- Chunking для длинных аудио (>30 минут)
- Конфигурация через `[providers.whisper]` секцию

---

### Phase 15.2: Local Embeddings (запланировано)

**Статус:** 📅 ЗАПЛАНИРОВАНО  
**Оценка:** 3-4 дня

Локальные эмбеддинги через sentence-transformers:

- `LocalEmbedder` реализует `BaseEmbedder`
- Поддержка моделей: multilingual-e5, labse, paraphrase-multilingual
- Настраиваемая размерность (384-1024)
- Кеширование моделей + GPU acceleration

---

### Phase 15.3: OpenAI LLM Provider (запланировано)

**Статус:** 📅 ЗАПЛАНИРОВАНО  
**Оценка:** 3-4 дня

Интеграция OpenAI для RAG:

- `OpenAILLMProvider` реализует `ILLMProvider`
- Поддержка моделей: gpt-4o, gpt-4-turbo, o1-preview
- Streaming responses для чата
- Token counting и cost tracking

---

### Phase 15.4: Configuration & Factory (запланировано)

**Статус:** 📅 ЗАПЛАНИРОВАНО  
**Оценка:** 2-3 дня

Конфигурация провайдеров через TOML + фабрики:

- Секции `[providers.embeddings]`, `[providers.vision]`, `[providers.transcription]`
- `ProviderFactory` для автоматического создания экземпляров
- Валидация конфигурации через Pydantic
- CLI команды для переключения провайдеров

---

### Phase 15.5: Optional Dependencies (запланировано)

**Статус:** 📅 ЗАПЛАНИРОВАНО  
**Оценка:** 1-2 дня

Управление зависимостями через `pyproject.toml` extras:

- `pip install semantic-core[whisper]` - Whisper support
- `pip install semantic-core[local]` - Local embeddings
- `pip install semantic-core[openai]` - OpenAI support
- `pip install semantic-core[all]` - All providers
- Graceful degradation при отсутствии зависимостей

---

## 🚀 Параллельная работа

**⚠️ ВАЖНО:** Фазы 15.1, 15.2, 15.3 могут выполняться **параллельно**!

**Почему:**

- Все три зависят только от 15.0 (интерфейсы)
- Каждая работает с разным провайдером
- Нет конфликтов в коде

**Рекомендация:** 2-3 агента одновременно → экономия **~30% времени** (9 дней вместо 12-14).

---

## 📊 Прогресс

| Подфаза | Статус | Прогресс | Дата завершения |
|---------|--------|----------|-----------------|
| 15.0 Interface Contracts | ✅ Завершено | 100% | 10.12.2025 |
| 15.1 Whisper Adapter | 📅 Запланировано | 0% | - |
| 15.2 Local Embeddings | 📅 Запланировано | 0% | - |
| 15.3 OpenAI LLM | 📅 Запланировано | 0% | - |
| 15.4 Configuration & Factory | 📅 Запланировано | 0% | - |
| 15.5 Optional Dependencies | 📅 Запланировано | 0% | - |

---

## 📚 Статьи фазы

1. [81. Interface Contracts](81_interface_contracts.md) ✅

---

## 🎓 Что дальше?

После Phase 15 открываются возможности:

**Phase 16: Debug Observatory** - визуализация и сравнение разных провайдеров

- Snapshot каждого этапа pipeline
- A/B тесты разных моделей
- Golden-file regression testing
- Multi-provider UI dashboard

**Phase 17: Advanced Providers** - интеграция enterprise-решений

- Anthropic Claude для RAG
- Cohere для embeddings + reranking
- Azure OpenAI для корпоративных клиентов
- HuggingFace Inference API

---

## 📝 Технический долг

После завершения Phase 15:

- [ ] Миграция документации с Gemini-специфичных примеров
- [ ] Обновление CLI help для новых провайдеров
- [ ] Benchmark разных embedding моделей
- [ ] Cost comparison разных LLM провайдеров
