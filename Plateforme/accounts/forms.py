from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.translation import gettext_lazy as _
from .models import CustomUser

ALLOWED_EMAIL_DOMAINS = ["usthb.dz", "gmail.com"]


class CustomUserCreationForm(UserCreationForm):
    speciality = forms.ChoiceField(
        choices=CustomUser.SPECIALITY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
        label=_("Field of Specialization in AI")
    )

    class Meta:
        model = CustomUser
        fields = ['full_name', 'email', 'institution', 'speciality']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add translations to form field labels
        self.fields['full_name'].label = _("Full name")
        self.fields['email'].label = _("Email address")
        self.fields['institution'].label = _("Institution")
        self.fields['password1'].label = _("Password")
        self.fields['password2'].label = _("Confirm password")
        
        # Add help texts with translations
        self.fields['password1'].help_text = _("Password must contain at least 8 characters")
        self.fields['password2'].help_text = _("Enter the same password for verification")

    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower()
        domain = email.split('@')[-1]
        if domain not in ALLOWED_EMAIL_DOMAINS:
            raise forms.ValidationError(
                _("Your email must end with %(domain)s") % {'domain': ALLOWED_EMAIL_DOMAINS[0]}
            )
        return email

    def try_save(self, request):
        """
        Custom method expected by the modified SignupView
        """
        user = super().save(commit=False)
        user.full_name = self.cleaned_data.get('full_name')
        user.institution = self.cleaned_data.get('institution')
        user.speciality = self.cleaned_data.get('speciality')
        user.save()
        return user, True

    def save(self, commit=True):
        """
        Standard method expected by django-allauth
        """
        user, _ = self.try_save(None)
        return user


class CustomUserChangeForm(UserChangeForm):
    speciality = forms.ChoiceField(
        choices=CustomUser.SPECIALITY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
        label=_("Field of Specialization in AI")
    )
    
    linkedin_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://linkedin.com/in/your-profile'
        }),
        label=_("LinkedIn")
    )
    
    twitter_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://twitter.com/your-account'
        }),
        label=_("Twitter")
    )
    
    facebook_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://facebook.com/your-profile'
        }),
        label=_("Facebook")
    )

    class Meta:
        model = CustomUser
        fields = [
            'full_name', 'email', 'institution', 'bio', 'avatar',
            'speciality', 'linkedin_url', 'twitter_url', 'facebook_url'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add translations to form field labels
        self.fields['full_name'].label = _("Full name")
        self.fields['email'].label = _("Email address")
        self.fields['institution'].label = _("Institution")
        self.fields['bio'].label = _("Biography")
        self.fields['avatar'].label = _("Profile Picture")


class EmailVerificationForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        label=_("Verification code")
    )