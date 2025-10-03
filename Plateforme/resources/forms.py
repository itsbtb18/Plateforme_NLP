from django import forms
from django.utils.translation import gettext_lazy as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Submit, Row, Column, HTML
from .models import Course, NLPTool, Corpus, Document, Article, Thesis, Memoir, ResourceBase ,FieldChoices
from accounts.models import Institution

class ResourceForm(forms.Form):
    RESOURCE_TYPES = [
        ('course', _('Course')),
        ('nlp_tool', _('NLP Tool')),
        ('corpus', _('Corpus')),
        ('document', _('Document')),
    ]

    DOCUMENT_TYPES = [
        ('article', _('Article')),
        ('thesis', _('Thesis')),
        ('memoir', _('Memoir')),
    ]

    # ==================== COMMON FIELDS ====================
    resource_type = forms.ChoiceField(
        choices=RESOURCE_TYPES,
        label=_("Resource Type *"),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    title = forms.CharField(
        label=_("Title *"),
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    description = forms.CharField(
        label=_("Description *"),
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )

    keywords = forms.CharField(
        label=_("Keywords"),
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text=_("Comma-separated")
    )
    access_link = forms.URLField(
        label=_("Access Link"),
        required=False,
        widget=forms.URLInput(attrs={'class': 'form-control'})
    )
    language = forms.ChoiceField(
    choices=ResourceBase.LanguageChoices.choices,
    label=_("Language *"),
    initial=ResourceBase.LanguageChoices.ARABIC,
    widget=forms.Select(attrs={'class': 'form-select'})
    )

    # ==================== SPECIFIC FIELDS ====================
    # Course
    course_field = forms.ChoiceField(
    choices=FieldChoices.choices,
    label=_("Field of Study *"),
    required=False,
    widget=forms.Select(attrs={'class': 'form-select'})
)
    academic_level = forms.ChoiceField(
        choices=Course.Level.choices,
        label=_("Academic Level *"),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    course_institution = forms.ModelChoiceField(
        queryset=Institution.objects.all(),
        label=_("Institution *"),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    academic_year = forms.CharField(
        label=_("Academic Year * (YYYY-YYYY)"),
        max_length=9,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text=_("Format: 2023-2024")
    )

    # NLP Tool
    tool_type = forms.ChoiceField(
        choices=NLPTool.ToolType.choices,
        label=_("Tool Type *"),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    tool_version = forms.CharField(
        label=_("Version *"),
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    documentation = forms.URLField(
        label=_("Documentation"),
        required=False,
        widget=forms.URLInput(attrs={'class': 'form-control'})
    )
    supported_languages = forms.MultipleChoiceField(
        choices=[
            ('ar', _('Arabic')),
            ('en', _('English')),
            ('fr', _('French')),
            ('es', _('Spanish')),
            # Ajoutez d'autres langues selon vos besoins
        ],
        label=_("Supported Languages *"),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'list-unstyled'}),
        help_text=_("Select all languages that this tool can process")
    )

    # Corpus
    corpus_size = forms.IntegerField(
        label=_("Size * (words/documents)"),
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    corpus_field = forms.ChoiceField(
    choices=FieldChoices.choices,
    label=_("Field of Study *"),
    required=False,
    widget=forms.Select(attrs={'class': 'form-select'})
)
    corpus_format = forms.CharField(
        label=_("Format * (TXT/CSV/JSON)"),
        max_length=10,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    # Document
    document_type = forms.ChoiceField(
        choices=DOCUMENT_TYPES,
        label=_("Document Type *"),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    authors = forms.CharField(
        required=False,
        label=_("Authors"),
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    document_format = forms.CharField(
        label=_("Format * (PDF/DOCX)"),
        max_length=10,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    # Article
    doi = forms.CharField(
        label=_("DOI"),
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text=_("e.g., 10.1234/abcd")
    )
    journal = forms.CharField(
        label=_("Journal *"),
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    publication_date = forms.DateField(
        label=_("Publication Date *"),
        required=False,
        widget=forms.DateInput(
            attrs={'class': 'form-control', 'type': 'date'},
            format='%Y-%m-%d'
        )
    )

    # Thesis
    supervisor = forms.CharField(
        label=_("Supervisor *"),
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    thesis_institution = forms.ModelChoiceField(
        queryset=Institution.objects.all(),
        label=_("Institution *"),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    defense_year = forms.IntegerField(
        label=_("Defense Year *"),
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    # Memoir
    memoir_level = forms.ChoiceField(
        choices=Memoir._meta.get_field('academic_level').choices,
        label=_("Academic Level *"),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    memoir_institution = forms.ModelChoiceField(
        queryset=Institution.objects.all(),
        label=_("Institution *"),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    memoir_defense_year = forms.IntegerField(
        label=_("Defense Year *"),
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.is_update = kwargs.pop('is_update', False) 
        instance = kwargs.get('instance', None)
    
    # Si nous avons une instance et des langues supportées
        if instance and hasattr(instance, 'supported_languages'):
         if 'initial' not in kwargs:
            kwargs['initial'] = {}
         kwargs['initial']['supported_languages'] = self.prepare_supported_languages(instance.supported_languages)
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'needs-validation'
        self.helper.attrs = {'novalidate': ''}
        
        if self.is_update:
            self.fields['resource_type'].disabled = True
        
        resource_type = self.initial.get('resource_type', 'course')
        document_type = self.initial.get('document_type', 'article')
        if 'supported_languages' in self.fields:
         self.fields['supported_languages'].widget.attrs.update({
            'class': 'checkbox-grid'
        })

        # Build dynamic layout
        self.helper.layout = self._build_layout(resource_type, document_type)

    def _build_layout(self, resource_type, document_type):
        layout = Layout(
            Fieldset(
                _('Basic Information'),
                Row(
                    Column('resource_type', css_class='col-md-6'),
                    Column('language', css_class='col-md-6'),
                    ),
                
                'title',
                'description',
                Row(Column('keywords', css_class='col-md-12')),
                'access_link',
                HTML("""<hr class="my-4">"""),
            )
        )

        if resource_type == 'course':
            layout.append(self._create_course_fields())
        elif resource_type == 'nlp_tool':
            layout.append(self._create_tool_fields())
        elif resource_type == 'corpus':
            layout.append(self._create_corpus_fields())
        elif resource_type == 'document':
            layout.append(self._create_document_fields(document_type))

        layout.append(Submit('submit', _('Save'), css_class='btn-primary w-100 py-2 mt-3'))
        return layout

    def _create_course_fields(self):
        return Fieldset(
            _('Course Details'),
            Row(
                Column('course_field', css_class='col-md-6'),
                Column('academic_level', css_class='col-md-6')
            ),
            Row(
                Column('course_institution', css_class='col-md-6'),
                Column('academic_year', css_class='col-md-6')
            )
        )

    def _create_tool_fields(self):
        return Fieldset(
            _('Tool Details'),
            Row(
                Column('tool_type', css_class='col-md-6'),
                Column('tool_version', css_class='col-md-6')
            ),
            Row(
                Column('documentation', css_class='col-md-6'),
                 Fieldset(
                _('Supported Languages'),
                'supported_languages',
                css_class='border p-3 mt-3'
             )
            )
        )

    def _create_corpus_fields(self):
        return Fieldset(
            _('Corpus Details'),
            Row(
                Column('corpus_size', css_class='col-md-6')
            ),
            Row(
                Column('corpus_field', css_class='col-md-6'),
                Column('corpus_format', css_class='col-md-6')
            )
        )

    def _create_document_fields(self, doc_type):
        fields = [
            Fieldset(
                _('Document Type'),
                Row(
                    Column('document_type', css_class='col-md-6'),
                    Column('document_format', css_class='col-md-6')
                )
            )
        ]
        
        if doc_type == 'article':
            fields.append(self._create_article_fields())
        elif doc_type == 'thesis':
            fields.append(self._create_thesis_fields())
        elif doc_type == 'memoir':
            fields.append(self._create_memoir_fields())
            
        return fields

    def _create_article_fields(self):
        return Fieldset(
            _('Article Details'),
            Row(
                Column('journal', css_class='col-md-6'),
                Column('publication_date', css_class='col-md-6')
            ),
            'doi'
        )

    def _create_thesis_fields(self):
        return Fieldset(
            _('Thesis Details'),
            Row(
                Column('supervisor', css_class='col-md-6'),
                Column('thesis_institution', css_class='col-md-6')
            ),
            'defense_year'
        )

    def _create_memoir_fields(self):
        return Fieldset(
            _('Memoir Details'),
            Row(
                Column('memoir_level', css_class='col-md-6'),
                Column('memoir_institution', css_class='col-md-6')
            ),
            'memoir_defense_year'
        )
    
    def clean_supported_languages(self):
        languages = self.cleaned_data.get('supported_languages')
        if not languages and self.cleaned_data.get('resource_type') == 'nlp_tool':
            raise forms.ValidationError(_("Please select at least one supported language"))
        return ','.join(languages) if languages else ''

    def prepare_supported_languages(self, value):
        """Convertit une chaîne de langues en liste pour l'affichage initial"""
        if value:
            return value.split(',')
        return []

    #
    # ... (votre logique existante de validation et sauvegarde)
    def clean(self):
      cleaned_data = super().clean()
      resource_type = cleaned_data.get('resource_type')
    
    # Validation principale
      required_fields = []
      if resource_type == 'course':
        required_fields = ['course_field', 'academic_level', 'course_institution', 'academic_year']
      elif resource_type == 'nlp_tool':
        required_fields = ['tool_type', 'tool_version']
      elif resource_type == 'corpus':
        required_fields = ['corpus_size', 'corpus_field', 'corpus_format']
      elif resource_type == 'document':
        required_fields = ['document_type', 'document_format']
        for field in required_fields:
         if not cleaned_data.get(field):
          print(field, "This field is required for this document type")

    # Validation des champs obligatoires
      for field in required_fields:
        if not cleaned_data.get(field):
            self.add_error(field, _("This field is required for this resource type"))

    # Validation des sous-types de document
      if resource_type == 'document':
        doc_type = cleaned_data.get('document_type')
        required = []  # Initialisation par défaut
        
        if doc_type == 'article':
            required = ['journal', 'publication_date']
        elif doc_type == 'thesis':
            required = ['supervisor', 'thesis_institution', 'defense_year']
        elif doc_type == 'memoir':
            required = ['memoir_level', 'memoir_institution', 'memoir_defense_year']
        else:
            # Si le type de document n'est pas reconnu, on considère qu'aucun champ supplémentaire n'est requis
            required = []
            
        for field in required:
            if not cleaned_data.get(field):
                self.add_error(field, _("This field is required for this document type"))

    # Validation de l'année académique
      if resource_type == 'course' and cleaned_data.get('academic_year'):
        try:
            start, end = map(int, cleaned_data['academic_year'].split('-'))
            if end != start + 1:
                self.add_error('academic_year', _("End year must be start year + 1"))
        except (ValueError, AttributeError):
            self.add_error('academic_year', _("Invalid format (ex: 2023-2024)"))

      if resource_type == 'course':
        field_value = cleaned_data.get('course_field')
        if field_value and field_value not in dict(FieldChoices.choices):
            self.add_error('course_field', _("Invalid field choice"))

      elif resource_type == 'corpus':
        field_value = cleaned_data.get('corpus_field')
        if field_value and field_value not in dict(FieldChoices.choices):
            self.add_error('corpus_field', _("Invalid field choice"))

      language_value = cleaned_data.get('language')
      if not language_value:
        self.add_error('language', _("Language is required"))
      elif language_value not in dict(ResourceBase.LanguageChoices.choices):
        self.add_error('language', _("Invalid language choice"))

      return cleaned_data
    
    def save(self, instance=None):
        resource_type = self.cleaned_data['resource_type']
        common_data = {
            'title': self.cleaned_data['title'],
            'description': self.cleaned_data['description'],
            'author': self.user,
            'keywords': self.cleaned_data['keywords'],
            'access_link': self.cleaned_data['access_link'] or None,
            'language': self.cleaned_data['language'] ,
        }

        if self.is_update and instance:
            # Mise à jour de l'instance existante
            for field, value in common_data.items():
                setattr(instance, field, value)
            instance.save()
            
            if resource_type == 'course':
                instance.field = self.cleaned_data['course_field'] 
                instance.academic_level = self.cleaned_data['academic_level']
                instance.institution = self.cleaned_data['course_institution']
                instance.academic_year = self.cleaned_data['academic_year']
                instance.save()
            elif resource_type == 'nlp_tool':
                instance.tool_type = self.cleaned_data['tool_type']
                instance.version = self.cleaned_data['tool_version']
                instance.documentation_link = self.cleaned_data['documentation']
                instance.supported_languages = self.cleaned_data['supported_languages']
                instance.save()
            elif resource_type == 'corpus':
                instance.size = self.cleaned_data['corpus_size']
                instance.field = self.cleaned_data['corpus_field'] 
                instance.file_format = self.cleaned_data['corpus_format']
                instance.save()
            elif resource_type == 'document':
                instance.document_type = self.cleaned_data['document_type']
                instance.file_format = self.cleaned_data['document_format']
                instance.save()
                
                if hasattr(instance, 'article'):
                    article = instance.article
                    article.doi = self.cleaned_data['doi']
                    article.journal = self.cleaned_data['journal']
                    article.publication_date = self.cleaned_data['publication_date']
                    article.save()
                elif hasattr(instance, 'thesis'):
                    thesis = instance.thesis
                    thesis.supervisor = self.cleaned_data['supervisor']
                    thesis.institution = self.cleaned_data['thesis_institution']
                    thesis.defense_year = self.cleaned_data['defense_year']
                    thesis.save()
                elif hasattr(instance, 'memoir'):
                    memoir = instance.memoir
                    memoir.academic_level = self.cleaned_data['memoir_level']
                    memoir.institution = self.cleaned_data['memoir_institution']
                    memoir.defense_year = self.cleaned_data['memoir_defense_year']
                    memoir.save()
            
            return instance
        else:
            # Création d'une nouvelle instance
            if resource_type == 'course':
                return Course.objects.create(
                    **common_data,
                    field=self.cleaned_data['course_field'],
                    academic_level=self.cleaned_data['academic_level'],
                    teacher=self.user,
                    institution=self.cleaned_data['course_institution'],
                    academic_year=self.cleaned_data['academic_year']
                )
            elif resource_type == 'nlp_tool':
                return NLPTool.objects.create(
                    **common_data,
                    tool_type=self.cleaned_data['tool_type'],
                    version=self.cleaned_data['tool_version'],
                    documentation_link=self.cleaned_data['documentation'],
                    supported_languages=self.cleaned_data['supported_languages']
                )
            elif resource_type == 'corpus':
                return Corpus.objects.create(
                    **common_data,
                    size=self.cleaned_data['corpus_size'],
                    field=self.cleaned_data['corpus_field'],
                    file_format=self.cleaned_data['corpus_format']
                )
            elif resource_type == 'document':
                doc = Document.objects.create(
                    **common_data,
                    document_type=self.cleaned_data['document_type'],
                    file_format=self.cleaned_data['document_format']
                )
            if doc.document_type == 'article':
                 Article.objects.create(
                     document= doc,
                     doi = self.cleaned_data['doi'],
                     journal = self.cleaned_data['journal'],
                     publication_date = self.cleaned_data['publication_date']
                     )
                 
                 
            elif doc.document_type == 'thesis':
                 Thesis.objects.create(
                     document=doc,
                     supervisor=self.cleaned_data['supervisor'],
                     institution=self.cleaned_data['thesis_institution'],
                     defense_year=self.cleaned_data['defense_year']
            )
            elif doc.document_type == 'memoir':
                  Memoir.objects.create(
                document=doc,
                academic_level=self.cleaned_data['memoir_level'],
                institution=self.cleaned_data['memoir_institution'],
                defense_year=self.cleaned_data['memoir_defense_year']
            )
                
                
            return doc