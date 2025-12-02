# H1 Top Level

Обычный текст под первым заголовком.

## H2 Second Level

Текст под вторым заголовком.

```python
# Это комментарий с # H1 внутри кода
print("Code inside H2")
def function():
    # Another # H2 comment
    pass
```

### H3 Third Level

Список с кодом внутри:

1. Первый пункт списка

   ```bash
   echo "Code inside list"
   # Comment with ## H2 inside bash
   ```

2. Второй пункт списка

   Текст внутри пункта.

<!-- HTML комментарий -->

#### H4 Deep Level

> Цитата с кодом:
>
> ```javascript
> console.log("Code in blockquote");
> ```

Текст после цитаты.

```
Блок кода без языка
Should be detected as code
```

### H3 Another Third Level

Резкая смена уровней: H1 -> H4 раньше, теперь обратно H3.

```python
# Большой блок кода для тестирования нарезки
def long_function():
    result = []
    for i in range(100):
        result.append(i * 2)
    return result

class MyClass:
    def __init__(self):
        self.data = []
    
    def process(self, items):
        for item in items:
            self.data.append(item)
    
    def get_data(self):
        return self.data
```

## H2 Final Section

Финальный текст с несколькими параграфами.

Второй параграф.

Третий параграф для проверки группировки.
