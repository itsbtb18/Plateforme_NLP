"""
Elasticsearch Document definitions for all searchable models.

This module defines the mappings between Django models and Elasticsearch indices.
Each Document class specifies:
- Field mappings with multi-language analyzers (Arabic, English, Phonetic)
- Custom prepare methods for computed fields
- Index settings with analyzer configurations

Supports dis_max ranking and faceted aggregations.
"""
from django_elasticsearch_dsl import fields
from django_elasticsearch_dsl.documents import Document
from elasticsearch_dsl import analyzer
from elasticsearch_dsl.analysis import token_filter
from django_elasticsearch_dsl.registries import registry

from resources.models import Course, Document as DocModel, NLPTool, Corpus
from institutions.models import Institution
from projects.models import Project
from events.models import Event
from accounts.models import CustomUser


# =============================================================================
# ANALYZER DEFINITIONS
# =============================================================================

phonetic_filter = token_filter(
    'phonetic_filter',
    type='phonetic',
    encoder='double_metaphone'
)

arabic_stop = token_filter(
    'arabic_stop',
    type='stop',
    stopwords='_arabic_'
)

arabic_stemmer = token_filter(
    'arabic_stemmer',
    type='stemmer',
    language='arabic'
)

english_stemmer = token_filter(
    'english_stemmer',
    type='stemmer',
    language='english'
)

arabic_analyzer = analyzer(
    'arabic_analyzer',
    tokenizer='icu_tokenizer',
    filter=['lowercase', 'arabic_normalization', arabic_stop, arabic_stemmer]
)

english_analyzer = analyzer(
    'english_analyzer',
    tokenizer='standard',
    filter=['lowercase', 'stop', english_stemmer]
)

phonetic_analyzer = analyzer(
    'phonetic_analyzer',
    tokenizer='standard',
    filter=['lowercase', 'asciifolding', phonetic_filter]
)


# =============================================================================
# SHARED INDEX SETTINGS
# =============================================================================

def get_index_settings():
    """Return standard index settings with all analyzers configured."""
    return {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "filter": {
                "arabic_stop": {"type": "stop", "stopwords": "_arabic_"},
                "arabic_stemmer": {"type": "stemmer", "language": "arabic"},
                "english_stemmer": {"type": "stemmer", "language": "english"},
                "phonetic_filter": {"type": "phonetic", "encoder": "beider_morse", "rule_type": "approx"}
            },
            "analyzer": {
                "arabic_analyzer": {
                    "type": "custom",
                    "tokenizer": "icu_tokenizer",
                    "filter": ["lowercase", "arabic_normalization", "arabic_stop", "arabic_stemmer"]
                },
                "english_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "english_stemmer"]
                },
                "phonetic_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "phonetic_filter"]
                }
            }
        }
    }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def prepare_author_field(instance):
    """Prepare author ObjectField from a model instance with an author FK."""
    if instance.author:
        return {
            'id': str(instance.author.id),
            'email': instance.author.email,
            'full_name': instance.author.get_full_name_display or instance.author.email
        }
    return {'id': '', 'email': '', 'full_name': 'Anonymous'}


def prepare_keywords_field(keywords):
    """Parse keywords string/list into a list of strings."""
    if not keywords:
        return []
    if isinstance(keywords, str):
        keywords = keywords.replace('،', ',')
        return [kw.strip() for kw in keywords.split(',') if kw.strip()]
    elif isinstance(keywords, (list, tuple)):
        return list(keywords)
    return []


# =============================================================================
# USER DOCUMENT
# =============================================================================

@registry.register_document
class UserDocument(Document):
    """
    Elasticsearch document for CustomUser model.
    
    Model fields: id, email, bio, avatar, is_email_verified, is_superuser, is_staff
    Computed: full_name (from full_name_en/full_name_ar)
    """
    # Manual field - computed from full_name_en/full_name_ar
    full_name = fields.TextField(
        analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
        }
    )
    
    bio = fields.TextField(
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )

    def prepare_full_name(self, instance):
        """Combine full_name fields with fallback."""
        return instance.get_full_name_display or instance.email
    
    def prepare_bio(self, instance):
        """Return bio with fallback."""
        return instance.bio or instance.bio_en or instance.bio_ar or ''

    class Index:
        name = 'users'
        settings = get_index_settings()

    class Django:
        model = CustomUser
        # Only list fields that exist on the model and are NOT manually defined above
        fields = [
            'id',
            'email',
            'avatar',
            'is_email_verified',
            'is_superuser',
            'is_staff'
        ]


# =============================================================================
# COURSE DOCUMENT
# =============================================================================

@registry.register_document
class CourseDocument(Document):
    """
    Elasticsearch document for Course model.
    
    Model fields: id, creation_date, academic_year
    Computed: author, institution_name, institution_acronym, title, description,
              keywords, field, field_display, language, language_display,
              academic_level, academic_level_display
    """
    author = fields.ObjectField(
        properties={
            'id': fields.KeywordField(),
            'email': fields.KeywordField(),
            'full_name': fields.TextField(),
        }
    )

    institution_name = fields.TextField(
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )

    institution_acronym = fields.TextField(
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer)
        }
    )

    title = fields.TextField(
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
        }
    )

    description = fields.TextField(
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
        }
    )

    keywords = fields.KeywordField(
        multi=True,
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
        }
    )

    field = fields.TextField(
        analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )

    field_display = fields.TextField(
        analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )

    language = fields.TextField(
        analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )

    language_display = fields.TextField(
        analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )

    academic_level = fields.TextField(
        analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )

    academic_level_display = fields.TextField(
        analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )

    def prepare_author(self, instance):
        return prepare_author_field(instance)

    def prepare_keywords(self, instance):
        return prepare_keywords_field(instance.keywords)

    def prepare_title(self, instance):
        return instance.title or ''

    def prepare_description(self, instance):
        return instance.description or ''

    def prepare_field(self, instance):
        return str(instance.field) if instance.field else ""

    def prepare_field_display(self, instance):
        if hasattr(instance, 'get_field_display'):
            return str(instance.get_field_display()) or ""
        return ""

    def prepare_language(self, instance):
        return str(instance.language) if instance.language else ""

    def prepare_language_display(self, instance):
        if hasattr(instance, 'get_language_display'):
            return str(instance.get_language_display()) or ""
        return ""

    def prepare_academic_level(self, instance):
        return str(instance.academic_level) if instance.academic_level else ""

    def prepare_academic_level_display(self, instance):
        if hasattr(instance, 'get_academic_level_display'):
            return str(instance.get_academic_level_display()) or ""
        return ""

    def prepare_institution_name(self, instance):
        if instance.institution:
            return str(instance.institution.name)
        return ""

    def prepare_institution_acronym(self, instance):
        if instance.institution:
            return str(instance.institution.acronym or '')
        return ""

    class Index:
        name = 'courses'
        settings = get_index_settings()

    class Django:
        model = Course
        # Course inherits from ResourceBase which has creation_date
        fields = ['id', 'creation_date', 'academic_year']


# =============================================================================
# TOOL DOCUMENT
# =============================================================================

@registry.register_document
class ToolDocument(Document):
    """
    Elasticsearch document for NLPTool model.
    
    Model fields: id, version, creation_date, last_updated
    Computed: author, title, description, keywords, tool_type, tool_type_display,
              language, language_display, supported_languages
    """
    author = fields.ObjectField(
        properties={
            'id': fields.KeywordField(),
            'email': fields.KeywordField(),
            'full_name': fields.TextField(),
        }
    )

    title = fields.TextField(
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
        }
    )

    description = fields.TextField(
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
        }
    )

    keywords = fields.KeywordField(
        multi=True,
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
        }
    )

    tool_type = fields.TextField(
        analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )

    tool_type_display = fields.TextField(
        analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )

    language = fields.TextField(
        analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )

    language_display = fields.TextField(
        analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )

    supported_languages = fields.KeywordField(multi=True)

    def prepare_author(self, instance):
        return prepare_author_field(instance)

    def prepare_keywords(self, instance):
        return prepare_keywords_field(instance.keywords)

    def prepare_title(self, instance):
        return instance.title or ''

    def prepare_description(self, instance):
        return instance.description or ''

    def prepare_tool_type(self, instance):
        return str(instance.tool_type) if instance.tool_type else ""

    def prepare_tool_type_display(self, instance):
        if hasattr(instance, 'get_tool_type_display'):
            return str(instance.get_tool_type_display()) or ""
        return ""

    def prepare_language(self, instance):
        return str(instance.language) if instance.language else ""

    def prepare_language_display(self, instance):
        if hasattr(instance, 'get_language_display'):
            return str(instance.get_language_display()) or ""
        return ""

    def prepare_supported_languages(self, instance):
        if instance.supported_languages:
            return instance.get_supported_languages_list()
        return []

    class Index:
        name = 'nlp_tools'
        settings = get_index_settings()

    class Django:
        model = NLPTool
        # NLPTool inherits from ResourceBase which has creation_date
        fields = ['id', 'version', 'creation_date', 'last_updated']


# =============================================================================
# CORPUS DOCUMENT
# =============================================================================

@registry.register_document
class CorpusDocument(Document):
    """
    Elasticsearch document for Corpus model.
    
    Model fields: id, creation_date, size, file_format
    Computed: author, title, description, keywords, field, field_display,
              language, language_display
    """
    author = fields.ObjectField(
        properties={
            'id': fields.KeywordField(),
            'email': fields.KeywordField(),
            'full_name': fields.TextField(),
        }
    )

    title = fields.TextField(
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
        }
    )

    description = fields.TextField(
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
        }
    )

    keywords = fields.KeywordField(
        multi=True,
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
        }
    )

    field = fields.TextField(
        analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )

    field_display = fields.TextField(
        analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )

    language = fields.TextField(
        analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )

    language_display = fields.TextField(
        analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )

    def prepare_author(self, instance):
        return prepare_author_field(instance)

    def prepare_keywords(self, instance):
        return prepare_keywords_field(instance.keywords)

    def prepare_title(self, instance):
        return instance.title or ''

    def prepare_description(self, instance):
        return instance.description or ''

    def prepare_field(self, instance):
        return str(instance.field) if instance.field else ""

    def prepare_field_display(self, instance):
        if hasattr(instance, 'get_field_display'):
            return str(instance.get_field_display()) or ""
        return ""

    def prepare_language(self, instance):
        return str(instance.language) if instance.language else ""

    def prepare_language_display(self, instance):
        if hasattr(instance, 'get_language_display'):
            return str(instance.get_language_display()) or ""
        return ""

    class Index:
        name = 'corpora'
        settings = get_index_settings()

    class Django:
        model = Corpus
        # Corpus inherits from ResourceBase which has creation_date
        fields = ['id', 'creation_date', 'file_format']


# =============================================================================
# RESOURCE/DOCUMENT DOCUMENT
# =============================================================================

@registry.register_document
class ResourceDocument(Document):
    """
    Elasticsearch document for Document model (theses, articles, memoirs).
    
    Model fields: id, file_format, creation_date
    Computed: document_type, document_type_display, author, title, description,
              keywords, subtype_fields
    """
    document_type = fields.TextField(
        analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )

    document_type_display = fields.TextField(
        analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )

    author = fields.ObjectField(
        properties={
            'id': fields.KeywordField(),
            'email': fields.KeywordField(),
            'full_name': fields.TextField(),
        }
    )

    title = fields.TextField(
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
        }
    )

    description = fields.TextField(
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
        }
    )

    keywords = fields.KeywordField(
        multi=True,
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
        }
    )

    subtype_fields = fields.ObjectField(
        properties={
            'supervisor': fields.TextField(
                fields={
                    'raw': fields.KeywordField(),
                    'english': fields.TextField(analyzer=english_analyzer),
                    'arabic': fields.TextField(analyzer=arabic_analyzer)
                }
            ),
            'journal': fields.TextField(
                fields={
                    'raw': fields.KeywordField(),
                    'english': fields.TextField(analyzer=english_analyzer)
                }
            ),
            'academic_level': fields.TextField(
                fields={
                    'raw': fields.KeywordField(),
                    'english': fields.TextField(analyzer=english_analyzer),
                    'arabic': fields.TextField(analyzer=arabic_analyzer)
                }
            ),
            'doi': fields.TextField(),
            'defense_year': fields.IntegerField(),
            'institution': fields.TextField(
                fields={
                    'raw': fields.KeywordField(),
                    'english': fields.TextField(analyzer=english_analyzer)
                }
            )
        }
    )

    def prepare_author(self, instance):
        return prepare_author_field(instance)

    def prepare_keywords(self, instance):
        return prepare_keywords_field(instance.keywords)

    def prepare_title(self, instance):
        return instance.title or ''

    def prepare_description(self, instance):
        return instance.description or ''

    def prepare_document_type(self, instance):
        return str(instance.document_type) if instance.document_type else ""

    def prepare_document_type_display(self, instance):
        if hasattr(instance, 'get_document_type_display'):
            return str(instance.get_document_type_display()) or ""
        return ""

    def prepare_subtype_fields(self, instance):
        data = {}
        if hasattr(instance, 'thesis') and instance.thesis:
            data.update({
                'supervisor': str(instance.thesis.supervisor) if instance.thesis.supervisor else "",
                'institution': str(instance.thesis.institution.name) if instance.thesis.institution else "",
                'defense_year': instance.thesis.defense_year
            })
        elif hasattr(instance, 'article') and instance.article:
            data.update({
                'journal': str(instance.article.journal) if instance.article.journal else "",
                'doi': str(instance.article.doi) if instance.article.doi else ""
            })
        elif hasattr(instance, 'memoir') and instance.memoir:
            data.update({
                'academic_level': str(instance.memoir.get_academic_level_display()) if hasattr(instance.memoir, 'get_academic_level_display') else "",
                'institution': str(instance.memoir.institution.name) if instance.memoir.institution else "",
                'defense_year': instance.memoir.defense_year
            })
        return data

    class Index:
        name = 'resources'
        settings = get_index_settings()

    class Django:
        model = DocModel
        # Document inherits from ResourceBase which has creation_date
        fields = ['id', 'file_format', 'creation_date']


# =============================================================================
# PROJECT DOCUMENT
# =============================================================================

@registry.register_document
class ProjectDocument(Document):
    """
    Elasticsearch document for Project model.
    
    Model fields: id (only - dates are manually defined)
    Computed: coordinator, institution, members, title, description, status,
              date_start, date_end, created_at
    """
    coordinator = fields.ObjectField(
        properties={
            'id': fields.IntegerField(),
            'full_name': fields.TextField()
        }
    )

    institution = fields.ObjectField(
        properties={
            'id': fields.IntegerField(),
            'name': fields.TextField(
                fields={
                    'raw': fields.KeywordField(),
                    'english': fields.TextField(analyzer=english_analyzer),
                    'arabic': fields.TextField(analyzer=arabic_analyzer)
                }
            )
        }
    )

    members = fields.NestedField(
        properties={
            'id': fields.IntegerField(),
            'full_name': fields.TextField()
        }
    )

    title = fields.TextField(
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
        }
    )

    description = fields.TextField(
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
        }
    )

    status = fields.TextField(
        analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )

    # Manually defined date fields (exist on model)
    date_start = fields.DateField()
    date_end = fields.DateField()
    created_at = fields.DateField()

    def prepare_coordinator(self, instance):
        if instance.coordinator:
            return {
                'id': instance.coordinator.id,
                'full_name': instance.coordinator.get_full_name_display or ''
            }
        return {'id': None, 'full_name': ''}

    def prepare_institution(self, instance):
        if instance.institution:
            return {
                'id': instance.institution.id,
                'name': instance.institution.name or ''
            }
        return {'id': None, 'name': ''}

    def prepare_members(self, instance):
        members = []
        for pm in instance.members.filter(status='accepted'):
            members.append({
                'id': pm.member.id,
                'full_name': pm.member.get_full_name_display or ''
            })
        return members

    def prepare_title(self, instance):
        return instance.title or ''

    def prepare_description(self, instance):
        return instance.description or ''

    def prepare_status(self, instance):
        return str(instance.status) if instance.status else ""

    class Index:
        name = 'projects'
        settings = get_index_settings()

    class Django:
        model = Project
        # Date fields are manually defined above, don't list them here
        fields = ['id']


# =============================================================================
# EVENT DOCUMENT
# =============================================================================

@registry.register_document
class EventDocument(Document):
    """
    Elasticsearch document for Event model.
    
    Model fields: id, start_date, end_date
    Note: Event model has 'created_at', NOT 'creation_date'
    Computed: organizer, created_by, domains, title, description, event_type, location
    """
    organizer = fields.ObjectField(
        properties={
            'id': fields.IntegerField(),
            'name': fields.TextField(
                fields={
                    'raw': fields.KeywordField(),
                    'english': fields.TextField(analyzer=english_analyzer),
                    'arabic': fields.TextField(analyzer=arabic_analyzer)
                }
            )
        }
    )

    created_by = fields.ObjectField(
        properties={
            'id': fields.IntegerField(),
            'full_name': fields.TextField()
        }
    )

    domains = fields.KeywordField(
        multi=True,
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )

    title = fields.TextField(
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
        }
    )

    description = fields.TextField(
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
        }
    )

    event_type = fields.TextField(
        analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )

    location = fields.TextField(
        analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )

    # Manually define created_at since it's used for sorting
    created_at = fields.DateField()

    def prepare_organizer(self, instance):
        if instance.organizer:
            return {
                'id': instance.organizer.id,
                'name': instance.organizer.name or ''
            }
        return {'id': None, 'name': ''}

    def prepare_created_by(self, instance):
        if instance.created_by:
            return {
                'id': instance.created_by.id,
                'full_name': instance.created_by.get_full_name_display or ''
            }
        return {'id': None, 'full_name': ''}

    def prepare_domains(self, instance):
        if not instance.domains:
            return []
        if isinstance(instance.domains, str):
            return [d.strip() for d in instance.domains.split(',') if d.strip()]
        return list(instance.domains) if isinstance(instance.domains, (list, tuple)) else []

    def prepare_title(self, instance):
        return instance.title or ''

    def prepare_description(self, instance):
        return instance.description or ''

    def prepare_event_type(self, instance):
        return str(instance.event_type) if instance.event_type else ""

    def prepare_location(self, instance):
        return instance.location or ''

    class Index:
        name = 'events'
        settings = get_index_settings()

    class Django:
        model = Event
        # FIXED: Event model has 'created_at', NOT 'creation_date'
        # created_at is manually defined above, so only list these
        fields = ['id', 'start_date', 'end_date']


# =============================================================================
# INSTITUTION DOCUMENT
# =============================================================================

@registry.register_document
class InstitutionDocument(Document):
    """
    Elasticsearch document for Institution model.
    
    Model fields: id, city, website, type
    Computed: name, acronym, description, country
    """
    name = fields.TextField(
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
        }
    )

    acronym = fields.TextField(
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )

    description = fields.TextField(
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
        }
    )

    country = fields.ObjectField(
        properties={
            'id': fields.IntegerField(),
            'name': fields.TextField()
        }
    )

    # Institution type for faceted filtering
    institution_type = fields.KeywordField()

    def prepare_name(self, instance):
        return instance.name or ''

    def prepare_acronym(self, instance):
        return instance.acronym or ''

    def prepare_description(self, instance):
        return instance.description or instance.description_en or instance.description_ar or ''

    def prepare_country(self, instance):
        if instance.country:
            return {
                'id': instance.country.id,
                'name': str(instance.country)
            }
        return {'id': None, 'name': ''}

    def prepare_institution_type(self, instance):
        return instance.type or ''

    class Index:
        name = 'institutions'
        settings = get_index_settings()

    class Django:
        model = Institution
        # Institution model has these fields directly
        fields = ['id', 'city', 'website', 'type']
