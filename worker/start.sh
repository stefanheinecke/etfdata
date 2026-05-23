#!/bin/bash
set -e

echo "🚀 Starting ETF Analytics Worker..."

# Wait for database to be ready
echo "⏳ Waiting for database..."
while ! nc -z $DATABASE_HOST 5432; do
  sleep 1
done
echo "✓ Database is ready"

# Start the worker
echo "🎯 Starting ETL Worker/Scheduler..."
exec python app/main.py
