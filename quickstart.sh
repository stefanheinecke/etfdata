#!/bin/bash

echo "🚀 ETF Analytics API - Quick Start"
echo "=================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

echo "✓ Docker found"

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed."
    exit 1
fi

echo "✓ Docker Compose found"
echo ""

# Build and start services
echo "📦 Building and starting services..."
docker-compose up --build -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check if services are running
echo ""
echo "🔍 Checking service health..."
echo ""

# Test Backend
echo -n "Backend API... "
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✓ Running on http://localhost:8000"
else
    echo "✗ Not responding"
fi

# Test Frontend
echo -n "Frontend... "
if curl -s http://localhost:3000 > /dev/null; then
    echo "✓ Running on http://localhost:3000"
else
    echo "✗ Not responding"
fi

# Test Database
echo -n "Database... "
if docker exec etfdata-db pg_isready -U postgres > /dev/null 2>&1; then
    echo "✓ Connected"
else
    echo "✗ Not responding"
fi

echo ""
echo "=================================="
echo "✅ ETF Analytics API is ready!"
echo "=================================="
echo ""
echo "📱 Access Points:"
echo "  - Frontend Dashboard: http://localhost:3000"
echo "  - API: http://localhost:8000"
echo "  - API Docs (Swagger): http://localhost:8000/docs"
echo "  - Alternative Docs (ReDoc): http://localhost:8000/redoc"
echo ""
echo "📊 Features:"
echo "  - 15 Sample ETFs (auto-seeded)"
echo "  - Overlap Analysis"
echo "  - Portfolio Exposure"
echo "  - ETF Similarity Search"
echo ""
echo "🛑 To stop services:"
echo "  docker-compose down"
echo ""
echo "📖 Full documentation: See README.md"
