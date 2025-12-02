"""Доменный слой управления аутентификацией и API-ключами.

Классы:
    GoogleKeyring
        Контейнер для API-ключей Google с разделением биллинга.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class GoogleKeyring:
    """Контейнер для API-ключей Google Gemini.
    
    Разделяет потоки биллинга для защиты основного приложения
    от исчерпания лимитов при массовых операциях.
    
    Attributes:
        default_key: Основной API-ключ для синхронных операций.
        batch_key: Опциональный ключ для батч-обработки (со скидкой 50%).
            Если None, батч-операции будут недоступны.
    
    Raises:
        ValueError: При попытке использовать батч без выделенного ключа.
    
    Examples:
        >>> # Только синхронный режим
        >>> keys = GoogleKeyring(default_key="FREE_TIER_KEY")
        
        >>> # Полная конфигурация с батчингом
        >>> keys = GoogleKeyring(
        ...     default_key="MAIN_APP_KEY",
        ...     batch_key="PAID_BATCH_KEY"
        ... )
    """
    
    default_key: str
    batch_key: Optional[str] = None
    
    def get_batch_key(self) -> str:
        """Получить ключ для батч-операций.
        
        Returns:
            API-ключ для батчинга.
            
        Raises:
            ValueError: Если batch_key не установлен.
        """
        if self.batch_key is None:
            raise ValueError(
                "Batch operations require a dedicated API key. "
                "Please set 'batch_key' in GoogleKeyring configuration."
            )
        return self.batch_key
    
    def has_batch_support(self) -> bool:
        """Проверить доступность батч-режима.
        
        Returns:
            True, если batch_key настроен.
        """
        return self.batch_key is not None
