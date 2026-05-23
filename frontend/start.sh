#!/bin/bash
set -e

echo "🚀 Starting ETF Analytics Frontend..."

# Build the app
echo "📦 Building Vue application..."
npm run build

# Start the server
echo "🎯 Starting frontend server..."
exec npx serve -s dist -l 3000
