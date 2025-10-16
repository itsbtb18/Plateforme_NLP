from django.db import models
from django.urls import reverse
from django.conf import settings
from institutions.models import Institution
import uuid
from django.utils.translation import gettext_lazy as _
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
        ('ongoing', _('قيد الإنجاز')),
        ('completed', _('منجز')),          
        ('planned', _('مخطط له')),    
    )
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    title = models.CharField(max_length=255)
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
    coordinator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='coordinated_projects'
    )
    description = models.TextField()
    date_start = models.DateField(blank=True, null=True)
    date_end = models.DateField(blank=True, null=True)
    attachment = models.FileField(upload_to='project_attachments/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_start', 'title']
        verbose_name = 'Project'
        verbose_name_plural = 'Projects'

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('projects:project_detail', kwargs={'pk': self.pk})


class ProjectMember(models.Model):
    STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('accepted', 'Accepté'),
        ('rejected', 'Refusé'),
    )
    LEAVE_REQUEST_STATUS_CHOICES = [
        ('none', 'None'),
        ('pending', 'Pending'),
        ('rejected', 'Rejected'),
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
        verbose_name = 'Project Member'
        verbose_name_plural = 'Project Members'

    def __str__(self):
        return f"{self.member.full_name} - {self.project.title}"

    def get_absolute_url(self):
        return reverse('projects:project_detail', kwargs={'pk': self.project.pk})