# 🗺️ Phase 6.6: Multimodal Markdown Testing Plan

**Цель:** Гарантировать корректную обработку медиа-файлов (картинки, аудио, видео), встроенных в Markdown.  
**Фокус:** Проверка парсинга по расширению, передачи контекста в API, корректности vector_text.

---

## 📊 Анализ Существующих Тестов

### ✅ Что уже есть

| Файл | Статус | Что тестирует |
|------|--------|---------------|
| `tests/integration/test_markdown_media_enrichment.py` | ⚠️ УСТАРЕЛ | Парсинг IMAGE_REF, роутинг MIME-типов |
| `tests/unit/test_markdown_asset_enricher.py` | ✅ OK | MediaContext для IMAGE_REF |
| `tests/unit/processing/parsers/test_markdown_parser.py` | ⚠️ НЕПОЛНЫЙ | Headers, CODE, без AUDIO/VIDEO |
| `tests/conftest.py` | ✅ OK | Фикстуры mock_audio/video_analyzer |

### ⚠️ Что нужно исправить

1. **`test_markdown_media_enrichment.py`:**
   - Класс `TestMarkdownAudioVideoLinks` проверяет OLD поведение
   - Тесты ожидают `IMAGE_REF` для `.mp3`/`.mp4` файлов
   - Нужно обновить на `AUDIO_REF` и `VIDEO_REF`

2. **`post_with_media.md`:**
   - Использует только `![Audio](file.mp3)` синтаксис
   - Нужно добавить `[Audio](file.mp3)` link-синтаксис для полноты

3. **`test_markdown_parser.py`:**
   - Нет тестов на детекцию AUDIO_REF/VIDEO_REF по расширению
   - Нет тестов на `_get_media_type_by_extension()`

---

## 📂 1. Тестовые Данные

### Существующие фикстуры (`tests/fixtures/media/`)

| Тип | Файл | Описание | Цель теста |
|-----|------|----------|------------|
| 🎵 Audio | `speech.mp3` | 15 сек, рассказ о векторах (русский) | Транскрипция, ключевые слова |
| 🎵 Audio | `noise.wav` | 10 сек тишины | Edge case: пустой контент |
| 🎬 Video | `slides.mp4` | 35 сек, диаграмма OAuth Django | OCR, визуальный анализ |
| 🎬 Video | `talking_head.mp4` | 16 сек, "Джунгли, Обезьянка, Пальма" | Мультимодальный анализ |
| 📝 MD | `post_with_media.md` | Markdown с медиа-ссылками | Интеграция парсинга |

### Доработки фикстур

1. **Обновить `post_with_media.md`:**
   - Добавить `[Link text](file.mp3)` синтаксис (не только `![]()`)
   - Добавить ссылку на картинку для полноты

2. **Создать `rich_document.md`:**
   - Полный тестовый документ со всеми типами медиа
   - Глубокая иерархия заголовков для проверки breadcrumbs

---

## 🧪 2. Unit-тесты: Парсинг (Phase 6.5 Coverage)

### A. Обновить `test_markdown_parser.py`

Добавить тесты на детекцию типа по расширению:

```python
class TestMediaTypeDetection:
    """Тесты детекции типа медиа по расширению файла."""
    
    def test_audio_extensions_detected(self, parser):
        """Аудио-ссылка с ![Audio](file.mp3) → AUDIO_REF."""
        
    def test_video_extensions_detected(self, parser):
        """Видео-ссылка с ![Video](file.mp4) → VIDEO_REF."""
    
    def test_audio_link_syntax(self, parser):
        """Ссылка [text](file.mp3) → AUDIO_REF."""
        
    def test_video_link_syntax(self, parser):
        """Ссылка [text](file.mp4) → VIDEO_REF."""
        
    def test_image_remains_image_ref(self, parser):
        """Картинка ![](image.png) → IMAGE_REF."""
        
    def test_unknown_extension_fallback(self, parser):
        """Неизвестное расширение в ![]() → IMAGE_REF fallback."""
```

### B. Обновить `test_markdown_asset_enricher.py`

Добавить тесты для AUDIO_REF и VIDEO_REF:

```python
class TestMediaContextForAudioVideo:
    """Тесты MediaContext для аудио и видео."""
    
    def test_audio_context_media_type(self, enricher):
        """AUDIO_REF → media_type='audio', role корректный."""
        
    def test_video_context_media_type(self, enricher):
        """VIDEO_REF → media_type='video', role корректный."""
        
    def test_format_for_api_audio(self, enricher):
        """format_for_api() для аудио использует 'Description:' label."""
        
    def test_format_for_api_video(self, enricher):
        """format_for_api() для видео использует 'Description:' label."""
```

---

## 🔗 3. Unit-тесты: HierarchicalContextStrategy

### `test_hierarchical_context_media.py`

Критически важно проверить формирование `vector_text`:

```python
class TestHierarchicalContextMedia:
    """Тесты формирования vector_text для медиа-чанков."""
    
    # === AUDIO_REF: Обогащённый ===
    def test_audio_enriched_includes_transcription(self):
        """Обогащённый AUDIO_REF: vector_text содержит транскрипцию."""
        
    def test_audio_enriched_includes_speakers(self):
        """Обогащённый AUDIO_REF: vector_text содержит 'Speakers:'."""
        
    def test_audio_enriched_includes_keywords(self):
        """Обогащённый AUDIO_REF: vector_text содержит 'Keywords:'."""
        
    # === AUDIO_REF: НЕ обогащённый ===
    def test_audio_raw_includes_source_path(self):
        """Необогащённый AUDIO_REF: vector_text содержит 'Source: path.mp3'."""
        
    def test_audio_raw_includes_alt_description(self):
        """Необогащённый AUDIO_REF: vector_text содержит alt-текст."""
    
    # === VIDEO_REF: Обогащённый ===
    def test_video_enriched_includes_description(self):
        """Обогащённый VIDEO_REF: vector_text содержит описание."""
        
    def test_video_enriched_includes_audio_transcription(self):
        """Обогащённый VIDEO_REF: vector_text содержит 'Audio transcription:'."""
        
    def test_video_enriched_includes_visible_text(self):
        """Обогащённый VIDEO_REF: vector_text содержит 'Visible text:' (OCR)."""
        
    # === VIDEO_REF: НЕ обогащённый ===
    def test_video_raw_includes_source_path(self):
        """Необогащённый VIDEO_REF: vector_text содержит путь к файлу."""
    
    # === Общие проверки ===
    def test_breadcrumbs_in_all_media_types(self):
        """Все медиа-типы содержат 'Section:' с breadcrumbs."""
        
    def test_document_title_in_media(self):
        """Медиа-чанки содержат 'Document:' заголовок."""
```

---

## 🔗 4. Интеграционные Тесты

### A. Исправить `test_markdown_media_enrichment.py`

Обновить класс `TestMarkdownAudioVideoLinks`:

```python
class TestMarkdownAudioVideoLinks:
    """Тесты для Phase 6.5: Audio/Video в Markdown."""

    def test_audio_link_parsed_as_audio_ref(self, parser):
        """Аудио-ссылка ![Audio](file.mp3) → AUDIO_REF."""
        md = "![Audio](audio/speech.mp3)"
        segments = list(parser.parse(md))
        assert segments[0].segment_type == ChunkType.AUDIO_REF  # Было IMAGE_REF

    def test_video_link_parsed_as_video_ref(self, parser):
        """Видео-ссылка ![Video](file.mp4) → VIDEO_REF."""
        md = "![Video](video/slides.mp4)"
        segments = list(parser.parse(md))
        assert segments[0].segment_type == ChunkType.VIDEO_REF  # Было IMAGE_REF
```

### B. Новый `test_pipeline_media_enrichment.py`

Интеграция SemanticCore + Mock анализаторы:

```python
class TestSemanticCoreMediaEnrichment:
    """Интеграция: SemanticCore.ingest() с медиа-обогащением."""
    
    def test_ingest_with_all_analyzers(self):
        """core.ingest() с image/audio/video анализаторами."""
        
    def test_enriched_chunks_saved_to_db(self):
        """Обогащённые чанки сохраняются в БД."""
        
    def test_original_path_preserved(self):
        """metadata['_original_path'] содержит исходный путь."""
        
    def test_enriched_flag_set(self):
        """metadata['_enriched'] == True после обогащения."""
        
    def test_missing_analyzer_skips_chunk(self):
        """Если нет audio_analyzer, AUDIO_REF пропускается без ошибки."""
```

---

## 🌐 5. E2E Тесты с Реальным API

### `tests/e2e/test_real_audio_video_analysis.py`

```python
@pytest.mark.real_api
class TestRealAudioAnalysis:
    """E2E: Реальный анализ аудио через Gemini API."""
    
    def test_speech_transcription(self, speech_audio_path):
        """speech.mp3 → транскрипция содержит 'вектор' или 'embedding'."""
        
    def test_noise_handling(self, noise_audio_path):
        """noise.wav (тишина) → не падает, описание адекватное."""


@pytest.mark.real_api  
class TestRealVideoAnalysis:
    """E2E: Реальный анализ видео через Gemini API."""
    
    def test_slides_ocr(self, slides_video_path):
        """slides.mp4 → OCR содержит 'OAuth' или 'Django'."""
        
    def test_talking_head_transcription(self, talking_head_video_path):
        """talking_head.mp4 → транскрипция содержит 'обезьянка' или 'пальма'."""


@pytest.mark.real_api
class TestRealMarkdownEnrichment:
    """E2E: Полный пайплайн Markdown → Enriched Chunks."""
    
    def test_rich_document_all_media_enriched(self):
        """rich_document.md → все 3 типа медиа обогащены."""
        
    def test_vector_text_quality(self):
        """vector_text содержит осмысленный контент, не пути к файлам."""
```

---

## 🛡️ 6. Edge Cases и Robustness

### `test_media_edge_cases.py`

```python
class TestMediaEdgeCases:
    """Edge cases обработки медиа."""
    
    def test_empty_analyzer_response(self):
        """Пустой ответ от анализатора → _media_error в metadata."""
        
    def test_missing_file_skipped(self):
        """Несуществующий файл → пропускается, не падает."""
        
    def test_url_media_skipped(self):
        """HTTP URL → пропускается (не локальный файл)."""
        
    def test_unsupported_extension_fallback(self):
        """Неизвестное расширение → IMAGE_REF fallback."""
```

---

## ✅ Чек-лист реализации

### Шаг 1: Исправить устаревшие тесты
- [ ] Обновить `test_markdown_media_enrichment.py` → AUDIO_REF, VIDEO_REF
- [ ] Обновить `post_with_media.md` → добавить link-синтаксис

### Шаг 2: Добавить Unit-тесты парсинга
- [ ] `test_markdown_parser.py` → TestMediaTypeDetection
- [ ] `test_markdown_asset_enricher.py` → TestMediaContextForAudioVideo

### Шаг 3: Добавить Unit-тесты контекста
- [ ] Создать `test_hierarchical_context_media.py`

### Шаг 4: Интеграционные тесты
- [ ] Создать `test_pipeline_media_enrichment.py`
- [ ] Обновить фикстуры в conftest.py если нужно

### Шаг 5: E2E тесты (опционально)
- [ ] `test_real_audio_video_analysis.py` с @real_api marker

### Шаг 6: Edge cases
- [ ] `test_media_edge_cases.py`

---

## 📋 Ожидаемый результат

После выполнения Phase 6.6:

1. ✅ **Парсинг:** `.mp3` → `AUDIO_REF`, `.mp4` → `VIDEO_REF`
2. ✅ **Контекст:** breadcrumbs и surrounding_text передаются в API
3. ✅ **vector_text:** Содержит транскрипцию/описание, не пути к файлам
4. ✅ **Robustness:** Пустые ответы и отсутствующие файлы не ломают систему
