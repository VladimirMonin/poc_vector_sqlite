# 🎨 Подфаза 11.7: PlantUML Diagrams

> Создание всех диаграмм для документации

---

## 🎯 Цель

Создать 8+ PlantUML диаграмм, покрывающих основные архитектурные аспекты.

---

## 📋 Файлы для создания

### 1. diagrams/architecture.puml

**Тип**: Component diagram

**Показывает**:
- Все слои: Domain, Interfaces, Infrastructure, Core, CLI
- Связи между слоями
- Какие компоненты в каком слое

**Используется в**: concepts/10_plugin_system.md, README

---

### 2. diagrams/data-flow.puml

**Тип**: Sequence diagram

**Показывает**:
- Полный цикл: Text → Embedder → VectorStore → Search
- Участники: User, CLI, SemanticCore, Embedder, VectorStore
- Ключевые данные на каждом шаге

**Используется в**: concepts/01_embeddings.md, guides/quickstart.md

---

### 3. diagrams/search-pipeline.puml

**Тип**: Activity diagram

**Показывает**:
- Ветвление по mode: vector / fts / hybrid
- Параллельное выполнение в hybrid mode
- RRF слияние результатов

**Используется в**: concepts/03_hybrid_rrf.md

---

### 4. diagrams/rag-sequence.puml

**Тип**: Sequence diagram

**Показывает**:
- Question → Search → Context building → LLM → Answer
- Участники: User, RAGEngine, SemanticCore, LLMProvider
- History management

**Используется в**: concepts/08_rag_architecture.md, guides/rag-chat.md

---

### 5. diagrams/plugin-classes.puml

**Тип**: Class diagram

**Показывает**:
- Все 7 интерфейсов
- Текущие реализации
- Связи implements/extends

**Используется в**: concepts/10_plugin_system.md, reference/interfaces.md

---

### 6. diagrams/media-activity.puml

**Тип**: Activity diagram

**Показывает**:
- Определение типа медиа
- Ветвление: Image / Audio / Video
- Queue processing flow

**Используется в**: concepts/07_multimodal.md, guides/media-processing.md

---

### 7. diagrams/batch-sequence.puml

**Тип**: Sequence diagram

**Показывает**:
- ingest(mode=async) → queue
- flush() → Batch API
- sync_status() → update vectors

**Используется в**: concepts/06_batch_processing.md

---

### 8. diagrams/llm-provider-class.puml

**Тип**: Class diagram

**Показывает**:
- BaseLLMProvider interface
- GeminiLLMProvider implementation
- Потенциальные: OpenAI, Anthropic, Ollama

**Используется в**: guides/extending/custom-llm-provider.md

---

## 📐 Правила PlantUML

### Обязательные элементы

```plantuml
@startuml
title Заголовок диаграммы    ' ← Обязательно

' Контент диаграммы

note right of Component       ' ← Рекомендуется
    Пояснение
end note

legend right                  ' ← Обязательно
    |= Символ |= Значение |
    | --> | Использует |
    | ..|> | Реализует |
endlegend
@enduml
```

### Запрещено

```plantuml
' ❌ НЕ использовать:
skinparam ...
!theme ...
<style>...</style>
```

### Цвета (только если критично)

```plantuml
' ✅ Допустимо для выделения:
component "Critical" #red
```

---

## 📊 Типы диаграмм по назначению

| Тип | Когда использовать | Ключевые слова |
|-----|-------------------|----------------|
| **Component** | Архитектура модулей | `component`, `package`, `-->` |
| **Sequence** | Поток данных, API calls | `->`, `-->`, `activate`, `note` |
| **Class** | Интерфейсы, наследование | `class`, `interface`, `<\|..` |
| **Activity** | Ветвление, workflow | `if`, `else`, `fork`, `end fork` |

---

## 🖼️ Компиляция в PNG

### Локально (plantuml.jar)

```bash
java -jar plantuml.jar diagrams/*.puml
```

### VS Code extension

- Name: PlantUML
- ID: jebbs.plantuml
- Ctrl+Shift+P → PlantUML: Export Current Diagram

### Makefile (рекомендуется)

```makefile
diagrams: $(patsubst %.puml,%.png,$(wildcard docs/diagrams/*.puml))

docs/diagrams/%.png: docs/diagrams/%.puml
	java -jar plantuml.jar -tpng $<
```

---

## ✅ Критерии готовности

- [ ] 8 .puml файлов созданы
- [ ] Все имеют title и legend
- [ ] Notes для сложных элементов
- [ ] Скомпилированы в .png
- [ ] .png добавлены в git (или .gitignore если генерируются)

---

## 🔗 Зависимости

**Требует**: 11.1 (структура папок)
**Блокирует**: Нет (можно делать параллельно с другими)

---

## 💡 Совет

Диаграммы можно создавать **параллельно с документами**, в которых они используются. Агент, пишущий concepts/03_hybrid_rrf.md, может сразу создать diagrams/search-pipeline.puml.
