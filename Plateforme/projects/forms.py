from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import get_language, gettext_lazy as _

from institutions.models import Country, Institution

from .models import Project, ProjectChatMessage, PROJECT_CHAT_URL_RE, validate_project_chat_file


def get_active_language():
    """Get the current language, normalizing to 'ar' or 'en'."""
    lang = get_language()
    if lang and lang.startswith('ar'):
        return 'ar'
    return 'en'


class ProjectForm(forms.ModelForm):
    """
    Context-aware project form that shows language-specific fields.
    
    - Title and Description are shown with the current language label
    - Data is saved to the appropriate _ar or _en field based on active language
    """
    
    # Bilingual field mappings: generic_field -> (ar_field, en_field)
    BILINGUAL_FIELDS = {
        'title': ('title_ar', 'title_en'),
        'description': ('description_ar', 'description_en'),
    }

    institution = forms.ChoiceField(required=True, label=_("Institution"))
    institution_name_ar_custom = forms.CharField(
        required=False,
        label=_("Institution Name (Arabic)"),
        widget=forms.TextInput(
            attrs={
                "placeholder": _("Type the institution name in Arabic"),
            }
        ),
    )
    institution_name_en_custom = forms.CharField(
        required=False,
        label=_("Institution Name (English)"),
        widget=forms.TextInput(
            attrs={
                "placeholder": _("Type the institution name in English"),
            }
        ),
    )
    
    class Meta:
        model = Project
        fields = ['title', 'institution', 'description', 
                  'status', 'date_start', 'date_end', 'attachment']
        widgets = {
            'date_start': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'date_end': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'description': forms.Textarea(attrs={'rows': 4}),
            'objectives': forms.Textarea(attrs={'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop("user", None)
        instance = kwargs.get('instance', None)
        
        # Pre-populate from bilingual fields based on current language
        if instance:
            if 'initial' not in kwargs:
                kwargs['initial'] = {}
            lang = get_active_language()
            for generic_field, (ar_field, en_field) in self.BILINGUAL_FIELDS.items():
                target_field = ar_field if lang == 'ar' else en_field
                value = getattr(instance, target_field, '') or getattr(instance, generic_field, '')
                if value:
                    kwargs['initial'][generic_field] = value
        
        super().__init__(*args, **kwargs)
        self._setup_institution_choices(instance)
        self._setup_bilingual_labels()

    def _setup_institution_choices(self, instance):
        current_lang = get_active_language()
        institution_choices = [("", _("Select institution"))]
        institutions = Institution.objects.all().order_by("name_ar", "name_en", "name")

        for institution in institutions:
            if current_lang == "ar":
                label = institution.name_ar or institution.name_en or institution.name
            else:
                label = institution.name_en or institution.name_ar or institution.name
            institution_choices.append((str(institution.pk), label))

        institution_choices.append(("other", _("Other")))
        self.fields["institution"].choices = institution_choices

        if instance and instance.pk and instance.institution_id and not self.is_bound:
            self.initial["institution"] = str(instance.institution_id)
    
    def _setup_bilingual_labels(self):
        """Set context-aware labels for bilingual fields."""
        lang = get_active_language()
        
        if lang == 'ar':
            self.fields['title'].label = _("Title (Arabic)")
            self.fields['title'].help_text = _("Enter the project title in Arabic")
            self.fields['description'].label = _("Description (Arabic)")
            self.fields['description'].help_text = _("Enter the description in Arabic")
        else:
            self.fields['title'].label = _("Title (English)")
            self.fields['title'].help_text = _("Enter the project title in English")
            self.fields['description'].label = _("Description (English)")
            self.fields['description'].help_text = _("Enter the description in English")

    def clean(self):
        cleaned_data = super().clean()
        institution_value = (cleaned_data.get("institution") or "").strip()
        name_ar = (cleaned_data.get("institution_name_ar_custom") or "").strip()
        name_en = (cleaned_data.get("institution_name_en_custom") or "").strip()

        if institution_value == "other":
            if not name_ar:
                self.add_error(
                    "institution_name_ar_custom",
                    _("Enter the institution name in Arabic."),
                )
            if not name_en:
                self.add_error(
                    "institution_name_en_custom",
                    _("Enter the institution name in English."),
                )
        elif institution_value:
            if not Institution.objects.filter(pk=institution_value).exists():
                self.add_error("institution", _("Select a valid institution."))

        return cleaned_data

    def _get_or_create_custom_institution(self):
        name_ar = (self.cleaned_data.get("institution_name_ar_custom") or "").strip()
        name_en = (self.cleaned_data.get("institution_name_en_custom") or "").strip()

        institution = Institution.objects.filter(
            name_ar__iexact=name_ar,
            name_en__iexact=name_en,
        ).first()
        if institution:
            return institution

        country = (
            Country.objects.filter(code__iexact="DZ").first()
            or Country.objects.order_by("name_en").first()
        )
        if not country:
            raise ValidationError(_("No country is available to create a custom institution."))

        return Institution.objects.create(
            name=name_en or name_ar,
            name_ar=name_ar,
            name_en=name_en,
            type="Other",
            country=country,
            city="Unknown",
            city_ar="غير محدد",
            city_en="Unknown",
            created_by=self.current_user if getattr(self.current_user, "is_authenticated", False) else None,
        )

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Save to bilingual fields based on active language
        lang = get_active_language()
        for generic_field, (ar_field, en_field) in self.BILINGUAL_FIELDS.items():
            target_field = ar_field if lang == 'ar' else en_field
            value = self.cleaned_data.get(generic_field, '')
            # Set both the language-specific field AND the main field
            setattr(instance, target_field, value)
            setattr(instance, generic_field, value)

        institution_value = (self.cleaned_data.get("institution") or "").strip()
        if institution_value == "other":
            instance.institution = self._get_or_create_custom_institution()
        else:
            instance.institution = Institution.objects.get(pk=institution_value)
        
        if commit:
            instance.save()
        return instance

    def clean_attachment(self):
        """Validate project attachment: max 5MB, PDF/Word only."""
        attachment = self.cleaned_data.get('attachment')
        if attachment:
            # File size validation (5MB max)
            max_size = 5 * 1024 * 1024
            if attachment.size > max_size:
                raise forms.ValidationError(
                    _("File size must be less than 5MB. Current size: %(size).1fMB.") %
                    {'size': attachment.size / (1024 * 1024)}
                )
            
            # File type validation (PDF and Word only)
            allowed_extensions = ['pdf', 'doc', 'docx']
            file_ext = attachment.name.rsplit('.', 1)[-1].lower() if '.' in attachment.name else ''
            if file_ext not in allowed_extensions:
                raise forms.ValidationError(
                    _("Only PDF and Word documents are allowed. Allowed formats: %(formats)s.") %
                    {'formats': ', '.join(allowed_extensions)}
                )
            
            # MIME type validation
            allowed_mimes = [
                'application/pdf',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            ]
            if hasattr(attachment, 'content_type') and attachment.content_type not in allowed_mimes:
                raise forms.ValidationError(
                    _("Invalid file type. Only PDF and Word documents are allowed.")
                )
        return attachment


class ProjectChatMessageForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        lang = get_active_language()
        if lang == "ar":
            self.fields["content"].widget.attrs.update(
                {
                    # Fallback literal to avoid missing compiled translations
                    "placeholder": "اكتب رسالة...",
                    "dir": "rtl",
                    "style": "text-align: right;",
                }
            )
        else:
            self.fields["content"].widget.attrs.update(
                {
                    "placeholder": _("Write a message..."),
                    "dir": "ltr",
                    "style": "text-align: left;",
                }
            )

    class Meta:
        model = ProjectChatMessage
        fields = ["content", "file_path"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "rows": 2,
                    "placeholder": _("Write a message..."),
                    "class": "pc-input",
                }
            ),
            "file_path": forms.ClearableFileInput(
                attrs={
                    "class": "pc-file-input",
                    "accept": ".pdf,.jpg,.jpeg,.png,.docx,.zip",
                }
            ),
        }

    def clean_file_path(self):
        file_obj = self.cleaned_data.get("file_path")
        if file_obj:
            validate_project_chat_file(file_obj)
        return file_obj

    def clean(self):
        cleaned = super().clean()
        content = (cleaned.get("content") or "").strip()
        file_obj = cleaned.get("file_path")

        if not content and not file_obj:
            raise forms.ValidationError(_("Enter a message or attach a file."))

        if file_obj:
            self.instance.message_type = ProjectChatMessage.MessageType.FILE
        elif PROJECT_CHAT_URL_RE.search(content):
            self.instance.message_type = ProjectChatMessage.MessageType.LINK
        else:
            self.instance.message_type = ProjectChatMessage.MessageType.TEXT

        return cleaned
