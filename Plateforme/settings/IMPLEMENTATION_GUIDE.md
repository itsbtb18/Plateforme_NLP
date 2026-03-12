# Global Settings Implementation Guide

## 📋 What We've Built

A complete **Global Settings Management System** for the Django platform with:

### Core Components
1. **GlobalSettings Model** - Singleton database model storing all configuration
2. **Admin Panel Interface** - Full-featured Django admin with organized fieldsets
3. **Utility Functions** - Easy access to settings throughout the codebase
4. **Template Tags** - Access settings directly in Django templates
5. **Middleware** - Maintenance mode support
6. **Management Command** - Easy initialization
7. **API Views** - REST endpoints for settings (optional)
8. **Caching System** - Settings cached for performance with auto-invalidation

## 🚀 Quick Start

### Step 1: Apply Migrations

Run the management command to set everything up:

```bash
python manage.py init_global_settings
```

This will:
- Run migrations
- Create the GlobalSettings database table
- Initialize default settings

### Step 2: Access Admin Panel

1. Go to: `http://localhost:8000/admin/`
2. Login with your admin account
3. Navigate to **"Platform Settings"** → **"Global Settings"**
4. You'll see a single entry - click to edit

### Step 3: Start Using Settings

#### In Python Code:

```python
from settings.utils import get_global_settings, is_feature_enabled

# Get entire settings
settings = get_global_settings()
print(settings.site_name)  # 'NLP Platform'

# Check feature flags
if is_feature_enabled('enable_forum'):
    print("Forum is enabled!")

# Use convenience methods
from settings.utils import forum_enabled, can_register_users
if forum_enabled():
    display_forum_link()
```

#### In Django Templates:

```django
{% load settings_tags %}

<!-- Get a setting value -->
<title>{% setting 'site_name' %}</title>

<!-- Check if feature is enabled -->
{% if "enable_forum"|is_feature_enabled %}
    <a href="{% url 'forum' %}">Forum</a>
{% endif %}

<!-- Use convenience tags -->
{% if forum_enabled %}
    <nav>...</nav>
{% endif %}

<!-- Show maintenance message -->
{% if maintenance_mode %}
    <div class="alert">Under maintenance</div>
{% endif %}
```

## 📁 File Structure Created

```
settings/
├── __init__.py
├── admin.py                      ← Admin panel configuration
├── apps.py                       ← App config with signal registration
├── models.py                     ← GlobalSettings model
├── views.py                      ← API views (optional)
├── utils.py                      ← Utility functions
├── middleware.py                 ← Maintenance mode middleware
├── signals.py                    ← Cache invalidation signals
├── serializers.py                ← DRF serializers
├── tests.py                      ← Test cases
├── initialize.py                 ← Standalone initialization script
├── README.md                     ← Basic documentation
├── IMPLEMENTATION_GUIDE.md       ← This file
├── migrations/
│   ├── __init__.py
│   └── 0001_initial.py          ← Database migration
├── management/
│   ├── __init__.py
│   └── commands/
│       ├── __init__.py
│       └── init_global_settings.py  ← Management command
└── templatetags/
    ├── __init__.py
    └── settings_tags.py         ← Template tags
```

## 🎯 Available Settings

### Platform Information
- `site_name` - Name of your platform
- `site_description` - Brief description
- `site_url` - Main website URL
- `logo` - Upload platform logo
- `favicon` - Upload favicon

### Email Configuration
- `email_from_name` - Display name for emails
- `email_from_address` - Sender email address
- `smtp_host` - SMTP server hostname
- `smtp_port` - SMTP port (usually 587 or 465)
- `smtp_use_tls` - Enable TLS encryption
- `admin_email` - Email for admin notifications

### Notifications
- `enable_email_notifications` - Master switch for emails
- `notify_on_user_registration` - New user signup
- `notify_on_resource_submission` - Resource submissions
- `notify_on_forum_post` - Forum activity
- `notify_on_event` - Event notifications
- `notification_email` - Where to send notifications

### Feature Flags
- `enable_user_registration` - Allow sign-ups
- `enable_social_login` - Google login, etc.
- `enable_two_factor_auth` - 2FA support
- `enable_forum` - Forum functionality
- `enable_qa` - Q&A section
- `enable_events` - Events feature
- `enable_projects` - Projects feature
- `enable_chatbot` - Chatbot functionality
- `enable_resource_submission` - User uploads
- `enable_resource_approval` - Moderation required

### Security & Moderation
- `enable_content_moderation` - Moderation tools
- `max_upload_size_mb` - Max file upload size
- `require_email_verification` - Email verification

### Maintenance
- `maintenance_mode` - Disable site for public
- `maintenance_message` - Custom message to users

## 💡 Common Usage Examples

### Example 1: Conditional Navigation

```django
<nav>
    {% load settings_tags %}
    
    <a href="/home/">Home</a>
    
    {% if forum_enabled %}
        <a href="/forum/">Forum</a>
    {% endif %}
    
    {% if qa_enabled %}
        <a href="/qa/">Q&A</a>
    {% endif %}
    
    {% if events_enabled %}
        <a href="/events/">Events</a>
    {% endif %}
    
    {% if projects_enabled %}
        <a href="/projects/">Projects</a>
    {% endif %}
</nav>
```

### Example 2: Feature-Based View Logic

```python
from django.shortcuts import redirect
from settings.utils import can_register_users

def registration_view(request):
    if not can_register_users():
        return redirect('registration_closed')
    
    # Handle registration...
```

### Example 3: Email Configuration

```python
from settings.utils import get_email_config

email_config = get_email_config()

# Use in your email sending logic
send_email(
    subject='Welcome',
    from_email=f"{email_config['from_name']} <{email_config['from_address']}>",
    recipient_list=['user@example.com'],
)
```

### Example 4: Maintenance Mode

```python
from settings.utils import is_maintenance_mode

if is_maintenance_mode():
    # Skip background tasks, disable forms, etc.
    return JsonResponse({'status': 'maintenance'}, status=503)
```

## 🔧 Configuration in Django Settings

The settings app is already added to `INSTALLED_APPS` in `Plateforme/settings.py`:

```python
INSTALLED_APPS = [
    # ... other apps ...
    "settings",
]
```

And the maintenance mode middleware is enabled:

```python
MIDDLEWARE = [
    # ... other middleware ...
    "settings.middleware.MaintenanceModeMiddleware",
]
```

## 📊 Admin Panel Features

### Organization
Settings are organized in logical fieldsets:
- 📱 Platform Information
- 📧 Email Configuration (collapsible)
- 🔔 Notification Settings
- ⚙️ Feature Flags
- 🛡️ Content Moderation & Security
- 🔧 Maintenance (collapsible)
- ℹ️ Metadata (read-only)

### Security Features
- ❌ **No deletion**: Settings can't be deleted
- ❌ **No duplication**: Only one settings instance allowed
- ✅ **Audit trail**: Shows who last updated settings
- ✅ **Visual status**: Maintenance mode clearly indicated

## 🧪 Testing

Run the included tests:

```bash
python manage.py test settings
```

Tests verify:
- Singleton pattern enforcement
- Default value initialization
- Cache invalidation on save

## 🚨 Troubleshooting

### Settings not appearing in admin
```bash
# Ensure migrations are applied
python manage.py migrate settings

# Check the app is installed
python manage.py check
```

### Cache not updating
```bash
# Clear the cache manually
python manage.py shell
>>> from django.core.cache import cache
>>> cache.clear()
>>> exit()
```

### Maintenance mode not working
1. Verify `settings.middleware.MaintenanceModeMiddleware` is in MIDDLEWARE
2. Enable maintenance mode in admin
3. Restart Django server
4. Test with non-admin user account

### Import errors
```bash
# Make sure settings app is in INSTALLED_APPS
python manage.py check
```

## 📚 Advanced Features

### API Endpoints (if needed)

You can enable REST API access to settings:

```python
# Add to urls.py
from settings.views import get_settings_api

path('api/settings/', get_settings_api, name='api_settings'),
```

Then access: `GET /api/settings/` (admin only)

### Custom Signals

The app automatically invalidates cache when settings change. To add custom behavior:

```python
from django.db.models.signals import post_save
from settings.models import GlobalSettings

@receiver(post_save, sender=GlobalSettings)
def on_settings_change(sender, instance, **kwargs):
    # Your custom logic here
    print(f"Settings updated by {instance.updated_by}")
```

### Template Tag Custom Filters

Create custom template filters in your templates:

```django
{% load settings_tags %}

{% feature_enabled 'enable_forum' as can_access_forum %}
{% if can_access_forum %}
    {# Show forum-related content #}
{% endif %}
```

## 🔐 Security Notes

- ✅ Settings are cached for 1 hour
- ✅ Cache auto-invalidates on admin changes
- ✅ Admin-only access required
- ✅ Maintenance mode properly escapes user input
- ⚠️ Never expose SMTP credentials in templates/API

## 📈 Performance

- **Caching**: Settings cached for 1 hour (configurable)
- **Query efficient**: Single database query per cache miss
- **Memory lean**: Minimal overhead
- **Scalable**: Works with any Django ORM cache backend

## 🎓 Learning Resources

- [Django Model Design Patterns](https://docs.djangoproject.com/en/stable/topics/patterns/)
- [Django Signals](https://docs.djangoproject.com/en/stable/topics/signals/)
- [Django Middleware](https://docs.djangoproject.com/en/stable/topics/http/middleware/)
- [Django Template Tags](https://docs.djangoproject.com/en/stable/howto/custom-template-tags/)

## 🆘 Support

For issues or questions:
1. Check `settings/README.md` for basic usage
2. Review this guide for advanced topics
3. Check Django error messages
4. Run `python manage.py check`
5. Review test cases in `settings/tests.py`

## ✅ Checklist

- [x] Settings app created
- [x] Migrations created
- [x] Admin panel configured
- [x] Utility functions provided
- [x] Template tags created
- [x] Middleware enabled
- [x] Management command added
- [x] Documentation written
- [x] Tests included
- [x] Cache system implemented
- [ ] Run `python manage.py init_global_settings`
- [ ] Test in admin panel
- [ ] Update feature checks in views
- [ ] Deploy to production

---

**Created**: February 28, 2026  
**Status**: ✅ Ready for use
