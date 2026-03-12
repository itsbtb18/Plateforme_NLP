"""
2FA OTP Utilities - Redis-based OTP storage and verification
"""
import redis
import secrets
import string
from django.conf import settings
from django.utils.translation import get_language
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)

# Redis connection
redis_client = redis.StrictRedis(
    host=getattr(settings, 'REDIS_HOST', 'redis'),
    port=getattr(settings, 'REDIS_PORT', 6379),
    db=getattr(settings, 'REDIS_DB', 0),
    password=getattr(settings, 'REDIS_PASSWORD', None),
    decode_responses=True
)

# Cooldown period between OTP requests (seconds)
OTP_COOLDOWN_SECONDS = 60


def _otp_msg(key: str) -> str:
    """Return localized OTP messages without relying on .po availability."""
    is_ar = (get_language() or "").startswith("ar")
    ar = {
        "expired": "انتهت صلاحية رمز التحقق. يرجى طلب رمز جديد.",
        "verified": "تم التحقق من الرمز بنجاح.",
        "invalid": "رمز التحقق غير صحيح. يرجى المحاولة مرة أخرى.",
        "error": "حدث خطأ. يرجى المحاولة مرة أخرى.",
    }
    en = {
        "expired": "OTP expired. Please request a new one.",
        "verified": "OTP verified successfully.",
        "invalid": "Invalid OTP code. Please try again.",
        "error": "An error occurred. Please try again.",
    }
    return ar[key] if is_ar else en[key]

def generate_otp(length=6):
    """
    Generate a cryptographically secure random 6-digit OTP
    """
    return ''.join(secrets.choice(string.digits) for _ in range(length))

def _get_cooldown_key(user_id):
    """Get Redis key for OTP cooldown tracking."""
    return f"otp_cooldown:{user_id}"

def check_otp_cooldown(user_id):
    """
    Check if user is still in cooldown period for OTP requests.
    
    Returns:
        dict: {'can_request': bool, 'remaining_seconds': int}
    """
    cooldown_key = _get_cooldown_key(user_id)
    try:
        ttl = redis_client.ttl(cooldown_key)
        if ttl > 0:
            return {'can_request': False, 'remaining_seconds': ttl}
        return {'can_request': True, 'remaining_seconds': 0}
    except Exception as e:
        logger.error(f"Error checking OTP cooldown: {e}")
        return {'can_request': True, 'remaining_seconds': 0}

def store_otp(user_id, otp_code, ttl_minutes=5):
    """
    Store OTP in Redis with TTL (Time To Live).
    Also sets a cooldown to prevent rapid re-requests.
    
    Args:
        user_id: UUID of the user
        otp_code: The OTP code to store
        ttl_minutes: How long the OTP is valid (default 5 minutes)
    
    Returns:
        bool: True if stored successfully
    """
    key = f"otp:{user_id}"
    cooldown_key = _get_cooldown_key(user_id)
    ttl_seconds = ttl_minutes * 60
    
    data = {
        'code': otp_code,
        'created_at': datetime.now().isoformat(),
        'expiry': (datetime.now() + timedelta(minutes=ttl_minutes)).isoformat()
    }
    
    try:
        redis_client.setex(key, ttl_seconds, json.dumps(data))
        # Set cooldown to prevent requesting another OTP too quickly
        redis_client.setex(cooldown_key, OTP_COOLDOWN_SECONDS, '1')
        return True
    except Exception as e:
        logger.error(f"Error storing OTP: {e}")
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
                'message': _otp_msg('expired')
            }
        
        data = json.loads(stored_data)
        stored_code = data['code']
        expiry = datetime.fromisoformat(data['expiry'])
        
        # Check if OTP has expired
        if datetime.now() > expiry:
            redis_client.delete(key)
            return {
                'valid': False,
                'message': _otp_msg('expired')
            }
        
        # Check if code matches
        if submitted_code.strip() == stored_code:
            redis_client.delete(key)  # Delete OTP after successful verification
            return {
                'valid': True,
                'message': _otp_msg('verified')
            }
        else:
            return {
                'valid': False,
                'message': _otp_msg('invalid')
            }
    
    except Exception as e:
        logger.error(f"Error verifying OTP: {e}")
        return {
            'valid': False,
            'message': _otp_msg('error')
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
        logger.error(f"Error getting OTP expiry: {e}")
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
        logger.error(f"Error clearing OTP: {e}")
        return False
