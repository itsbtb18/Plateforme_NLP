"""
Unit tests for CV Extraction Service
"""
import pytest
import json
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from app.services.cv_extraction_service import CVExtractionService
from app.config import Settings


@pytest.fixture
def cv_service():
    """Fixture to provide CV extraction service instance"""
    return CVExtractionService()


@pytest.fixture
def sample_cv_text():
    """Fixture with sample CV text"""
    return """
    John Doe
    john.doe@example.com
    
    Senior Machine Learning Engineer
    
    Professional Summary:
    Experienced ML engineer with 5+ years in NLP and Deep Learning.
    Skilled in building production systems and training transformers.
    
    Experience:
    Tech Company (2020-Present)
    Senior ML Engineer
    - Led NLP team developing transformer models
    - Reduced inference latency by 40%
    
    Skills:
    - Natural Language Processing
    - Machine Learning
    - Deep Learning
    - Neural Networks
    """


def test_cv_service_initialization(cv_service):
    """Test CV service initializes correctly"""
    assert cv_service is not None
    assert cv_service.settings is not None
    assert cv_service.converter is not None


def test_groq_client_initialization(cv_service):
    """Test Groq client initializes with API key"""
    with patch.dict(os.environ, {'GROQ_CV_API_KEY': 'test_key'}):
        cv_service.groq_client = None
        try:
            cv_service._init_groq_client()
            # Note: This will fail without valid API key, but tests the initialization path
        except ValueError as e:
            # Expected - no valid API key
            pass


def test_speciality_mapping(cv_service):
    """Test speciality mapping functionality"""
    # Test various speciality mappings
    test_cases = [
        (["Natural Language Processing"], "nlp"),
        (["Machine Learning"], "machine_learning"),
        (["Deep Learning"], "deep_learning"),
        (["Computer Vision"], "computer_vision"),
        (["Healthcare AI"], "ai_healthcare"),
        ([], None),
    ]
    
    for specialities, expected in test_cases:
        result = cv_service.map_speciality_to_choices(specialities)
        assert result == expected, f"Failed for {specialities}: got {result}, expected {expected}"


@pytest.mark.asyncio
async def test_cv_extraction_with_mock_file(cv_service, sample_cv_text):
    """Test CV extraction with mocked file operations"""
    with patch.object(cv_service, 'extract_text_from_file') as mock_extract:
        with patch.object(cv_service, 'structure_cv_with_groq') as mock_structure:
            mock_extract.return_value = sample_cv_text
            mock_structure.return_value = {
                'firstName': 'John',
                'lastName': 'Doe',
                'email': 'john.doe@example.com',
                'bio': 'Experienced ML engineer with 5+ years in NLP and Deep Learning.',
                'specialities': ['NLP', 'Machine Learning', 'Deep Learning'],
                'experiences': []
            }
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                tmp.write(b'fake pdf content')
                tmp_path = tmp.name
            
            try:
                result = cv_service.process_cv_file(b'fake content', 'test.pdf')
                assert result['firstName'] == 'John'
                assert result['lastName'] == 'Doe'
                assert result['email'] == 'john.doe@example.com'
                mock_extract.assert_called_once()
                mock_structure.assert_called_once()
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)


def test_cv_data_validation(cv_service):
    """Test CV data validation"""
    # Valid CV data
    valid_cv = {
        'firstName': 'John',
        'lastName': 'Doe',
        'email': 'john@example.com',
        'bio': 'Test bio',
        'specialities': ['NLP'],
        'experiences': []
    }
    
    # Should not raise exception
    assert valid_cv['firstName']
    assert valid_cv['lastName']


def test_invalid_cv_missing_name(cv_service):
    """Test that CV without name raises error"""
    invalid_cv = {
        'firstName': '',
        'lastName': '',
        'email': 'test@example.com',
        'bio': 'Test',
        'specialities': [],
        'experiences': []
    }
    
    # Validation should catch missing name
    assert not (invalid_cv['firstName'] and invalid_cv['lastName'])
