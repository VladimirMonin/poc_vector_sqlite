---
title: "MCP Server"
description: "SemanticCore как Model Context Protocol сервер для AI-агентов"
tags: ["extending", "mcp", "tools", "integration", "ai-agents"]
difficulty: "advanced"
prerequisites: ["../../concepts/08_rag_architecture"]
---

# MCP Server 🔌

> Превратите SemanticCore в MCP сервер для Claude, Cursor и других AI-агентов.

---

## Что такое MCP? 🎯

**Model Context Protocol** — стандарт для подключения инструментов к LLM.

```
┌─────────────────────────────────────────────┐
│           AI Agent (Claude, Cursor)         │
│                     │                        │
│                     ▼                        │
│              MCP Protocol                    │
│                     │                        │
│                     ▼                        │
│            ┌───────────────┐                │
│            │  MCP Server   │                │
│            │ (ваш сервер)  │                │
│            └───────┬───────┘                │
│                    │                         │
│                    ▼                         │
│            ┌───────────────┐                │
│            │ SemanticCore  │                │
│            └───────────────┘                │
└─────────────────────────────────────────────┘
```

---

## Три основных инструмента 🛠️

| Tool | Описание |
|------|----------|
| `semantic_search` | Поиск по базе знаний |
| `semantic_ingest` | Индексация документов |
| `semantic_ask` | RAG-запрос с генерацией |

---

## Пример: FastMCP сервер 📝

```python
# mcp_server.py
from fastmcp import FastMCP
from semantic_core import SemanticCore
from semantic_core.core.rag import RAGEngine

# Инициализация
core = SemanticCore.from_config()
mcp = FastMCP("Semantic Core MCP")

@mcp.tool()
def semantic_search(
    query: str,
    limit: int = 5,
    mode: str = "hybrid",
) -> list[dict]:
    """Поиск по семантической базе знаний.
    
    Args:
        query: Поисковый запрос
        limit: Количество результатов (1-20)
        mode: Режим поиска (vector/fts/hybrid)
    
    Returns:
        Список найденных документов с score
    """
    results = core.search(query, limit=limit, mode=mode)
    return [
        {
            "title": r.document.metadata.get("title", "Untitled"),
            "content": r.document.content[:500],
            "score": r.score,
        }
        for r in results
    ]

@mcp.tool()
def semantic_ingest(
    path: str,
    recursive: bool = False,
) -> dict:
    """Индексация файлов в базу знаний.
    
    Args:
        path: Путь к файлу или директории
        recursive: Рекурсивная обработка папок
    
    Returns:
        Статистика индексации
    """
    from pathlib import Path
    
    p = Path(path)
    if p.is_file():
        core.ingest_file(p)
        return {"files": 1, "status": "success"}
    elif p.is_dir():
        count = 0
        pattern = "**/*" if recursive else "*"
        for f in p.glob(pattern):
            if f.is_file() and f.suffix in [".md", ".txt"]:
                core.ingest_file(f)
                count += 1
        return {"files": count, "status": "success"}
    
    return {"error": "Path not found"}

@mcp.tool()
def semantic_ask(
    question: str,
    context_chunks: int = 5,
) -> dict:
    """RAG-запрос: поиск + генерация ответа.
    
    Args:
        question: Вопрос к базе знаний
        context_chunks: Количество чанков контекста
    
    Returns:
        Ответ с источниками
    """
    from semantic_core.infrastructure.llm import GeminiLLMProvider
    
    llm = GeminiLLMProvider(api_key=core.config.gemini_api_key)
    rag = RAGEngine(core=core, llm=llm, context_chunks=context_chunks)
    
    result = rag.ask(question)
    return {
        "answer": result.answer,
        "sources": [
            {"title": s.parent_doc_title, "score": s.score}
            for s in result.sources[:3]
        ],
    }

if __name__ == "__main__":
    mcp.run()
```

---

## Запуск сервера 🚀

```bash
# Установка FastMCP
pip install fastmcp

# Запуск
python mcp_server.py
```

---

## Конфигурация Claude Desktop 🖥️

```json
// claude_desktop_config.json
{
  "mcpServers": {
    "semantic-core": {
      "command": "python",
      "args": ["/path/to/mcp_server.py"],
      "env": {
        "GEMINI_API_KEY": "your-key"
      }
    }
  }
}
```

---

## Tool Definitions (JSON Schema) 📋

```json
{
  "name": "semantic_search",
  "description": "Search semantic knowledge base",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Search query"
      },
      "limit": {
        "type": "integer",
        "default": 5,
        "minimum": 1,
        "maximum": 20
      },
      "mode": {
        "type": "string",
        "enum": ["vector", "fts", "hybrid"],
        "default": "hybrid"
      }
    },
    "required": ["query"]
  }
}
```

---

## Security ⚠️

| Риск | Решение |
|------|---------|
| Path traversal | Валидируйте пути, ограничьте директории |
| API key exposure | Передавайте через env, не в коде |
| Prompt injection | Не доверяйте user input как системным |

```python
# Валидация пути
from pathlib import Path

ALLOWED_DIRS = [Path("./docs"), Path("./data")]

def validate_path(path: str) -> Path:
    p = Path(path).resolve()
    if not any(p.is_relative_to(d) for d in ALLOWED_DIRS):
        raise ValueError("Path outside allowed directories")
    return p
```

---

## Клиенты MCP 🤝

| Клиент | Поддержка |
|--------|-----------|
| Claude Desktop | ✅ Нативная |
| Cursor | ✅ Через настройки |
| VS Code + Copilot | ✅ MCP extension |
| Custom | Используйте mcp SDK |

---

## Следующие шаги 🔗

| Ресурс | Что узнаете |
|--------|-------------|
| [RAG Architecture](../../concepts/08_rag_architecture.md) | Как работает RAG |
| [FastMCP Docs](https://github.com/jlowin/fastmcp) | Документация FastMCP |
