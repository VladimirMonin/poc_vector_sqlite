# 📊 Reporters: Экспорт Inspection Snapshots

> Rich Console, Markdown, JSON, Diff — 4 формата вывода

**Коммит:** `591f972` — phase 16.0 feat: Реализован Debug Observatory (Reporters)

---

## 🎯 Задача

После создания `InspectionSnapshot` нужно представить данные в удобном виде:

- ✅ **ConsoleReporter** — для быстрого просмотра в терминале (Rich UI)
- ✅ **MarkdownReporter** — для документации и отчётов
- ✅ **JsonReporter** — для интеграций и автоматизации
- ✅ **DiffReporter** — для сравнения конфигураций

**Единый интерфейс:**
```python
class BaseReporter(ABC):
    @abstractmethod
    def report(self, snapshot: InspectionSnapshot) -> str:
        pass
```

---

## 🖥️ ConsoleReporter: Rich Terminal UI

### Задачи

1. **Красивый вывод** с использованием `rich` (таблицы, панели, цвета)
2. **Многоуровневая информация**: провайдеры → чанки → метрики
3. **Удобство восприятия**: эмодзи, выделение ключевых данных

### Реализация

```python
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

class ConsoleReporter(BaseReporter):
    """Rich-reporter для терминала."""
    
    def __init__(self):
        self.console = Console()
    
    def report(self, snapshot: InspectionSnapshot) -> str:
        """Выводит snapshot в консоль с Rich UI."""
        
        # 1. Заголовок
        self.console.print(Panel.fit(
            f"[bold cyan]🔍 Inspection Snapshot[/bold cyan]\n"
            f"[dim]{snapshot.processing_timestamp}[/dim]",
            border_style="cyan"
        ))
        
        # 2. Провайдеры
        self._render_providers(snapshot)
        
        # 3. Чанки
        self._render_chunks(snapshot)
        
        # 4. Поиск (если есть)
        if snapshot.searches:
            self._render_searches(snapshot)
        
        # 5. Метрики
        self._render_metrics(snapshot)
        
        return ""  # Вывод идёт в консоль напрямую
    
    def _render_providers(self, snapshot: InspectionSnapshot):
        """Рендерит информацию о провайдерах."""
        self.console.print("\n[bold yellow]📦 Providers Configuration[/bold yellow]")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Provider", style="cyan", width=20)
        table.add_column("Type", style="green")
        table.add_column("Model", style="blue")
        table.add_column("Dimension", justify="right", style="yellow")
        
        # Embedder
        if snapshot.embedder_metadata:
            meta = snapshot.embedder_metadata
            table.add_row(
                "Embedder",
                meta.provider_type,
                meta.model_name or "-",
                str(meta.dimension) if meta.dimension else "-"
            )
        
        # Transcriber
        if snapshot.transcriber_metadata:
            meta = snapshot.transcriber_metadata
            table.add_row(
                "Transcriber",
                meta.provider_type,
                meta.model_name or "-",
                "-"
            )
        
        # Vision
        if snapshot.vision_metadata:
            meta = snapshot.vision_metadata
            table.add_row(
                "Vision",
                meta.provider_type,
                meta.model_name or "-",
                "-"
            )
        
        self.console.print(table)
    
    def _render_chunks(self, snapshot: InspectionSnapshot):
        """Рендерит информацию о чанках."""
        self.console.print(f"\n[bold yellow]📄 Chunks ({len(snapshot.chunks)})[/bold yellow]")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("ID", justify="right", style="cyan", width=5)
        table.add_column("Content Preview", style="white", no_wrap=False, max_width=60)
        table.add_column("Dimension", justify="right", style="yellow")
        table.add_column("Hash", style="dim", width=10)
        
        for chunk in snapshot.chunks[:10]:  # Показываем первые 10
            preview = chunk.content[:100].replace("\n", " ")
            if len(chunk.content) > 100:
                preview += "..."
            
            table.add_row(
                str(chunk.chunk_id),
                preview,
                str(chunk.embedding_dimension),
                chunk.embedding_hash
            )
        
        if len(snapshot.chunks) > 10:
            table.add_row(
                "...",
                f"[dim]+ {len(snapshot.chunks) - 10} more chunks[/dim]",
                "",
                ""
            )
        
        self.console.print(table)
    
    def _render_searches(self, snapshot: InspectionSnapshot):
        """Рендерит результаты поиска."""
        self.console.print(f"\n[bold yellow]🔎 Search Results[/bold yellow]")
        
        for search in snapshot.searches:
            self.console.print(f"\n[cyan]Query:[/cyan] {search.query}")
            self.console.print(f"[dim]Mode: {search.search_mode} | Limit: {search.limit} | Results: {search.results_count}[/dim]")
            
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Rank", justify="right", style="cyan", width=5)
            table.add_column("Chunk ID", justify="right", style="yellow")
            table.add_column("Similarity", justify="right", style="green")
            table.add_column("Content Preview", style="white", no_wrap=False, max_width=50)
            
            for idx, result in enumerate(search.results[:5], 1):
                content_preview = result.get("content", "")[:80].replace("\n", " ")
                if len(result.get("content", "")) > 80:
                    content_preview += "..."
                
                table.add_row(
                    str(idx),
                    str(result.get("chunk_id", "-")),
                    f"{result.get('similarity', 0):.4f}",
                    content_preview
                )
            
            self.console.print(table)
    
    def _render_metrics(self, snapshot: InspectionSnapshot):
        """Рендерит метрики производительности."""
        self.console.print(f"\n[bold yellow]⚡ Performance Metrics[/bold yellow]")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Step", style="cyan")
        table.add_column("Duration", justify="right", style="green")
        
        for step in snapshot.steps:
            table.add_row(
                step["step_name"],
                f"{step['duration_ms']:.2f}ms"
            )
        
        table.add_row(
            "[bold]Total[/bold]",
            f"[bold]{snapshot.total_duration_ms:.2f}ms[/bold]"
        )
        
        self.console.print(table)
```

### Пример вывода

```
╭────────────────────────────────────────╮
│ 🔍 Inspection Snapshot                 │
│ 2025-12-10T14:30:15.123456            │
╰────────────────────────────────────────╯

📦 Providers Configuration
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━┓
┃ Provider         ┃ Type             ┃ Model ┃ Dimension ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━┩
│ Embedder         │ GeminiEmbedder   │ -     │       768 │
│ Vision           │ GeminiVision     │ -     │         - │
└──────────────────┴──────────────────┴───────┴───────────┘

📄 Chunks (5)
┏━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┓
┃  ID ┃ Content Preview                                        ┃ Dimension ┃ Hash     ┃
┡━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━┩
│   1 │ # Introduction to Python  Python is a high-level...   │       768 │ a3f2c1d4 │
│   2 │ ## Basic Syntax  Python uses indentation to define... │       768 │ b7e4a2f1 │
│   3 │ ### Variables  Variables in Python don't need...      │       768 │ c1d5b3a8 │
└─────┴────────────────────────────────────────────────────────┴───────────┴──────────┘

⚡ Performance Metrics
┏━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Step     ┃   Duration ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━┩
│ ingest   │   1234.56ms │
│ Total    │   1234.56ms │
└──────────┴────────────┘
```

**Преимущества:**

✅ **Визуально приятно** — таблицы, цвета, границы
✅ **Информативно** — вся ключевая информация с первого взгляда
✅ **Компактно** — первые N результатов + "... more"

---

## 📝 MarkdownReporter: Документация

### Задачи

1. **Структурированный Markdown** с заголовками и таблицами
2. **Копируемый формат** — можно вставить в документацию
3. **Полная информация** — без truncation

### Реализация

```python
class MarkdownReporter(BaseReporter):
    """Markdown-reporter для документации."""
    
    def report(self, snapshot: InspectionSnapshot) -> str:
        """Генерирует Markdown отчёт."""
        
        lines = []
        
        # Заголовок
        lines.append("# Inspection Snapshot")
        lines.append(f"\n**Timestamp:** {snapshot.processing_timestamp}")
        lines.append(f"**File:** `{snapshot.file_path}`\n")
        
        # Провайдеры
        lines.append("## Providers Configuration\n")
        lines.extend(self._render_providers_md(snapshot))
        
        # Чанки
        lines.append(f"\n## Chunks ({len(snapshot.chunks)})\n")
        lines.extend(self._render_chunks_md(snapshot))
        
        # Поиск
        if snapshot.searches:
            lines.append("\n## Search Results\n")
            lines.extend(self._render_searches_md(snapshot))
        
        # Метрики
        lines.append("\n## Performance Metrics\n")
        lines.extend(self._render_metrics_md(snapshot))
        
        return "\n".join(lines)
    
    def _render_providers_md(self, snapshot: InspectionSnapshot) -> List[str]:
        """Рендерит провайдеры в Markdown таблицу."""
        lines = [
            "| Provider | Type | Model | Dimension |",
            "|----------|------|-------|-----------|"
        ]
        
        if snapshot.embedder_metadata:
            meta = snapshot.embedder_metadata
            lines.append(
                f"| Embedder | {meta.provider_type} | "
                f"{meta.model_name or '-'} | {meta.dimension or '-'} |"
            )
        
        if snapshot.transcriber_metadata:
            meta = snapshot.transcriber_metadata
            lines.append(
                f"| Transcriber | {meta.provider_type} | "
                f"{meta.model_name or '-'} | - |"
            )
        
        if snapshot.vision_metadata:
            meta = snapshot.vision_metadata
            lines.append(
                f"| Vision | {meta.provider_type} | "
                f"{meta.model_name or '-'} | - |"
            )
        
        return lines
    
    def _render_chunks_md(self, snapshot: InspectionSnapshot) -> List[str]:
        """Рендерит чанки в Markdown таблицу."""
        lines = [
            "| ID | Content Preview | Dimension | Hash |",
            "|----|----------------|-----------|------|"
        ]
        
        for chunk in snapshot.chunks:
            preview = chunk.content[:80].replace("\n", " ").replace("|", "\\|")
            if len(chunk.content) > 80:
                preview += "..."
            
            lines.append(
                f"| {chunk.chunk_id} | {preview} | "
                f"{chunk.embedding_dimension} | `{chunk.embedding_hash}` |"
            )
        
        return lines
    
    def _render_searches_md(self, snapshot: InspectionSnapshot) -> List[str]:
        """Рендерит поиск в Markdown."""
        lines = []
        
        for search in snapshot.searches:
            lines.append(f"### Query: `{search.query}`")
            lines.append(f"**Mode:** {search.search_mode} | **Limit:** {search.limit} | **Results:** {search.results_count}\n")
            
            lines.append("| Rank | Chunk ID | Similarity | Content Preview |")
            lines.append("|------|----------|------------|----------------|")
            
            for idx, result in enumerate(search.results, 1):
                content = result.get("content", "")[:60].replace("\n", " ").replace("|", "\\|")
                if len(result.get("content", "")) > 60:
                    content += "..."
                
                lines.append(
                    f"| {idx} | {result.get('chunk_id', '-')} | "
                    f"{result.get('similarity', 0):.4f} | {content} |"
                )
            
            lines.append("")
        
        return lines
    
    def _render_metrics_md(self, snapshot: InspectionSnapshot) -> List[str]:
        """Рендерит метрики в Markdown таблицу."""
        lines = [
            "| Step | Duration |",
            "|------|----------|"
        ]
        
        for step in snapshot.steps:
            lines.append(f"| {step['step_name']} | {step['duration_ms']:.2f}ms |")
        
        lines.append(f"| **Total** | **{snapshot.total_duration_ms:.2f}ms** |")
        
        return lines
```

### Пример вывода

```markdown
# Inspection Snapshot

**Timestamp:** 2025-12-10T14:30:15.123456
**File:** `docs/example.md`

## Providers Configuration

| Provider | Type | Model | Dimension |
|----------|------|-------|-----------|
| Embedder | GeminiEmbedder | - | 768 |
| Vision | GeminiVision | - | - |

## Chunks (5)

| ID | Content Preview | Dimension | Hash |
|----|----------------|-----------|------|
| 1 | # Introduction to Python  Python is a high-level programming language that... | 768 | `a3f2c1d4` |
| 2 | ## Basic Syntax  Python uses indentation to define code blocks. Here's an... | 768 | `b7e4a2f1` |
| 3 | ### Variables  Variables in Python don't need explicit type declarations... | 768 | `c1d5b3a8` |

## Performance Metrics

| Step | Duration |
|------|----------|
| ingest | 1234.56ms |
| **Total** | **1234.56ms** |
```

**Преимущества:**

✅ **Копируемый** — можно вставить в GitHub Issues, PR, документацию
✅ **Полная информация** — все чанки без truncation
✅ **Читаемость** — Markdown таблицы удобны для восприятия

---

## 🗂️ JsonReporter: Machine-Readable

### Задачи

1. **JSON сериализация** snapshot для автоматизации
2. **Pretty print** с indent для читаемости
3. **Совместимость** с JSON tools (jq, json-diff и т.д.)

### Реализация

```python
import json
from dataclasses import asdict

class JsonReporter(BaseReporter):
    """JSON-reporter для автоматизации."""
    
    def report(self, snapshot: InspectionSnapshot) -> str:
        """Генерирует JSON отчёт."""
        
        # Конвертируем dataclass → dict
        data = self._snapshot_to_dict(snapshot)
        
        # Pretty print
        return json.dumps(data, ensure_ascii=False, indent=2, default=str)
    
    def _snapshot_to_dict(self, snapshot: InspectionSnapshot) -> dict:
        """Конвертирует snapshot в dict."""
        
        data = {
            "file_path": snapshot.file_path,
            "file_content": snapshot.file_content,
            "processing_timestamp": snapshot.processing_timestamp,
            "total_duration_ms": snapshot.total_duration_ms,
        }
        
        # Embedder metadata
        if snapshot.embedder_metadata:
            data["embedder_metadata"] = {
                "provider_type": snapshot.embedder_metadata.provider_type,
                "model_name": snapshot.embedder_metadata.model_name,
                "dimension": snapshot.embedder_metadata.dimension,
                "max_tokens": snapshot.embedder_metadata.max_tokens,
                "device": snapshot.embedder_metadata.device,
                "extra": snapshot.embedder_metadata.extra,
            }
        
        # Chunks
        data["chunks"] = [
            {
                "chunk_id": c.chunk_id,
                "content": c.content,
                "embedding_preview": c.embedding_preview,
                "embedding_dimension": c.embedding_dimension,
                "embedding_hash": c.embedding_hash,
            }
            for c in snapshot.chunks
        ]
        
        # Searches
        data["searches"] = [
            {
                "query": s.query,
                "search_mode": s.search_mode,
                "limit": s.limit,
                "results_count": s.results_count,
                "results": s.results,
            }
            for s in snapshot.searches
        ]
        
        # Steps
        data["steps"] = snapshot.steps
        
        return data
```

### Пример вывода

```json
{
  "file_path": "docs/example.md",
  "file_content": "# Introduction to Python\n\nPython is...",
  "processing_timestamp": "2025-12-10T14:30:15.123456",
  "total_duration_ms": 1234.56,
  "embedder_metadata": {
    "provider_type": "GeminiEmbedder",
    "model_name": null,
    "dimension": 768,
    "max_tokens": 2048,
    "device": null,
    "extra": {"has_api_key": true}
  },
  "chunks": [
    {
      "chunk_id": 1,
      "content": "# Introduction to Python\n\nPython is a high-level programming language...",
      "embedding_preview": [0.123, -0.456, 0.789, ...],
      "embedding_dimension": 768,
      "embedding_hash": "a3f2c1d4"
    }
  ],
  "searches": [],
  "steps": [
    {"step_name": "ingest", "duration_ms": 1234.56}
  ]
}
```

**Использование:**

```bash
# Поиск по JSON
semantic inspect docs/example.md --format json | jq '.chunks[] | select(.chunk_id == 1)'

# Сравнение с json-diff
json-diff snapshot1.json snapshot2.json

# Автоматизация
output=$(semantic inspect docs/example.md --format json)
chunk_count=$(echo "$output" | jq '.chunks | length')
echo "Total chunks: $chunk_count"
```

**Преимущества:**

✅ **Machine-readable** — для скриптов и CI/CD
✅ **Полная информация** — все поля без потерь
✅ **Tooling** — jq, json-diff, REST APIs

---

## 🔍 DiffReporter: Сравнение Конфигураций

### Задачи

1. **Сравнение двух snapshots** (старый vs новый)
2. **Показ различий** в провайдерах, чанках, embeddings
3. **Выявление регрессий** в качестве embeddings

### Реализация

```python
class DiffReporter(BaseReporter):
    """Diff-reporter для сравнения snapshots."""
    
    def compare(
        self,
        old_snapshot: InspectionSnapshot,
        new_snapshot: InspectionSnapshot
    ) -> str:
        """Сравнивает два snapshot."""
        
        lines = []
        
        # Заголовок
        lines.append("# Snapshot Comparison")
        lines.append(f"\n**Old:** {old_snapshot.processing_timestamp}")
        lines.append(f"**New:** {new_snapshot.processing_timestamp}\n")
        
        # Провайдеры
        lines.append("## Provider Changes\n")
        lines.extend(self._diff_providers(old_snapshot, new_snapshot))
        
        # Чанки
        lines.append("\n## Chunks Changes\n")
        lines.extend(self._diff_chunks(old_snapshot, new_snapshot))
        
        # Embeddings
        lines.append("\n## Embedding Changes\n")
        lines.extend(self._diff_embeddings(old_snapshot, new_snapshot))
        
        # Метрики
        lines.append("\n## Performance Changes\n")
        lines.extend(self._diff_metrics(old_snapshot, new_snapshot))
        
        return "\n".join(lines)
    
    def _diff_providers(
        self,
        old: InspectionSnapshot,
        new: InspectionSnapshot
    ) -> List[str]:
        """Сравнивает провайдеры."""
        lines = []
        
        # Embedder
        if old.embedder_metadata and new.embedder_metadata:
            old_meta = old.embedder_metadata
            new_meta = new.embedder_metadata
            
            if old_meta.provider_type != new_meta.provider_type:
                lines.append(f"- **Embedder Type:** `{old_meta.provider_type}` → `{new_meta.provider_type}`")
            
            if old_meta.dimension != new_meta.dimension:
                lines.append(f"- **Dimension:** `{old_meta.dimension}` → `{new_meta.dimension}`")
        
        if not lines:
            lines.append("*No changes in providers*")
        
        return lines
    
    def _diff_chunks(
        self,
        old: InspectionSnapshot,
        new: InspectionSnapshot
    ) -> List[str]:
        """Сравнивает количество и структуру чанков."""
        lines = []
        
        old_count = len(old.chunks)
        new_count = len(new.chunks)
        
        if old_count != new_count:
            lines.append(f"- **Chunk Count:** {old_count} → {new_count} ({new_count - old_count:+d})")
        else:
            lines.append(f"- **Chunk Count:** {new_count} (unchanged)")
        
        # Сравниваем content hash чанков
        old_content_hashes = {c.chunk_id: hashlib.md5(c.content.encode()).hexdigest()[:8] for c in old.chunks}
        new_content_hashes = {c.chunk_id: hashlib.md5(c.content.encode()).hexdigest()[:8] for c in new.chunks}
        
        changed_content = []
        for chunk_id in set(old_content_hashes.keys()) & set(new_content_hashes.keys()):
            if old_content_hashes[chunk_id] != new_content_hashes[chunk_id]:
                changed_content.append(chunk_id)
        
        if changed_content:
            lines.append(f"- **Content Changed:** {len(changed_content)} chunks ({', '.join(map(str, changed_content[:5]))})")
        
        return lines
    
    def _diff_embeddings(
        self,
        old: InspectionSnapshot,
        new: InspectionSnapshot
    ) -> List[str]:
        """Сравнивает embeddings."""
        lines = []
        
        # Сравниваем по embedding_hash
        old_hashes = {c.chunk_id: c.embedding_hash for c in old.chunks}
        new_hashes = {c.chunk_id: c.embedding_hash for c in new.chunks}
        
        changed_embeddings = []
        for chunk_id in set(old_hashes.keys()) & set(new_hashes.keys()):
            if old_hashes[chunk_id] != new_hashes[chunk_id]:
                changed_embeddings.append(chunk_id)
        
        if changed_embeddings:
            lines.append(f"- **Embeddings Changed:** {len(changed_embeddings)} chunks")
            lines.append(f"  - Chunk IDs: {', '.join(map(str, changed_embeddings[:10]))}")
            
            if len(changed_embeddings) > 10:
                lines.append(f"  - ... and {len(changed_embeddings) - 10} more")
        else:
            lines.append("- **Embeddings:** No changes")
        
        return lines
    
    def _diff_metrics(
        self,
        old: InspectionSnapshot,
        new: InspectionSnapshot
    ) -> List[str]:
        """Сравнивает метрики производительности."""
        lines = []
        
        old_duration = old.total_duration_ms
        new_duration = new.total_duration_ms
        delta = new_duration - old_duration
        percent = (delta / old_duration) * 100 if old_duration > 0 else 0
        
        lines.append(f"- **Total Duration:** {old_duration:.2f}ms → {new_duration:.2f}ms ({delta:+.2f}ms, {percent:+.1f}%)")
        
        return lines
    
    def report(self, snapshot: InspectionSnapshot) -> str:
        """DiffReporter требует два snapshot, используйте compare()."""
        raise NotImplementedError("DiffReporter.report() не поддерживается. Используйте compare()")
```

### Пример вывода

```markdown
# Snapshot Comparison

**Old:** 2025-12-09T10:30:00.000000
**New:** 2025-12-10T14:30:15.123456

## Provider Changes

- **Embedder Type:** `GeminiEmbedder` → `MLXEmbedder`
- **Dimension:** `768` → `384`

## Chunks Changes

- **Chunk Count:** 5 (unchanged)
- **Content Changed:** 0 chunks

## Embedding Changes

- **Embeddings Changed:** 5 chunks
  - Chunk IDs: 1, 2, 3, 4, 5

## Performance Changes

- **Total Duration:** 1234.56ms → 890.23ms (-344.33ms, -27.9%)
```

**Интерпретация:**

1. **Provider Changes:** Сменили Gemini на MLX → dimension уменьшилась
2. **Content:** Контент не изменился → чанки идентичны
3. **Embeddings:** Все embeddings изменились → новый провайдер дал другие векторы
4. **Performance:** Скорость выросла на 28% → MLX быстрее на локальном железе

**Использование:**

```python
from semantic_core.core.observatory import DiffReporter

# Загружаем старый и новый snapshots
old_snapshot = manager.load_snapshot(Path("snapshots/old/example_md.json"))
new_snapshot = inspector.ingest_with_inspection("docs/example.md")

# Сравниваем
diff_reporter = DiffReporter()
diff_report = diff_reporter.compare(old_snapshot, new_snapshot)

print(diff_report)
```

---

## 🎯 Использование

### Выбор формата

```python
from semantic_core.core.observatory import (
    ProviderInspector,
    ConsoleReporter,
    MarkdownReporter,
    JsonReporter,
)

# Инспекция
inspector = ProviderInspector(core=core)
snapshot = inspector.ingest_with_inspection("docs/example.md")

# 1. Console (для быстрого просмотра)
console_reporter = ConsoleReporter()
console_reporter.report(snapshot)

# 2. Markdown (для документации)
md_reporter = MarkdownReporter()
md_output = md_reporter.report(snapshot)
Path("report.md").write_text(md_output)

# 3. JSON (для автоматизации)
json_reporter = JsonReporter()
json_output = json_reporter.report(snapshot)
Path("snapshot.json").write_text(json_output)
```

### CLI интеграция

```bash
# Console output (по умолчанию)
semantic inspect docs/example.md

# Markdown report
semantic inspect docs/example.md --format markdown > report.md

# JSON output
semantic inspect docs/example.md --format json > snapshot.json

# Diff comparison
semantic compare snapshots/old.json snapshots/new.json
```

---

## 📊 Таблица Reporters

| Reporter | Формат | Для кого | Применение |
|----------|--------|----------|-----------|
| **ConsoleReporter** | Rich UI | Разработчик | Быстрый просмотр в терминале |
| **MarkdownReporter** | Markdown | Документация | GitHub Issues, PR, отчёты |
| **JsonReporter** | JSON | Автоматизация | CI/CD, скрипты, REST APIs |
| **DiffReporter** | Markdown Diff | QA, DevOps | Сравнение конфигураций, регрессии |

---

## 🔗 Связанные материалы

- [README.md](README.md) — обзор Phase 16
- [02_inspector_core.md](02_inspector_core.md) — ProviderInspector и SnapshotManager
- [04_cli_inspect.md](04_cli_inspect.md) — CLI команда `semantic inspect`

---

**← [Назад к Phase 16](README.md)**
