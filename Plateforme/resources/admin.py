from django.contrib import admin
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from .models import Document, NLPTool, Course, Article, Thesis, Memoir, Corpus
from Plateforme.admin_forms import (
    DocumentAdminForm, NLPToolAdminForm, CourseAdminForm, CorpusAdminForm
)


# ============================================
# ADMIN ACTIONS FOR APPROVAL WORKFLOW
# ============================================

@admin.action(description=_("Approve selected items"))
def approve_selected(modeladmin, request, queryset):
    """Admin action to approve selected items."""
    updated = queryset.update(approval_status='approved')
    messages.success(request, _(f"{updated} item(s) have been approved."))


@admin.action(description=_("Reject and delete selected items"))
def reject_selected(modeladmin, request, queryset):
    """Admin action to reject and delete selected items."""
    count = queryset.count()
    queryset.delete()
    messages.warning(request, _(f"{count} item(s) have been rejected and deleted."))


@admin.action(description=_("Mark as pending review"))
def mark_pending(modeladmin, request, queryset):
    """Admin action to mark items as pending."""
    updated = queryset.update(approval_status='pending')
    messages.info(request, _(f"{updated} item(s) marked as pending."))


# ============================================
# BASE ADMIN CLASS FOR APPROVABLE RESOURCES
# ============================================

class ApprovableResourceAdmin(admin.ModelAdmin):
    """Base admin class for resources with approval workflow."""
    
    actions = [approve_selected, reject_selected, mark_pending]
    
    list_filter = ['approval_status', 'language', 'creation_date']
    search_fields = ['title', 'title_ar', 'title_en', 'description', 'keywords']
    date_hierarchy = 'creation_date'
    
    # Fieldsets for translation fields - to be customized in subclasses
    translation_fieldset = (
        _('Translation Fields (Admin fills before approval)'), {
            'fields': ('title_ar', 'title_en', 'description_ar', 'description_en'),
            'classes': ('collapse',),
            'description': _('Fill in the Arabic and English translations before approving this content.')
        }
    )
    
    approval_fieldset = (
        _('Approval Status'), {
            'fields': ('approval_status',),
            'classes': ('wide',),
        }
    )
    
    def status_badge(self, obj):
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
    status_badge.short_description = _('Status')
    status_badge.admin_order_field = 'approval_status'


# ============================================
# INLINES FOR DOCUMENT TYPES
# ============================================

class ArticleInline(admin.StackedInline):
    model = Article
    extra = 1


class ThesisInline(admin.StackedInline):
    model = Thesis
    extra = 1


class MemoirInline(admin.StackedInline):
    model = Memoir
    extra = 1


# ============================================
# DOCUMENT ADMIN
# ============================================

@admin.register(Document)
class DocumentAdmin(ApprovableResourceAdmin):
    form = DocumentAdminForm
    list_display = ['title', 'document_type', 'author', 'status_badge', 'creation_date']
    list_filter = ['approval_status', 'document_type', 'language', 'creation_date']
    
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'document_type', 'file_format', 'author', 'keywords', 'access_link', 'language')
        }),
        ApprovableResourceAdmin.translation_fieldset,
        ApprovableResourceAdmin.approval_fieldset,
    )
    
    def author_name(self, obj):
        return obj.author.get_full_name() or obj.author.email
    author_name.short_description = _('Author')

    def get_inlines(self, request, obj=None):
        """Display only the inline corresponding to the document type."""
        if obj:
            if obj.document_type == Document.DocumentType.ARTICLE:
                return [ArticleInline]
            elif obj.document_type == Document.DocumentType.THESIS:
                return [ThesisInline]
            elif obj.document_type == Document.DocumentType.MEMOIR:
                return [MemoirInline]
        return []


# ============================================
# NLP TOOL ADMIN
# ============================================

@admin.register(NLPTool)
class NLPToolAdmin(ApprovableResourceAdmin):
    form = NLPToolAdminForm
    list_display = ['title', 'tool_type', 'version', 'author', 'status_badge', 'creation_date']
    list_filter = ['approval_status', 'tool_type', 'supported_languages', 'creation_date']
    
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'tool_type', 'version', 'documentation_link', 
                      'supported_languages', 'author', 'keywords', 'access_link', 'language')
        }),
        ApprovableResourceAdmin.translation_fieldset,
        ApprovableResourceAdmin.approval_fieldset,
    )


# ============================================
# COURSE ADMIN
# ============================================

@admin.register(Course)
class CourseAdmin(ApprovableResourceAdmin):
    form = CourseAdminForm
    list_display = ['title', 'field', 'academic_level', 'teacher', 'institution', 'status_badge', 'creation_date']
    list_filter = ['approval_status', 'field', 'academic_level', 'institution', 'creation_date']
    
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'field', 'academic_level', 'teacher', 
                      'institution', 'academic_year', 'author', 'keywords', 'access_link', 'language')
        }),
        ApprovableResourceAdmin.translation_fieldset,
        ApprovableResourceAdmin.approval_fieldset,
    )


# ============================================
# CORPUS ADMIN
# ============================================

@admin.register(Corpus)
class CorpusAdmin(ApprovableResourceAdmin):
    form = CorpusAdminForm
    list_display = ['title', 'field', 'size', 'file_format', 'author', 'status_badge', 'creation_date']
    list_filter = ['approval_status', 'field', 'file_format', 'language', 'creation_date']
    
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'size', 'field', 'file_format', 
                      'author', 'keywords', 'access_link', 'language')
        }),
        ApprovableResourceAdmin.translation_fieldset,
        ApprovableResourceAdmin.approval_fieldset,
    )


# ============================================
# ARTICLE, THESIS, MEMOIR ADMIN
# ============================================

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ['get_title', 'journal', 'doi', 'publication_date']
    list_filter = ['publication_date']
    search_fields = ['document__title', 'journal', 'doi']
    
    def get_title(self, obj):
        return obj.document.title
    get_title.short_description = _('Title')


@admin.register(Thesis)
class ThesisAdmin(admin.ModelAdmin):
    list_display = ['get_title', 'supervisor', 'institution', 'defense_year']
    list_filter = ['defense_year', 'institution']
    search_fields = ['document__title', 'supervisor']
    
    def get_title(self, obj):
        return obj.document.title
    get_title.short_description = _('Title')


@admin.register(Memoir)
class MemoirAdmin(admin.ModelAdmin):
    list_display = ['get_title', 'academic_level', 'institution', 'defense_year']
    list_filter = ['defense_year', 'academic_level', 'institution']
    search_fields = ['document__title']
    
    def get_title(self, obj):
        return obj.document.title
    get_title.short_description = _('Title')


# ============================================
# PENDING REVIEW PROXY MODELS & ADMINS
# ============================================

class PendingDocument(Document):
    """Proxy model to show only pending documents in admin."""
    class Meta:
        proxy = True
        verbose_name = _('Pending Document')
        verbose_name_plural = _('Pending Documents')


class PendingNLPTool(NLPTool):
    """Proxy model to show only pending NLP tools in admin."""
    class Meta:
        proxy = True
        verbose_name = _('Pending NLP Tool')
        verbose_name_plural = _('Pending NLP Tools')


class PendingCourse(Course):
    """Proxy model to show only pending courses in admin."""
    class Meta:
        proxy = True
        verbose_name = _('Pending Course')
        verbose_name_plural = _('Pending Courses')


class PendingCorpus(Corpus):
    """Proxy model to show only pending corpora in admin."""
    class Meta:
        proxy = True
        verbose_name = _('Pending Corpus')
        verbose_name_plural = _('Pending Corpora')


@admin.register(PendingDocument)
class PendingDocumentAdmin(DocumentAdmin):
    """Admin view showing only pending documents for review."""
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(approval_status='pending')
    
    def has_add_permission(self, request):
        return False


@admin.register(PendingNLPTool)
class PendingNLPToolAdmin(NLPToolAdmin):
    """Admin view showing only pending NLP tools for review."""
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(approval_status='pending')
    
    def has_add_permission(self, request):
        return False


@admin.register(PendingCourse)
class PendingCourseAdmin(CourseAdmin):
    """Admin view showing only pending courses for review."""
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(approval_status='pending')
    
    def has_add_permission(self, request):
        return False


@admin.register(PendingCorpus)
class PendingCorpusAdmin(CorpusAdmin):
    """Admin view showing only pending corpora for review."""
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(approval_status='pending')
    
    def has_add_permission(self, request):
        return False

