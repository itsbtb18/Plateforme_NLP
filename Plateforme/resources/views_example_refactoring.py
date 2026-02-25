"""
EXAMPLE: Updated CorpusCreateView using the new ContentCreationService

This file demonstrates how to refactor existing views to use the new service layer.
Copy this pattern to update other creation views.

BEFORE vs AFTER Comparison
"""

# ============================================================================
# BEFORE: Old implementation (using FormView + ResourceForm)
# ============================================================================

class CorpusCreateView_OLD(LoginAndVerifiedRequiredMixin, FormView):
    """OLD PATTERN - Don't use this"""
    template_name = 'resources/corpus_create_form.html'
    form_class = ResourceForm
    success_url = reverse_lazy('resources:corpus_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_initial(self):
        initial = super().get_initial()
        initial['resource_type'] = 'corpus'
        return initial
    
    def form_valid(self, form):
        resource = form.save()
        messages.info(
            self.request, 
            _("Your corpus '%(title)s' has been submitted and is pending admin review.") % {'title': resource.title}
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page'] = 'resources'
        return context


# ============================================================================
# AFTER: New implementation (using CreateView + ContentCreationService)
# ============================================================================

from django.views.generic.edit import CreateView
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from accounts.views import LoginAndVerifiedRequiredMixin
from resources.models import Corpus
from core.content_service import ContentCreationService


class CorpusCreateView(LoginAndVerifiedRequiredMixin, CreateView):
    """
    NEW PATTERN - Professional content creation with service layer.
    
    Features:
    - Uses ContentCreationService for business logic
    - Modern template with rich text editor
    - Comprehensive validation and error handling
    - Automatic approval workflow
    - Detailed logging
    """
    model = Corpus
    template_name = 'resources/corpus_create_modern.html'
    fields = [
        'title_en', 'title_ar',
        'description_en', 'description_ar',
        'corpus_size', 'corpus_field', 'corpus_format',
        'language', 'keywords', 'access_link', 'uploaded_file'
    ]
    success_url = reverse_lazy('resources:corpus_list')
    
    def get_form(self, form_class=None):
        """Customize form to add Bootstrap classes and placeholders."""
        form = super().get_form(form_class)
        
        # Add CSS classes to all fields
        for field_name, field in form.fields.items():
            field.widget.attrs['class'] = 'form-control'
            
            # Add placeholders for better UX
            placeholders = {
                'title_en': 'Enter corpus title in English',
                'title_ar': 'أدخل عنوان المجموعة بالعربية',
                'corpus_size': 'Number of words/tokens (e.g., 10000)',
                'keywords': 'Comma-separated keywords (e.g., NLP, Arabic, corpus)',
                'access_link': 'https://example.com/corpus',
            }
            if field_name in placeholders:
                field.widget.attrs['placeholder'] = placeholders[field_name]
        
        return form
    
    def form_valid(self, form):
        """
        Handle form submission using ContentCreationService.
        
        This method:
        1. Uses the service layer for clean business logic
        2. Handles validation errors gracefully
        3. Provides appropriate user feedback
        4. Logs all operations
        """
        # Initialize the service
        service = ContentCreationService(
            user=self.request.user,
            content_type='corpus'
        )
        
        # Create the corpus using the service
        success, result = service.create_content(
            model_class=Corpus,
            data=form.cleaned_data
        )
        
        if success:
            # Success! Result is the created Corpus instance
            corpus = result
            
            # Determine if auto-approved or pending
            status = corpus.approval_status
            
            if status == 'approved':
                messages.success(
                    self.request,
                    _("Corpus '%(title)s' created and published successfully! It's now visible to all users.") 
                    % {'title': corpus.title}
                )
            else:
                messages.info(
                    self.request,
                    _("Corpus '%(title)s' submitted for review. You'll receive a notification once it's approved by our admin team.") 
                    % {'title': corpus.title}
                )
            
            return redirect(self.success_url)
            
        else:
            # Failure! Result is a dictionary of errors
            errors = result
            
            # Add errors to the form
            for field, error_list in errors.items():
                if field == 'error':
                    # Non-field errors
                    form.add_error(None, error_list)
                else:
                    # Field-specific errors
                    form.add_error(field, error_list)
            
            # Show general error message
            messages.error(
                self.request,
                _("Please correct the errors below and try again.")
            )
            
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        """Add extra context for the template."""
        context = super().get_context_data(**kwargs)
        context['page'] = 'resources'
        context['content_type'] = 'corpus'
        context['content_icon'] = 'database'  # FontAwesome icon
        return context


# ============================================================================
# ALTERNATIVE: Using the convenience function (even simpler)
# ============================================================================

from core.content_service import create_corpus

class CorpusCreateView_Alternative(LoginAndVerifiedRequiredMixin, CreateView):
    """
    Even simpler implementation using convenience function.
    Perfect for straightforward cases.
    """
    model = Corpus
    template_name = 'resources/corpus_create_modern.html'
    fields = ['title_en', 'title_ar', 'description_en', 'description_ar',
              'corpus_size', 'corpus_field', 'language']
    success_url = reverse_lazy('resources:corpus_list')
    
    def form_valid(self, form):
        # One-line creation using convenience function
        success, result = create_corpus(
            user=self.request.user,
            data=form.cleaned_data
        )
        
        if success:
            corpus = result
            messages.success(self.request, f"Corpus '{corpus}' created!")
            return redirect(self.success_url)
        else:
            for field, errors in result.items():
                form.add_error(field if field != 'error' else None, errors)
            return self.form_invalid(form)


# ============================================================================
# USAGE IN urls.py
# ============================================================================

"""
# resources/urls.py

from django.urls import path
from .views import CorpusCreateView

app_name = 'resources'

urlpatterns = [
    # ... other URLs ...
    path('corpus/create/', CorpusCreateView.as_view(), name='corpus_create'),
]
"""


# ============================================================================
# BENEFITS OF NEW APPROACH
# ============================================================================

"""
✅ BEFORE (Old System):
- Logic scattered in form.save() and view
- Inconsistent error handling
- Manual approval_status setting
- Basic logging
- Old template with plain textarea
- No standardization across different content types

✅ AFTER (New System):
- Business logic centralized in ContentCreationService
- Comprehensive error handling with proper logging
- Automatic approval workflow based on user permissions
- Structured logging with [CORPUS_CREATE] prefix
- Modern template with Quill rich text editor
- Consistent pattern for all content types (Corpus, Tool, Course, etc.)
- Easy to maintain and extend
- Reusable across different apps

PERFORMANCE:
- No performance overhead (same database operations)
- Better error handling = fewer failed requests
- Comprehensive logging = easier debugging

MAINTAINABILITY:
- Change business logic in one place (service layer)
- All content types follow same pattern
- Easy to add new features (e.g., email notifications)
- Clear separation of concerns

DEVELOPER EXPERIENCE:
- Clean, readable code
- Self-documenting with comprehensive docstrings
- Easy to test (service layer is easily mockable)
- Consistent API across all content types
"""
