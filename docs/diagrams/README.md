# Диаграммы Semantic Core

PlantUML диаграммы архитектуры проекта.

## Список диаграмм

### Общая архитектура

- `architecture.puml` - Общая архитектура системы
- `plugin_classes.puml` - Система плагинов и интерфейсов

### Core компоненты

- `data_flow.puml` - Поток данных: Ingest → Search
- `search_pipeline.puml` - Пайплайн поиска (vector/fts/hybrid)
- `batch_sequence.puml` - Batch API обработка

### RAG и LLM

- `rag_sequence.puml` - RAG: вопрос-ответ
- `llm_provider_class.puml` - Абстракция LLM провайдеров

### Media обработка

- `media_activity.puml` - Пайплайн обработки медиа

### Phase 15: Multi-Provider Architecture

- `phase15_component_factory_class.puml` - ComponentFactory классы
- `phase15_factory_sequence.puml` - Sequence создания компонентов
- `phase15_multi_provider.puml` - Экосистема провайдеров

### Phase 16: Debug Observatory

- `phase16_observatory_classes.puml` - Observatory классы
- `phase16_inspect_sequence.puml` - Sequence инспекции
- `phase16_snapshot_lifecycle.puml` - Lifecycle снимков

## Рендеринг

```bash
# Установка PlantUML (требует Java)
brew install plantuml

# Рендеринг в PNG
plantuml -tpng *.puml

# Рендеринг в SVG
plantuml -tsvg *.puml

# Рендеринг в WebP (требует конвертер)
plantuml -tpng *.puml && mogrify -format webp *.png && rm *.png
```

## Стиль

Все диаграммы написаны в чистом PlantUML без стилизации:

- Без `skinparam`
- Без `!theme`
- Без цветовых схем
- Только структура, notes и legend
