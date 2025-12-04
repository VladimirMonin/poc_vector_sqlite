---
title: Коды ошибок
description: Справочник исключений и ошибок Semantic Core
tags: [reference, errors, exceptions, troubleshooting]
---

# Коды ошибок ⚠️

Справочник исключений и типичных ошибок Semantic Core.

## Иерархия исключений 📊

```
Exception
├── MediaProcessingError     # Ошибка обработки медиа
├── DependencyError          # Отсутствует системная зависимость
├── ValueError               # Некорректные данные
├── FileNotFoundError        # Файл не найден
├── NotImplementedError      # Метод не реализован
└── pydantic.ValidationError # Ошибка валидации конфига
```

## MediaProcessingError 🎬

**Модуль:** `semantic_core.infrastructure.gemini.resilience`

Выбрасывается после исчерпания retry-попыток при обращении к Gemini API.

```python
from semantic_core.infrastructure.gemini.resilience import MediaProcessingError

try:
    result = await image_analyzer.analyze(image_path)
except MediaProcessingError as e:
    print(f"Анализ не удался после всех попыток: {e}")
```

**Причины:**

| Код     | Описание                          | Решение                          |
| :------ | :-------------------------------- | :------------------------------- |
| `429`   | Rate limit exceeded               | Уменьшить `media_rpm_limit`      |
| `503`   | Service unavailable               | Подождать и повторить            |
| `500`   | Internal server error             | Проверить формат файла           |

**Retryable паттерны:**

```python
RETRYABLE_PATTERNS = (
    "429",       # Rate limit
    "503",       # Service unavailable
    "500",       # Internal server error
    "timeout",   # Timeout
    "connection",# Connection error
    "reset",     # Connection reset
)
```

## DependencyError 🔧

**Модуль:** `semantic_core.infrastructure.media.utils.audio`

Выбрасывается при отсутствии системной зависимости (ffmpeg).

```python
from semantic_core.infrastructure.media.utils.audio import DependencyError

try:
    ensure_ffmpeg()
except DependencyError as e:
    print(f"Установите ffmpeg: {e}")
```

**Решение:**

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows
# Скачать с https://ffmpeg.org/download.html
```

## ValueError 📋

Выбрасывается при некорректных входных данных.

| Контекст                  | Сообщение                              | Решение                    |
| :------------------------ | :------------------------------------- | :------------------------- |
| Gemini response           | `Gemini returned empty response`       | Проверить API ключ         |
| JSON parsing              | `Invalid JSON in Gemini response`      | Проверить модель           |
| API key validation        | `API key must start with 'AIza'`       | Проверить формат ключа     |
| Dimension validation      | `embedding_dimension must be 256-3072` | Исправить размерность      |

## FileNotFoundError 📁

Выбрасывается при отсутствии файла.

| Контекст         | Сообщение                         | Решение                     |
| :--------------- | :-------------------------------- | :-------------------------- |
| Video processing | `Video file not found: {path}`    | Проверить путь к видео      |
| Audio processing | `Audio file not found: {path}`    | Проверить путь к аудио      |
| Image analysis   | `Image file not found: {path}`    | Проверить путь к изображению|

## ValidationError (Pydantic) ✅

Выбрасывается при невалидной конфигурации.

```python
from pydantic import ValidationError
from semantic_core.config import SemanticConfig

try:
    config = SemanticConfig(
        embedding_dimension=5000,  # Некорректно: max 3072
        log_level="SUPER_DEBUG",   # Некорректно: нет такого уровня
    )
except ValidationError as e:
    print(e.errors())
```

**Типичные ошибки валидации:**

| Поле                  | Ошибка                           | Ограничение        |
| :-------------------- | :------------------------------- | :----------------- |
| `embedding_dimension` | `Input should be <= 3072`        | 256–3072           |
| `media_rpm_limit`     | `Input should be <= 100`         | 1–100              |
| `search_limit`        | `Input should be >= 1`           | 1–100              |
| `log_level`           | `Input should be 'DEBUG'...`     | TRACE–CRITICAL     |
| `splitter`            | `Input should be 'simple'...`    | simple \| smart    |
| `search_type`         | `Input should be 'vector'...`    | vector\|fts\|hybrid|

## NotImplementedError 🚧

Выбрасывается абстрактными методами интерфейсов.

```python
from semantic_core.interfaces import BaseEmbedder

class MyEmbedder(BaseEmbedder):
    pass  # Не реализованы методы

embedder = MyEmbedder()
embedder.embed_text("test")  # NotImplementedError
```

**Требуемые методы по интерфейсам:**

| Интерфейс              | Обязательные методы                |
| :--------------------- | :--------------------------------- |
| `BaseEmbedder`         | `embed_text`, `embed_batch`        |
| `BaseVectorStore`      | `add`, `search`, `get_by_id`, ...  |
| `BaseSplitter`         | `split`                            |
| `BaseContextStrategy`  | `enrich`                           |
| `DocumentParser`       | `parse`                            |
| `BaseLLMProvider`      | `generate`                         |

## Диагностика ошибок 🔍

### Проверка окружения

```bash
# Проверить конфигурацию
semantic config show

# Диагностика системы
semantic doctor
```

### Включение отладки

```bash
# Через env
export SEMANTIC_LOG_LEVEL=DEBUG

# Через CLI
semantic --log-level DEBUG ingest doc.md
```

### Trace-уровень логирования

```python
from semantic_core.config import get_config
from semantic_core.utils.logger import configure_logging

config = get_config(log_level="TRACE")
configure_logging(level="TRACE")
```

## См. также 🔗

- [CLI команды](cli-commands.md) — команда `doctor` для диагностики
- [Конфигурация](configuration-options.md) — параметр `log_level`
- [Интерфейсы](interfaces.md) — требуемые методы
