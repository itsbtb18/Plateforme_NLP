from django.db import models
from django.urls import reverse
from django.conf import settings
from institutions.models import Institution
import uuid
from django.utils.translation import gettext_lazy as _, pgettext_lazy
from django.db.models import Manager, QuerySet
from typing import Any
from datetime import datetime, date

class User(models.Model):
    id: int
    full_name: str
    is_staff: bool
    is_superuser: bool
    is_active: bool

class ProjectMemberQuerySet(QuerySet["ProjectMember"]): ...

class ProjectMemberManager(Manager["ProjectMember"]):
    def filter(self, *args: Any, **kwargs: Any) -> ProjectMemberQuerySet: ...
    def get(self, *args: Any, **kwargs: Any) -> "ProjectMember": ...

class ProjectQuerySet(QuerySet["Project"]): ...

class ProjectManager(Manager["Project"]):
    def filter(self, *args: Any, **kwargs: Any) -> ProjectQuerySet: ...
    def get(self, *args: Any, **kwargs: Any) -> "Project": ...

class Project(models.Model):
    STATUS_CHOICES = (
        ('ongoing', pgettext_lazy('project_status', 'Ongoing')),
        ('completed', pgettext_lazy('project_status', 'Completed')),          
        ('planned', pgettext_lazy('project_status', 'Planned')),    
    )
    APPROVAL_STATUS_CHOICES = (
        ('pending', pgettext_lazy('approval_status', 'Pending')),
        ('approved', pgettext_lazy('approval_status', 'Approved')),
        ('rejected', pgettext_lazy('approval_status', 'Rejected')),
    )
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    title = models.CharField(max_length=255)
    title_ar = models.CharField(max_length=255, blank=True, default='', verbose_name=_('Title (Arabic)'))
    title_en = models.CharField(max_length=255, blank=True, default='', verbose_name=_('Title (English)'))
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name='projects'
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='ongoing'
    )
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default='pending',
        verbose_name=_('Approval Status')
    )
    coordinator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='coordinated_projects'
    )
    description = models.TextField()
    description_ar = models.TextField(blank=True, default='', verbose_name=_('Description (Arabic)'))
    description_en = models.TextField(blank=True, default='', verbose_name=_('Description (English)'))
    date_start = models.DateField(blank=True, null=True)
    date_end = models.DateField(blank=True, null=True)
    attachment = models.FileField(upload_to='project_attachments/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_start', 'title']
        verbose_name = _('Project')
        verbose_name_plural = _('Projects')

    def __str__(self):
        return self.title

    def get_localized_title(self):
        """Return title based on current language"""
        from django.utils.translation import get_language
        lang = get_language()
        if lang == 'ar' and self.title_ar:
            return self.title_ar
        elif self.title_en:
            return self.title_en
        return self.title

    def get_localized_description(self):
        """Return description based on current language"""
        from django.utils.translation import get_language
        lang = get_language()
        if lang == 'ar' and self.description_ar:
            return self.description_ar
        elif self.description_en:
            return self.description_en
        return self.description

    @property
    def title_display(self):
        """Return title based on current language - NO fallback (strict i18n)."""
        from django.utils.translation import get_language
        lang = get_language()
        if lang and lang.startswith('ar'):
            return self.title_ar or ''
        return self.title_en or ''

    @property
    def description_display(self):
        """Return description based on current language - NO fallback (strict i18n)."""
        from django.utils.translation import get_language
        lang = get_language()
        if lang and lang.startswith('ar'):
            return self.description_ar or ''
        return self.description_en or ''

    def get_absolute_url(self):
        return reverse('projects:project_detail', kwargs={'pk': self.pk})


class ProjectMember(models.Model):
    STATUS_CHOICES = (
        ('pending', pgettext_lazy('member_status', 'Pending')),
        ('accepted', pgettext_lazy('member_status', 'Accepted')),
        ('rejected', pgettext_lazy('member_status', 'Rejected')),
    )
    LEAVE_REQUEST_STATUS_CHOICES = [
        ('none', pgettext_lazy('leave_status', 'None')),
        ('pending', pgettext_lazy('leave_status', 'Pending')),
        ('rejected', pgettext_lazy('leave_status', 'Rejected')),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='members'
    )
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='projects'
    )
    role = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    leave_request_status = models.CharField(
        max_length=10, 
        choices=LEAVE_REQUEST_STATUS_CHOICES, 
        default='none'
    )
    leave_request_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ('project', 'member')
        ordering = ['project', 'member']
        verbose_name = _('Project Member')
        verbose_name_plural = _('Project Members')

    def __str__(self):
        return f"{self.member.full_name} - {self.project.title}"

    def get_absolute_url(self):
        return reverse('projects:project_detail', kwargs={'pk': self.project.pk})