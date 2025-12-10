# 🤖 Phase 9: RAG Integration

> **Статус:** ✅ ЗАВЕРШЕНА  
> **Цель:** Retrieval-Augmented Generation для вопросов к базе знаний

---

## 📖 Содержание фазы

### 44. RAG Engine Architecture

**Файл:** [44_rag_engine_architecture.md](44_rag_engine_architecture.md)

Оркестратор вопрос-ответа: поиск → контекст → LLM → ответ с источниками.

**Pipeline:**

1. User question → Embeddings API
2. Hybrid search → top N chunks
3. Build context from chunks
4. LLM generates answer
5. Return answer + sources

---

### 45. LLM Provider Abstraction

**Файл:** [45_llm_provider_abstraction.md](45_llm_provider_abstraction.md)

`BaseLLMProvider` интерфейс, `GeminiLLMProvider` и возможность подключить любую LLM (OpenAI, Claude, Llama).

---

### 46. RAG Chat CLI

**Файл:** [46_rag_chat_cli.md](46_rag_chat_cli.md)

Интерактивный REPL для вопросов к базе знаний из терминала.

**Запуск:**

```bash
semantic chat
```

---

### 47. Chat History Management

**Файл:** [47_chat_history_management.md](47_chat_history_management.md)

Управление историей чата: стратегии `LastNMessages`, `TokenBudget` и автотримминг.

---

### 48. Context Compression

**Файл:** [48_context_compression.md](48_context_compression.md)

Сжатие истории через LLM summarization: `ContextCompressor` и `AdaptiveWithCompression`.

---

### 49. Slash Commands

**Файл:** [49_slash_commands.md](49_slash_commands.md)

Интерактивные команды чата: `/search`, `/sources`, `/model` и управление сессией.

**Команды:**

- `/search <query>` — поиск без LLM
- `/sources` — показать источники последнего ответа
- `/model <name>` — сменить модель
- `/clear` — очистить историю

---

## 🔗 Связанные фазы

- **Phase 2:** [Storage](../phase_2_storage/) — hybrid search для RAG
- **Phase 8:** [CLI](../phase_8_cli/) — команда `semantic chat`
- **Phase 12:** [Flask](../phase_12_flask/) — веб-интерфейс для RAG

---

**← [Вернуться к оглавлению](../00_overview.md)**
