# 🎩 Phase 3: Integration Layer

> **Статус:** ✅ ЗАВЕРШЕНА  
> **Цель:** Связать ORM модели с семантическим поиском через descriptor magic

---

## 📖 Содержание фазы

### 12. Descriptor Protocol: Магия атрибутов класса
**Файл:** [12_descriptor_protocol.md](12_descriptor_protocol.md)

Как `Article.search` превращается в объект с методами поиска через `__get__()` дескриптора.

**Пример использования:**
```python
results = Article.search.hybrid("SOLID принципы", limit=5)
```

---

### 13. Method Patching: Автоматическая индексация
**Файл:** [13_method_patching.md](13_method_patching.md)

Патчинг `save()` и `delete_instance()` для автоматической индексации без `SignalModel`.

**Когда патчинг происходит:**
```python
class Article(BaseModel):
    search = SemanticIndexDescriptor()  # ← здесь патчится save()
```

---

### 14. SearchProxy и DocumentBuilder: От ORM к семантике
**Файл:** [14_orm_to_semantic.md](14_orm_to_semantic.md)

Превращение `Article` → `Document` → поиск → обратно в `Article`.

**Архитектура:**
- `SearchProxy` — фасад для всех типов поиска
- `DocumentBuilder` — преобразование ORM ↔ Document
- `SemanticIndexDescriptor` — точка входа из модели

---

## 🔗 Связанные фазы

- **Phase 1:** [SOLID Refactoring](../phase_1_solid/) — интерфейсы для зависимостей
- **Phase 2:** [Storage Layer](../phase_2_storage/) — PeeweeVectorStore как backend
- **Phase 4:** [Smart Parsing](../phase_4_smart_parsing/) — DocumentBuilder использует SmartSplitter

---

**← [Вернуться к оглавлению](../00_overview.md)**
