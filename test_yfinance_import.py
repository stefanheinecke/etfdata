#!/usr/bin/env python3
"""
Test script to verify yfinance ISIN price fetching works for LU0136234068.

This script tests the /admin/etf/import-data endpoint with a sample ETF.
"""

import requests
import json
from datetime import date as date_type

# Configuration
ADMIN_SECRET = "your_admin_secret_here"  # Get from Railway environment
API_BASE_URL = "http://localhost:8000"  # Change to Railway URL after deployment

def test_etf_import():
    """Test importing an ETF with yfinance price fetching."""
    
    headers = {
        "X-Admin-Secret": ADMIN_SECRET,
        "Content-Type": "application/json",
    }
    
    # Sample ETF data for LU0136234068 (Amundi MSCI World ETF)
    import_data = {
        "metadata": {
            "isin": "LU0136234068",
            "name": "Amundi MSCI World ETF",
            "provider": "Amundi",
            "domicile": "LU",
            "ter": 0.38,
            "currency": "USD",
        },
        "holdings": [
            {
                "instrument_name": "Apple Inc",
                "instrument_isin": "US0378331005",
                "weight": 7.5,
                "sector": "Technology",
                "country": "US",
            },
            {
                "instrument_name": "Microsoft Corp",
                "instrument_isin": "US5949181045",
                "weight": 6.2,
                "sector": "Technology",
                "country": "US",
            },
        ],
        "date": date_type.today().isoformat(),
        "eodhd_symbol": None,  # Test fallback to yfinance
    }
    
    print("[TEST] Importing ETF LU0136234068...")
    print(f"[TEST] Endpoint: POST {API_BASE_URL}/admin/etf/import-data")
    print(f"[TEST] Payload: {json.dumps(import_data, indent=2)}")
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/admin/etf/import-data",
            json=import_data,
            headers=headers,
            timeout=60,
        )
        
        print(f"[TEST] Status: {response.status_code}")
        result = response.json()
        print(f"[TEST] Response: {json.dumps(result, indent=2)}")
        
        if response.status_code == 200:
            etf_info = result.get("etf", {})
            if etf_info.get("price_count", 0) > 0:
                print(f"\n✅ SUCCESS!")
                print(f"   - Fetched {etf_info['price_count']} prices from {etf_info['price_source']}")
                return True
            else:
                print(f"\n❌ FAILED: No prices fetched")
                print(f"   - Error: {etf_info.get('price_error')}")
                return False
        else:
            print(f"\n❌ HTTP Error: {response.status_code}")
            return False
    
    except Exception as e:
        print(f"\n❌ Exception: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    test_etf_import()
