# Phase 12.5: Media Gallery Page

**Статус:** 📋 СПЕЦИФИКАЦИЯ  
**Дата:** 2025-12-05  
**Зависимость:** Phase 12.4  
**Цель:** Реализовать страницу галереи медиа — убрать заглушку "Soon" из sidebar

---

## 📋 Описание

В sidebar есть пункт "Медиа" с badge "Soon". Нужна страница со всеми медиа-файлами (изображения, аудио, видео).

---

## 🎯 Решение

Создать `/media` страницу с:

- Grid/List view
- Фильтрация по типу (image/audio/video)
- Превью для изображений
- Иконки для аудио/видео
- Клик → document_detail

---

## 🔧 Задачи

### 1. Route

**Файл:** `app/routes/ingest.py`

```python
@ingest_bp.route("/media")
def media_gallery():
    """Галерея медиа-файлов."""
    filter_type = request.args.get("type", "all")  # image, audio, video, all
    
    # Запрос документов с media_type
    query = DocumentModel.select().where(
        DocumentModel.metadata.contains('"media_type":')
    )
    
    if filter_type != "all":
        query = query.where(
            DocumentModel.metadata.contains(f'"media_type": "{filter_type}"')
        )
    
    media_items = []
    for doc in query.order_by(DocumentModel.created_at.desc()):
        meta = json.loads(doc.metadata) if isinstance(doc.metadata, str) else doc.metadata
        if meta.get("media_type") in ("image", "audio", "video"):
            media_items.append({
                "id": doc.id,
                "title": meta.get("title", "Untitled"),
                "media_type": meta.get("media_type"),
                "filename": meta.get("filename"),
                "created_at": doc.created_at,
            })
    
    return render_template(
        "media.html",
        media_items=media_items,
        filter_type=filter_type,
    )
```

---

### 2. Template

**Файл:** `app/templates/media.html` (новый)

```html
{% extends "base.html" %}

{% block title %}Медиа — Semantic KB{% endblock %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h4><i class="bi bi-images me-2"></i>Медиа-галерея</h4>
    
    <!-- Фильтр по типу -->
    <div class="btn-group">
        <a href="?type=all" class="btn btn-outline-secondary {% if filter_type == 'all' %}active{% endif %}">Все</a>
        <a href="?type=image" class="btn btn-outline-info {% if filter_type == 'image' %}active{% endif %}">
            <i class="bi bi-image"></i> Изображения
        </a>
        <a href="?type=audio" class="btn btn-outline-success {% if filter_type == 'audio' %}active{% endif %}">
            <i class="bi bi-music-note"></i> Аудио
        </a>
        <a href="?type=video" class="btn btn-outline-danger {% if filter_type == 'video' %}active{% endif %}">
            <i class="bi bi-camera-video"></i> Видео
        </a>
    </div>
</div>

<div class="row row-cols-2 row-cols-md-3 row-cols-lg-4 g-3">
    {% for item in media_items %}
    <div class="col">
        <a href="{{ url_for('ingest.document_detail', doc_id=item.id) }}" class="text-decoration-none">
            <div class="card h-100 shadow-sm">
                {% if item.media_type == 'image' %}
                    <img src="{{ url_for('static', filename='uploads/' ~ item.filename) }}" 
                         class="card-img-top" 
                         alt="{{ item.title }}"
                         style="height: 150px; object-fit: cover;">
                {% elif item.media_type == 'audio' %}
                    <div class="card-img-top bg-success text-white d-flex align-items-center justify-content-center" style="height: 150px;">
                        <i class="bi bi-music-note display-1"></i>
                    </div>
                {% else %}
                    <div class="card-img-top bg-danger text-white d-flex align-items-center justify-content-center" style="height: 150px;">
                        <i class="bi bi-camera-video display-1"></i>
                    </div>
                {% endif %}
                <div class="card-body">
                    <h6 class="card-title text-truncate">{{ item.title }}</h6>
                    <small class="text-muted">{{ item.created_at.strftime('%d.%m.%Y') }}</small>
                </div>
            </div>
        </a>
    </div>
    {% else %}
    <div class="col-12">
        <div class="alert alert-info">Нет медиа-файлов</div>
    </div>
    {% endfor %}
</div>
{% endblock %}
```

---

### 3. Убрать заглушку в sidebar

**Файл:** `app/templates/base.html`

```html
<!-- Было -->
<a class="nav-link disabled text-muted" href="#" aria-disabled="true">
    <i class="bi bi-image"></i>
    Медиа
    <span class="badge bg-secondary ms-1">Soon</span>
</a>

<!-- Стало -->
<a class="nav-link {% if request.endpoint == 'ingest.media_gallery' %}active{% endif %}" 
   href="{{ url_for('ingest.media_gallery') }}">
    <i class="bi bi-image"></i>
    Медиа
</a>
```

---

## 🧪 Тесты

```python
def test_media_gallery_all(client):
    response = client.get("/media")
    assert response.status_code == 200

def test_media_gallery_filter_image(client):
    response = client.get("/media?type=image")
    assert response.status_code == 200
```

---

## 📊 Чеклист

- [ ] Route `/media` создан
- [ ] Template `media.html` создан
- [ ] Фильтрация по типу работает
- [ ] Превью изображений отображается
- [ ] Sidebar обновлён
- [ ] Клик ведёт на document_detail
