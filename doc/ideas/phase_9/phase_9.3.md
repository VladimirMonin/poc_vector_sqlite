# Phase 9.3: Slash Commands

**Статус:** 🔲 Планируется  
**Зависимости:** Phase 9.0 ✅  
**Оценка:** ~1 день

---

## 🎯 Цель

Расширенные slash-команды для поиска, добавления файлов, медиа.

---

## 📋 Все команды

### Базовые (9.0)

| Команда | Действие |
|---------|----------|
| `/help` | Справка по командам |
| `/clear` | Очистить экран |
| `/quit`, `/q` | Выход |

### Контекст (9.1-9.2)

| Команда | Действие |
|---------|----------|
| `/tokens` | Показать использование токенов |
| `/compress` | Принудительное сжатие истории |
| `/history` | Показать историю (кратко) |

### Поиск (9.3)

| Команда | Действие |
|---------|----------|
| `/search <query>` | Поиск в базе, добавить в контекст |
| `/search-mode <mode>` | Сменить режим: vector/fts/hybrid |
| `/sources` | Показать источники последнего ответа |
| `/source N` | Полный текст источника N |

### Файлы (9.3)

| Команда | Действие |
|---------|----------|
| `/add <path>` | Добавить файл в RAG базу |
| `/refresh` | Переиндексировать изменённые файлы |

### Медиа (9.3)

| Команда | Действие |
|---------|----------|
| `/image <path>` | Анализ изображения, добавить в контекст |
| `/audio <path>` | Анализ аудио, добавить в контекст |

### Настройки (9.3)

| Команда | Действие |
|---------|----------|
| `/model` | Показать текущую модель |
| `/model <name>` | Сменить модель |
| `/context <N>` | Изменить кол-во чанков контекста |

---

## 📦 Структура

```
semantic_core/cli/
├── commands/
│   └── chat.py
└── chat/
    ├── __init__.py
    ├── session.py          # ChatSession
    └── slash/
        ├── __init__.py
        ├── handler.py      # SlashCommandHandler
        ├── base.py         # BaseSlashCommand
        ├── search.py       # /search, /sources, /source
        ├── files.py        # /add, /refresh
        ├── media.py        # /image, /audio
        └── settings.py     # /model, /context, /tokens
```

---

## 📐 SlashCommandHandler

```python
# semantic_core/cli/chat/slash/handler.py

class SlashCommandHandler:
    """Обработчик slash-команд."""
    
    def __init__(self, session: ChatSession):
        self.session = session
        self.commands: dict[str, BaseSlashCommand] = {}
        self._register_defaults()
    
    def _register_defaults(self):
        self.register(HelpCommand())
        self.register(ClearCommand())
        self.register(SearchCommand())
        self.register(SourcesCommand())
        # ...
    
    def register(self, cmd: BaseSlashCommand):
        self.commands[cmd.name] = cmd
        for alias in cmd.aliases:
            self.commands[alias] = cmd
    
    def handle(self, input: str) -> bool:
        """Обработать команду. Возвращает True если обработана."""
        if not input.startswith("/"):
            return False
        
        parts = input[1:].split(maxsplit=1)
        cmd_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if cmd_name in self.commands:
            self.commands[cmd_name].execute(self.session, args)
            return True
        
        console.print(f"[yellow]Unknown command: /{cmd_name}[/]")
        return True
```

---

## 📐 BaseSlashCommand

```python
# semantic_core/cli/chat/slash/base.py

class BaseSlashCommand(ABC):
    name: str
    description: str
    aliases: list[str] = []
    
    @abstractmethod
    def execute(self, session: ChatSession, args: str) -> None:
        pass
```

---

## 📐 Примеры команд

```python
# semantic_core/cli/chat/slash/search.py

class SearchCommand(BaseSlashCommand):
    name = "search"
    description = "Search knowledge base and add to context"
    
    def execute(self, session, args):
        if not args:
            console.print("[yellow]Usage: /search <query>[/]")
            return
        
        results = session.core.search(args, limit=3)
        if not results:
            console.print("[yellow]No results found[/]")
            return
        
        # Добавляем в контекст
        context = "\n\n".join(r.content for r in results)
        session.add_to_context("search_results", context)
        
        console.print(f"[green]Added {len(results)} results to context[/]")


class SourcesCommand(BaseSlashCommand):
    name = "sources"
    description = "Show sources from last answer"
    aliases = ["src"]
    
    def execute(self, session, args):
        if not session.last_result:
            console.print("[yellow]No previous answer[/]")
            return
        
        table = Table(title="Sources")
        table.add_column("#")
        table.add_column("Source")
        table.add_column("Score")
        
        for i, src in enumerate(session.last_result.sources, 1):
            table.add_row(
                str(i),
                src.metadata.get("source", "unknown"),
                f"{src.score:.3f}"
            )
        
        console.print(table)
```

---

## 📐 /image и /audio

```python
# semantic_core/cli/chat/slash/media.py

class ImageCommand(BaseSlashCommand):
    name = "image"
    description = "Analyze image and add to context"
    
    def execute(self, session, args):
        path = Path(args.strip())
        if not path.exists():
            console.print(f"[red]File not found: {path}[/]")
            return
        
        with console.status("🖼️ Analyzing image..."):
            # Используем существующий ImageAnalyzer
            analyzer = session.get_image_analyzer()
            result = analyzer.analyze(path)
        
        session.add_to_context("image_analysis", result.description)
        console.print(f"[green]Image analyzed and added to context[/]")
```

---

## ✅ Acceptance Criteria

- [ ] `/help` показывает все команды
- [ ] `/search` работает и добавляет в контекст
- [ ] `/sources` и `/source N` работают
- [ ] `/add` добавляет файл в базу
- [ ] `/image` анализирует изображение
- [ ] `/model` меняет модель на лету
- [ ] Команды расширяемы (BaseSlashCommand)

---

## ⏱️ Оценка

| Задача | Часы |
|--------|------|
| slash/handler.py + base.py | 1 |
| search.py (/search, /sources) | 1.5 |
| files.py (/add, /refresh) | 1.5 |
| media.py (/image, /audio) | 2 |
| settings.py (/model, /context) | 1 |
| Тесты | 2 |
| **Итого** | **~9 часов** |
