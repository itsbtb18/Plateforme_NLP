"""
Pydantic Schemas for CV Processing API
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class CVExperience(BaseModel):
    """CV Experience entry"""
    type: str = Field(..., description="Type: professional, internship, project, volunteer, event")
    institution: str = Field(..., description="Company or organization name")
    role: str = Field(..., description="Job title or role")
    startDate: Optional[str] = Field(None, description="Start date in YYYY-MM-DD format")
    endDate: Optional[str] = Field(None, description="End date in YYYY-MM-DD format")
    isCurrent: Optional[bool] = Field(False, description="Whether this is current position")
    description: Optional[str] = Field(None, description="Description of responsibilities")


class CVExtractionRequest(BaseModel):
    """Request to extract CV data"""
    file_name: str = Field(..., description="Original filename")
    file_content: bytes = Field(..., description="Binary file content")


class CVExtractionResponse(BaseModel):
    """Response with extracted CV data"""
    firstName: str = Field(..., description="First name")
    lastName: str = Field(..., description="Last name")
    email: Optional[str] = Field(None, description="Email address")
    bio: Optional[str] = Field(None, description="Professional summary")
    specialities: List[str] = Field(default_factory=list, description="List of specialties")
    experiences: List[CVExperience] = Field(default_factory=list, description="List of experiences")


class CVTaskResponse(BaseModel):
    """Response for async CV processing task"""
    task_id: str = Field(..., description="Celery task ID")
    status: str = Field(..., description="Task status: PENDING, STARTED, SUCCESS, FAILURE")
    data: Optional[CVExtractionResponse] = Field(None, description="Extracted CV data when completed")
    error: Optional[str] = Field(None, description="Error message if task failed")


class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
