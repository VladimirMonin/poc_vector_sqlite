"""Примеры использования OpenAI LLM провайдера.

Демонстрирует работу с OpenAI API для RAG системы.
"""

from semantic_core.infrastructure.openai import OpenAILLMProvider


def example_basic():
    """Базовое использование OpenAI LLM."""
    print("=" * 60)
    print("Example 1: Базовая генерация")
    print("=" * 60)

    provider = OpenAILLMProvider(
        api_key="sk-...",  # Ваш API ключ
        model="gpt-4o-mini",
    )

    result = provider.generate(
        prompt="Что такое RAG в контексте AI?",
        temperature=0.7,
        max_tokens=200,
    )

    print(f"Model: {result.model}")
    print(f"Response: {result.text}")
    print(f"Tokens: {result.input_tokens} in, {result.output_tokens} out")
    print()


def example_with_system_prompt():
    """Использование системного промпта."""
    print("=" * 60)
    print("Example 2: С системным промптом")
    print("=" * 60)

    provider = OpenAILLMProvider(
        api_key="sk-...",
        model="gpt-4o-mini",
    )

    result = provider.generate(
        prompt="Объясни разницу между Vector Search и Full-Text Search",
        system_prompt="Ты эксперт по поисковым системам. Отвечай кратко и технично.",
        temperature=0.3,
    )

    print(f"Response: {result.text}")
    print()


def example_streaming():
    """Использование streaming генерации."""
    print("=" * 60)
    print("Example 3: Streaming генерация")
    print("=" * 60)

    provider = OpenAILLMProvider(
        api_key="sk-...",
        model="gpt-4o-mini",
    )

    print("Question: Напиши короткую функцию на Python для поиска")
    print("\nStreaming response:")
    print("-" * 40)

    for chunk in provider.generate_stream(
        prompt="Напиши короткую функцию на Python для поиска в списке",
        temperature=0.2,
    ):
        print(chunk, end="", flush=True)

    print("\n")


def example_with_history():
    """Использование с историей чата."""
    print("=" * 60)
    print("Example 4: Чат с историей")
    print("=" * 60)

    provider = OpenAILLMProvider(
        api_key="sk-...",
        model="gpt-4o-mini",
    )

    # История предыдущих сообщений
    history = [
        {"role": "user", "content": "Привет! Меня зовут Алиса."},
        {"role": "assistant", "content": "Привет, Алиса! Чем могу помочь?"},
        {"role": "user", "content": "Расскажи про SQLite."},
        {
            "role": "assistant",
            "content": "SQLite - это легковесная встраиваемая СУБД...",
        },
    ]

    # Новый вопрос с контекстом
    result = provider.generate(
        prompt="А как мне вспомнить моё имя?",
        history=history,
    )

    print(f"Response: {result.text}")
    # Должен вспомнить: "Твоё имя - Алиса!"
    print()


def example_with_rag():
    """Интеграция с RAGEngine."""
    print("=" * 60)
    print("Example 5: Использование с RAGEngine")
    print("=" * 60)

    from semantic_core import SemanticCore
    from semantic_core.core.rag import RAGEngine

    # Создаём SemanticCore
    core = SemanticCore(db_path="semantic.db", api_key="your-gemini-key")

    # Создаём OpenAI LLM провайдер
    llm = OpenAILLMProvider(
        api_key="sk-...",
        model="gpt-4o-mini",
        temperature=0.7,
    )

    # Создаём RAG Engine
    rag = RAGEngine(
        semantic_core=core,
        llm_provider=llm,  # Используем OpenAI вместо Gemini
        context_strategy="hierarchical",
    )

    # Задаём вопрос
    result = rag.ask(
        question="Что такое векторный поиск?",
        top_k=5,
    )

    print(f"Answer: {result.answer}")
    print(f"Sources: {len(result.sources)} документов")
    print()


def example_token_counting():
    """Подсчёт токенов через tiktoken."""
    print("=" * 60)
    print("Example 6: Подсчёт токенов")
    print("=" * 60)

    provider = OpenAILLMProvider(
        api_key="sk-...",
        model="gpt-4o-mini",
    )

    texts = [
        "Hello, world!",
        "Что такое векторный поиск?",
        "This is a longer text with multiple sentences. It contains more tokens.",
    ]

    for text in texts:
        tokens = provider.count_tokens(text)
        print(f"Text: {text[:50]}...")
        print(f"Tokens: {tokens}")
        print()


def example_different_models():
    """Сравнение разных моделей OpenAI."""
    print("=" * 60)
    print("Example 7: Разные модели OpenAI")
    print("=" * 60)

    prompt = "Напиши функцию факториала на Python"

    models = {
        "gpt-4o": "Самое высокое качество",
        "gpt-4o-mini": "Баланс цена/качество",
        "gpt-3.5-turbo": "Быстро и дёшево",
    }

    for model, description in models.items():
        print(f"\n{model} ({description}):")
        print("-" * 40)

        provider = OpenAILLMProvider(
            api_key="sk-...",
            model=model,
            temperature=0.2,
        )

        result = provider.generate(prompt, max_tokens=150)
        print(result.text[:200] + "...")
        print(
            f"Tokens: {result.input_tokens or 'N/A'} in, "
            f"{result.output_tokens or 'N/A'} out"
        )


def example_error_handling():
    """Обработка ошибок API."""
    print("=" * 60)
    print("Example 8: Обработка ошибок")
    print("=" * 60)

    provider = OpenAILLMProvider(
        api_key="sk-...",
        model="gpt-4o-mini",
        timeout=10.0,  # 10 секунд timeout
        max_retries=2,  # 2 попытки при ошибках
    )

    try:
        result = provider.generate("Test prompt")
        print(f"Success: {result.text}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    # Раскомментируйте нужные примеры

    # example_basic()
    # example_with_system_prompt()
    # example_streaming()
    # example_with_history()
    # example_with_rag()
    # example_token_counting()
    # example_different_models()
    # example_error_handling()

    print("Примеры готовы к запуску!")
    print("Раскомментируйте нужные функции в __main__ блоке.")
    print("\nДля работы требуется:")
    print("1. pip install openai tiktoken")
    print("2. Установить OPENAI_API_KEY или передать api_key явно")
