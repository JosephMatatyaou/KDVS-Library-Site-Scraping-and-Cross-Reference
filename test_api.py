#!/usr/bin/env python3
"""Debug test script to check API connectivity and data fetching."""

import requests
from datetime import datetime

API_BASE_URL = "https://library.kdvs.org/api/library/albums/"

print("🔍 Testing KDVS API Connection...")
print("-" * 50)

try:
    # Test 1: Basic API connectivity
    print("1. Testing basic API connection...")
    params = {
        "tracking_end_date__gte": "2026-01-01",
        "limit": 5,
        "page": 1,
    }
    
    print(f"   URL: {API_BASE_URL}")
    print(f"   Params: {params}")
    print("   Sending request...")
    
    response = requests.get(API_BASE_URL, params=params, timeout=10)
    response.raise_for_status()
    
    print(f"   ✅ Response status: {response.status_code}")
    
    data = response.json()
    print(f"   ✅ Got JSON back")
    print(f"   Total albums in database: {data.get('count', 'N/A')}")
    print(f"   Albums on this page: {len(data.get('results', []))}")
    
    if data.get('results'):
        first_album = data['results'][0]
        print(f"\n   Sample album:")
        print(f"     - Title: {first_album.get('title')}")
        print(f"     - Artist: {first_album.get('artists')}")
        print(f"     - Created: {first_album.get('created')}")
    
    # Test 2: Check pagination
    print(f"\n2. Checking pagination...")
    if data.get('next'):
        print(f"   ✅ Next page exists: Yes")
    else:
        print(f"   ℹ️  No next page available")
    
    print("\n" + "=" * 50)
    print("✅ API is working! The app should work too.")
    print("=" * 50)
    
except requests.exceptions.Timeout:
    print(f"   ❌ Request timed out (API too slow)")
except requests.exceptions.ConnectionError:
    print(f"   ❌ Could not connect to API")
except Exception as e:
    print(f"   ❌ Error: {e}")
