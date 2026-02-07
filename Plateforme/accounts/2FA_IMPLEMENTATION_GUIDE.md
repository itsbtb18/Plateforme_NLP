<!-- 2FA_IMPLEMENTATION_GUIDE.md -->

# Two-Factor Authentication (2FA) Implementation Guide

## Overview
Email-based Two-Factor Authentication has been fully implemented for the Plateforme NLP platform. This guide explains the complete 2FA workflow and how to use it.

## Features
✅ **Email-based OTP (One-Time Password)**
- 6-digit security codes sent to user-registered email
- 5-minute validity period
- Automatic expiration via Redis

✅ **Redis-backed OTP Storage**
- Fast, in-memory storage with automatic TTL
- Scalable architecture for high-traffic environments
- Atomic operations for data integrity

✅ **Beautiful UI Components**
- Modern, standalone HTML templates (no CSS conflicts)
- Real-time countdown timer for code expiration
- Professional security-focused design

✅ **Complete User Management**
- Enable/disable 2FA from settings page
- Backup codes support (future enhancement)
- Session-based user tracking

---

## Implementation Details

### 1. **Database Model**
**File:** `accounts/two_factor_models.py`

```python
TwoFactorAuth Model
├── id (UUID, Primary Key)
├── user (OneToOneField -> CustomUser)
├── is_enabled (Boolean, default=False)
├── backup_codes (JSON Field, future use)
├── created_at (DateTime, auto_now_add)
└── updated_at (DateTime, auto_now)
```

**Migration:** `accounts/migrations/0006_twofactorauth.py`

### 2. **OTP Management Utilities**
**File:** `accounts/two_factor_utils.py`

#### Available Functions:

```python
# Generate a 6-digit OTP code
otp_code = generate_otp(length=6)

# Store OTP in Redis with 5-min TTL
store_otp(user_id="uuid-string", otp_code="123456", ttl_minutes=5)

# Verify OTP and auto-delete on success
result = verify_otp(user_id="uuid-string", submitted_code="123456")
# Returns: {'valid': True/False, 'message': 'Success/Error message'}

# Get OTP expiry info
expiry_info = get_otp_expiry(user_id="uuid-string")
# Returns: {'remaining_seconds': int}

# Manually clear OTP
clear_otp(user_id="uuid-string")
```

**Redis Storage Format:**
```json
Key: otp:{user_id}
Value: {
  "code": "123456",
  "created_at": "2026-02-06T09:30:00Z",
  "expiry": "2026-02-06T09:35:00Z"
}
TTL: 300 seconds (5 minutes)
```

### 3. **Email Service**
**File:** `accounts/two_factor_email.py`

```python
send_otp_email(user_email, user_name, otp_code)
```

**Email Template Features:**
- Professional gradient header (blue theme)
- Large, monospace OTP display (32px)
- ⏱️ 5-minute validity indicator
- 🛡️ Security warning box
- Professional footer with branding
- Plain text fallback version

---

### 4. **Authentication Views**

#### OTP Verification View
**File:** `accounts/two_factor_views.py` → `OTPVerificationView`
**URL:** `/accounts/verify-2fa/`
**Template:** `templates/account/two_factor_verify.html`

**GET Request:**
- Displays OTP input form
- Shows email where code was sent
- Displays countdown timer (5 minutes)
- Requires `session['pending_2fa_user_id']`

**POST Request (AJAX):**
```json
Request: {"otp_code": "123456"}
Response Success: {
  "success": true,
  "message": "✅ Two-factor authentication successful!",
  "redirect_url": "/"
}
Response Failure: {
  "success": false,
  "message": "❌ Invalid or expired code"
}
```

#### Resend OTP View
**File:** `accounts/two_factor_views.py` → `ResendOTPView`
**URL:** `/accounts/resend-otp/`

**POST Request (AJAX):**
- Generates new OTP
- Updates Redis storage (resets 5-min timer)
- Resends email
- Returns JSON response

#### 2FA Settings View
**File:** `accounts/two_factor_views.py` → `TwoFactorSettingsView`
**URL:** `/accounts/2fa-settings/`
**Template:** `templates/account/two_factor_settings.html`
**Authentication:** `@login_required`

**GET Request:**
- Shows current 2FA status (enabled/disabled)
- Displays toggle switch
- Shows backup codes section (if enabled)

**POST Request (AJAX):**
```json
Request: {"two_factor_enabled": "on|off"}
Response: {
  "success": true,
  "message": "✅ Two-factor authentication has been enabled!",
  "is_enabled": true
}
```

---

### 5. **Integration with Django-Allauth**

#### Signal Handler
**File:** `accounts/two_factor_auth.py` → `check_2fa_enabled()`

**Triggers on:** `django.contrib.auth.signals.user_logged_in`

**Flow:**
1. User successfully logs in via django-allauth
2. Signal checks if user has 2FA enabled
3. If enabled:
   - Generates OTP
   - Stores in Redis
   - Sends email
   - Sets `session['pending_2fa_user_id']`
4. User must verify OTP before accessing platform

#### Middleware Handler
**File:** `accounts/two_factor_auth.py` → `TwoFactorAuthenticationMiddleware`

**Purpose:**
- Intercepts all requests from users with pending 2FA
- Redirects to `/accounts/verify-2fa/` if needed
- Exempts certain paths (logout, API, etc.)

**Exempt Paths:**
```python
'/accounts/verify-2fa/',
'/accounts/resend-otp/',
'/accounts/logout/',
'/api/',
```

---

## User Workflow

### **Enabling 2FA**

```
1. User logs in with email + password
2. Session created (temporarily marked as pending_2fa_user_id)
3. → Redirected to 2FA verification page
4. Email sent with 6-digit code
5. User enters code (6 digits)
6. Code verified against Redis
7. Session created, user logged in
8. → Redirected to home page
```

### **Disabling 2FA**

```
1. Logged-in user visits /accounts/2fa-settings/
2. Toggles "Enable 2FA" switch to OFF
3. ← Saved to database (TwoFactorAuth.is_enabled = False)
4. Next login won't trigger 2FA verification
```

---

## Configuration

### Environment Variables

```bash
# Redis
REDIS_URL=redis://127.0.0.1:6379/0

# Email (SMTP)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-gmail@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

### Django Settings

The following are already configured in `Plateforme/settings.py`:

```python
# Redis Cache
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
    }
}

# Email Configuration
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

# Middleware
MIDDLEWARE = [
    # ... other middleware ...
    "accounts.two_factor_auth.TwoFactorAuthenticationMiddleware",
]
```

---

## Files Created/Modified

### **New Files:**
```
accounts/
├── two_factor_models.py           # TwoFactorAuth model
├── two_factor_utils.py            # OTP management utilities
├── two_factor_email.py            # Email sending service
├── two_factor_views.py            # View classes (verification, resend, settings)
└── two_factor_auth.py             # Signal & Middleware integration

migrations/
└── 0006_twofactorauth.py          # Database migration

templates/account/
├── two_factor_verify.html         # OTP verification form
└── two_factor_settings.html       # 2FA settings toggle
```

### **Modified Files:**
```
accounts/
├── urls.py                        # Added 3 new URL paths
├── apps.py                        # Added ready() method for signals
└── admin.py                       # Registered TwoFactorAuth admin

Plateforme/
└── settings.py                    # Added Redis cache & Middleware config
```

---

## Testing the 2FA System

### Test 1: Enable 2FA
```bash
1. Log in to your account
2. Navigate to Profile > 2FA Settings
3. Toggle "Enable Two-Factor Authentication" to ON
4. Click "Save Settings"
5. Verify: TwoFactorAuth.is_enabled = True in database
```

### Test 2: Login with 2FA
```bash
1. Log out
2. Try to log in with email + password
3. Should see: → Redirected to OTP verification page
4. Email should contain 6-digit code
5. Enter code within 5 minutes
6. Verify: User logged in successfully
```

### Test 3: Resend OTP
```bash
1. On OTP verification page
2. Wait 2 minutes
3. Click "Resend Code" button
4. New email should arrive with new code
5. Old code should be invalid (replaced in Redis)
```

### Test 4: Expired Code
```bash
1. Do NOT enter code for 5+ minutes
2. Try to submit expired code
3. Should see: Error message "Code expired"
4. Click "Resend Code" to get new code
```

### Test 5: Disable 2FA
```bash
1. Log in normally (with 2FA verification if enabled)
2. Navigate to Profile > 2FA Settings
3. Toggle "Enable Two-Factor Authentication" to OFF
4. Click "Save Settings"
5. Log out and log in again
6. Verify: No 2FA verification required
```

---

## Dependencies

```
redis==7.1.0              # Redis client
django-redis==6.0.0       # Django cache backend
django==5.1.7             # (Already installed)
```

Install missing dependencies:
```bash
pip install redis django-redis
```

---

## Architecture Diagram

```
Login (django-allauth)
        ↓
    ✓ Authentication
        ↓
  [Signal: user_logged_in]
        ↓
  Check TwoFactorAuth.is_enabled
        ├─ NO → Skip 2FA, create session
        └─ YES:
            1. Generate OTP (6 digits)
            2. Store in Redis (ttl=5min)
            3. Send email
            4. Set session['pending_2fa_user_id']
            5. → Redirect to verify-2fa
                ↓
            [User receives email with code]
                ↓
            [User submits 6-digit code]
                ↓
            verify_otp() checks Redis
                ├─ INVALID → Error message
                └─ VALID:
                    1. Delete OTP from Redis
                    2. Create user session
                    3. auth_login(user)
                    4. → Redirect to home
```

---

## Security Considerations

✅ **What's Secured:**
- OTP codes stored in Redis (not in plaintext)
- Automatic 5-minute expiration
- One-time use (deleted after verification)
- Session-based user tracking
- CSRF protection on forms

⚠️ **Future Enhancements:**
- Backup codes (currently placeholder)
- TOTP (Time-based OTP) support
- SMS-based OTP fallback
- Account recovery options
- Rate limiting on OTP attempts

---

## Common Issues & Solutions

### Issue: "No module named 'redis'"
**Solution:**
```bash
pip install redis
```

### Issue: "No module named 'django_redis'"
**Solution:**
```bash
pip install django-redis
```

### Issue: Redis connection refused
**Solution:**
1. Ensure Redis server is running: `redis-cli ping` should return PONG
2. Check REDIS_URL in environment variables
3. For development: `redis-server` (Windows: `redis-server.exe`)

### Issue: Email not sending
**Solution:**
1. Check EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in .env
2. For Gmail: Use "App Password" (not regular password)
3. Enable "Less secure app access" in Gmail settings
4. Test with: `python manage.py shell`
   ```python
   from django.core.mail import send_mail
   send_mail("Test", "Test message", "from@gmail.com", ["to@gmail.com"])
   ```

---

## Admin Panel Access

View 2FA status for all users:

```
Django Admin → Two Factor Authentications
```

Shows:
- User email
- Current 2FA status (enabled/disabled)
- Creation & update timestamps
- Backup codes (if any)

---

## Next Steps (Future)

1. **Backup Codes:**
   - Generate 10 unique backup codes during 2FA setup
   - Store encrypted in TwoFactorAuth.backup_codes
   - Allow users to download/print backup codes
   - Use as fallback if email access is lost

2. **TOTP Support:**
   - Add Google Authenticator / Authy support
   - Generate QR codes for app scanning
   - Time-synchronized OTP (30-second window)

3. **Rate Limiting:**
   - Limit OTP verification attempts to 3 per code
   - Temporary lockout after 5 failed attempts
   - Block brute force attacks

4. **Recovery Codes:**
   - Generate single-use recovery codes
   - Require identity verification to use
   - SMS-based recovery option

---

## Support & Documentation

For detailed code documentation, see inline comments in:
- `accounts/two_factor_utils.py` - OTP logic
- `accounts/two_factor_views.py` - View handling
- `accounts/two_factor_email.py` - Email templates

