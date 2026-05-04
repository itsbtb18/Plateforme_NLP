"""
Elasticsearch Document definitions for all searchable models.

This module defines the mappings between Django models and Elasticsearch indices.
Each Document class specifies:
- Field mappings with multi-language analyzers (Arabic, English, Phonetic)
- Custom prepare methods for computed fields
- Index settings with analyzer configurations

Supports dis_max ranking and faceted aggregations.
"""
<<<<<<< HEAD

=======
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
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
<<<<<<< HEAD
    "phonetic_filter", type="phonetic", encoder="double_metaphone"
)

arabic_stop = token_filter("arabic_stop", type="stop", stopwords="_arabic_")

arabic_stemmer = token_filter("arabic_stemmer", type="stemmer", language="arabic")

english_stemmer = token_filter("english_stemmer", type="stemmer", language="english")

arabic_analyzer = analyzer(
    "arabic_analyzer",
    tokenizer="icu_tokenizer",
    filter=["lowercase", "arabic_normalization", arabic_stop, arabic_stemmer],
)

english_analyzer = analyzer(
    "english_analyzer",
    tokenizer="standard",
    filter=["lowercase", "stop", english_stemmer],
)

phonetic_analyzer = analyzer(
    "phonetic_analyzer",
    tokenizer="standard",
    filter=["lowercase", "asciifolding", phonetic_filter],
=======
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
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
)


# =============================================================================
# SHARED INDEX SETTINGS
# =============================================================================

<<<<<<< HEAD

=======
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
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
<<<<<<< HEAD
                "phonetic_filter": {
                    "type": "phonetic",
                    "encoder": "beider_morse",
                    "rule_type": "approx",
                },
=======
                "phonetic_filter": {"type": "phonetic", "encoder": "beider_morse", "rule_type": "approx"}
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
            },
            "analyzer": {
                "arabic_analyzer": {
                    "type": "custom",
                    "tokenizer": "icu_tokenizer",
<<<<<<< HEAD
                    "filter": [
                        "lowercase",
                        "arabic_normalization",
                        "arabic_stop",
                        "arabic_stemmer",
                    ],
=======
                    "filter": ["lowercase", "arabic_normalization", "arabic_stop", "arabic_stemmer"]
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
                },
                "english_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
<<<<<<< HEAD
                    "filter": ["lowercase", "english_stemmer"],
=======
                    "filter": ["lowercase", "english_stemmer"]
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
                },
                "phonetic_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
<<<<<<< HEAD
                    "filter": ["lowercase", "phonetic_filter"],
                },
            },
        },
=======
                    "filter": ["lowercase", "phonetic_filter"]
                }
            }
        }
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
    }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

<<<<<<< HEAD

=======
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
def prepare_author_field(instance):
    """Prepare author ObjectField from a model instance with an author FK."""
    if instance.author:
        return {
<<<<<<< HEAD
            "id": str(instance.author.id),
            "email": instance.author.email,
            "full_name": instance.author.get_full_name_display or instance.author.email,
        }
    return {"id": "", "email": "", "full_name": "Anonymous"}
=======
            'id': str(instance.author.id),
            'email': instance.author.email,
            'full_name': instance.author.get_full_name_display or instance.author.email
        }
    return {'id': '', 'email': '', 'full_name': 'Anonymous'}
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e


def prepare_keywords_field(keywords):
    """Parse keywords string/list into a list of strings."""
    if not keywords:
        return []
    if isinstance(keywords, str):
<<<<<<< HEAD
        keywords = keywords.replace("،", ",")
        return [kw.strip() for kw in keywords.split(",") if kw.strip()]
=======
        keywords = keywords.replace('،', ',')
        return [kw.strip() for kw in keywords.split(',') if kw.strip()]
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
    elif isinstance(keywords, (list, tuple)):
        return list(keywords)
    return []


# =============================================================================
# USER DOCUMENT
# =============================================================================

<<<<<<< HEAD

=======
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
@registry.register_document
class UserDocument(Document):
    """
    Elasticsearch document for CustomUser model.
<<<<<<< HEAD

    Model fields: id, email, bio, avatar, is_email_verified, is_superuser, is_staff
    Computed: full_name (from full_name_en/full_name_ar)
    """

    # Manual field - computed from full_name_en/full_name_ar
    full_name = fields.TextField(
        analyzer="standard",
        fields={
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
            "phonetic": fields.TextField(analyzer=phonetic_analyzer),
        },
    )

    bio = fields.TextField(
        fields={
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
=======
    
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
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }
    )

    def prepare_full_name(self, instance):
        """Combine full_name fields with fallback."""
        return instance.get_full_name_display or instance.email
<<<<<<< HEAD

    def prepare_bio(self, instance):
        """Return bio with fallback."""
        return instance.bio or instance.bio_en or instance.bio_ar or ""

    class Index:
        name = "users"
=======
    
    def prepare_bio(self, instance):
        """Return bio with fallback."""
        return instance.bio or instance.bio_en or instance.bio_ar or ''

    class Index:
        name = 'users'
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        settings = get_index_settings()

    class Django:
        model = CustomUser
        # Only list fields that exist on the model and are NOT manually defined above
        fields = [
<<<<<<< HEAD
            "id",
            "email",
            "avatar",
            "is_email_verified",
            "is_superuser",
            "is_staff",
=======
            'id',
            'email',
            'avatar',
            'is_email_verified',
            'is_superuser',
            'is_staff'
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        ]


# =============================================================================
# COURSE DOCUMENT
# =============================================================================

<<<<<<< HEAD

=======
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
@registry.register_document
class CourseDocument(Document):
    """
    Elasticsearch document for Course model.
<<<<<<< HEAD

=======
    
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
    Model fields: id, creation_date, academic_year
    Computed: author, institution_name, institution_acronym, title, description,
              keywords, field, field_display, language, language_display,
              academic_level, academic_level_display
    """
<<<<<<< HEAD

    author = fields.ObjectField(
        properties={
            "id": fields.KeywordField(),
            "email": fields.KeywordField(),
            "full_name": fields.TextField(),
=======
    author = fields.ObjectField(
        properties={
            'id': fields.KeywordField(),
            'email': fields.KeywordField(),
            'full_name': fields.TextField(),
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }
    )

    institution_name = fields.TextField(
        fields={
<<<<<<< HEAD
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
=======
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }
    )

    institution_acronym = fields.TextField(
        fields={
<<<<<<< HEAD
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
=======
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer)
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }
    )

    title = fields.TextField(
        fields={
<<<<<<< HEAD
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
            "phonetic": fields.TextField(analyzer=phonetic_analyzer),
=======
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }
    )

    description = fields.TextField(
        fields={
<<<<<<< HEAD
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
            "phonetic": fields.TextField(analyzer=phonetic_analyzer),
=======
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }
    )

    keywords = fields.KeywordField(
        multi=True,
        fields={
<<<<<<< HEAD
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
            "phonetic": fields.TextField(analyzer=phonetic_analyzer),
        },
    )

    field = fields.TextField(
        analyzer="standard",
        fields={
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
        },
    )

    field_display = fields.TextField(
        analyzer="standard",
        fields={
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
        },
    )

    language = fields.TextField(
        analyzer="standard",
        fields={
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
        },
    )

    language_display = fields.TextField(
        analyzer="standard",
        fields={
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
        },
    )

    academic_level = fields.TextField(
        analyzer="standard",
        fields={
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
        },
    )

    academic_level_display = fields.TextField(
        analyzer="standard",
        fields={
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
        },
=======
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
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
    )

    def prepare_author(self, instance):
        return prepare_author_field(instance)

    def prepare_keywords(self, instance):
        return prepare_keywords_field(instance.keywords)

    def prepare_title(self, instance):
<<<<<<< HEAD
        return instance.title or ""

    def prepare_description(self, instance):
        return instance.description or ""
=======
        return instance.title or ''

    def prepare_description(self, instance):
        return instance.description or ''
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e

    def prepare_field(self, instance):
        return str(instance.field) if instance.field else ""

    def prepare_field_display(self, instance):
<<<<<<< HEAD
        if hasattr(instance, "get_field_display"):
=======
        if hasattr(instance, 'get_field_display'):
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
            return str(instance.get_field_display()) or ""
        return ""

    def prepare_language(self, instance):
        return str(instance.language) if instance.language else ""

    def prepare_language_display(self, instance):
<<<<<<< HEAD
        if hasattr(instance, "get_language_display"):
=======
        if hasattr(instance, 'get_language_display'):
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
            return str(instance.get_language_display()) or ""
        return ""

    def prepare_academic_level(self, instance):
        return str(instance.academic_level) if instance.academic_level else ""

    def prepare_academic_level_display(self, instance):
<<<<<<< HEAD
        if hasattr(instance, "get_academic_level_display"):
=======
        if hasattr(instance, 'get_academic_level_display'):
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
            return str(instance.get_academic_level_display()) or ""
        return ""

    def prepare_institution_name(self, instance):
        if instance.institution:
            return str(instance.institution.name)
        return ""

    def prepare_institution_acronym(self, instance):
        if instance.institution:
<<<<<<< HEAD
            return str(instance.institution.acronym or "")
        return ""

    def get_queryset(self):
        return super().get_queryset().filter(approval_status="approved")

    class Index:
        name = "courses"
=======
            return str(instance.institution.acronym or '')
        return ""

    class Index:
        name = 'courses'
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        settings = get_index_settings()

    class Django:
        model = Course
        # Course inherits from ResourceBase which has creation_date
<<<<<<< HEAD
        fields = ["id", "creation_date", "academic_year"]
=======
        fields = ['id', 'creation_date', 'academic_year']
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e


# =============================================================================
# TOOL DOCUMENT
# =============================================================================

<<<<<<< HEAD

=======
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
@registry.register_document
class ToolDocument(Document):
    """
    Elasticsearch document for NLPTool model.
<<<<<<< HEAD

=======
    
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
    Model fields: id, version, creation_date, last_updated
    Computed: author, title, description, keywords, tool_type, tool_type_display,
              language, language_display, supported_languages
    """
<<<<<<< HEAD

    author = fields.ObjectField(
        properties={
            "id": fields.KeywordField(),
            "email": fields.KeywordField(),
            "full_name": fields.TextField(),
=======
    author = fields.ObjectField(
        properties={
            'id': fields.KeywordField(),
            'email': fields.KeywordField(),
            'full_name': fields.TextField(),
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }
    )

    title = fields.TextField(
        fields={
<<<<<<< HEAD
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
            "phonetic": fields.TextField(analyzer=phonetic_analyzer),
=======
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }
    )

    description = fields.TextField(
        fields={
<<<<<<< HEAD
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
            "phonetic": fields.TextField(analyzer=phonetic_analyzer),
=======
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }
    )

    keywords = fields.KeywordField(
        multi=True,
        fields={
<<<<<<< HEAD
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
            "phonetic": fields.TextField(analyzer=phonetic_analyzer),
        },
    )

    tool_type = fields.TextField(
        analyzer="standard",
        fields={
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
        },
    )

    tool_type_display = fields.TextField(
        analyzer="standard",
        fields={
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
        },
    )

    language = fields.TextField(
        analyzer="standard",
        fields={
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
        },
    )

    language_display = fields.TextField(
        analyzer="standard",
        fields={
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
        },
=======
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
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
    )

    supported_languages = fields.KeywordField(multi=True)

    def prepare_author(self, instance):
        return prepare_author_field(instance)

    def prepare_keywords(self, instance):
        return prepare_keywords_field(instance.keywords)

    def prepare_title(self, instance):
<<<<<<< HEAD
        return instance.title or ""

    def prepare_description(self, instance):
        return instance.description or ""
=======
        return instance.title or ''

    def prepare_description(self, instance):
        return instance.description or ''
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e

    def prepare_tool_type(self, instance):
        return str(instance.tool_type) if instance.tool_type else ""

    def prepare_tool_type_display(self, instance):
<<<<<<< HEAD
        if hasattr(instance, "get_tool_type_display"):
=======
        if hasattr(instance, 'get_tool_type_display'):
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
            return str(instance.get_tool_type_display()) or ""
        return ""

    def prepare_language(self, instance):
        return str(instance.language) if instance.language else ""

    def prepare_language_display(self, instance):
<<<<<<< HEAD
        if hasattr(instance, "get_language_display"):
=======
        if hasattr(instance, 'get_language_display'):
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
            return str(instance.get_language_display()) or ""
        return ""

    def prepare_supported_languages(self, instance):
        if instance.supported_languages:
            return instance.get_supported_languages_list()
        return []

<<<<<<< HEAD
    def get_queryset(self):
        return super().get_queryset().filter(approval_status="approved")

    class Index:
        name = "nlp_tools"
=======
    class Index:
        name = 'nlp_tools'
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        settings = get_index_settings()

    class Django:
        model = NLPTool
        # NLPTool inherits from ResourceBase which has creation_date
<<<<<<< HEAD
        fields = ["id", "version", "creation_date", "last_updated"]
=======
        fields = ['id', 'version', 'creation_date', 'last_updated']
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e


# =============================================================================
# CORPUS DOCUMENT
# =============================================================================

<<<<<<< HEAD

=======
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
@registry.register_document
class CorpusDocument(Document):
    """
    Elasticsearch document for Corpus model.
<<<<<<< HEAD

    Model fields: id, creation_date
    Computed: author, title, description, keywords, field, field_display,
              language, language_display
    """

    author = fields.ObjectField(
        properties={
            "id": fields.KeywordField(),
            "email": fields.KeywordField(),
            "full_name": fields.TextField(),
=======
    
    Model fields: id, creation_date, size, file_format
    Computed: author, title, description, keywords, field, field_display,
              language, language_display
    """
    author = fields.ObjectField(
        properties={
            'id': fields.KeywordField(),
            'email': fields.KeywordField(),
            'full_name': fields.TextField(),
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }
    )

    title = fields.TextField(
        fields={
<<<<<<< HEAD
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
            "phonetic": fields.TextField(analyzer=phonetic_analyzer),
=======
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }
    )

    description = fields.TextField(
        fields={
<<<<<<< HEAD
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
            "phonetic": fields.TextField(analyzer=phonetic_analyzer),
=======
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }
    )

    keywords = fields.KeywordField(
        multi=True,
        fields={
<<<<<<< HEAD
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
            "phonetic": fields.TextField(analyzer=phonetic_analyzer),
        },
    )

    field = fields.TextField(
        analyzer="standard",
        fields={
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
        },
    )

    field_display = fields.TextField(
        analyzer="standard",
        fields={
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
        },
    )

    language = fields.TextField(
        analyzer="standard",
        fields={
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
        },
    )

    language_display = fields.TextField(
        analyzer="standard",
        fields={
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
        },
=======
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
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
    )

    def prepare_author(self, instance):
        return prepare_author_field(instance)

    def prepare_keywords(self, instance):
        return prepare_keywords_field(instance.keywords)

    def prepare_title(self, instance):
<<<<<<< HEAD
        return instance.title or ""

    def prepare_description(self, instance):
        return instance.description or ""
=======
        return instance.title or ''

    def prepare_description(self, instance):
        return instance.description or ''
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e

    def prepare_field(self, instance):
        return str(instance.field) if instance.field else ""

    def prepare_field_display(self, instance):
<<<<<<< HEAD
        if hasattr(instance, "get_field_display"):
=======
        if hasattr(instance, 'get_field_display'):
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
            return str(instance.get_field_display()) or ""
        return ""

    def prepare_language(self, instance):
        return str(instance.language) if instance.language else ""

    def prepare_language_display(self, instance):
<<<<<<< HEAD
        if hasattr(instance, "get_language_display"):
            return str(instance.get_language_display()) or ""
        return ""

    def get_queryset(self):
        return super().get_queryset().filter(approval_status="approved")

    class Index:
        name = "corpora"
=======
        if hasattr(instance, 'get_language_display'):
            return str(instance.get_language_display()) or ""
        return ""

    class Index:
        name = 'corpora'
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        settings = get_index_settings()

    class Django:
        model = Corpus
        # Corpus inherits from ResourceBase which has creation_date
<<<<<<< HEAD
        fields = ["id", "creation_date"]
=======
        fields = ['id', 'creation_date', 'file_format']
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e


# =============================================================================
# RESOURCE/DOCUMENT DOCUMENT
# =============================================================================

<<<<<<< HEAD

=======
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
@registry.register_document
class ResourceDocument(Document):
    """
    Elasticsearch document for Document model (theses, articles, memoirs).
<<<<<<< HEAD

=======
    
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
    Model fields: id, file_format, creation_date
    Computed: document_type, document_type_display, author, title, description,
              keywords, subtype_fields
    """
<<<<<<< HEAD

    document_type = fields.TextField(
        analyzer="standard",
        fields={
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
        },
    )

    document_type_display = fields.TextField(
        analyzer="standard",
        fields={
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
        },
=======
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
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
    )

    author = fields.ObjectField(
        properties={
<<<<<<< HEAD
            "id": fields.KeywordField(),
            "email": fields.KeywordField(),
            "full_name": fields.TextField(),
=======
            'id': fields.KeywordField(),
            'email': fields.KeywordField(),
            'full_name': fields.TextField(),
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }
    )

    title = fields.TextField(
        fields={
<<<<<<< HEAD
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
            "phonetic": fields.TextField(analyzer=phonetic_analyzer),
=======
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }
    )

    description = fields.TextField(
        fields={
<<<<<<< HEAD
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
            "phonetic": fields.TextField(analyzer=phonetic_analyzer),
=======
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }
    )

    keywords = fields.KeywordField(
        multi=True,
        fields={
<<<<<<< HEAD
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
            "phonetic": fields.TextField(analyzer=phonetic_analyzer),
        },
=======
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
        }
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
    )

    subtype_fields = fields.ObjectField(
        properties={
<<<<<<< HEAD
            "supervisor": fields.TextField(
                fields={
                    "raw": fields.KeywordField(),
                    "english": fields.TextField(analyzer=english_analyzer),
                    "arabic": fields.TextField(analyzer=arabic_analyzer),
                }
            ),
            "journal": fields.TextField(
                fields={
                    "raw": fields.KeywordField(),
                    "english": fields.TextField(analyzer=english_analyzer),
                }
            ),
            "academic_level": fields.TextField(
                fields={
                    "raw": fields.KeywordField(),
                    "english": fields.TextField(analyzer=english_analyzer),
                    "arabic": fields.TextField(analyzer=arabic_analyzer),
                }
            ),
            "doi": fields.TextField(),
            "defense_year": fields.IntegerField(),
            "institution": fields.TextField(
                fields={
                    "raw": fields.KeywordField(),
                    "english": fields.TextField(analyzer=english_analyzer),
                }
            ),
=======
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
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }
    )

    def prepare_author(self, instance):
        return prepare_author_field(instance)

    def prepare_keywords(self, instance):
        return prepare_keywords_field(instance.keywords)

    def prepare_title(self, instance):
<<<<<<< HEAD
        return instance.title or ""

    def prepare_description(self, instance):
        return instance.description or ""
=======
        return instance.title or ''

    def prepare_description(self, instance):
        return instance.description or ''
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e

    def prepare_document_type(self, instance):
        return str(instance.document_type) if instance.document_type else ""

    def prepare_document_type_display(self, instance):
<<<<<<< HEAD
        if hasattr(instance, "get_document_type_display"):
=======
        if hasattr(instance, 'get_document_type_display'):
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
            return str(instance.get_document_type_display()) or ""
        return ""

    def prepare_subtype_fields(self, instance):
        data = {}
<<<<<<< HEAD
        if hasattr(instance, "thesis") and instance.thesis:
            data.update(
                {
                    "supervisor": str(instance.thesis.supervisor)
                    if instance.thesis.supervisor
                    else "",
                    "institution": str(instance.thesis.institution.name)
                    if instance.thesis.institution
                    else "",
                    "defense_year": instance.thesis.defense_year,
                }
            )
        elif hasattr(instance, "article") and instance.article:
            data.update(
                {
                    "journal": str(instance.article.journal)
                    if instance.article.journal
                    else "",
                    "doi": str(instance.article.doi) if instance.article.doi else "",
                }
            )
        elif hasattr(instance, "memoir") and instance.memoir:
            data.update(
                {
                    "academic_level": str(instance.memoir.get_academic_level_display())
                    if hasattr(instance.memoir, "get_academic_level_display")
                    else "",
                    "institution": str(instance.memoir.institution.name)
                    if instance.memoir.institution
                    else "",
                    "defense_year": instance.memoir.defense_year,
                }
            )
        return data

    def get_queryset(self):
        return super().get_queryset().filter(approval_status="approved")

    class Index:
        name = "resources"
=======
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
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        settings = get_index_settings()

    class Django:
        model = DocModel
        # Document inherits from ResourceBase which has creation_date
<<<<<<< HEAD
        fields = ["id", "creation_date"]
=======
        fields = ['id', 'file_format', 'creation_date']
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e


# =============================================================================
# PROJECT DOCUMENT
# =============================================================================

<<<<<<< HEAD

=======
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
@registry.register_document
class ProjectDocument(Document):
    """
    Elasticsearch document for Project model.
<<<<<<< HEAD

=======
    
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
    Model fields: id (only - dates are manually defined)
    Computed: coordinator, institution, members, title, description, status,
              date_start, date_end, created_at
    """
<<<<<<< HEAD

    coordinator = fields.ObjectField(
        properties={"id": fields.IntegerField(), "full_name": fields.TextField()}
=======
    coordinator = fields.ObjectField(
        properties={
            'id': fields.IntegerField(),
            'full_name': fields.TextField()
        }
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
    )

    institution = fields.ObjectField(
        properties={
<<<<<<< HEAD
            "id": fields.IntegerField(),
            "name": fields.TextField(
                fields={
                    "raw": fields.KeywordField(),
                    "english": fields.TextField(analyzer=english_analyzer),
                    "arabic": fields.TextField(analyzer=arabic_analyzer),
                }
            ),
=======
            'id': fields.IntegerField(),
            'name': fields.TextField(
                fields={
                    'raw': fields.KeywordField(),
                    'english': fields.TextField(analyzer=english_analyzer),
                    'arabic': fields.TextField(analyzer=arabic_analyzer)
                }
            )
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }
    )

    members = fields.NestedField(
<<<<<<< HEAD
        properties={"id": fields.IntegerField(), "full_name": fields.TextField()}
=======
        properties={
            'id': fields.IntegerField(),
            'full_name': fields.TextField()
        }
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
    )

    title = fields.TextField(
        fields={
<<<<<<< HEAD
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
            "phonetic": fields.TextField(analyzer=phonetic_analyzer),
=======
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }
    )

    description = fields.TextField(
        fields={
<<<<<<< HEAD
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
            "phonetic": fields.TextField(analyzer=phonetic_analyzer),
=======
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }
    )

    status = fields.TextField(
<<<<<<< HEAD
        analyzer="standard",
        fields={
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
        },
=======
        analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
    )

    # Manually defined date fields (exist on model)
    date_start = fields.DateField()
    date_end = fields.DateField()
    created_at = fields.DateField()

    def prepare_coordinator(self, instance):
        if instance.coordinator:
            return {
<<<<<<< HEAD
                "id": instance.coordinator.id,
                "full_name": instance.coordinator.get_full_name_display or "",
            }
        return {"id": None, "full_name": ""}
=======
                'id': instance.coordinator.id,
                'full_name': instance.coordinator.get_full_name_display or ''
            }
        return {'id': None, 'full_name': ''}
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e

    def prepare_institution(self, instance):
        if instance.institution:
            return {
<<<<<<< HEAD
                "id": instance.institution.id,
                "name": instance.institution.name or "",
            }
        return {"id": None, "name": ""}

    def prepare_members(self, instance):
        members = []
        for pm in instance.members.filter(status="accepted"):
            members.append(
                {"id": pm.member.id, "full_name": pm.member.get_full_name_display or ""}
            )
        return members

    def prepare_title(self, instance):
        return instance.title or ""

    def prepare_description(self, instance):
        return instance.description or ""
=======
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
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e

    def prepare_status(self, instance):
        return str(instance.status) if instance.status else ""

<<<<<<< HEAD
    def get_queryset(self):
        return super().get_queryset().filter(approval_status="approved")

    class Index:
        name = "projects"
=======
    class Index:
        name = 'projects'
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        settings = get_index_settings()

    class Django:
        model = Project
        # Date fields are manually defined above, don't list them here
<<<<<<< HEAD
        fields = ["id"]
=======
        fields = ['id']
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e


# =============================================================================
# EVENT DOCUMENT
# =============================================================================

<<<<<<< HEAD

=======
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
@registry.register_document
class EventDocument(Document):
    """
    Elasticsearch document for Event model.
<<<<<<< HEAD

=======
    
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
    Model fields: id, start_date, end_date
    Note: Event model has 'created_at', NOT 'creation_date'
    Computed: organizer, created_by, domains, title, description, event_type, location
    """
<<<<<<< HEAD

    organizer = fields.ObjectField(
        properties={
            "id": fields.IntegerField(),
            "name": fields.TextField(
                fields={
                    "raw": fields.KeywordField(),
                    "english": fields.TextField(analyzer=english_analyzer),
                    "arabic": fields.TextField(analyzer=arabic_analyzer),
                }
            ),
=======
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
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }
    )

    created_by = fields.ObjectField(
<<<<<<< HEAD
        properties={"id": fields.IntegerField(), "full_name": fields.TextField()}
=======
        properties={
            'id': fields.IntegerField(),
            'full_name': fields.TextField()
        }
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
    )

    domains = fields.KeywordField(
        multi=True,
        fields={
<<<<<<< HEAD
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
        },
=======
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
    )

    title = fields.TextField(
        fields={
<<<<<<< HEAD
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
            "phonetic": fields.TextField(analyzer=phonetic_analyzer),
=======
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }
    )

    description = fields.TextField(
        fields={
<<<<<<< HEAD
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
            "phonetic": fields.TextField(analyzer=phonetic_analyzer),
=======
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }
    )

    event_type = fields.TextField(
<<<<<<< HEAD
        analyzer="standard",
        fields={
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
        },
    )

    location = fields.TextField(
        analyzer="standard",
        fields={
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
        },
=======
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
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
    )

    # Manually define created_at since it's used for sorting
    created_at = fields.DateField()

    def prepare_organizer(self, instance):
        if instance.organizer:
<<<<<<< HEAD
            return {"id": instance.organizer.id, "name": instance.organizer.name or ""}
        return {"id": None, "name": ""}
=======
            return {
                'id': instance.organizer.id,
                'name': instance.organizer.name or ''
            }
        return {'id': None, 'name': ''}
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e

    def prepare_created_by(self, instance):
        if instance.created_by:
            return {
<<<<<<< HEAD
                "id": instance.created_by.id,
                "full_name": instance.created_by.get_full_name_display or "",
            }
        return {"id": None, "full_name": ""}
=======
                'id': instance.created_by.id,
                'full_name': instance.created_by.get_full_name_display or ''
            }
        return {'id': None, 'full_name': ''}
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e

    def prepare_domains(self, instance):
        if not instance.domains:
            return []
        if isinstance(instance.domains, str):
<<<<<<< HEAD
            return [d.strip() for d in instance.domains.split(",") if d.strip()]
        return (
            list(instance.domains)
            if isinstance(instance.domains, (list, tuple))
            else []
        )

    def prepare_title(self, instance):
        return instance.title or ""

    def prepare_description(self, instance):
        return instance.description or ""
=======
            return [d.strip() for d in instance.domains.split(',') if d.strip()]
        return list(instance.domains) if isinstance(instance.domains, (list, tuple)) else []

    def prepare_title(self, instance):
        return instance.title or ''

    def prepare_description(self, instance):
        return instance.description or ''
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e

    def prepare_event_type(self, instance):
        return str(instance.event_type) if instance.event_type else ""

    def prepare_location(self, instance):
<<<<<<< HEAD
        return instance.location or ""

    def get_queryset(self):
        return super().get_queryset().filter(approval_status="approved")

    class Index:
        name = "events"
=======
        return instance.location or ''

    class Index:
        name = 'events'
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        settings = get_index_settings()

    class Django:
        model = Event
        # FIXED: Event model has 'created_at', NOT 'creation_date'
        # created_at is manually defined above, so only list these
<<<<<<< HEAD
        fields = ["id", "start_date", "end_date"]
=======
        fields = ['id', 'start_date', 'end_date']
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e


# =============================================================================
# INSTITUTION DOCUMENT
# =============================================================================

<<<<<<< HEAD

=======
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
@registry.register_document
class InstitutionDocument(Document):
    """
    Elasticsearch document for Institution model.
<<<<<<< HEAD

    Model fields: id, city, website, type
    Computed: name, acronym, description, country
    """

    name = fields.TextField(
        fields={
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
            "phonetic": fields.TextField(analyzer=phonetic_analyzer),
=======
    
    Model fields: id, city, website, type
    Computed: name, acronym, description, country
    """
    name = fields.TextField(
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }
    )

    acronym = fields.TextField(
        fields={
<<<<<<< HEAD
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
=======
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }
    )

    description = fields.TextField(
        fields={
<<<<<<< HEAD
            "raw": fields.KeywordField(),
            "english": fields.TextField(analyzer=english_analyzer),
            "arabic": fields.TextField(analyzer=arabic_analyzer),
            "phonetic": fields.TextField(analyzer=phonetic_analyzer),
=======
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        }
    )

    country = fields.ObjectField(
<<<<<<< HEAD
        properties={"id": fields.IntegerField(), "name": fields.TextField()}
=======
        properties={
            'id': fields.IntegerField(),
            'name': fields.TextField()
        }
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
    )

    # Institution type for faceted filtering
    institution_type = fields.KeywordField()

    def prepare_name(self, instance):
<<<<<<< HEAD
        return instance.name or ""

    def prepare_acronym(self, instance):
        return instance.acronym or ""

    def prepare_description(self, instance):
        return (
            instance.description
            or instance.description_en
            or instance.description_ar
            or ""
        )

    def prepare_country(self, instance):
        if instance.country:
            return {"id": instance.country.id, "name": str(instance.country)}
        return {"id": None, "name": ""}

    def prepare_institution_type(self, instance):
        return instance.type or ""

    def get_queryset(self):
        return super().get_queryset().filter(approval_status="approved")

    class Index:
        name = "institutions"
=======
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
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        settings = get_index_settings()

    class Django:
        model = Institution
        # Institution model has these fields directly
<<<<<<< HEAD
        fields = ["id", "city", "website", "type"]
=======
        fields = ['id', 'city', 'website', 'type']
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
