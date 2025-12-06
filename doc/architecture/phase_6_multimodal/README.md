# 🖼️ Phase 6: Multimodal Processing

> **Статус:** ✅ ЗАВЕРШЕНА  
> **Цель:** Обработка изображений, аудио и видео через Gemini API

---

## 📖 Содержание фазы

### 25. Media Processing Architecture
**Файл:** [25_media_processing_architecture.md](25_media_processing_architecture.md)

Архитектура обработки изображений: sync/async режимы, DTO и интеграция в `SemanticCore`.

---

### 26. Gemini Vision Integration
**Файл:** [26_gemini_vision_integration.md](26_gemini_vision_integration.md)

Анализ изображений через Gemini Vision API: structured JSON output и расчёт токенов.

---

### 27. Resilience Patterns
**Файл:** [27_resilience_patterns.md](27_resilience_patterns.md)

Паттерны устойчивости: retry с exponential backoff, классификация ошибок и graceful degradation.

---

### 28. Rate Limiting
**Файл:** [28_rate_limiting.md](28_rate_limiting.md)

Token Bucket алгоритм для контроля RPM и защиты от `429 Too Many Requests`.

---

### 29. Media Queue Processor
**Файл:** [29_media_queue_processor.md](29_media_queue_processor.md)

Персистентная очередь задач: `MediaTaskModel`, пакетная обработка и мониторинг.

---

### 30. Audio Analysis Architecture
**Файл:** [30_audio_analysis_architecture.md](30_audio_analysis_architecture.md)

`GeminiAudioAnalyzer`: транскрипция, 32kbps оптимизация, 83 минуты в одном запросе.

---

### 31. Video Multimodal Analysis
**Файл:** [31_video_multimodal_analysis.md](31_video_multimodal_analysis.md)

`GeminiVideoAnalyzer`: кадры + аудио в одном запросе, режимы извлечения кадров (fps/total/interval).

---

### 32. Media Optimization Strategies
**Файл:** [32_media_optimization_strategies.md](32_media_optimization_strategies.md)

Утилиты `audio.py`/`video.py`: сжатие, пресеты качества, FFmpeg dependency.

---

### 33. Markdown-Media Integration
**Файл:** [33_markdown_media_integration.md](33_markdown_media_integration.md)

Обогащение `IMAGE_REF` чанков через Vision API: контекст из документа, резолв путей.

---

### 34. Audio & Video in Markdown
**Файл:** [34_audio_video_in_markdown.md](34_audio_video_in_markdown.md)

Детекция аудио/видео ссылок по расширению, `AUDIO_REF` и `VIDEO_REF` чанки.

---

## 🔗 Связанные фазы

- **Phase 4:** [Smart Parsing](../phase_4_smart_parsing/) — парсинг IMAGE_REF из Markdown
- **Phase 13:** [Total Visual Check](../phase_13_audit/) — валидация media pipeline
- **Phase 14:** [Media Crisis](../phase_14_media_crisis/) — multi-chunk архитектура

---

**← [Вернуться к оглавлению](../00_overview.md)**
