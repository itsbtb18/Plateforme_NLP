from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.password_validation import validate_password
from django.core.validators import EmailValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _, get_language
from .models import CustomUser
from institutions.models import Institution
import re


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


def get_algerian_institutions_queryset():
    """
    Return Algerian institutions for account forms.
    Fallback to all institutions if DZ-tagged rows are unavailable.
    """
    qs = Institution.objects.filter(country__code__iexact="DZ").order_by("name")
    if qs.exists():
        return qs
    return Institution.objects.all().order_by("name")


class CustomUserCreationForm(UserCreationForm):
    """
    Enhanced user creation form with bilingual support and validation.
    """
    email = forms.EmailField(
        max_length=254,
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': _("Enter your email address"),
            'autocomplete': 'email'
        }),
        label=_("Email Address"),
        validators=[EmailValidator(message=_("Please enter a valid email address."))]
    )
    
    speciality = forms.ChoiceField(
        choices=[('', _("Select your specialization"))] + list(CustomUser.SPECIALITY_CHOICES),
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
            'placeholder': _("Enter your full name in Arabic"),
            'autocomplete': 'name'
        }),
        label=_("Full Name (Arabic)")
    )
    
    full_name_en = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _("Enter your full name in English"),
            'autocomplete': 'name'
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
        
        # Configure field labels and attributes
        self.fields['full_name'].label = _("Full name (Legacy)")
        self.fields['full_name'].required = False
        self.fields['full_name'].widget.attrs.update({'class': 'form-control d-none'})  # Hide legacy field
        
        self.fields['full_name_ar'].label = labels['full_name_ar']
        self.fields['full_name_en'].label = labels['full_name_en']
        self.fields['email'].label = _("Email Address")
        self.fields['institution'].label = _("Institution")
        self.fields['institution'].widget.attrs.update({'class': 'form-select'})
        self.fields['institution'].queryset = get_algerian_institutions_queryset()
        
        # Password fields with enhanced security labels
        self.fields['password1'].label = _("Password")
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'autocomplete': 'new-password'
        })
        self.fields['password2'].label = _("Confirm Password")
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'autocomplete': 'new-password'
        })
        
        # Help texts
        self.fields['password1'].help_text = _(
            "Your password must contain at least 8 characters, "
            "cannot be too similar to your personal information, "
            "and cannot be a commonly used password."
        )
        self.fields['password2'].help_text = _("Enter the same password for verification.")
        self.fields['full_name_ar'].help_text = _("Required - Your name as it appears in Arabic")
        self.fields['full_name_en'].help_text = _("Required - Your name as it appears in English")

    def clean_email(self):
        """Normalize and validate email."""
        email = self.cleaned_data.get('email', '').lower().strip()
        
        if not email:
            raise forms.ValidationError(_("Email address is required."))
        
        # Check for existing email (case-insensitive)
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("This email address is already registered."))
        
        return email

    def clean_full_name_ar(self):
        """Validate Arabic name."""
        name = self.cleaned_data.get('full_name_ar', '').strip()
        if not name:
            raise forms.ValidationError(_("Arabic name is required."))
        if len(name) < 2:
            raise forms.ValidationError(_("Name must be at least 2 characters long."))
        return name

    def clean_full_name_en(self):
        """Validate English name."""
        name = self.cleaned_data.get('full_name_en', '').strip()
        if not name:
            raise forms.ValidationError(_("English name is required."))
        if len(name) < 2:
            raise forms.ValidationError(_("Name must be at least 2 characters long."))
        # Basic validation for Latin characters
        if not re.match(r'^[a-zA-Z\s\-\'\.]+$', name):
            raise forms.ValidationError(_("Please use only Latin characters for the English name."))
        return name

    def clean_password1(self):
        """Validate password strength."""
        password1 = self.cleaned_data.get('password1')
        if password1:
            # Use Django's built-in password validators
            try:
                validate_password(password1)
            except ValidationError as e:
                raise forms.ValidationError(list(e.messages))
        return password1

    def save(self, commit=True):
        """
        Standard save method. Honors commit=False.
        """
        user = super().save(commit=False)
        user.email = self.cleaned_data.get('email', '').lower().strip()
        user.full_name = self.cleaned_data.get('full_name') or self.cleaned_data.get('full_name_en')
        user.full_name_ar = self.cleaned_data.get('full_name_ar', '').strip()
        user.full_name_en = self.cleaned_data.get('full_name_en', '').strip()
        user.institution = self.cleaned_data.get('institution')
        user.speciality = self.cleaned_data.get('speciality')
        if commit:
            user.save()
        return user


class CustomUserChangeForm(UserChangeForm):
    """
    Enhanced user profile edit form with bilingual support and social links.
    """
    password = None  # Remove password field from change form
    
    speciality = forms.ChoiceField(
        choices=[('', _("Select your specialization"))] + list(CustomUser.SPECIALITY_CHOICES),
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
            'placeholder': _("Write your biography in Arabic"),
            'maxlength': '1000'
        }),
        label=_("Biography (Arabic)")
    )
    
    bio_en = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': _("Write your biography in English"),
            'maxlength': '1000'
        }),
        label=_("Biography (English)")
    )
    
    linkedin_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://linkedin.com/in/your-profile'
        }),
        label=_("LinkedIn"),
        help_text=_("Your LinkedIn profile URL")
    )
    
    twitter_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://twitter.com/your-handle'
        }),
        label=_("Twitter / X"),
        help_text=_("Your Twitter or X profile URL")
    )
    
    facebook_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://facebook.com/your-profile'
        }),
        label=_("Facebook"),
        help_text=_("Your Facebook profile URL")
    )
    
    class Meta:
        model = CustomUser
        fields = [
            'full_name', 'full_name_ar', 'full_name_en', 
            'email', 'institution', 'bio', 'bio_ar', 'bio_en',
            'speciality', 'linkedin_url', 'twitter_url', 'facebook_url'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Get conditional labels based on current language
        labels = get_bilingual_labels()
        
        # Configure field labels and attributes
        self.fields['full_name'].label = _("Full name (Legacy)")
        self.fields['full_name'].required = False
        self.fields['full_name'].widget.attrs.update({'class': 'form-control d-none'})  # Hide legacy field
        
        self.fields['full_name_ar'].label = labels['full_name_ar']
        self.fields['full_name_en'].label = labels['full_name_en']
        self.fields['bio_ar'].label = labels['bio_ar']
        self.fields['bio_en'].label = labels['bio_en']
        
        self.fields['email'].label = _("Email Address")
        self.fields['email'].widget.attrs.update({
            'class': 'form-control',
            'readonly': 'readonly'  # Email shouldn't be changed easily
        })
        
        self.fields['institution'].label = _("Institution")
        self.fields['institution'].widget.attrs.update({'class': 'form-select'})
        self.fields['institution'].queryset = get_algerian_institutions_queryset()
        
        self.fields['bio'].label = _("Biography (Legacy)")
        self.fields['bio'].widget.attrs.update({'class': 'form-control d-none'})  # Hide legacy field

    def clean_full_name_ar(self):
        """Validate Arabic name."""
        name = self.cleaned_data.get('full_name_ar', '').strip()
        if not name:
            raise forms.ValidationError(_("Arabic name is required."))
        if len(name) < 2:
            raise forms.ValidationError(_("Name must be at least 2 characters long."))
        return name

    def clean_full_name_en(self):
        """Validate English name."""
        name = self.cleaned_data.get('full_name_en', '').strip()
        if not name:
            raise forms.ValidationError(_("English name is required."))
        if len(name) < 2:
            raise forms.ValidationError(_("Name must be at least 2 characters long."))
        if not re.match(r'^[a-zA-Z\s\-\'\.]+$', name):
            raise forms.ValidationError(_("Please use only Latin characters for the English name."))
        return name

    def clean_linkedin_url(self):
        """Validate LinkedIn URL."""
        url = self.cleaned_data.get('linkedin_url', '').strip()
        if url and 'linkedin.com' not in url.lower():
            raise forms.ValidationError(_("Please enter a valid LinkedIn URL."))
        return url

    def clean_twitter_url(self):
        """Validate Twitter/X URL."""
        url = self.cleaned_data.get('twitter_url', '').strip()
        if url:
            url_lower = url.lower()
            if 'twitter.com' not in url_lower and 'x.com' not in url_lower:
                raise forms.ValidationError(_("Please enter a valid Twitter or X URL."))
        return url

    def clean_facebook_url(self):
        """Validate Facebook URL."""
        url = self.cleaned_data.get('facebook_url', '').strip()
        if url and 'facebook.com' not in url.lower():
            raise forms.ValidationError(_("Please enter a valid Facebook URL."))
        return url

    def clean_avatar(self):
        """Validate avatar image with content-based verification."""
        avatar = self.cleaned_data.get('avatar')
        if avatar:
            # Check file size (2MB limit)
            if avatar.size > 2 * 1024 * 1024:
                raise forms.ValidationError(_("Image file size must be less than 2MB."))
            
            # Check file extension
            allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp']
            file_ext = avatar.name.split('.')[-1].lower()
            if file_ext not in allowed_extensions:
                raise forms.ValidationError(
                    _("Allowed image formats: %(formats)s") % {'formats': ', '.join(allowed_extensions)}
                )
            
            # Content-based validation: verify actual image data using Pillow
            try:
                from PIL import Image
                avatar.seek(0)
                img = Image.open(avatar)
                img.verify()  # Verify it's a valid image
                avatar.seek(0)
                
                # Re-open to strip EXIF/metadata (security measure)
                img = Image.open(avatar)
                if img.format and img.format.lower() not in ['jpeg', 'png', 'gif', 'webp']:
                    raise forms.ValidationError(
                        _("Invalid image content. Allowed formats: JPEG, PNG, GIF, WebP.")
                    )
                avatar.seek(0)
            except forms.ValidationError:
                raise
            except Exception:
                raise forms.ValidationError(
                    _("The uploaded file is not a valid image.")
                )
        return avatar

    def save(self, commit=True):
        """Save the user with normalized data."""
        user = super().save(commit=False)
        
        # Sync legacy full_name with current language preference
        user.full_name = self.cleaned_data.get('full_name_en', '').strip()
        
        # Sync legacy bio if both bilingual versions are empty
        bio_ar = self.cleaned_data.get('bio_ar', '').strip()
        bio_en = self.cleaned_data.get('bio_en', '').strip()
        if not bio_ar and not bio_en:
            user.bio = self.cleaned_data.get('bio', '').strip()
        
        if commit:
            user.save()
        return user


class EmailVerificationForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        label=_("Verification code")
    )
