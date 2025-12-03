"""RAG Engine для Retrieval-Augmented Generation.

Классы:
    RAGResult
        DTO с результатом RAG-запроса.
    RAGEngine
        Движок для RAG: поиск контекста + генерация ответа.
"""

from dataclasses import dataclass, field
from typing import Optional, Literal, Union, TYPE_CHECKING

from semantic_core.interfaces.llm import BaseLLMProvider, GenerationResult
from semantic_core.domain import SearchResult, ChunkResult
from semantic_core.utils.logger import get_logger

if TYPE_CHECKING:
    from semantic_core.pipeline import SemanticCore

logger = get_logger(__name__)

SearchMode = Literal["vector", "fts", "hybrid"]


@dataclass
class RAGResult:
    """Результат RAG-запроса.

    Attributes:
        answer: Сгенерированный ответ.
        sources: Найденные чанки (по умолчанию) или документы (full_docs).
        generation: Метаданные генерации (токены, модель).
        query: Исходный запрос пользователя.
        full_docs: Использовались ли полные документы вместо чанков.
    """

    answer: str
    sources: Union[list[ChunkResult], list[SearchResult]]
    generation: GenerationResult
    query: str = ""
    full_docs: bool = False

    @property
    def has_sources(self) -> bool:
        """Были ли найдены релевантные источники."""
        return len(self.sources) > 0

    @property
    def total_tokens(self) -> Optional[int]:
        """Общее количество токенов."""
        return self.generation.total_tokens


class RAGEngine:
    """Движок для Retrieval-Augmented Generation.

    Объединяет семантический поиск и генерацию LLM:
    1. Находит релевантные документы по запросу.
    2. Формирует контекст из найденных чанков.
    3. Генерирует ответ на основе контекста.

    Attributes:
        core: SemanticCore для поиска.
        llm: Провайдер LLM для генерации.
        context_chunks: Количество чанков для контекста.
        system_prompt: Системный промпт по умолчанию.

    Example:
        >>> rag = RAGEngine(core=core, llm=provider, context_chunks=5)
        >>> result = rag.ask("Что такое гибридный поиск?")
        >>> print(result.answer)
    """

    DEFAULT_SYSTEM_PROMPT = """You are a helpful assistant that answers questions based on the provided context.

IMPORTANT RULES:
1. Answer ONLY based on the provided CONTEXT below.
2. If the context doesn't contain relevant information, say: "I don't have enough information in the provided context to answer this question."
3. Be concise and accurate.
4. Format your response in Markdown when appropriate.
5. If quoting from context, use proper citations.

CONTEXT:
{context}"""

    def __init__(
        self,
        core: "SemanticCore",
        llm: BaseLLMProvider,
        context_chunks: int = 5,
        system_prompt: Optional[str] = None,
    ):
        """Инициализация RAG Engine.

        Args:
            core: SemanticCore для семантического поиска.
            llm: Провайдер LLM для генерации ответов.
            context_chunks: Количество чанков для контекста (по умолчанию 5).
            system_prompt: Кастомный системный промпт (опционально).
        """
        self.core = core
        self.llm = llm
        self.context_chunks = context_chunks
        self._custom_system_prompt = system_prompt

        logger.debug(
            "RAGEngine initialized",
            llm_model=llm.model_name,
            context_chunks=context_chunks,
        )

    def ask(
        self,
        query: str,
        search_mode: SearchMode = "hybrid",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        full_docs: bool = False,
    ) -> RAGResult:
        """Выполняет RAG-запрос: поиск + генерация.

        Args:
            query: Вопрос пользователя.
            search_mode: Режим поиска (vector/fts/hybrid).
            temperature: Температура генерации LLM.
            max_tokens: Ограничение токенов ответа.
            full_docs: Использовать полные документы вместо чанков.
                       По умолчанию False — используются гранулярные чанки.

        Returns:
            RAGResult с ответом и источниками.

        Raises:
            ValueError: Если query пустой.
            RuntimeError: Если LLM вернул ошибку.
        """
        if not query or not query.strip():
            raise ValueError("Запрос не может быть пустым")

        logger.info(
            "RAG query started",
            query_length=len(query),
            search_mode=search_mode,
            context_chunks=self.context_chunks,
            full_docs=full_docs,
        )

        # 1. Retrieval — поиск релевантных источников
        if full_docs:
            # Режим полных документов (старое поведение)
            sources = self.core.search(
                query=query,
                limit=self.context_chunks,
                mode=search_mode,
            )
            context = self._build_full_docs_context(sources)
        else:
            # Режим гранулярных чанков (по умолчанию)
            sources = self.core.search_chunks(
                query=query,
                limit=self.context_chunks,
                mode=search_mode,
            )
            context = self._build_chunks_context(sources)

        logger.debug(
            "Retrieval completed",
            found_sources=len(sources),
            mode="full_docs" if full_docs else "chunks",
        )

        # 2. Generation — генерируем ответ
        system_prompt = self._format_system_prompt(context)

        generation = self.llm.generate(
            prompt=query,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        result = RAGResult(
            answer=generation.text,
            sources=sources,
            generation=generation,
            query=query,
            full_docs=full_docs,
        )

        logger.info(
            "RAG query completed",
            sources_count=len(sources),
            answer_length=len(generation.text),
            total_tokens=result.total_tokens,
        )

        return result

    def _build_chunks_context(self, sources: list[ChunkResult]) -> str:
        """Формирует контекст из найденных чанков.

        Args:
            sources: Найденные чанки.

        Returns:
            Отформатированный текст контекста.
        """
        if not sources:
            return "No relevant context found."

        context_parts = []

        for i, source in enumerate(sources, 1):
            # Заголовок источника — берём из parent_doc_title
            source_label = source.parent_doc_title or f"Doc#{source.parent_doc_id}"
            if len(source_label) > 50:
                source_label = "..." + source_label[-47:]

            # Добавляем информацию о типе чанка
            chunk_info = f"[{source.chunk_type.value}]"
            if source.language:
                chunk_info += f" ({source.language})"

            # Контент чанка
            content = source.content
            # Ограничиваем длину контента для контекста
            if len(content) > 2000:
                content = content[:2000] + "..."

            # Форматируем блок
            block = f"[{i}] {source_label} {chunk_info} (score: {source.score:.3f})\n{content}"
            context_parts.append(block)

        return "\n\n---\n\n".join(context_parts)

    def _build_full_docs_context(self, sources: list[SearchResult]) -> str:
        """Формирует контекст из полных документов.

        Args:
            sources: Найденные документы.

        Returns:
            Отформатированный текст контекста.
        """
        if not sources:
            return "No relevant context found."

        context_parts = []

        for i, source in enumerate(sources, 1):
            # Заголовок источника
            source_label = source.document.metadata.get("source", f"Source {i}")
            if len(source_label) > 50:
                source_label = "..." + source_label[-47:]

            # Контент документа (может быть длинным)
            content = source.document.content
            # Ограничиваем длину контента для контекста
            if len(content) > 2000:
                content = content[:2000] + "..."

            # Форматируем блок
            block = f"[{i}] {source_label} (score: {source.score:.3f})\n{content}"
            context_parts.append(block)

        return "\n\n---\n\n".join(context_parts)

    def _format_system_prompt(self, context: str) -> str:
        """Форматирует системный промпт с контекстом.

        Args:
            context: Отформатированный контекст.

        Returns:
            Финальный системный промпт.
        """
        if self._custom_system_prompt:
            # Кастомный промпт может содержать {context}
            if "{context}" in self._custom_system_prompt:
                return self._custom_system_prompt.format(context=context)
            # Или добавляем контекст в конец
            return f"{self._custom_system_prompt}\n\nCONTEXT:\n{context}"

        return self.DEFAULT_SYSTEM_PROMPT.format(context=context)


__all__ = ["RAGResult", "RAGEngine"]
