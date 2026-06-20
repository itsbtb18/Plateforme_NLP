from app.schemas import CVExtractionResponse, CVExperience
import pytest
from pydantic import ValidationError

def test_null_fields_coercion():
    # Simulate Groq output with explicit None values for required fields
    data = {
        "firstName": "Jane",
        "lastName": "Doe",
        "experiences": [
            {
                "type": "professional",
                "institution": None,
                "role": None,
                "startDate": "2020",
                "endDate": "2022",
                "isCurrent": False,
                "description": "Some task"
            }
        ]
    }
    
    # Needs to not raise ValidationError
    response = CVExtractionResponse(**data)
    
    assert response.experiences[0].institution == ""
    assert response.experiences[0].role == ""

def test_null_names_coercion():
    # Simulate Groq output with explicit None values for optional/required fields
    data = {
        "firstName": None,
        "lastName": None,
    }
    
    # Needs to not raise ValidationError
    response = CVExtractionResponse(**data)
    
    assert response.firstName == ""
    assert response.lastName == ""
