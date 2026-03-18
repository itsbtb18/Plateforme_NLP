# Global Settings Management

## Overview

The `settings` app provides a comprehensive admin panel for managing platform-wide configuration. It uses a singleton pattern to ensure only one set of global settings exists in the database.

## Features

### 📱 Platform Information
- Site name, description, and URL
- Logo and favicon uploads

### 📧 Email Configuration
- SMTP server settings (host, port, TLS)
- From name and address
- Admin notification email

### 🔔 Notifications
- Enable/disable email notifications globally
- Granular control over which events trigger notifications:
  - User registration
  - Resource submission
  - Forum posts
  - Events
- Notification email destination

### ⚙️ Feature Flags
Toggle platform features on/off:
- User registration
- Social login (Google, etc.)
- Two-factor authentication
- Forum functionality
- Q&A functionality
- Events
- Projects
- Chatbot
- Resource submission & approval

### 🛡️ Security & Moderation
- Content moderation toggle
- Maximum file upload size
- Email verification requirement
- Two-factor authentication

### 🔧 Maintenance Mode
- Enable/disable maintenance mode for site updates
- Custom maintenance message for users

## Usage

### Accessing Settings in Code

```python
from settings.utils import get_global_settings, is_feature_enabled

# Get the entire settings object
settings = get_global_settings()

# Access specific settings
site_name = settings.site_name
email_config = settings.email_from_address

# Check if a feature is enabled
if is_feature_enabled('enable_forum'):
    # Forum is enabled
    pass

# Or use convenience methods
from settings.utils import forum_enabled, can_register_users

if forum_enabled():
    # Forum is available
    pass

if can_register_users():
    # Registration is open
    pass
```

### Feature Flag Convenience Methods

Available in `settings.utils`:

- `can_register_users()`
- `social_login_enabled()`
- `two_factor_auth_enabled()`
- `forum_enabled()`
- `qa_enabled()`
- `events_enabled()`
- `projects_enabled()`
- `chatbot_enabled()`
- `resource_submission_enabled()`
- `content_moderation_enabled()`
- `is_maintenance_mode()`

### Admin Panel Access

1. Go to Django admin panel
2. Navigate to "Platform Settings"
3. Click the single GlobalSettings entry to edit
4. Organize changes using the fieldsets:
   - Platform Information
   - Email Configuration (collapsed)
   - Notification Settings
   - Feature Flags
   - Content Moderation & Security
   - Maintenance (collapsed)

## Caching

Settings are cached for 1 hour by default. Changes are reflected immediately because:

1. When admin updates settings, the `post_save` signal fires
2. Signal handler calls `invalidate_settings_cache()`
3. Next call to `get_global_settings()` fetches fresh data

## Maintenance Mode

When maintenance mode is enabled:
- Non-staff users see a maintenance page (HTTP 503)
- Staff/superuser users can still access the site
- Custom message is displayed to users
- Admin email is shown as a contact point

## Next Steps

### Template Usage Example

```html
{% load settings %}

{% if "enable_forum"|is_feature_enabled %}
    <a href="{% url 'forum' %}">Forum</a>
{% endif %}

{% if "is_maintenance_mode"|is_feature_enabled %}
    <div class="alert alert-warning">
        Maintenance in progress. We're back soon!
    </div>
{% endif %}
```

### Middleware Integration

Maintenance mode middleware is available in `settings.middleware`:
- `MaintenanceModeMiddleware` - Handles maintenance mode display

Add to `settings.py` MIDDLEWARE if you want to enable it:
```python
MIDDLEWARE = [
    ...
    'settings.middleware.MaintenanceModeMiddleware',
    ...
]
```

## File Structure

```
settings/
├── __init__.py
├── admin.py              # Admin configuration
├── apps.py               # App configuration
├── models.py             # GlobalSettings model
├── signals.py            # Signal handlers for cache invalidation
├── utils.py              # Utility functions for accessing settings
├── middleware.py         # Middleware for maintenance mode and other features
├── tests.py              # Test cases
├── migrations/
│   ├── __init__.py
│   └── 0001_initial.py   # Initial migration
└── README.md             # This file
```

## Testing

Run tests:
```bash
python manage.py test settings
```

## Troubleshooting

### Settings cache not updating
- Manually clear cache: `python manage.py shell` → `from django.core.cache import cache; cache.clear()`
- Restart your Django development server

### Maintenance mode not working
- Ensure `MaintenanceModeMiddleware` is added to MIDDLEWARE
- Check that maintenance_mode flag is True in admin
- Clear cache and restart server

### Email settings not being used
- Verify SMTP settings are correct in admin
- Test with Django shell: `from settings.utils import get_email_config; print(get_email_config())`
