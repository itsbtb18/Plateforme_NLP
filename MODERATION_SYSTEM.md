# Content Moderation System Documentation

## Overview

This platform implements a comprehensive content moderation workflow for all user-generated content. All content submissions require admin approval before being publicly visible.

## Moderated Content Types

The following content types require moderation:

1. **Resources**
   - Corpus
   - NLP Tools
   - Courses
   - Documents (Articles, Theses, Memoirs)

2. **Community Content**
   - Forum Topics
   - Posts/News

3. **Research**
   - Projects
   - Events

4. **Institutions**

## How It Works

### 1. Content Creation

When a user creates new content:

```python
# Automatic workflow:
1. User submits form
2. System sets:
   - approval_status = 'pending'  (or 'approved' if user is staff)
   - created_by/author/creator = current_user
   - created_at = current timestamp
3. Content is saved to database
4. User sees confirmation message
```

**Example: Creating a Corpus**

```python
# In resources/forms.py
corpus = Corpus.objects.create(
    title_en='My Corpus',
    title_ar='مجموعتي',
    author=request.user,
    approval_status='pending',  # Explicitly set
    # ... other fields
)
```

### 2. Admin Review

Admins access pending content through the Admin Panel:

- **URL Pattern**: `/admin/{module}/`
- **Tabs**: 
  - `?tab=pending` - Shows items awaiting approval
  - `?tab=approved` - Shows approved items

**Example URLs:**
- Pending Corpora: `/admin/corpora/?tab=pending`
- Pending Projects: `/admin/projects/?tab=pending`
- Pending Topics: `/admin/forum/?tab=pending`

### 3. Approval Actions

Admins can:
- **Approve**: `approval_status` → `'approved'` (content becomes public)
- **Reject**: `approval_status` → `'rejected'` (content hidden, can be deleted)
- **Delete**: Permanently remove content

## Database Schema

### Required Fields

All moderated models must have:

```python
class MyModel(models.Model):
    # Unique identifier
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    
    # Moderation status
    approval_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        default='pending',
        db_index=True  # Important for fast filtering
    )
    
    # Creator tracking
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    # OR: author, creator, coordinator (depending on model)
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
```

### Field Name Variations

Different models use different field names for the creator:

| Model | Creator Field |
|-------|--------------|
| Corpus, NLPTool, Course, Document | `author` |
| Project | `coordinator` |
| Event | `created_by` |
| Topic | `creator` |
| Institution | `created_by` |
| Post | `author` |

## API Reference

### Utilities Module

Location: `core/moderation.py`

#### ModerationMixin

Abstract mixin providing moderation fields and methods:

```python
from core.moderation import ModerationMixin

class MyModel(ModerationMixin):
    # Your fields here
    pass

# Usage
instance = MyModel.objects.create(...)
instance.approve()  # Sets status to 'approved'
instance.reject()   # Sets status to 'rejected'
instance.is_approved()  # Boolean check
```

#### ModeratedContentCreationMixin

View mixin for handling content creation with automatic moderation:

```python
from core.moderation import ModeratedContentCreationMixin
from django.views.generic import CreateView

class MyContentCreateView(ModeratedContentCreationMixin, CreateView):
    model = MyModel
    form_class = MyForm
    
    def get_author_field_name(self):
        return 'author'  # or 'created_by', etc.
```

#### Helper Functions

```python
from core.moderation import log_moderation_action, get_pending_count

# Log moderation events
log_moderation_action(
    model_name='Corpus',
    instance_id=corpus.id,
    action='created',
    user_email=user.email
)

# Get pending counts
pending = get_pending_count(Corpus)
```

### Management Commands

#### check_moderation

Check the status of the moderation system:

```bash
# Basic check
python manage.py check_moderation

# Detailed check with recent items
python manage.py check_moderation --detailed

# Check specific model only
python manage.py check_moderation --model Corpus
python manage.py check_moderation --model Project --detailed
```

**Output Example:**
```
================================================================================
MODERATION SYSTEM STATUS CHECK
================================================================================

CORPUS:
  Total: 45
  Pending: 3
  Approved: 40
  Rejected: 2

  Recent Pending Items:
    - [2026-02-21 14:30] Arabic News Corpus by user@example.com
    - [2026-02-21 10:15] Social Media Dataset by researcher@uni.edu
    - [2026-02-20 16:45] Legal Documents Corpus by admin@legal.org

  Created in last 24h: 5

PROJECT:
  Total: 23
  Pending: 1
  Approved: 22
  Rejected: 0
```

## Logging

All creation and moderation actions are logged with consistent prefixes:

### Log Levels

- **INFO**: Successful operations
- **WARNING**: Validation failures
- **ERROR**: Creation errors, exceptions

### Log Prefixes

```
[RESOURCE_CREATE] - Resource creation
[PROJECT_CREATE] - Project creation
[EVENT_CREATE] - Event creation
[TOPIC_CREATE] - Topic creation
[INSTITUTION_CREATE] - Institution creation
[POST_CREATE] - Post creation
```

### Example Logs

```
INFO [RESOURCE_CREATE] Starting save for resource type: corpus, user: user@example.com
INFO [RESOURCE_CREATE] Common data prepared: author=user@example.com, approval_status=pending
INFO [RESOURCE_CREATE] Creating new corpus
INFO [RESOURCE_CREATE] ✓ Corpus created successfully (ID: 123e4567-e89b-12d3, Status: pending)

WARNING [PROJECT_CREATE] Form validation failed: {"title": ["This field is required"]}

ERROR [EVENT_CREATE] ✗ Error creating event: IntegrityError at field 'organizer'
```

### Viewing Logs

```bash
# Real-time monitoring
tail -f logs/debug.log | grep "RESOURCE_CREATE\|PROJECT_CREATE\|EVENT_CREATE"

# Filter specific action
tail -f logs/debug.log | grep "✓"  # Successful creations
tail -f logs/debug.log | grep "✗"  # Failed creations
```

## Admin Views

### Filtering Logic

All admin views filter by approval_status:

```python
# pages/views.py
def admin_corpora(request):
    tab = request.GET.get('tab', 'approved')
    
    base_qs = Corpus.objects.select_related('author').order_by('-creation_date')
    
    # Separate queries for pending and approved
    pending_corpora = base_qs.filter(approval_status='pending')
    approved_corpora = base_qs.filter(approval_status='approved')
    
    # Return appropriate queryset based on tab
    context = {
        'corpora': approved_corpora if tab == 'approved' else pending_corpora,
        'pending_count': pending_corpora.count(),
        'approved_count': approved_corpora.count(),
        'active_tab': tab,
    }
    return render(request, 'admin/corpora.html', context)
```

### URL Patterns

| Content Type | Pending URL | Approved URL |
|-------------|-------------|--------------|
| Corpora | `/admin/corpora/?tab=pending` | `/admin/corpora/?tab=approved` |
| Tools | `/admin/tools/?tab=pending` | `/admin/tools/?tab=approved` |
| Courses | `/admin/courses/?tab=pending` | `/admin/courses/?tab=approved` |
| Projects | `/admin/projects/?tab=pending` | `/admin/projects/?tab=approved` |
| Events | `/admin/calls/?tab=pending` | `/admin/calls/?tab=approved` |
| Topics | `/admin/forum/?tab=pending` | `/admin/forum/?tab=approved` |
| Institutions | `/admin/institutions/?tab=pending` | `/admin/institutions/?tab=approved` |
| Posts | `/admin/news/?tab=pending` | `/admin/news/?tab=approved` |

## Troubleshooting

### Issue: Items not appearing in Pending section

**Possible Causes:**
1. approval_status not set correctly
2. Form validation failing silently
3. Database transaction not committing
4. Missing field in model

**Debug Steps:**

```bash
# 1. Check logs for creation errors
tail -f logs/debug.log | grep "✗"

# 2. Check moderation system status
python manage.py check_moderation --detailed

# 3. Check database directly
python manage.py shell
>>> from resources.models import Corpus
>>> Corpus.objects.filter(approval_status='pending').count()
>>> # Should show pending items

# 4. Check recent items
>>> recent = Corpus.objects.order_by('-created_at')[:5]
>>> for c in recent:
...     print(f"{c.id}: {c.title}, Status: {c.approval_status}, Author: {c.author.email}")
```

### Issue: Items not saving to database

**Check:**
1. Form validation errors in logs
2. Database connection
3. Required fields not provided

```python
# In view or form
import logging
logger = logging.getLogger(__name__)

try:
    instance.save()
    logger.info(f"✓ Saved: {instance.id}")
except Exception as e:
    logger.error(f"✗ Error: {e}", exc_info=True)
```

### Issue: Wrong approval status

**Verify:**
1. Model default is set to 'pending'
2. View explicitly sets approval_status
3. Form doesn't override status

```python
# Check model default
class MyModel(models.Model):
    approval_status = models.CharField(
        default='pending'  # Must be here
    )

# Check view sets it explicitly
def form_valid(self, form):
    form.instance.approval_status = 'pending'  # Explicit is better
    return super().form_valid(form)
```

## Best Practices

### 1. Always Set Approval Status Explicitly

```python
# ✓ GOOD
instance.approval_status = 'pending'
instance.save()

# ✗ BAD (relying only on model default)
instance.save()  # What if default changes?
```

### 2. Always Log Creation Events

```python
logger.info(f"[MODULE_CREATE] Creating {model_name} by {user.email}")
instance.save()
logger.info(f"[MODULE_CREATE] ✓ Created successfully (ID: {instance.id})")
```

### 3. Handle Exceptions Gracefully

```python
try:
    instance.save()
except Exception as e:
    logger.error(f"[MODULE_CREATE] ✗ Error: {e}", exc_info=True)
    messages.error(request, "Creation failed. Please try again.")
    return redirect('error_page')
```

### 4. Test Moderation Workflow

```python
# In tests.py
def test_corpus_creation_requires_approval(self):
    corpus = Corpus.objects.create(
        title="Test",
        author=self.user
    )
    # Default should be pending
    self.assertEqual(corpus.approval_status, 'pending')
    
    # Should not appear in public view
    public_corpora = Corpus.objects.filter(approval_status='approved')
    self.assertNotIn(corpus, public_corpora)
```

## Staff Auto-Approval

Staff users can create content that is automatically approved:

```python
def form_valid(self, form):
    if self.request.user.is_staff:
        form.instance.approval_status = 'approved'
        logger.info(f"Auto-approving {model} created by staff")
    else:
        form.instance.approval_status = 'pending'
    return super().form_valid(form)
```

## Security Considerations

1. **Public Views**: Must filter by `approval_status='approved'`
2. **Author Access**: Users can see their own pending items
3. **Admin Access**: Only staff can access admin panel
4. **Audit Trail**: All actions are logged

```python
# Public view - only approved
def public_list(request):
    items = Model.objects.filter(approval_status='approved')
    
# User's own items - including pending
def my_items(request):
    items = Model.objects.filter(
        Q(author=request.user) | Q(approval_status='approved')
    )
```

## Summary Checklist

When adding moderation to a new model:

- [ ] Add `approval_status` field with default='pending'
- [ ] Add `created_at` field with auto_now_add=True
- [ ] Add creator field (author/created_by/etc)
- [ ] Add db_index=True to approval_status and created_at
- [ ] Set approval_status explicitly in create view
- [ ] Add comprehensive logging
- [ ] Add error handling with try/except
- [ ] Create admin view with pending/approved tabs
- [ ] Filter public views by approval_status='approved'
- [ ] Add management command check for the model
- [ ] Write tests for moderation workflow

---

**Last Updated**: February 21, 2026
**Version**: 1.0
