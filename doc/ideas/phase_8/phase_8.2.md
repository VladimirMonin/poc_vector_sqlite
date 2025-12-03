````markdown
# 📋 Phase 8.2: RAG Chat — Интерактивный интерфейс

**Статус:** 🔲 Планируется  
**Зависимости:** Phase 8.0 (Core CLI) ✅

---

## 🎯 Цель

Создать интерактивный чат-интерфейс с RAG (Retrieval-Augmented Generation):
- **REPL режим** — бесконечный цикл вопрос-ответ
- **Контекстный поиск** — автоматический retrieval из базы
- **LLM генерация** — ответы через Gemini с контекстом

---

## 🧠 RAG Pipeline

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   User      │────▶│   Search    │────▶│  Build      │────▶│   Gemini    │
│   Query     │     │   (top-k)   │     │  Prompt     │     │   Generate  │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           │                                       │
                           ▼                                       ▼
                    ┌─────────────┐                         ┌─────────────┐
                    │  Retrieved  │                         │   Answer    │
                    │  Chunks     │                         │  + Sources  │
                    └─────────────┘                         └─────────────┘
```

### Шаги

1. **Retrieval:** `core.search(query, limit=5)` → список релевантных чанков
2. **Prompt Building:** Формируем контекст из чанков + вопрос пользователя
3. **Generation:** Отправляем в Gemini, получаем ответ
4. **Presentation:** Рендерим ответ как Markdown + показываем источники

---

## 📦 Новые модули

```text
semantic_core/cli/commands/
└── chat.py               # semantic chat

semantic_core/core/
└── rag.py                # RAGPipeline class (опционально)
```

---

## 📐 Команда `chat` — Интерактивный режим

**Файл:** `commands/chat.py`

### Сигнатура

```bash
semantic chat [OPTIONS]
```

### Опции

| Опция | Тип | Описание |
|-------|-----|----------|
| `--model` | TEXT | Модель Gemini (default: gemini-2.5-flash) |
| `--context-chunks` | INT | Кол-во чанков для контекста (default: 5) |
| `--system-prompt` | TEXT | Кастомный системный промпт |
| `--no-sources` | FLAG | Не показывать источники |

### REPL Loop

```python
from rich.prompt import Prompt
from rich.markdown import Markdown

console.print("💬 Semantic Chat (type 'exit' to quit, '/help' for commands)")
console.print()

while True:
    try:
        query = Prompt.ask("[bold blue]You[/]")
        
        if query.lower() in ("exit", "quit", "/q"):
            break
        
        if query.startswith("/"):
            handle_slash_command(query)
            continue
        
        # RAG Pipeline
        with console.status("🔍 Searching..."):
            chunks = core.search(query, limit=context_chunks)
        
        with console.status("🧠 Thinking..."):
            answer = generate_answer(query, chunks, model)
        
        # Render answer
        console.print()
        console.print(Markdown(answer))
        console.print()
        
        # Show sources
        if not no_sources and chunks:
            render_sources(chunks, console)
        
    except KeyboardInterrupt:
        break

console.print("\n👋 Goodbye!")
```

### Slash Commands

| Команда | Действие |
|---------|----------|
| `/help` | Показать справку |
| `/sources` | Показать источники последнего ответа |
| `/source N` | Показать полный текст источника N |
| `/clear` | Очистить экран |
| `/model <name>` | Сменить модель |
| `/context N` | Изменить кол-во контекстных чанков |

### UX

```
$ semantic chat

💬 Semantic Chat (type 'exit' to quit, '/help' for commands)

You: Как настроить гибридный поиск?

🔍 Searching... ━━━━━━━━━━━━━━━━━━━━━━━━ 100%
🧠 Thinking... ━━━━━━━━━━━━━━━━━━━━━━━━ 100%

Для настройки гибридного поиска используйте метод `search()` с параметром 
`search_type="hybrid"`:

```python
results = core.search(
    query="ваш запрос",
    search_type="hybrid",
    limit=10,
)
```

Гибридный поиск комбинирует **векторный поиск** (семантическое сходство) 
и **FTS5** (точное совпадение) через алгоритм **RRF** (Reciprocal Rank Fusion).

📚 Sources:
  [1] docs/architecture/05_hybrid_search_rrf.md (score: 0.94)
  [2] docs/architecture/04_search_types.md (score: 0.87)

You: /source 1

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Source [1]: docs/architecture/05_hybrid_search_rrf.md

## Hybrid Search с RRF

Reciprocal Rank Fusion (RRF) — это алгоритм объединения ранжированных списков...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You: exit

👋 Goodbye!
```

---

## 📐 Генерация ответа

### System Prompt Template

```python
SYSTEM_PROMPT = """You are a helpful assistant for the Semantic Core library.
Answer questions based ONLY on the provided context.
If the context doesn't contain the answer, say "I don't have information about that."

Format your response in Markdown. Use code blocks for code examples.
Be concise but complete."""
```

### Context Building

```python
def build_context(chunks: list[SearchResult]) -> str:
    """Строит контекст из чанков для промпта."""
    context_parts = []
    
    for i, chunk in enumerate(chunks, 1):
        source = chunk.metadata.get("source_file", "unknown")
        context_parts.append(f"[Source {i}: {source}]\n{chunk.content}\n")
    
    return "\n---\n".join(context_parts)
```

### Prompt Assembly

```python
def build_prompt(query: str, context: str, system_prompt: str) -> str:
    return f"""{system_prompt}

CONTEXT:
{context}

USER QUESTION:
{query}

ANSWER:"""
```

### Gemini Call

```python
from google import genai

def generate_answer(query: str, chunks: list, model: str) -> str:
    context = build_context(chunks)
    prompt = build_prompt(query, context, SYSTEM_PROMPT)
    
    client = genai.Client(api_key=settings.api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
    )
    
    return response.text
```

---

## 🔤 CLI Эмодзи для логгера

**Новые паттерны:**

| Паттерн | Эмодзи | Модуль |
|---------|--------|--------|
| `chat` | 💬 | chat.py |
| `rag` | 🤖 | rag.py |
| `generate`, `llm` | 🧠 | Уже есть |

**Добавить в EMOJI_MAP:**
- `chat` → 💬
- `rag` → 🤖

---

## ✅ Acceptance Criteria

### Функциональные

1. [ ] `semantic chat` запускает REPL
2. [ ] Поиск находит релевантные чанки
3. [ ] Gemini генерирует ответ на основе контекста
4. [ ] Ответ рендерится как Markdown
5. [ ] Источники показываются после ответа
6. [ ] `/source N` показывает полный текст источника
7. [ ] `/help` работает
8. [ ] `exit` и Ctrl+C корректно завершают чат

### Качество

9. [ ] Rate limiting для Gemini (не спамить API)
10. [ ] Ошибки API показываются красиво
11. [ ] История команд (readline интеграция)

### Тесты

12. [ ] Unit-тест для build_context()
13. [ ] Unit-тест для build_prompt()
14. [ ] Integration-тест RAG pipeline (mock Gemini)

---

## 📚 Документация (после реализации)

### Архитектурный сериал

1. **Episode 42:** `42_rag_pipeline.md` — RAG архитектура
   - Retrieval + Augmentation + Generation
   - Prompt engineering
   - Context window management

2. **Episode 43:** `43_chat_interface.md` — REPL паттерны
   - Slash commands
   - Session state
   - Rich console integration

### Обновления

- Добавить секцию "Chat Mode" в README
- Примеры кастомных system prompts
- Гайд по оптимизации context_chunks

### EMOJI_MAP

Добавить в `formatters.py`:
```python
"chat": "💬",
"rag": "🤖",
```

---

## 🔮 Идеи на будущее (не в скоупе)

1. **Streaming responses:** Потоковый вывод ответа (печатает по мере генерации)
2. **Conversation history:** Хранить контекст диалога для follow-up вопросов
3. **Multi-turn RAG:** Использовать предыдущие ответы как контекст
4. **Export chat:** Сохранить диалог в Markdown файл
5. **Voice input:** Интеграция с whisper для голосового ввода

---

## 🔗 Связанные документы

- **Предыдущая:** [Phase 8.1 — Operations CLI](phase_8.1.md)
- **Gemini API:** [Phase 2 — Gemini Integration](../phase_2/report_phase_2.md)
- **Search:** [04_search_types.md](../../architecture/04_search_types.md)

````
