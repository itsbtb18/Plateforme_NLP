"""
2FA OTP Utilities - Redis-based OTP storage and verification.

Security properties:
- OTP is stored as SHA-256 hash with server-side pepper.
- Verification uses constant-time comparison.
- Failed attempts are tracked per OTP.
- Lockout is enforced after repeated failures.
"""

import hashlib
import hmac
import json
import logging
import secrets
import string
from base64 import b64encode
from io import BytesIO
from datetime import datetime, timedelta

import pyotp
import qrcode
import redis
from django.conf import settings
from django.utils.translation import get_language

logger = logging.getLogger(__name__)


class OTPLockedOut(Exception):
    """Raised when OTP verification is locked after too many failed attempts."""


# Redis connection
redis_client = redis.StrictRedis(
    host=getattr(settings, "REDIS_HOST", "redis"),
    port=getattr(settings, "REDIS_PORT", 6379),
    db=getattr(settings, "REDIS_DB", 0),
    password=getattr(settings, "REDIS_PASSWORD", None),
    decode_responses=True,
)


# Cooldown period between OTP requests (seconds)
OTP_COOLDOWN_SECONDS = 60
OTP_MAX_ATTEMPTS = 5
OTP_LOCKOUT_SECONDS = 900  # 15 minutes


def _otp_pepper() -> str:
    pepper = getattr(settings, "OTP_PEPPER", "")
    if not pepper:
        raise RuntimeError("OTP_PEPPER is not configured in Django settings.")
    return pepper


def _hash_otp(otp_code: str) -> str:
    payload = f"{_otp_pepper()}:{otp_code}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _otp_msg(key: str) -> str:
    """Return localized OTP messages without relying on .po availability."""
    is_ar = (get_language() or "").startswith("ar")
    ar = {
        "expired": "انتهت صلاحية رمز التحقق. يرجى طلب رمز جديد.",
        "verified": "تم التحقق من الرمز بنجاح.",
        "invalid": "رمز التحقق غير صحيح. يرجى المحاولة مرة أخرى.",
        "error": "حدث خطأ. يرجى المحاولة مرة أخرى.",
        "locked": "تم قفل التحقق مؤقتاً بعد محاولات فاشلة متعددة. حاول لاحقاً.",
    }
    en = {
        "expired": "OTP expired. Please request a new one.",
        "verified": "OTP verified successfully.",
        "invalid": "Invalid OTP code. Please try again.",
        "error": "An error occurred. Please try again.",
        "locked": "Too many failed attempts. OTP verification is temporarily locked.",
    }
    return ar[key] if is_ar else en[key]


def generate_otp(length: int = 6) -> str:
    """Generate a cryptographically secure numeric OTP."""
    return "".join(secrets.choice(string.digits) for _ in range(length))


def _get_otp_key(user_id: str) -> str:
    return f"otp:{user_id}"


def _get_lock_key(user_id: str) -> str:
    return f"otp_lock:{user_id}"


def _get_cooldown_key(user_id: str) -> str:
    return f"otp_cooldown:{user_id}"


def check_otp_cooldown(user_id: str):
    """
    Check if user is still in cooldown period for OTP requests.

    Returns:
        dict: {'can_request': bool, 'remaining_seconds': int}
    """
    cooldown_key = _get_cooldown_key(user_id)
    try:
        ttl = redis_client.ttl(cooldown_key)
        if ttl > 0:
            return {"can_request": False, "remaining_seconds": ttl}
        return {"can_request": True, "remaining_seconds": 0}
    except Exception as exc:
        logger.error("Error checking OTP cooldown: %s", exc)
        return {"can_request": True, "remaining_seconds": 0}


def _is_locked(user_id: str) -> bool:
    lock_key = _get_lock_key(user_id)
    return bool(redis_client.exists(lock_key))


def store_otp(user_id: str, otp_code: str, ttl_minutes: int = 5) -> bool:
    """
    Store OTP hash in Redis with TTL and reset attempts for this OTP.

    Args:
        user_id: UUID of the user
        otp_code: Raw OTP code to hash and store
        ttl_minutes: OTP validity duration in minutes
    """
    key = _get_otp_key(user_id)
    cooldown_key = _get_cooldown_key(user_id)
    ttl_seconds = ttl_minutes * 60

    payload = {
        "otp_hash": _hash_otp(otp_code),
        "attempts": 0,
        "created_at": datetime.now().isoformat(),
        "expiry": (datetime.now() + timedelta(minutes=ttl_minutes)).isoformat(),
    }

    try:
        redis_client.setex(key, ttl_seconds, json.dumps(payload))
        redis_client.setex(cooldown_key, OTP_COOLDOWN_SECONDS, "1")
        return True
    except Exception as exc:
        logger.error("Error storing OTP: %s", exc)
        return False


def verify_otp(user_id: str, submitted_code: str):
    """
    Verify submitted OTP against stored hash.

    Raises:
        OTPLockedOut: if user reached max failed attempts and lock is active.
    """
    key = _get_otp_key(user_id)
    lock_key = _get_lock_key(user_id)

    try:
        if _is_locked(user_id):
            raise OTPLockedOut(_otp_msg("locked"))

        stored_data = redis_client.get(key)
        if not stored_data:
            return {"valid": False, "message": _otp_msg("expired")}

        data = json.loads(stored_data)
        stored_hash = data.get("otp_hash", "")
        attempts = int(data.get("attempts", 0))
        expiry_raw = data.get("expiry")

        if not expiry_raw:
            redis_client.delete(key)
            return {"valid": False, "message": _otp_msg("expired")}

        expiry = datetime.fromisoformat(expiry_raw)
        if datetime.now() > expiry:
            redis_client.delete(key)
            return {"valid": False, "message": _otp_msg("expired")}

        submitted_hash = _hash_otp(submitted_code.strip())
        if hmac.compare_digest(submitted_hash, stored_hash):
            redis_client.delete(key)
            return {"valid": True, "message": _otp_msg("verified")}

        attempts += 1
        ttl_remaining = redis_client.ttl(key)
        if ttl_remaining <= 0:
            ttl_remaining = 1

        if attempts >= OTP_MAX_ATTEMPTS:
            redis_client.setex(lock_key, OTP_LOCKOUT_SECONDS, "1")
            redis_client.delete(key)
            raise OTPLockedOut(_otp_msg("locked"))

        data["attempts"] = attempts
        redis_client.setex(key, ttl_remaining, json.dumps(data))
        return {"valid": False, "message": _otp_msg("invalid")}

    except OTPLockedOut:
        raise
    except Exception as exc:
        logger.error("Error verifying OTP: %s", exc)
        return {"valid": False, "message": _otp_msg("error")}


def get_otp_expiry(user_id: str):
    """
    Get OTP expiry info.

    Returns:
        dict: {'expiry': datetime|None, 'remaining_seconds': int}
    """
    key = _get_otp_key(user_id)
    try:
        ttl = redis_client.ttl(key)
        if ttl == -2:
            return {"expiry": None, "remaining_seconds": 0}
        if ttl == -1:
            return {"expiry": None, "remaining_seconds": -1}
        expiry = datetime.now() + timedelta(seconds=ttl)
        return {"expiry": expiry, "remaining_seconds": ttl}
    except Exception as exc:
        logger.error("Error getting OTP expiry: %s", exc)
        return {"expiry": None, "remaining_seconds": 0}


def clear_otp(user_id: str) -> bool:
    """Clear OTP key for a user."""
    key = _get_otp_key(user_id)
    try:
        redis_client.delete(key)
        return True
    except Exception as exc:
        logger.error("Error clearing OTP: %s", exc)
        return False


def resend_otp(user_id: str, otp_code: str, ttl_minutes: int = 5) -> bool:
    """
    Resend flow:
    - clears current OTP key
    - stores a fresh OTP hash payload
    """
    key = _get_otp_key(user_id)
    try:
        redis_client.delete(key)
    except Exception as exc:
        logger.warning("Error deleting old OTP before resend: %s", exc)

    return store_otp(user_id, otp_code, ttl_minutes=ttl_minutes)


def send_otp(user, ttl_minutes: int = 5) -> bool:
    """
    Generate, store, and email an OTP for a user.
    """
    from .two_factor_email import send_otp_email

    otp_code = generate_otp()
    if not store_otp(str(user.id), otp_code, ttl_minutes=ttl_minutes):
        return False
    return bool(send_otp_email(user.email, user.get_full_name(), otp_code))


def setup_totp(user):
    """
    Generate and persist a TOTP secret for the user, then return provisioning data.

    Returns:
        dict: {'secret': str, 'provisioning_uri': str, 'qr_code_base64': str}
    """
    from .two_factor_models import TwoFactorAuth

    two_fa, _ = TwoFactorAuth.objects.get_or_create(user=user)
    secret = pyotp.random_base32()

    two_fa.totp_secret = secret
    two_fa.method = TwoFactorAuth.METHOD_TOTP
    two_fa.save(update_fields=["totp_secret", "method", "updated_at"])

    issuer = getattr(settings, "TOTP_ISSUER_NAME", "Plateforme NLP")
    account_name = user.email or str(user.pk)
    provisioning_uri = pyotp.TOTP(secret).provisioning_uri(
        name=account_name,
        issuer_name=issuer,
    )

    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    qr_code_base64 = b64encode(buffer.getvalue()).decode("utf-8")

    return {
        "secret": secret,
        "provisioning_uri": provisioning_uri,
        "qr_code_base64": qr_code_base64,
    }


def verify_totp(user, token: str) -> bool:
    """
    Verify a TOTP code with a ±1-step grace window.
    """
    from .two_factor_models import TwoFactorAuth

    try:
        two_fa = TwoFactorAuth.objects.get(user=user)
    except TwoFactorAuth.DoesNotExist:
        return False

    if not two_fa.totp_secret:
        return False

    totp = pyotp.TOTP(two_fa.totp_secret)
    return bool(totp.verify((token or "").strip(), valid_window=1))


def _backup_code_hash(code: str) -> str:
    normalized = (code or "").strip().upper()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def generate_backup_codes(user):
    """
    Generate 10 one-time backup codes, store only hashes, and return plaintext once.
    """
    from .two_factor_models import TwoFactorAuth

    two_fa, _ = TwoFactorAuth.objects.get_or_create(user=user)

    plaintext_codes = [secrets.token_hex(5).upper() for _ in range(10)]
    hashed_codes = [_backup_code_hash(code) for code in plaintext_codes]

    two_fa.backup_codes = hashed_codes
    two_fa.save(update_fields=["backup_codes", "updated_at"])
    return plaintext_codes


def verify_backup_code(user, submitted_code: str) -> bool:
    """
    Verify a submitted backup code, consume it on success, and persist the remaining hashes.
    """
    from .two_factor_models import TwoFactorAuth

    try:
        two_fa = TwoFactorAuth.objects.get(user=user)
    except TwoFactorAuth.DoesNotExist:
        return False

    submitted_hash = _backup_code_hash(submitted_code)

    codes = two_fa.backup_codes or []
    if isinstance(codes, str):
        try:
            codes = json.loads(codes)
        except (TypeError, ValueError):
            codes = []

    if submitted_hash not in codes:
        return False

    updated_codes = list(codes)
    updated_codes.remove(submitted_hash)
    two_fa.backup_codes = updated_codes
    two_fa.save(update_fields=["backup_codes", "updated_at"])
    return True
