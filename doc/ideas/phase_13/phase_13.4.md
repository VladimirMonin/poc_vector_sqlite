# 🧪 Phase 13.4 — E2E тесты для прямой загрузки медиа

**Статус:** 📋 СПЕЦИФИКАЦИЯ  
**Зависимость:** Phase 13.3 (исправление бага)  
**Цель:** Добавить тесты, которые ловят баг автоматически (без ручного тестирования)

---

## 1. Анализ текущего покрытия

### 1.1 Что уже тестируется (700+ тестов)

| Область | Файлы | Что проверяют |
|---------|-------|---------------|
| CLI | `tests/unit/cli/test_cli_phase_8_0.py` | `_detect_media_type()`, `_create_document()` |
| Parser | `tests/unit/processing/parsers/test_markdown_parser.py` | Парсинг `![](...)` → IMAGE_REF |
| Splitter | `tests/unit/processing/splitters/test_smart_splitter.py` | Разбиение markdown |
| Enrichment | `tests/integration/test_pipeline_media_enrichment.py` | **Только markdown!** |
| E2E Media | `tests/e2e/audit/test_media_audit.py` | Только анализаторы напрямую |

### 1.2 Что НЕ тестируется (пробелы)

| Сценарий | Покрыт? | Файл теста |
|----------|---------|------------|
| `ingest(Document(media_type=IMAGE))` → chunk_type=IMAGE_REF | ❌ НЕТ | — |
| `ingest(Document(media_type=AUDIO))` → chunk_type=AUDIO_REF | ❌ НЕТ | — |
| `ingest(Document(media_type=VIDEO))` → chunk_type=VIDEO_REF | ❌ НЕТ | — |
| Поиск находит медиа по содержимому (не по пути) | ❌ НЕТ | — |
| CLI `semantic ingest photo.jpg -e` → правильный chunk_type в БД | ❌ НЕТ | — |

### 1.3 Почему баг не обнаружился

1. **Unit-тесты CLI**: Тестируют `_detect_media_type()` → возвращает `MediaType.IMAGE` ✓  
   Но НЕ проверяют, что chunk_type в БД будет `IMAGE_REF`!

2. **Integration-тесты**: Тестируют **markdown** с `![](path)` → парсер создаёт IMAGE_REF ✓  
   Но НЕ тестируют прямую загрузку `.jpg` файла!

3. **E2E тесты**: Тестируют `GeminiImageAnalyzer.analyze()` напрямую ✓  
   Но НЕ тестируют полный пайплайн `ingest()` → БД!

**Вывод:** Нет E2E теста, который проверяет: "Загрузи `.jpg` → проверь в БД что `chunk_type=image_ref`"

---

## 2. Требуемые тесты

### 2.1 Integration-тест: Прямая загрузка с проверкой БД

**Файл:** `tests/integration/test_direct_media_ingestion.py`

```python
"""Integration-тесты: прямая загрузка медиа-файлов.

Проверяем что Document(media_type=IMAGE) создаёт chunk_type=IMAGE_REF,
а не TEXT (как было до фикса).
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
import numpy as np

from semantic_core import SemanticCore, PeeweeVectorStore, init_peewee_database
from semantic_core.domain import Document, MediaType
from semantic_core.domain.chunk import ChunkType
from semantic_core.domain.media import MediaAnalysisResult
from semantic_core.processing.parsers.markdown_parser import MarkdownNodeParser
from semantic_core.processing.splitters.smart_splitter import SmartSplitter
from semantic_core.processing.context.hierarchical_strategy import HierarchicalContextStrategy


@pytest.fixture
def test_db(tmp_path):
    """Временная БД для тестов."""
    db_path = tmp_path / "test_direct_media.db"
    db = init_peewee_database(str(db_path))
    yield db
    db.close()


@pytest.fixture
def mock_embedder():
    """Mock embedder."""
    embedder = MagicMock()
    embedder.embed_query.return_value = np.array([0.1] * 768, dtype=np.float32)
    embedder.embed_documents.return_value = [
        np.array([0.1] * 768, dtype=np.float32)
    ]
    return embedder


@pytest.fixture
def mock_image_analyzer():
    """Mock image analyzer."""
    analyzer = MagicMock()
    analyzer.analyze.return_value = MediaAnalysisResult(
        description="A beautiful sunset over the ocean",
        alt_text="Sunset photo",
        keywords=["sunset", "ocean", "nature"],
    )
    return analyzer


@pytest.fixture
def semantic_core(test_db, mock_embedder, mock_image_analyzer):
    """SemanticCore для тестов прямой загрузки."""
    parser = MarkdownNodeParser()
    splitter = SmartSplitter(parser=parser, chunk_size=500)
    context = HierarchicalContextStrategy(include_doc_title=True)
    store = PeeweeVectorStore(test_db)
    
    return SemanticCore(
        embedder=mock_embedder,
        store=store,
        splitter=splitter,
        context_strategy=context,
        image_analyzer=mock_image_analyzer,
    )


class TestDirectImageIngestion:
    """Тесты прямой загрузки изображений."""
    
    def test_image_document_creates_image_ref_chunk(self, semantic_core, test_db):
        """Document(media_type=IMAGE) → chunk_type=IMAGE_REF.
        
        ЭТО ГЛАВНЫЙ ТЕСТ, который ловит баг!
        До фикса: chunk_type=text (FAIL)
        После фикса: chunk_type=image_ref (PASS)
        """
        # Arrange
        doc = Document(
            content="/path/to/sunset.jpg",  # Просто путь!
            media_type=MediaType.IMAGE,
            metadata={"title": "Sunset"},
        )
        
        # Act
        result = semantic_core.ingest(doc, mode="sync", enrich_media=False)
        
        # Assert: Проверяем в БД напрямую!
        from semantic_core.infrastructure.storage.peewee.models import ChunkModel
        chunks = list(ChunkModel.select().where(ChunkModel.document == result.id))
        
        assert len(chunks) == 1, "Должен быть ровно 1 чанк"
        assert chunks[0].chunk_type == "image_ref", \
            f"chunk_type должен быть 'image_ref', а не '{chunks[0].chunk_type}'"
    
    def test_image_enrichment_stores_description(
        self, semantic_core, test_db, mock_image_analyzer
    ):
        """При enrich_media=True в content попадает описание, а не путь."""
        # Arrange
        doc = Document(
            content="/path/to/sunset.jpg",
            media_type=MediaType.IMAGE,
            metadata={"title": "Sunset"},
        )
        
        # Act
        result = semantic_core.ingest(doc, mode="sync", enrich_media=True)
        
        # Assert
        from semantic_core.infrastructure.storage.peewee.models import ChunkModel
        chunks = list(ChunkModel.select().where(ChunkModel.document == result.id))
        
        assert "sunset" in chunks[0].content.lower(), \
            "Content должен содержать описание от Vision API"
        assert "/path/to/sunset.jpg" not in chunks[0].content, \
            "Content НЕ должен содержать путь к файлу"
    
    def test_original_path_in_metadata(self, semantic_core, test_db):
        """Путь к файлу сохраняется в metadata._original_path."""
        doc = Document(
            content="/path/to/photo.jpg",
            media_type=MediaType.IMAGE,
            metadata={"title": "Photo"},
        )
        
        result = semantic_core.ingest(doc, mode="sync", enrich_media=False)
        
        from semantic_core.infrastructure.storage.peewee.models import ChunkModel
        import json
        
        chunk = ChunkModel.get(ChunkModel.document == result.id)
        metadata = json.loads(chunk.metadata)
        
        assert "_original_path" in metadata
        assert "photo.jpg" in metadata["_original_path"]


class TestDirectAudioIngestion:
    """Тесты прямой загрузки аудио."""
    
    def test_audio_document_creates_audio_ref_chunk(self, semantic_core, test_db):
        """Document(media_type=AUDIO) → chunk_type=AUDIO_REF."""
        doc = Document(
            content="/path/to/lecture.ogg",
            media_type=MediaType.AUDIO,
            metadata={"title": "Lecture"},
        )
        
        result = semantic_core.ingest(doc, mode="sync", enrich_media=False)
        
        from semantic_core.infrastructure.storage.peewee.models import ChunkModel
        chunk = ChunkModel.get(ChunkModel.document == result.id)
        
        assert chunk.chunk_type == "audio_ref"


class TestDirectVideoIngestion:
    """Тесты прямой загрузки видео."""
    
    def test_video_document_creates_video_ref_chunk(self, semantic_core, test_db):
        """Document(media_type=VIDEO) → chunk_type=VIDEO_REF."""
        doc = Document(
            content="/path/to/demo.mp4",
            media_type=MediaType.VIDEO,
            metadata={"title": "Demo"},
        )
        
        result = semantic_core.ingest(doc, mode="sync", enrich_media=False)
        
        from semantic_core.infrastructure.storage.peewee.models import ChunkModel
        chunk = ChunkModel.get(ChunkModel.document == result.id)
        
        assert chunk.chunk_type == "video_ref"


class TestMarkdownStillWorks:
    """Регрессионные тесты: markdown не сломался."""
    
    def test_markdown_with_image_ref_still_works(self, semantic_core, test_db):
        """Markdown с ![](path) продолжает создавать IMAGE_REF."""
        doc = Document(
            content="# Article\n\n![Photo](images/photo.jpg)\n\nText here.",
            media_type=MediaType.TEXT,  # TEXT!
            metadata={"title": "Article"},
        )
        
        result = semantic_core.ingest(doc, mode="sync", enrich_media=False)
        
        from semantic_core.infrastructure.storage.peewee.models import ChunkModel
        chunks = list(ChunkModel.select().where(ChunkModel.document == result.id))
        
        chunk_types = {c.chunk_type for c in chunks}
        assert "image_ref" in chunk_types, "Markdown парсер должен создать IMAGE_REF"
        assert "text" in chunk_types, "Должен быть текстовый чанк"
```

### 2.2 E2E-тест: Полный цикл с реальной БД и SQLite-проверкой

**Файл:** `tests/e2e/test_direct_media_e2e.py`

```python
"""E2E-тесты: полный цикл прямой загрузки медиа.

Проверяем:
1. CLI создаёт Document с правильным media_type
2. Pipeline создаёт chunk с правильным chunk_type
3. В БД записаны правильные данные
4. Поиск находит медиа по содержимому
"""

import sqlite3
import pytest
from pathlib import Path

from semantic_core import SemanticCore, PeeweeVectorStore, init_peewee_database
from semantic_core.domain import Document, MediaType
from semantic_core.cli.commands.ingest import _detect_media_type, _create_document


class TestE2EDirectMediaIngestion:
    """E2E тесты с прямым доступом к SQLite."""
    
    @pytest.fixture
    def db_path(self, tmp_path):
        """Путь к тестовой БД."""
        return tmp_path / "e2e_test.db"
    
    @pytest.fixture
    def setup_db(self, db_path):
        """Инициализация БД."""
        db = init_peewee_database(str(db_path))
        yield db
        db.close()
    
    def test_full_cycle_image_ingestion(self, db_path, setup_db, tmp_path):
        """Полный цикл: файл → CLI → pipeline → БД → проверка."""
        # 1. Создаём тестовый файл
        image_file = tmp_path / "test_image.jpg"
        image_file.write_bytes(b"fake jpg data")
        
        # 2. CLI определяет тип
        media_type = _detect_media_type(image_file)
        assert media_type == MediaType.IMAGE
        
        # 3. CLI создаёт Document
        doc = _create_document(image_file)
        assert doc.media_type == MediaType.IMAGE
        
        # 4. Инициализируем SemanticCore (с моками)
        # ... (код инициализации)
        
        # 5. Ingest
        result = core.ingest(doc, mode="sync", enrich_media=False)
        
        # 6. ПРЯМАЯ ПРОВЕРКА В SQLite!
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        
        cur.execute("""
            SELECT c.chunk_type, d.media_type
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE d.id = ?
        """, (result.id,))
        
        row = cur.fetchone()
        conn.close()
        
        assert row is not None, "Чанк должен существовать в БД"
        chunk_type, doc_media_type = row
        
        assert doc_media_type == "image", f"Document.media_type={doc_media_type}"
        assert chunk_type == "image_ref", \
            f"БАГ! chunk_type='{chunk_type}', должен быть 'image_ref'"
    
    def test_search_finds_media_by_content(self, db_path, setup_db):
        """Поиск находит медиа по описанию, а не по пути."""
        # ... (код с mock analyzer, который возвращает "sunset ocean")
        
        # Поиск
        results = core.search("beautiful sunset")
        
        assert len(results) > 0, "Поиск должен найти медиа"
        # Проверяем что нашли не путь, а описание
        found_content = results[0].document.content
        assert "sunset" in found_content.lower()


class TestDatabaseAudit:
    """Тесты-аудиторы для проверки целостности БД."""
    
    def test_no_media_files_stored_as_text(self, db_path, setup_db):
        """Аудит: медиа-документы НЕ должны иметь chunk_type=text.
        
        Этот тест запускается ПОСЛЕ инжеста и проверяет:
        - Если document.media_type IN (image, audio, video)
        - То chunk.chunk_type НЕ ДОЛЖЕН быть 'text'
        """
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        
        cur.execute("""
            SELECT d.id, d.media_type, c.chunk_type, d.metadata
            FROM documents d
            JOIN chunks c ON c.document_id = d.id
            WHERE d.media_type IN ('image', 'audio', 'video')
              AND c.chunk_type = 'text'
        """)
        
        violations = cur.fetchall()
        conn.close()
        
        if violations:
            details = "\n".join([
                f"  Doc {v[0]}: media_type={v[1]}, chunk_type={v[2]}"
                for v in violations
            ])
            pytest.fail(
                f"НАРУШЕНИЕ: {len(violations)} медиа-документов с chunk_type='text':\n"
                f"{details}"
            )
```

---

## 3. Структура тестовых файлов

```
tests/
├── integration/
│   ├── test_pipeline_media_enrichment.py  # Существует (markdown)
│   └── test_direct_media_ingestion.py     # НОВЫЙ! (прямая загрузка)
│
├── e2e/
│   └── test_direct_media_e2e.py           # НОВЫЙ! (полный цикл + SQLite)
│
└── audit/
    └── test_db_integrity.py               # НОВЫЙ! (аудит БД)
```

---

## 4. Чеклист тестов

### 4.1 Integration-тесты (`test_direct_media_ingestion.py`)

- [ ] `test_image_document_creates_image_ref_chunk` — **ГЛАВНЫЙ ТЕСТ БАГА**
- [ ] `test_audio_document_creates_audio_ref_chunk`
- [ ] `test_video_document_creates_video_ref_chunk`
- [ ] `test_image_enrichment_stores_description`
- [ ] `test_original_path_in_metadata`
- [ ] `test_markdown_with_image_ref_still_works` — регрессия

### 4.2 E2E-тесты (`test_direct_media_e2e.py`)

- [ ] `test_full_cycle_image_ingestion` — полный цикл с SQLite
- [ ] `test_full_cycle_audio_ingestion`
- [ ] `test_full_cycle_video_ingestion`
- [ ] `test_search_finds_media_by_content`

### 4.3 Аудит-тесты (`test_db_integrity.py`)

- [ ] `test_no_media_files_stored_as_text` — аудит после любого инжеста
- [ ] `test_all_media_chunks_have_original_path` — metadata проверка

---

## 5. Как тесты должны были поймать баг

### Сценарий A: До фикса (текущее состояние)

```
test_image_document_creates_image_ref_chunk:
  - Создаём Document(media_type=IMAGE)
  - Вызываем ingest()
  - Проверяем в БД: chunk_type
  
  РЕЗУЛЬТАТ: chunk_type='text' 
  ОЖИДАНИЕ: chunk_type='image_ref'
  
  ❌ FAIL — "chunk_type должен быть 'image_ref', а не 'text'"
```

### Сценарий B: После фикса

```
test_image_document_creates_image_ref_chunk:
  - Создаём Document(media_type=IMAGE)
  - Вызываем ingest() → _ingest_direct_media()
  - Проверяем в БД: chunk_type
  
  РЕЗУЛЬТАТ: chunk_type='image_ref'
  ОЖИДАНИЕ: chunk_type='image_ref'
  
  ✅ PASS
```

---

## 6. Приоритет реализации

1. **Phase 13.3** — Исправить баг (`_ingest_direct_media()`)
2. **Phase 13.4** — Добавить тесты (этот документ)
3. **CI** — Тесты запускаются на каждый PR

---

## 7. Выводы

### Почему 700 тестов не поймали баг

1. **Юниты изолированы** — тестируют `_detect_media_type()` отдельно
2. **Интеграционные тесты для markdown** — проверяют `![](...)`, не прямую загрузку
3. **E2E тесты для анализаторов** — проверяют API, не пайплайн
4. **Нет сквозного теста** — `файл.jpg → ingest() → БД.chunk_type = ?`

### Урок

> **Тест должен проверять то, что видит пользователь.**
>
> Пользователь видит: "Загрузил картинку → поиск не находит её по содержимому".
> Тест должен: "Загрузить картинку → проверить chunk_type в БД → проверить поиск".

---

## 8. Ссылки

- **Баг:** `doc/ideas/phase_13/phase_13.3.md`
- **Существующие тесты markdown:** `tests/integration/test_pipeline_media_enrichment.py`
- **CLI тесты:** `tests/unit/cli/test_cli_phase_8_0.py`
