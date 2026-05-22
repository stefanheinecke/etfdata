@echo off
setlocal enabledelayedexpansion

echo.
echo 🔍 ETF Analytics API - Setup Verification
echo ========================================
echo.

set PASS=0
set FAIL=0

REM Check Docker
echo Checking Docker installation...
docker --version >nul 2>&1
if !errorlevel! equ 0 (
    echo ✓ Docker found
    set /a PASS=!PASS!+1
) else (
    echo ✗ Docker not found
    set /a FAIL=!FAIL!+1
)

REM Check if Backend is running
echo Checking Backend API (port 8000)...
curl -s http://localhost:8000/health -H "X-API-Key: test-key" >nul 2>&1
if !errorlevel! equ 0 (
    echo ✓ Backend running
    set /a PASS=!PASS!+1
) else (
    echo ✗ Backend not responding
    set /a FAIL=!FAIL!+1
)

REM Check Frontend
echo Checking Frontend (port 3000)...
curl -s http://localhost:3000 >nul 2>&1
if !errorlevel! equ 0 (
    echo ✓ Frontend running
    set /a PASS=!PASS!+1
) else (
    echo ✗ Frontend not responding
    set /a FAIL=!FAIL!+1
)

REM Check Database
echo Checking Database...
docker exec etfdata-db pg_isready -U postgres >nul 2>&1
if !errorlevel! equ 0 (
    echo ✓ Database running
    set /a PASS=!PASS!+1
) else (
    echo ✗ Database not responding
    set /a FAIL=!FAIL!+1
)

echo.
echo ========================================

if !FAIL! equ 0 (
    echo ✅ All checks passed! Setup is ready.
    echo.
    echo 🎉 Next steps:
    echo   - Frontend: http://localhost:3000
    echo   - API Docs: http://localhost:8000/docs
    echo   - Enjoy! 🚀
) else (
    echo ❌ Some checks failed (!FAIL!/4)
    echo.
    echo To fix:
    echo 1. Make sure Docker Desktop is running
    echo 2. Run: docker-compose up --build
    echo 3. Wait 60 seconds for initialization
    echo 4. Re-run this script
)

echo.
