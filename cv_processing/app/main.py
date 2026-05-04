"""
FastAPI CV Processing Service

Main application with endpoints for CV extraction and processing.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from contextlib import asynccontextmanager

from app.config import get_settings
from app.schemas import CVExtractionResponse, CVTaskResponse, HealthCheckResponse
from app.services.cv_extraction_service import get_cv_extraction_service
from app.tasks import extract_cv_from_file, health_check
from app.celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()

# Configure logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    Handles startup and shutdown events
    """
    logger.info(f"Starting {settings.SERVICE_NAME}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug: {settings.DEBUG}")
    yield
    logger.info(f"Shutting down {settings.SERVICE_NAME}")


# Create FastAPI app
app = FastAPI(
    title="CV Processing Service",
    description="Service for extracting and processing CV/Resume data",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)


# Health check endpoint
@app.get("/health", response_model=HealthCheckResponse)
async def health():
    """Health check endpoint"""
    try:
        return HealthCheckResponse(
            status="healthy",
            service=settings.SERVICE_NAME,
            version="1.0.0"
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Service unavailable")


# Synchronous CV extraction endpoint
@app.post("/extract-cv-sync/", response_model=CVExtractionResponse)
async def extract_cv_sync(file: UploadFile = File(...)):
    """
    Extract CV information synchronously (blocking)
    
    Useful for small files and immediate response requirements.
    
    Args:
        file: Uploaded PDF or DOCX file
        
    Returns:
        Extracted CV data
    """
    try:
        # Validate file type
        allowed_types = settings.ALLOWED_FILE_TYPES
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}"
            )
        
        # Validate file size
        max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        file_content = await file.read()
        
        if len(file_content) > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE_MB}MB"
            )
        
        logger.info(f"Processing CV file synchronously: {file.filename}")
        
        # Process CV
        service = get_cv_extraction_service()
        result = service.process_cv_file(file_content, file.filename)
        
        return CVExtractionResponse(**result)
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error processing CV file: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing CV: {str(e)}"
        )


# Asynchronous CV extraction endpoint (using Celery)
@app.post("/extract-cv-async/", response_model=CVTaskResponse)
async def extract_cv_async(file: UploadFile = File(...)):
    """
    Extract CV information asynchronously using Celery background task
    
    Returns a task ID that can be used to check processing status.
    Suitable for large files and when immediate response is not needed.
    
    Args:
        file: Uploaded PDF or DOCX file
        
    Returns:
        Task ID and initial status
    """
    try:
        # Validate file type
        allowed_types = settings.ALLOWED_FILE_TYPES
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}"
            )
        
        # Validate file size
        max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        file_content = await file.read()
        
        if len(file_content) > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE_MB}MB"
            )
        
        logger.info(f"Queuing CV extraction task for file: {file.filename}")
        
        # Queue the extraction task
        task = extract_cv_from_file.delay(file_content, file.filename)
        
        return CVTaskResponse(
            task_id=task.id,
            status=task.status,
            data=None,
            error=None
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error queuing CV extraction task: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error queuing task: {str(e)}"
        )


# Check async task status
@app.get("/task-status/{task_id}", response_model=CVTaskResponse)
async def get_task_status(task_id: str):
    """
    Check the status of an async CV extraction task
    
    Args:
        task_id: Celery task ID
        
    Returns:
        Task status and result if completed
    """
    try:
        task = celery_app.AsyncResult(task_id)
        
        response = CVTaskResponse(
            task_id=task_id,
            status=task.status,
            data=None,
            error=None
        )
        
        if task.status == 'SUCCESS':
            response.data = CVExtractionResponse(**task.result)
        elif task.status == 'FAILURE':
            response.error = str(task.info)
        
        return response
        
    except Exception as e:
        logger.error(f"Error checking task status {task_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error checking task status: {str(e)}"
        )


# Legacy endpoint (for compatibility with existing code)
@app.post("/extract-cv-signup/", response_model=CVExtractionResponse)
async def extract_cv_signup(file: UploadFile = File(...)):
    """
    Legacy endpoint for signup CV extraction (synchronous)
    
    This endpoint exists for backward compatibility with existing code.
    New code should use /extract-cv-sync/ endpoint.
    
    Args:
        file: Uploaded PDF or DOCX file
        
    Returns:
        Extracted CV data
    """
    return await extract_cv_sync(file)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
