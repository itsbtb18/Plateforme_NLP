from django.http import Http404
from django.utils.timezone import now
from django.shortcuts import redirect, render, get_object_or_404
from django.views.generic import ListView, DetailView
from django.views.generic.edit import CreateView, FormView, UpdateView, DeleteView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse, reverse_lazy
from django.db.models import Q, F
from django.contrib import messages
from .forms import ResourceForm
from django.conf import settings
from accounts.views import LoginAndVerifiedRequiredMixin
from django.db import models
from .models import Document, NLPTool, Article, Thesis, Memoir, Course, Corpus, ResourceBase
from django.contrib.auth import get_user_model
from notifications.models import Notification
from django.utils.translation import gettext_lazy as _
import logging
from typing import Any, Dict, List, Optional, Sequence, Union, cast, Type

logger = logging.getLogger(__name__)

ResourceVariant = Union[Document, NLPTool, Course, Corpus]


class ResourceListView(LoginAndVerifiedRequiredMixin, ListView):
    template_name = 'resources/list.html'
    context_object_name = 'resources'
    paginate_by = 9

    def get_queryset(self) -> List[ResourceVariant]:
        search_query = self.request.GET.get('q', '')
        resource_type = self.request.GET.get('type', '')
        field_filter = self.request.GET.get('field', '')
        language_filter = self.request.GET.get('language', '')
        
        # Base filter: only show approved content (unless staff)
        approval_filter = {} if self.request.user.is_staff else {'approval_status': 'approved'}
        
        querysets = []
        
        if resource_type in ['', 'article', 'thesis', 'memoir']:
            docs = Document.objects.filter(**approval_filter)
            if language_filter:
                docs = docs.filter(language=language_filter)
            if resource_type in ['article', 'thesis', 'memoir']:
                docs = docs.filter(document_type=resource_type)
            if search_query:
                docs = docs.filter(
                    Q(title__icontains=search_query) | 
                    Q(description__icontains=search_query) |
                    Q(title_ar__icontains=search_query) |
                    Q(title_en__icontains=search_query)
                )
            querysets.append(docs)
        
        if resource_type in ['', 'tool']:
            tools = NLPTool.objects.filter(**approval_filter)
            if language_filter:
                tools = tools.filter(supported_languages__contains=language_filter)
            if search_query:
                tools = tools.filter(
                    Q(title__icontains=search_query) | 
                    Q(description__icontains=search_query) |
                    Q(title_ar__icontains=search_query) |
                    Q(title_en__icontains=search_query)
                )
            querysets.append(tools)
        
        if resource_type in ['', 'course']:
            courses = Course.objects.filter(**approval_filter)
            if language_filter:
                courses = courses.filter(language=language_filter)
            if field_filter:
                courses = courses.filter(field=field_filter)
            if search_query:
                courses = courses.filter(
                    Q(title__icontains=search_query) | 
                    Q(description__icontains=search_query) |
                    Q(title_ar__icontains=search_query) |
                    Q(title_en__icontains=search_query)
                )
            querysets.append(courses)
        
        if resource_type in ['', 'corpus']:
            corpora = Corpus.objects.filter(**approval_filter)
            if language_filter:
                corpora = corpora.filter(language=language_filter)
            if field_filter:
                corpora = corpora.filter(field=field_filter)
            if search_query:
                corpora = corpora.filter(
                    Q(title__icontains=search_query) | 
                    Q(description__icontains=search_query) |
                    Q(title_ar__icontains=search_query) |
                    Q(title_en__icontains=search_query)
                )
            querysets.append(corpora)

        combined: List[ResourceVariant] = []
        for qs in querysets:
            for obj in qs:
                obj.resource_type = self.get_resource_type(obj)
                combined.append(obj)

        # Handle sorting
        sort_by = self.request.GET.get('sort', 'newest')
        if sort_by == 'oldest':
            return sorted(combined, key=lambda x: x.creation_date, reverse=False)
        elif sort_by == 'popular':
            return sorted(combined, key=lambda x: getattr(x, 'views_count', 0), reverse=True)
        else:  # default: newest
            return sorted(combined, key=lambda x: x.creation_date, reverse=True)

    def get_resource_type(self, obj):
        if isinstance(obj, Document):
            return obj.document_type
        elif isinstance(obj, NLPTool):
            return 'tool'
        elif isinstance(obj, Course):
            return 'course'
        elif isinstance(obj, Corpus):
            return 'corpus'
        return 'unknown'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_query'] = self.request.GET.urlencode()
        resources = cast(Sequence[ResourceVariant], self.object_list)
        context['total_count'] = len(resources)
        from .models import FieldChoices
        context['field_choices'] = FieldChoices.choices
        context['current_field'] = self.request.GET.get('field', '')
        context['current_language'] = self.request.GET.get('language', '')
        context['current_type'] = self.request.GET.get('type', '')
        context['current_sort'] = self.request.GET.get('sort', 'newest')
        context['page'] = 'resources'
        return context


class ToolListView(LoginAndVerifiedRequiredMixin, ListView):
    model = NLPTool
    template_name = 'resources/tool_list.html'
    context_object_name = 'tools'
    paginate_by = 12
    
    def get_queryset(self):
        # Only show approved content (unless staff)
        if self.request.user.is_staff:
            queryset = NLPTool.objects.all()
        else:
            queryset = NLPTool.objects.filter(approval_status='approved')
        
        # Filter by tool type/category
        tool_type = self.request.GET.get('type', '').strip()
        if tool_type:
            queryset = queryset.filter(tool_type=tool_type)
        
        # Search functionality
        search_query = self.request.GET.get('q', '').strip()
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(title_ar__icontains=search_query) |
                Q(title_en__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(tool_type__icontains=search_query) |
                Q(keywords__icontains=search_query) |
                Q(author__first_name__icontains=search_query) |
                Q(author__last_name__icontains=search_query) |
                Q(supported_languages__icontains=search_query)
            ).distinct()
        
        return queryset.order_by('-creation_date')
    
    def get_template_names(self):
        """Return partial template for AJAX requests"""
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return ['resources/_tool_cards.html']
        return [self.template_name]
     
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search_query = self.request.GET.get('q', '')
        tool_type = self.request.GET.get('type', '')
        
        # Always use filtered queryset for count (respects approval_status)
        context['total_count'] = self.get_queryset().count()
        
        if search_query:
            context['search_query'] = search_query
            context['is_search'] = True
        else:
            context['is_search'] = False
        
        # Tool type choices for filter chips
        context['tool_type_choices'] = NLPTool.ToolType.choices
        
        context['current_type'] = tool_type
        context['page'] = 'tools'
        return context


class CourseListView(LoginAndVerifiedRequiredMixin, ListView):
    model = Course
    template_name = 'resources/course_list.html'
    context_object_name = 'courses'
    paginate_by = 12
    
    def get_queryset(self):
        # Only show approved content to public (staff sees all)
        if self.request.user.is_authenticated and self.request.user.is_staff:
            queryset = Course.objects.all()
        else:
            queryset = Course.objects.filter(approval_status='approved')
        
        search_query = self.request.GET.get('q', '').strip()
        
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(title_ar__icontains=search_query) |
                Q(title_en__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(keywords__icontains=search_query) |
                Q(author__first_name__icontains=search_query) |
                Q(author__last_name__icontains=search_query) |
                Q(field__icontains=search_query) |
                Q(academic_level__icontains=search_query) |
                Q(institution__name__icontains=search_query)
            ).distinct()
        
        return queryset.order_by('-creation_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search_query = self.request.GET.get('q', '')
        
        # Always use filtered queryset for count (respects approval_status)
        context['total_count'] = self.get_queryset().count()
        
        if search_query:
            context['search_query'] = search_query
            context['is_search'] = True
        else:
            context['is_search'] = False
        
        context['page'] = 'course'
        return context


class ArticleListView(LoginAndVerifiedRequiredMixin, ListView):
    model = Article
    template_name = 'resources/article_list.html'
    context_object_name = 'articles'
    
    def get_queryset(self):
        # Only show approved articles (staff sees all, users see own + approved)
        if self.request.user.is_staff:
            return Article.objects.all()
        return Article.objects.filter(
            Q(approval_status='approved') | 
            Q(author=self.request.user)
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_count'] = self.get_queryset().count()
        return context


class ThesisListView(LoginAndVerifiedRequiredMixin, ListView):
    model = Thesis
    template_name = 'resources/thesis_list.html'
    context_object_name = 'theses'
    
    def get_queryset(self):
        # Only show approved theses (staff sees all, users see own + approved)
        if self.request.user.is_staff:
            return Thesis.objects.all()
        return Thesis.objects.filter(
            Q(approval_status='approved') | 
            Q(author=self.request.user)
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_count'] = self.get_queryset().count()
        return context


class MemoirListView(LoginAndVerifiedRequiredMixin, ListView):
    model = Memoir
    template_name = 'resources/memoir_list.html'
    context_object_name = 'memoirs'
    
    def get_queryset(self):
        # Only show approved memoirs (staff sees all, users see own + approved)
        if self.request.user.is_staff:
            return Memoir.objects.all()
        return Memoir.objects.filter(
            Q(approval_status='approved') | 
            Q(author=self.request.user)
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_count'] = self.get_queryset().count()
        return context


class CorpusListView(LoginAndVerifiedRequiredMixin, ListView):
    model = Corpus
    template_name = 'resources/corpus_list.html'
    context_object_name = 'corpora'
    paginate_by = 12
    
    def get_queryset(self):
        # Only show approved content (unless staff)
        if self.request.user.is_staff:
            queryset = Corpus.objects.all()
        else:
            queryset = Corpus.objects.filter(approval_status='approved')
        
        # Search query
        search_query = self.request.GET.get('q', '').strip()
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(title_ar__icontains=search_query) |
                Q(title_en__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(keywords__icontains=search_query) |
                Q(author__first_name__icontains=search_query) |
                Q(author__last_name__icontains=search_query) |
                Q(field__icontains=search_query) |
                Q(file_format__icontains=search_query)
            ).distinct()
        
        # Filter by fields (categories) - supports multiple values
        fields = self.request.GET.getlist('field')
        if fields:
            queryset = queryset.filter(field__in=fields)
        
        # Filter by file formats - supports multiple values
        formats = self.request.GET.getlist('format')
        if formats:
            # Case-insensitive format matching
            format_q = Q()
            for fmt in formats:
                format_q |= Q(file_format__iexact=fmt)
            queryset = queryset.filter(format_q)
        
        # Filter by languages - supports multiple values
        languages = self.request.GET.getlist('language')
        if languages:
            queryset = queryset.filter(language__in=languages)
        
        return queryset.order_by('-creation_date')
    
    def render_to_response(self, context, **response_kwargs):
        # Return partial HTML for AJAX requests
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return render(self.request, 'resources/_corpus_cards.html', context)
        return super().render_to_response(context, **response_kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search_query = self.request.GET.get('q', '')
        
        # Always use filtered queryset for count (respects approval_status)
        context['total_count'] = self.get_queryset().count()
        
        if search_query:
            context['search_query'] = search_query
            context['is_search'] = True
        else:
            context['is_search'] = False
        
        # Provide field choices for the filter sidebar
        from .models import FieldChoices
        context['field_choices'] = FieldChoices.choices
        
        # Track active filters
        context['active_fields'] = self.request.GET.getlist('field')
        context['active_formats'] = self.request.GET.getlist('format')
        context['active_languages'] = self.request.GET.getlist('language')
        
        # Check if any filters are active
        context['has_active_filters'] = bool(
            context['active_fields'] or 
            context['active_formats'] or 
            context['active_languages'] or 
            search_query
        )

        context['page'] = 'corpus'
        return context


class ResourceDetailView(LoginAndVerifiedRequiredMixin, DetailView):
    template_name = 'resources/resource_detail.html'
    context_object_name = 'object'

    TYPE_MODELS: Dict[str, Type[models.Model]] = {
        'tool': NLPTool,
        'course': Course,
        'article': Article,
        'thesis': Thesis,
        'memoir': Memoir,
        'corpus': Corpus,
    }

    MODEL_VIEW_NAMES: Dict[str, str] = {
        'nlptool': 'tool',
        'course': 'course',
        'article': 'article',
        'thesis': 'thesis',
        'memoir': 'memoir',
        'corpus': 'corpus',
    }

    URL_NAMES: Dict[str, str] = {
        'tool': 'tool_list',
        'course': 'course_list',
        'article': 'article_list',
        'thesis': 'thesis_list',
        'memoir': 'memoir_list',
        'corpus': 'corpus_list',
        'document': 'list',
    }

    def get_object(self):
        resource_type = self.kwargs.get('type')
        pk = self.kwargs.get('pk')

        model = self.TYPE_MODELS.get(resource_type)
        if not model:
            raise Http404("Type de ressource invalide")

        if resource_type in ['article', 'thesis', 'memoir']:
            try:
                obj = get_object_or_404(model, pk=pk)
            except Http404:
                document = get_object_or_404(Document, pk=pk)
                if resource_type == 'article' and hasattr(document, 'article'):
                    obj = document.article
                elif resource_type == 'thesis' and hasattr(document, 'thesis'):
                    obj = document.thesis
                elif resource_type == 'memoir' and hasattr(document, 'memoir'):
                    obj = document.memoir
                else:
                    raise Http404(f"No {resource_type.capitalize()} matches the given query.")
        else:
            obj = get_object_or_404(model, pk=pk)

        # Check approval status - only allow viewing if approved, staff, or author
        if hasattr(obj, 'approval_status'):
            is_staff = self.request.user.is_authenticated and self.request.user.is_staff
            is_author = self.request.user.is_authenticated and getattr(obj, 'author', None) == self.request.user
            if obj.approval_status != 'approved' and not is_staff and not is_author:
                raise Http404("This resource is pending approval.")

        return obj

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        resource_type = self.kwargs.get('type')
        
        if resource_type in ['article', 'thesis', 'memoir']:
            if hasattr(self.object, 'document') and self.object.document:
                self.object.document.increment_views()
            else:
                logger.warning(f"Object {self.object.pk} has no associated document")
        elif hasattr(self.object, 'increment_views'):
            self.object.increment_views()
        else:
            logger.warning(f"Object {self.object.pk} has no increment_views method")
        
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_template_names(self):
        return [
            f"resources/{self.kwargs['type']}_detail.html",
            self.template_name
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        model_name = str(self.object._meta.model_name)
        resource_type = self.MODEL_VIEW_NAMES.get(model_name, model_name) or model_name
        context['resource_type'] = resource_type
        context['list_url_name'] = self.URL_NAMES.get(resource_type, 'list')
        context['page'] = 'resources'

        document_obj = getattr(self.object, 'document', None)
        if document_obj is not None:
            context['specific_object'] = self.object
            context['object'] = document_obj

        if resource_type in ['article', 'thesis', 'memoir', 'course']:
            field = getattr(self.object, 'field', None)
            if field is None and document_obj is not None:
                field = getattr(document_obj, 'field', None)

            if field:
                context['related_corpora'] = Corpus.objects.filter(field__icontains=field)[:3]
            else:
                context['related_corpora'] = Corpus.objects.all()[:3]

        return context


class ResourceUpdateView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    form_class = ResourceForm
    template_name = 'resources/resource_update_form.html'
    
    # Updated TYPE_MODELS to treat article, thesis, memoir as top-level types
    TYPE_MODELS: Dict[str, Type[ResourceBase]] = {
        'tool': NLPTool,
        'nlp_tool': NLPTool,
        'course': Course,
        'corpus': Corpus,
        'article': Document,  # Changed: Article is accessed via Document
        'thesis': Document,   # Changed: Thesis is accessed via Document
        'memoir': Document,   # Changed: Memoir is accessed via Document
    }

    def get_object(self) -> ResourceBase:
        resource_type = self.kwargs['type']
        pk = self.kwargs['pk']
        
        # Get the Document for article, thesis, memoir
        if resource_type in ['article', 'thesis', 'memoir']:
            document = get_object_or_404(Document, pk=pk)
            # Verify the document has the correct subtype
            if not hasattr(document, resource_type):
                raise Http404(f"{resource_type.capitalize()} not found for document ID {pk}")
            return document
        else:
            model = self.TYPE_MODELS.get(resource_type)
            if not model:
                raise Http404("Invalid resource type")
            return get_object_or_404(model, pk=pk)

    def get_initial(self):
        resource = cast(ResourceBase, self.get_object())
        resource_type = self.kwargs['type']
        initial = {}
        
        # Common fields
        initial.update({
            'title': resource.title,
            'description': resource.description,
            'keywords': resource.keywords,
            'access_link': resource.access_link or '',
            'language': resource.language,
        })
        
        # Type-specific fields
        if resource_type == 'course' and isinstance(resource, Course):
            initial.update({
                'course_field': resource.field,
                'academic_level': resource.academic_level,
                'course_institution': resource.institution.id if resource.institution else None,
                'academic_year': resource.academic_year,
                'resource_type': 'course'
            })
        elif resource_type in ['nlp_tool', 'tool'] and isinstance(resource, NLPTool):
            initial.update({
                'tool_type': resource.tool_type,
                'tool_version': resource.version,
                'documentation': resource.documentation_link or '',
                'supported_languages': resource.get_supported_languages_list() if hasattr(resource, 'get_supported_languages_list') else [],
                'resource_type': 'nlp_tool'
            })
        elif resource_type == 'corpus' and isinstance(resource, Corpus):
            initial.update({
                'corpus_size': resource.size,
                'corpus_field': resource.field,
                'corpus_format': resource.file_format,
                'resource_type': 'corpus'
            })
        elif resource_type == 'article':
            article = getattr(resource, 'article', None)
            if article:
                initial.update({
                    'document_format': resource.file_format,
                    'journal': article.journal,
                    'publication_date': article.publication_date,
                    'doi': article.doi or '',
                    'resource_type': 'article'
                })
        elif resource_type == 'thesis':
            thesis = getattr(resource, 'thesis', None)
            if thesis:
                initial.update({
                    'document_format': resource.file_format,
                    'supervisor': thesis.supervisor,
                    'thesis_institution': thesis.institution.id if thesis.institution else None,
                    'defense_year': thesis.defense_year,
                    'resource_type': 'thesis'
                })
        elif resource_type == 'memoir':
            memoir = getattr(resource, 'memoir', None)
            if memoir:
                initial.update({
                    'document_format': resource.file_format,
                    'memoir_level': memoir.academic_level,
                    'memoir_institution': memoir.institution.id if memoir.institution else None,
                    'memoir_defense_year': memoir.defense_year,
                    'resource_type': 'memoir'
                })
        
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['is_update'] = True
        kwargs['instance'] = self.get_object()
        return kwargs

    def form_valid(self, form):
        resource = cast(ResourceBase, self.get_object())
        resource_type = self.kwargs['type']
        current_time = now()
        
        # Common data update
        common_data = {
            'title': form.cleaned_data['title'],
            'description': form.cleaned_data['description'],
            'keywords': form.cleaned_data['keywords'],
            'access_link': form.cleaned_data['access_link'],
            'language': form.cleaned_data['language'],
            'update_date': current_time
        }
        
        for attr, value in common_data.items():
            setattr(resource, attr, value)
        
        # Handle bilingual fields from POST data (not in form)
        title_ar = self.request.POST.get('title_ar', '').strip()
        title_en = self.request.POST.get('title_en', '').strip()
        description_ar = self.request.POST.get('description_ar', '').strip()
        description_en = self.request.POST.get('description_en', '').strip()
        
        if title_ar:
            resource.title_ar = title_ar
        if title_en:
            resource.title_en = title_en
        if description_ar:
            resource.description_ar = description_ar
        if description_en:
            resource.description_en = description_en
        
        # Type-specific updates
        if resource_type == 'course' and isinstance(resource, Course):
            resource.field = form.cleaned_data['course_field']
            resource.academic_level = form.cleaned_data['academic_level']
            resource.institution = form.cleaned_data['course_institution']
            resource.academic_year = form.cleaned_data['academic_year']
            resource.save()
        elif resource_type in ['nlp_tool', 'tool'] and isinstance(resource, NLPTool):
            resource.tool_type = form.cleaned_data['tool_type']
            resource.version = form.cleaned_data['tool_version']
            resource.documentation_link = form.cleaned_data['documentation']
            resource.supported_languages = form.cleaned_data['supported_languages']
            resource.save()
        elif resource_type == 'corpus' and isinstance(resource, Corpus):
            resource.size = form.cleaned_data['corpus_size']
            resource.field = form.cleaned_data['corpus_field']
            resource.file_format = form.cleaned_data['corpus_format']
            resource.save()
        elif resource_type == 'article' and isinstance(resource, Document):
            resource.file_format = form.cleaned_data['document_format']
            resource.save()
            article = getattr(resource, 'article', None)
            if article:
                article.doi = form.cleaned_data.get('doi', '')
                article.journal = form.cleaned_data['journal']
                article.publication_date = form.cleaned_data['publication_date']
                article.save()
        elif resource_type == 'thesis' and isinstance(resource, Document):
            resource.file_format = form.cleaned_data['document_format']
            resource.save()
            thesis = getattr(resource, 'thesis', None)
            if thesis:
                thesis.supervisor = form.cleaned_data['supervisor']
                thesis.institution = form.cleaned_data['thesis_institution']
                thesis.defense_year = form.cleaned_data['defense_year']
                thesis.save()
        elif resource_type == 'memoir' and isinstance(resource, Document):
            resource.file_format = form.cleaned_data['document_format']
            resource.save()
            memoir = getattr(resource, 'memoir', None)
            if memoir:
                memoir.academic_level = form.cleaned_data['memoir_level']
                memoir.institution = form.cleaned_data['memoir_institution']
                memoir.defense_year = form.cleaned_data['memoir_defense_year']
                memoir.save()
        
        # Handle "Approve & Publish" button
        if self.request.POST.get('approve_and_publish') and self.request.user.is_staff:
            # Validate bilingual fields before approving
            missing = []
            if not resource.title_ar:
                missing.append(_("Title (Arabic)"))
            if not resource.title_en:
                missing.append(_("Title (English)"))
            if not resource.description_ar:
                missing.append(_("Description (Arabic)"))
            if not resource.description_en:
                missing.append(_("Description (English)"))
            
            if missing:
                messages.error(self.request, _("Cannot approve: Missing %(fields)s") % {'fields': ", ".join(str(f) for f in missing)})
                return redirect(self.request.get_full_path())
            
            resource.approval_status = 'approved'
            resource.save()
            
            # Notify author
            from notifications.models import Notification
            author = resource.author
            if author:
                Notification.objects.create(
                    recipient=author,
                    title=_("Your submission has been approved"),
                    message=_("Your submission '%(title)s' has been approved and is now visible to the public.") % {'title': resource.title}
                )
            
            messages.success(self.request, _("'%(title)s' has been approved and published!") % {'title': resource.title})
            # Redirect to admin page instead of detail page
            return redirect(self.get_admin_redirect_url(resource_type))
        
        messages.success(self.request, _("Resource '%(title)s' updated successfully!") % {'title': resource.title})
        return super().form_valid(form)

    def get_admin_redirect_url(self, resource_type):
        """Get the admin page URL for the resource type."""
        admin_urls = {
            'course': 'pages:admin_courses',
            'tool': 'pages:admin_tools',
            'nlp_tool': 'pages:admin_tools',
            'corpus': 'pages:admin_corpora',
            'article': 'pages:admin_publications',
            'thesis': 'pages:admin_publications',
            'memoir': 'pages:admin_publications',
        }
        url_name = admin_urls.get(resource_type, 'pages:admin_dashboard')
        return f"{reverse(url_name)}?tab=pending"

    def get_success_url(self):
        resource_type = self.kwargs['type']
        pk = self.kwargs['pk']
        return reverse('resources:resource-detail', kwargs={'type': resource_type, 'pk': pk})

    def test_func(self):
        if self.request.user.is_staff or self.request.user.is_superuser:
            return True
        resource = self.get_object()
        return resource.author == self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page'] = 'resources'
        # Check if in admin review mode
        context['review_mode'] = self.request.GET.get('review') == '1'
        resource = self.get_object()
        context['is_pending'] = getattr(resource, 'approval_status', None) == 'pending'
        context['resource'] = resource
        return context


class ResourceDeleteView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, DeleteView):
    template_name = 'resources/resource_confirm_delete.html'
    success_url = reverse_lazy('resources:list')
    
    TYPE_MODELS = {
        'tool': NLPTool,
        'course': Course,
        'corpus': Corpus,
        'article': Document,
        'thesis': Document,
        'memoir': Document
    }
    
    def get_object(self):
        model = self.TYPE_MODELS.get(self.kwargs['type'])
        if not model:
            raise Http404("Invalid resource type")
        return get_object_or_404(model, pk=self.kwargs['pk'])
    
    def delete(self, request, *args, **kwargs):
        resource = self.get_object()
        resource_title = resource.title
        
        # For Document types, the related Article/Thesis/Memoir will be deleted automatically
        # due to OneToOneField cascade
        response = super().delete(request, *args, **kwargs)
        
        messages.success(self.request, f"Resource '{resource_title}' deleted successfully!")
        return response
    
    def test_func(self):
        resource = self.get_object()
        if self.request.user.is_staff or self.request.user.is_superuser:
            return True
        return resource.author == self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page'] = 'resources'
        return context


class ResourceCreateView(LoginAndVerifiedRequiredMixin, FormView):
    template_name = 'resources/resource_form.html'
    form_class = ResourceForm
    success_url = reverse_lazy('resources:list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        try:
            resource = form.save()
            # Show pending approval message instead of success
            messages.info(
                self.request, 
                _("Your submission '%(title)s' has been received and is pending admin review. It will be visible to the public once approved.") % {'title': resource.title}
            )
            # Don't notify all users - wait for approval
            return super().form_valid(form)
        except Exception as e:
            logger.error(f"Error creating resource: {str(e)}")
            messages.error(self.request, _("An error occurred while creating the resource. Please try again."))
            return self.form_invalid(form)
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page'] = 'resources'
        return context


class CourseCreateView(LoginAndVerifiedRequiredMixin, FormView):
    template_name = 'resources/course_create_form.html'
    form_class = ResourceForm
    success_url = reverse_lazy('resources:course_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_initial(self):
        initial = super().get_initial()
        initial['resource_type'] = 'course'
        return initial
    
    def form_valid(self, form):
        resource = form.save()
        messages.info(
            self.request, 
            _("Your course '%(title)s' has been submitted and is pending admin review.") % {'title': resource.title}
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page'] = 'resources'
        return context


class CorpusCreateView(LoginAndVerifiedRequiredMixin, FormView):
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


class ToolCreateView(LoginAndVerifiedRequiredMixin, FormView):
    template_name = 'resources/tool_create_form.html'
    form_class = ResourceForm
    success_url = reverse_lazy('resources:tool_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_initial(self):
        initial = super().get_initial()
        initial['resource_type'] = 'nlp_tool'
        return initial
    
    def form_valid(self, form):
        resource = form.save()
        messages.info(
            self.request, 
            _("Your tool '%(title)s' has been submitted and is pending admin review.") % {'title': resource.title}
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page'] = 'resources'
        return context
