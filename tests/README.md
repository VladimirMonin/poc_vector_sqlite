# 🧪 Тесты Semantic Core

> 980+ тестов, покрывающих от unit-логики до E2E с реальными API.

---

## 📂 Структура

```
tests/
├── conftest.py              # Все фикстуры проекта
├── unit/                    # Изолированные unit-тесты
│   ├── core/                # BatchManager, очереди
│   ├── domain/              # DTO-модели (Document, Chunk, SearchResult)
│   ├── infrastructure/      # Инфраструктурный слой
│   │   ├── batching/        # Batch API логика
│   │   ├── gemini/          # RateLimiter, Resilience
│   │   └── media/           # Токены, FileUtils
│   ├── integrations/        # SemanticIndex, SearchProxy
│   └── processing/          # Парсинг и контекст
│       ├── context/         # HierarchicalContextStrategy
│       ├── parsers/         # MarkdownNodeParser
│       └── splitters/       # SmartSplitter
├── integration/             # Тесты с реальной БД (in-memory)
│   ├── batching/            # Async ingestion workflow
│   ├── descriptor/          # ORM + SemanticIndex
│   ├── granular_search/     # Поиск по чанкам с фильтрами
│   ├── media/               # Pipeline + QueueProcessor
│   └── search/              # Гибридный поиск (RRF)
├── e2e/                     # End-to-End с реальными API
│   └── gemini/              # Реальные вызовы Gemini Vision/Audio/Video
├── fixtures/                # Тестовые данные
│   ├── images/              # Генерируемые картинки (red_square.png)
│   ├── media/               # Markdown, audio, video фикстуры
│   │   ├── audio/           # speech.mp3, noise.wav
│   │   ├── markdown/        # post_with_media.md
│   │   └── video/           # slides.mp4, talking_head.mp4
│   └── real_docs/           # evil.md и другие edge cases
├── asests/                  # Реальные картинки для E2E
└── _archived/               # Устаревшие тесты (на удаление)
```

---

## 🔧 Ключевые фикстуры

### База данных

| Фикстура | Scope | Описание |
|----------|-------|----------|
| `in_memory_db` | function | SQLite :memory: с sqlite-vec extension |
| `media_db` | function | Временная БД с MediaTaskModel |
| `test_db` | function | Старый API (для backward compatibility) |

### Embedder и Core

| Фикстура | Описание |
|----------|----------|
| `mock_embedder` | Детерминированные векторы через MD5-хеш |
| `semantic_core` | SemanticCore с mock embedder и in-memory DB |
| `smart_semantic_core` | + SmartSplitter + HierarchicalContext |

### Парсинг

| Фикстура | Описание |
|----------|----------|
| `markdown_parser` | MarkdownNodeParser instance |
| `smart_splitter` | SmartSplitter с настройками для тестов |
| `hierarchical_context` | HierarchicalContextStrategy |

### Media анализ

| Фикстура | Описание |
|----------|----------|
| `mock_image_analyzer` | MagicMock с MediaAnalysisResult |
| `mock_audio_analyzer` | + transcription, participants |
| `mock_video_analyzer` | + frames, ocr_text |
| `rate_limiter` | RateLimiter (60 RPM) |
| `media_queue_processor` | Готовый QueueProcessor с моками |

### Тестовые файлы

| Фикстура | Путь |
|----------|------|
| `red_square_path` | fixtures/images/red_square.png (генерируется) |
| `evil_md_path` | fixtures/real_docs/evil.md |
| `speech_audio_path` | fixtures/media/audio/speech.mp3 |
| `slides_video_path` | fixtures/media/video/slides.mp4 |

---

## 🏃 Запуск тестов

**ВАЖНО:** Тесты ВСЕГДА запускать через виртуальное окружение:

```bash
# Активация окружения
source .venv/bin/activate

# ИЛИ напрямую через python из venv
.venv/bin/python -m pytest tests/

# Все тесты
pytest tests/

# Только unit
pytest tests/unit/

# Только integration
pytest tests/integration/

# С покрытием
pytest tests/ --cov=semantic_core --cov-report=html

# Конкретный модуль
pytest tests/unit/processing/parsers/ -v

# По маркеру (пропустить реальные API)
pytest tests/ -m "not real_api"
```

### 🖥️ Запуск на разных машинах

```bash
# MacBook (Apple Silicon) — пропустить CUDA тесты
pytest tests/unit/ -m "not cuda"

# RTX 3080 (NVIDIA GPU) — пропустить MLX тесты
pytest tests/unit/ -m "not mlx"

# Только MLX тесты (локальные модели на Mac)
pytest tests/unit/ -m "mlx"

# Только CPU тесты (универсальные)
pytest tests/unit/ -m "cpu"
```

---

## 🏷️ Маркеры (pytest markers)

| Маркер | Описание | Когда использовать |
|--------|----------|-------------------|
| `@pytest.mark.mlx` | Тесты для Apple Silicon MLX backend | Локальные embeddings/whisper на Mac |
| `@pytest.mark.cuda` | Тесты для NVIDIA CUDA backend | sentence-transformers, PyTorch GPU |
| `@pytest.mark.cpu` | Универсальные CPU тесты | Везде |
| `@pytest.mark.requires_sentence_transformers` | Требует sentence-transformers | CUDA тесты |
| `@pytest.mark.requires_torch` | Требует PyTorch | GPU/CPU тесты |
| `@pytest.mark.real_api` | Реальные API-вызовы (медленные, платные) | E2E тесты |

**Примеры:**

```python
# Unit-тесты для MLX локальных моделей
pytestmark = pytest.mark.mlx

# CUDA тесты (sentence-transformers)
pytestmark = [pytest.mark.cuda, pytest.mark.requires_sentence_transformers]

# E2E тесты с реальным Gemini API
@pytest.mark.real_api
def test_gemini_vision_real():
    ...
```

### 🔑 API ключи для тестов

Тесты читают API ключи из **`.env` файла** в корне проекта:

```bash
# .env (не коммитится)
GEMINI_API_KEY=your-api-key-here
OPENAI_API_KEY=your-openai-key  # опционально
```

**Unit-тесты** изолируют себя от реальных ключей через фикстуру `isolate_env_for_config_tests` (см. `tests/unit/cli/conftest.py`).

**E2E тесты** (`tests/e2e/`) требуют реальный `GEMINI_API_KEY` и помечены маркером `@pytest.mark.real_api`.

---

## 📊 Покрытие по фазам

| Фаза | Описание | Основные тесты |
|------|----------|----------------|
| Phase 1 | SOLID архитектура | `test_phase_1_architecture.py` |
| Phase 2 | Storage Layer | `test_phase_2_storage.py` |
| Phase 3 | ORM Integration | `integration/descriptor/` |
| Phase 4 | Smart Parsing | `processing/parsers/`, `processing/context/` |
| Phase 5 | Async Batching | `unit/core/`, `integration/batching/` |
| Phase 6 | Multimodal | `infrastructure/media/`, `integration/media/` |
| Phase 7 | Observability | `unit/utils/logger/` |
| Phase 8 | CLI & Configuration | `unit/cli/` |
| Phase 9 | RAG | `unit/core/test_rag.py` |
| Phase 10 | Batch API Real | `unit/infrastructure/batching/` |
| Phase 13 | Audit Tools | `e2e/audit/` |
| Phase 14 | Media Crisis | `integration/media/` |
| Phase 15 | Multi-Provider | `unit/core/test_factory.py`, `unit/infrastructure/local/` |
| Phase 16 | Observatory | `unit/core/observatory/` |

---

## 💡 Соглашения

1. **Unit vs Integration** — unit тесты не должны использовать реальную БД или API
2. **Mock-first** — для API-зависимостей используем MagicMock/AsyncMock
3. **Fixtures в conftest.py** — все общие фикстуры централизованы
4. **Генерируемые файлы** — картинки создаются фикстурами через Pillow
5. **Skip при отсутствии** — `pytest.skip()` или маркеры если зависимость недоступна
6. **Запуск через venv** — **ВСЕГДА** используй `.venv/bin/python -m pytest`
7. **Платформо-зависимые тесты** — используй маркеры `mlx`/`cuda` для изоляции
8. **API ключи из .env** — unit тесты изолируют себя, e2e требуют реальные ключи

### ⚠️ Частые проблемы

**Проблема:** `ModuleNotFoundError: No module named 'numpy'`
```bash
# Решение: запускай через venv
.venv/bin/python -m pytest tests/
```

**Проблема:** Тесты падают с `GEMINI_API_KEY not configured`
```bash
# Решение: создай .env файл в корне
echo "GEMINI_API_KEY=your-key" > .env
```

**Проблема:** Падают MLX тесты на Linux
```bash
# Решение: пропусти MLX тесты
pytest tests/unit/ -m "not mlx"
```

**Проблема:** Падают CUDA тесты на Mac
```bash
# Решение: пропусти CUDA тесты
pytest tests/unit/ -m "not cuda"
```

---

## 🔗 Связанные документы

- [Concept Instructions](../.github/instructions/concept.instructions.md) — общая архитектура
- [Phase 6.6 Report](../doc/ideas/phase_6/report_phase_6.6.md) — тестирование мультимодальности
