---
title: "Custom ORM Adapter"
description: "Blueprint: как написать адаптер для Django, SQLAlchemy и др."
tags: ["integration", "django", "sqlalchemy", "adapter", "blueprint"]
difficulty: "advanced"
prerequisites: ["peewee"]
---

# Custom ORM Adapter 🔧

> Рецепт: ~50 строк кода для интеграции с любой ORM.

---

## Ключевая идея 💡

Semantic Core не знает о вашей ORM.
Вы пишете **тонкий адаптер**, который:
1. Перехватывает save/delete
2. Конвертирует ORM → Document
3. Вызывает core.ingest() / core.delete_by_metadata()

---

## Что нужно реализовать 📋

| Компонент | Задача |
|-----------|--------|
| **Event hooks** | Перехват save/delete |
| **Field mapping** | ORM instance → Document |
| **Search bridge** | SearchResult → ORM objects |

---

## Django Blueprint 🐍

### 1. Адаптер (~50 строк)

```python
# adapters/django_semantic.py
from django.db.models.signals import post_save, post_delete
from semantic_core import SemanticCore, Document

class DjangoSemanticAdapter:
    """Адаптер для Django ORM."""
    
    def __init__(
        self,
        model,
        core: SemanticCore,
        content_field: str,
        context_fields: list[str] = None,
    ):
        self.model = model
        self.core = core
        self.content_field = content_field
        self.context_fields = context_fields or []
        
        # Подключаем сигналы
        post_save.connect(self._on_save, sender=model)
        post_delete.connect(self._on_delete, sender=model)
    
    def _on_save(self, sender, instance, created, **kwargs):
        """Индексация при сохранении."""
        doc = self._to_document(instance)
        
        if not created:
            # Обновление — удаляем старое
            self.core.delete_by_metadata({"source_id": instance.pk})
        
        self.core.ingest(doc)
    
    def _on_delete(self, sender, instance, **kwargs):
        """Удаление из индекса."""
        self.core.delete_by_metadata({"source_id": instance.pk})
    
    def _to_document(self, instance) -> Document:
        """Конвертация Django model → Document."""
        content = getattr(instance, self.content_field, "")
        
        metadata = {"source_id": instance.pk}
        for field in self.context_fields:
            metadata[field] = getattr(instance, field, None)
        
        return Document(content=content, metadata=metadata)
    
    def search(self, query: str, limit: int = 10):
        """Поиск с конвертацией в ORM объекты."""
        results = self.core.search(query, limit=limit)
        
        ids = [r.document.metadata["source_id"] for r in results]
        objects = self.model.objects.filter(pk__in=ids)
        
        # Сохраняем порядок по score
        id_to_obj = {obj.pk: obj for obj in objects}
        return [id_to_obj[id] for id in ids if id in id_to_obj]
```

### 2. Использование

```python
# models.py
from django.db import models

class Article(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()

# apps.py
from .adapters.django_semantic import DjangoSemanticAdapter

class ArticlesConfig(AppConfig):
    def ready(self):
        from .models import Article
        from semantic_core import SemanticCore
        
        core = SemanticCore.from_config()
        self.search = DjangoSemanticAdapter(
            model=Article,
            core=core,
            content_field="content",
            context_fields=["title"],
        )
```

---

## SQLAlchemy Blueprint 🗃️

```python
# adapters/sqlalchemy_semantic.py
from sqlalchemy import event
from semantic_core import SemanticCore, Document

class SQLAlchemySemanticAdapter:
    """Адаптер для SQLAlchemy 2.0+."""
    
    def __init__(self, model, core: SemanticCore, content_field: str):
        self.model = model
        self.core = core
        self.content_field = content_field
        
        # События SQLAlchemy
        event.listen(model, 'after_insert', self._on_insert)
        event.listen(model, 'after_update', self._on_update)
        event.listen(model, 'before_delete', self._on_delete)
    
    def _on_insert(self, mapper, connection, target):
        doc = self._to_document(target)
        self.core.ingest(doc)
    
    def _on_update(self, mapper, connection, target):
        self.core.delete_by_metadata({"source_id": target.id})
        doc = self._to_document(target)
        self.core.ingest(doc)
    
    def _on_delete(self, mapper, connection, target):
        self.core.delete_by_metadata({"source_id": target.id})
    
    def _to_document(self, target) -> Document:
        return Document(
            content=getattr(target, self.content_field, ""),
            metadata={"source_id": target.id},
        )
```

---

## Разделение БД ⚠️

```
┌─────────────────────────────────────────────┐
│                                              │
│  ┌────────────────┐  ┌────────────────┐    │
│  │ Your Database  │  │  semantic.db   │    │
│  │  (PostgreSQL)  │  │   (SQLite)     │    │
│  └───────┬────────┘  └───────┬────────┘    │
│          │                    │             │
│    Django ORM          SemanticCore        │
│    SQLAlchemy                               │
│                                              │
│  ⚠️ Разные соединения, разные транзакции!  │
└─────────────────────────────────────────────┘
```

**Важно**: Если Django rollback — данные в semantic.db останутся!

---

## Маппинг полей 📊

| Django/SQLAlchemy | Document |
|-------------------|----------|
| `TextField` | content |
| `CharField` | content или metadata |
| `IntegerField` | metadata |
| `DateTimeField` | metadata |
| `ForeignKey` | metadata (id) |

---

## Частые ошибки ⚠️

| Ошибка | Почему | Решение |
|--------|--------|---------|
| Дубликаты после update | Не удаляли старое | `delete_by_metadata()` перед `ingest()` |
| Рассинхрон после rollback | Разные транзакции | Обрабатывайте `transaction.on_commit` |
| Медленная индексация | Синхронная обработка | Используйте Celery для batch |

---

## Следующие шаги 🔗

| Ресурс | Что узнаете |
|--------|-------------|
| [Plugin System](../../concepts/10_plugin_system.md) | Архитектура интерфейсов |
| [Batch Processing](../../concepts/06_batch_processing.md) | Async индексация |
