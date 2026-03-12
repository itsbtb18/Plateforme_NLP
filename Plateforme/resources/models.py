import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError, PermissionDenied
from institutions.models import Institution
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import F
from django_elasticsearch_dsl.registries import registry
import logging
from typing import Iterable, Tuple, cast

logger = logging.getLogger(__name__)

class ResourceBase(models.Model):
    """
    Base model for all resources.
    """

    class LanguageChoices(models.TextChoices):
        ARABIC = 'ar', _('Arabic')
        ENGLISH = 'en', _('English')

    class ApprovalStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        APPROVED = 'approved', _('Approved')
        REJECTED = 'rejected', _('Rejected')

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    title = models.CharField(
        max_length=200,
        verbose_name=_("Title"),
        help_text=_("Descriptive title of the resource")
    )
    title_ar = models.CharField(
        max_length=200,
        verbose_name=_("Title (Arabic)"),
        blank=True,
        default='',
        help_text=_("Arabic title of the resource")
    )
    title_en = models.CharField(
        max_length=200,
        verbose_name=_("Title (English)"),
        blank=True,
        default='',
        help_text=_("English title of the resource")
    )
    description = models.TextField(
        verbose_name=_("Description"),
        help_text=_("Detailed description of the resource")
    )
    creation_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Creation Date")
    )
    access_link = models.URLField(
        verbose_name=_("Access Link"),
        blank=True,
        null=True
    )
    author = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        verbose_name=_("Author"),
        related_name="%(class)s_set"  
    )
    keywords = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Keywords")
    )
    update_date = models.DateTimeField(
        null=True,  
        blank=True, 
        verbose_name=_("Update Date"),
        help_text=_("Last time this resource was updated")
    )
    language = models.CharField(
        max_length=10,
        choices=LanguageChoices.choices,
        default=LanguageChoices.ARABIC,
        verbose_name=_("Language")
    )
    views_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Views Count")
    )
    
    # Legacy approval field (kept for database compatibility)
    is_approved = models.BooleanField(
        default=False,
        verbose_name=_("Is Approved (Legacy)"),
        help_text=_("Legacy field - use approval_status instead")
    )
    
    approval_status = models.CharField(
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
        verbose_name=_("Approval Status"),
        help_text=_("Content must be approved by admin before being publicly visible")
    )
    
    rejection_reason = models.TextField(
        verbose_name=_("Rejection Reason"),
        blank=True,
        null=True,
        default='',
        help_text=_("Reason for rejection (only filled when status is rejected)")
    )
    
    description_ar = models.TextField(
        verbose_name=_("Description (Arabic)"),
        blank=True,
        default='',
        help_text=_("Arabic description of the resource")
    )
    description_en = models.TextField(
        verbose_name=_("Description (English)"),
        blank=True,
        default='',
        help_text=_("English description of the resource")
    )
    
    # File upload field for documents (PDF, DOCX, etc.)
    uploaded_file = models.FileField(
        upload_to='resources/files/%Y/%m/',
        verbose_name=_("Uploaded File"),
        blank=True,
        null=True,
        help_text=_("Upload a document (PDF, DOCX, TXT, etc.)")
    )

    
    def get_supported_languages_list(self):
        """Return supported languages as a list"""
        supported_langs = getattr(self, 'supported_languages', None)
        if supported_langs:
            return [lang.strip() for lang in str(supported_langs).split(',') if lang.strip()]
        return []

    def get_keywords_list(self):
        """Return keywords as list regardless of storage format"""
        if not self.keywords:
            return []

        if isinstance(self.keywords, str):
            keywords = self.keywords.replace('OO', ',')
            return [kw.strip() for kw in keywords.split(',') if kw.strip()]
        if isinstance(self.keywords, (list, tuple)):
            return list(self.keywords)
        return []

    def get_author_full_name(self):
        if self.author:
            return self.author.get_full_name() or self.author.email
        return ''

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
        model_name = self.__class__.__name__.lower()
        return reverse(f'resources:{model_name}_detail', kwargs={'pk': self.pk})

    def __str__(self):
        from django.utils.translation import get_language
        current_lang = get_language()
        if current_lang == 'ar' and self.title_ar:
            return self.title_ar
        elif self.title_en:
            return self.title_en
        return self.title

    def increment_views(self):
        type(self).objects.filter(pk=self.pk).update(views_count=F('views_count') + 1)
        self.refresh_from_db(fields=['views_count'])

    def save(self, *args, **kwargs):
        try:
            super().save(*args, **kwargs)
            logger.info(f"Resource {self.title} saved successfully")
        except Exception as e:
            logger.error(f"Error saving resource {self.title}: {str(e)}")
            raise

    class Meta:
        abstract = True
        ordering = ['-creation_date']

def validate_academic_year(value):
    import re
    if not re.match(r'^\d{4}-\d{4}$', value):
        raise ValidationError(
            _("Invalid academic year format. Use the format: 2023-2024")
        )
    start_year, end_year = map(int, value.split('-'))
    if end_year != start_year + 1:
        raise ValidationError(
            _("The ending year must be the starting year + 1")
        )
    return value

class FieldChoices(models.TextChoices):
        
        # Domaines principaux
        COMPUTER_SCIENCE = 'computer_science', _('Computer Science')
        LINGUISTICS = 'linguistics', _('Linguistics')
        ARTIFICIAL_INTELLIGENCE = 'ai', _('Artificial Intelligence')
        NLP = 'nlp', _('Natural Language Processing')
        MACHINE_LEARNING = 'ml', _('Machine Learning')
        DATA_SCIENCE = 'data_science', _('Data Science')
        
        # Sous-domaines spécifiques
        COMPUTATIONAL_LINGUISTICS = 'comp_linguistics', _('Computational Linguistics')
        SPEECH_PROCESSING = 'speech_processing', _('Speech Processing')
        TEXT_MINING = 'text_mining', _('Text Mining')
        INFORMATION_RETRIEVAL = 'ir', _('Information Retrieval')
        
        # Domaines linguistiques
        ARABIC_LINGUISTICS = 'arabic_linguistics', _('Arabic Linguistics')
        MORPHOLOGY = 'morphology', _('Morphology')
        SYNTAX = 'syntax', _('Syntax')
        SEMANTICS = 'semantics', _('Semantics')
        
        # Domaines d'application
        TRANSLATION = 'translation', _('Translation')
        SENTIMENT_ANALYSIS = 'sentiment_analysis', _('Sentiment Analysis')
        NAMED_ENTITY = 'named_entity', _('Named Entity Recognition')
        TEXT_CLASSIFICATION = 'text_classification', _('Text Classification')

        # Autres domaines pertinents
        DIGITAL_HUMANITIES = 'digital_humanities', _('Digital Humanities')
        CORPUS_LINGUISTICS = 'corpus_linguistics', _('Corpus Linguistics')
        DOCUMENTATION = 'documentation', _('Documentation')
        OTHER = 'other', _('Other')

class Course(ResourceBase):
    """
    Model representing an academic course.
    """
    class Level(models.TextChoices):
        BACHELOR = 'bachelor', _('Bachelor')
        MASTER = 'master', _('Master')
        DOCTORATE = 'doctorate', _('Doctorate')


    field = models.CharField(
        max_length=50,
        choices=FieldChoices.choices,  # Modifié ici
        default=FieldChoices.OTHER, 
        verbose_name=_("Field of Study"),
        help_text=_("Primary field of the course")
    )

    academic_level = models.CharField(
        max_length=20,
        choices=Level.choices,
        verbose_name=_("Academic Level"),
        help_text=_("Required level of study")
    )

    teacher = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        verbose_name=_("Responsible Teacher"),
        help_text=_("Full name of the teacher"),
        related_name='taught_courses'
    )

    institution = models.ForeignKey(
        Institution,
        on_delete=models.PROTECT,
        verbose_name=_("Institution"),
        help_text=_("University or school offering the course")
    )

    academic_year = models.CharField(
        max_length=9,
        verbose_name=_("Academic Year"),
        help_text=_("Format: 2023-2024"),
        validators=[validate_academic_year]
    )

    prerequisites = models.TextField(
        verbose_name=_("Prerequisites"),
        blank=True,
        default='',
        help_text=_("List the prerequisites for this course")
    )

    syllabus = models.TextField(
        verbose_name=_("Syllabus & Curriculum"),
        blank=True,
        default='',
        help_text=_("Describe the syllabus and curriculum of this course")
    )

    class Meta:
        verbose_name = _("Course")
        verbose_name_plural = _("Courses")
        ordering = ['-academic_year', 'field']
        indexes = [
            models.Index(fields=['field', 'academic_level']),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_academic_level_display()}) - {self.teacher}"

    def get_academic_level_display(self) -> str:
        """Return readable academic level while remaining type-checker friendly."""
        try:
            return self.Level(self.academic_level).label
        except ValueError:
            return self.academic_level

    def publish(self):
        """Publish the course."""
        self.is_public = True
        self.save()
        return self

    def access(self):
        """Check access to the course."""
        if not self.is_public:
            raise PermissionDenied(_("This course requires authentication"))
        return self

class Document(ResourceBase):
    class DocumentType(models.TextChoices):
        ARTICLE = 'article', _('Article')
        THESIS = 'thesis', _('Thesis')
        MEMOIR = 'memoir', _('Memoir')

    document_type = models.CharField(
        max_length=20,
        choices=DocumentType.choices,
        verbose_name=_("Document Type")
    )
    file_format = models.CharField(
        max_length=10,
        verbose_name=_("Format"),
        help_text=_("PDF, DOCX, TXT, etc.")
    )
    authors = models.ManyToManyField(
        get_user_model(),
        related_name='documents',
        verbose_name="Auteurs",
        blank=True,
    )

    class Meta:
        verbose_name = _("Document")
        verbose_name_plural = _("Documents")

    def get_citation(self):
        """Generate a standardized citation based on the type."""
        article = getattr(self, 'article', None)
        if article:
            return article.get_citation()
        thesis = getattr(self, 'thesis', None)
        if thesis:
            return thesis.get_citation()
        memoir = getattr(self, 'memoir', None)
        if memoir:
            return memoir.get_citation()
        author_name = self.author.get_full_name() if self.author else ''
        return f"{self.title} ({author_name}, {self.creation_date.year})"

    def get_detail_url(self):
        """Get detail URL based on document type."""
        article = getattr(self, 'article', None)
        if article:
            return reverse('resources:article_detail', kwargs={'pk': article.pk})
        thesis = getattr(self, 'thesis', None)
        if thesis:
            return reverse('resources:thesis_detail', kwargs={'pk': thesis.pk})
        memoir = getattr(self, 'memoir', None)
        if memoir:
            return reverse('resources:memoir_detail', kwargs={'pk': memoir.pk})
        return reverse('resources:document_detail', kwargs={'pk': self.pk})

class Thesis(models.Model):
    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        related_name='thesis',  # Changed from 'these' to 'thesis'
        limit_choices_to={'document_type': Document.DocumentType.THESIS}
    )
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    supervisor = models.CharField(
        max_length=100,
        verbose_name=_("Thesis Supervisor")
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.PROTECT,
        verbose_name=_("Institution")
    )
    defense_year = models.IntegerField(
        verbose_name=_("Defense Year")
    )

    def get_citation(self):
        return f"{self.document.author} ({self.defense_year}). {self.document.title}. Doctoral thesis, {self.institution}."

    def get_absolute_url(self):
        return reverse('resources:thesis_detail', kwargs={'pk': self.pk})
    

    class Meta:  
        verbose_name = _("thesis")
        verbose_name_plural = _("Theses")

class Memoir(models.Model):
    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        related_name='memoir',  # Changed from 'memoire' to 'memoir'
        limit_choices_to={'document_type': Document.DocumentType.MEMOIR}
    )
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    academic_level = models.CharField(
        max_length=50,
        choices=[
            ('bachelor', _('Bachelor')),
            ('master', _('Master')),
            ('doctorate', _('Doctorate'))
        ],
        verbose_name=_("Academic Level")
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.PROTECT,
        verbose_name=_("Institution")
    )
    defense_year = models.IntegerField(
        verbose_name=_("Defense Year")
    )

    def get_citation(self):
        field = self._meta.get_field('academic_level')
        choices_iter: Iterable[Tuple[str, str]] = cast(Iterable[Tuple[str, str]], field.choices or [])
        levels = {key: label for key, label in choices_iter}
        level_display = levels.get(self.academic_level, self.academic_level)
        return f"{self.document.author} ({self.defense_year}). {self.document.title}. Dissertation for {level_display}, {self.institution}."

    def get_absolute_url(self):
        return reverse('resources:memoir_detail', kwargs={'pk': self.pk})

    class Meta:
        verbose_name = _("memoir")
        verbose_name_plural = _("Memoirs")


class Article(models.Model):
    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        related_name='article',
        limit_choices_to={'document_type': Document.DocumentType.ARTICLE}
    )
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    doi = models.CharField(
        max_length=100,
        verbose_name=_("DOI"),
        blank=True,
        help_text=_("Digital Object Identifier (e.g., 10.1234/abcd)")
    )
    journal = models.CharField(
        max_length=200,
        verbose_name=_("Journal")
    )
    publication_date = models.DateField(
        verbose_name=_("Publication Date"),
        null=True,
        blank=True
    )

    def get_citation(self):
        year = self.publication_date.year if self.publication_date else _("Unknown year")
        doi = self.doi or _("N/A")
        return f"{self.document.author} ({year}). {self.document.title}. {self.journal}. DOI: {doi}"

    def get_absolute_url(self):
        return reverse('resources:article_detail', kwargs={'pk': self.pk})

    class Meta:
        verbose_name = _("article")
        verbose_name_plural = _("Scientific Articles")


class NLPTool(ResourceBase):
    class ToolType(models.TextChoices):
        TOKENIZATION = 'tokenization', _('Tokenization')
        STEMMING = 'stemming', _('Stemming')
        NER = 'ner', _('Named Entity Recognition')
        POS_TAGGING = 'pos_tagging', _('Part-of-Speech Tagging')
        SENTIMENT_ANALYSIS = 'sentiment_analysis', _('Sentiment Analysis')
        MACHINE_TRANSLATION = 'machine_translation', _('Machine Translation')

    class SupportedLanguages(models.TextChoices):
        ARABIC = 'ar', _('Arabic')
        ENGLISH = 'en', _('English')
        FRENCH = 'fr', _('French')
        SPANISH = 'es', _('Spanish')

    tool_type = models.CharField(
        max_length=50,
        choices=ToolType.choices,
        verbose_name=_("Tool Type"),
        help_text=_("Type of NLP tool")
    )
    version = models.CharField(
        max_length=20,
        verbose_name=_("Version"),
        help_text=_("Tool version (e.g., 1.0.0)")
    )
    documentation_link = models.URLField(
        verbose_name=_("Documentation Link"),
        blank=True,
        null=True,
        help_text=_("URL of the official documentation")
    )
    last_updated = models.DateField(
        auto_now=True,
        verbose_name=_("Last Updated")
    )
    supported_languages = models.CharField(
        max_length=255,
        verbose_name=_("Supported Languages"),
        help_text=_("Languages that this tool can process"),
        choices=SupportedLanguages.choices,
        default=SupportedLanguages.ARABIC
    )

    class Meta:
        verbose_name = _("NLP Tool")
        verbose_name_plural = _("NLP Tools")
        ordering = ['-creation_date']

    def clean(self):
        """Specific validation for NLP tools."""
        if self.tool_type == self.ToolType.MACHINE_TRANSLATION and not (self.supported_languages or '').strip():
            raise ValidationError(
                _("A machine translation tool must specify supported languages.")
            )

    def __str__(self):
        return f"{self.title} ({self.get_tool_type_display()})"
    
    def get_supported_languages_list(self):
        """Return supported languages as a list"""
        if self.supported_languages:
            return [lang.strip() for lang in str(self.supported_languages).split(',') if lang.strip()]
        return []

    def get_supported_languages_display(self):
        """Return human-readable supported languages"""
        display_values = []
        for lang in self.get_supported_languages_list():
            try:
                display_values.append(self.SupportedLanguages(lang).label)
            except ValueError:
                display_values.append(lang)
        return display_values
    
    def get_absolute_url(self):
        """Override to use the correct URL name for tools"""
        return reverse('resources:tool_detail', kwargs={'pk': self.pk})

    def get_tool_type_display(self) -> str:
        """Explicit helper for static analyzers."""
        try:
            return self.ToolType(self.tool_type).label
        except ValueError:
            return self.tool_type

class Corpus(ResourceBase):
    """
    Model representing a corpus of textual data.
    """
    size = models.IntegerField(
        verbose_name=_("Corpus Size"),
        help_text=_("Size in number of words or documents")
    )
    field = models.CharField(
        max_length=50,
        choices=FieldChoices.choices,  
        default=FieldChoices.OTHER, 
        verbose_name=_("Field of Study"),
        help_text=_("Main field of the corpus")
    )
    file_format = models.CharField(
        max_length=10,
        verbose_name=_("Format"),
        help_text=_("Format of the corpus (e.g., TXT, CSV, JSON)")
    )

    class Meta:
        db_table = 'resources_corpus' 

@receiver(post_save, sender=Course)
@receiver(post_save, sender=NLPTool)
@receiver(post_save, sender=Corpus)
@receiver(post_save, sender=Document)
def index_resource(sender, instance, **kwargs):
    try:
        registry.update(instance)
        logger.info(f"Resource {instance.title} indexed successfully")
    except KeyError as exc:
        logger.warning(
            "Elasticsearch connection missing while indexing %s: %s. "
            "Skipping search indexing for this resource.", instance.title, exc
        )
    except Exception as exc:
        logger.error(f"Error indexing resource {instance.title}: {exc}")
