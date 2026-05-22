#!/bin/bash

echo "🔍 ETF Analytics API - Setup Verification"
echo "========================================"
echo ""

PASS=0
FAIL=0

# Check Docker
echo -n "Checking Docker installation... "
if command -v docker &> /dev/null; then
    echo "✓"
    ((PASS++))
else
    echo "✗"
    ((FAIL++))
fi

# Check Docker Compose
echo -n "Checking Docker Compose... "
if docker-compose --version &> /dev/null; then
    echo "✓"
    ((PASS++))
else
    echo "✗"
    ((FAIL++))
fi

# Check if containers running
echo -n "Checking if containers are running... "
if docker ps | grep -q etfdata; then
    echo "✓"
    ((PASS++))
else
    echo "✗ (Run 'docker-compose up' first)"
    ((FAIL++))
fi

# Check Backend
echo -n "Checking Backend API (port 8000)... "
if curl -s http://localhost:8000/health -H "X-API-Key: test-key" > /dev/null 2>&1; then
    echo "✓"
    ((PASS++))
else
    echo "✗"
    ((FAIL++))
fi

# Check Frontend
echo -n "Checking Frontend (port 3000)... "
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo "✓"
    ((PASS++))
else
    echo "✗"
    ((FAIL++))
fi

# Check Database
echo -n "Checking Database... "
if docker exec etfdata-db pg_isready -U postgres > /dev/null 2>&1; then
    echo "✓"
    ((PASS++))
else
    echo "✗"
    ((FAIL++))
fi

# Count ETFs
echo -n "Checking if ETFs are seeded... "
ETF_COUNT=$(curl -s -X GET "http://localhost:8000/etfs?limit=100" -H "X-API-Key: test-key" 2>/dev/null | grep -o '"id"' | wc -l)
if [ "$ETF_COUNT" -gt 0 ]; then
    echo "✓ ($ETF_COUNT ETFs found)"
    ((PASS++))
else
    echo "✗"
    ((FAIL++))
fi

echo ""
echo "========================================"
echo "✅ Passed: $PASS / Checks run: $(($PASS + $FAIL))"

if [ $FAIL -gt 0 ]; then
    echo "❌ Failed: $FAIL"
    echo ""
    echo "To fix:"
    echo "1. Make sure Docker is running"
    echo "2. Run: docker-compose up --build"
    echo "3. Wait 60 seconds for initialization"
    echo "4. Re-run this script"
    exit 1
else
    echo ""
    echo "🎉 All checks passed! Your setup is ready."
    echo ""
    echo "Next steps:"
    echo "  - Frontend: http://localhost:3000"
    echo "  - API Docs: http://localhost:8000/docs"
    echo "  - Enjoy! 🚀"
fi
