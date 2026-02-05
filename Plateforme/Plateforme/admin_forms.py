"""
Admin forms with translation validation for approval workflow.

These forms ensure that bilingual content (Arabic and English) is provided
before an admin can approve any content.
"""

from __future__ import annotations

from typing import Any, ClassVar, List, Tuple

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class BilingualApprovalFormMixin:
    """
    Mixin for admin forms that require bilingual content before approval.
    
    Subclasses must define:
    - bilingual_fields: list of tuples (ar_field, en_field, display_name)
    """
    
    bilingual_fields: ClassVar[List[Tuple[str, str, str]]] = []  # Override in subclass
    
    def clean(self) -> dict[str, Any]:
        # Call parent clean() - when used with ModelForm, this calls forms.ModelForm.clean()
        cleaned_data: dict[str, Any] = super().clean()  # type: ignore[misc]
        approval_status = cleaned_data.get('approval_status')
        
        if approval_status == 'approved':
            missing_translations = []
            
            for ar_field, en_field, display_name in self.bilingual_fields:
                ar_value = cleaned_data.get(ar_field, '') or ''
                en_value = cleaned_data.get(en_field, '') or ''
                
                if not ar_value.strip() or not en_value.strip():
                    missing_translations.append(display_name)
            
            if missing_translations:
                fields_list = ', '.join(missing_translations)
                raise ValidationError(
                    _("You must provide both Arabic and English translations for the following fields before approving this content: %(fields)s"),
                    code='missing_translation',
                    params={'fields': fields_list}
                )
        
        return cleaned_data


# ============================================
# RESOURCE ADMIN FORMS
# ============================================

class DocumentAdminForm(BilingualApprovalFormMixin, forms.ModelForm):
    """Admin form for Document with translation validation."""
    
    bilingual_fields = [
        ('title_ar', 'title_en', _('Title')),
        ('description_ar', 'description_en', _('Description')),
    ]
    
    class Meta:
        from resources.models import Document
        model = Document
        fields = '__all__'


class NLPToolAdminForm(BilingualApprovalFormMixin, forms.ModelForm):
    """Admin form for NLPTool with translation validation."""
    
    bilingual_fields = [
        ('title_ar', 'title_en', _('Title')),
        ('description_ar', 'description_en', _('Description')),
    ]
    
    class Meta:
        from resources.models import NLPTool
        model = NLPTool
        fields = '__all__'


class CourseAdminForm(BilingualApprovalFormMixin, forms.ModelForm):
    """Admin form for Course with translation validation."""
    
    bilingual_fields = [
        ('title_ar', 'title_en', _('Title')),
        ('description_ar', 'description_en', _('Description')),
    ]
    
    class Meta:
        from resources.models import Course
        model = Course
        fields = '__all__'


class CorpusAdminForm(BilingualApprovalFormMixin, forms.ModelForm):
    """Admin form for Corpus with translation validation."""
    
    bilingual_fields = [
        ('title_ar', 'title_en', _('Title')),
        ('description_ar', 'description_en', _('Description')),
    ]
    
    class Meta:
        from resources.models import Corpus
        model = Corpus
        fields = '__all__'


# ============================================
# PROJECT ADMIN FORM
# ============================================

class ProjectAdminForm(BilingualApprovalFormMixin, forms.ModelForm):
    """Admin form for Project with translation validation."""
    
    bilingual_fields = [
        ('title_ar', 'title_en', _('Title')),
        ('description_ar', 'description_en', _('Description')),
    ]
    
    class Meta:
        from projects.models import Project
        model = Project
        fields = '__all__'


# ============================================
# EVENT ADMIN FORM
# ============================================

class EventAdminForm(BilingualApprovalFormMixin, forms.ModelForm):
    """Admin form for Event with translation validation."""
    
    bilingual_fields = [
        ('title_ar', 'title_en', _('Title')),
        ('description_ar', 'description_en', _('Description')),
        ('location_ar', 'location_en', _('Location')),
    ]
    
    class Meta:
        from events.models import Event
        model = Event
        fields = '__all__'


# ============================================
# FORUM ADMIN FORM
# ============================================

class TopicAdminForm(BilingualApprovalFormMixin, forms.ModelForm):
    """Admin form for Topic with translation validation."""
    
    bilingual_fields = [
        ('title_ar', 'title_en', _('Title')),
        ('description_ar', 'description_en', _('Description')),
    ]
    
    class Meta:
        from forum.models import Topic
        model = Topic
        fields = '__all__'
