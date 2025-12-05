# Руководство по Python для начинающих

Добро пожаловать в мир Python! Этот документ поможет вам освоить основы программирования.

## Глава 1: Основы синтаксиса

Python известен своей читаемостью и простотой. Давайте начнём с базовых концепций.

### 1.1 Переменные и типы данных

В Python не нужно объявлять тип переменной — он определяется автоматически.

```python
# Примеры переменных
name = "Alice"        # строка
age = 25             # целое число
height = 1.65        # число с плавающей точкой
is_student = True    # логическое значение
```

#### 1.1.1 Строки и их методы

Строки в Python неизменяемы. Основные методы:

```python
text = "Hello, World!"
print(text.lower())      # hello, world!
print(text.upper())      # HELLO, WORLD!
print(text.split(", "))  # ['Hello', 'World!']
```

#### 1.1.2 Числа и операции

Python поддерживает все стандартные математические операции:

```python
a = 10
b = 3
print(a + b)   # 13 - сложение
print(a - b)   # 7 - вычитание
print(a * b)   # 30 - умножение
print(a / b)   # 3.333... - деление
print(a // b)  # 3 - целочисленное деление
print(a % b)   # 1 - остаток
print(a ** b)  # 1000 - возведение в степень
```

### 1.2 Управляющие конструкции

#### 1.2.1 Условные операторы

```python
age = 18

if age >= 18:
    print("Вы совершеннолетний")
elif age >= 14:
    print("Вы подросток")
else:
    print("Вы ребёнок")
```

#### 1.2.2 Циклы

##### For цикл

```python
fruits = ["яблоко", "банан", "апельсин"]
for fruit in fruits:
    print(f"Я люблю {fruit}")
```

##### While цикл

```python
count = 0
while count < 5:
    print(count)
    count += 1
```

## Глава 2: Функции

Функции позволяют организовать код в переиспользуемые блоки.

### 2.1 Определение функций

```python
def greet(name, greeting="Привет"):
    """Приветствует пользователя.
    
    Args:
        name: Имя пользователя
        greeting: Текст приветствия
    
    Returns:
        Строка с приветствием
    """
    return f"{greeting}, {name}!"
```

### 2.2 Lambda-функции

Анонимные функции для простых операций:

```python
square = lambda x: x ** 2
numbers = [1, 2, 3, 4, 5]
squared = list(map(square, numbers))
# [1, 4, 9, 16, 25]
```

## Глава 3: Классы и ООП

### 3.1 Создание класса

```python
class Dog:
    """Класс, представляющий собаку."""
    
    def __init__(self, name: str, age: int):
        self.name = name
        self.age = age
    
    def bark(self) -> str:
        return f"{self.name} говорит: Гав!"
    
    def birthday(self) -> None:
        self.age += 1
```

### 3.2 Наследование

```python
class GoldenRetriever(Dog):
    """Золотистый ретривер — дружелюбная порода."""
    
    def __init__(self, name: str, age: int):
        super().__init__(name, age)
        self.breed = "Golden Retriever"
    
    def fetch(self, item: str) -> str:
        return f"{self.name} принёс {item}!"
```

## Заключение

Теперь вы знаете основы Python! Практикуйтесь каждый день.
