"""
Tests for Celery background tasks
"""
import pytest
from unittest.mock import patch, MagicMock
from app.tasks import extract_cv_from_file, process_cv_batch, health_check


class TestCeleryTasks:
    """Test suite for Celery background tasks"""

    @patch('app.tasks.CVExtractionService')
    def test_extract_cv_from_file_success(self, mock_service_class):
        """Test successful CV extraction task"""
        # Mock the service
        mock_service = MagicMock()
        mock_service.process_cv_file.return_value = {
            'firstName': 'John',
            'lastName': 'Doe',
            'email': 'john@example.com',
            'bio': 'Test',
            'specialities': ['NLP'],
            'experiences': []
        }
        mock_service_class.return_value = mock_service

        # Execute task
        result = extract_cv_from_file.apply(
            args=(b'fake content', 'test.pdf')
        ).get()

        # Verify result
        assert result['firstName'] == 'John'
        assert result['lastName'] == 'Doe'
        mock_service.process_cv_file.assert_called_once()

    @patch('app.tasks.CVExtractionService')
    def test_extract_cv_from_file_failure(self, mock_service_class):
        """Test CV extraction task failure and retry"""
        # Mock the service to raise an exception
        mock_service = MagicMock()
        mock_service.process_cv_file.side_effect = ValueError("Invalid file")
        mock_service_class.return_value = mock_service

        # Task should be set for retry
        with patch('app.tasks.logger') as mock_logger:
            with pytest.raises(ValueError):
                extract_cv_from_file.apply(
                    args=(b'invalid', 'test.pdf')
                ).get()

    @patch('app.tasks.CVExtractionService')
    def test_process_cv_batch(self, mock_service_class):
        """Test batch CV processing"""
        # Mock the service
        mock_service = MagicMock()
        mock_service.process_cv_file.side_effect = [
            {'firstName': 'John', 'lastName': 'Doe', 'email': 'john@test.com', 'bio': '', 'specialities': [], 'experiences': []},
            {'firstName': 'Jane', 'lastName': 'Smith', 'email': 'jane@test.com', 'bio': '', 'specialities': [], 'experiences': []},
        ]
        mock_service_class.return_value = mock_service

        # Create batch
        batch = [
            ('resume1.pdf', b'content1'),
            ('resume2.pdf', b'content2'),
        ]

        # Execute task
        result = process_cv_batch.apply(args=(batch,)).get()

        # Verify results
        assert 'resume1.pdf' in result
        assert 'resume2.pdf' in result
        assert result['resume1.pdf']['status'] == 'success'
        assert result['resume2.pdf']['status'] == 'success'

    @patch('app.tasks.CVExtractionService')
    def test_process_cv_batch_partial_failure(self, mock_service_class):
        """Test batch processing with one file failing"""
        # Mock the service
        mock_service = MagicMock()
        mock_service.process_cv_file.side_effect = [
            {'firstName': 'John', 'lastName': 'Doe', 'email': 'john@test.com', 'bio': '', 'specialities': [], 'experiences': []},
            ValueError("Could not process file"),
        ]
        mock_service_class.return_value = mock_service

        # Create batch
        batch = [
            ('resume1.pdf', b'content1'),
            ('resume2.pdf', b'content2'),
        ]

        # Execute task - should continue despite one failure
        result = process_cv_batch.apply(args=(batch,)).get()

        # Verify results
        assert result['resume1.pdf']['status'] == 'success'
        assert result['resume2.pdf']['status'] == 'error'

    def test_health_check_task(self):
        """Test health check task"""
        result = health_check.apply().get()

        assert result['status'] == 'healthy'
        assert 'message' in result
        assert 'operational' in result['message'].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
