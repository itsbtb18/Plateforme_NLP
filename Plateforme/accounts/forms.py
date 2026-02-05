from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.translation import gettext_lazy as _, get_language
from .models import CustomUser

ALLOWED_EMAIL_DOMAINS = ["yahoo.fr", "gmail.com"]


def get_bilingual_labels():
    """Return language-appropriate labels for bilingual fields."""
    lang = get_language()
    if lang and lang.startswith('ar'):
        return {
            'full_name_ar': _("الاسم الكامل (بالعربية)"),
            'full_name_en': _("الاسم الكامل (بالإنجليزية)"),
            'bio_ar': _("السيرة الذاتية (بالعربية)"),
            'bio_en': _("السيرة الذاتية (بالإنجليزية)"),
        }
    else:
        return {
            'full_name_ar': _("Full Name (Arabic)"),
            'full_name_en': _("Full Name (English)"),
            'bio_ar': _("Biography (Arabic)"),
            'bio_en': _("Biography (English)"),
        }


class CustomUserCreationForm(UserCreationForm):
    speciality = forms.ChoiceField(
        choices=CustomUser.SPECIALITY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
        label=_("Field of Specialization in AI")
    )
    
    full_name_ar = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'dir': 'rtl',
            'placeholder': _("Enter your full name in Arabic")
        }),
        label=_("Full Name (Arabic)")
    )
    
    full_name_en = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _("Enter your full name in English")
        }),
        label=_("Full Name (English)")
    )

    class Meta:
        model = CustomUser
        fields = ['full_name', 'full_name_ar', 'full_name_en', 'email', 'institution', 'speciality']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Get conditional labels based on current language
        labels = get_bilingual_labels()
        
        # Add translations to form field labels
        self.fields['full_name'].label = _("Full name (Legacy)")
        self.fields['full_name'].required = False
        self.fields['full_name_ar'].label = labels['full_name_ar']
        self.fields['full_name_en'].label = labels['full_name_en']
        self.fields['email'].label = _("Email address")
        self.fields['institution'].label = _("Institution")
        self.fields['password1'].label = _("Password")
        self.fields['password2'].label = _("Confirm password")
        
        # Add help texts with translations
        self.fields['password1'].help_text = _("Password must contain at least 8 characters")
        self.fields['password2'].help_text = _("Enter the same password for verification")
        self.fields['full_name_ar'].help_text = _("Required - Your name as it appears in Arabic")
        self.fields['full_name_en'].help_text = _("Required - Your name as it appears in English")

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
        user.full_name = self.cleaned_data.get('full_name') or self.cleaned_data.get('full_name_en')
        user.full_name_ar = self.cleaned_data.get('full_name_ar', '')
        user.full_name_en = self.cleaned_data.get('full_name_en', '')
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
    
    full_name_ar = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'dir': 'rtl',
            'placeholder': _("Enter your full name in Arabic")
        }),
        label=_("Full Name (Arabic)")
    )
    
    full_name_en = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _("Enter your full name in English")
        }),
        label=_("Full Name (English)")
    )
    
    bio_ar = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'dir': 'rtl',
            'rows': 4,
            'placeholder': _("Write your biography in Arabic")
        }),
        label=_("Biography (Arabic)")
    )
    
    bio_en = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': _("Write your biography in English")
        }),
        label=_("Biography (English)")
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
            'full_name', 'full_name_ar', 'full_name_en', 
            'email', 'institution', 'bio', 'bio_ar', 'bio_en', 'avatar',
            'speciality', 'linkedin_url', 'twitter_url', 'facebook_url'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Get conditional labels based on current language
        labels = get_bilingual_labels()
        
        # Add translations to form field labels
        self.fields['full_name'].label = _("Full name (Legacy)")
        self.fields['full_name'].required = False
        self.fields['full_name_ar'].label = labels['full_name_ar']
        self.fields['full_name_en'].label = labels['full_name_en']
        self.fields['bio_ar'].label = labels['bio_ar']
        self.fields['bio_en'].label = labels['bio_en']
        self.fields['email'].label = _("Email address")
        self.fields['institution'].label = _("Institution")
        self.fields['bio'].label = _("Biography (Legacy)")
        self.fields['avatar'].label = _("Profile Picture")


class EmailVerificationForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        label=_("Verification code")
    )