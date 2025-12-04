# 🖼️ Диаграммы проекта

Этот каталог содержит отрендеренные диаграммы из PlantUML исходников.

---

## 📁 Структура

```
docs/diagrams/
├── *.puml              # Исходники PlantUML
└── images/
    ├── README.md       # Этот файл
    ├── architecture.webp
    ├── data-flow.webp
    ├── search-pipeline.webp
    ├── rag-sequence.webp
    ├── plugin-classes.webp
    ├── media-activity.webp
    ├── batch-sequence.webp
    └── llm-provider-class.webp
```

---

## 🔗 Как встраивать в документы

### Относительные пути

Документы лежат в `doc/architecture/`, а картинки в `docs/diagrams/images/`.

**Путь из документа:** `../../docs/diagrams/images/`

### Синтаксис Markdown

```markdown
![Название диаграммы](../../docs/diagrams/images/architecture.webp)

*Подпись: Описание диаграммы*
```

---

## 📋 Маппинг диаграмм → документов

| Диаграмма | Документ | Раздел |
|-----------|----------|--------|
| `architecture.webp` | `06_project_architecture.md` | 🏗 Архитектура системы |
| `data-flow.webp` | `07_data_flow.md` | 🔄 Поток данных |
| `search-pipeline.webp` | `05_hybrid_search_rrf.md` | 🔍 Pipeline поиска |
| `rag-sequence.webp` | `44_rag_engine_architecture.md` | 🤖 RAG Pipeline |
| `plugin-classes.webp` | `10_solid_refactoring.md` | 🧩 Интерфейсы |
| `media-activity.webp` | `25_media_processing_architecture.md` | 🖼️ Обработка медиа |
| `batch-sequence.webp` | `50_batch_api_implementation.md` | 📦 Batch API |
| `llm-provider-class.webp` | `45_llm_provider_abstraction.md` | 🔌 LLM Providers |

---

## 🎨 Пример встраивания

### В `06_project_architecture.md`

```markdown
## 🏗 Обзор архитектуры

![Component Diagram](../../docs/diagrams/images/architecture.webp)

*Диаграмма: Слои системы — Domain, Interfaces, Infrastructure, Integration*

Проект разделён на четыре основных слоя...
```

### В `44_rag_engine_architecture.md`

```markdown
## 🔄 Sequence диаграмма

![RAG Sequence](../../docs/diagrams/images/rag-sequence.webp)

*Диаграмма: Путь вопроса от пользователя до ответа с источниками*

1. Пользователь задаёт вопрос
2. RAGEngine ищет релевантные чанки
3. ...
```

---

## 🛠️ Генерация из PlantUML

### Локально (PlantUML JAR)

```bash
cd docs/diagrams
java -jar plantuml.jar -tpng *.puml -o images

# Конвертация в WebP (требует cwebp)
for f in images/*.png; do
  cwebp -q 90 "$f" -o "${f%.png}.webp"
  rm "$f"
done
```

### Через Docker

```bash
docker run --rm -v $(pwd)/docs/diagrams:/data \
  plantuml/plantuml -tpng "*.puml" -o images
```

### Онлайн (PlantUML Server)

1. Открыть <https://www.plantuml.com/plantuml/uml>
2. Вставить содержимое `.puml` файла
3. Скачать PNG/SVG
4. Конвертировать в WebP

---

## ⚠️ Важные нюансы

### 1. Относительные пути

```
doc/architecture/06_project_architecture.md
                  ↓
          ../../docs/diagrams/images/architecture.webp
          ^^    ^^
          │     └── docs/diagrams/images/
          └── выход из doc/architecture/
```

### 2. Регистр имён файлов

Linux чувствителен к регистру! Используй lowercase:

- ✅ `architecture.webp`
- ❌ `Architecture.webp`

### 3. WebP поддержка

WebP поддерживается:

- ✅ GitHub/GitLab Markdown
- ✅ VS Code Preview
- ✅ Все современные браузеры
- ⚠️ Старые версии Safari (до 14) — нет

---

## 📊 Размеры файлов (ориентир)

| Формат | Типичный размер | Качество |
|--------|-----------------|----------|
| PNG | 50-200 KB | Lossless |
| WebP | 20-80 KB | 90% quality |
| SVG | 5-30 KB | Vector |

**Рекомендация:** WebP с quality 90 — оптимальный баланс.

---

## ✅ Чеклист добавления диаграммы

1. [ ] Создать/обновить `.puml` в `docs/diagrams/`
2. [ ] Отрендерить в PNG/WebP
3. [ ] Положить в `docs/diagrams/images/`
4. [ ] Добавить в соответствующий документ
5. [ ] Проверить превью в VS Code
6. [ ] Обновить эту таблицу маппинга

---

**Последнее обновление:** 4 декабря 2025
