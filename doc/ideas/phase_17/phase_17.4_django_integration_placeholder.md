# Phase 17.4: Django Integration Pattern

> Расширение паттерна интеграций на Django (placeholder для будущего)

---

## 📦 Статус

- **Фаза:** 17.4 (Placeholder)
- **Зависит от:** Phase 17.2 (Flask Integration)
- **Блокирует:** Ничего
- **Приоритет:** 📌 Низкий (future work)
- **Оценка:** 3-4 дня (когда начнётся)

---

## 🎯 Назначение

Этот документ — **placeholder** для будущей Django интеграции.

**Текущий статус:** NOT STARTED

**Когда начать:**
- После Phase 17.2 (Flask Integration готов)
- Когда появится запрос на Django
- Или Phase 18+

---

## 💡 Предварительный план

### Отличия Django от Flask

| Аспект | Flask | Django |
|--------|-------|--------|
| DI Pattern | app.extensions dict | AppConfig.ready() |
| Config | Pydantic Settings | settings.py dict |
| Lifecycle | Application Factory | INSTALLED_APPS |
| Views | Functions/Class | Class-based views |

### Django специфика

#### 1. Инициализация через AppConfig

```python
# semantic_core_app/apps.py
from django.apps import AppConfig
from semantic_core.core.factory import ComponentFactory
from semantic_core import get_config

class SemanticCoreConfig(AppConfig):
    name = 'semantic_core_app'
    
    def ready(self):
        """Инициализация SemanticCore при старте Django."""
        config = get_config()
        self.semantic_core = ComponentFactory.create_semantic_core(config)
```

#### 2. Доступ в views

```python
# views.py
from django.apps import apps
from django.http import JsonResponse

def search_view(request):
    app_config = apps.get_app_config('semantic_core_app')
    core = app_config.semantic_core
    
    query = request.GET.get('q', '')
    results = core.search(query, limit=10)
    
    return JsonResponse({'results': [r.to_dict() for r in results]})
```

#### 3. Конфигурация через settings.py

```python
# settings.py
import os
from semantic_core import get_config

# SemanticCore config из semantic.toml
SEMANTIC_CONFIG = get_config()

# Django override (если нужен)
SEMANTIC_CONFIG.db_path = os.path.join(BASE_DIR, 'semantic.db')
```

---

## 📂 Структура документов (draft)

### Создать документы:

1. **`docs/guides/integrations/django.md`**
   - Setup и установка
   - AppConfig pattern
   - Доступ в views (function-based, class-based)
   - Management commands (`./manage.py semantic_ingest`)
   - Admin integration (опционально)

2. **Обновить `docs/guides/integrations/architecture.md`**
   - Добавить Django pattern
   - Сравнение Flask vs Django DI

3. **Обновить `docs/guides/integrations/sync-nature.md`**
   - Django async views (Django 3.1+)
   - Sync SemanticCore в async views (run_in_executor)

---

## 📋 Чек-лист (для будущего)

### Когда начнётся Phase 17.4:

- [ ] Создать Django example app (`examples/django_app/`)
- [ ] Реализовать AppConfig integration
- [ ] Создать management commands
- [ ] Написать `django.md` гайд
- [ ] Обновить `architecture.md`
- [ ] Протестировать на Django 4.2+

---

## 🔗 Связанные задачи

| Задача | Статус |
|--------|--------|
| Phase 17.2 (Flask) | ✅ Done (prerequisite) |
| **Phase 17.4 (Django)** | 📌 Placeholder |
| Phase 18+ (FastAPI?) | 💭 Potential |

---

## 🎨 Паттерн расширяемости

Flask Integration (Phase 17.2) создал **шаблон** для фреймворков:

```
1. Application Factory / Lifecycle hook
2. DI через фреймворк-специфичный механизм
3. Доступ к SemanticCore в views
4. semantic.toml конфигурация (унифицированная)
5. Production checklist
```

**Django просто переиспользует этот паттерн с Django-специфичными деталями.**

---

**Статус:** 📌 Placeholder | **Автор:** GitHub Copilot | **Дата:** 11 декабря 2025
