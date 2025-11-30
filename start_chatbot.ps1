# PowerShell script to start the complete chatbot system
# Run this script to start both Django and FastAPI servers

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  NLP Platform Chatbot Startup Script  " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
Write-Host "[1/5] Checking Python installation..." -ForegroundColor Yellow
Set-Location "D:\PFE\Plateforme_NLP"

# Activate virtual environment
& ".\.venv\Scripts\Activate.ps1"

try {
    $pythonVersion = python --version 2>&1
    Write-Host "OK - Python detected: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR - Python is not installed or not in PATH" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Install FastAPI dependencies
Write-Host "[2/5] Installing FastAPI dependencies..." -ForegroundColor Yellow
Set-Location "fastapi_chatbot"
python -m pip install -r requirements.txt --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "OK - FastAPI dependencies installed" -ForegroundColor Green
} else {
    Write-Host "WARNING - Some dependencies might have failed" -ForegroundColor Yellow
}
Write-Host ""

# Install Django dependencies
Write-Host "[3/5] Installing Django dependencies..." -ForegroundColor Yellow
Set-Location "..\Plateforme"
python -m pip install -r requirements.txt --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "OK - Django dependencies installed" -ForegroundColor Green
} else {
    Write-Host "WARNING - Some dependencies might have failed" -ForegroundColor Yellow
}
Write-Host ""

# Initialize FastAPI database
Write-Host "[4/5] Initializing FastAPI database..." -ForegroundColor Yellow
Set-Location "..\fastapi_chatbot"
Write-Host "Note: Database will be initialized when FastAPI starts" -ForegroundColor Cyan
Write-Host ""

# Start servers
Write-Host "[5/5] Starting servers..." -ForegroundColor Yellow
Set-Location ".."
Write-Host ""
Write-Host "Starting FastAPI server on http://localhost:8001..." -ForegroundColor Cyan
Write-Host "Starting Django server on http://localhost:8000..." -ForegroundColor Cyan
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  IMPORTANT INSTRUCTIONS:              " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Two terminal windows will open:" -ForegroundColor White
Write-Host "  1. FastAPI Backend (Port 8001) - Keep this running" -ForegroundColor Yellow
Write-Host "  2. Django Frontend (Port 8000) - Keep this running" -ForegroundColor Yellow
Write-Host ""
Write-Host "Access the chatbot at: http://localhost:8000/chatbot/" -ForegroundColor Cyan
Write-Host ""
Write-Host "To stop servers: Press Ctrl+C in each terminal" -ForegroundColor White
Write-Host ""

# Start FastAPI in new terminal
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd D:\PFE\Plateforme_NLP; & .\.venv\Scripts\Activate.ps1; cd fastapi_chatbot; Write-Host 'FastAPI Backend Server' -ForegroundColor Green; Write-Host 'Starting on http://localhost:8001' -ForegroundColor Cyan; Write-Host ''; python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload"

# Wait a moment for FastAPI to start
Start-Sleep -Seconds 3

# Start Django in new terminal
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd D:\PFE\Plateforme_NLP; & .\.venv\Scripts\Activate.ps1; cd Plateforme; Write-Host 'Django Frontend Server' -ForegroundColor Green; Write-Host 'Starting on http://localhost:8000' -ForegroundColor Cyan; Write-Host ''; python manage.py runserver 8000"

Write-Host "OK - Servers starting in separate terminals..." -ForegroundColor Green
Write-Host ""
Write-Host "Monitor the terminal windows for any errors." -ForegroundColor Yellow
Write-Host "The chatbot should be ready in a few seconds." -ForegroundColor Yellow
Write-Host ""
