
from django import forms
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from accounts.models import CustomUser
from pages.security import ROLE_ADMIN, ROLE_MODERATOR, ROLE_USER, sanitize_admin_text
from .models import ContactMessage




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
