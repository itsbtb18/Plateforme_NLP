"""
2FA OTP Utilities - Redis-based OTP storage and verification
"""
import redis
import random
import string
from django.conf import settings
from datetime import datetime, timedelta
import json

# Redis connection
redis_client = redis.StrictRedis(
    host=getattr(settings, 'REDIS_HOST', 'redis'),
    port=getattr(settings, 'REDIS_PORT', 6379),
    db=getattr(settings, 'REDIS_DB', 0),
    password=getattr(settings, 'REDIS_PASSWORD', None),
    decode_responses=True
)

def generate_otp(length=6):
    """
    Generate a random 6-digit OTP
    """
    return ''.join(random.choices(string.digits, k=length))

def store_otp(user_id, otp_code, ttl_minutes=5):
    """
    Store OTP in Redis with TTL (Time To Live)
    
    Args:
        user_id: UUID of the user
        otp_code: The OTP code to store
        ttl_minutes: How long the OTP is valid (default 5 minutes)
    
    Returns:
        bool: True if stored successfully
    """
    key = f"otp:{user_id}"
    ttl_seconds = ttl_minutes * 60
    
    data = {
        'code': otp_code,
        'created_at': datetime.now().isoformat(),
        'expiry': (datetime.now() + timedelta(minutes=ttl_minutes)).isoformat()
    }
    
    try:
        redis_client.setex(key, ttl_seconds, json.dumps(data))
        return True
    except Exception as e:
        print(f"Error storing OTP: {e}")
        return False

def verify_otp(user_id, submitted_code):
    """
    Verify if the submitted OTP matches the stored one
    
    Args:
        user_id: UUID of the user
        submitted_code: The code entered by the user
    
    Returns:
        dict: {'valid': bool, 'message': str}
    """
    key = f"otp:{user_id}"
    
    try:
        stored_data = redis_client.get(key)
        
        if not stored_data:
            return {
                'valid': False,
                'message': 'OTP expired. Please request a new one.'
            }
        
        data = json.loads(stored_data)
        stored_code = data['code']
        expiry = datetime.fromisoformat(data['expiry'])
        
        # Check if OTP has expired
        if datetime.now() > expiry:
            redis_client.delete(key)
            return {
                'valid': False,
                'message': 'OTP expired. Please request a new one.'
            }
        
        # Check if code matches
        if submitted_code.strip() == stored_code:
            redis_client.delete(key)  # Delete OTP after successful verification
            return {
                'valid': True,
                'message': 'OTP verified successfully.'
            }
        else:
            return {
                'valid': False,
                'message': 'Invalid OTP code. Please try again.'
            }
    
    except Exception as e:
        print(f"Error verifying OTP: {e}")
        return {
            'valid': False,
            'message': 'An error occurred. Please try again.'
        }

def get_otp_expiry(user_id):
    """
    Get the expiry time of the OTP for a user
    
    Returns:
        dict: {'expiry': datetime, 'remaining_seconds': int}
    """
    key = f"otp:{user_id}"
    
    try:
        ttl = redis_client.ttl(key)
        
        if ttl == -2:  # Key doesn't exist
            return {'expiry': None, 'remaining_seconds': 0}
        
        if ttl == -1:  # Key exists but has no expiry
            return {'expiry': None, 'remaining_seconds': -1}
        
        expiry = datetime.now() + timedelta(seconds=ttl)
        return {
            'expiry': expiry,
            'remaining_seconds': ttl
        }
    except Exception as e:
        print(f"Error getting OTP expiry: {e}")
        return {'expiry': None, 'remaining_seconds': 0}

def clear_otp(user_id):
    """
    Clear OTP for a user (used after verification or cancellation)
    """
    key = f"otp:{user_id}"
    try:
        redis_client.delete(key)
        return True
    except Exception as e:
        print(f"Error clearing OTP: {e}")
        return False
