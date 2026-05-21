"""
Integration tests for CV Processing API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import io
from app.main import app

client = TestClient(app)


@pytest.fixture
def sample_pdf_file():
    """Create a mock PDF file"""
    return ("resume.pdf", io.BytesIO(b"fake pdf content"), "application/pdf")


@pytest.fixture
def sample_docx_file():
    """Create a mock DOCX file"""
    return ("resume.docx", io.BytesIO(b"fake docx content"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")


def test_health_check():
    """Test health check endpoint"""
    with patch('app.main.health_check.delay') as mock_health:
        mock_task = MagicMock()
        mock_task.id = "test-task-id"
        mock_health.return_value = mock_task
        
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'
        assert data['service'] == 'CV Processing Service'
        assert 'version' in data


def test_extract_cv_sync_invalid_file_type():
    """Test sync extraction with invalid file type"""
    files = {'file': ('document.txt', io.BytesIO(b"text content"), 'text/plain')}
    
    response = client.post("/extract-cv-sync/", files=files)
    
    assert response.status_code == 400
    assert "Invalid file type" in response.json()['detail']


def test_extract_cv_sync_file_too_large():
    """Test sync extraction with oversized file"""
    # Create a file larger than max size
    large_content = b"x" * (25 * 1024 * 1024)  # 25MB
    files = {'file': ('resume.pdf', io.BytesIO(large_content), 'application/pdf')}
    
    response = client.post("/extract-cv-sync/", files=files)
    
    assert response.status_code == 413
    assert "too large" in response.json()['detail'].lower()


@patch('app.services.cv_extraction_service.CVExtractionService.process_cv_file')
def test_extract_cv_sync_success(mock_process):
    """Test successful synchronous CV extraction"""
    mock_process.return_value = {
        'firstName': 'John',
        'lastName': 'Doe',
        'email': 'john@example.com',
        'bio': 'Experienced engineer',
        'specialities': ['NLP', 'ML'],
        'experiences': []
    }
    
    files = {'file': ('resume.pdf', io.BytesIO(b"fake pdf"), 'application/pdf')}
    
    response = client.post("/extract-cv-sync/", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert data['firstName'] == 'John'
    assert data['lastName'] == 'Doe'
    assert data['email'] == 'john@example.com'
    assert data['bio'] == 'Experienced engineer'
    assert 'NLP' in data['specialities']


def test_extract_cv_async_invalid_file_type():
    """Test async extraction with invalid file type"""
    files = {'file': ('document.txt', io.BytesIO(b"text content"), 'text/plain')}
    
    response = client.post("/extract-cv-async/", files=files)
    
    assert response.status_code == 400
    assert "Invalid file type" in response.json()['detail']


@patch('app.main.extract_cv_from_file.delay')
def test_extract_cv_async_success(mock_delay):
    """Test successful asynchronous CV extraction"""
    mock_task = MagicMock()
    mock_task.id = "test-task-id-123"
    mock_task.status = "PENDING"
    mock_delay.return_value = mock_task
    
    files = {'file': ('resume.pdf', io.BytesIO(b"fake pdf"), 'application/pdf')}
    
    response = client.post("/extract-cv-async/", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert data['task_id'] == "test-task-id-123"
    assert data['status'] == 'PENDING'
    assert data['data'] is None


@patch('app.celery_app.celery_app')
def test_task_status_pending(mock_celery_app):
    """Test getting status of pending task"""
    mock_task = MagicMock()
    mock_task.status = 'PENDING'
    mock_task.result = None
    mock_celery_app.AsyncResult.return_value = mock_task
    
    response = client.get("/task-status/test-task-id")
    
    assert response.status_code == 200
    data = response.json()
    assert data['task_id'] == 'test-task-id'
    assert data['status'] == 'PENDING'
    assert data['data'] is None


@patch('app.celery_app.celery_app')
def test_task_status_success(mock_celery_app):
    """Test getting status of completed task"""
    mock_task = MagicMock()
    mock_task.status = 'SUCCESS'
    mock_task.result = {
        'firstName': 'Jane',
        'lastName': 'Smith',
        'email': 'jane@example.com',
        'bio': 'Test bio',
        'specialities': ['ML'],
        'experiences': []
    }
    mock_celery_app.AsyncResult.return_value = mock_task
    
    response = client.get("/task-status/test-task-id")
    
    assert response.status_code == 200
    data = response.json()
    assert data['task_id'] == 'test-task-id'
    assert data['status'] == 'SUCCESS'
    assert data['data']['firstName'] == 'Jane'
    assert data['data']['lastName'] == 'Smith'


@patch('app.celery_app.celery_app')
def test_task_status_failure(mock_celery_app):
    """Test getting status of failed task"""
    mock_task = MagicMock()
    mock_task.status = 'FAILURE'
    mock_task.info = 'Error processing file'
    mock_celery_app.AsyncResult.return_value = mock_task
    
    response = client.get("/task-status/test-task-id")
    
    assert response.status_code == 200
    data = response.json()
    assert data['task_id'] == 'test-task-id'
    assert data['status'] == 'FAILURE'
    assert data['error'] is not None


@patch('app.services.cv_extraction_service.CVExtractionService.process_cv_file')
def test_legacy_extract_cv_signup_endpoint(mock_process):
    """Test legacy /extract-cv-signup/ endpoint (backward compatibility)"""
    mock_process.return_value = {
        'firstName': 'John',
        'lastName': 'Doe',
        'email': 'john@example.com',
        'bio': 'Legacy test',
        'specialities': [],
        'experiences': []
    }
    
    files = {'file': ('resume.pdf', io.BytesIO(b"fake pdf"), 'application/pdf')}
    
    response = client.post("/extract-cv-signup/", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert data['firstName'] == 'John'
    assert data['lastName'] == 'Doe'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
