from django.contrib import admin
from django.contrib import messages
from django.utils.translation import gettext_lazy as _, ngettext
from django.utils.html import format_html
from .models import Project, ProjectMember
from Plateforme.admin_forms import ProjectAdminForm


# ============================================
# ADMIN ACTIONS FOR APPROVAL WORKFLOW
# ============================================

@admin.action(description=_("Approve selected projects"))
def approve_projects(modeladmin, request, queryset):
    """Admin action to approve selected projects (validates translations)."""
    approved = 0
    skipped = []
    for project in queryset:
        missing = []
        if not (project.title_ar or '').strip() or not (project.title_en or '').strip():
            missing.append(str(_("Title")))
        if not (project.description_ar or '').strip() or not (project.description_en or '').strip():
            missing.append(str(_("Description")))
        if missing:
            skipped.append(f"{project.title} ({', '.join(missing)})")
        else:
            project.approval_status = 'approved'
            project.save(update_fields=['approval_status'])
            approved += 1
    if approved:
        messages.success(
            request,
            ngettext(
                "%(count)d project approved.",
                "%(count)d projects approved.",
                approved,
            ) % {'count': approved},
        )
    if skipped:
        messages.error(
            request,
            _("Could not approve (missing translations): %(items)s") % {'items': '; '.join(skipped)},
        )


@admin.action(description=_("Reject and delete selected projects"))
def reject_projects(modeladmin, request, queryset):
    """Admin action to reject and delete selected projects."""
    count = queryset.count()
    queryset.delete()
    messages.warning(
        request,
        ngettext(
            "%(count)d project rejected and deleted.",
            "%(count)d projects rejected and deleted.",
            count,
        ) % {'count': count},
    )


@admin.action(description=_("Mark as pending review"))
def mark_projects_pending(modeladmin, request, queryset):
    """Admin action to mark projects as pending."""
    updated = queryset.update(approval_status='pending')
    messages.info(
        request,
        ngettext(
            "%(count)d project marked as pending.",
            "%(count)d projects marked as pending.",
            updated,
        ) % {'count': updated},
    )


# ============================================
# PROJECT ADMIN
# ============================================

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    form = ProjectAdminForm
    list_display = ['title', 'institution', 'coordinator', 'status', 'approval_status_badge', 'created_at']
    list_filter = ['approval_status', 'status', 'institution', 'created_at']
    search_fields = ['title', 'title_ar', 'title_en', 'description', 'coordinator__email']
    date_hierarchy = 'created_at'
    actions = [approve_projects, reject_projects, mark_projects_pending]

    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'institution', 'coordinator', 'status',
                       'date_start', 'date_end', 'attachment')
        }),
        (_('Translation Fields (Admin fills before approval)'), {
            'fields': ('title_ar', 'title_en', 'description_ar', 'description_en'),
            'description': _('Fill in the Arabic and English translations before approving.')
        }),
        (_('Approval Status'), {
            'fields': ('approval_status',),
            'classes': ('wide',),
        }),
    )

    def approval_status_badge(self, obj):
        """Display approval status as a colored badge."""
        colors = {
            'pending': '#ffc107',
            'approved': '#28a745',
            'rejected': '#dc3545',
        }
        color = colors.get(obj.approval_status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_approval_status_display()
        )
    approval_status_badge.short_description = _('Approval Status')
    approval_status_badge.admin_order_field = 'approval_status'


# ============================================
# PENDING PROJECT PROXY MODEL & ADMIN
# ============================================

class PendingProject(Project):
    """Proxy model to show only pending projects in admin."""
    class Meta:
        proxy = True
        verbose_name = _('Pending Project')
        verbose_name_plural = _('Pending Projects')


@admin.register(PendingProject)
class PendingProjectAdmin(ProjectAdmin):
    """Admin view showing only pending projects for review."""

    def get_queryset(self, request):
        return super().get_queryset(request).filter(approval_status='pending')

    def has_add_permission(self, request):
        return False


@admin.register(ProjectMember)
class ProjectMemberAdmin(admin.ModelAdmin):
    list_display = ['member', 'project', 'role', 'status', 'created_at']
    list_filter = ['status', 'project']
    search_fields = ['member__email', 'project__title', 'role']


