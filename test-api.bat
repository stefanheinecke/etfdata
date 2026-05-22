@echo off
REM ETF Analytics API - Test Script

setlocal enabledelayedexpansion

set API_URL=http://localhost:8000
set API_KEY=test-key

echo.
echo 🧪 ETF Analytics API - Test Suite
echo ==================================
echo.

REM Test 1: Health Check
echo Test 1: Health Check
echo -------------------
curl -X GET "%API_URL%/health" ^
  -H "X-API-Key: %API_KEY%" ^
  -s
echo.
echo.

REM Test 2: Get All ETFs
echo Test 2: Get All ETFs (first 5)
echo -------------------
curl -X GET "%API_URL%/etfs?skip=0&limit=5" ^
  -H "X-API-Key: %API_KEY%" ^
  -s
echo.
echo.

REM Test 3: Analytics Endpoints
echo Test 3: Example Overlap Query
echo -------------------
echo (Copy ETF IDs from Test 2 and use in this curl command:)
echo.
echo curl -X POST "%API_URL%/analytics/overlap" ^
  -H "X-API-Key: %API_KEY%" ^
  -H "Content-Type: application/json" ^
  -d "{\"etf_ids\": [\"id1\", \"id2\"]}"
echo.
echo.

echo ==================================
echo ✅ Basic tests completed!
echo ==================================
echo.
echo 📖 For interactive API exploration:
echo    - Swagger UI: %API_URL%/docs
echo    - ReDoc: %API_URL%/redoc
echo.
echo 📱 Frontend: http://localhost:3000
