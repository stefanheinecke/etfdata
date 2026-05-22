@echo off
echo.
echo 🚀 ETF Analytics API - Quick Start
echo ==================================
echo.

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker is not installed. Please install Docker Desktop first.
    exit /b 1
)

echo ✓ Docker found

REM Check if Docker Compose is installed
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker Compose is not installed.
    exit /b 1
)

echo ✓ Docker Compose found
echo.

REM Build and start services
echo 📦 Building and starting services...
docker-compose up --build -d

echo.
echo ⏳ Waiting for services to be ready...
timeout /t 10 /nobreak

echo.
echo 🔍 Checking service health...
echo.

REM Test Backend
echo Backend API...
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 0 (
    echo ✓ Running on http://localhost:8000
) else (
    echo ✗ Not responding yet
)

echo.
echo ==================================
echo ✅ ETF Analytics API is starting up!
echo ==================================
echo.
echo 📱 Access Points:
echo   - Frontend Dashboard: http://localhost:3000
echo   - API: http://localhost:8000
echo   - API Docs (Swagger): http://localhost:8000/docs
echo.
echo ⏳ Services are initializing (wait 30-60 seconds for full startup)
echo.
echo 🛑 To stop services:
echo   docker-compose down
echo.
echo 📖 Full documentation: See README.md
echo.

start http://localhost:3000
