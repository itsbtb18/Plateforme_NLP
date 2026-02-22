"""
QUICK REFERENCE: Content Moderation System
===========================================

## Common Tasks

### Check System Status
```bash
python manage.py check_moderation
python manage.py check_moderation --detailed
python manage.py check_moderation --model Corpus
```

### View Logs
```bash
# All creation logs
tail -f logs/debug.log | grep "CREATE"

# Successful creations
tail -f logs/debug.log | grep "✓"

# Failed creations
tail -f logs/debug.log | grep "✗"

# Specific module
tail -f logs/debug.log | grep "RESOURCE_CREATE"
```

### Database Queries
```python
from resources.models import Corpus
from projects.models import Project

# Pending items
Corpus.objects.filter(approval_status='pending')
Project.objects.filter(approval_status='pending')

# Approved items
Corpus.objects.filter(approval_status='approved')

# Count pending
Corpus.objects.filter(approval_status='pending').count()

# Recent items
Corpus.objects.order_by('-created_at')[:10]

# Items by user
Corpus.objects.filter(author__email='user@example.com')
```

### Admin URLs
```
/admin/corpora/?tab=pending
/admin/tools/?tab=pending
/admin/courses/?tab=pending
/admin/projects/?tab=pending
/admin/calls/?tab=pending
/admin/forum/?tab=pending
/admin/institutions/?tab=pending
/admin/news/?tab=pending
```

## Code Templates

### Adding Moderation to New Model
```python
# models.py
from django.db import models
import uuid

class MyModel(models.Model):
    APPROVAL_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default='pending',
        db_index=True  # Important for performance
    )
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Your fields here...
```

### Create View Template
```python
# views.py
import logging
from django.views.generic import CreateView
from django.contrib import messages

logger = logging.getLogger(__name__)

class MyModelCreateView(LoginAndVerifiedRequiredMixin, CreateView):
    model = MyModel
    form_class = MyModelForm
    
    def form_valid(self, form):
        import logging
        logger = logging.getLogger(__name__)
        
        form.instance.created_by = self.request.user
        
        # Set approval status
        if self.request.user.is_staff:
            form.instance.approval_status = 'approved'
            logger.info(f"[MYMODEL_CREATE] Auto-approving by staff: {self.request.user.email}")
        else:
            form.instance.approval_status = 'pending'
            logger.info(f"[MYMODEL_CREATE] Setting to pending by: {self.request.user.email}")
        
        try:
            response = super().form_valid(form)
            logger.info(
                f"[MYMODEL_CREATE] ✓ Created successfully "
                f"(ID: {form.instance.id}, Status: {form.instance.approval_status})"
            )
            
            if form.instance.approval_status == 'approved':
                messages.success(self.request, "Created and published!")
            else:
                messages.info(self.request, "Submitted for review. Pending approval.")
            
            return response
            
        except Exception as e:
            logger.error(f"[MYMODEL_CREATE] ✗ Error: {str(e)}", exc_info=True)
            messages.error(self.request, "Creation failed. Please try again.")
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        logger.warning(f"[MYMODEL_CREATE] Form validation failed: {form.errors.as_json()}")
        messages.error(self.request, "Please correct the errors.")
        return super().form_invalid(form)
```

### Admin View Template
```python
# pages/views.py
@login_required
@user_passes_test(is_admin)
def admin_mymodel(request):
    tab = request.GET.get('tab', 'approved')
    search = request.GET.get('search', '').strip()
    
    base_qs = MyModel.objects.select_related('created_by').order_by('-created_at')
    
    if search:
        base_qs = base_qs.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search)
        )
    
    pending_items = base_qs.filter(approval_status='pending')
    approved_items = base_qs.filter(approval_status='approved')
    
    context = {
        'items': approved_items if tab == 'approved' else pending_items,
        'pending_items': pending_items,
        'approved_items': approved_items,
        'pending_count': pending_items.count(),
        'approved_count': approved_items.count(),
        'active_tab': tab,
        'search': search,
        'model_type': 'mymodel',
    }
    return render(request, 'admin/mymodel.html', context)
```

## Debugging Checklist

When items not appearing in pending:

1. ✅ Check logs for creation attempt
   ```bash
   tail -f logs/debug.log | grep "MYMODEL_CREATE"
   ```

2. ✅ Verify item was created
   ```python
   MyModel.objects.order_by('-created_at').first()
   ```

3. ✅ Check approval status
   ```python
   item = MyModel.objects.last()
   print(f"Status: {item.approval_status}")
   ```

4. ✅ Verify admin query
   ```python
   MyModel.objects.filter(approval_status='pending').count()
   ```

5. ✅ Check for form validation errors
   ```bash
   tail -f logs/debug.log | grep "validation failed"
   ```

## Log Prefixes

[RESOURCE_CREATE] - Resource (Corpus, Tool, Course, Document)
[PROJECT_CREATE] - Project
[EVENT_CREATE] - Event
[TOPIC_CREATE] - Topic
[INSTITUTION_CREATE] - Institution
[POST_CREATE] - Post

## Success Indicators

✓ = Success
✗ = Error
⚠ = Warning

## Model Field Reference

| Model | Status Field | Creator Field | Timestamp Field |
|-------|-------------|---------------|-----------------|
| Corpus | approval_status | author | created_at |
| NLPTool | approval_status | author | created_at |
| Course | approval_status | author | created_at |
| Document | approval_status | author | created_at |
| Project | approval_status | coordinator | created_at |
| Event | approval_status | created_by | created_at |
| Topic | approval_status | creator | created_at |
| Institution | approval_status | created_by | created_at |
| Post | approval_status | author | created_at |

---
Last Updated: 2026-02-21
"""
print(__doc__)
