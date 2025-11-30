# Quick start script for Django frontend only
# Use this when you only need to restart the Django server

Write-Host "Starting Django Frontend Server..." -ForegroundColor Cyan
Write-Host "Server will run on: http://localhost:8000" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""
Write-Host "Make sure FastAPI is running on port 8001!" -ForegroundColor Red
Write-Host ""

Set-Location "D:\PFE\Plateforme_NLP"

# Activate virtual environment
& "D:\PFE\Plateforme_NLP\.venv\Scripts\Activate.ps1"

# Navigate to Django directory
Set-Location "Plateforme"

# Run migrations if needed
Write-Host "Checking for database migrations..." -ForegroundColor Yellow
python manage.py migrate --noinput

# Start server
python manage.py runserver 8000
