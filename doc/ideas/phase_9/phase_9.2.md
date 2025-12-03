# Phase 9.2: Context Compression

**Статус:** 🔲 Планируется  
**Зависимости:** Phase 9.1 ✅  
**Оценка:** ~0.5 дня

---

## 🎯 Цель

Автоматическое сжатие истории через summarization.

---

## 💡 Идея

Когда история достигает порога → вызываем LLM:
> "Сожми следующую историю чата в 2-3 параграфа, сохрани ключевые факты"

Сжатая summary заменяет старые сообщения.

---

## 📦 Структура

```
semantic_core/core/context/
├── strategies.py             # + AdaptiveWithCompression
└── compressor.py             # ContextCompressor
```

---

## 📐 ContextCompressor

```python
# semantic_core/core/context/compressor.py

class ContextCompressor:
    """Сжимает историю через LLM."""
    
    COMPRESS_PROMPT = """Summarize this conversation in 2-3 paragraphs.
Keep key facts, decisions, and context. Be concise.

CONVERSATION:
{history}

SUMMARY:"""
    
    def __init__(self, llm: BaseLLMProvider):
        self.llm = llm
    
    def compress(self, messages: list[Message]) -> Message:
        history_text = "\n".join(
            f"{m.role.upper()}: {m.content}" for m in messages
        )
        
        result = self.llm.generate(
            prompt=self.COMPRESS_PROMPT.format(history=history_text),
            temperature=0.3,  # более детерминированно
        )
        
        return Message(
            role="system",
            content=f"[Previous conversation summary]\n{result.text}",
            tokens=result.output_tokens or 0,
        )
```

---

## 📐 AdaptiveWithCompression

```python
# semantic_core/core/context/strategies.py

class AdaptiveWithCompression(BaseContextStrategy):
    """Сжимает когда достигнут порог."""
    
    def __init__(
        self,
        compressor: ContextCompressor,
        threshold_tokens: int = 30000,
        target_tokens: int = 10000,
    ):
        self.compressor = compressor
        self.threshold = threshold_tokens
        self.target = target_tokens
        self.summary: Optional[Message] = None
    
    def should_trim(self, messages):
        total = sum(m.tokens for m in messages)
        if self.summary:
            total += self.summary.tokens
        return total > self.threshold
    
    def trim(self, messages):
        # Сжимаем старые сообщения
        to_compress = []
        to_keep = []
        running_tokens = 0
        
        for msg in reversed(messages):
            if running_tokens < self.target:
                to_keep.insert(0, msg)
                running_tokens += msg.tokens
            else:
                to_compress.insert(0, msg)
        
        if to_compress:
            # Добавляем старую summary если есть
            if self.summary:
                to_compress.insert(0, self.summary)
            
            self.summary = self.compressor.compress(to_compress)
        
        return to_keep
    
    def get_full_context(self, messages: list[Message]) -> list[Message]:
        """Возвращает контекст с summary."""
        if self.summary:
            return [self.summary] + messages
        return messages
```

---

## 📐 CLI опции

```python
@chat_cmd.callback()
def chat(
    # ... existing ...
    compress_at: int = Option(None, "--compress-at", help="Auto-compress at N tokens"),
    no_compress: bool = Option(False, "--no-compress"),
):
    if compress_at and not no_compress:
        compressor = ContextCompressor(llm)
        strategy = AdaptiveWithCompression(compressor, threshold_tokens=compress_at)
    # ...
```

---

## 🔧 Slash команды

| Команда | Действие |
|---------|----------|
| `/compress` | Принудительное сжатие сейчас |
| `/tokens` | Показать использование токенов |

```
You: /tokens

📊 Token Usage:
  History: 12,450 tokens (8 messages)
  Summary: 850 tokens
  Total: 13,300 / 50,000 limit
```

---

## ✅ Acceptance Criteria

- [ ] `ContextCompressor` работает
- [ ] `AdaptiveWithCompression` автоматически сжимает
- [ ] Summary сохраняется между сжатиями
- [ ] `/compress` команда
- [ ] `/tokens` показывает статистику

---

## ⏱️ Оценка

| Задача | Часы |
|--------|------|
| compressor.py | 1.5 |
| AdaptiveWithCompression | 1.5 |
| CLI интеграция | 1 |
| /compress, /tokens | 0.5 |
| Тесты | 1.5 |
| **Итого** | **~6 часов** |
