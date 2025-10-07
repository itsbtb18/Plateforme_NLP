from django.http import Http404
from django.utils.timezone import now
from django.shortcuts import redirect, render, get_object_or_404
from django.views.generic import ListView, DetailView
from django.views.generic.edit import CreateView, FormView ,UpdateView ,DeleteView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse, reverse_lazy
from django.db.models import Q, F
from django.contrib import messages
from .forms import ResourceForm
from django.conf import settings
from accounts.views import LoginAndVerifiedRequiredMixin

# Import the correct model names from your models.py
from .models import Document, NLPTool, Article, Thesis, Memoir, Course, Corpus, ResourceBase        
from django.contrib.auth import get_user_model
from notifications.models import Notification

from django.db.models import Q
import logging

logger = logging.getLogger(__name__)

class ResourceListView(LoginAndVerifiedRequiredMixin, ListView):
    template_name = 'resources/list.html'
    context_object_name = 'resources'
    paginate_by = 9

    def get_queryset(self):
        search_query = self.request.GET.get('q', '')
        resource_type = self.request.GET.get('type', '')
        field_filter = self.request.GET.get('field', '')
        language_filter = self.request.GET.get('language', '') 
        
        querysets = []
        
        if resource_type in ['', 'article', 'thesis', 'memoir']:
            docs = Document.objects.all()
            if language_filter:
                 docs = docs.filter(language=language_filter)
            if resource_type in ['article', 'thesis', 'memoir']:
                docs = docs.filter(document_type=resource_type)
            if search_query:
                docs = docs.filter(
                    Q(title__icontains=search_query) | 
                    Q(description__icontains=search_query)
                )
            querysets.append(docs)
        
        if resource_type in ['', 'tool']:
            tools = NLPTool.objects.all()
            if language_filter:
                tools = tools.filter(supported_languages__contains=language_filter)
            if search_query:
                tools = tools.filter(
                    Q(title__icontains=search_query) | 
                    Q(description__icontains=search_query)
                )
            querysets.append(tools)
        
        if resource_type in ['', 'course']:
            courses = Course.objects.all()
            if language_filter:
                courses = courses.filter(language=language_filter)
            if field_filter:
                courses = courses.filter(field=field_filter)
            if search_query:
                courses = courses.filter(
                    Q(title__icontains=search_query) | 
                    Q(description__icontains=search_query)
                )
            querysets.append(courses)
        
        if resource_type in ['', 'corpus']:
            corpora = Corpus.objects.all()
            if language_filter:
                corpora = corpora.filter(language=language_filter)
            if field_filter:
                corpora = corpora.filter(field=field_filter)
            if search_query:
                corpora = corpora.filter(
                    Q(title__icontains=search_query) | 
                    Q(description__icontains=search_query)
                )
            querysets.append(corpora)

        combined = []
        for qs in querysets:
            for obj in qs:
                obj.resource_type = self.get_resource_type(obj)
                combined.append(obj)

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
        context['total_count'] = len(self.object_list)
        from .models import FieldChoices
        context['field_choices'] = FieldChoices.choices
        context['current_field'] = self.request.GET.get('field', '')
        context['current_language'] = self.request.GET.get('language', '')
        context['page'] = 'resources'
        return context

class ToolListView(LoginAndVerifiedRequiredMixin, ListView):
    model = NLPTool
    template_name = 'resources/tool_list.html'
    context_object_name = 'tools'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = NLPTool.objects.all()
        search_query = self.request.GET.get('q', '').strip()
        
        if search_query:
            # Recherche dans plusieurs champs
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(tool_type__icontains=search_query) |
                Q(keywords__icontains=search_query) |
                Q(author__first_name__icontains=search_query) |
                Q(author__last_name__icontains=search_query) |
                Q(supported_languages__icontains=search_query)
            ).distinct()
        
        return queryset.order_by('-creation_date')
     
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search_query = self.request.GET.get('q', '')
        
        if search_query:
            context['total_count'] = self.get_queryset().count()
            context['search_query'] = search_query
            context['is_search'] = True
        else:
            context['total_count'] = NLPTool.objects.count()
            context['is_search'] = False
        
        context['page'] = 'tools'
            
        return context

class CourseListView(ListView):
    model = Course
    template_name = 'resources/course_list.html'
    context_object_name = 'courses'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Course.objects.all()
        search_query = self.request.GET.get('q', '').strip()
        
        if search_query:
            # Recherche dans plusieurs champs
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
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
        
        if search_query:
            context['total_count'] = self.get_queryset().count()
            context['search_query'] = search_query
            context['is_search'] = True
        else:
            context['total_count'] = Course.objects.count()
            context['is_search'] = False
            
        return context

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_count'] = Course.objects.count()
        context['page'] = 'course'
        return context

class ArticleListView(LoginAndVerifiedRequiredMixin, ListView):
    model = Article
    template_name = 'resources/article_list.html'
    context_object_name = 'articles'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_count'] = Article.objects.count()
        return context

class ThesisListView(LoginAndVerifiedRequiredMixin, ListView):
    model = Thesis
    template_name = 'resources/thesis_list.html'
    context_object_name = 'theses'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_count'] = Thesis.objects.count()
        return context

class MemoirListView(LoginAndVerifiedRequiredMixin, ListView):
    model = Memoir
    template_name = 'resources/memoir_list.html'
    context_object_name = 'memoirs'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_count'] = Memoir.objects.count()
        return context
    
class CorpusListView(LoginAndVerifiedRequiredMixin, ListView):
    model = Corpus
    template_name = 'resources/corpus_list.html'
    context_object_name = 'corpora'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Corpus.objects.all()
        search_query = self.request.GET.get('q', '').strip()
        
        if search_query:
            # Recherche dans plusieurs champs
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(keywords__icontains=search_query) |
                Q(author__first_name__icontains=search_query) |
                Q(author__last_name__icontains=search_query) |
                Q(field__icontains=search_query) |
                Q(file_format__icontains=search_query)
            ).distinct()
        
        return queryset.order_by('-creation_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search_query = self.request.GET.get('q', '')
        
        if search_query:
            context['total_count'] = self.get_queryset().count()
            context['search_query'] = search_query
            context['is_search'] = True
        else:
            context['total_count'] = Corpus.objects.count()
            context['is_search'] = False

        context['page'] = 'corpus'
            
        return context

class ResourceDetailView(LoginAndVerifiedRequiredMixin, DetailView):
    template_name = 'resources/resource_detail.html'
    context_object_name = 'object'

    TYPE_MODELS = {
        'tool': NLPTool,
        'course': Course,
        'article': Article,
        'thesis': Thesis,
        'memoir': Memoir,
        'corpus': Corpus,
    }

    MODEL_VIEW_NAMES = {
        'nlptool': 'tool',
        'course': 'course',
        'article': 'article',
        'thesis': 'thesis',
        'memoir': 'memoir',
        'corpus': 'corpus',
    }

    URL_NAMES = {
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

        # Gérer les sous-types de Document
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

        return obj

    def get(self, request, *args, **kwargs):
        """Override get method to handle view increment after object is retrieved"""
        self.object = self.get_object()
        
        # Incrémentation du compteur de vues avec gestion spéciale pour les documents
        resource_type = self.kwargs.get('type')
        
        if resource_type in ['article', 'thesis', 'memoir']:
            # Pour les sous-types de Document, incrémenter les vues du document parent
            if hasattr(self.object, 'document') and self.object.document:
                self.object.document.increment_views()
            else:
                logger.warning(f"Object {self.object.pk} has no associated document")
        elif hasattr(self.object, 'increment_views'):
            # Pour les autres types (Course, NLPTool, Corpus)
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
        model_name = self.object._meta.model_name
        resource_type = self.MODEL_VIEW_NAMES.get(model_name, model_name)
        context['resource_type'] = resource_type
        context['list_url_name'] = self.URL_NAMES.get(resource_type, 'list')
        context['page'] = 'resources'

        if hasattr(self.object, 'document'):
            context['specific_object'] = self.object  # Article, Thesis, Memoir...
            context['object'] = self.object.document  # Document parent

        # Section "Related Corpora"
        if resource_type in ['article', 'thesis', 'memoir', 'course']:
            if hasattr(self.object, 'field'):
                field = self.object.field
            elif hasattr(self.object, 'document') and hasattr(self.object.document, 'field'):
                field = self.object.document.field
            else:
                field = None

            if field:
                context['related_corpora'] = Corpus.objects.filter(field__icontains=field)[:3]
            else:
                context['related_corpora'] = Corpus.objects.all()[:3]

    

        return context

class ResourceUpdateView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    form_class = ResourceForm
    template_name = 'resources/resource_update_form.html'
    
    TYPE_MODELS = {
        'tool': NLPTool,
        'nlp_tool': NLPTool,  # Ajout pour la cohérence des types
        'course': Course,
        'document': Document,
        'corpus': Corpus,
        'article': Article,
        'thesis': Thesis,
        'memoir': Memoir,
    }

    def get_object(self):
        resource_type = self.kwargs['type']
        pk = self.kwargs['pk']
        
        # Pour les sous-types de Document
        if resource_type in ['article', 'thesis', 'memoir']:
            try:
                # Essayer d'abord de récupérer directement le sous-type
                model = self.TYPE_MODELS.get(resource_type)
                return get_object_or_404(model, pk=pk)
            except Http404:
                # Si ça échoue, essayer via le Document parent
                document = get_object_or_404(Document, pk=pk)
                if hasattr(document, resource_type):
                    return getattr(document, resource_type)
                raise Http404(f"{resource_type.capitalize()} not found for document ID {pk}")
        else:
            model = self.TYPE_MODELS.get(resource_type)
            if not model:
                raise Http404("Invalid resource type")
            return get_object_or_404(model, pk=pk)

    def get_initial(self):
      resource = self.get_object()
      initial = {}
    
    # Pour les sous-types de Document (Article, Thesis, Memoir)
      if hasattr(resource, 'document'):
        # Récupérer les champs du Document parent
        document = resource.document
        initial.update({
            'title': document.title,
            'description': document.description,
            'keywords': document.keywords,
            'access_link': document.access_link or '',
            'document_type': document.document_type,
            'document_format': document.file_format,
        })
        
        # Ajouter les champs spécifiques au sous-type
        if isinstance(resource, Article):
            initial.update({
                'doi': resource.doi,
                'journal': resource.journal,
                'publication_date': resource.publication_date,
            })
        elif isinstance(resource, Thesis):
            initial.update({
                'supervisor': resource.supervisor,
                'thesis_institution': resource.institution.id if resource.institution else None,
                'defense_year': resource.defense_year,
            })
        elif isinstance(resource, Memoir):
            initial.update({
                'memoir_level': resource.academic_level,
                'memoir_institution': resource.institution.id if resource.institution else None,
                'memoir_defense_year': resource.defense_year,
            })
        
        initial['resource_type'] = 'document'
      else:
        # Pour les autres types de ressources (Course, NLPTool, Corpus, Document de base)
        initial.update({
            'title': resource.title,
            'description': resource.description,
            'keywords': resource.keywords,
            'access_link': resource.access_link or '',
            'language': resource.language,
        })
        
        """if isinstance(resource, Document):
            initial.update({
                'document_type': resource.document_type,
                'document_format': resource.file_format,
            })
            initial['resource_type'] = 'document'"""
        if isinstance(resource, Course):
            initial.update({
                'course_field': resource.field,
                'academic_level': resource.academic_level,
                'course_institution': resource.institution.id if resource.institution else None,
                'academic_year': resource.academic_year,
            })
            initial['resource_type'] = 'course'
        elif isinstance(resource, NLPTool):
            initial.update({
                'tool_type': resource.tool_type,
                'tool_version': resource.version,
                'documentation': resource.documentation_link or '',
                'supported_languages': resource.supported_languages,  # Changed from 'languages'
            })
            initial['resource_type'] = 'nlp_tool'
        elif isinstance(resource, Corpus):
            initial.update({
                'corpus_size': resource.size,
                'corpus_field': resource.field,
                'corpus_format': resource.file_format,
            })
            initial['resource_type'] = 'corpus'

        

      return initial
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page'] = 'resources'  
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['is_update'] = True  # Important pour désactiver les champs de type
        return kwargs

    def _get_resource_type(self, resource):
        """Retourne le type de base"""
        if isinstance(resource, Article) or hasattr(resource, 'article'):
            return 'document'
        elif isinstance(resource, Thesis) or hasattr(resource, 'thesis'):
            return 'document'
        elif isinstance(resource, Memoir) or hasattr(resource, 'memoir'):
            return 'document'
        elif isinstance(resource, NLPTool):
            return 'nlp_tool'
        elif isinstance(resource, Course):
            return 'course'
        elif isinstance(resource, Corpus):
            return 'corpus'
        elif isinstance(resource, Document):
            return 'document'
        return resource._meta.model_name

    def form_valid(self, form):
        resource = self.get_object()
        resource_type = self._get_resource_type(resource)

        current_time = now()
        # Mise à jour des champs communs
        common_data = {
            'title': form.cleaned_data['title'],
            'description': form.cleaned_data['description'],
            'keywords': form.cleaned_data['keywords'],
            'access_link': form.cleaned_data['access_link'],
            'language': form.cleaned_data['language'],
            'update_date': current_time
        }

        # Pour les sous-types de Document
        document = None
        if hasattr(resource, 'document'):
              # Si c'est un sous-type de Document
              document = resource.document
              for attr, value in common_data.items():
                setattr(document, attr, value)
              document.file_format = form.cleaned_data['document_format']
              document.update_date = current_time
              document.save()

        elif resource_type == 'document':
            # Si c'est un Document de base
                for attr, value in common_data.items():
                    setattr(document, attr, value)
                resource.file_format = form.cleaned_data['document_format']
                resource.update_date = current_time 
                resource.save()
                document = resource
        else:
            # Pour les autres types de ressources
            for attr, value in common_data.items():
                setattr(resource, attr, value)
            resource.update_date = current_time
            resource.save()

        # Mise à jour des champs spécifiques
        if resource_type == 'course':
            resource.field = form.cleaned_data['course_field']
            resource.academic_level = form.cleaned_data['academic_level']
            resource.institution = form.cleaned_data['course_institution']
            resource.academic_year = form.cleaned_data['academic_year']
            resource.save()
        elif resource_type == 'nlp_tool':
            resource.tool_type = form.cleaned_data['tool_type']
            resource.version = form.cleaned_data['tool_version']
            resource.documentation_link = form.cleaned_data['documentation']
            resource.supported_languages = form.cleaned_data['supported_languages']
            resource.save()
        elif resource_type == 'corpus':
            resource.size = form.cleaned_data['corpus_size']
            resource.field = form.cleaned_data['corpus_field']
            resource.file_format = form.cleaned_data['corpus_format']
            resource.save()
        
        # Traitement des sous-types de Document
        if document:
            doc_type = document.document_type
            if doc_type == 'article':
             if hasattr(document, 'article'):
                    article = document.article
             else:
                article, _ = Article.objects.get_or_create(document=document)
                article.doi = form.cleaned_data['doi']
                article.journal = form.cleaned_data['journal']
                article.publication_date = form.cleaned_data['publication_date']
                article.save()
            elif doc_type == 'thesis':
                if hasattr(document, 'thesis'):
                    thesis = document.thesis
                else:
                    thesis = Thesis(document=document)
                thesis.supervisor = form.cleaned_data['supervisor']
                thesis.institution = form.cleaned_data['thesis_institution']
                thesis.defense_year = form.cleaned_data['defense_year']
                thesis.save()
            elif doc_type == 'memoir':
                if hasattr(document, 'memoir'):
                    memoir = document.memoir
                else:
                    memoir = Memoir(document=document)
                memoir.academic_level = form.cleaned_data['memoir_level']
                memoir.institution = form.cleaned_data['memoir_institution']
                memoir.defense_year = form.cleaned_data['memoir_defense_year']
                memoir.save()

        if hasattr(resource, 'document'):
         messages.success(self.request, f"Ressource '{resource.document.title}' updated successfully !")
        else:
         messages.success(self.request, f"Resource '{resource.title}' updated successfully !")
        return super().form_valid(form)

    def get_success_url(self):
        resource = self.get_object()
        resource_type = self.kwargs['type']
        pk = self.kwargs['pk']
        
        # Redirection vers la vue détaillée appropriée
        return reverse('resources:resource-detail', kwargs={
            'type': resource_type,
            'pk': pk
        })

    def test_func(self):
         
        if self.request.user.is_staff or self.request.user.is_superuser:
            return True

        resource = self.get_object()
       
        if hasattr(resource, 'document'):
            return resource.document.author == self.request.user
        return resource.author == self.request.user 
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page'] = 'resources'  
        return context


class ResourceDeleteView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, DeleteView):
    template_name = 'resources/resource_confirm_delete.html'
    success_url = reverse_lazy('resources:list')
    
    TYPE_MODELS = {
        'tool': NLPTool,
        'course': Course,
        'document': Document,
        'corpus': Corpus,
        'article': Document,
        'memoir': Document,
        'thesis': Document
    }
    
    def get_object(self):
        model = self.TYPE_MODELS.get(self.kwargs['type'])
        if not model:
            raise Http404("Invalid resource type")
        return get_object_or_404(model, pk=self.kwargs['pk'])
    
    def delete(self, request, *args, **kwargs):
        resource = self.get_object()
        resource_title = resource.title
        
        if isinstance(resource, Document):
            if hasattr(resource, 'article'):
                resource.article.delete()
            elif hasattr(resource, 'thesis'):
                resource.thesis.delete()
            elif hasattr(resource, 'memoir'):
                resource.memoir.delete()
                
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
            messages.success(self.request, f"Resource '{resource.title}' created successfully!")
            User = get_user_model()
            for user in User.objects.filter(is_active=True):
                Notification.objects.create(
                    recipient=user,
                    title="New resource",
                    message=f"The resource« {resource.title} » has been added to the platform."
                )
            return super().form_valid(form)
        except Exception as e:
            logger.error(f"Error creating resource: {str(e)}")
            messages.error(self.request, f"An error occurred while creating the resource: {str(e)}")
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
        messages.success(self.request, f"Cours '{resource.title}' created successfully!")
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
        messages.success(self.request, f"Corpus '{resource.title}' created successfully!")
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
        messages.success(self.request, f"Tool '{resource.title}' created successfully!")
        return super().form_valid(form)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page'] = 'resources'  
        return context