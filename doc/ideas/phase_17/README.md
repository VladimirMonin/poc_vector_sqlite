# Phase 17: Local Embeddings & Flask Multi-Provider

> Документация локальных embeddings и интеграция Multi-Provider архитектуры в Flask App

---

## 📦 Каталог подфаз

### 📚 Документация (17.1-17.4)

| Подфаза | Название | Статус | Файлы в docs/ |
|---------|----------|--------|---------------|
| **17.1** | Local Embeddings Documentation | ✅ **DONE** | `concepts/13_local_embeddings.md`<br>`guides/core/local-embeddings.md`<br>`reference/local-models.md` |
| **17.2** | Flask Integration Guide | 📝 TODO | `guides/frameworks/flask.md` |
| **17.3** | API Reference Updates | 📝 TODO | `reference/interfaces.md`<br>`reference/factory.md` |
| **17.4** | Django Integration Pattern | 📌 Placeholder | `guides/frameworks/django.md` (future) |

### 🔧 Реализация (17.5-17.7)

| Подфаза | Название | Статус | Код |
|---------|----------|--------|-----|
| **17.5** | Flask Multi-Provider Integration | 📋 Planned | `examples/flask_app/app/extensions.py`<br>`examples/flask_app/semantic.toml` |
| **17.6** | Settings UI (Provider Switcher) | 📋 Planned | `examples/flask_app/app/routes/settings.py`<br>`examples/flask_app/app/templates/settings.html` |
| **17.7** | Testing & Demo Stand | 📋 Planned | `tests/test_extensions.py`<br>`examples/flask_app/DEMO.md` |

---

## 🎯 Цель Phase 17

**Проблема:**
1. LocalEmbedder реализован (Phase 15.0), но **не задокументирован** — пользователи не знают про Qwen3
2. Flask App использует hardcoded Gemini — **не поддерживает Local embeddings**
3. Нет демо стенда для проверки всей функциональности библиотеки

**Решение:**
- ✅ **17.1:** Создать полную документацию Local Embeddings (Qwen3, MRL, hardware)
- 📝 **17.2-17.3:** Дописать документацию интеграций и API reference
- 📋 **17.5-17.7:** Интегрировать ComponentFactory в Flask App + Settings UI + Demo Stand

---

## 📝 Прогресс

### ✅ Phase 17.1 — Local Embeddings Documentation (DONE)

**Commit:** `d092405` — "phase 17.1 feat: Добавлена документация локальных embeddings"

**Созданные файлы:**
- `docs/concepts/13_local_embeddings.md` (~700 строк) — теория MRL, backends, сравнение с cloud
- `docs/guides/core/local-embeddings.md` (~850 строк) — Quick Start, миграция, troubleshooting
- `docs/reference/local-models.md` (~550 строк) — таблицы моделей, config, API reference

**Обновлённые файлы:**
- `docs/concepts/11_multi_provider.md` — добавлен Qwen3 в сравнительную таблицу
- `docs/guides/extending/custom-embedder.md` — Windows/Linux альтернатива (sentence-transformers)

**Ключевые концепции:**
- **Matryoshka Representation Learning (MRL)** — vec[:N] + ре-нормализация
- **Два backend:** mlx-embeddings (BERT-like) vs mlx-lm (LLM-based для Qwen3)
- **Hardware:** MLX = macOS only (Apple Silicon M1+)
- **Qwen3-Embedding-0.6B** — лучшая локальная модель (1024D, multilingual, MRL 32-1024)

---

## 📋 Следующие шаги

### TODO: Phase 17.2 — Flask Integration Guide

Написать `docs/guides/frameworks/flask.md` с:
- Application Factory паттерн
- ComponentFactory интеграция
- DI через app.extensions
- Graceful degradation
- Примеры кода

### TODO: Phase 17.3 — API Reference Updates

Обновить `docs/reference/interfaces.md` с:
- Полные сигнатуры методов
- Properties (dimension, max_tokens)
- Raises (какие исключения)
- Примеры использования
- ComponentFactory API

**Результат:** Техническое задание для Phase 17.1-17.4

---

### Phase 17.1: Local Embeddings Documentation 🔥

**Цель:** Актуализировать документацию локальных моделей.

**Что будет создано:**

1. **`docs/concepts/13_local_embeddings.md`** — концепция локальных моделей
   - MLX vs sentence-transformers
   - Выбор модели по hardware (Apple/CUDA/CPU)
   - MRL и dimension truncation

---

## 📚 Детальные планы

### Документация

- 📄 [phase_17.1_local_embeddings_docs.md](phase_17.1_local_embeddings_docs.md) — план + результаты Phase 17.1
- 📄 [phase_17.2_flask_integration.md](phase_17.2_flask_integration.md) — план Flask интеграции
- 📄 [phase_17.3_api_reference_updates.md](phase_17.3_api_reference_updates.md) — план API reference
- 📄 [phase_17.4_django_integration_placeholder.md](phase_17.4_django_integration_placeholder.md) — заглушка для Django

### Реализация

- 📄 [phase_17.5_flask_multi_provider.md](phase_17.5_flask_multi_provider.md) — рефакторинг Flask App (ComponentFactory)
- 📄 [phase_17.6_settings_ui.md](phase_17.6_settings_ui.md) — Settings UI для переключения провайдеров
- 📄 [phase_17.7_testing_demo.md](phase_17.7_testing_demo.md) — тестирование и демо стенд

### Notes

- 📄 [phase_17_notes.md](phase_17_notes.md) — исследования MRL, backends, hardware
- ✅ Все таблицы провайдеров актуальны
- ✅ Примеры кода протестированы

### Расширяемость

- ✅ Легко добавить новую локальную модель (структура готова)
- ✅ Легко добавить Django integration (паттерн заложен)
- ✅ Легко добавить новый провайдер (шаблон есть)

---

## 🔗 Связанные фазы

| Фаза | Отношение | Статус |
|------|-----------|--------|
| Phase 15 | Реализация multi-provider | ✅ Done |
| Phase 16 | Debug Observatory | ✅ Done |
| **Phase 17** | **Документация 15-16** | **🚧 In Progress** |
| Phase 18+ | Новые провайдеры/модели | 📌 Future |

---

## 🎨 Принципы документации

### Согласованность с архитектурным сериалом

- `doc/architecture/` — детальные технические статьи (для разработчиков)
- `docs/` — практические гайды (для пользователей)

**Разделение:**

| Тип | Где | Для кого |
|-----|-----|----------|
| Архитектурные решения | doc/architecture/ | Контрибьюторы |
| Концепции | docs/concepts/ | Advanced пользователи |
| Гайды | docs/guides/ | Все пользователи |
| Справочники | docs/reference/ | Quick lookup |

### Стиль (из 00_documentation_style_guide.md)

1. **Минимум кода, максимум объяснений**
   - Не дублировать код из репо
   - Фокус на паттернах и концептах

2. **Таблицы для сравнения**
   - Модели, провайдеры, фреймворки
   - Чёткие критерии выбора

3. **Практические примеры**
   - Реальные use cases
   - Типичные ошибки и решения

4. **Связанные ресурсы**
   - Ссылки между документами
   - Ссылки на архитектурный сериал

---

## 📅 Временная оценка

| Подфаза | Оценка | Зависимости |
|---------|--------|--------------|
| 17.0 Audit | 1 день | ✅ Done |
| 17.1 Local Embeddings | 2-3 дня | 17.0 |
| 17.2 Flask Integration | 4-5 дней | 17.1 (код + доки) |
| 17.3 API Reference | 2-3 дня | 17.1 |
| 17.4 Django | - | Future (не сейчас) |

**Итого:** ~10-12 дней работы

---

## 🚀 Workflow

### Приоритет выполнения

```
17.0 Audit (Done)
    ↓
17.1 Local Embeddings Docs ← Начать первым
    ↓
17.2 Flask Migration (код) ← СНАЧАЛА код
    ↓
17.2 Flask Docs (документация) ← ПОТОМ доки
    ↓
17.3 API Reference ← Параллельно с 17.2 docs
    ↓
17.4 Django (когда понадобится)
```

### Правила коммитов

Формат: `phase 17.N feat: <описание>`

Примеры:
- `phase 17.1 feat: Добавлена документация Qwen3-Embedding`
- `phase 17.2 feat: Flask App миграция на ComponentFactory`
- `phase 17.3 feat: Детальный API Reference для LocalEmbedder`

---

**Статус:** 🚧 In Progress | **Версия:** Draft | **Дата:** 11 декабря 2025
