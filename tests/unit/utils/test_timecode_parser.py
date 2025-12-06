"""Unit-тесты для TimecodeParser — парсинг и валидация таймкодов.

Архитектурный контекст:
-----------------------
Phase 14.1.2: Advanced Features — тесты для TimecodeParser утилиты.

Покрытие:
---------
- ✅ parse() для [MM:SS] и [HH:MM:SS]
- ✅ parse_all() для множественных таймкодов
- ✅ inherit_timecode() для чанков без маркеров
- ✅ Валидация max_duration_seconds
- ✅ Валидация strict_ordering
- ✅ Edge cases (нет таймкода, невалидный формат, граничные значения)
"""

import pytest

from semantic_core.utils.timecode_parser import TimecodeInfo, TimecodeParser


class TestTimecodeParserBasic:
    """Тесты базового парсинга таймкодов."""
    
    def test_parse_mmss_format(self):
        """Парсинг формата [MM:SS]."""
        parser = TimecodeParser()
        
        info = parser.parse("[12:30] Speaker talks")
        
        assert info is not None
        assert info.original == "[12:30]"
        assert info.seconds == 750  # 12*60 + 30
        assert info.minutes == 12
        assert info.secs == 30
        assert info.hours == 0
    
    def test_parse_hhmmss_format(self):
        """Парсинг формата [HH:MM:SS]."""
        parser = TimecodeParser()
        
        info = parser.parse("[01:23:45] Long talk")
        
        assert info is not None
        assert info.original == "[01:23:45]"
        assert info.seconds == 5025  # 1*3600 + 23*60 + 45
        assert info.minutes == 23
        assert info.secs == 45
        assert info.hours == 1
    
    def test_parse_zero_timecode(self):
        """Парсинг [00:00] — начало файла."""
        parser = TimecodeParser()
        
        info = parser.parse("[00:00] Introduction")
        
        assert info is not None
        assert info.seconds == 0
        assert info.original == "[00:00]"
    
    def test_parse_no_timecode(self):
        """Текст без таймкода возвращает None."""
        parser = TimecodeParser()
        
        info = parser.parse("Just some text without timecode")
        
        assert info is None
    
    def test_parse_invalid_format(self):
        """Невалидный формат (не [MM:SS]) возвращает None."""
        parser = TimecodeParser()
        
        info = parser.parse("12:30 without brackets")
        
        assert info is None
    
    def test_parse_prefers_hhmmss_over_mmss(self):
        """Если в строке оба формата, выбирает [HH:MM:SS]."""
        parser = TimecodeParser()
        
        # В строке есть и [01:23:45] и [23:45]
        info = parser.parse("[01:23:45] and also [23:45]")
        
        assert info is not None
        assert info.original == "[01:23:45]"
        assert info.hours == 1


class TestTimecodeParserParseAll:
    """Тесты парсинга множественных таймкодов."""
    
    def test_parse_all_multiple_timecodes(self):
        """Извлекает все таймкоды из текста."""
        parser = TimecodeParser()
        
        text = """
        [00:00] Introduction
        [05:30] Chapter 1
        [15:45] Chapter 2
        """
        
        timecodes = parser.parse_all(text)
        
        assert len(timecodes) == 3
        assert timecodes[0].seconds == 0
        assert timecodes[1].seconds == 330  # 5*60 + 30
        assert timecodes[2].seconds == 945  # 15*60 + 45
    
    def test_parse_all_mixed_formats(self):
        """Извлекает смешанные [MM:SS] и [HH:MM:SS]."""
        parser = TimecodeParser()
        
        text = """
        [00:00] Start
        [01:00:00] One hour mark
        [90:00] Ninety minutes
        """
        
        timecodes = parser.parse_all(text)
        
        # parse_all() сначала находит все [HH:MM:SS], потом все [MM:SS]
        # Порядок: [01:00:00], затем [00:00], [90:00]
        assert len(timecodes) == 3
        
        # Сортируем по seconds для проверки корректности
        sorted_by_time = sorted(timecodes, key=lambda t: t.seconds)
        assert sorted_by_time[0].seconds == 0      # [00:00]
        assert sorted_by_time[1].seconds == 3600   # [01:00:00]
        assert sorted_by_time[2].seconds == 5400   # [90:00]
    
    def test_parse_all_empty_text(self):
        """Пустой текст возвращает пустой список."""
        parser = TimecodeParser()
        
        timecodes = parser.parse_all("")
        
        assert timecodes == []
    
    def test_parse_all_no_timecodes(self):
        """Текст без таймкодов возвращает пустой список."""
        parser = TimecodeParser()
        
        text = "Just a long text without any timecode markers in it."
        
        timecodes = parser.parse_all(text)
        
        assert timecodes == []


class TestTimecodeParserValidation:
    """Тесты валидации таймкодов."""
    
    def test_max_duration_validation_pass(self):
        """Таймкод в пределах max_duration проходит."""
        parser = TimecodeParser(max_duration_seconds=600)  # 10 минут
        
        info = parser.parse("[05:30] Within limits")
        
        assert info is not None
        assert info.seconds == 330
    
    def test_max_duration_validation_fail(self):
        """Таймкод больше max_duration отклоняется."""
        parser = TimecodeParser(max_duration_seconds=600)  # 10 минут
        
        info = parser.parse("[15:00] Exceeds duration")
        
        assert info is None  # Отклонён валидацией
    
    def test_strict_ordering_ascending(self):
        """strict_ordering=True принимает возрастающие таймкоды."""
        parser = TimecodeParser(strict_ordering=True)
        
        info1 = parser.parse("[01:00] First")
        info2 = parser.parse("[02:00] Second")
        info3 = parser.parse("[03:00] Third")
        
        assert info1 is not None
        assert info2 is not None
        assert info3 is not None
    
    def test_strict_ordering_violation(self):
        """strict_ordering=True отклоняет не возрастающие."""
        parser = TimecodeParser(strict_ordering=True)
        
        info1 = parser.parse("[02:00] First")
        info2 = parser.parse("[01:00] Goes back — invalid")
        
        assert info1 is not None
        assert info2 is None  # Отклонён из-за нарушения порядка
    
    def test_strict_ordering_equal(self):
        """strict_ordering=True отклоняет равные таймкоды."""
        parser = TimecodeParser(strict_ordering=True)
        
        info1 = parser.parse("[02:00] First")
        info2 = parser.parse("[02:00] Same — invalid")
        
        assert info1 is not None
        assert info2 is None  # Равные таймкоды недопустимы


class TestTimecodeParserInheritance:
    """Тесты наследования таймкодов для чанков без маркеров."""
    
    def test_inherit_first_chunk_is_zero(self):
        """Первый чанк (position=0) всегда начинается с 0."""
        parser = TimecodeParser()
        
        inherited = parser.inherit_timecode(
            last_timecode_seconds=None,
            chunk_position=0,
            total_chunks=10,
            total_duration_seconds=1000,
        )
        
        assert inherited == 0
    
    def test_inherit_without_last_timecode(self):
        """Без last_timecode — равномерное распределение."""
        parser = TimecodeParser()
        
        # 10 чанков, 1000 секунд → delta = 100
        inherited = parser.inherit_timecode(
            last_timecode_seconds=None,
            chunk_position=3,
            total_chunks=10,
            total_duration_seconds=1000,
        )
        
        assert inherited == 300  # 3 * 100
    
    def test_inherit_with_last_timecode(self):
        """С last_timecode — инкремент от последнего."""
        parser = TimecodeParser()
        
        # 10 чанков, 1000 секунд → delta = 100
        # Последний был 250, добавляем 100
        inherited = parser.inherit_timecode(
            last_timecode_seconds=250,
            chunk_position=4,
            total_chunks=10,
            total_duration_seconds=1000,
        )
        
        assert inherited == 350  # 250 + 100
    
    def test_inherit_last_chunk(self):
        """Последний чанк наследует корректно."""
        parser = TimecodeParser()
        
        # 10 чанков, last был 900
        inherited = parser.inherit_timecode(
            last_timecode_seconds=900,
            chunk_position=9,
            total_chunks=10,
            total_duration_seconds=1000,
        )
        
        # 900 + (1000/10) = 1000
        assert inherited == 1000
    
    def test_inherit_zero_chunks_edge_case(self):
        """Edge case: total_chunks=0 не вызывает деление на 0."""
        parser = TimecodeParser()
        
        inherited = parser.inherit_timecode(
            last_timecode_seconds=None,
            chunk_position=0,
            total_chunks=0,  # Нереалистично, но не должно крашиться
            total_duration_seconds=1000,
        )
        
        assert inherited == 0  # Первый чанк всегда 0


class TestTimecodeParserEdgeCases:
    """Тесты граничных случаев и corner cases."""
    
    def test_single_digit_minutes(self):
        """Парсинг [5:30] (одна цифра в минутах)."""
        parser = TimecodeParser()
        
        info = parser.parse("[5:30] Short minutes")
        
        assert info is not None
        assert info.seconds == 330  # 5*60 + 30
    
    def test_large_minutes(self):
        """Парсинг [99:59] (большие минуты)."""
        parser = TimecodeParser()
        
        info = parser.parse("[99:59] Near 100 minutes")
        
        assert info is not None
        assert info.seconds == 5999  # 99*60 + 59
    
    def test_timecode_in_middle_of_text(self):
        """Таймкод в середине строки."""
        parser = TimecodeParser()
        
        info = parser.parse("Some text before [12:30] and after")
        
        assert info is not None
        assert info.original == "[12:30]"
    
    def test_multiple_timecodes_in_one_line(self):
        """parse() возвращает только первый таймкод."""
        parser = TimecodeParser()
        
        info = parser.parse("[01:00] first [02:00] second")
        
        # parse() возвращает первый найденный
        assert info is not None
        assert info.original == "[01:00]"
    
    def test_parse_all_with_duplicates(self):
        """parse_all() возвращает дубликаты если они есть."""
        parser = TimecodeParser()
        
        text = "[01:00] First\n[01:00] Duplicate\n[02:00] Third"
        
        timecodes = parser.parse_all(text)
        
        # Оба [01:00] включены (если нет strict_ordering)
        assert len(timecodes) == 3


class TestTimecodeInfo:
    """Тесты TimecodeInfo dataclass."""
    
    def test_timecode_info_creation(self):
        """Создание TimecodeInfo с полными данными."""
        info = TimecodeInfo(
            original="[01:23:45]",
            seconds=5025,
            minutes=23,
            secs=45,
            hours=1,
        )
        
        assert info.original == "[01:23:45]"
        assert info.seconds == 5025
        assert info.minutes == 23
        assert info.secs == 45
        assert info.hours == 1
    
    def test_timecode_info_default_hours(self):
        """hours по умолчанию = 0."""
        info = TimecodeInfo(
            original="[12:30]",
            seconds=750,
            minutes=12,
            secs=30,
        )
        
        assert info.hours == 0
