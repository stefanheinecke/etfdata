#!/bin/bash
set -e

echo "🚀 Starting ETF Analytics API Backend..."

# Wait for database to be ready
echo "⏳ Waiting for database..."
# Extract host and port from DATABASE_URL (postgresql://user:pass@host:port/db)
DB_HOST=$(echo "$DATABASE_URL" | sed -e 's|.*@||' -e 's|:.*||' -e 's|/.*||')
DB_PORT=$(echo "$DATABASE_URL" | sed -e 's|.*@[^:]*:||' -e 's|/.*||' -e 's|[^0-9].*||')
DB_PORT=${DB_PORT:-5432}
TIMEOUT=60
ELAPSED=0
while ! nc -z "$DB_HOST" "$DB_PORT"; do
  if [ $ELAPSED -ge $TIMEOUT ]; then
    echo "⚠ Database not reachable after ${TIMEOUT}s, starting anyway..."
    break
  fi
  sleep 1
  ELAPSED=$((ELAPSED + 1))
done
echo "✓ Database is ready"

# Initialize database
echo "📊 Initializing database..."
python -c "from app.db.database import init_db; init_db()"
echo "✓ Database initialized"

# Start the application
echo "🎯 Starting Uvicorn server..."
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT
