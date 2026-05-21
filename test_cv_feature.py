#!/usr/bin/env python3
"""
Test script to verify CV extraction service is working correctly.
Run this to ensure all dependencies are installed and configured.
"""

import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=r"D:\Plateforme_NLP\.env.example", override=True)
import sys
from pathlib import Path

def check_imports():
    """Check if all required packages are installed"""
    print("🔍 Checking imports...")
    
    required_packages = {
        'docling': 'Document conversion library',
        'docling_core': 'Docling core types',
        'groq': 'Groq API client',
    }
    
    missing = []
    for package, description in required_packages.items():
        try:
            __import__(package)
            print(f"  ✅ {package}: {description}")
        except ImportError:
            print(f"  ❌ {package}: {description} - NOT INSTALLED")
            missing.append(package)
    
    return missing

def check_env_variables():
    """Check if required environment variables are set"""
    print("\n🔍 Checking environment variables...")
    
    required_vars = {
        'GROQ_CV_SIGNUP_API_KEY': 'Groq API key for CV signup',
        'GROQ_CV_SIGNUP_MODEL': 'Groq model for CV processing',
    }
    
    missing = []
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            # Show masked value for security
            masked = value[:20] + '...' if len(value) > 20 else value
            print(f"  ✅ {var}: {description}")
            print(f"     Value: {masked}")
        else:
            print(f"  ❌ {var}: {description} - NOT SET")
            missing.append(var)
    
    return missing

def check_groq_connection():
    """Test Groq API connection"""
    print("\n🔍 Testing Groq connection...")
    
    api_key = os.getenv('GROQ_CV_SIGNUP_API_KEY')
    if not api_key:
        print("  ⚠️  Skipping - API key not configured")
        return False
    
    try:
        from groq import Groq
        
        client = Groq(api_key=api_key)
        
        # Send a simple test message
        message = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            max_tokens=100,
            messages=[{
                'role': 'user',
                'content': 'Return only: {"status": "ok"}'
            }]
        )
        
        print(f"  ✅ Groq API connection successful")
        print(f"     Model: {message.model}")
        return True
        
    except Exception as e:
        print(f"  ❌ Groq API connection failed: {str(e)}")
        return False

def check_cv_service():
    """Check if CV extraction service can be imported"""
    print("\n🔍 Checking CV extraction service...")
    
    try:
        # Add parent directories to path
        sys.path.insert(0, str(Path(__file__).parent / 'fastapi_chatbot'))
        
        from app.services.cv_extraction_service import CVExtractionService
        print("  ✅ CV extraction service imported successfully")
        
        # Try to instantiate
        service = CVExtractionService()
        print("  ✅ CV extraction service instantiated")
        
        return True
        
    except ImportError as e:
        print(f"  ❌ Failed to import CV service: {str(e)}")
        return False
    except Exception as e:
        print(f"  ⚠️  CV service check failed: {str(e)}")
        return False

def main():
    print("=" * 50)
    print("CV Signup Feature - Configuration Check")
    print("=" * 50)
    
    # Run all checks
    missing_imports = check_imports()
    missing_env = check_env_variables()
    groq_ok = check_groq_connection()
    service_ok = check_cv_service()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Summary")
    print("=" * 50)
    
    all_ok = True
    
    if missing_imports:
        print(f"❌ Missing packages: {', '.join(missing_imports)}")
        print("   Install with: pip install " + " ".join(missing_imports))
        all_ok = False
    else:
        print("✅ All packages installed")
    
    if missing_env:
        print(f"❌ Missing environment variables: {', '.join(missing_env)}")
        print("   Update your .env file")
        all_ok = False
    else:
        print("✅ All environment variables configured")
    
    if groq_ok:
        print("✅ Groq API connection working")
    else:
        print("⚠️  Groq API connection failed")
        all_ok = False
    
    if service_ok:
        print("✅ CV extraction service ready")
    else:
        print("⚠️  CV extraction service check failed")
    
    if all_ok:
        print("\n🎉 All checks passed! Feature is ready to use.")
        return 0
    else:
        print("\n⚠️  Some checks failed. See above for details.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
