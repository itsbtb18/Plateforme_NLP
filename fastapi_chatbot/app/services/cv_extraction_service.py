"""
CV Extraction Service for Signup

Uses Docling to extract text from PDF/DOCX and Groq to structure the data.
"""

import logging
import json
import re
from typing import Optional
from datetime import datetime
from docling.document_converter import DocumentConverter
from docling_core.types.doc import DoclingDocument
import tempfile
import os

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CVExtractionService:
    """Service to extract and structure CV information"""

    def __init__(self):
        self.settings = settings
        self.converter = DocumentConverter()
        # Import Groq client inside method to avoid import errors if not available
        self.groq_client = None

    def _init_groq_client(self):
        """Initialize Groq client with CV-specific API key"""
        if self.groq_client is None:
            from groq import Groq
            
            api_key = self.settings.GROQ_CV_SIGNUP_API_KEY
            if not api_key:
                raise ValueError("GROQ_CV_SIGNUP_API_KEY not configured in environment")
            
            self.groq_client = Groq(api_key=api_key)
        return self.groq_client

    def extract_text_from_file(self, file_path: str) -> str:
        """
        Extract text from PDF or DOCX file using Docling
        
        Args:
            file_path: Path to the uploaded file
            
        Returns:
            Extracted text content
        """
        try:
            logger.info(f"Extracting text from file: {file_path}")
            
            doc: DoclingDocument = self.converter.convert(file_path).document
            
            # Extract all text from the document
            text_content = doc.export_to_markdown()
            
            if not text_content or not text_content.strip():
                raise ValueError("No text content could be extracted from the document")
            
            logger.info(f"Successfully extracted {len(text_content)} characters")
            return text_content
            
        except Exception as e:
            logger.error(f"Error extracting text from file: {str(e)}")
            raise

    def structure_cv_with_groq(self, cv_text: str) -> dict:
        """
        Use Groq to structure CV text into JSON format
        """
        try:
            client = self._init_groq_client()

            prompt = f"""Analyze the following CV/Resume text and extract the information in JSON format.

IMPORTANT: Return ONLY valid JSON, no markdown, no extra text.

Extract the following fields:
{{
    "firstName": "First name of the person",
    "lastName": "Last name of the person",
    "email": "Email if found",
    "bio": "2-3 sentence professional summary",
    "specialities": ["List of AI/tech specialties mentioned (e.g., 'NLP', 'Machine Learning', 'Deep Learning')"],
    "experiences": [
        {{
            "type": "professional|internship|project|volunteer|event",
            "institution": "Company/Organization name",
            "role": "Job title or role",
            "startDate": "YYYY-MM-DD format or approximate year",
            "endDate": "YYYY-MM-DD format or approximate year or null if current",
            "isCurrent": true,
            "description": "Brief description of responsibilities"
        }}
    ]
}}

CV TEXT TO ANALYZE:
---
{cv_text[:4000]}
---

Return ONLY the JSON object, nothing else."""

            logger.info("Sending CV text to Groq for structuring...")

            message = client.chat.completions.create(
                model=self.settings.GROQ_CV_SIGNUP_MODEL,
                max_tokens=2048,
                temperature=0.3,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            response_text = message.choices[0].message.content.strip()

            if response_text.startswith("```"):
                json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)

            structured_data = json.loads(response_text)

            logger.info("Successfully structured CV data with Groq")
            return structured_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response from Groq: {str(e)}")
            logger.error(f"Response was: {response_text}")
            raise ValueError(f"Failed to parse CV extraction response: {str(e)}")
        except Exception as e:
            logger.exception("Error structuring CV with Groq")
            raise


    def process_cv_file(self, file_content: bytes, filename: str) -> dict:
        """
        Complete pipeline: extract text and structure with Groq
        
        Args:
            file_content: Binary content of uploaded file
            filename: Original filename
            
        Returns:
            Structured CV data as dictionary
        """
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=os.path.splitext(filename)[1],
            dir=tempfile.gettempdir()
        ) as tmp_file:
            tmp_file.write(file_content)
            tmp_path = tmp_file.name
        
        try:
            # Extract text
            cv_text = self.extract_text_from_file(tmp_path)
            
            # Structure with Groq
            structured_data = self.structure_cv_with_groq(cv_text)
            
            # Validate required fields
            if not structured_data.get("firstName") or not structured_data.get("lastName"):
                raise ValueError("Could not extract name from CV")
            
            return structured_data
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(tmp_path)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file: {str(e)}")

    def map_speciality_to_choices(self, specialities: list) -> Optional[str]:
        """
        Map extracted specialities to Django SPECIALITY_CHOICES
        
        Args:
            specialities: List of extracted speciality strings
            
        Returns:
            Best matching speciality choice key
        """
        # Django speciality choices (from models.py)
        speciality_mapping = {
            "machine learning": "machine_learning",
            "deep learning": "deep_learning",
            "nlp": "nlp",
            "natural language": "nlp",
            "computer vision": "computer_vision",
            "reinforcement learning": "reinforcement_learning",
            "ai ethics": "ai_ethics",
            "robotics": "robotics",
            "neural networks": "neural_networks",
            "ai security": "ai_security",
            "ai healthcare": "ai_healthcare",
            "healthcare": "ai_healthcare",
            "ai finance": "ai_finance",
            "finance": "ai_finance",
            "ai education": "ai_education",
            "education": "ai_education",
            "ai transport": "ai_transport",
            "transportation": "ai_transport",
            "ai agriculture": "ai_agriculture",
            "agriculture": "ai_agriculture",
            "ai energy": "ai_energy",
            "energy": "ai_energy",
            "ai manufacturing": "ai_manufacturing",
            "manufacturing": "ai_manufacturing",
            "ai research": "ai_research",
            "research": "ai_research",
        }
        
        if not specialities:
            return None
        
        # Find best match for first speciality
        for spec in specialities:
            spec_lower = spec.lower()
            for key, choice_value in speciality_mapping.items():
                if key in spec_lower:
                    return choice_value
        
        # If no match found, try "autre"
        return "autre"


def get_cv_extraction_service() -> CVExtractionService:
    """Get or create CV extraction service instance"""
    return CVExtractionService()
