# Phase 12.3: Fix Chat Interface

**Статус:** 📋 СПЕЦИФИКАЦИЯ  
**Дата:** 2025-12-05  
**Зависимость:** Phase 12.2  
**Цель:** Починить RAG-чат — сообщения отправляются, ответы приходят

---

## 📋 Описание проблемы

При отправке сообщения в чате:

- Сообщение исчезает из input
- Ответ не появляется
- Нет ошибок в консоли браузера (или есть?)

---

## 🔍 Диагностика

### 1. HTMX Flow

```
User types → Submit form → POST /chat/send → ChatService.ask() → RAGEngine.ask() → HTML partial
```

### 2. Возможные точки отказа

| Этап | Что проверить | Как проверить |
|------|---------------|---------------|
| HTMX form | `hx-post`, `hx-target`, `hx-swap` | Inspect element в браузере |
| Network | Запрос уходит, ответ приходит? | DevTools → Network |
| Flask route | Exception в `chat.py:send()`? | Логи Flask |
| ChatService | `service is None`? | Логи в `_check_service_available()` |
| RAGEngine | Не инициализирован? | `extensions.py` логи |
| LLM API | Ошибка Gemini? | Exception в `ChatService.ask()` |

---

## 🔧 Задачи

### 1. Проверить HTMX атрибуты

**Файл:** `app/templates/chat.html`

**Что искать:**

```html
<form hx-post="{{ url_for('chat.send') }}"
      hx-target="#chat-messages"
      hx-swap="beforeend">
```

**Проверить:**

- [ ] `hx-post` указывает на правильный endpoint
- [ ] `hx-target` — куда вставлять ответ
- [ ] `hx-swap` — как вставлять (beforeend, afterbegin, innerHTML?)

---

### 2. Добавить логирование в route

**Файл:** `app/routes/chat.py:send()`

```python
@chat_bp.route("/send", methods=["POST"])
def send():
    logger.info("🔵 Chat send started")
    
    service, error = _check_service_available()
    if error:
        logger.error(f"🔴 Service error: {error}")
        return error
    
    question = request.form.get("question", "").strip()
    logger.info(f"💬 Question: {question[:50]}...")
    
    try:
        response = service.ask(question=question, ...)
        logger.info(f"✅ Response received: {len(response.answer)} chars")
        return render_template("partials/chat_response.html", response=response)
    except Exception as e:
        logger.exception(f"🔥 Chat error: {e}")
        return render_template("partials/chat_error.html", error=str(e))
```

---

### 3. Проверить ChatService инициализацию

**Файл:** `app/extensions.py:165-186`

**Что проверить:**

- [ ] `GeminiLLMProvider` создаётся без exception
- [ ] `ChatService` создаётся и сохраняется в `app.extensions["chat_service"]`
- [ ] При ошибке — логируется warning

---

### 4. Проверить partial template

**Файл:** `app/templates/partials/chat_response.html`

**Что проверить:**

- [ ] Template существует
- [ ] Переменные `response.answer`, `response.sources` доступны
- [ ] Нет Jinja2 ошибок

---

## 🧪 Тестирование

### Manual Testing

1. Открыть `/chat`
2. Открыть DevTools → Network
3. Написать "Привет" → Submit
4. Смотреть:
   - Request уходит? (POST /chat/send)
   - Response приходит? (200 OK? HTML?)
   - Куда вставляется? (hx-target)

### Automated Test

```python
# tests/flask_app/test_chat_e2e.py
def test_chat_send(client):
    response = client.post("/chat/send", data={"question": "Привет"})
    assert response.status_code == 200
    assert b"<div" in response.data  # HTML partial
```

---

## 📊 Чеклист

- [ ] HTMX атрибуты проверены
- [ ] Логирование добавлено
- [ ] Network запрос уходит
- [ ] Response приходит (200)
- [ ] ChatService инициализирован
- [ ] Partial template рендерится
- [ ] Ответ отображается в UI
