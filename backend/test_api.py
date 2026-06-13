"""
Test script for H2Open API
Run this after starting the server to verify everything works
"""
import requests
import json
from datetime import datetime

API_BASE = "http://localhost:8000/api/v1"

def print_response(name, response):
    """Pretty print API response"""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"Status Code: {response.status_code}")
    try:
        print(f"Response:\n{json.dumps(response.json(), indent=2)}")
    except:
        print(f"Response: {response.text}")
    print(f"{'='*60}")


def test_health():
    """Test health check endpoint"""
    response = requests.get("http://localhost:8000/health")
    print_response("Health Check", response)
    return response.status_code == 200


def test_create_reading():
    """Test creating a sensor reading"""
    data = {
        "buoy_id": "buoy_001",
        "ecoli_cfu": 180.5,
        "temperature": 22.3,
        "ph": 7.2,
        "latitude": 42.3601,
        "longitude": -71.0942
    }
    response = requests.post(f"{API_BASE}/readings", json=data)
    print_response("Create Reading (Safe Water)", response)
    return response.status_code == 201


def test_create_unsafe_reading():
    """Test creating a reading with high E. coli (unsafe)"""
    data = {
        "buoy_id": "buoy_002",
        "ecoli_cfu": 350.0,  # Above EPA threshold
        "temperature": 21.5,
        "latitude": 42.3605,
        "longitude": -71.0950
    }
    response = requests.post(f"{API_BASE}/readings", json=data)
    print_response("Create Reading (Unsafe Water)", response)
    return response.status_code == 201


def test_get_readings():
    """Test getting all readings"""
    response = requests.get(f"{API_BASE}/readings")
    print_response("Get All Readings", response)
    return response.status_code == 200


def test_get_readings_filtered():
    """Test getting readings with filter"""
    response = requests.get(f"{API_BASE}/readings?buoy_id=buoy_001&limit=10")
    print_response("Get Filtered Readings", response)
    return response.status_code == 200


def test_check_safety():
    """Test water safety check"""
    response = requests.get(f"{API_BASE}/safety/buoy_001")
    print_response("Check Water Safety", response)
    return response.status_code == 200


def test_get_buoy_status():
    """Test getting buoy status"""
    response = requests.get(f"{API_BASE}/status/buoy_001")
    print_response("Get Buoy Status", response)
    return response.status_code == 200


def test_get_all_buoys():
    """Test getting all buoy IDs"""
    response = requests.get(f"{API_BASE}/buoys")
    print_response("Get All Buoy IDs", response)
    return response.status_code == 200


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("H2OPEN API TEST SUITE")
    print("="*60)
    
    tests = [
        ("Health Check", test_health),
        ("Create Safe Reading", test_create_reading),
        ("Create Unsafe Reading", test_create_unsafe_reading),
        ("Get All Readings", test_get_readings),
        ("Get Filtered Readings", test_get_readings_filtered),
        ("Check Water Safety", test_check_safety),
        ("Get Buoy Status", test_get_buoy_status),
        ("Get All Buoys", test_get_all_buoys),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n❌ ERROR in {name}: {e}")
            results.append((name, False))
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} tests passed")
    print("="*60 + "\n")


if __name__ == "__main__":
    try:
        run_all_tests()
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to API")
        print("Make sure the server is running:")
        print("  python main.py")
        print("\nThen run this test script again.\n")
