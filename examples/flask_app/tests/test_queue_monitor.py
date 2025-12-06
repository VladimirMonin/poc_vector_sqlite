"""Тесты для страницы мониторинга очереди обработки медиа."""
import pytest
from unittest.mock import Mock, patch


def test_queue_monitor_page_accessible(client):
    """Проверяем что страница очереди доступна."""
    response = client.get("/queue")
    assert response.status_code == 200
    assert b"\xd0\x9e\xd1\x87\xd0\xb5\xd1\x80\xd0\xb5\xd0\xb4\xd1\x8c" in response.data  # "Очередь"


def test_queue_monitor_displays_stats(client):
    """Проверяем отображение статистики."""
    response = client.get("/queue")
    assert response.status_code == 200
    
    # Проверяем наличие карточек статистики
    assert b"\xd0\x9e\xd0\xb6\xd0\xb8\xd0\xb4\xd0\xb0\xd1\x8e\xd1\x82" in response.data  # "Ожидают"
    assert b"\xd0\x9e\xd0\xb1\xd1\x80\xd0\xb0\xd0\xb1\xd0\xbe\xd1\x82\xd0\xba\xd0\xb0" in response.data  # "Обработка"
    assert b"\xd0\x97\xd0\xb0\xd0\xb2\xd0\xb5\xd1\x80\xd1\x88\xd0\xb5\xd0\xbd\xd0\xbe" in response.data  # "Завершено"
    assert b"\xd0\x9e\xd1\x88\xd0\xb8\xd0\xb1\xd0\xba\xd0\xb8" in response.data  # "Ошибки"


def test_queue_tasks_partial(client):
    """Проверяем HTMX partial для таблицы задач."""
    response = client.get("/queue/tasks")
    assert response.status_code == 200
    
    # Проверяем наличие таблицы
    assert b"<table" in response.data
    assert b"<thead" in response.data


@patch("semantic_core.infrastructure.storage.peewee.models.MediaTaskModel")
def test_queue_monitor_empty_queue(mock_model, client):
    """Проверяем отображение пустой очереди."""
    mock_model.select.return_value.order_by.return_value.limit.return_value = []
    
    response = client.get("/queue")
    assert response.status_code == 200


@patch("semantic_core.infrastructure.storage.peewee.models.MediaTaskModel")
def test_retry_task_success(mock_model, client):
    """Проверяем успешный retry задачи."""
    # Mock задачи
    mock_task = Mock()
    mock_task.id = "test-task-id"
    mock_task.status = "failed"
    mock_task.error_message = "Test error"
    
    mock_model.get_by_id.return_value = mock_task
    
    response = client.post("/queue/retry/test-task-id", follow_redirects=True)
    assert response.status_code == 200
    
    # Проверяем что статус был изменён
    assert mock_task.status == "pending"
    assert mock_task.error_message is None
    mock_task.save.assert_called_once()


@patch("semantic_core.infrastructure.storage.peewee.models.MediaTaskModel")
def test_retry_task_not_failed(mock_model, client):
    """Проверяем retry для задачи не в статусе failed."""
    mock_task = Mock()
    mock_task.id = "test-task-id"
    mock_task.status = "completed"  # Не failed
    
    mock_model.get_by_id.return_value = mock_task
    
    response = client.post("/queue/retry/test-task-id", follow_redirects=True)
    assert response.status_code == 200
    
    # Статус не должен измениться
    assert mock_task.status == "completed"


@patch("semantic_core.infrastructure.storage.peewee.models.MediaTaskModel")
def test_retry_task_not_found(mock_model, client):
    """Проверяем retry для несуществующей задачи."""
    mock_model.get_by_id.side_effect = Exception("Task not found")
    
    response = client.post("/queue/retry/nonexistent-id", follow_redirects=True)
    assert response.status_code == 200
