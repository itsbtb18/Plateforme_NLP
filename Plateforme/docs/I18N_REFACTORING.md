# Internationalization (i18n) Refactoring Summary

## Overview

This document outlines the complete i18n refactoring implemented for the NLP Research Platform.
The system follows an **Admin-Controlled Translation Workflow** where:

1. Users submit content in ONE language (based on their active locale)
2. Admins translate missing fields BEFORE approval
3. Frontend strictly shows content in the current language

---

## 1. Model Changes

### Display Properties Added

All models with bilingual fields now have `@property` methods that return the appropriate
language version based on `get_language()` **without fallback** (strict i18n).

#### CustomUser (`accounts/models.py`)
```python
@property
def full_name_display(self):
    """Return full name based on current language - NO fallback."""
    
@property
def bio_display(self):
    """Return bio based on current language - NO fallback."""
```

#### Institution (`institutions/models.py`)
- Added `description_ar` and `description_en` fields (NEW)
```python
@property
def name_display(self):
    """Return name based on current language - NO fallback."""
    
@property
def description_display(self):
    """Return description based on current language - NO fallback."""
```

#### ResourceBase (`resources/models.py`)
```python
@property
def title_display(self):
    """Return title based on current language - NO fallback."""
    
@property
def description_display(self):
    """Return description based on current language - NO fallback."""
```

#### Project (`projects/models.py`)
```python
@property
def title_display(self):
@property
def description_display(self):
```

#### Event (`events/models.py`)
```python
@property
def title_display(self):
@property
def description_display(self):
@property
def location_display(self):
```

#### Topic (`forum/models.py`)
```python
@property
def title_display(self):
@property
def description_display(self):
```

---

## 2. Form Changes

### Context-Aware Bilingual Forms

All forms now detect the active language and:
1. Show appropriate field labels (e.g., "Title (English)" vs "العنوان (بالعربية)")
2. Pre-populate from the correct `_ar` or `_en` field when editing
3. Save to the appropriate bilingual field based on active language

#### Form Pattern
```python
BILINGUAL_FIELDS = {
    'title': ('title_ar', 'title_en'),
    'description': ('description_ar', 'description_en'),
}

def __init__(self, *args, **kwargs):
    # Pre-populate from bilingual fields based on current language
    lang = get_active_language()
    for generic_field, (ar_field, en_field) in self.BILINGUAL_FIELDS.items():
        target_field = ar_field if lang == 'ar' else en_field
        # ... set initial values

def save(self, commit=True):
    # Save to bilingual fields based on active language
    lang = get_active_language()
    for generic_field, (ar_field, en_field) in self.BILINGUAL_FIELDS.items():
        target_field = ar_field if lang == 'ar' else en_field
        setattr(instance, target_field, value)
```

#### Updated Forms
- `ResourceForm` (`resources/forms.py`) - title, description
- `EventForm` (`events/forms.py`) - title, description, location
- `ProjectForm` (`projects/forms.py`) - title, description
- `TopicForm` (`forum/forms.py`) - NEW FILE - title, description
- `InstitutionForm` (`institutions/forms.py`) - name, description

---

## 3. Admin Translation Gate

The approval workflow now **blocks approval** if translations are incomplete.

### Implementation (`pages/views.py`)

```python
TRANSLATION_FIELDS = {
    'document': {'title': ('title_ar', 'title_en'), 'description': ('description_ar', 'description_en')},
    'corpus': {'title': ('title_ar', 'title_en'), 'description': ('description_ar', 'description_en')},
    'nlptool': {'title': ('title_ar', 'title_en'), 'description': ('description_ar', 'description_en')},
    'course': {'title': ('title_ar', 'title_en'), 'description': ('description_ar', 'description_en')},
    'project': {'title': ('title_ar', 'title_en'), 'description': ('description_ar', 'description_en')},
    'topic': {'title': ('title_ar', 'title_en'), 'description': ('description_ar', 'description_en')},
    'event': {
        'title': ('title_ar', 'title_en'), 
        'description': ('description_ar', 'description_en'),
        'location': ('location_ar', 'location_en')
    },
}

def validate_translations(item, model_type):
    """Validate that all required translation fields are filled."""
    # Returns (is_valid, list_of_missing_fields)

@login_required
@user_passes_test(is_admin)
def admin_approve_item(request, model_type, pk):
    # TRANSLATION GATE: Validate that all translations are complete
    is_valid, missing_fields = validate_translations(item, model_type)
    if not is_valid:
        messages.error(request, "Cannot approve: Missing translations...")
        return redirect(...)
    # ... proceed with approval
```

---

## 4. Template Usage

### Before (OLD - with fallback)
```django
{{ resource.title }}
{{ resource.get_localized_title }}
```

### After (NEW - strict i18n)
```django
{{ resource.title_display }}
{{ resource.description_display }}
```

---

## 5. Helper Module

A new utility module was created at `core/i18n_helpers.py` with:

```python
def get_active_language() -> str:
    """Normalize language to 'ar' or 'en'."""

def get_bilingual_field_suffix() -> str:
    """Get '_ar' or '_en' suffix."""

def get_context_field_label(base_label, include_language_hint=True) -> str:
    """Get label with language hint."""

class BilingualFormMixin:
    """Mixin for forms needing bilingual field handling."""

def validate_all_translations(item, field_configs) -> Tuple[bool, List[str]]:
    """Validate translations for approval workflow."""

def copy_to_bilingual_fields(data, field_mappings, current_lang=None) -> dict:
    """Map generic field data to bilingual fields."""
```

---

## 6. Database Migration Required

A migration needs to be created for the Institution model:

```bash
# Inside Docker container
docker-compose exec nlp_django python manage.py makemigrations institutions --name add_bilingual_description
docker-compose exec nlp_django python manage.py migrate
```

This adds:
- `description_ar` (TextField, blank)
- `description_en` (TextField, blank)

---

## 7. Workflow Summary

### User Submission (Arabic Site)
1. User visits Arabic version of site
2. Form shows "العنوان (بالعربية)" and "الوصف (بالعربية)"
3. User enters content in Arabic
4. Data saved to `title_ar`, `description_ar`
5. Item status = "pending"

### User Submission (English Site)
1. User visits English version of site
2. Form shows "Title (English)" and "Description (English)"
3. User enters content in English
4. Data saved to `title_en`, `description_en`
5. Item status = "pending"

### Admin Translation
1. Admin views pending item
2. Admin sees which language fields are filled
3. Admin enters missing translations
4. Admin clicks "Approve"

### Translation Gate Check
1. System checks if BOTH `title_ar` AND `title_en` are filled
2. System checks if BOTH `description_ar` AND `description_en` are filled
3. If ANY missing: Show error, prevent approval
4. If ALL filled: Approve and publish

### Frontend Display
1. User visits site in Arabic → `{{ item.title_display }}` returns `title_ar`
2. User visits site in English → `{{ item.title_display }}` returns `title_en`
3. **No fallback** - if translation missing, returns empty string

---

## 8. Files Modified

| File | Changes |
|------|---------|
| `accounts/models.py` | Added `full_name_display`, `bio_display` properties |
| `institutions/models.py` | Added `description_ar/en` fields, `name_display`, `description_display` |
| `resources/models.py` | Added `title_display`, `description_display` properties |
| `projects/models.py` | Added `title_display`, `description_display` properties |
| `events/models.py` | Added `title_display`, `description_display`, `location_display` |
| `forum/models.py` | Added `title_display`, `description_display` properties |
| `resources/forms.py` | Updated for context-aware bilingual fields |
| `events/forms.py` | Updated for context-aware bilingual fields |
| `projects/forms.py` | Updated for context-aware bilingual fields |
| `forum/forms.py` | **NEW FILE** - TopicForm with bilingual support |
| `forum/views.py` | Updated to use TopicForm |
| `institutions/forms.py` | Added `description_ar/en` fields to form |
| `pages/views.py` | Added Translation Gate validation |
| `core/__init__.py` | **NEW FILE** |
| `core/i18n_helpers.py` | **NEW FILE** - i18n utilities |

---

## 9. Testing Checklist

- [ ] Create resource in Arabic → verify saved to `*_ar` fields
- [ ] Create resource in English → verify saved to `*_en` fields
- [ ] Try to approve with missing translation → verify error shown
- [ ] Fill both translations → verify approval succeeds
- [ ] View in Arabic → verify `*_display` returns Arabic
- [ ] View in English → verify `*_display` returns English
- [ ] Edit existing item → verify correct language loaded
