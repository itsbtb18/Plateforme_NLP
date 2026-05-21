"""
CV Extraction Service

Uses Docling to extract text from PDF/DOCX and Groq to structure the data.
"""

import logging
import json
import re
import tempfile
import os
from typing import Optional
from docling.document_converter import DocumentConverter
from docling_core.types.doc import DoclingDocument

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CVExtractionService:
    """Service to extract and structure CV information"""

    def __init__(self):
        self.settings = settings
        self.converter = DocumentConverter()
        self.groq_client = None

    def _init_groq_client(self):
        """Initialize Groq client with CV-specific API key"""
        if self.groq_client is None:
            from groq import Groq
            
            api_key = self.settings.GROQ_CV_API_KEY
            if not api_key:
                raise ValueError("GROQ_CV_API_KEY not configured in environment")
            
            self.groq_client = Groq(api_key=api_key)
        return self.groq_client

    def _derive_name_fallback(self, structured_data: dict, filename: str) -> tuple[str, str]:
        """Derive a best-effort name from email or filename when LLM output misses it."""
        first_name = (structured_data.get("firstName") or "").strip()
        last_name = (structured_data.get("lastName") or "").strip()

        if first_name and last_name:
            return first_name, last_name

        # Try parsing the local part of the email (e.g., john.doe@x.com).
        email = (structured_data.get("email") or "").strip()
        if email and "@" in email:
            local = email.split("@", 1)[0]
            email_tokens = [t for t in re.split(r"[._\-\s]+", local) if t]
            if len(email_tokens) >= 2:
                if not first_name:
                    first_name = email_tokens[0].capitalize()
                if not last_name:
                    last_name = email_tokens[-1].capitalize()

        if first_name and last_name:
            return first_name, last_name

        # Fallback to filename tokens (e.g., jean_dupont_cv.pdf).
        base = os.path.splitext(os.path.basename(filename))[0]
        file_tokens = [t for t in re.split(r"[^A-Za-z]+", base) if t]
        if len(file_tokens) >= 2:
            if not first_name:
                first_name = file_tokens[0].capitalize()
            if not last_name:
                last_name = file_tokens[-1].capitalize()

        if not first_name:
            first_name = "Candidate"
        if not last_name:
            last_name = "Unknown"

        return first_name, last_name

    def extract_text_from_file(self, file_path: str) -> str:
        """
        Extract text from PDF or DOCX file using Docling
        
        Args:
            file_path: Path to the uploaded file
            
        Returns:
            Extracted text content
            
        Raises:
            ValueError: If no text content could be extracted
            Exception: If extraction fails
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
            logger.error(f"Error extracting text from file: {str(e)}", exc_info=True)
            raise

    def structure_cv_with_groq(self, cv_text: str) -> dict:
        """
        Use Groq to structure CV text into JSON format
        
        Args:
            cv_text: Extracted CV text content
            
        Returns:
            Structured CV data as dictionary
            
        Raises:
            ValueError: If JSON parsing fails
            Exception: If Groq API call fails
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
                model=self.settings.GROQ_CV_MODEL,
                max_tokens=self.settings.GROQ_MAX_TOKENS,
                temperature=self.settings.GROQ_TEMPERATURE,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            response_text = message.choices[0].message.content.strip()

            # Handle markdown code blocks if present
            if response_text.startswith("```"):
                json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)

            structured_data = json.loads(response_text)

            logger.info("Successfully structured CV data with Groq")
            return structured_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response from Groq: {str(e)}", exc_info=True)
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
            
        Raises:
            ValueError: If extraction or validation fails
            Exception: If processing fails
        """
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=os.path.splitext(filename)[1],
            dir=self.settings.get_temp_dir
        ) as tmp_file:
            tmp_file.write(file_content)
            tmp_path = tmp_file.name
        
        try:
            # Extract text
            cv_text = self.extract_text_from_file(tmp_path)
            
            # Structure with Groq
            structured_data = self.structure_cv_with_groq(cv_text)
            
            # Ensure required name fields exist; use best-effort fallback instead of failing.
            first_name, last_name = self._derive_name_fallback(structured_data, filename)
            structured_data["firstName"] = first_name
            structured_data["lastName"] = last_name
            
            logger.info(f"Successfully processed CV file: {filename}")
            return structured_data
            
        finally:
            # Clean up temporary file
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                    logger.debug(f"Cleaned up temporary file: {tmp_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {tmp_path}: {str(e)}")

    def map_speciality_to_choices(self, specialities: list) -> Optional[str]:
        """
        Map extracted specialities to Django SPECIALITY_CHOICES
        
        Args:
            specialities: List of extracted speciality strings
            
        Returns:
            Best matching speciality choice key
        """
        # Django speciality choices mapping
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
        
        # If no match found, return "autre"
        return "autre"


def get_cv_extraction_service() -> CVExtractionService:
    """Get or create CV extraction service instance"""
    return CVExtractionService()
