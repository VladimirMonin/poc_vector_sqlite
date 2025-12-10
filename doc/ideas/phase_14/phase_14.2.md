# 🔗 Phase 14.2: MediaService & Aggregation Layer

**Дата:** 2025-12-06  
**Статус:** Planning  
**Зависимости:** Phase 14.1 (ProcessingStep Architecture)  
**Цель:** Создать сервисный слой для агрегации медиа-чанков в структурированные DTO

---

## 📋 Оглавление

1. [Мотивация и проблема текущего подхода](#1-мотивация-и-проблема-текущего-подхода)
2. [Целевая архитектура](#2-целевая-архитектура)
3. [Реализация MediaService](#3-реализация-mediaservice)
4. [Flask UI интеграция](#4-flask-ui-интеграция)
5. [Search filters по role](#5-search-filters-по-role)
6. [План реализации](#6-план-реализации)

---

## 1. Мотивация и проблема текущего подхода

### 1.1 Текущая ситуация

После Phase 14.1 мы получаем **разрозненные чанки** в БД:

```
document_id: "abc-123" (video: python_tutorial.mp4)
├─ chunk_0: SUMMARY (type: video_ref, role: summary)
├─ chunk_1: TRANSCRIPT chunk #1 (type: text, role: transcript, start_seconds: 0)
├─ chunk_2: TRANSCRIPT chunk #2 (type: text, role: transcript, start_seconds: 45)
├─ chunk_3: OCR chunk #1 (type: code, role: ocr, language: python)
└─ chunk_4: OCR chunk #2 (type: text, role: ocr)
```

**Проблема для UI:**

❌ Нужно вручную собирать данные из нескольких чанков  
❌ Нет единой точки доступа к "полной информации о медиа"  
❌ Дублирование логики сборки в Flask routes, CLI, notebooks  
❌ Нет фильтрации по типам контента (только transcript / только OCR)

**Пример текущего anti-pattern:**

```python
# examples/flask_app/routes/media.py (BAD)
@bp.route("/media/<doc_id>")
def view_media(doc_id):
    doc = store.get_document_by_id(doc_id)
    
    # Собираем чанки вручную
    summary_chunk = ChunkModel.select().where(
        (ChunkModel.document_id == doc_id) &
        (ChunkModel.metadata["role"].as_json() == "summary")
    ).get()
    
    transcript_chunks = ChunkModel.select().where(
        (ChunkModel.document_id == doc_id) &
        (ChunkModel.metadata["role"].as_json() == "transcript")
    ).order_by(ChunkModel.chunk_index)
    
    ocr_chunks = ChunkModel.select().where(...).order_by(...)
    
    return render_template("media.html", 
        summary=summary_chunk.content,
        transcripts=[c.content for c in transcript_chunks],
        # ... 30 строк ручной сборки
    )
```

### 1.2 Что нужно от сервисного слоя

**Требования:**

1. **Единая точка агрегации** — один метод `get_media_details(doc_id)` возвращает всё
2. **Structured DTO** — Pydantic модель с валидацией
3. **Timeline support** — список чанков с таймкодами для навигации
4. **Role filtering** — "дай только transcript" или "только OCR"
5. **Reusable** — использовать в Flask, CLI, notebooks, RAG

---

## 2. Целевая архитектура

### 2.1 MediaService — Aggregation Layer

**Файл:** `semantic_core/services/media_service.py`

```python
from dataclasses import dataclass
from typing import Optional, List
from pathlib import Path

from semantic_core.domain import Document, Chunk
from semantic_core.interfaces.vector_store import BaseVectorStore
from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TimelineItem:
    """Элемент timeline для медиа-плеера."""
    
    chunk_id: str
    start_seconds: int
    content_preview: str  # Первые 100 символов
    role: str  # "transcript" | "ocr"
    chunk_type: str  # "text" | "code"
    

@dataclass
class MediaDetails:
    """Агрегированные данные о медиа-файле.
    
    Используется для отображения в UI и RAG context.
    """
    
    # Базовая информация
    document_id: str
    media_path: Path
    media_type: str  # "image" | "audio" | "video"
    
    # Summary chunk
    summary: str
    keywords: List[str]
    
    # Transcript chunks (объединённые)
    full_transcript: Optional[str] = None
    transcript_chunks: List[Chunk] = None
    
    # OCR chunks (объединённые)
    full_ocr_text: Optional[str] = None
    ocr_chunks: List[Chunk] = None
    
    # Timeline для плеера (только если есть таймкоды)
    timeline: Optional[List[TimelineItem]] = None
    
    # Метаданные
    duration_seconds: Optional[int] = None
    participants: Optional[List[str]] = None
    action_items: Optional[List[str]] = None
    
    @property
    def has_timeline(self) -> bool:
        """Есть ли таймкоды для навигации."""
        return self.timeline is not None and len(self.timeline) > 0
    
    @property
    def total_chunks(self) -> int:
        """Общее количество чанков."""
        return 1 + len(self.transcript_chunks or []) + len(self.ocr_chunks or [])


class MediaService:
    """Сервис для работы с медиа-данными.
    
    Агрегирует чанки из БД в структурированные DTO.
    """
    
    def __init__(self, store: BaseVectorStore):
        """Инициализация.
        
        Args:
            store: Хранилище для доступа к документам и чанкам.
        """
        self.store = store
    
    def get_media_details(
        self,
        document_id: str,
        include_transcript: bool = True,
        include_ocr: bool = True,
    ) -> MediaDetails:
        """Получает полную информацию о медиа-файле.
        
        Args:
            document_id: ID документа.
            include_transcript: Включать ли transcript чанки.
            include_ocr: Включать ли OCR чанки.
        
        Returns:
            MediaDetails с агрегированными данными.
        
        Raises:
            ValueError: Если документ не найден или не является медиа.
        """
        # Получаем документ
        doc = self.store.get_document_by_id(document_id)
        if doc is None:
            raise ValueError(f"Document {document_id} not found")
        
        # Проверяем, что это медиа
        if doc.media_type.value not in ("image", "audio", "video"):
            raise ValueError(f"Document {document_id} is not a media file")
        
        # Получаем все чанки
        chunks = self.store.get_chunks_by_document_id(document_id)
        
        # Разделяем по ролям
        summary_chunk = next((c for c in chunks if c.metadata.get("role") == "summary"), None)
        transcript_chunks = [c for c in chunks if c.metadata.get("role") == "transcript"]
        ocr_chunks = [c for c in chunks if c.metadata.get("role") == "ocr"]
        
        if summary_chunk is None:
            raise ValueError(f"Summary chunk not found for document {document_id}")
        
        # Извлекаем метаданные из summary
        summary_meta = summary_chunk.metadata or {}
        
        # Формируем MediaDetails
        details = MediaDetails(
            document_id=document_id,
            media_path=Path(summary_meta.get("_original_path", "unknown")),
            media_type=doc.media_type.value,
            summary=summary_chunk.content,
            keywords=self._extract_keywords(summary_meta, doc.media_type.value),
            duration_seconds=summary_meta.get("_audio_duration") or summary_meta.get("_video_duration"),
            participants=summary_meta.get("_audio_participants"),
            action_items=summary_meta.get("_audio_action_items"),
        )
        
        # Добавляем transcript
        if include_transcript and transcript_chunks:
            details.transcript_chunks = sorted(transcript_chunks, key=lambda c: c.chunk_index)
            details.full_transcript = "\n\n".join(c.content for c in details.transcript_chunks)
        
        # Добавляем OCR
        if include_ocr and ocr_chunks:
            details.ocr_chunks = sorted(ocr_chunks, key=lambda c: c.chunk_index)
            details.full_ocr_text = "\n\n".join(c.content for c in details.ocr_chunks)
        
        # Формируем timeline
        details.timeline = self._build_timeline(transcript_chunks, ocr_chunks)
        
        logger.info(
            "Media details aggregated",
            document_id=document_id,
            total_chunks=details.total_chunks,
            has_timeline=details.has_timeline,
        )
        
        return details
    
    def _extract_keywords(self, metadata: dict, media_type: str) -> List[str]:
        """Извлекает keywords из metadata summary чанка."""
        if media_type == "image":
            return metadata.get("_vision_keywords", [])
        elif media_type == "audio":
            return metadata.get("_audio_keywords", [])
        elif media_type == "video":
            return metadata.get("_video_keywords", [])
        return []
    
    def _build_timeline(
        self,
        transcript_chunks: List[Chunk],
        ocr_chunks: List[Chunk],
    ) -> Optional[List[TimelineItem]]:
        """Строит timeline для медиа-плеера.
        
        Args:
            transcript_chunks: Чанки транскрипции.
            ocr_chunks: Чанки OCR.
        
        Returns:
            Список TimelineItem с таймкодами или None, если таймкодов нет.
        """
        timeline_items = []
        
        # Добавляем transcript chunks с таймкодами
        for chunk in transcript_chunks:
            start_seconds = chunk.metadata.get("start_seconds")
            if start_seconds is not None:
                timeline_items.append(TimelineItem(
                    chunk_id=chunk.id,
                    start_seconds=start_seconds,
                    content_preview=chunk.content[:100],
                    role="transcript",
                    chunk_type=chunk.chunk_type.value,
                ))
        
        # Добавляем OCR chunks с таймкодами (если есть)
        for chunk in ocr_chunks:
            start_seconds = chunk.metadata.get("start_seconds")
            if start_seconds is not None:
                timeline_items.append(TimelineItem(
                    chunk_id=chunk.id,
                    start_seconds=start_seconds,
                    content_preview=chunk.content[:100],
                    role="ocr",
                    chunk_type=chunk.chunk_type.value,
                ))
        
        if not timeline_items:
            return None
        
        # Сортируем по времени
        timeline_items.sort(key=lambda x: x.start_seconds)
        
        return timeline_items
    
    def search_media_by_role(
        self,
        query: str,
        role: Optional[str] = None,
        media_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[MediaDetails]:
        """Поиск медиа с фильтрацией по role.
        
        Args:
            query: Поисковый запрос.
            role: Фильтр по роли чанка ("transcript" | "ocr" | None для всех).
            media_type: Фильтр по типу медиа ("audio" | "video" | "image" | None).
            limit: Максимальное количество результатов.
        
        Returns:
            Список MediaDetails.
        """
        # Формируем SQL-фильтры
        filters = {}
        if role:
            filters["metadata.role"] = role
        if media_type:
            filters["media_type"] = media_type
        
        # Поиск через store
        search_results = self.store.search(
            query=query,
            limit=limit,
            filters=filters,
        )
        
        # Агрегируем по document_id (убираем дубликаты)
        seen_docs = set()
        media_list = []
        
        for result in search_results:
            doc_id = result.chunk.metadata.get("parent_document_id") or result.document_id
            
            if doc_id not in seen_docs:
                seen_docs.add(doc_id)
                try:
                    media_details = self.get_media_details(
                        doc_id,
                        include_transcript=(role != "ocr"),
                        include_ocr=(role != "transcript"),
                    )
                    media_list.append(media_details)
                except ValueError:
                    # Пропускаем невалидные документы
                    continue
        
        return media_list
```

---

## 3. Реализация MediaService

### 3.1 Интеграция в SemanticCore

**Модификация:** `semantic_core/pipeline.py`

```python
class SemanticCore:
    def __init__(self, ...):
        # ... существующая инициализация ...
        
        # Инициализируем MediaService
        self.media_service = MediaService(store=self.store)
    
    def get_media_details(self, document_id: str) -> MediaDetails:
        """Proxy метод для MediaService."""
        return self.media_service.get_media_details(document_id)
```

### 3.2 Добавление метода в BaseVectorStore

**Модификация:** `semantic_core/interfaces/vector_store.py`

```python
from abc import ABC, abstractmethod
from typing import List, Optional

class BaseVectorStore(ABC):
    # ... существующие методы ...
    
    @abstractmethod
    def get_chunks_by_document_id(
        self,
        document_id: str,
        role: Optional[str] = None,
    ) -> List[Chunk]:
        """Получает все чанки документа.
        
        Args:
            document_id: ID документа.
            role: Фильтр по роли чанка (опционально).
        
        Returns:
            Список чанков.
        """
        pass
```

**Реализация:** `semantic_core/infrastructure/storage/peewee/peewee_store.py`

```python
def get_chunks_by_document_id(
    self,
    document_id: str,
    role: Optional[str] = None,
) -> List[Chunk]:
    """Получает все чанки документа."""
    query = ChunkModel.select().where(ChunkModel.document_id == document_id)
    
    if role:
        query = query.where(ChunkModel.metadata["role"].as_json() == role)
    
    chunks = []
    for chunk_model in query:
        chunks.append(self._chunk_from_model(chunk_model))
    
    return chunks
```

---

## 4. Flask UI интеграция

### 4.1 Media Detail Page

**Файл:** `examples/flask_app/routes/media.py`

```python
from flask import Blueprint, render_template, abort
from semantic_core.services.media_service import MediaDetails

bp = Blueprint("media", __name__, url_prefix="/media")


@bp.route("/<document_id>")
def view_media(document_id: str):
    """Страница детальной информации о медиа."""
    try:
        # Получаем агрегированные данные через сервис
        media = current_app.extensions["semantic_core"].get_media_details(document_id)
    except ValueError as e:
        abort(404, description=str(e))
    
    return render_template("media/detail.html", media=media)


@bp.route("/<document_id>/timeline")
def get_timeline(document_id: str):
    """API endpoint для получения timeline (для AJAX)."""
    try:
        media = current_app.extensions["semantic_core"].get_media_details(document_id)
    except ValueError:
        abort(404)
    
    if not media.has_timeline:
        return {"timeline": []}, 200
    
    return {
        "timeline": [
            {
                "chunk_id": item.chunk_id,
                "start_seconds": item.start_seconds,
                "preview": item.content_preview,
                "role": item.role,
                "type": item.chunk_type,
            }
            for item in media.timeline
        ]
    }, 200
```

### 4.2 HTML Template с плеером

**Файл:** `examples/flask_app/templates/media/detail.html`

```html
{% extends "base.html" %}

{% block content %}
<div class="container mt-4">
    <div class="row">
        <!-- Media Player Column -->
        <div class="col-md-8">
            <h2>{{ media.media_path.name }}</h2>
            
            {% if media.media_type == "video" %}
                <video id="media-player" controls class="w-100">
                    <source src="/static/media/{{ media.document_id }}" type="video/mp4">
                </video>
            {% elif media.media_type == "audio" %}
                <audio id="media-player" controls class="w-100">
                    <source src="/static/media/{{ media.document_id }}" type="audio/mpeg">
                </audio>
            {% elif media.media_type == "image" %}
                <img src="/static/media/{{ media.document_id }}" class="img-fluid">
            {% endif %}
            
            <!-- Summary -->
            <div class="card mt-3">
                <div class="card-body">
                    <h5 class="card-title">Summary</h5>
                    <p>{{ media.summary }}</p>
                    
                    {% if media.keywords %}
                    <div class="mt-2">
                        {% for keyword in media.keywords %}
                        <span class="badge bg-primary">{{ keyword }}</span>
                        {% endfor %}
                    </div>
                    {% endif %}
                </div>
            </div>
        </div>
        
        <!-- Timeline Sidebar -->
        <div class="col-md-4">
            {% if media.has_timeline %}
            <div class="card">
                <div class="card-header">
                    <h5>Timeline</h5>
                </div>
                <div class="card-body p-0">
                    <div class="list-group list-group-flush" id="timeline">
                        {% for item in media.timeline %}
                        <a href="#" 
                           class="list-group-item list-group-item-action timeline-item"
                           data-seconds="{{ item.start_seconds }}"
                           data-role="{{ item.role }}">
                            <div class="d-flex justify-content-between">
                                <span class="badge bg-secondary">{{ item.start_seconds | format_timecode }}</span>
                                <span class="badge bg-info">{{ item.role }}</span>
                            </div>
                            <small class="text-muted">{{ item.content_preview }}</small>
                        </a>
                        {% endfor %}
                    </div>
                </div>
            </div>
            {% endif %}
            
            <!-- Metadata -->
            <div class="card mt-3">
                <div class="card-body">
                    <h6>Metadata</h6>
                    <ul class="list-unstyled">
                        <li><strong>Type:</strong> {{ media.media_type }}</li>
                        {% if media.duration_seconds %}
                        <li><strong>Duration:</strong> {{ media.duration_seconds | format_duration }}</li>
                        {% endif %}
                        <li><strong>Chunks:</strong> {{ media.total_chunks }}</li>
                        {% if media.participants %}
                        <li><strong>Participants:</strong> {{ media.participants | join(", ") }}</li>
                        {% endif %}
                    </ul>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Tabs: Transcript / OCR / Action Items -->
    <div class="row mt-4">
        <div class="col-12">
            <ul class="nav nav-tabs" id="contentTabs" role="tablist">
                {% if media.full_transcript %}
                <li class="nav-item">
                    <a class="nav-link active" data-bs-toggle="tab" href="#transcript">Transcript</a>
                </li>
                {% endif %}
                {% if media.full_ocr_text %}
                <li class="nav-item">
                    <a class="nav-link" data-bs-toggle="tab" href="#ocr">OCR Text</a>
                </li>
                {% endif %}
                {% if media.action_items %}
                <li class="nav-item">
                    <a class="nav-link" data-bs-toggle="tab" href="#actions">Action Items</a>
                </li>
                {% endif %}
            </ul>
            
            <div class="tab-content p-3 border border-top-0">
                {% if media.full_transcript %}
                <div class="tab-pane fade show active" id="transcript">
                    <pre class="bg-light p-3">{{ media.full_transcript }}</pre>
                </div>
                {% endif %}
                
                {% if media.full_ocr_text %}
                <div class="tab-pane fade" id="ocr">
                    <pre class="bg-light p-3">{{ media.full_ocr_text }}</pre>
                </div>
                {% endif %}
                
                {% if media.action_items %}
                <div class="tab-pane fade" id="actions">
                    <ul class="list-group">
                        {% for item in media.action_items %}
                        <li class="list-group-item">{{ item }}</li>
                        {% endfor %}
                    </ul>
                </div>
                {% endif %}
            </div>
        </div>
    </div>
</div>

<script>
// Timeline navigation
document.querySelectorAll('.timeline-item').forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        const seconds = parseInt(item.dataset.seconds);
        const player = document.getElementById('media-player');
        
        if (player) {
            player.currentTime = seconds;
            player.play();
        }
    });
});
</script>
{% endblock %}
```

---

## 5. Search filters по role

### 5.1 Search Page с фильтрами

**Файл:** `examples/flask_app/routes/search.py`

```python
@bp.route("/")
def search():
    """Страница поиска с фильтрами."""
    query = request.args.get("q", "")
    role_filter = request.args.get("role")  # "transcript" | "ocr" | None
    media_type = request.args.get("media_type")  # "audio" | "video" | None
    
    if not query:
        return render_template("search/index.html", results=[])
    
    # Поиск через MediaService
    core = current_app.extensions["semantic_core"]
    results = core.media_service.search_media_by_role(
        query=query,
        role=role_filter,
        media_type=media_type,
        limit=20,
    )
    
    return render_template(
        "search/results.html",
        query=query,
        role_filter=role_filter,
        media_type=media_type,
        results=results,
    )
```

**Template:** `templates/search/index.html`

```html
<form method="get" action="/search">
    <div class="input-group mb-3">
        <input type="text" name="q" class="form-control" placeholder="Search media...">
        
        <select name="role" class="form-select" style="max-width: 150px;">
            <option value="">All Content</option>
            <option value="transcript">Transcript Only</option>
            <option value="ocr">OCR Only</option>
        </select>
        
        <select name="media_type" class="form-select" style="max-width: 150px;">
            <option value="">All Types</option>
            <option value="audio">Audio</option>
            <option value="video">Video</option>
            <option value="image">Image</option>
        </select>
        
        <button class="btn btn-primary" type="submit">Search</button>
    </div>
</form>
```

---

## 6. План реализации

### 6.1 Этапы разработки

**Week 1: MediaService Core**

- [ ] Создать `MediaDetails` dataclass
- [ ] Создать `TimelineItem` dataclass
- [ ] Реализовать `MediaService.get_media_details()`
- [ ] Добавить `get_chunks_by_document_id()` в BaseVectorStore
- [ ] Реализовать в PeeweeVectorStore
- [ ] Unit-тесты для MediaService

**Week 2: Flask UI**

- [ ] Создать `/media/<id>` route
- [ ] Создать `media/detail.html` template с плеером
- [ ] Добавить timeline navigation (JavaScript)
- [ ] Добавить filters в search page
- [ ] Реализовать `search_media_by_role()`
- [ ] E2E тест: открыть медиа → кликнуть на timeline → плеер перемотался

**Deliverables:**

- ✅ `MediaService` в production
- ✅ Flask UI с timeline
- ✅ Search filters работают
- ✅ E2E тесты проходят
- ✅ Документация обновлена

### 6.2 Success Metrics

**Code:**

- ✅ 100% покрытие unit-тестами для `MediaService`
- ✅ E2E тест: timeline navigation работает в браузере
- ✅ Агрегация 100-чанкового видео < 500ms

**UI:**

- ✅ Timeline кликабелен и перематывает плеер
- ✅ Search filters по role возвращают релевантные результаты
- ✅ Media detail page грузится < 1 секунды

---

**End of Phase 14.2 Plan**  
**Estimated Duration:** 2 weeks  
**Team:** 1 engineer
