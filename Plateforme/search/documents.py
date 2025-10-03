from django_elasticsearch_dsl import Document, fields
from elasticsearch_dsl import analysis, analyzer
from django_elasticsearch_dsl.registries import registry
from resources.models import Course, Document as DocModel, NLPTool, Corpus, Institution
from projects.models import Project
from events.models import Event
from accounts.models import CustomUser

phonetic_filter = analysis.token_filter(
    'phonetic_filter',
    type='phonetic',
    encoder='double_metaphone'
)

arabic_stop = analysis.token_filter(
    'arabic_stop',
    type='stop',
    stopwords='_arabic_'
)

arabic_stemmer = analysis.token_filter(
    'arabic_stemmer',
    type='stemmer',
    language='arabic'
)

english_stemmer = analysis.token_filter(
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

@registry.register_document
class UserDocument(Document):
    full_name = fields.TextField(
        analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )

    class Index:
        name = 'users'
        settings = {
            'number_of_shards': 1,
            'number_of_replicas': 0
        }

    class Django:
        model = CustomUser
        fields = [
            'id',
            'email',
            'bio',
            'avatar',
            'is_email_verified',
            'is_superuser',
            'is_staff'
        ]

@registry.register_document
class CourseDocument(Document):
    author = fields.ObjectField(
        properties={
            'id': fields.Keyword(),
            'email': fields.Keyword(),
            'full_name': fields.Text(),
        }
    )

    institution_name = fields.TextField(
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer)
        }
    )

    institution_acronym = fields.TextField(
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer)
        }
    )

    title = fields.TextField(fields={
        'raw': fields.KeywordField(),
        'english': fields.TextField(analyzer=english_analyzer),
        'arabic': fields.TextField(analyzer=arabic_analyzer),
        'phonetic': fields.TextField(analyzer=phonetic_analyzer)
    })
    
    description = fields.TextField(fields={
        'raw': fields.KeywordField(),
        'english': fields.TextField(analyzer=english_analyzer),
        'arabic': fields.TextField(analyzer=arabic_analyzer)
    })
    
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
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
        }
    )

    field_display = fields.TextField(
        analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
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
        if instance.author:
            return {
                'id': str(instance.author.id),
                'email': instance.author.email,
                'full_name': instance.author.full_name or instance.author.email
            }
        return {
            'id': '',
            'email': '',
            'full_name': 'Anonymous'
        }

    def prepare_keywords(self, instance):
     if not instance.keywords:
        return []
    
     if isinstance(instance.keywords, str):
        keywords = instance.keywords.replace('،', ',')  # conversion des virgules arabes
        return [kw.strip() for kw in keywords.split(',') if kw.strip()]
    
     elif isinstance(instance.keywords, (list, tuple)):
        return list(instance.keywords)

     return []
    
    def prepare_field(self, instance):
        value = instance.field
        return str(value) if value else ""

    def prepare_field_display(self, instance):
        if hasattr(instance, 'get_field_display'):
            value = instance.get_field_display()
            return str(value) if value else ""
        return ""

    def prepare_language(self, instance):
        value = instance.language
        return str(value) if value else ""

    def prepare_language_display(self, instance):
        if hasattr(instance, 'get_language_display'):
            value = instance.get_language_display()
            return str(value) if value else ""
        return ""

    def prepare_academic_level(self, instance):
        value = instance.academic_level
        return str(value) if value else ""

    def prepare_academic_level_display(self, instance):
        if hasattr(instance, 'get_academic_level_display'):
            value = instance.get_academic_level_display()
            return str(value) if value else ""
        return ""
    
    def prepare_institution_name(self, instance):
        if instance.institution:
            return str(instance.institution.name)
        return ""

    def prepare_institution_acronym(self, instance):
        if instance.institution:
            return str(instance.institution.acronym)
        return ""

    class Index:
        name = 'courses'
        settings = {
            "number_of_shards": 1,
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

    class Django:
        model = Course
        fields = [
            'id',
            'creation_date',
            'academic_year',
        ]

@registry.register_document
class ToolDocument(Document):
    author = fields.ObjectField(
        properties={
            'id': fields.Keyword(),
            'email': fields.Keyword(),
            'full_name': fields.Text(),
        }
    )
    
    title = fields.TextField(fields={
        'raw': fields.KeywordField(),
        'english': fields.TextField(analyzer=english_analyzer),
        'arabic': fields.TextField(analyzer=arabic_analyzer),
        'phonetic': fields.TextField(analyzer=phonetic_analyzer)
    })
    
    description = fields.TextField(fields={
        'raw': fields.KeywordField(),
        'english': fields.TextField(analyzer=english_analyzer),
        'arabic': fields.TextField(analyzer=arabic_analyzer),
        'phonetic': fields.TextField(analyzer=phonetic_analyzer)
    })

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
        if instance.author:
            return {
                'id': str(instance.author.id),
                'email': instance.author.email,
                'full_name': instance.author.full_name or instance.author.email
            }
        return {
            'id': '',
            'email': '',
            'full_name': 'Anonymous'
        }

    def prepare_keywords(self, instance):
     if not instance.keywords:
        return []
    
     if isinstance(instance.keywords, str):
        keywords = instance.keywords.replace('،', ',')  # conversion des virgules arabes
        return [kw.strip() for kw in keywords.split(',') if kw.strip()]
    
     elif isinstance(instance.keywords, (list, tuple)):
        return list(instance.keywords)

     return []

    def prepare_tool_type(self, instance):
        value = instance.tool_type
        return str(value) if value else ""

    def prepare_tool_type_display(self, instance):
        if hasattr(instance, 'get_tool_type_display'):
            value = instance.get_tool_type_display()
            return str(value) if value else ""
        return ""

    def prepare_language(self, instance):
        value = instance.language
        return str(value) if value else ""

    def prepare_language_display(self, instance):
        if hasattr(instance, 'get_language_display'):
            value = instance.get_language_display()
            return str(value) if value else ""
        return ""

    def prepare_supported_languages(self, instance):
        if instance.supported_languages:
            return [str(lang) for lang in instance.get_supported_languages_display()]
        return []

    class Index:
        name = 'nlp_tools'
        settings = {
            "number_of_shards": 1,
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

    class Django:
        model = NLPTool
        fields = [
            'id',
            'version',
            'creation_date',
            'last_updated',
        ]

@registry.register_document
class CorpusDocument(Document):
    author = fields.ObjectField(
        properties={
            'id': fields.Keyword(),
            'email': fields.Keyword(),
            'full_name': fields.Text(),
        }
    )
    
    title = fields.TextField(fields={
        'raw': fields.KeywordField(),
        'english': fields.TextField(analyzer=english_analyzer),
        'arabic': fields.TextField(analyzer=arabic_analyzer),
        'phonetic': fields.TextField(analyzer=phonetic_analyzer)
    })

    description = fields.TextField(fields={
        'raw': fields.KeywordField(),
        'english': fields.TextField(analyzer=english_analyzer),
        'arabic': fields.TextField(analyzer=arabic_analyzer),
        'phonetic': fields.TextField(analyzer=phonetic_analyzer)
    })

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
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
        }
    )

    field_display = fields.TextField(
        analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
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
        if instance.author:
            return {
                'id': str(instance.author.id),
                'email': instance.author.email,
                'full_name': instance.author.full_name or instance.author.email
            }
        return {
            'id': '',
            'email': '',
            'full_name': 'Anonymous'
        }

    def prepare_keywords(self, instance):
     if not instance.keywords:
        return []
    
     if isinstance(instance.keywords, str):
        keywords = instance.keywords.replace('،', ',')  # conversion des virgules arabes
        return [kw.strip() for kw in keywords.split(',') if kw.strip()]
    
     elif isinstance(instance.keywords, (list, tuple)):
        return list(instance.keywords)

     return []
    
    def prepare_field(self, instance):
        value = instance.field
        return str(value) if value else ""

    def prepare_field_display(self, instance):
        if hasattr(instance, 'get_field_display'):
            value = instance.get_field_display()
            return str(value) if value else ""
        return ""

    def prepare_language(self, instance):
        value = instance.language
        return str(value) if value else ""

    def prepare_language_display(self, instance):
        if hasattr(instance, 'get_language_display'):
            value = instance.get_language_display()
            return str(value) if value else ""
        return ""

    class Index:
        name = 'corpora'
        settings = {
            "number_of_shards": 1,
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
    
    class Django:
        model = Corpus
        fields = [
            'id',
            'creation_date',
            'size',
            'file_format'
        ]

@registry.register_document
class ResourceDocument(Document):
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
            'id': fields.Keyword(),
            'email': fields.Keyword(),
            'full_name': fields.Text(),
        }
    )

    title = fields.TextField(fields={
        'raw': fields.KeywordField(),
        'english': fields.TextField(analyzer=english_analyzer),
        'arabic': fields.TextField(analyzer=arabic_analyzer),
        'phonetic': fields.TextField(analyzer=phonetic_analyzer)
    })

    description = fields.TextField(fields={
        'raw': fields.KeywordField(),
        'english': fields.TextField(analyzer=english_analyzer),
        'arabic': fields.TextField(analyzer=arabic_analyzer),
        'phonetic': fields.TextField(analyzer=phonetic_analyzer)
    })

    keywords = fields.KeywordField(
        multi=True,
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer),
            'phonetic': fields.TextField(analyzer=phonetic_analyzer)
        }
    )

    subtype_fields = fields.ObjectField(properties={
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
    })

    def prepare_author(self, instance):
        if instance.author:
            return {
                'id': str(instance.author.id),
                'email': instance.author.email,
                'full_name': instance.author.full_name or instance.author.email
            }
        return {
            'id': '',
            'email': '',
            'full_name': 'Anonymous'
        }

    def prepare_keywords(self, instance):
     if not instance.keywords:
        return []
    
     if isinstance(instance.keywords, str):
        keywords = instance.keywords.replace('،', ',')  # conversion des virgules arabes
        return [kw.strip() for kw in keywords.split(',') if kw.strip()]
    
     elif isinstance(instance.keywords, (list, tuple)):
        return list(instance.keywords)

     return []
    
    def prepare_document_type(self, instance):
        value = instance.document_type
        return str(value) if value else ""

    def prepare_document_type_display(self, instance):
        if hasattr(instance, 'get_document_type_display'):
            value = instance.get_document_type_display()
            return str(value) if value else ""
        return ""
    
    def prepare_subtype_fields(self, instance):
        data = {}
        if hasattr(instance, 'thesis'):
            data.update({
                'supervisor': str(instance.thesis.supervisor) if instance.thesis.supervisor else "",
                'institution': str(instance.thesis.institution.name) if instance.thesis.institution else "",
                'defense_year': instance.thesis.defense_year
            })
        elif hasattr(instance, 'article'):
            data.update({
                'journal': str(instance.article.journal) if instance.article.journal else "",
                'doi': str(instance.article.doi) if instance.article.doi else ""
            })
        elif hasattr(instance, 'memoir'):
            data.update({
                'academic_level': str(instance.memoir.get_academic_level_display()) if hasattr(instance.memoir, 'get_academic_level_display') else "",
                'institution': str(instance.memoir.institution.name) if instance.memoir.institution else "",
                'defense_year': instance.memoir.defense_year
            })
        return data

    class Index:
        name = 'resources'
        settings = {
            "number_of_shards": 1,
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
    
    class Django:
        model = DocModel
        fields = [
            'id',
            'file_format',
            'creation_date',
        ]

@registry.register_document
class ProjectDocument(Document):
    coordinator = fields.ObjectField(properties={
        'id': fields.IntegerField(),
        'full_name': fields.TextField(),
    })

    institution = fields.ObjectField(properties={
        'id': fields.IntegerField(),
        'name': fields.TextField(
            fields={
                'raw': fields.KeywordField(),
                'english': fields.TextField(analyzer=english_analyzer)
            }
        ),
    })

    members = fields.NestedField(properties={
        'id': fields.IntegerField(),
        'full_name': fields.TextField(),
    })

    title = fields.TextField(fields={
        'raw': fields.KeywordField(),
        'english': fields.TextField(analyzer=english_analyzer),
        'arabic': fields.TextField(analyzer=arabic_analyzer),
        'phonetic': fields.TextField(analyzer=phonetic_analyzer)
    })
    
    description = fields.TextField(fields={
        'raw': fields.KeywordField(),
        'english': fields.TextField(analyzer=english_analyzer),
        'arabic': fields.TextField(analyzer=arabic_analyzer),
        'phonetic': fields.TextField(analyzer=phonetic_analyzer)
    })

    status = fields.TextField(
        analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )
    

    class Index:
        name = 'projects'
        settings = {
            "number_of_shards": 1,
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
    
    class Django:
        model = Project
        fields = [
            'id',
        ]

@registry.register_document
class EventDocument(Document):
    organizer = fields.ObjectField(properties={
        'id': fields.IntegerField(),
        'name': fields.TextField(
            fields={
                'raw': fields.KeywordField(),
                'english': fields.TextField(analyzer=english_analyzer)
            }
        ),
    })

    created_by = fields.ObjectField(properties={
        'id': fields.IntegerField(),
        'full_name': fields.TextField(),
    })

    domains = fields.KeywordField(
        multi=True,
        fields={
            'raw': fields.KeywordField(),
            'english': fields.TextField(analyzer=english_analyzer),
            'arabic': fields.TextField(analyzer=arabic_analyzer)
        }
    )
    
    title = fields.TextField(fields={
        'raw': fields.KeywordField(),
        'english': fields.TextField(analyzer=english_analyzer),
        'arabic': fields.TextField(analyzer=arabic_analyzer),
        'phonetic': fields.TextField(analyzer=phonetic_analyzer)
    })
    
    description = fields.TextField(fields={
        'raw': fields.KeywordField(),
        'english': fields.TextField(analyzer=english_analyzer),
        'arabic': fields.TextField(analyzer=arabic_analyzer),
        'phonetic': fields.TextField(analyzer=phonetic_analyzer)
    })

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

    def prepare_domains(self, instance):
        if instance.domains:
            return [str(domain.strip()) for domain in instance.domains.split(',')]
        return []

    def prepare_event_type(self, instance):
        value = instance.event_type
        return str(value) if value else ""

    def prepare_event_type_display(self, instance):
        if hasattr(instance, 'get_event_type_display'):
            value = instance.get_event_type_display()
            return str(value) if value else ""
        return ""

    def prepare_location(self, instance):
        value = instance.location
        return str(value) if value else ""

    class Index:
        name = 'events'
        settings = {
            "number_of_shards": 1,
            "analysis": {
                "filter": {
                    "arabic_stop": {"type": "stop", "stopwords": "_arabic_"},
                    "arabic_stemmer": {"type": "stemmer", "language": "arabic"},
                    "english_stemmer": {"type": "stemmer", "language": "english"},
                    "phonetic_filter": {"type": "phonetic", "encoder": "beider_morse", "rule_type": "approx"},
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
                    },
                }
            }
        }
    
    class Django:
        model = Event
        fields = [
            'id',
            'start_date',
            'end_date',
            'submission_deadline',
            'website',
            'contact_email',
            'is_approved',
            'created_at',
            'updated_at',
        ]
@registry.register_document
class InstitutionDocument(Document):
    country = fields.ObjectField(
        properties={
            'name': fields.TextField(
                fields={
                    'raw': fields.KeywordField(),
                    'english': fields.TextField(analyzer=english_analyzer),
                    'arabic': fields.TextField(analyzer=arabic_analyzer),
                }
            ),
            'code': fields.KeywordField()
        }
    )
    
    specialties = fields.NestedField(
        properties={
            'name': fields.TextField(
                fields={
                    'raw': fields.KeywordField(),
                    'english': fields.TextField(analyzer=english_analyzer),
                    'arabic': fields.TextField(analyzer=arabic_analyzer),
                }
            ),
            'code': fields.KeywordField()
        }
    )
    
    name = fields.TextField(fields={
        'raw': fields.KeywordField(),
        'english': fields.TextField(analyzer=english_analyzer),
        'arabic': fields.TextField(analyzer=arabic_analyzer),
        'phonetic': fields.TextField(analyzer=phonetic_analyzer),
    })
    
    acronym = fields.TextField(fields={
        'raw': fields.KeywordField(),
        'english': fields.TextField(analyzer=english_analyzer),
        'arabic': fields.TextField(analyzer=arabic_analyzer),
        'phonetic': fields.TextField(analyzer=phonetic_analyzer),
    })
    
    description = fields.TextField(fields={
        'raw': fields.KeywordField(),
        'english': fields.TextField(analyzer=english_analyzer),
        'arabic': fields.TextField(analyzer=arabic_analyzer),
    })
    
    def prepare_country(self, instance):
        if instance.country:
            return {
                'name': str(instance.country.name),
                'code': str(instance.country.code)
            }
        return {'name': '', 'code': ''}
    
    def prepare_specialties(self, instance):
        if instance.specialties.exists():
            return [{
                'name': str(specialty.name),
                'code': str(specialty.code)
            } for specialty in instance.specialties.all()]
        return []
    
    class Index:
        name = 'institutions'
        settings = {
            "number_of_shards": 1,
            "analysis": {
                "filter": {
                    "arabic_stop": {"type": "stop", "stopwords": "_arabic_"},
                    "arabic_stemmer": {"type": "stemmer", "language": "arabic"},
                    "english_stemmer": {"type": "stemmer", "language": "english"},
                    "phonetic_filter": {"type": "phonetic", "encoder": "beider_morse", "rule_type": "approx"},
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
                    },
                }
            }
        }
    
    class Django:
        model = Institution
        fields = [
            'id',
            'type',
            'city',
            'website',
            'email',
            'phone',
            'address',
          
        ]
