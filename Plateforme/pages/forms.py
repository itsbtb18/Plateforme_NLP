
from django import forms
import json
import re
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from accounts.models import CustomUser
from pages.security import ROLE_ADMIN, ROLE_MODERATOR, ROLE_USER, sanitize_admin_text
from .models import ContactMessage, NewsPublication




class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Your full name'),
                'required': True
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': _('Your email address'),
                'required': True
            }),
            'subject': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': _('Your message...'),
                'required': True
            }),
        }
        labels = {
            'name': _('Full Name'),
            'email': _('Email Address'),
            'subject': _('Subject'),
            'message': _('Message'),
        }

class AdminResponseForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['admin_response', 'status']
        widgets = {
            'admin_response': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Your response to the user...'),
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
        labels = {
            'admin_response': _('Response'),
            'status': _('Status'),
        }


class AdminUserCreateForm(forms.Form):
    ROLE_CHOICES = [
        (ROLE_USER, _("User")),
        (ROLE_MODERATOR, _("Moderator")),
        (ROLE_ADMIN, _("Admin")),
    ]
    STATUS_CHOICES = list(CustomUser.STATUS_CHOICES)

    full_name = forms.CharField(max_length=255, required=True)
    email = forms.EmailField(required=True)
    institution = forms.CharField(max_length=255, required=False)
    password1 = forms.CharField(widget=forms.PasswordInput(), required=True)
    password2 = forms.CharField(widget=forms.PasswordInput(), required=True)
    status = forms.ChoiceField(choices=STATUS_CHOICES, required=True)
    role = forms.ChoiceField(choices=ROLE_CHOICES, required=True, initial=ROLE_USER)

    def clean_full_name(self):
        return sanitize_admin_text(self.cleaned_data.get("full_name"), max_len=255)

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        validate_email(email)
        User = get_user_model()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("This email is already registered."))
        return email

    def clean_password1(self):
        password = self.cleaned_data.get("password1") or ""
        try:
            validate_password(password)
        except ValidationError as exc:
            raise forms.ValidationError(exc.messages)
        return password

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password1") != cleaned.get("password2"):
            self.add_error("password2", _("Passwords do not match."))
        return cleaned

    def save(self, *, created_by):
        User = get_user_model()
        institution_name = sanitize_admin_text(self.cleaned_data.get("institution"), max_len=255)
        role = self.cleaned_data["role"]
        status = self.cleaned_data["status"]

        institution_obj = None
        if institution_name:
            try:
                from institutions.models import Institution

                institution_obj = Institution.objects.filter(name__iexact=institution_name).first()
            except Exception:
                institution_obj = None

        full_name = self.cleaned_data["full_name"]
        email = self.cleaned_data["email"]
        password = self.cleaned_data["password1"]

        user = User.objects.create_user(
            email=email,
            password=password,
            full_name=full_name,
            full_name_en=full_name,
            full_name_ar=full_name,
            institution=institution_obj,
        )

        user.status = status
        user.is_active = status != "blocked"
        user.is_verified = status == "active"
        user.is_email_verified = True
        user.is_staff = role in {ROLE_ADMIN, ROLE_MODERATOR}
        user.is_superuser = role == ROLE_ADMIN
        user.save(
            update_fields=[
                "status",
                "is_active",
                "is_verified",
                "is_email_verified",
                "is_staff",
                "is_superuser",
            ]
        )

        moderator_group, _ = Group.objects.get_or_create(name="moderator")
        if role == ROLE_MODERATOR:
            user.groups.add(moderator_group)
        else:
            user.groups.remove(moderator_group)

        return user


class AdminNewsPublicationForm(forms.ModelForm):
    DOI_PATTERN = re.compile(r"^10\.\d{4,}/\S+$")

    authors_input = forms.CharField(required=False, widget=forms.HiddenInput())
    nlp_tasks_input = forms.CharField(required=False, widget=forms.HiddenInput())
    languages_input = forms.CharField(required=False, widget=forms.HiddenInput())
    keywords_input = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = NewsPublication
        fields = [
            "type",
            "title",
            "abstract",
            "affiliations",
            "year",
            "venue",
            "doi",
            "pdf_url",
            "github_url",
            "dataset_url",
            "demo_url",
            "cover_image",
            "pdf_file",
        ]
        widgets = {
            "type": forms.Select(),
            "title": forms.TextInput(attrs={"maxlength": 120}),
            "abstract": forms.Textarea(attrs={"maxlength": 1500, "rows": 8}),
            "affiliations": forms.TextInput(),
            "year": forms.NumberInput(),
            "venue": forms.TextInput(),
            "doi": forms.TextInput(),
            "pdf_url": forms.URLInput(),
            "github_url": forms.URLInput(),
            "dataset_url": forms.URLInput(),
            "demo_url": forms.URLInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get("instance") or self.instance
        if instance and instance.pk:
            self.fields["authors_input"].initial = json.dumps(instance.authors or [])
            self.fields["nlp_tasks_input"].initial = json.dumps(instance.nlp_tasks or [])
            self.fields["languages_input"].initial = json.dumps(instance.languages or [])
            self.fields["keywords_input"].initial = json.dumps(instance.keywords or [])

    def _parse_json_list(self, field_name):
        raw_value = self.cleaned_data.get(field_name) or "[]"
        try:
            values = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(_("Invalid tag data.")) from exc

        if not isinstance(values, list):
            raise forms.ValidationError(_("Invalid tag data."))

        clean_values = []
        for value in values:
            cleaned = sanitize_admin_text(value, max_len=80)
            if cleaned and cleaned not in clean_values:
                clean_values.append(cleaned)
        return clean_values

    def clean_title(self):
        return sanitize_admin_text(self.cleaned_data.get("title"), max_len=120)

    def clean_abstract(self):
        abstract = sanitize_admin_text(self.cleaned_data.get("abstract"), max_len=1500)
        if len(abstract) < 150:
            raise forms.ValidationError(_("Abstract must contain at least 150 characters."))
        return abstract

    def clean_affiliations(self):
        return sanitize_admin_text(self.cleaned_data.get("affiliations"), max_len=255)

    def clean_venue(self):
        return sanitize_admin_text(self.cleaned_data.get("venue"), max_len=255)

    def clean_doi(self):
        doi = sanitize_admin_text(self.cleaned_data.get("doi"), max_len=255)
        if doi and not self.DOI_PATTERN.match(doi):
            raise forms.ValidationError(_("Please enter a valid DOI."))
        return doi or None

    def clean_cover_image(self):
        cover = self.cleaned_data.get("cover_image")
        if cover and cover.size > 4 * 1024 * 1024:
            raise forms.ValidationError(_("Cover image must be 4MB or less."))
        return cover

    def clean_pdf_file(self):
        pdf_file = self.cleaned_data.get("pdf_file")
        if pdf_file and pdf_file.size > 20 * 1024 * 1024:
            raise forms.ValidationError(_("PDF file must be 20MB or less."))
        return pdf_file

    def clean(self):
        cleaned = super().clean()
        cleaned["authors"] = self._parse_json_list("authors_input")
        cleaned["nlp_tasks"] = self._parse_json_list("nlp_tasks_input")
        cleaned["languages"] = self._parse_json_list("languages_input")
        cleaned["keywords"] = self._parse_json_list("keywords_input")

        if not cleaned["authors"]:
            self.add_error("authors_input", _("Please add at least one author."))
        if not cleaned["nlp_tasks"]:
            self.add_error("nlp_tasks_input", _("Please add at least one NLP task."))
        return cleaned

    def save(self, commit=True, *, created_by=None, publish_status=None):
        instance = super().save(commit=False)
        instance.authors = self.cleaned_data["authors"]
        instance.nlp_tasks = self.cleaned_data["nlp_tasks"]
        instance.languages = self.cleaned_data["languages"]
        instance.keywords = self.cleaned_data["keywords"]

        valid_statuses = {
            NewsPublication.STATUS_DRAFT,
            NewsPublication.STATUS_PUBLISHED,
        }
        if publish_status in valid_statuses:
            instance.status = publish_status
        else:
            instance.status = NewsPublication.STATUS_PUBLISHED

        if created_by is not None and not instance.pk:
            instance.created_by = created_by
        if commit:
            instance.save()
        return instance
