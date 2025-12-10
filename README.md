# 🧠 Semantic Core

> Production-ready библиотека для локального семантического поиска и мультимодального анализа на базе SQLite + Gemini AI.

## 🎯 Что это?

**Local-First альтернатива** облачным векторным БД. SQLite (`sqlite-vec` + `fts5`) вместо Pinecone/Weaviate, Gemini AI для интеллекта.

**Ключевые возможности:**

- 🔍 **Гибридный поиск** — векторный (по смыслу) + FTS5 (по словам) + RRF
- 🖼️ **Мультимодальность** — анализ изображений, аудио, видео через Gemini Vision/Audio
- 📝 **Smart Parsing** — AST-парсинг Markdown с иерархическим контекстом
- 💰 **Batch API** — 50% экономия через асинхронную векторизацию
- 📊 **Semantic Logging** — dual-mode логи с эмодзи-семантикой

---

## 🚀 Быстрый старт

### Установка

```bash
# Минимальная установка (только core)
poetry install

# С Google Gemini (рекомендуется)
poetry install --extras google

# С мультимодальностью (изображения, аудио, видео)
poetry install --extras media

# Полная установка (все провайдеры)
poetry install --extras all
```

### Дополнительные провайдеры

| Extra | Описание | Установка |
|-------|----------|-----------|
| `google` | Google Gemini API (embeddings, vision, audio) | `poetry install --extras google` |
| `openai` | OpenAI API (embeddings, GPT) | `poetry install --extras openai` |
| `media` | Обработка медиа (Pillow, pydub, imageio) | `poetry install --extras media` |
| `local-embeddings-mlx` | Локальные embeddings (Apple Silicon) | `poetry install --extras local-embeddings-mlx` |
| `local-whisper-mlx` | Локальный Whisper (Apple Silicon) | `poetry install --extras local-whisper-mlx` |
| `local-embeddings` | Локальные embeddings (CPU/GPU) | `poetry install --extras local-embeddings` |
| `local-whisper` | Локальный Whisper (CPU/GPU) | `poetry install --extras local-whisper` |
| `all-google` | Google + media | `poetry install --extras all-google` |
| `all-local-mlx` | Все локальные (MLX) + media | `poetry install --extras all-local-mlx` |
| `all-local` | Все локальные (CPU/GPU) + media | `poetry install --extras all-local` |
| `all` | Всё | `poetry install --extras all` |

### Настройка

```bash
cp .env.example .env
# GEMINI_API_KEY=your_key (https://aistudio.google.com/apikey)

# Диагностика окружения
poetry run semantic doctor --verbose
```

### Тесты

```bash
poetry run pytest tests/ -v
```

---

## 🛠️ Стек

| Компонент | Назначение |
|-----------|-----------|
| **SQLite + sqlite-vec** | Векторное хранилище (zero-dependency) |
| **Peewee ORM** | Модели, адаптеры, расширения SQLite |
| **google-genai** | Embeddings, Vision, Audio, Batch API |
| **markdown-it-py** | AST-парсинг Markdown |
| **Rich** | Console logging с эмодзи |

---

## 📂 Структура

```
semantic_core/
├── domain/              # DTO: Document, Chunk, MediaAnalysisResult
├── interfaces/          # Контракты: VectorStore, Embedder, Splitter
├── integrations/peewee/ # ORM: SemanticIndex, PeeweeAdapter
├── infrastructure/
│   ├── gemini/          # Embedder, ImageAnalyzer, AudioAnalyzer, VideoAnalyzer
│   └── media/utils/     # Pillow, pydub, imageio утилиты
├── processing/          # MarkdownNodeParser, SmartSplitter, HierarchicalContext
├── core/                # MediaQueueProcessor, BatchManager
└── utils/logger/        # Semantic logging (TRACE, bind, secrets)

tests/                   # 470+ тестов (unit/integration/e2e)
doc/architecture/        # 38 архитектурных документов
```

---

## 📚 Документация

| Раздел | Описание |
|--------|----------|
| **[User Guide](docs/README.md)** | Гайды, концепции, справочники — как использовать |
| **[Architecture Deep Dive](doc/architecture/00_overview.md)** | 51 документ: от эмбеддингов до Batch API |
| **[Тесты](tests/README.md)** | Структура, фикстуры, маркеры |
| **[Логирование](semantic_core/utils/logger/README.md)** | TRACE уровень, bind(), маскирование секретов |

---

## 🎓 Для кого?

- **Разработчики** — изучение семантического поиска и RAG
- **Стартапы** — локальное решение без облачных затрат
- **Исследователи** — эксперименты с мультимодальным AI

---

## 📊 Фазы разработки

| Фаза | Статус | Описание |
|------|--------|----------|
| 1-2 | ✅ | Core + Storage Layer |
| 3 | ✅ | ORM Integration (SemanticIndex) |
| 4 | ✅ | Smart Parsing (AST Markdown) |
| 5 | ✅ | Batch API + Async Processing |
| 6 | ✅ | Multimodality (Image/Audio/Video) |
| 7 | ✅ | Observability (Semantic Logging) |
| 8 | ✅ | CLI & Configuration |
| 9 | ✅ | RAG Integration |
| 10 | ✅ | Batch API Real Implementation |
| 11 | 🔄 | Documentation & Diagrams |

---

## 🔗 Ссылки

- [Gemini API](https://ai.google.dev/gemini-api/docs) • [sqlite-vec](https://github.com/asg017/sqlite-vec) • [Peewee](http://docs.peewee-orm.com/)

---

**MIT License** • Python 3.14+ • Poetry 2.0
