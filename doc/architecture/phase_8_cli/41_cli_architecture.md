# 🖥 Episode 41: CLI Architecture

> Как Typer превращает библиотеку в удобный инструмент командной строки

---

## 🎯 Зачем CLI?

Библиотека предоставляет Python API, но часто нужно:

- Быстро проиндексировать документы
- Сделать поиск без написания кода
- Проверить конфигурацию
- Запустить batch-обработку

**CLI решает эти задачи:**

```bash
# Вместо Python скрипта
semantic add notes/
semantic search "как работает RRF?"
semantic batch flush
semantic doctor
```

---

## 🏗 Архитектура CLI

```
┌─────────────────────────────────────────────────────────────────┐
│                         semantic                                │
│                      (entry point)                              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                          app.py                                 │
│              Typer Application + Callback                       │
│                                                                 │
│   semantic --version                                            │
│   semantic --help                                               │
└────────────────────────────┬────────────────────────────────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
           ▼                 ▼                 ▼
    ┌────────────┐    ┌────────────┐    ┌────────────┐
    │   init     │    │   config   │    │   doctor   │
    │ init_cmd   │    │ config_cmd │    │ doctor_cmd │
    └──────┬─────┘    └──────┬─────┘    └──────┬─────┘
           │                 │                 │
           └─────────────────┼─────────────────┘
                             │
                             ▼
              ┌────────────────────────────┐
              │        CLIContext          │
              │                            │
              │  get_config() → immediate  │
              │  get_core()   → lazy       │
              │  get_batch()  → lazy       │
              └────────────────────────────┘
```

---

## 🧩 Компоненты

### Entry Point

```python
# semantic_core/cli/__init__.py
from .app import app

def main() -> None:
    """Entry point для CLI."""
    app()

# pyproject.toml
[project.scripts]
semantic = "semantic_core.cli:main"
```

### Typer Application

```python
# semantic_core/cli/app.py
import typer
from semantic_core import __version__

app = typer.Typer(
    name="semantic",
    help="🔍 Semantic Core CLI — семантический поиск из терминала",
    add_completion=False,
)

def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"Semantic Core v{__version__}")
        raise typer.Exit()

@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v",
        callback=version_callback,
        is_eager=True,  # Выполнить до команды
        help="Показать версию"
    ),
) -> None:
    """🔍 Semantic Core CLI."""
    pass
```

### CLIContext — ленивая инициализация

**Ключевая идея:** `semantic --help` должен работать мгновенно!

```python
# semantic_core/cli/context.py
class CLIContext:
    """Контекст CLI с ленивой инициализацией."""
    
    def __init__(self) -> None:
        self._config: SemanticConfig | None = None
        self._core: SemanticCore | None = None
        self._batch_manager: BatchManager | None = None
    
    def get_config(self) -> SemanticConfig:
        """Config загружается сразу — это быстро."""
        if self._config is None:
            self._config = get_config()
        return self._config
    
    def get_core(self) -> SemanticCore:
        """Core создаётся лениво — только когда нужен."""
        if self._core is None:
            config = self.get_config()
            self._core = SemanticCore(...)  # Тяжёлая инициализация
        return self._core
```

**Почему это важно:**

```bash
# Быстро — не создаёт Core
$ semantic --help
$ semantic config show
$ semantic doctor

# Медленно — создаёт Core
$ semantic add document.md  # Нужен для индексации
$ semantic search "query"   # Нужен для поиска
```

---

## 📝 Анатомия команды

### Простая команда: doctor

```python
# semantic_core/cli/commands/doctor_cmd.py
import typer
from rich.table import Table
from ..console import console

app = typer.Typer(help="🔬 Диагностика окружения")

@app.command()
def run() -> None:
    """Проверить окружение Semantic Core."""
    console.print("\n🔬 Диагностика Semantic Core...\n")
    
    table = Table()
    table.add_column("Компонент")
    table.add_column("Версия")
    table.add_column("Статус")
    
    # Python
    table.add_row("Python", sys.version.split()[0], "✅")
    
    # sqlite-vec
    try:
        import sqlite_vec
        table.add_row("sqlite-vec", sqlite_vec.__version__, "✅")
    except ImportError:
        table.add_row("sqlite-vec", "не установлен", "❌")
    
    console.print(table)
```

### Команда с подкомандами: config

```python
# semantic_core/cli/commands/config_cmd.py
import typer

app = typer.Typer(help="⚙️ Управление конфигурацией")

@app.command("show")
def show() -> None:
    """Показать текущую конфигурацию."""
    ...

@app.command("check")
def check() -> None:
    """Проверить валидность конфигурации."""
    ...
```

### Интерактивная команда: init

```python
# semantic_core/cli/commands/init_cmd.py
@app.command()
def run(
    force: bool = typer.Option(False, "--force", "-f", help="Перезаписать")
) -> None:
    """Создать semantic.toml интерактивно."""
    console.print("\n⚙️  Инициализация Semantic Core проекта...\n")
    
    # Интерактивные prompts
    db_path = typer.prompt(
        "📁 Путь к базе данных",
        default="semantic.db"
    )
    
    log_level = typer.prompt(
        "📊 Уровень логирования",
        default="INFO"
    )
    
    # Запись TOML
    config_path = Path.cwd() / "semantic.toml"
    with open(config_path, "w") as f:
        toml.dump(config_dict, f)
    
    console.print(f"\n✅ Создан {config_path}")
```

---

## 🎨 Rich Console

Все CLI команды используют Rich для красивого вывода:

```python
# semantic_core/cli/console.py
from rich.console import Console

console = Console()  # Синглтон

# Использование в командах:
console.print("[green]✅ Успех![/green]")
console.print("[red]❌ Ошибка[/red]")

# Таблицы
from rich.table import Table
table = Table(title="Результаты")
table.add_column("Документ")
table.add_column("Score")
console.print(table)

# Прогресс-бары
from rich.progress import Progress
with Progress() as progress:
    task = progress.add_task("Индексация...", total=100)
    for i in range(100):
        progress.update(task, advance=1)
```

---

## 📦 Регистрация команд

```python
# semantic_core/cli/commands/__init__.py
from ..app import app
from . import init_cmd, config_cmd, doctor_cmd

# Регистрация простых команд
app.command("init")(init_cmd.run)
app.command("doctor")(doctor_cmd.run)

# Регистрация группы команд
app.add_typer(config_cmd.app, name="config")
```

**Результат:**

```bash
$ semantic --help

Usage: semantic [OPTIONS] COMMAND [ARGS]...

🔍 Semantic Core CLI — семантический поиск из терминала

Options:
  -v, --version  Показать версию
  --help         Show this message and exit.

Commands:
  init     Создать semantic.toml
  config   ⚙️ Управление конфигурацией
  doctor   🔬 Диагностика окружения
```

---

## 🧪 Тестирование CLI

Typer предоставляет `CliRunner` для тестов:

```python
from typer.testing import CliRunner
from semantic_core.cli.app import app

runner = CliRunner()

def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.8.0" in result.stdout

def test_doctor():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Python" in result.stdout

def test_config_show():
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "database" in result.stdout.lower()
```

---

## 🔄 Exit Codes

Стандартные коды выхода:

```python
# 0 — успех
raise typer.Exit(0)

# 1 — ошибка (проблемы с конфигурацией, валидацией)
raise typer.Exit(1)

# 2 — неправильное использование (Typer делает автоматически)
```

```bash
$ semantic config check
✅ Всё в порядке
$ echo $?
0

$ semantic config check  # Нет API ключа
❌ GEMINI_API_KEY не настроен
$ echo $?
1
```

---

## 🔒 Обработка ошибок

```python
@app.command()
def search(query: str) -> None:
    try:
        ctx = CLIContext()
        results = ctx.get_core().search(query)
        display_results(results)
    except ValueError as e:
        console.print(f"[red]❌ Ошибка:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]💥 Неожиданная ошибка:[/red] {e}")
        if os.getenv("DEBUG"):
            console.print_exception()
        raise typer.Exit(1)
```

---

## 📊 Структура CLI пакета

```
semantic_core/cli/
├── __init__.py      # main() entry point
├── app.py           # Typer app + callback
├── console.py       # Rich Console singleton
├── context.py       # CLIContext (lazy init)
└── commands/
    ├── __init__.py  # Регистрация команд
    ├── init_cmd.py  # semantic init
    ├── config_cmd.py # semantic config show/check
    └── doctor_cmd.py # semantic doctor
```

---

## 💡 Best Practices

### 1. Lazy initialization для быстрого --help

```python
# ❌ Плохо — медленный --help
@app.command()
def search(query: str):
    core = SemanticCore()  # Тяжело!
    
# ✅ Хорошо — быстрый --help
@app.command()
def search(query: str):
    ctx = CLIContext()
    core = ctx.get_core()  # Лениво
```

### 2. Используй Rich для вывода

```python
# ❌ Плохо — скучно
print("Results:", len(results))

# ✅ Хорошо — красиво
console.print(f"[green]✅ Найдено:[/green] {len(results)} результатов")
```

### 3. Информативные exit codes

```python
# ❌ Плохо — всегда 0
sys.exit(0)

# ✅ Хорошо — отражает результат
if problems:
    raise typer.Exit(1)
raise typer.Exit(0)
```

---

## 🎯 Итог

**Typer + Rich = мощный CLI:**

1. **Декларативные команды** — минимум boilerplate
2. **Автоматическая справка** — из docstrings
3. **Красивый вывод** — Rich Console
4. **Ленивая инициализация** — мгновенный --help
5. **Простое тестирование** — CliRunner

**Следующий шаг:** [Episode 42: CLI Commands](42_cli_commands.md) — детальный разбор каждой команды

---

**← [Назад к Episode 40](40_unified_configuration.md)** | **[Оглавление](00_overview.md)**
