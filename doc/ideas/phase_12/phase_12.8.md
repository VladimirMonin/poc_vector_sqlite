# Phase 12.8: Queue Monitor Page

**Статус:** 📋 СПЕЦИФИКАЦИЯ  
**Дата:** 2025-12-05  
**Зависимость:** Phase 12.7  
**Цель:** Реализовать страницу мониторинга очереди обработки медиа

---

## 📋 Описание

В sidebar есть пункт "Очередь" с badge "Soon". Нужна страница для мониторинга:

- Pending tasks
- Completed tasks
- Failed tasks
- Статус воркера

---

## 🎯 Решение

Создать `/queue` страницу с:

- Таблицей задач из `MediaTaskModel`
- Группировкой по статусу
- Кнопкой retry для failed
- Auto-refresh через HTMX polling

---

## 🔧 Задачи

### 1. Route

**Файл:** `app/routes/main.py`

```python
@main_bp.route("/queue")
def queue_monitor():
    """Мониторинг очереди обработки медиа."""
    from semantic_core.infrastructure.storage.peewee.models import MediaTaskModel
    
    tasks = list(MediaTaskModel.select().order_by(MediaTaskModel.created_at.desc()).limit(100))
    
    stats = {
        "pending": sum(1 for t in tasks if t.status == "pending"),
        "processing": sum(1 for t in tasks if t.status == "processing"),
        "completed": sum(1 for t in tasks if t.status == "completed"),
        "failed": sum(1 for t in tasks if t.status == "failed"),
    }
    
    return render_template(
        "queue.html",
        tasks=tasks,
        stats=stats,
    )
```

---

### 2. Template

**Файл:** `app/templates/queue.html` (новый)

```html
{% extends "base.html" %}

{% block title %}Очередь — Semantic KB{% endblock %}

{% block content %}
<h4 class="mb-4"><i class="bi bi-list-task me-2"></i>Очередь обработки</h4>

<!-- Статистика -->
<div class="row mb-4">
    <div class="col-md-3">
        <div class="card text-bg-warning">
            <div class="card-body">
                <h5 class="card-title">{{ stats.pending }}</h5>
                <p class="card-text">Ожидают</p>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card text-bg-info">
            <div class="card-body">
                <h5 class="card-title">{{ stats.processing }}</h5>
                <p class="card-text">Обработка</p>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card text-bg-success">
            <div class="card-body">
                <h5 class="card-title">{{ stats.completed }}</h5>
                <p class="card-text">Завершено</p>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card text-bg-danger">
            <div class="card-body">
                <h5 class="card-title">{{ stats.failed }}</h5>
                <p class="card-text">Ошибки</p>
            </div>
        </div>
    </div>
</div>

<!-- Таблица задач -->
<div class="card" hx-get="{{ url_for('main.queue_tasks') }}" hx-trigger="every 5s" hx-swap="innerHTML">
    <div class="table-responsive">
        <table class="table table-hover mb-0">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Тип</th>
                    <th>Файл</th>
                    <th>Статус</th>
                    <th>Создан</th>
                    <th>Действия</th>
                </tr>
            </thead>
            <tbody>
                {% for task in tasks %}
                <tr>
                    <td><code>{{ task.id[:8] }}</code></td>
                    <td>{{ task.media_type }}</td>
                    <td>{{ task.source_path | basename }}</td>
                    <td>
                        <span class="badge 
                            {% if task.status == 'completed' %}bg-success
                            {% elif task.status == 'failed' %}bg-danger
                            {% elif task.status == 'processing' %}bg-info
                            {% else %}bg-warning{% endif %}">
                            {{ task.status }}
                        </span>
                    </td>
                    <td>{{ task.created_at.strftime('%H:%M:%S') }}</td>
                    <td>
                        {% if task.status == 'failed' %}
                        <form action="{{ url_for('main.retry_task', task_id=task.id) }}" method="POST">
                            <button type="submit" class="btn btn-sm btn-outline-warning">Retry</button>
                        </form>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
{% endblock %}
```

---

### 3. Убрать заглушку в sidebar

**Файл:** `app/templates/base.html`

```html
<a class="nav-link {% if request.endpoint == 'main.queue_monitor' %}active{% endif %}" 
   href="{{ url_for('main.queue_monitor') }}">
    <i class="bi bi-list-task"></i>
    Очередь
</a>
```

---

## 🧪 Тесты

```python
def test_queue_monitor(client):
    response = client.get("/queue")
    assert response.status_code == 200
    assert b"Очередь" in response.data
```

---

## 📊 Чеклист

- [ ] Route `/queue` создан
- [ ] Template `queue.html` создан
- [ ] Статистика отображается
- [ ] Таблица задач работает
- [ ] Auto-refresh через HTMX
- [ ] Sidebar обновлён
- [ ] Retry для failed задач
