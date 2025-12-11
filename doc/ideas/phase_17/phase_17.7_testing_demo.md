# Phase 17.7 — Testing & Demo Stand

> Финальное тестирование Flask App с Multi-Provider и подготовка демо стенда

**Статус:** 📋 Planned  
**Зависимости:** Phase 17.5 (Flask Multi-Provider), Phase 17.6 (Settings UI)  
**Оценка:** 2-3 дня

---

## 🎯 Цель

Полное тестирование обновлённого Flask App с Multi-Provider архитектурой и создание демонстрационного стенда для проверки всей функциональности библиотеки SemanticCore.

**Результат:**

- Проверенная работа с 2 провайдерами (Gemini, Local Qwen3)
- E2E тесты для полного цикла (ingest → search → chat)
- Демо стенд для клиента (Cloud и Local режимы)
- Обновлённая документация Flask App

---

## 📋 Задачи

### 1. Unit Testing

**Что тестируем:**

**extensions.py:**

- Инициализация с Gemini provider → embedder=768D
- Инициализация с Local provider → embedder=1024D
- Dimension mismatch → ValueError с читаемым сообщением
- MPS недоступен → fallback на CPU с warning
- MLX не установлен → ImportError с инструкцией
- Vision/Audio optional → graceful degradation (None если ошибка)

**settings.py:**

- GET `/settings` → отображает current provider
- POST `/settings/switch` → обновляет semantic.toml
- Dimension compatibility check → correct warnings

**Файлы для тестов:**

- `tests/test_extensions.py` (создать новый)
- `tests/test_settings_ui.py` (создать новый)

---

### 2. Integration Testing

**Что тестируем:**

**Сценарий 1: Gemini (Cloud Mode)**

- Запустить Flask с Gemini provider
- Загрузить тестовый документ (ingest)
- Выполнить поиск → должен найти релевантные чанки
- Выполнить RAG запрос (chat) → должен ответить с источниками
- Проверить размерности векторов → 768D

**Сценарий 2: Local (Qwen3 Mode)**

- Запустить Flask с Local provider на macOS
- Загрузить тот же документ (ingest)
- Выполнить поиск → должен найти релевантные чанки
- Выполнить RAG запрос (chat) → должен ответить с источниками
- Проверить размерности векторов → 1024D

**Сценарий 3: Provider Switch**

- Создать БД с Gemini (768D)
- Переключить на Local через Settings UI
- Проверить что показывается dimension mismatch warning
- Пересоздать БД (`rm semantic.db` + re-ingest)
- Проверить что теперь всё работает с Local (1024D)

**Файлы для тестов:**

- `tests/integration/test_flask_workflow.py` (новый)

---

### 3. E2E Testing

**Полный цикл использования:**

**Test 1: Document Ingestion**

- Upload markdown file через `/ingest`
- Проверить что chunks созданы в БД
- Проверить что embeddings сохранены (правильная dimension)

**Test 2: Search Functionality**

- Query через `/search` (hybrid mode)
- Проверить что возвращаются релевантные результаты
- Проверить что RRF scores корректны

**Test 3: RAG Chat**

- Запрос через `/chat`
- Проверить что LLM использует найденный контекст
- Проверить что sources отображаются корректно

**Test 4: Settings UI**

- Открыть `/settings`
- Проверить отображение current provider
- Switch provider → проверить обновление semantic.toml
- Проверить dimension mismatch warning

**Файлы для тестов:**

- `tests/e2e/test_flask_full_workflow.py` (новый)

---

### 4. Manual Testing Checklist

**Cloud Mode (Gemini):**

- [ ] Flask запускается с `GEMINI_API_KEY`
- [ ] Ingest работает (upload markdown)
- [ ] Search находит документы
- [ ] Chat отвечает с источниками
- [ ] Settings показывает "Gemini (768D)"

**Local Mode (macOS):**

- [ ] Flask запускается без API key
- [ ] Qwen3 загружается (см. логи "Loading qwen3-embedding")
- [ ] Ingest работает (может быть медленнее)
- [ ] Search находит документы
- [ ] Chat отвечает (нужен LLM провайдер)
- [ ] Settings показывает "Local (1024D)"

**Provider Switch:**

- [ ] Settings UI показывает dimension mismatch при несовпадении
- [ ] semantic.toml корректно обновляется
- [ ] После restart Flask использует новый провайдер

**Error Scenarios:**

- [ ] Нет API key → readable error message
- [ ] MPS недоступен → fallback на CPU
- [ ] MLX не установлен → инструкция по установке
- [ ] Dimension mismatch → ссылка на migration guide

---

### 5. Demo Stand Preparation

**Цель:** Создать готовый стенд для демонстрации клиенту

**Компоненты демо:**

**Mode 1: Cloud Demo (для любого ПК)**

- Flask App с Gemini provider
- Предзагруженная БД с документацией SemanticCore
- Демонстрация Search + Chat
- Показать скорость и качество Gemini

**Mode 2: Local Demo (только macOS)**

- Flask App с Local Qwen3 provider
- Та же БД (пересоздана с 1024D)
- Демонстрация полностью оффлайн работы
- Показать что не нужен интернет

**Документация для демо:**

- `examples/flask_app/DEMO.md` (создать)
  - Quick start для каждого режима
  - Описание функций (search, chat, ingest)
  - Примеры запросов для демонстрации
  - Troubleshooting секция

**Скриншоты для README:**

- Dashboard (главная страница)
- Search Results (с highlight)
- Chat Interface (с источниками)
- Settings UI (provider switcher)

---

### 6. Documentation Updates

**README.md:**

- Секция "Multi-Provider Architecture"
- Quick Start для Cloud и Local режимов
- Таблица сравнения провайдеров (cost, quality, hardware)
- Ссылки на Phase 17 documentation

**PROVIDERS.md (новый файл):**

- Детальное описание каждого провайдера
- Hardware requirements
- Cost analysis
- Performance benchmarks (latency, throughput)
- Migration guide между провайдерами

**DEMO.md (новый файл):**

- Инструкции по запуску демо
- Примеры запросов
- Expected results
- FAQ для демонстрации

---

## 📝 Чеклист

### Testing

- [ ] **Unit tests:**
  - [ ] `test_extensions.py` — инициализация провайдеров
  - [ ] `test_settings_ui.py` — Settings UI функциональность

- [ ] **Integration tests:**
  - [ ] `test_flask_workflow.py` — полный цикл (ingest→search→chat)

- [ ] **E2E tests:**
  - [ ] `test_flask_full_workflow.py` — все routes

- [ ] **Manual testing:**
  - [ ] Cloud mode checklist
  - [ ] Local mode checklist
  - [ ] Provider switch checklist
  - [ ] Error scenarios checklist

### Demo Stand

- [ ] **Cloud Demo:**
  - [ ] Настроить Flask с Gemini
  - [ ] Предзагрузить документацию
  - [ ] Создать список demo queries

- [ ] **Local Demo:**
  - [ ] Настроить Flask с Qwen3
  - [ ] Пересоздать БД с 1024D
  - [ ] Проверить работу на macOS

- [ ] **Documentation:**
  - [ ] Создать DEMO.md
  - [ ] Создать PROVIDERS.md
  - [ ] Обновить README.md
  - [ ] Сделать скриншоты

---

## 🧪 Testing Commands

```bash
# Unit tests
cd examples/flask_app
pytest tests/test_extensions.py -v
pytest tests/test_settings_ui.py -v

# Integration tests
pytest tests/integration/test_flask_workflow.py -v

# E2E tests (требует running Flask)
pytest tests/e2e/test_flask_full_workflow.py -v

# All tests
pytest tests/ -v --cov=app

# Manual testing
python run.py  # Cloud mode
SEMANTIC_DEFAULTS__EMBEDDING_PROVIDER=local python run.py  # Local mode
```

---

## 🎯 Результат

**Testing:**

- ✅ Все unit tests passing (>95% coverage)
- ✅ Integration tests проходят для обоих провайдеров
- ✅ E2E tests покрывают критичные сценарии
- ✅ Manual testing checklist выполнен

**Demo Stand:**

- ✅ Cloud demo работает на любом ПК
- ✅ Local demo работает на macOS
- ✅ Документация готова (DEMO.md, PROVIDERS.md)
- ✅ Скриншоты для README

**Quality:**

- ✅ Нет критичных багов
- ✅ Graceful degradation работает
- ✅ Error messages читаемые и полезные
- ✅ Performance приемлемый (Gemini: <1s, Local: <3s)

---

## 📚 Связанные фазы

- **Phase 17.5:** Flask Multi-Provider Integration
- **Phase 17.6:** Settings UI
- **Phase 17.1:** Local Embeddings Documentation
- **Phase 15.4:** ComponentFactory

---

## ⚠️ Known Issues для Phase 18

- VideoAnalyzer не в ComponentFactory (требует рефакторинг)
- OpenAI embedder не реализован (нужен для полной Multi-Provider)
- Dimension migration не автоматическая (UX можно улучшить)
- Windows/Linux нет Local embeddings (только через sentence-transformers)

---

## 💡 Next Steps

После завершения Phase 17:

- **Phase 18:** Полная Multi-Provider архитектура (OpenAI, VideoAnalyzer в Factory)
- **Phase 19:** Automatic dimension migration (одна кнопка в Settings UI)
- **Phase 20:** Performance monitoring dashboard
- **Phase 21:** Django migration (if needed)
