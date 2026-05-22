#!/bin/bash

# ETF Analytics API - Test Script

API_URL="http://localhost:8000"
API_KEY="test-key"

echo "🧪 ETF Analytics API - Test Suite"
echo "=================================="
echo ""

# Test 1: Health Check
echo "Test 1: Health Check"
echo "-------------------"
curl -X GET "$API_URL/health" \
  -H "X-API-Key: $API_KEY" \
  -s | jq .
echo ""

# Test 2: Get All ETFs
echo "Test 2: Get All ETFs"
echo "-------------------"
curl -X GET "$API_URL/etfs?skip=0&limit=5" \
  -H "X-API-Key: $API_KEY" \
  -s | jq .
echo ""

# Extract first ETF ID for further tests
ETF_ID=$(curl -s -X GET "$API_URL/etfs?skip=0&limit=1" \
  -H "X-API-Key: $API_KEY" | jq -r '.[0].id' 2>/dev/null)

if [ ! -z "$ETF_ID" ] && [ "$ETF_ID" != "null" ]; then
  echo "Using ETF ID: $ETF_ID"
  echo ""

  # Test 3: Get Holdings
  echo "Test 3: Get Holdings"
  echo "-------------------"
  curl -X GET "$API_URL/etfs/$ETF_ID/holdings" \
    -H "X-API-Key: $API_KEY" \
    -s | jq '.[0:3]'
  echo ""

  # Test 4: Get Allocations
  echo "Test 4: Get Allocations"
  echo "-------------------"
  curl -X GET "$API_URL/etfs/$ETF_ID/allocations?type=sector" \
    -H "X-API-Key: $API_KEY" \
    -s | jq '.[0:3]'
  echo ""

  # Test 5: Find Similar ETFs
  echo "Test 5: Find Similar ETFs"
  echo "-------------------"
  curl -X GET "$API_URL/analytics/similar/$ETF_ID?top_n=3" \
    -H "X-API-Key: $API_KEY" \
    -s | jq .
  echo ""

  # Get second ETF for overlap test
  ETF_ID_2=$(curl -s -X GET "$API_URL/etfs?skip=1&limit=1" \
    -H "X-API-Key: $API_KEY" | jq -r '.[0].id' 2>/dev/null)

  if [ ! -z "$ETF_ID_2" ] && [ "$ETF_ID_2" != "null" ]; then
    echo "Using second ETF ID: $ETF_ID_2"
    echo ""

    # Test 6: Overlap Analysis
    echo "Test 6: Overlap Analysis"
    echo "-------------------"
    curl -X POST "$API_URL/analytics/overlap" \
      -H "X-API-Key: $API_KEY" \
      -H "Content-Type: application/json" \
      -d "{\"etf_ids\": [\"$ETF_ID\", \"$ETF_ID_2\"]}" \
      -s | jq .
    echo ""

    # Test 7: Portfolio Exposure
    echo "Test 7: Portfolio Exposure"
    echo "-------------------"
    curl -X POST "$API_URL/analytics/exposure" \
      -H "X-API-Key: $API_KEY" \
      -H "Content-Type: application/json" \
      -d "{\"portfolio\": [{\"etf_id\": \"$ETF_ID\", \"weight\": 60}, {\"etf_id\": \"$ETF_ID_2\", \"weight\": 40}]}" \
      -s | jq .
    echo ""
  fi
else
  echo "❌ Could not retrieve ETF IDs. Make sure the API is running."
  exit 1
fi

echo "=================================="
echo "✅ All tests completed!"
echo ""
echo "📖 For interactive API exploration:"
echo "   - Swagger UI: http://localhost:8000/docs"
echo "   - ReDoc: http://localhost:8000/redoc"
