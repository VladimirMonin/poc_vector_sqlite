"""Слой интеграции с ORM.

Классы:
    SemanticIndex
        Дескриптор для добавления семантического поиска к ORM моделям.
    DocumentBuilder
        Строитель документов из ORM инстансов.
    SearchProxy
        Прокси-объект для выполнения поисковых запросов.
"""

from semantic_core.integrations.base import SemanticIndex, DocumentBuilder
from semantic_core.integrations.search_proxy import SearchProxy

__all__ = [
    "SemanticIndex",
    "DocumentBuilder",
    "SearchProxy",
]
