#!/bin/bash
set -e

echo "🚀 Starting ETF Analytics API Backend..."

# Wait for database to be ready
echo "⏳ Waiting for database..."
while ! nc -z $DATABASE_HOST 5432; do
  sleep 1
done
echo "✓ Database is ready"

# Initialize database
echo "📊 Initializing database..."
python -c "from app.db.database import init_db; init_db()"
echo "✓ Database initialized"

# Start the application
echo "🎯 Starting Uvicorn server..."
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT
