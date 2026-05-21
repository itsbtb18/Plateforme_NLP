#!/usr/bin/env python
"""Test script for CV extraction endpoint"""
import requests
import json
import time

def test_cv_extraction():
    """Test the CV extraction endpoint"""
    print("Testing CV extraction endpoint...")
    print("=" * 60)
    
    # Test 1: Health check
    print("\n1. Health check...")
    try:
        response = requests.get("http://localhost:8001/health", timeout=5)
        print(f"   ✓ Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False
    
    # Test 2: Try with a real PDF
    print("\n2. Testing CV extraction with PDF...")
    pdf_path = r"rapport\main.pdf"
    try:
        with open(pdf_path, 'rb') as f:
            print(f"   Uploading {pdf_path}...")
            response = requests.post(
                "http://localhost:8001/extract-cv-signup/",
                files={'file': (pdf_path, f, 'application/pdf')},
                timeout=120
            )
        
        print(f"   ✓ Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Success! Extracted data:")
            print(json.dumps(data, indent=2, ensure_ascii=False)[:500])
        else:
            print(f"   ✗ Error: {response.text[:200]}")
    
    except requests.exceptions.Timeout:
        print(f"   ⚠ Request timed out (server may still be processing)")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n" + "=" * 60)
    print("Test complete!")

if __name__ == "__main__":
    test_cv_extraction()
