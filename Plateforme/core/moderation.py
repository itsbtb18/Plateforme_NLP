"""
Reusable moderation utilities for content approval workflow.

This module provides:
1. Base mixin for models with approval status
2. View mixin for handling content creation with moderation
3. Logging utilities for debugging moderation issues
"""
import logging
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from django.conf import settings
from typing import Optional

logger = logging.getLogger(__name__)


class ApprovalStatusChoices(models.TextChoices):
    """Standardized approval status choices."""
    PENDING = 'pending', _('Pending')
    APPROVED = 'approved', _('Approved')
    REJECTED = 'rejected', _('Rejected')


class ModerationMixin(models.Model):
    """
    Abstract mixin for models requiring moderation.
    
    Provides:
    - approval_status field with default='pending'
    - created_at timestamp
    - Helper methods for approval workflow
    """
    
    approval_status = models.CharField(
        max_length=20,
        choices=ApprovalStatusChoices.choices,
        default=ApprovalStatusChoices.PENDING,
        verbose_name=_("Approval Status"),
        help_text=_("Content must be approved by admin before being publicly visible"),
        db_index=True  # Index for faster filtering
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At"),
        db_index=True
    )
    
    class Meta:
        abstract = True
    
    def approve(self):
        """Approve this content."""
        self.approval_status = ApprovalStatusChoices.APPROVED
        self.save(update_fields=['approval_status'])
        logger.info(f"{self.__class__.__name__} {self.pk} approved")
        return self
    
    def reject(self):
        """Reject this content."""
        self.approval_status = ApprovalStatusChoices.REJECTED
        self.save(update_fields=['approval_status'])
        logger.info(f"{self.__class__.__name__} {self.pk} rejected")
        return self
    
    def is_approved(self):
        """Check if content is approved."""
        return self.approval_status == ApprovalStatusChoices.APPROVED
    
    def is_pending(self):
        """Check if content is pending approval."""
        return self.approval_status == ApprovalStatusChoices.PENDING
    
    def is_rejected(self):
        """Check if content is rejected."""
        return self.approval_status == ApprovalStatusChoices.REJECTED


class ModeratedContentCreationMixin:
    """
    View mixin for handling moderated content creation.
    
    Usage in CreateView:
        class MyContentCreateView(ModeratedContentCreationMixin, CreateView):
            model = MyModel
            form_class = MyForm
            
            def get_author_field_name(self):
                return 'author'  # or 'created_by', 'creator', etc.
    """
    
    def get_author_field_name(self) -> str:
        """
        Return the name of the field that stores the creator.
        Override this in subclasses if needed.
        """
        # Common field names
        for field in ['author', 'created_by', 'creator', 'coordinator']:
            if hasattr(self.model, field):
                return field
        raise NotImplementedError(
            f"Could not find author field in {self.model.__name__}. "
            "Override get_author_field_name() method."
        )
    
    def form_valid(self, form):
        """Handle form submission with automatic moderation setup."""
        instance = form.instance
        
        # Set the author/creator
        author_field = self.get_author_field_name()
        setattr(instance, author_field, self.request.user)
        logger.info(
            f"Creating {instance.__class__.__name__} by user {self.request.user.email}"
        )
        
        # Set approval status
        if self.request.user.is_staff:
            instance.approval_status = ApprovalStatusChoices.APPROVED
            logger.info(f"Auto-approving {instance.__class__.__name__} created by staff")
        else:
            instance.approval_status = ApprovalStatusChoices.PENDING
            logger.info(f"Setting {instance.__class__.__name__} to pending approval")
        
        # Save the instance
        try:
            response = super().form_valid(form)
            
            # Log successful creation
            logger.info(
                f"Successfully created {instance.__class__.__name__} "
                f"(ID: {instance.pk}, Status: {instance.approval_status})"
            )
            
            # Add appropriate message
            if instance.approval_status == ApprovalStatusChoices.APPROVED:
                messages.success(
                    self.request,
                    _("Your submission has been published successfully!")
                )
            else:
                messages.info(
                    self.request,
                    _("Your submission has been received and is pending admin review. "
                      "It will be visible to the public once approved.")
                )
            
            return response
            
        except Exception as e:
            logger.error(
                f"Error creating {instance.__class__.__name__}: {str(e)}",
                exc_info=True
            )
            messages.error(
                self.request,
                _("An error occurred while submitting your content. Please try again.")
            )
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        """Log form validation errors."""
        logger.warning(
            f"Form validation failed for {self.model.__name__}: {form.errors.as_json()}"
        )
        messages.error(
            self.request,
            _("Please correct the errors below and try again.")
        )
        return super().form_invalid(form)


def log_moderation_action(model_name: str, instance_id, action: str, 
                          user_email: Optional[str] = None, details: Optional[str] = None):
    """
    Centralized logging for moderation actions.
    
    Args:
        model_name: Name of the model (e.g., 'Corpus', 'Event')
        instance_id: ID of the instance
        action: Action performed ('created', 'approved', 'rejected', 'deleted')
        user_email: Email of the user performing the action
        details: Additional details
    """
    log_message = (
        f"MODERATION: {action.upper()} - {model_name} (ID: {instance_id})"
    )
    if user_email:
        log_message += f" by {user_email}"
    if details:
        log_message += f" - {details}"
    
    logger.info(log_message)


def get_pending_count(model_class) -> int:
    """
    Get count of pending items for a model.
    
    Args:
        model_class: Django model class with approval_status field
        
    Returns:
        Count of pending items
    """
    try:
        if hasattr(model_class, 'approval_status'):
            return model_class.objects.filter(
                approval_status=ApprovalStatusChoices.PENDING
            ).count()
        return 0
    except Exception as e:
        logger.error(f"Error getting pending count for {model_class.__name__}: {e}")
        return 0


def get_approved_count(model_class) -> int:
    """
    Get count of approved items for a model.
    
    Args:
        model_class: Django model class with approval_status field
        
    Returns:
        Count of approved items
    """
    try:
        if hasattr(model_class, 'approval_status'):
            return model_class.objects.filter(
                approval_status=ApprovalStatusChoices.APPROVED
            ).count()
        return 0
    except Exception as e:
        logger.error(f"Error getting approved count for {model_class.__name__}: {e}")
        return 0
