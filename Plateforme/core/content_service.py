"""
Professional Content Creation Service
Provides reusable, clean logic for creating and managing content across all modules.
"""

import logging
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)
User = get_user_model()


class ContentCreationService:
    """
    Centralized service for handling content creation across all modules.
    Provides validation, logging, and consistent approval workflow.
    """

    def __init__(self, user: AbstractBaseUser, content_type: str):
        """
        Initialize the service.

        Args:
            user: The user creating the content
            content_type: Type of content (corpus, tool, project, etc.)
        """
        self.user = user
        self.content_type = content_type
        self.logger = logging.getLogger(f"content_service.{content_type}")

    def validate_bilingual_fields(
        self, data: dict[str, Any], fields: list
    ) -> dict[str, str]:
        """
        Validate that bilingual fields are provided.

        Args:
            data: Form data dictionary
            fields: List of field names to validate (e.g., ['title', 'description'])

        Returns:
            Dictionary of validation errors
        """
        errors = {}

        for field in fields:
            en_field = f"{field}_en"
            ar_field = f"{field}_ar"

            if not data.get(en_field) and not data.get(ar_field):
                errors[en_field] = _("At least one language version is required")
                errors[ar_field] = _("At least one language version is required")

        return errors

    def validate_required_fields(
        self, data: dict[str, Any], required_fields: list
    ) -> dict[str, str]:
        """
        Validate that required fields are present and not empty.

        Args:
            data: Form data dictionary
            required_fields: List of required field names

        Returns:
            Dictionary of validation errors
        """
        errors = {}

        for field in required_fields:
            value = data.get(field)
            if not value or (isinstance(value, str) and not value.strip()):
                errors[field] = _("This field is required")

        return errors

    def create_content(
        self,
        model_class: type[models.Model],
        data: dict[str, Any],
        extra_fields: dict[str, Any] | None = None,
    ) -> tuple:
        """
        Create content with proper validation and approval workflow.

        Args:
            model_class: The model class to create
            data: Cleaned form data
            extra_fields: Additional fields to set on the instance

        Returns:
            Tuple of (success: bool, instance_or_errors: Model or dict)
        """
        try:
            # Log the creation attempt
            self.logger.info(
                f"[{self.content_type.upper()}_CREATE] "
                f"User {self.user.username} (ID: {self.user.id}) attempting to create {self.content_type}"
            )

            # Determine approval status based on user permissions
            approval_status = "approved" if self.user.is_staff else "pending"

            # Create the instance
            instance = model_class(**data)

            # Set creator field (different models use different field names)
            creator_fields = ["created_by", "author", "coordinator", "creator"]
            for field in creator_fields:
                if hasattr(instance, field):
                    setattr(instance, field, self.user)
                    break

            # Set approval status
            if hasattr(instance, "approval_status"):
                instance.approval_status = approval_status

            # Set any extra fields
            if extra_fields:
                for field, value in extra_fields.items():
                    setattr(instance, field, value)

            # Validate and save
            instance.full_clean()
            instance.save()

            # Log success
            self.logger.info(
                f"[{self.content_type.upper()}_CREATE_SUCCESS] "
                f"{self.content_type.capitalize()} '{instance}' (ID: {instance.id}) "
                f"created successfully by {self.user.username}. "
                f"Status: {approval_status}"
            )

            return True, instance

        except ValidationError as e:
            # Log validation errors
            self.logger.error(
                f"[{self.content_type.upper()}_CREATE_VALIDATION_ERROR] "
                f"Validation failed for user {self.user.username}: {e.message_dict}",
                exc_info=True,
            )
            return False, e.message_dict

        except Exception as e:
            # Log unexpected errors
            self.logger.error(
                f"[{self.content_type.upper()}_CREATE_ERROR] "
                f"Unexpected error for user {self.user.username}: {str(e)}",
                exc_info=True,
            )
            return False, {
                "error": _("An unexpected error occurred. Please try again.")
            }

    def update_content(self, instance: models.Model, data: dict[str, Any]) -> tuple:
        """
        Update content with validation.

        Args:
            instance: The model instance to update
            data: New data to update with

        Returns:
            Tuple of (success: bool, instance_or_errors: Model or dict)
        """
        try:
            self.logger.info(
                f"[{self.content_type.upper()}_UPDATE] "
                f"User {self.user.username} updating {self.content_type} ID: {instance.id}"
            )

            # Update fields
            for field, value in data.items():
                if hasattr(instance, field):
                    setattr(instance, field, value)

            # Validate and save
            instance.full_clean()
            instance.save()

            self.logger.info(
                f"[{self.content_type.upper()}_UPDATE_SUCCESS] "
                f"{self.content_type.capitalize()} ID: {instance.id} updated successfully"
            )

            return True, instance

        except ValidationError as e:
            self.logger.error(
                f"[{self.content_type.upper()}_UPDATE_VALIDATION_ERROR] "
                f"Validation failed: {e.message_dict}",
                exc_info=True,
            )
            return False, e.message_dict

        except Exception as e:
            self.logger.error(
                f"[{self.content_type.upper()}_UPDATE_ERROR] "
                f"Unexpected error: {str(e)}",
                exc_info=True,
            )
            return False, {
                "error": _("An unexpected error occurred. Please try again.")
            }

    def get_pending_count(self, model_class: type[models.Model]) -> int:
        """
        Get count of pending items for this content type.

        Args:
            model_class: The model class to query

        Returns:
            Count of pending items
        """
        try:
            if hasattr(model_class, "approval_status"):
                return model_class.objects.filter(approval_status="pending").count()
            return 0
        except Exception as e:
            self.logger.error(
                f"[{self.content_type.upper()}_PENDING_COUNT_ERROR] {str(e)}"
            )
            return 0

    @staticmethod
    def approve_content(instance: models.Model, approver: AbstractBaseUser) -> bool:
        """
        Approve content.

        Args:
            instance: The content instance to approve
            approver: The user approving the content

        Returns:
            True if successful, False otherwise
        """
        try:
            if hasattr(instance, "approval_status"):
                instance.approval_status = "approved"
                instance.save()

                logger.info(
                    f"[CONTENT_APPROVED] {instance.__class__.__name__} ID: {instance.id} "
                    f"approved by {approver.username}"
                )
                return True
        except Exception as e:
            logger.error(
                f"[CONTENT_APPROVE_ERROR] Failed to approve {instance.__class__.__name__} "
                f"ID: {instance.id}: {str(e)}",
                exc_info=True,
            )
        return False

    @staticmethod
    def reject_content(
        instance: models.Model, rejector: AbstractBaseUser, reason: str | None = None
    ) -> bool:
        """
        Reject content.

        Args:
            instance: The content instance to reject
            rejector: The user rejecting the content
            reason: Optional rejection reason

        Returns:
            True if successful, False otherwise
        """
        try:
            if hasattr(instance, "approval_status"):
                instance.approval_status = "rejected"

                # Store rejection reason if the model supports it
                if reason and hasattr(instance, "rejection_reason"):
                    instance.rejection_reason = reason

                instance.save()

                logger.info(
                    f"[CONTENT_REJECTED] {instance.__class__.__name__} ID: {instance.id} "
                    f"rejected by {rejector.username}"
                    + (f" - Reason: {reason}" if reason else "")
                )
                return True
        except Exception as e:
            logger.error(
                f"[CONTENT_REJECT_ERROR] Failed to reject {instance.__class__.__name__} "
                f"ID: {instance.id}: {str(e)}",
                exc_info=True,
            )
        return False


# Convenience functions for common operations


def create_corpus(user: AbstractBaseUser, data: dict[str, Any]) -> tuple:
    """Create a corpus."""
    from resources.models import Corpus

    service = ContentCreationService(user, "corpus")
    return service.create_content(Corpus, data)


def create_tool(user: AbstractBaseUser, data: dict[str, Any]) -> tuple:
    """Create an NLP tool."""
    from resources.models import NLPTool

    service = ContentCreationService(user, "tool")
    return service.create_content(NLPTool, data)


def create_project(user: AbstractBaseUser, data: dict[str, Any]) -> tuple:
    """Create a project."""
    from projects.models import Project

    service = ContentCreationService(user, "project")
    return service.create_content(Project, data)


def create_event(user: AbstractBaseUser, data: dict[str, Any]) -> tuple:
    """Create an event."""
    from events.models import Event

    service = ContentCreationService(user, "event")
    return service.create_content(Event, data)


def create_institution(user: AbstractBaseUser, data: dict[str, Any]) -> tuple:
    """Create an institution."""
    from institutions.models import Institution

    service = ContentCreationService(user, "institution")
    return service.create_content(Institution, data)


def create_topic(user: AbstractBaseUser, data: dict[str, Any]) -> tuple:
    """Create a forum topic."""
    from forum.models import Topic

    service = ContentCreationService(user, "topic")
    return service.create_content(Topic, data)
