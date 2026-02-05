"""
Internationalization helpers for context-aware form handling.

This module provides utilities for:
1. Language-dependent field display in forms
2. Mapping form fields to model bilingual fields
3. Translation validation for admin approval workflow
"""

from __future__ import annotations

from typing import Any, ClassVar

from django.utils.translation import get_language, gettext_lazy as _


def get_active_language():
    """Get the current language, normalizing to 'ar' or 'en'."""
    lang = get_language()
    if lang and lang.startswith('ar'):
        return 'ar'
    return 'en'


def get_bilingual_field_suffix():
    """Get the appropriate field suffix based on current language."""
    return f'_{get_active_language()}'


def get_context_field_label(base_label, include_language_hint=True):
    """
    Get a label appropriate for current language context.
    
    Args:
        base_label: The base label without language specification
        include_language_hint: Whether to add a language hint in parentheses
    
    Returns:
        Label string with or without language hint
    """
    if not include_language_hint:
        return base_label
    
    lang = get_active_language()
    if lang == 'ar':
        return f"{base_label} (بالعربية)"
    return f"{base_label} (English)"


class BilingualFormMixin:
    """
    Mixin for forms that need to handle bilingual input based on current language.
    
    Usage:
        class MyForm(BilingualFormMixin, forms.ModelForm):
            bilingual_fields = {
                'title': ('title_ar', 'title_en'),
                'description': ('description_ar', 'description_en'),
            }
    
    The mixin will:
    1. Show only the current language field to the user
    2. Map the generic field to the appropriate _ar/_en model field
    3. Auto-populate labels with language context
    """
    
    # Override in subclass: {'generic_name': ('ar_field', 'en_field'), ...}
    bilingual_fields: ClassVar[dict[str, tuple[str, str]]] = {}
    
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._setup_bilingual_fields()
    
    def _setup_bilingual_fields(self) -> None:
        """Configure bilingual fields based on current language."""
        lang = get_active_language()
        
        for generic_name, (ar_field, en_field) in self.bilingual_fields.items():
            target_field = ar_field if lang == 'ar' else en_field
            
            # If the form has the generic field but not the target field
            # self.fields is provided by the Form class this mixin is used with
            if generic_name in self.fields:  # type: ignore[attr-defined]
                field = self.fields[generic_name]  # type: ignore[attr-defined]
                
                # Update label with language hint
                if hasattr(field, 'label') and field.label:
                    base_label = str(field.label).replace(' *', '').replace(' (Arabic)', '').replace(' (English)', '')
                    field.label = get_context_field_label(base_label)
                
                # Store mapping info for save()
                field.bilingual_target = target_field
    
    def save_bilingual_fields(self, instance: Any) -> Any:
        """
        Save form data to the appropriate bilingual model fields.
        Call this from your save() method.
        
        Args:
            instance: The model instance being saved
        
        Returns:
            The instance with bilingual fields populated
        """
        for generic_name, (ar_field, en_field) in self.bilingual_fields.items():
            # self.cleaned_data is provided by the Form class this mixin is used with
            if generic_name in self.cleaned_data:  # type: ignore[attr-defined]
                value = self.cleaned_data[generic_name]  # type: ignore[attr-defined]
                lang = get_active_language()
                
                target_field = ar_field if lang == 'ar' else en_field
                setattr(instance, target_field, value)
                
                # Also set legacy field if it exists
                if hasattr(instance, generic_name):
                    setattr(instance, generic_name, value)
        
        return instance


def get_bilingual_labels(field_name, ar_label=None, en_label=None):
    """
    Get the appropriate label for a field based on current language.
    
    Args:
        field_name: The base field name
        ar_label: Custom Arabic label (defaults to "{field_name} (Arabic)")
        en_label: Custom English label (defaults to "{field_name} (English)")
    
    Returns:
        The appropriate label string
    """
    lang = get_active_language()
    
    if lang == 'ar':
        return ar_label or f"{field_name} (بالعربية)"
    return en_label or f"{field_name} (English)"


def validate_all_translations(item, field_configs):
    """
    Validate that all required translation fields are filled.
    
    Args:
        item: The model instance to validate
        field_configs: Dict mapping field names to (ar_field, en_field) tuples
    
    Returns:
        Tuple of (is_valid, list_of_missing_fields)
    """
    missing_fields = []
    
    for field_name, (ar_field, en_field) in field_configs.items():
        ar_value = getattr(item, ar_field, None)
        en_value = getattr(item, en_field, None)
        
        if not ar_value or not str(ar_value).strip():
            missing_fields.append(f"{field_name} (Arabic)")
        if not en_value or not str(en_value).strip():
            missing_fields.append(f"{field_name} (English)")
    
    return len(missing_fields) == 0, missing_fields


def copy_to_bilingual_fields(data, field_mappings, current_lang=None):
    """
    Map generic field data to bilingual fields based on current language.
    
    Args:
        data: Dictionary of form data (e.g., cleaned_data)
        field_mappings: Dict mapping generic names to (ar_field, en_field) tuples
        current_lang: Override language detection (for testing)
    
    Returns:
        Dictionary with bilingual field values set
    """
    lang = current_lang or get_active_language()
    result = dict(data)
    
    for generic_name, (ar_field, en_field) in field_mappings.items():
        if generic_name in data:
            value = data[generic_name]
            target_field = ar_field if lang == 'ar' else en_field
            result[target_field] = value
    
    return result
