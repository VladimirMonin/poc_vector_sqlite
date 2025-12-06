"""TimecodeParser — извлечение и валидация таймкодов из transcription.

Этот модуль содержит утилиту для парсинга таймкодов формата [MM:SS] и [HH:MM:SS]
из текста транскрипций, с валидацией по длительности файла и обработкой edge cases.

Архитектурный контекст:
-----------------------
- Phase 14.1.2: Advanced Features — таймкоды для транскрипций
- Используется в TranscriptionStep для обогащения metadata
- Поддерживает наследование таймкодов для чанков без явного маркера

Пример использования:
--------------------
>>> parser = TimecodeParser(max_duration_seconds=3600)  # 1 час
>>> 
>>> # Парсинг одного таймкода
>>> info = parser.parse("[12:30] Speaker talks about Python")
>>> print(info.seconds)  # 750
>>> print(info.original)  # "[12:30]"
>>> 
>>> # Парсинг всех таймкодов из текста
>>> text = '''
... [00:00] Introduction
... [05:30] Chapter 1
... [15:45] Chapter 2
... '''
>>> timecodes = parser.parse_all(text)
>>> print(len(timecodes))  # 3
>>> 
>>> # Наследование таймкода для чанка без маркера
>>> inherited = parser.inherit_timecode(
...     last_timecode_seconds=300,  # Последний известный таймкод (5:00)
...     chunk_position=3,
...     total_chunks=10,
...     total_duration_seconds=3600,
... )
>>> print(inherited)  # ~660 (300 + delta)
"""

import re
from dataclasses import dataclass
from typing import Optional

from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TimecodeInfo:
    """Результат парсинга одного таймкода.
    
    Attributes:
        original: Исходная строка (например, "[12:30]")
        seconds: Количество секунд от начала файла
        minutes: Минуты компонент таймкода
        secs: Секунды компонент таймкода
        hours: Часы компонент (если есть, иначе 0)
    """
    
    original: str
    seconds: int
    minutes: int
    secs: int
    hours: int = 0


class TimecodeParser:
    """Парсер таймкодов из текста с валидацией и наследованием.
    
    Поддерживаемые форматы:
    - [MM:SS] — минуты:секунды (основной)
    - [HH:MM:SS] — часы:минуты:секунды (для длинных файлов)
    
    Валидация:
    - Таймкод не может превышать max_duration_seconds
    - Опциональная проверка строгого порядка (ascending)
    
    Attributes:
        max_duration_seconds: Максимальная длительность файла (None = без валидации)
        strict_ordering: Проверять ли строгое возрастание таймкодов
    """
    
    # Regex для [MM:SS]
    TIMECODE_PATTERN_MMSS = re.compile(r"\[(\d{1,2}):(\d{2})\]")
    
    # Regex для [HH:MM:SS]
    TIMECODE_PATTERN_HHMMSS = re.compile(r"\[(\d{1,2}):(\d{2}):(\d{2})\]")
    
    def __init__(
        self,
        max_duration_seconds: Optional[int] = None,
        strict_ordering: bool = False,
    ):
        """Инициализация парсера.
        
        Args:
            max_duration_seconds: Максимальная длительность файла (для валидации).
                                 Если None, валидация по длительности отключена.
            strict_ordering: Если True, проверяет что таймкоды идут по возрастанию.
                            Полезно для детекции ошибок Gemini.
        """
        self.max_duration_seconds = max_duration_seconds
        self.strict_ordering = strict_ordering
        self._last_timecode_seconds: Optional[int] = None
    
    def parse(self, text: str) -> Optional[TimecodeInfo]:
        """Парсит первый таймкод из текста.
        
        Приоритет: [HH:MM:SS] > [MM:SS] (если в строке оба, выбирает более специфичный).
        
        Args:
            text: Текст, содержащий таймкод (обычно начало чанка).
        
        Returns:
            TimecodeInfo если найден валидный таймкод, иначе None.
        
        Example:
            >>> parser = TimecodeParser(max_duration_seconds=3600)
            >>> info = parser.parse("[12:30] Speaker talks")
            >>> print(info.seconds)  # 750
            >>> print(info.original)  # "[12:30]"
        """
        # Пробуем [HH:MM:SS] сначала (более специфичный)
        match_hhmmss = self.TIMECODE_PATTERN_HHMMSS.search(text)
        if match_hhmmss:
            hours, minutes, secs = map(int, match_hhmmss.groups())
            total_seconds = hours * 3600 + minutes * 60 + secs
            original = match_hhmmss.group(0)
            
            if self._validate_timecode(original, total_seconds):
                return TimecodeInfo(
                    original=original,
                    seconds=total_seconds,
                    minutes=minutes,
                    secs=secs,
                    hours=hours,
                )
            return None
        
        # Если нет [HH:MM:SS], пробуем [MM:SS]
        match_mmss = self.TIMECODE_PATTERN_MMSS.search(text)
        if match_mmss:
            minutes, secs = map(int, match_mmss.groups())
            total_seconds = minutes * 60 + secs
            original = match_mmss.group(0)
            
            if self._validate_timecode(original, total_seconds):
                return TimecodeInfo(
                    original=original,
                    seconds=total_seconds,
                    minutes=minutes,
                    secs=secs,
                    hours=0,
                )
            return None
        
        return None
    
    def parse_all(self, text: str) -> list[TimecodeInfo]:
        """Парсит все таймкоды из текста.
        
        Args:
            text: Текст с несколькими таймкодами (например, полная транскрипция).
        
        Returns:
            Список TimecodeInfo (может быть пустым, если таймкодов нет).
        
        Example:
            >>> text = '''
            ... [00:00] Introduction
            ... [05:30] Chapter 1
            ... [15:45] Chapter 2
            ... '''
            >>> timecodes = parser.parse_all(text)
            >>> print(len(timecodes))  # 3
        """
        timecodes = []
        
        # Находим все [HH:MM:SS]
        for match in self.TIMECODE_PATTERN_HHMMSS.finditer(text):
            hours, minutes, secs = map(int, match.groups())
            total_seconds = hours * 3600 + minutes * 60 + secs
            original = match.group(0)
            
            if self._validate_timecode(original, total_seconds):
                timecodes.append(
                    TimecodeInfo(
                        original=original,
                        seconds=total_seconds,
                        minutes=minutes,
                        secs=secs,
                        hours=hours,
                    )
                )
        
        # Находим все [MM:SS]
        for match in self.TIMECODE_PATTERN_MMSS.finditer(text):
            minutes, secs = map(int, match.groups())
            total_seconds = minutes * 60 + secs
            original = match.group(0)
            
            if self._validate_timecode(original, total_seconds):
                timecodes.append(
                    TimecodeInfo(
                        original=original,
                        seconds=total_seconds,
                        minutes=minutes,
                        secs=secs,
                        hours=0,
                    )
                )
        
        return timecodes
    
    def inherit_timecode(
        self,
        last_timecode_seconds: Optional[int],
        chunk_position: int,
        total_chunks: int,
        total_duration_seconds: int,
    ) -> int:
        """Вычисляет таймкод для чанка без явного маркера (наследование).
        
        Логика:
        1. Если chunk_position == 0 → возвращаем 0 (начало файла)
        2. Если last_timecode_seconds известен → добавляем дельту
        3. Иначе → равномерное распределение по длительности
        
        Дельта рассчитывается как: total_duration / total_chunks
        
        Args:
            last_timecode_seconds: Последний известный таймкод от предыдущего чанка.
                                  None если ни один чанк ещё не имел таймкода.
            chunk_position: Позиция текущего чанка (0-based index).
            total_chunks: Общее количество чанков в транскрипции.
            total_duration_seconds: Общая длительность медиа-файла.
        
        Returns:
            Секунды от начала файла (estimated timecode).
        
        Example:
            >>> # 10 chunks, файл 1000 секунд
            >>> parser = TimecodeParser()
            >>> 
            >>> # Первый чанк без таймкода
            >>> t0 = parser.inherit_timecode(None, 0, 10, 1000)
            >>> print(t0)  # 0
            >>> 
            >>> # Чанк #3 без таймкода, last был 200
            >>> t3 = parser.inherit_timecode(200, 3, 10, 1000)
            >>> print(t3)  # 300 (200 + 100)
        """
        # Первый чанк всегда начинается с 0
        if chunk_position == 0:
            return 0
        
        # Вычисляем среднюю дельту между чанками
        delta = total_duration_seconds / total_chunks if total_chunks > 0 else 0
        
        if last_timecode_seconds is None:
            # Равномерное распределение от начала
            return int(chunk_position * delta)
        
        # Инкремент от последнего известного таймкода
        return int(last_timecode_seconds + delta)
    
    def _validate_timecode(self, original: str, seconds: int) -> bool:
        """Внутренняя валидация таймкода.
        
        Args:
            original: Исходная строка таймкода (для логирования).
            seconds: Количество секунд.
        
        Returns:
            True если таймкод валиден, False иначе.
        """
        # Валидация: таймкод не может превышать длительность файла
        if self.max_duration_seconds is not None:
            if seconds > self.max_duration_seconds:
                logger.warning(
                    "[TimecodeParser] Timecode exceeds file duration — ignoring",
                    timecode=original,
                    seconds=seconds,
                    max_duration=self.max_duration_seconds,
                )
                return False
        
        # Валидация: строгий порядок (опционально)
        if self.strict_ordering and self._last_timecode_seconds is not None:
            if seconds <= self._last_timecode_seconds:
                logger.warning(
                    "[TimecodeParser] Timecode order violation — non-ascending",
                    timecode=original,
                    seconds=seconds,
                    last_seconds=self._last_timecode_seconds,
                )
                return False
        
        # Обновляем последний таймкод для strict_ordering
        self._last_timecode_seconds = seconds
        
        return True
