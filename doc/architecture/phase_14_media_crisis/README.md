# 🔥 Phase 14: Media Content Crisis

> **Статус:** 🔄 В РАЗРАБОТКЕ  
> **Цель:** Устранить потери 67-95% данных в медиа-контенте

---

## 📖 Содержание фазы

### 71. Media Content Truncation Crisis

**Файл:** [71_media_content_truncation_crisis.md](71_media_content_truncation_crisis.md)

Обнаружение катастрофы: 67-95% потеря данных в медиа-файлах, hardcoded лимиты 8k токенов.

**Проблема:**

- Audio: 83 минуты → 8k токенов (потеря 67%)
- Video: OCR 65k токенов → 8k (потеря 87%)
- Long video: 360k токенов → 8k (потеря 95%)

---

### 72. Multi-Chunk Media Architecture

**Файл:** [72_multi_chunk_media_architecture.md](72_multi_chunk_media_architecture.md)

Решение кризиса: summary + transcript chunks, конфигурируемые лимиты, полное покрытие контента.

**Архитектура:**

- **Summary chunk** (max 2k tokens): краткое описание
- **Transcript chunks** (по 8k tokens): полный контент
- **OCR chunks** (через SmartSplitter): структурированный текст

---

### 73. Multilingual Media Analysis

**Файл:** [73_multilingual_media_analysis.md](73_multilingual_media_analysis.md)

Настройка языка вывода через конфиг: template промпты, инъекция параметров, backward compatibility.

**Конфиг:**

```toml
[media.analysis]
language = "Russian"  # Gemini ответит на русском!
```

---

### 74. Media Smart Splitter Integration

**Файл:** [74_media_smart_splitter_integration.md](74_media_smart_splitter_integration.md)

`SmartSplitter` для OCR-текста: изоляция кода в скринкастах, Markdown промпты, `code_ratio` мониторинг.

**Решение:**

- Gemini генерирует Markdown (инструкции в промптах)
- `SmartSplitter` парсит через `MarkdownNodeParser`
- Code blocks изолируются в `ChunkType.CODE`
- Мониторинг false positives через `code_ratio > 0.5`

---

## 🔗 Связанные фазы

- **Phase 4:** [Smart Parsing](../phase_4_smart_parsing/) — SmartSplitter для OCR
- **Phase 6:** [Multimodal](../phase_6_multimodal/) — media analyzers
- **Phase 13:** [Audit](../phase_13_audit/) — обнаружение кризиса

---

## 🚧 Phase 14.1 Preview

**Следующий шаг:** ProcessingStep Abstraction

Рефакторинг `_build_media_chunks()` → `SummaryStep`, `TranscriptionStep`, `OCRStep` для гибкости и тестируемости.

---

**← [Вернуться к оглавлению](../00_overview.md)**
