"""E2E Audit Tests Package.

Визуальные тесты для Phase 13: Total Visual Audit.

Структура:
    - test_chunking_audit.py: Сценарий А — Анатомия чанкинга
    - test_search_audit.py: Сценарий В — Качество поиска
    - test_media_audit.py: Сценарий Б — Медиа-обогащение

Запуск:
    # Все тесты аудита
    pytest tests/e2e/audit/ -v -s
    
    # Только чанкинг
    pytest tests/e2e/audit/test_chunking_audit.py -v -s
    
    # С реальным API
    SEMANTIC_GEMINI_API_KEY=your_key pytest tests/e2e/audit/ -v -s

Отчёты:
    Результаты сохраняются в audit_reports/YYYY-MM-DD_HH-MM/
"""
