#!/bin/bash
set -e

echo "🚀 Starting ETF Analytics API Backend..."

# Initialize database
echo "📊 Initializing database..."
python -c "from app.db.database import init_db; init_db()" || echo "⚠ init_db failed, continuing..."
echo "✓ Database initialized"

# Start the application
echo "🎯 Starting Uvicorn server..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
