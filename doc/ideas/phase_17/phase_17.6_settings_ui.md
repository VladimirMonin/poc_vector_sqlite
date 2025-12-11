# Phase 17.6 — Settings UI (Provider Switcher)

> Web интерфейс для управления провайдерами embeddings в Flask App

**Статус:** 📋 Planned  
**Зависимости:** Phase 17.5 (Flask Multi-Provider Integration)  
**Оценка:** 1-2 дня

---

## 🎯 Цель

Создать **Settings page** в Flask App для:

- Просмотра текущего провайдера (Gemini/Local/OpenAI)
- Переключения между провайдерами через UI
- Предупреждения о dimension mismatch
- Отображения статуса провайдера (работает/ошибка)

**UX Flow:**

```
User открывает /settings
  ↓
Видит: "Current Provider: Gemini (768D)"
  ↓
Кликает: "Switch to Local (Qwen3, 1024D)"
  ↓
Видит предупреждение: "⚠️ Dimension mismatch! DB recreation required"
  ↓
Подтверждает → semantic.toml обновляется → Flask перезапускается
```

---

## 📋 Задачи

### 1. Route: /settings

**Что делаем:**

- Создать новый blueprint `app/routes/settings.py`
- GET `/settings` — страница с текущим провайдером и списком доступных
- POST `/settings/switch` — переключение провайдера (обновляет semantic.toml)
- POST `/settings/check-dimension` — AJAX проверка dimension compatibility

**Данные на странице:**

- Current Provider: name, dimension, status (✅ работает / ❌ ошибка)
- DB Dimension: dimension из БД
- Dimension Match Status: compatible / mismatch с предупреждением
- Available Providers: карточки с Gemini, Local, OpenAI
  - Каждая карточка: name, dimension, hardware requirements, cost
  - Кнопка "Switch to X" (disabled если уже active)
  - Badge "Active" / "Coming Soon" / "Requires API Key"

**Логика:**

- При switch → обновить semantic.toml секцию `[defaults]`
- Показать flash message "✅ Switched, перезапусти Flask"
- Если dimension mismatch → показать JS confirmation с инструкциями

---

### 2. Template: settings.html

**Что делаем:**

- Создать `templates/settings.html` с Bootstrap 5 cards
- Current Provider Card:
  - Provider name badge (info color)
  - Dimension badge (secondary color)
  - DB dimension badge
  - Alert danger/success для dimension status
- Available Providers Grid:
  - col-md-4 для каждого провайдера
  - Card с provider info (dimension, hardware, cost)
  - Form с кнопкой "Switch to X"
  - Border-primary для active provider
- Help Section:
  - Ссылки на documentation (concepts, guides, reference)
- JavaScript:
  - confirmSwitch() — modal перед переключением
  - Warning если dimension mismatch
  - Инструкции по миграции БД (rm + re-ingest)

---

### 3. Navigation Link

**Что делаем:**

- Обновить `templates/base.html` navbar
- Добавить `<a href="{{ url_for('settings.index') }}">⚙️ Settings</a>`
- Разместить после Chat, перед возможным About/Help

---

### 4. Blueprint Registration

**Что делаем:**

- Обновить `app/__init__.py` в `create_app()`
- Добавить `from app.routes import settings`
- Добавить `app.register_blueprint(settings.bp)`

---

## 🎨 UI/UX Features

**Interactive Elements:**

1. **Provider Cards:**
   - Current provider выделен border-primary
   - Показывает badge "Active"
   - Disabled если уже активен

2. **Dimension Warning:**
   - Alert danger при mismatch
   - Link на migration guide
   - Подсветка несовместимости

3. **JavaScript Confirmation:**
   - Modal подтверждение перед switch
   - Предупреждение о dimension mismatch
   - Инструкции по миграции БД

4. **Provider Status:**
   - Badge "Coming Soon" для недоступных
   - Badge "Active" для текущего
   - Badge "Requires API Key" если нужен ключ

---

## 📝 Чеклист

### Backend

- [ ] Создать `app/routes/settings.py`:
  - [ ] GET `/settings` — показать текущий провайдер
  - [ ] POST `/settings/switch` — переключить провайдера
  - [ ] POST `/settings/check-dimension` — проверить compatibility (AJAX)

- [ ] Зарегистрировать blueprint в `app/__init__.py`

- [ ] Хелперы:
  - [ ] `get_provider_info()` — метаданные провайдера
  - [ ] `check_dimension_compatibility()` — проверка dimension
  - [ ] `update_semantic_toml()` — обновление конфига

### Frontend

- [ ] Создать `templates/settings.html`:
  - [ ] Current Provider section
  - [ ] Available Providers grid
  - [ ] Dimension mismatch alert
  - [ ] Help & Documentation links

- [ ] Обновить `templates/base.html`:
  - [ ] Добавить "Settings" в navbar

- [ ] JavaScript:
  - [ ] Confirmation modal перед switch
  - [ ] AJAX проверка dimension compatibility
  - [ ] Toast notifications для success/error

### Styling

- [ ] Bootstrap 5 cards для провайдеров
- [ ] Alert danger/success для dimension status
- [ ] Badges для provider status
- [ ] Responsive grid (col-md-4)

---

## 🧪 Тестирование

**Manual:**

- Открыть `/settings` → должен показать Gemini (768D) как current
- Кликнуть "Switch to Local" → должен показать warning о dimension mismatch
- Подтвердить → должен обновить semantic.toml
- Проверить semantic.toml → `embedding_provider` должен быть "local"
- Restart Flask → должен запуститься с Local (1024D)
- Settings должен показать Local как Active

**E2E:**

- `test_settings_page_loads()` — страница загружается
- `test_switch_provider()` — переключение провайдера
- `test_dimension_mismatch_warning()` — показывается warning

---

## 🎯 Результат

**Должно работать:**

- Settings page доступна по `/settings`
- Показывает текущий провайдер и dimension
- Кнопки "Switch to X" работают
- semantic.toml обновляется корректно
- Dimension mismatch показывает warning
- Confirmation modal работает
- Links на документацию кликабельны

**UX:**

- Интуитивный интерфейс выбора провайдера
- Предупреждения о последствиях переключения
- Инструкции по миграции БД

---

## 📚 Связанные фазы

- **Phase 17.5:** Flask Multi-Provider Integration
- **Phase 17.7:** Testing & Demo Stand
- **Phase 12.1:** Query Cache (existing Settings UI plan)

---

## ⚠️ Ограничения

- **Требует restart Flask** после switch (не hot-reload)
- **Dimension migration** не автоматическая (manual rm + re-ingest)
- **API key validation** не реализована в UI
- **Provider health check** не реализован (ping test)

---

## 💡 Future Enhancements (Out of Scope)

- Hot-reload провайдера без restart Flask
- One-click dimension migration (автоматическое пересоздание БД)
- API key validation в UI (test connection)
- Provider performance metrics (latency, throughput)
- A/B testing UI (compare providers side-by-side)

**Файл:** `examples/flask_app/app/routes/settings.py` (новый)

```python
"""Settings route для управления провайдерами."""

from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from semantic_core.config import get_config, SemanticConfig
from pathlib import Path
import toml

bp = Blueprint("settings", __name__, url_prefix="/settings")


@bp.route("/", methods=["GET"])
def index():
    """Страница настроек провайдеров."""
    config = get_config()
    core = current_app.extensions["semantic_core"]
    
    # Текущий провайдер
    current_provider = config.defaults.embedding_provider
    current_dimension = core.embedder.dimension if core else None
    
    # Доступные провайдеры
    available_providers = [
        {
            "id": "gemini",
            "name": "Gemini (Cloud)",
            "dimension": 768,
            "requires_api_key": True,
            "hardware": "Any",
            "cost": "$0.00001/1K tokens",
        },
        {
            "id": "local",
            "name": "Qwen3 (Local)",
            "dimension": 1024,
            "requires_api_key": False,
            "hardware": "macOS Apple Silicon",
            "cost": "FREE",
        },
        {
            "id": "openai",
            "name": "OpenAI (Cloud)",
            "dimension": 1536,
            "requires_api_key": True,
            "hardware": "Any",
            "cost": "$0.02/1M tokens",
            "status": "Coming Soon",
        },
    ]
    
    # DB dimension
    db_dimension = config.embedding_dimension
    dimension_mismatch = current_dimension != db_dimension if current_dimension else False
    
    return render_template(
        "settings.html",
        current_provider=current_provider,
        current_dimension=current_dimension,
        db_dimension=db_dimension,
        dimension_mismatch=dimension_mismatch,
        available_providers=available_providers,
    )


@bp.route("/switch", methods=["POST"])
def switch_provider():
    """Переключить провайдера embeddings."""
    new_provider = request.form.get("provider")
    
    if not new_provider:
        flash("❌ Provider не указан", "error")
        return redirect(url_for("settings.index"))
    
    # Валидация
    valid_providers = ["gemini", "local", "openai"]
    if new_provider not in valid_providers:
        flash(f"❌ Недопустимый provider: {new_provider}", "error")
        return redirect(url_for("settings.index"))
    
    # Обновить semantic.toml
    toml_path = Path("semantic.toml")
    if not toml_path.exists():
        flash("❌ semantic.toml не найден", "error")
        return redirect(url_for("settings.index"))
    
    try:
        config_data = toml.load(toml_path)
        config_data["defaults"]["embedding_provider"] = new_provider
        
        with toml_path.open("w") as f:
            toml.dump(config_data, f)
        
        flash(
            f"✅ Provider изменён на '{new_provider}'. "
            f"Перезапустите Flask для применения изменений.",
            "success"
        )
    
    except Exception as e:
        flash(f"❌ Ошибка обновления конфига: {e}", "error")
    
    return redirect(url_for("settings.index"))


@bp.route("/check-dimension", methods=["POST"])
def check_dimension():
    """Проверить dimension compatibility."""
    provider = request.form.get("provider")
    
    # Dimension mapping
    dimensions = {
        "gemini": 768,
        "local": 1024,
        "openai": 1536,
    }
    
    new_dimension = dimensions.get(provider)
    config = get_config()
    db_dimension = config.embedding_dimension
    
    if new_dimension != db_dimension:
        return {
            "compatible": False,
            "message": f"⚠️ Dimension mismatch! DB={db_dimension}D, {provider}={new_dimension}D",
            "action_required": "DB recreation",
            "guide_url": "/docs/guides/core/local-embeddings.html#migration",
        }
    
    return {
        "compatible": True,
        "message": "✅ Dimensions compatible",
    }
```

---

### 2. Template: settings.html

**Файл:** `examples/flask_app/app/templates/settings.html`

```html
{% extends "base.html" %}

{% block title %}Settings - Provider Management{% endblock %}

{% block content %}
<div class="container mt-4">
  <h1>⚙️ Settings</h1>
  
  <!-- Current Provider Card -->
  <div class="card mb-4">
    <div class="card-header bg-primary text-white">
      <h4 class="mb-0">📦 Current Provider</h4>
    </div>
    <div class="card-body">
      <div class="row">
        <div class="col-md-6">
          <p class="mb-1"><strong>Provider:</strong> 
            <span class="badge bg-info">{{ current_provider }}</span>
          </p>
          <p class="mb-1"><strong>Dimension:</strong> 
            <span class="badge bg-secondary">{{ current_dimension }}D</span>
          </p>
          <p class="mb-0"><strong>DB Dimension:</strong> 
            <span class="badge bg-secondary">{{ db_dimension }}D</span>
          </p>
        </div>
        
        <div class="col-md-6">
          {% if dimension_mismatch %}
          <div class="alert alert-danger mb-0">
            <strong>⚠️ Dimension Mismatch!</strong><br>
            Embedder ({{ current_dimension }}D) ≠ DB ({{ db_dimension }}D)<br>
            <a href="/docs/guides/core/local-embeddings.html#migration" target="_blank" class="alert-link">
              См. Migration Guide →
            </a>
          </div>
          {% else %}
          <div class="alert alert-success mb-0">
            <strong>✅ Dimensions Compatible</strong><br>
            Provider работает корректно
          </div>
          {% endif %}
        </div>
      </div>
    </div>
  </div>
  
  <!-- Available Providers -->
  <div class="card">
    <div class="card-header bg-secondary text-white">
      <h4 class="mb-0">🔄 Switch Provider</h4>
    </div>
    <div class="card-body">
      <div class="row">
        {% for provider in available_providers %}
        <div class="col-md-4 mb-3">
          <div class="card {% if provider.id == current_provider %}border-primary{% endif %}">
            <div class="card-body">
              <h5 class="card-title">
                {{ provider.name }}
                {% if provider.id == current_provider %}
                <span class="badge bg-success">Active</span>
                {% endif %}
                {% if provider.get('status') %}
                <span class="badge bg-warning">{{ provider.status }}</span>
                {% endif %}
              </h5>
              
              <ul class="list-unstyled">
                <li><strong>Dimension:</strong> {{ provider.dimension }}D</li>
                <li><strong>Hardware:</strong> {{ provider.hardware }}</li>
                <li><strong>Cost:</strong> {{ provider.cost }}</li>
                {% if provider.requires_api_key %}
                <li><strong>API Key:</strong> Required</li>
                {% endif %}
              </ul>
              
              {% if provider.id != current_provider and not provider.get('status') %}
              <form method="POST" action="{{ url_for('settings.switch_provider') }}" 
                    onsubmit="return confirmSwitch('{{ provider.id }}', {{ provider.dimension }})">
                <input type="hidden" name="provider" value="{{ provider.id }}">
                <button type="submit" class="btn btn-primary btn-sm w-100">
                  Switch to {{ provider.name }}
                </button>
              </form>
              {% endif %}
            </div>
          </div>
        </div>
        {% endfor %}
      </div>
    </div>
  </div>
  
  <!-- Help Section -->
  <div class="card mt-4">
    <div class="card-header">
      <h5 class="mb-0">💡 Help & Documentation</h5>
    </div>
    <div class="card-body">
      <ul>
        <li><a href="/docs/concepts/13_local_embeddings.html" target="_blank">Local Embeddings Concepts</a></li>
        <li><a href="/docs/guides/core/local-embeddings.html" target="_blank">Local Embeddings Guide</a></li>
        <li><a href="/docs/reference/local-models.html" target="_blank">Model Reference</a></li>
        <li><a href="/docs/concepts/11_multi_provider.html" target="_blank">Multi-Provider Architecture</a></li>
      </ul>
    </div>
  </div>
</div>

<script>
function confirmSwitch(provider, dimension) {
  const dbDimension = {{ db_dimension }};
  
  if (dimension !== dbDimension) {
    return confirm(
      `⚠️ WARNING: Dimension mismatch!\n\n` +
      `New provider: ${provider} (${dimension}D)\n` +
      `Current DB: ${dbDimension}D\n\n` +
      `You will need to RECREATE the database:\n` +
      `1. rm instance/semantic.db\n` +
      `2. flask ingest ./docs\n\n` +
      `Continue?`
    );
  }
  
  return confirm(`Switch to ${provider}?`);
}
</script>
{% endblock %}
```

---

### 3. Navigation Link

**Файл:** `examples/flask_app/app/templates/base.html`

Добавить в navbar:

```html
<!-- base.html navbar -->
<nav class="navbar navbar-expand-lg navbar-dark bg-dark">
  <div class="container-fluid">
    <a class="navbar-brand" href="{{ url_for('main.index') }}">
      🧠 Semantic KB
    </a>
    
    <div class="collapse navbar-collapse">
      <ul class="navbar-nav me-auto">
        <li class="nav-item">
          <a class="nav-link" href="{{ url_for('search.index') }}">🔍 Search</a>
        </li>
        <li class="nav-item">
          <a class="nav-link" href="{{ url_for('ingest.index') }}">📥 Ingest</a>
        </li>
        <li class="nav-item">
          <a class="nav-link" href="{{ url_for('chat.index') }}">💬 Chat</a>
        </li>
        <li class="nav-item">
          <a class="nav-link" href="{{ url_for('settings.index') }}">⚙️ Settings</a>
        </li>
      </ul>
    </div>
  </div>
</nav>
```

---

### 4. Blueprint Registration

**Файл:** `examples/flask_app/app/__init__.py`

```python
def create_app(**config_overrides) -> Flask:
    """Factory для создания Flask приложения."""
    app = Flask(__name__)
    
    # ... existing code ...
    
    # Register blueprints
    from app.routes import main, search, ingest, chat, settings
    
    app.register_blueprint(main.bp)
    app.register_blueprint(search.bp)
    app.register_blueprint(ingest.bp)
    app.register_blueprint(chat.bp)
    app.register_blueprint(settings.bp)  # ← Новый!
    
    return app
```

---

## 🎨 UI/UX Features

### Interactive Elements

1. **Provider Cards:**
   - Current provider выделен border-primary
   - Показывает badge "Active"
   - Disabled если уже активен

2. **Dimension Warning:**
   - Alert danger при mismatch
   - Link на migration guide
   - Подсветка несовместимости

3. **JavaScript Confirmation:**
   - Modal подтверждение перед switch
   - Предупреждение о dimension mismatch
   - Инструкции по миграции БД

4. **Provider Status:**
   - Badge "Coming Soon" для недоступных
   - Badge "Active" для текущего
   - Badge "Requires API Key" если нужен ключ

---

## 📝 Implementation Checklist

### Backend

- [ ] Создать `app/routes/settings.py`:
  - [ ] GET `/settings` — показать текущий провайдер
  - [ ] POST `/settings/switch` — переключить провайдера
  - [ ] POST `/settings/check-dimension` — проверить compatibility (AJAX)

- [ ] Зарегистрировать blueprint в `app/__init__.py`

- [ ] Хелперы:
  - [ ] `get_provider_info()` — метаданные провайдера
  - [ ] `check_dimension_compatibility()` — проверка dimension
  - [ ] `update_semantic_toml()` — обновление конфига

### Frontend

- [ ] Создать `templates/settings.html`:
  - [ ] Current Provider section
  - [ ] Available Providers grid
  - [ ] Dimension mismatch alert
  - [ ] Help & Documentation links

- [ ] Обновить `templates/base.html`:
  - [ ] Добавить "Settings" в navbar

- [ ] JavaScript:
  - [ ] Confirmation modal перед switch
  - [ ] AJAX проверка dimension compatibility
  - [ ] Toast notifications для success/error

### Styling

- [ ] Bootstrap 5 cards для провайдеров
- [ ] Alert danger/success для dimension status
- [ ] Badges для provider status
- [ ] Responsive grid (col-md-4)

---

## 🧪 Testing

### Manual Testing

```bash
# Test 1: Открыть Settings
python run.py
# → Открыть http://127.0.0.1:5000/settings
# → Должен показать Gemini (768D) как current

# Test 2: Switch to Local
# → Кликнуть "Switch to Local"
# → Должен показать warning о dimension mismatch
# → Подтвердить
# → Должен обновить semantic.toml

# Test 3: Проверить semantic.toml
cat semantic.toml
# → embedding_provider должен быть "local"

# Test 4: Restart Flask
python run.py
# → Должен запуститься с Local (1024D)
# → Settings должен показать Local как Active
```

### E2E Tests

```python
# tests/test_settings_ui.py
def test_settings_page_loads(client):
    """Settings page загружается."""
    response = client.get("/settings")
    assert response.status_code == 200
    assert b"Current Provider" in response.data

def test_switch_provider(client):
    """Переключение провайдера через UI."""
    response = client.post("/settings/switch", data={"provider": "local"})
    assert response.status_code == 302  # Redirect
    
    # Проверить что semantic.toml обновился
    import toml
    config = toml.load("semantic.toml")
    assert config["defaults"]["embedding_provider"] == "local"

def test_dimension_mismatch_warning(client):
    """Показывается warning при dimension mismatch."""
    # Создать БД с 768D
    # Переключить на Local 1024D
    
    response = client.get("/settings")
    assert b"Dimension Mismatch" in response.data
    assert b"Migration Guide" in response.data
```

---

## 🎯 Success Criteria

- ✅ Settings page доступна по `/settings`
- ✅ Показывает текущий провайдер и dimension
- ✅ Кнопки "Switch to X" работают
- ✅ semantic.toml обновляется корректно
- ✅ Dimension mismatch показывает warning
- ✅ Confirmation modal работает
- ✅ Links на документацию кликабельны

---

## 📚 Related

- **Phase 17.5:** Flask Multi-Provider Integration
- **Phase 17.7:** Testing & Demo Stand
- **Phase 12.1:** Query Cache (existing Settings UI plan)

---

## 🚧 Known Limitations

1. **Требует restart Flask** после switch (не hot-reload)
2. **Dimension migration** не автоматическая (manual rm + re-ingest)
3. **API key validation** не реализована в UI
4. **Provider health check** не реализован (ping test)

---

## 💡 Future Enhancements (Out of Scope)

- [ ] Hot-reload провайдера без restart Flask
- [ ] One-click dimension migration (автоматическое пересоздание БД)
- [ ] API key validation в UI (test connection)
- [ ] Provider performance metrics (latency, throughput)
- [ ] A/B testing UI (compare providers side-by-side)
