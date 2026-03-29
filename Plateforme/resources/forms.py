import os

from django import forms
from django.utils.translation import gettext_lazy as _, get_language
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Submit, Row, Column, HTML
from .models import (
    Course,
    CourseComment,
    NLPTool,
    Corpus,
    Document,
    Article,
    Thesis,
    Memoir,
    ResourceBase,
    FieldChoices,
)
from accounts.models import Institution


class CourseCommentForm(forms.ModelForm):
    class Meta:
        model = CourseComment
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": "course-detail-comment-input",
                    "rows": 3,
                    "placeholder": _("Write your comment about this course..."),
                }
            )
        }


def get_active_language():
    """Get the current language, normalizing to 'ar' or 'en'."""
    lang = get_language()
    if lang and lang.startswith("ar"):
        return "ar"
    return "en"


class ResourceForm(forms.Form):
    """
    Context-aware resource form that shows language-specific fields.

    - Title and Description are shown with the current language label
    - Data is saved to the appropriate _ar or _en field based on active language
    """

    # Bilingual field mappings: generic_field -> (ar_field, en_field)
    BILINGUAL_FIELDS = {
        "title": ("title_ar", "title_en"),
        "description": ("description_ar", "description_en"),
    }

    RESOURCE_TYPES = [
        ("course", _("Course")),
        ("nlp_tool", _("NLP Tool")),
        ("corpus", _("Corpus")),
        ("article", _("Article")),
        ("thesis", _("Thesis")),
        ("memoir", _("Memoir")),
    ]

    MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB
    CORPUS_ALLOWED_EXTENSIONS = {".pdf", ".docx"}
    CORPUS_ALLOWED_MIME_TYPES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }

    # ==================== COMMON FIELDS ====================
    resource_type = forms.ChoiceField(
        choices=RESOURCE_TYPES,
        label=_("Resource Type *"),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    title_en = forms.CharField(
        label=_("Title * (English)"),
        max_length=200,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "spellcheck": "false",
                "placeholder": _("Enter the title in English"),
            }
        ),
    )
    title_ar = forms.CharField(
        label=_("Title (Arabic / العنوان)"),
        max_length=200,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "dir": "rtl",
                "spellcheck": "false",
                "placeholder": _("أدخل العنوان بالعربية"),
            }
        ),
    )
    description_en = forms.CharField(
        label=_("Description * (English)"),
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "spellcheck": "false",
                "placeholder": _("Enter the description in English"),
            }
        ),
    )
    description_ar = forms.CharField(
        label=_("Description (Arabic / الوصف)"),
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "dir": "rtl",
                "spellcheck": "false",
                "placeholder": _("أدخل الوصف بالعربية"),
            }
        ),
    )
    keywords = forms.CharField(
        label=_("Keywords"),
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text=_("Comma-separated"),
    )
    access_link = forms.URLField(
        label=_("Access Link"),
        required=False,
        widget=forms.URLInput(attrs={"class": "form-control"}),
    )
    language = forms.ChoiceField(
        choices=ResourceBase.LanguageChoices.choices,
        label=_("Language *"),
        initial=ResourceBase.LanguageChoices.ARABIC,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    # File upload field
    uploaded_file = forms.FileField(
        label=_("Upload Document"),
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '*/*'
        }),
        help_text=_("Upload any file type (max 50MB)")
    )

    # ==================== COURSE FIELDS ====================
    course_field = forms.ChoiceField(
        choices=FieldChoices.choices,
        label=_("Field of Study *"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    academic_level = forms.ChoiceField(
        choices=Course.Level.choices,
        label=_("Academic Level *"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    course_institution = forms.ModelChoiceField(
        queryset=Institution.objects.all(),
        label=_("Institution *"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    academic_year = forms.CharField(
        label=_("Academic Year * (YYYY-YYYY)"),
        max_length=9,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text=_("Format: 2023-2024"),
    )
    prerequisites = forms.CharField(
        label=_("Prerequisites"),
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": _("List prerequisites, one per line"),
            }
        ),
    )
    syllabus = forms.CharField(
        label=_("Syllabus & Curriculum"),
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 6,
                "placeholder": _("Describe the course syllabus and curriculum"),
            }
        ),
    )

    # ==================== NLP TOOL FIELDS ====================
    tool_type = forms.ChoiceField(
        choices=NLPTool.ToolType.choices,
        label=_("Tool Type *"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    tool_version = forms.CharField(
        label=_("Version *"),
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    documentation = forms.URLField(
        label=_("Documentation"),
        required=False,
        widget=forms.URLInput(attrs={"class": "form-control"}),
    )
    supported_languages = forms.MultipleChoiceField(
        choices=[
            ("ar", _("Arabic")),
            ("en", _("English")),
            ("fr", _("French")),
            ("es", _("Spanish")),
        ],
        label=_("Supported Languages *"),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "list-unstyled"}),
        help_text=_("Select all languages that this tool can process"),
    )

    # ==================== CORPUS FIELDS ====================
    corpus_field = forms.ChoiceField(
        choices=FieldChoices.choices,
        label=_("Field of Study *"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    # ==================== DOCUMENT COMMON FIELDS ====================

    # ==================== ARTICLE FIELDS ====================
    doi = forms.CharField(
        label=_("DOI"),
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text=_("e.g., 10.1234/abcd"),
    )
    journal = forms.CharField(
        label=_("Journal *"),
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    publication_date = forms.DateField(
        label=_("Publication Date *"),
        required=False,
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "type": "text",
                "placeholder": "dd/mm/yyyy",
            },
            format="%Y-%m-%d",
        ),
    )

    # ==================== THESIS FIELDS ====================
    supervisor = forms.CharField(
        label=_("Supervisor *"),
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    thesis_institution = forms.ModelChoiceField(
        queryset=Institution.objects.all(),
        label=_("Institution *"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    defense_year = forms.IntegerField(
        label=_("Defense Year *"),
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    # ==================== MEMOIR FIELDS ====================
    memoir_level = forms.ChoiceField(
        choices=Memoir._meta.get_field("academic_level").choices,
        label=_("Academic Level *"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    memoir_institution = forms.ModelChoiceField(
        queryset=Institution.objects.all(),
        label=_("Institution *"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    memoir_defense_year = forms.IntegerField(
        label=_("Defense Year *"),
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        self.is_update = kwargs.pop("is_update", False)
        # Pop instance since forms.Form doesn't accept it (unlike ModelForm)
        instance = kwargs.pop("instance", None)

        if instance and hasattr(instance, "supported_languages"):
            if "initial" not in kwargs:
                kwargs["initial"] = {}
            kwargs["initial"]["supported_languages"] = self.prepare_supported_languages(
                instance.supported_languages
            )

        # Pre-populate bilingual fields from instance
        if instance and "initial" not in kwargs:
            kwargs["initial"] = {}
        if instance:
            for generic_field, (ar_field, en_field) in self.BILINGUAL_FIELDS.items():
                ar_value = getattr(instance, ar_field, "") or ""
                en_value = (
                    getattr(instance, en_field, "")
                    or getattr(instance, generic_field, "")
                    or ""
                )
                kwargs["initial"][f"{generic_field}_ar"] = ar_value
                kwargs["initial"][f"{generic_field}_en"] = en_value

        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_class = "needs-validation"
        self.helper.attrs = {"novalidate": ""}

        if self.is_update:
            self.fields["resource_type"].disabled = True

        resource_type = self.initial.get("resource_type", "course")

        if "supported_languages" in self.fields:
            self.fields["supported_languages"].widget.attrs.update(
                {"class": "checkbox-grid"}
            )

        self.helper.layout = self._build_layout(resource_type)

    def _build_layout(self, resource_type):
        layout = Layout(
            Fieldset(
                _("Basic Information"),
                Row(
                    Column("resource_type", css_class="col-md-6"),
                    Column("language", css_class="col-md-6"),
                ),
                "title_en",
                "title_ar",
                "description_en",
                "description_ar",
                Row(Column("keywords", css_class="col-md-12")),
                "access_link",
                HTML("""<hr class="my-4">"""),
            )
        )

        if resource_type == "course":
            layout.append(self._create_course_fields())
        elif resource_type == "nlp_tool":
            layout.append(self._create_tool_fields())
        elif resource_type == "corpus":
            layout.append(self._create_corpus_fields())
        elif resource_type == "article":
            layout.append(self._create_article_fields())
        elif resource_type == "thesis":
            layout.append(self._create_thesis_fields())
        elif resource_type == "memoir":
            layout.append(self._create_memoir_fields())

        layout.append(
            Submit("submit", _("Save"), css_class="btn-primary w-100 py-2 mt-3")
        )
        return layout

    def _create_course_fields(self):
        return Fieldset(
            _("Course Details"),
            Row(
                Column("course_field", css_class="col-md-6"),
                Column("academic_level", css_class="col-md-6"),
            ),
            Row(
                Column("course_institution", css_class="col-md-6"),
                Column("academic_year", css_class="col-md-6"),
            ),
            "prerequisites",
            "syllabus",
        )

    def _create_tool_fields(self):
        return Fieldset(
            _("Tool Details"),
            Row(
                Column("tool_type", css_class="col-md-6"),
                Column("tool_version", css_class="col-md-6"),
            ),
            Row(
                Column("documentation", css_class="col-md-6"),
                Fieldset(
                    _("Supported Languages"),
                    "supported_languages",
                    css_class="border p-3 mt-3",
                ),
            ),
        )

    def _create_corpus_fields(self):
        return Fieldset(
            _("Corpus Details"), Row(Column("corpus_field", css_class="col-md-12"))
        )

    def _create_article_fields(self):
        return Fieldset(
            _("Article Details"),
            Row(
                Column("journal", css_class="col-md-6"),
                Column("publication_date", css_class="col-md-6"),
            ),
            "doi",
        )

    def _create_thesis_fields(self):
        return Fieldset(
            _("Thesis Details"),
            Row(
                Column("supervisor", css_class="col-md-6"),
                Column("thesis_institution", css_class="col-md-6"),
            ),
            "defense_year",
        )

    def _create_memoir_fields(self):
        return Fieldset(
            _("Memoir Details"),
            Row(
                Column("memoir_level", css_class="col-md-6"),
                Column("memoir_institution", css_class="col-md-6"),
            ),
            "memoir_defense_year",
        )

    def clean_supported_languages(self):
        languages = self.cleaned_data.get("supported_languages")
        if not languages and self.cleaned_data.get("resource_type") == "nlp_tool":
            raise forms.ValidationError(
                _("Please select at least one supported language")
            )
        return ",".join(languages) if languages else ""

    def prepare_supported_languages(self, value):
        if value:
            return value.split(",")
        return []

    def clean(self):
        import logging

        logger = logging.getLogger(__name__)

        cleaned_data = super().clean()
        resource_type = cleaned_data.get("resource_type")
        title_en = (cleaned_data.get("title_en") or "").strip()
        title_ar = (cleaned_data.get("title_ar") or "").strip()
        description_en = (cleaned_data.get("description_en") or "").strip()
        description_ar = (cleaned_data.get("description_ar") or "").strip()

        logger.info(
            f"[RESOURCE_FORM] Validating form for resource_type: {resource_type}"
        )
        logger.info(f"[RESOURCE_FORM] User: {self.user.email if self.user else 'None'}")

        required_fields = []
        if resource_type == "course":
            required_fields = [
                "course_field",
                "academic_level",
                "course_institution",
                "academic_year",
            ]
        elif resource_type == "nlp_tool":
            required_fields = ["tool_type", "tool_version"]
        elif resource_type == "corpus":
            required_fields = ["corpus_field"]
        elif resource_type == "article":
            required_fields = ["journal", "publication_date"]
        elif resource_type == "thesis":
            required_fields = [
                "supervisor",
                "thesis_institution",
                "defense_year",
            ]
        elif resource_type == "memoir":
            required_fields = [
                "memoir_level",
                "memoir_institution",
                "memoir_defense_year",
            ]

        logger.info(
            f"[RESOURCE_FORM] Required fields for {resource_type}: {required_fields}"
        )

        if not title_en and not title_ar:
            message = _("Please provide a title in English or Arabic")
            self.add_error("title_en", message)
            self.add_error("title_ar", message)

        if not description_en and not description_ar:
            message = _("Please provide a description in English or Arabic")
            self.add_error("description_en", message)
            self.add_error("description_ar", message)

        for field in required_fields:
            if not cleaned_data.get(field):
                logger.warning(f"[RESOURCE_FORM] Missing required field: {field}")
                self.add_error(
                    field, _("This field is required for this resource type")
                )

        if resource_type == "course" and cleaned_data.get("academic_year"):
            try:
                start, end = map(int, cleaned_data["academic_year"].split("-"))
                if end != start + 1:
                    logger.warning(
                        f"[RESOURCE_FORM] Invalid academic year: {cleaned_data['academic_year']}"
                    )
                    self.add_error(
                        "academic_year", _("End year must be start year + 1")
                    )
            except (ValueError, AttributeError):
                logger.warning(
                    f"[RESOURCE_FORM] Invalid academic year format: {cleaned_data.get('academic_year')}"
                )
                self.add_error("academic_year", _("Invalid format (ex: 2023-2024)"))

        if resource_type == "course":
            field_value = cleaned_data.get("course_field")
            if field_value and field_value not in dict(FieldChoices.choices):
                logger.warning(f"[RESOURCE_FORM] Invalid course field: {field_value}")
                self.add_error("course_field", _("Invalid field choice"))
        elif resource_type == "corpus":
            field_value = cleaned_data.get("corpus_field")
            if field_value and field_value not in dict(FieldChoices.choices):
                logger.warning(f"[RESOURCE_FORM] Invalid corpus field: {field_value}")
                self.add_error("corpus_field", _("Invalid field choice"))

        language_value = cleaned_data.get("language")
        if not language_value:
            logger.warning("[RESOURCE_FORM] Language field is missing")
            self.add_error("language", _("Language is required"))
        elif language_value not in dict(ResourceBase.LanguageChoices.choices):
            logger.warning(f"[RESOURCE_FORM] Invalid language value: {language_value}")
            self.add_error("language", _("Invalid language choice"))

        if self.errors:
            logger.warning(
                f"[RESOURCE_FORM] Form validation failed with errors: {self.errors}"
            )
        else:
            logger.info("[RESOURCE_FORM] ✓ Form validation passed")

        return cleaned_data

    def clean_uploaded_file(self):
        """Validate uploaded file size."""
        uploaded_file = self.cleaned_data.get('uploaded_file')
        if uploaded_file:
            # Check file size (50MB max)
            max_size = 50 * 1024 * 1024  # 50MB in bytes
            if uploaded_file.size > max_size:
                raise forms.ValidationError(_("File is too large. Maximum size is 50MB."))
        return uploaded_file

    def save(self, instance=None):
        import logging

        logger = logging.getLogger(__name__)

        resource_type = self.cleaned_data["resource_type"]
        logger.info(
            f"[RESOURCE_CREATE] Starting save for resource type: {resource_type}, user: {self.user.email if self.user else 'None'}"
        )

        title_en = (self.cleaned_data.get("title_en") or "").strip()
        title_ar = (self.cleaned_data.get("title_ar") or "").strip()
        desc_en = (self.cleaned_data.get("description_en") or "").strip()
        desc_ar = (self.cleaned_data.get("description_ar") or "").strip()
        legacy_title = title_en or title_ar
        legacy_description = desc_en or desc_ar

        common_data = {
            "title": legacy_title,
            "title_en": title_en,
            "title_ar": title_ar,
            "description": legacy_description,
            "description_en": desc_en,
            "description_ar": desc_ar,
            "author": self.user,
            "keywords": self.cleaned_data["keywords"],
            "access_link": self.cleaned_data["access_link"] or None,
            "language": self.cleaned_data["language"],
            "uploaded_file": self.cleaned_data.get("uploaded_file"),
            # CRITICAL: Explicitly set approval fields
            "approval_status": "pending",
            "is_approved": False,  # Legacy field - must be set for database compatibility
            "rejection_reason": "",  # Initialize to empty string to avoid NOT NULL errors
        }

        logger.info(
            f"[RESOURCE_CREATE] Common data prepared: author={self.user.email if self.user else 'None'}, approval_status=pending"
        )

        if self.is_update and instance:
            instance.title = legacy_title
            instance.title_en = title_en
            instance.title_ar = title_ar
            instance.description = legacy_description
            instance.description_en = desc_en
            instance.description_ar = desc_ar
            instance.keywords = self.cleaned_data["keywords"]
            instance.access_link = self.cleaned_data["access_link"] or None
            instance.language = self.cleaned_data["language"]
            # Handle file upload (only update if a new file is provided)
            uploaded_file = self.cleaned_data.get("uploaded_file")
            if uploaded_file:
                instance.uploaded_file = uploaded_file
            instance.save()

            if resource_type == "course":
                instance.field = self.cleaned_data["course_field"]
                instance.academic_level = self.cleaned_data["academic_level"]
                instance.institution = self.cleaned_data["course_institution"]
                instance.academic_year = self.cleaned_data["academic_year"]
                instance.prerequisites = self.cleaned_data.get("prerequisites", "")
                instance.syllabus = self.cleaned_data.get("syllabus", "")
                instance.save()
            elif resource_type == "nlp_tool":
                instance.tool_type = self.cleaned_data["tool_type"]
                instance.version = self.cleaned_data["tool_version"]
                instance.documentation_link = self.cleaned_data["documentation"]
                instance.supported_languages = self.cleaned_data["supported_languages"]
                instance.save()
            elif resource_type == "corpus":
                instance.field = self.cleaned_data["corpus_field"]
                instance.save()
            elif resource_type == "article":
                instance.document_type = Document.DocumentType.ARTICLE
                if hasattr(instance, "file_format") and "document_format" in self.cleaned_data:
                    instance.file_format = self.cleaned_data["document_format"]
                instance.save()
                article = instance.article
                article.doi = self.cleaned_data.get("doi", "")
                article.journal = self.cleaned_data["journal"]
                article.publication_date = self.cleaned_data["publication_date"]
                article.save()
            elif resource_type == "thesis":
                instance.document_type = Document.DocumentType.THESIS
                if hasattr(instance, "file_format") and "document_format" in self.cleaned_data:
                    instance.file_format = self.cleaned_data["document_format"]
                instance.save()
                thesis = instance.thesis
                thesis.supervisor = self.cleaned_data["supervisor"]
                thesis.institution = self.cleaned_data["thesis_institution"]
                thesis.defense_year = self.cleaned_data["defense_year"]
                thesis.save()
            elif resource_type == "memoir":
                instance.document_type = Document.DocumentType.MEMOIR
                if hasattr(instance, "file_format") and "document_format" in self.cleaned_data:
                    instance.file_format = self.cleaned_data["document_format"]
                instance.save()
                memoir = instance.memoir
                memoir.academic_level = self.cleaned_data["memoir_level"]
                memoir.institution = self.cleaned_data["memoir_institution"]
                memoir.defense_year = self.cleaned_data["memoir_defense_year"]
                memoir.save()
            return instance
        else:
            try:
                logger.info(f"[RESOURCE_CREATE] Creating new {resource_type}")

                if resource_type == "course":
                    course = Course.objects.create(
                        **common_data,
                        field=self.cleaned_data["course_field"],
                        academic_level=self.cleaned_data["academic_level"],
                        teacher=self.user,
                        institution=self.cleaned_data["course_institution"],
                        academic_year=self.cleaned_data["academic_year"],
                        prerequisites=self.cleaned_data.get("prerequisites", ""),
                        syllabus=self.cleaned_data.get("syllabus", ""),
                    )
                    logger.info(
                        f"[RESOURCE_CREATE] ✓ Course created successfully (ID: {course.id}, Status: {course.approval_status})"
                    )
                    return course

                elif resource_type == "nlp_tool":
                    tool = NLPTool.objects.create(
                        **common_data,
                        tool_type=self.cleaned_data["tool_type"],
                        version=self.cleaned_data["tool_version"],
                        documentation_link=self.cleaned_data["documentation"],
                        supported_languages=self.cleaned_data["supported_languages"],
                    )
                    logger.info(
                        f"[RESOURCE_CREATE] ✓ NLP Tool created successfully (ID: {tool.id}, Status: {tool.approval_status})"
                    )
                    return tool

                elif resource_type == "corpus":
                    corpus = Corpus.objects.create(
                        **common_data, field=self.cleaned_data["corpus_field"]
                    )
                    logger.info(
                        f"[RESOURCE_CREATE] ✓ Corpus created successfully (ID: {corpus.id}, Status: {corpus.approval_status})"
                    )
                    return corpus

                elif resource_type == "article":
                    doc_create_kwargs = {
                        **common_data,
                        "document_type": Document.DocumentType.ARTICLE,
                    }
                    if (
                        hasattr(Document, "file_format")
                        and "document_format" in self.cleaned_data
                    ):
                        doc_create_kwargs["file_format"] = self.cleaned_data["document_format"]
                    doc = Document.objects.create(**doc_create_kwargs)
                    Article.objects.create(
                        document=doc,
                        doi=self.cleaned_data.get("doi", ""),
                        journal=self.cleaned_data["journal"],
                        publication_date=self.cleaned_data["publication_date"],
                    )
                    logger.info(
                        f"[RESOURCE_CREATE] ✓ Article created successfully (ID: {doc.id}, Status: {doc.approval_status})"
                    )
                    return doc

                elif resource_type == "thesis":
                    doc_create_kwargs = {
                        **common_data,
                        "document_type": Document.DocumentType.THESIS,
                    }
                    if (
                        hasattr(Document, "file_format")
                        and "document_format" in self.cleaned_data
                    ):
                        doc_create_kwargs["file_format"] = self.cleaned_data["document_format"]
                    doc = Document.objects.create(**doc_create_kwargs)
                    Thesis.objects.create(
                        document=doc,
                        supervisor=self.cleaned_data["supervisor"],
                        institution=self.cleaned_data["thesis_institution"],
                        defense_year=self.cleaned_data["defense_year"],
                    )
                    logger.info(
                        f"[RESOURCE_CREATE] ✓ Thesis created successfully (ID: {doc.id}, Status: {doc.approval_status})"
                    )
                    return doc

                elif resource_type == "memoir":
                    doc_create_kwargs = {
                        **common_data,
                        "document_type": Document.DocumentType.MEMOIR,
                    }
                    if (
                        hasattr(Document, "file_format")
                        and "document_format" in self.cleaned_data
                    ):
                        doc_create_kwargs["file_format"] = self.cleaned_data["document_format"]
                    doc = Document.objects.create(**doc_create_kwargs)
                    Memoir.objects.create(
                        document=doc,
                        academic_level=self.cleaned_data["memoir_level"],
                        institution=self.cleaned_data["memoir_institution"],
                        defense_year=self.cleaned_data["memoir_defense_year"],
                    )
                    logger.info(
                        f"[RESOURCE_CREATE] ✓ Memoir created successfully (ID: {doc.id}, Status: {doc.approval_status})"
                    )
                    return doc

                else:
                    logger.error(
                        f"[RESOURCE_CREATE] ✗ Unknown resource type: {resource_type}"
                    )
                    raise ValueError(f"Unknown resource type: {resource_type}")

            except Exception as e:
                logger.error(
                    f"[RESOURCE_CREATE] ✗ Error creating {resource_type}: {str(e)}",
                    exc_info=True,
                )
                import traceback

                logger.error(
                    f"[RESOURCE_CREATE] Stack trace:\n{traceback.format_exc()}"
                )
                raise
