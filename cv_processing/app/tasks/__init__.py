"""
Celery Tasks for CV Processing

These tasks run in the background to process CV files asynchronously.
"""
import logging
from app.celery_app import celery_app
from app.services.cv_extraction_service import CVExtractionService

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name='cv_processing.tasks.extract_cv_from_file',
    retry_kwargs={'max_retries': 3},
    time_limit=3600,
    soft_time_limit=3300,
)
def extract_cv_from_file(self, file_content: bytes, filename: str):
    """
    Async task to extract CV information from uploaded file
    
    Args:
        file_content: Binary content of the uploaded file
        filename: Original filename
        
    Returns:
        Dictionary with extracted CV data
        
    Raises:
        Exception: If extraction fails
    """
    try:
        logger.info(f"Starting CV extraction task for file: {filename}")
        
        # Create service instance
        service = CVExtractionService()
        
        # Process the CV file
        result = service.process_cv_file(file_content, filename)
        
        logger.info(f"Successfully extracted CV data for file: {filename}")
        return result
        
    except Exception as exc:
        logger.error(f"Error extracting CV from file {filename}: {str(exc)}", exc_info=True)
        
        # Retry the task with exponential backoff
        raise self.retry(exc=exc, countdown=5 * (2 ** self.request.retries))


@celery_app.task(
    bind=True,
    name='cv_processing.tasks.process_cv_batch',
)
def process_cv_batch(self, file_list: list):
    """
    Process multiple CV files in batch
    
    Args:
        file_list: List of tuples (filename, file_content)
        
    Returns:
        Dictionary with results for each file
    """
    try:
        logger.info(f"Starting batch CV extraction for {len(file_list)} files")
        
        results = {}
        service = CVExtractionService()
        
        for filename, file_content in file_list:
            try:
                result = service.process_cv_file(file_content, filename)
                results[filename] = {
                    'status': 'success',
                    'data': result
                }
            except Exception as e:
                logger.error(f"Failed to process {filename}: {str(e)}")
                results[filename] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        logger.info(f"Batch CV extraction completed")
        return results
        
    except Exception as exc:
        logger.error(f"Error processing CV batch: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc, countdown=10)


@celery_app.task(
    name='cv_processing.tasks.health_check',
)
def health_check():
    """
    Simple health check task
    
    Returns:
        Dictionary with health status
    """
    logger.info("Health check task executed")
    return {
        'status': 'healthy',
        'message': 'CV Processing service is operational'
    }
