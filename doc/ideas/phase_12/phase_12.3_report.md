# Phase 12.3: Chat Interface Improvements — Отчёт

**Статус:** ✅ ЗАВЕРШЕНО  
**Дата:** 2025-12-06  
**Ветка:** `phase_12`

---

## 📋 Выполненные задачи

### 1. Исправление HTMX Submit (Enter)

**Проблема:** При нажатии Enter форма делала обычный GET-submit вместо HTMX POST.

**Решение:**
```javascript
// Было: form.dispatchEvent(new Event('submit', { bubbles: true }));
// Стало:
htmx.trigger(form, 'submit');
```

**Файл:** `chat.html`

---

### 2. Исправление Typing Indicator

**Проблема:** Индикатор загрузки не исчезал после получения ответа.

**Решение:** Использование `htmx:afterRequest` вместо `htmx:afterSwap`:
```javascript
document.body.addEventListener('htmx:afterRequest', function(e) {
    if (e.detail.elt === form || e.detail.elt.closest('#chat-form')) {
        typing.classList.remove('show');
    }
});
```

---

### 3. Улучшение RAG Промпта

**Проблема:** LLM отвечал "I don't have enough information" даже когда контекст содержал ответ (особенно для video_ref/image_ref).

**Решение:** Переписан системный промпт:
- Явно указаны типы контента: `[text]`, `[code]`, `[image_ref]`, `[audio_ref]`, `[video_ref]`
- Инструкция использовать описания медиа для ответов о внешнем виде
- Убрана излишняя строгость "Answer ONLY based on context"

**Файл:** `semantic_core/core/rag.py`

---

### 4. Счётчик токенов беседы

**Реализация:**
- `ChatService.get_session_total_tokens()` — SUM по tokens_used
- `ChatResponse.total_tokens` — новое поле
- `chat_tokens_counter.html` — OOB partial
- Отображение в header чата: "Всего: X,XXX токенов"

**Обновление:** При каждом ответе и удалении сообщения через OOB swap.

---

### 5. Удаление отдельных сообщений

**Backend:**
- `ChatService.delete_message(message_id)` — удаляет и возвращает session_id
- `DELETE /chat/message/<id>` — HTMX endpoint

**Frontend:**
- Кнопка `×` на каждом сообщении (появляется при hover)
- `hx-delete` + `hx-confirm` для подтверждения
- OOB обновление счётчика токенов после удаления

**CSS:**
```css
.message-delete-btn {
    position: absolute;
    top: 0.25rem;
    right: 0.25rem;
    opacity: 0;
    transition: opacity 0.15s;
}
.message:hover .message-delete-btn { opacity: 0.7; }
```

---

### 6. Клик на источник → документ

**Реализация:** Source badges теперь `<a>` вместо `<span>`:
```html
<a href="{{ url_for('ingest.document_detail', doc_id=source.doc_id) }}" 
   target="_blank"
   class="source-badge text-decoration-none">
```

**CSS:**
```css
a.source-badge:hover {
    background: var(--bs-primary-bg-subtle) !important;
    transform: translateY(-1px);
}
```

---

### 7. Jinja фильтр from_json

**Проблема:** sources_json хранится как строка, нужен парсинг в шаблоне.

**Решение:**
```python
@app.template_filter("from_json")
def from_json_filter(value: str) -> any:
    return json.loads(value) if value else []
```

**Использование:** `{% set sources = msg.sources_json | from_json %}`

---

## 📁 Изменённые файлы

| Файл | Изменения |
|------|-----------|
| `semantic_core/core/rag.py` | Улучшен системный промпт |
| `app/services/chat_service.py` | +delete_message, +get_session_total_tokens, +total_tokens |
| `app/routes/chat.py` | +DELETE endpoint, +GET tokens, +total_tokens в index |
| `app/__init__.py` | +from_json filter |
| `app/templates/chat.html` | Счётчик, кнопки удаления, CSS, htmx fixes |
| `app/templates/partials/chat_response.html` | Delete btn, source links, OOB tokens |
| `app/templates/partials/chat_tokens_counter.html` | Новый partial |

---

## 🔧 Коммиты

1. `1b8d090` — feat: Улучшен RAG промпт для мультимедийного контента
2. `fb5ae3b` — feat: Методы удаления сообщений и подсчёта токенов в ChatService
3. `4b80263` — feat: HTMX endpoints для удаления сообщений и токенов
4. `299e93f` — feat: Jinja фильтр from_json для парсинга JSON строк
5. `3b3eaa1` — feat: Partial для OOB обновления счётчика токенов
6. `816db6f` — feat: Улучшен chat_response partial
7. `19cfdad` — feat: Полная переработка chat.html

---

## ✅ Результат

- ✅ Enter корректно отправляет сообщение через HTMX
- ✅ Typing indicator исчезает после ответа
- ✅ RAG отвечает на вопросы про внешний вид из video_ref
- ✅ Отображается общее количество токенов беседы
- ✅ Можно удалить любое сообщение
- ✅ Счётчик обновляется при удалении (OOB)
- ✅ Клик на источник открывает документ в новой вкладке
