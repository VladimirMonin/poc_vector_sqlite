# 49. Slash Commands: Интерактивное управление чатом

> **Эпизод 49** — Как превратить простой вопрос-ответ в полноценную командную оболочку

---

## 🎯 О чём этот эпизод

В предыдущих эпизодах мы создали RAG-чат, управление историей и сжатие контекста. Но пользователь по-прежнему мог только задавать вопросы. А что если ему нужно:

- Посмотреть источники ответа?
- Сменить модель на лету?
- Выполнить поиск без генерации?
- Узнать статистику токенов?

Для этого нужна система команд — знакомая всем по IRC, Discord, Slack.

---

## 🔮 Slash-паттерн: почему именно так?

Почему именно `/command`, а не `!command` или `:command`?

**Slash стал стандартом де-факто:**
- Discord, Slack, Telegram боты — везде `/`
- Git GUI клиенты — `/search`, `/commit`
- IDE — VS Code Command Palette начинается с `/`

**Плюсы slash-подхода:**
- Чёткое разделение: `/help` — команда, `help me` — вопрос
- Пользователь уже знает этот паттерн
- Легко парсить: проверил первый символ — готово

---

## 🏛️ Архитектура: Command Pattern

Классический паттерн Command идеально подходит для CLI:

```
┌─────────────────────────────────────────────────────────────┐
│                    SlashCommandHandler                       │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ _commands: dict[str, BaseSlashCommand]              │    │
│  │   "help" → HelpCommand                               │    │
│  │   "h"    → HelpCommand  (alias)                      │    │
│  │   "quit" → QuitCommand                               │    │
│  │   "q"    → QuitCommand  (alias)                      │    │
│  │   ...                                                │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  handle("/search query") → parse → route → execute          │
└─────────────────────────────────────────────────────────────┘
```

### Базовый контракт

```
BaseSlashCommand (ABC)
├── name: str           # "help"
├── description: str    # "Показать справку"
├── aliases: list[str]  # ["h", "?"]
├── usage: str          # "/help [command]"
└── execute(ctx, args) → SlashResult
```

### Результат выполнения

```
SlashResult
├── action: SlashAction    # CONTINUE / EXIT / CLEAR
├── message: str | None    # Текст для вывода
└── add_to_context: str    # Будущее: добавить в контекст LLM
```

**SlashAction** определяет, что делает REPL после команды:
- `CONTINUE` — продолжаем цикл (по умолчанию)
- `EXIT` — выходим из чата
- `CLEAR` — очищаем экран и продолжаем

---

## 🔧 ChatContext: связующее звено

Каждая команда получает доступ ко всему состоянию чата через один объект:

```
ChatContext (dataclass)
├── console: Console           # Rich для вывода
├── core: SemanticCore         # Поиск и индексация
├── rag: RAGEngine             # Вопрос-ответ
├── llm: BaseLLMProvider       # LLM провайдер
├── history_manager: ...       # История чата
├── last_result: RAGResult     # Последний ответ
├── search_mode: str           # "hybrid"
├── context_chunks: int        # 5
├── temperature: float         # 0.7
└── extra_context: dict        # Расширяемый словарь
```

**Почему dataclass, а не просто передача параметров?**

1. **Мутабельность** — команды могут менять настройки
2. **Расширяемость** — extra_context для будущих фич
3. **Единый интерфейс** — не надо менять сигнатуры при добавлении полей

---

## 📚 Каталог команд

### Базовые команды

| Команда | Алиасы | Описание |
|---------|--------|----------|
| `/help` | `/h`, `/?` | Список всех команд |
| `/quit` | `/q`, `/exit` | Выход из чата |
| `/clear` | `/cls` | Очистить экран |
| `/tokens` | — | Статистика токенов истории |
| `/history` | — | Показать историю сообщений |
| `/compress` | — | Принудительное сжатие истории |

### Поисковые команды

| Команда | Алиасы | Описание |
|---------|--------|----------|
| `/search <query>` | `/s` | Поиск без генерации ответа |
| `/search-mode [mode]` | `/mode` | Показать/сменить режим поиска |
| `/sources` | `/src` | Источники последнего ответа |
| `/source <N>` | — | Полный текст источника N |

### Настройки

| Команда | Алиасы | Описание |
|---------|--------|----------|
| `/model [name]` | `/m` | Показать/сменить модель LLM |
| `/context [N]` | `/ctx` | Количество чанков контекста |
| `/temperature [T]` | `/temp` | Температура генерации |

---

## 🔄 Роутинг в REPL

Изменения в основном цикле минимальны:

```
REPL Loop
    │
    ▼
query = input()
    │
    ├── query.startswith("/") ?
    │       │
    │       ▼
    │   SlashCommandHandler.handle(query, ctx)
    │       │
    │       ├── action == EXIT → break
    │       ├── action == CLEAR → clear_screen()
    │       └── action == CONTINUE → continue
    │
    └── else
            │
            ▼
        RAG.ask(query) → показать ответ
```

Ключевой момент: **команды обрабатываются ДО RAG**. Иначе `/help` пошло бы в LLM как вопрос.

---

## 🎨 Красивый вывод с Rich

Команды активно используют Rich для красивого вывода:

**HelpCommand** → Table с командами
**SourcesCommand** → Table с источниками и scores
**SourceCommand** → Panel с Markdown-контентом
**TokensCommand** → Table со статистикой

Пример таблицы `/sources`:

```
┌─────────────────────────────────────────────┐
│       📚 Источники последнего ответа        │
├───┬────────────────────────────┬────────────┤
│ # │ Источник                   │ Score      │
├───┼────────────────────────────┼────────────┤
│ 1 │ doc/architecture/05_rrf.md │ 0.892      │
│ 2 │ notes/search_types.md      │ 0.847      │
│ 3 │ ...                        │ ...        │
└───┴────────────────────────────┴────────────┘
```

---

## 🔌 Динамическая смена настроек

Особенность `/model` и `/context` — они меняют настройки на лету.

**ModelCommand** — создаёт новый LLM провайдер:
1. Проверяет, что ctx.llm — это GeminiLLMProvider
2. Создаёт новый провайдер с другой моделью
3. Обновляет ctx.llm и ctx.rag._llm

**ContextCommand** — проще:
1. Парсит и валидирует число (1-20)
2. Обновляет ctx.context_chunks
3. Обновляет ctx.rag._context_chunks

Пользователь может переключиться с `gemini-2.0-flash` на `gemini-1.5-pro` без перезапуска чата!

---

## 🧪 Тестирование команд

Для unit-тестов создаём моки всех зависимостей:

```
ChatContext с моками:
├── console: MagicMock(spec=Console)
├── core: MagicMock()
├── rag: MagicMock() с search.return_value
├── llm: MagicMock() с model_name
├── history_manager: MagicMock()
│   ├── __len__ = 5
│   ├── total_tokens() = 1500
│   └── has_summary = False
└── last_result: MagicMock()
    ├── sources = [source1, source2]
    ├── has_sources = True
    └── full_docs = False
```

**Особенности тестирования:**
- Команды выводят через `ctx.console.print()`, не возвращают message
- Проверяем `mock_context.console.print.assert_called()`
- Моки источников должны иметь реальные строки для Rich Markdown

---

## 🚧 Подводные камни

### LogRecord конфликты

Python logging резервирует имена `name`, `args`, `message` и другие. Наш логгер использовал их как kwargs:

```python
# ❌ Падает
logger.debug("Command", name=cmd_name, args=args)

# ✅ Работает
logger.debug("Command", cmd_name=cmd_name, cmd_args=args)
```

### HelpCommand требует handler

HelpCommand показывает список команд, значит ему нужен доступ к handler:

```python
# HelpCommand.__init__(handler)
cmd = HelpCommand(slash_handler)
slash_handler.register(cmd)
```

Цикл зависимостей решается тем, что register() вызывается после создания.

---

## 🔮 Будущие расширения

Архитектура готова к расширению:

1. **Автодополнение** — Tab completion по именам команд
2. **Плагины** — загрузка команд из внешних модулей
3. **Права** — некоторые команды только для админов
4. **Аргументы** — парсинг `--flag value` вместо позиционных

---

## 📊 Связь с экосистемой

```
┌─────────────────────────────────────────────────────────┐
│                     chat.py REPL                         │
│                          │                               │
│           ┌──────────────┴──────────────┐               │
│           ▼                              ▼               │
│   SlashCommandHandler              RAGEngine            │
│           │                              │               │
│     ┌─────┴─────┐                   ┌────┴────┐         │
│     ▼           ▼                   ▼         ▼         │
│  /search    /sources           SearchProxy   LLM       │
│     │           │                   │         │         │
│     ▼           ▼                   ▼         ▼         │
│  SemanticCore  last_result    SemanticCore  Gemini     │
└─────────────────────────────────────────────────────────┘
```

---

## 🎯 Итоги

**Slash-команды превращают чат в интерактивную среду:**

- `/search` — поиск без генерации
- `/sources` — анализ ответа
- `/model` — эксперименты с моделями
- `/tokens` — мониторинг расходов

**Архитектурные решения:**

- Command Pattern для расширяемости
- ChatContext как единый контейнер состояния
- SlashAction для управления REPL
- Rich для красивого вывода

**Результат:** Пользователь получает полный контроль над сессией чата.

---

**← [Назад: Context Compression](48_context_compression.md)** | **[Вперёд: TBD](50_tbd.md) →**
