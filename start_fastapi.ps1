# Quick start script for FastAPI backend only
# Use this when you only need to restart the FastAPI server

Write-Host "Starting FastAPI Chatbot Backend..." -ForegroundColor Cyan
Write-Host "Server will run on: http://localhost:8001" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

Set-Location "D:\PFE\Plateforme_NLP"

# Activate virtual environment
& "D:\PFE\Plateforme_NLP\.venv\Scripts\Activate.ps1"

# Navigate to FastAPI directory
Set-Location "fastapi_chatbot"

# Check if dependencies are installed
python -c "import groq" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    python -m pip install -r requirements.txt
}

# Start server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
