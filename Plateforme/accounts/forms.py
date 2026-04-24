import re

from django import forms
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from institutions.models import Institution

from .models import CustomUser, Experience


def get_bilingual_labels():
    """Return language-appropriate labels for bilingual fields."""
    lang = get_language()
    if lang and lang.startswith("ar"):
        return {
            "full_name_ar": _("الاسم الكامل (بالعربية)"),
            "full_name_en": _("الاسم الكامل (بالإنجليزية)"),
            "bio_ar": _("السيرة الذاتية (بالعربية)"),
            "bio_en": _("السيرة الذاتية (بالإنجليزية)"),
        }
    else:
        return {
            "full_name_ar": _("Full Name (Arabic)"),
            "full_name_en": _("Full Name (English)"),
            "bio_ar": _("Biography (Arabic)"),
            "bio_en": _("Biography (English)"),
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


def get_experience_institution_choices():
    base_queryset = get_algerian_institutions_queryset()
    seen = set()
    choices = []

    for item in base_queryset:
        name_en = (
            getattr(item, "name_en", "") or getattr(item, "name", "") or ""
        ).strip()
        name_ar = (getattr(item, "name_ar", "") or name_en or "").strip()
        if not name_en and not name_ar:
            continue
        key = (name_en or name_ar).lower()
        if key in seen:
            continue
        seen.add(key)
        label = (
            f"{name_ar} / {name_en}"
            if name_ar and name_en and name_ar != name_en
            else (name_ar or name_en)
        )
        choices.append((name_en or name_ar, label))

    fallback_companies = [
        ("University of Algiers 1", "جامعة الجزائر 1"),
        ("University of Algiers 2", "جامعة الجزائر 2"),
        ("University of Algiers 3", "جامعة الجزائر 3"),
        ("USTHB", "جامعة العلوم والتكنولوجيا هواري بومدين"),
        ("ESI Algiers", "المدرسة الوطنية العليا للإعلام الآلي"),
        ("ENSIA", "المدرسة الوطنية العليا للذكاء الاصطناعي"),
        ("University of Oran 1", "جامعة وهران 1"),
        ("University of Constantine 2", "جامعة قسنطينة 2"),
        ("University of Blida 1", "جامعة البليدة 1"),
        ("University of Sidi Bel Abbes", "جامعة سيدي بلعباس"),
        ("Sonatrach", "سوناطراك"),
        ("Sonelgaz", "سونلغاز"),
        ("Mobilis", "موبيليس"),
        ("Djezzy", "جازي"),
        ("Ooredoo Algeria", "أوريدو الجزائر"),
        ("Yassir", "ياسير"),
        ("Condor Electronics", "كوندور إلكترونيكس"),
        ("SATIM", "ساتيم"),
        ("CERIST", "مركز البحث في الإعلام العلمي والتقني"),
    ]
    for name_en, name_ar in fallback_companies:
        if name_en.lower() in seen:
            continue
        seen.add(name_en.lower())
        choices.append((name_en, f"{name_ar} / {name_en}"))

    choices.sort(key=lambda item: item[1].lower())
    return choices


def get_experience_role_choices():
    return [
        ("NLP Engineer", _("مهندس NLP / NLP Engineer")),
        ("AI Engineer", _("مهندس ذكاء اصطناعي / AI Engineer")),
        ("Researcher", _("باحث / Researcher")),
        ("Research Assistant", _("مساعد بحث / Research Assistant")),
        ("Data Scientist", _("عالم بيانات / Data Scientist")),
        ("Machine Learning Engineer", _("مهندس تعلم آلي / Machine Learning Engineer")),
        ("Intern", _("متربص / Intern")),
        ("Project Member", _("عضو مشروع / Project Member")),
        ("Teaching Assistant", _("مساعد تدريس / Teaching Assistant")),
    ]


def get_experience_institution_choices_localized():
    is_arabic = bool(get_language() and get_language().startswith("ar"))
    base_queryset = get_algerian_institutions_queryset()
    seen = set()
    choices = []

    for item in base_queryset:
        name_en = (
            getattr(item, "name_en", "") or getattr(item, "name", "") or ""
        ).strip()
        name_ar = (getattr(item, "name_ar", "") or name_en or "").strip()
        if not name_en and not name_ar:
            continue
        key = (name_en or name_ar).lower()
        if key in seen:
            continue
        seen.add(key)
        label = (name_ar or name_en) if is_arabic else (name_en or name_ar)
        choices.append((name_en or name_ar, label))

    fallback_companies = [
        ("University of Algiers 1", "جامعة الجزائر 1"),
        ("University of Algiers 2", "جامعة الجزائر 2"),
        ("University of Algiers 3", "جامعة الجزائر 3"),
        ("USTHB", "جامعة العلوم والتكنولوجيا هواري بومدين"),
        ("ESI Algiers", "المدرسة الوطنية العليا للإعلام الآلي"),
        ("ENSIA", "المدرسة الوطنية العليا للذكاء الاصطناعي"),
        ("University of Oran 1", "جامعة وهران 1"),
        ("University of Constantine 2", "جامعة قسنطينة 2"),
        ("University of Blida 1", "جامعة البليدة 1"),
        ("University of Sidi Bel Abbes", "جامعة سيدي بلعباس"),
        ("Sonatrach", "سوناطراك"),
        ("Sonelgaz", "سونلغاز"),
        ("Mobilis", "موبيليس"),
        ("Djezzy", "جازي"),
        ("Ooredoo Algeria", "أوريدو الجزائر"),
        ("Yassir", "ياسير"),
        ("Condor Electronics", "كوندور إلكترونيكس"),
        ("SATIM", "ساتيم"),
        ("CERIST", "مركز البحث في الإعلام العلمي والتقني"),
    ]
    for name_en, name_ar in fallback_companies:
        if name_en.lower() in seen:
            continue
        seen.add(name_en.lower())
        choices.append((name_en, name_ar if is_arabic else name_en))

    choices.sort(key=lambda item: item[1].lower())
    return choices


def get_experience_role_choices_localized():
    is_arabic = bool(get_language() and get_language().startswith("ar"))
    return [
        (
            "NLP Engineer",
            "مهندس معالجة اللغة الطبيعية" if is_arabic else "NLP Engineer",
        ),
        ("AI Engineer", "مهندس ذكاء اصطناعي" if is_arabic else "AI Engineer"),
        (
            "Machine Learning Engineer",
            "مهندس تعلم آلي" if is_arabic else "Machine Learning Engineer",
        ),
        ("Data Scientist", "عالم بيانات" if is_arabic else "Data Scientist"),
        ("Researcher", "باحث" if is_arabic else "Researcher"),
        ("Research Assistant", "مساعد بحث" if is_arabic else "Research Assistant"),
        ("Professor", "أستاذ" if is_arabic else "Professor"),
        ("Teaching Assistant", "مساعد تدريس" if is_arabic else "Teaching Assistant"),
        ("PhD Student", "طالب دكتوراه" if is_arabic else "PhD Student"),
        ("Master Student", "طالب ماستر" if is_arabic else "Master Student"),
        ("Intern", "متدرب" if is_arabic else "Intern"),
        ("Volunteer", "متطوع" if is_arabic else "Volunteer"),
        ("Project Member", "عضو مشروع" if is_arabic else "Project Member"),
        ("Project Lead", "قائد مشروع" if is_arabic else "Project Lead"),
        ("Consultant", "مستشار" if is_arabic else "Consultant"),
    ]


class CustomUserCreationForm(UserCreationForm):
    """
    Enhanced user creation form with bilingual support and validation.
    """

    email = forms.EmailField(
        max_length=254,
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": _("Enter your email address"),
                "autocomplete": "email",
            }
        ),
        label=_("Email Address"),
        validators=[EmailValidator(message=_("Please enter a valid email address."))],
    )

    speciality = forms.ChoiceField(
        choices=[("", _("Select your specialization"))]
        + list(CustomUser.SPECIALITY_CHOICES),
        widget=forms.Select(attrs={"class": "form-select"}),
        required=False,
        label=_("Field of Specialization in AI"),
    )

    full_name_ar = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "dir": "rtl",
                "placeholder": _("Enter your full name in Arabic"),
                "autocomplete": "name",
            }
        ),
        label=_("Full Name (Arabic)"),
    )

    full_name_en = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": _("Enter your full name in English"),
                "autocomplete": "name",
            }
        ),
        label=_("Full Name (English)"),
    )

    class Meta:
        model = CustomUser
        fields = [
            "full_name",
            "full_name_ar",
            "full_name_en",
            "email",
            "institution",
            "speciality",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Get conditional labels based on current language
        labels = get_bilingual_labels()

        # Configure field labels and attributes
        self.fields["full_name"].label = _("Full name (Legacy)")
        self.fields["full_name"].required = False
        self.fields["full_name"].widget.attrs.update(
            {"class": "form-control d-none"}
        )  # Hide legacy field

        self.fields["full_name_ar"].label = labels["full_name_ar"]
        self.fields["full_name_en"].label = labels["full_name_en"]
        self.fields["email"].label = _("Email Address")
        self.fields["institution"].label = _("Institution")
        self.fields["institution"].widget.attrs.update({"class": "form-select"})
        self.fields["institution"].queryset = get_algerian_institutions_queryset()

        # Password fields with enhanced security labels
        self.fields["password1"].label = _("Password")
        self.fields["password1"].widget.attrs.update(
            {"class": "form-control", "autocomplete": "new-password"}
        )
        self.fields["password2"].label = _("Confirm Password")
        self.fields["password2"].widget.attrs.update(
            {"class": "form-control", "autocomplete": "new-password"}
        )

        # Help texts
        self.fields["password1"].help_text = _(
            "Your password must contain at least 8 characters, "
            "cannot be too similar to your personal information, "
            "and cannot be a commonly used password."
        )
        self.fields["password2"].help_text = _(
            "Enter the same password for verification."
        )
        self.fields["full_name_ar"].help_text = _(
            "Required - Your name as it appears in Arabic"
        )
        self.fields["full_name_en"].help_text = _(
            "Required - Your name as it appears in English"
        )

    def clean_email(self):
        """Normalize and validate email."""
        email = self.cleaned_data.get("email", "").lower().strip()

        if not email:
            raise forms.ValidationError(_("Email address is required."))

        # Check for existing email (case-insensitive)
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("This email address is already registered."))

        return email

    def clean_full_name_ar(self):
        """Validate Arabic name."""
        name = self.cleaned_data.get("full_name_ar", "").strip()
        if not name:
            raise forms.ValidationError(_("Arabic name is required."))
        if len(name) < 2:
            raise forms.ValidationError(_("Name must be at least 2 characters long."))
        return name

    def clean_full_name_en(self):
        """Validate English name."""
        name = self.cleaned_data.get("full_name_en", "").strip()
        if not name:
            raise forms.ValidationError(_("English name is required."))
        if len(name) < 2:
            raise forms.ValidationError(_("Name must be at least 2 characters long."))
        # Basic validation for Latin characters
        if not re.match(r"^[a-zA-Z\s\-\'\.]+$", name):
            raise forms.ValidationError(
                _("Please use only Latin characters for the English name.")
            )
        return name

    def clean_password1(self):
        """Validate password strength."""
        password1 = self.cleaned_data.get("password1")
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
        user.email = self.cleaned_data.get("email", "").lower().strip()
        user.full_name = self.cleaned_data.get("full_name") or self.cleaned_data.get(
            "full_name_en"
        )
        user.full_name_ar = self.cleaned_data.get("full_name_ar", "").strip()
        user.full_name_en = self.cleaned_data.get("full_name_en", "").strip()
        user.institution = self.cleaned_data.get("institution")
        user.speciality = self.cleaned_data.get("speciality")
        if commit:
            user.save()
        return user


class CustomUserChangeForm(UserChangeForm):
    """
    Enhanced user profile edit form with bilingual support and social links.
    """

    password = None  # Remove password field from change form

    speciality = forms.ChoiceField(
        choices=[("", _("Select your specialization"))]
        + list(CustomUser.SPECIALITY_CHOICES),
        widget=forms.Select(attrs={"class": "form-select"}),
        required=False,
        label=_("Field of Specialization in AI"),
    )

    full_name_ar = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "dir": "rtl",
                "placeholder": _("Enter your full name in Arabic"),
            }
        ),
        label=_("Full Name (Arabic)"),
    )

    full_name_en = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": _("Enter your full name in English"),
            }
        ),
        label=_("Full Name (English)"),
    )

    bio_ar = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "dir": "rtl",
                "rows": 4,
                "placeholder": _("Write your biography in Arabic"),
                "maxlength": "1000",
            }
        ),
        label=_("Biography (Arabic)"),
    )

    bio_en = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": _("Write your biography in English"),
                "maxlength": "1000",
            }
        ),
        label=_("Biography (English)"),
    )

    linkedin_url = forms.URLField(
        required=False,
        assume_scheme="https",
        widget=forms.URLInput(
            attrs={
                "class": "form-control",
                "placeholder": "https://linkedin.com/in/your-profile",
            }
        ),
        label=_("LinkedIn"),
        help_text=_("Your LinkedIn profile URL"),
    )

    twitter_url = forms.URLField(
        required=False,
        assume_scheme="https",
        widget=forms.URLInput(
            attrs={
                "class": "form-control",
                "placeholder": "https://twitter.com/your-handle",
            }
        ),
        label=_("Twitter / X"),
        help_text=_("Your Twitter or X profile URL"),
    )

    facebook_url = forms.URLField(
        required=False,
        assume_scheme="https",
        widget=forms.URLInput(
            attrs={
                "class": "form-control",
                "placeholder": "https://facebook.com/your-profile",
            }
        ),
        label=_("Facebook"),
        help_text=_("Your Facebook profile URL"),
    )

    class Meta:
        model = CustomUser
        fields = [
            "full_name",
            "full_name_ar",
            "full_name_en",
            "email",
            "institution",
            "bio",
            "bio_ar",
            "bio_en",
            "speciality",
            "linkedin_url",
            "twitter_url",
            "facebook_url",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Get conditional labels based on current language
        labels = get_bilingual_labels()

        # Configure field labels and attributes
        self.fields["full_name"].label = _("Full name (Legacy)")
        self.fields["full_name"].required = False
        self.fields["full_name"].widget.attrs.update(
            {"class": "form-control d-none"}
        )  # Hide legacy field

        self.fields["full_name_ar"].label = labels["full_name_ar"]
        self.fields["full_name_en"].label = labels["full_name_en"]
        self.fields["bio_ar"].label = labels["bio_ar"]
        self.fields["bio_en"].label = labels["bio_en"]

        self.fields["email"].label = _("Email Address")
        self.fields["email"].widget.attrs.update(
            {
                "class": "form-control",
                "readonly": "readonly",  # Email shouldn't be changed easily
            }
        )

        self.fields["institution"].label = _("Institution")
        self.fields["institution"].widget.attrs.update({"class": "form-select"})
        self.fields["institution"].queryset = get_algerian_institutions_queryset()

        self.fields["bio"].label = _("Biography (Legacy)")
        self.fields["bio"].widget.attrs.update(
            {"class": "form-control d-none"}
        )  # Hide legacy field

    def clean_full_name_ar(self):
        """Validate Arabic name."""
        name = self.cleaned_data.get("full_name_ar", "").strip()
        if not name:
            raise forms.ValidationError(_("Arabic name is required."))
        if len(name) < 2:
            raise forms.ValidationError(_("Name must be at least 2 characters long."))
        return name

    def clean_full_name_en(self):
        """Validate English name."""
        name = self.cleaned_data.get("full_name_en", "").strip()
        if not name:
            raise forms.ValidationError(_("English name is required."))
        if len(name) < 2:
            raise forms.ValidationError(_("Name must be at least 2 characters long."))
        if not re.match(r"^[a-zA-Z\s\-\'\.]+$", name):
            raise forms.ValidationError(
                _("Please use only Latin characters for the English name.")
            )
        return name

    def clean_linkedin_url(self):
        """Validate LinkedIn URL."""
        url = self.cleaned_data.get("linkedin_url", "").strip()
        if url and "linkedin.com" not in url.lower():
            raise forms.ValidationError(_("Please enter a valid LinkedIn URL."))
        return url

    def clean_twitter_url(self):
        """Validate Twitter/X URL."""
        url = self.cleaned_data.get("twitter_url", "").strip()
        if url:
            url_lower = url.lower()
            if "twitter.com" not in url_lower and "x.com" not in url_lower:
                raise forms.ValidationError(_("Please enter a valid Twitter or X URL."))
        return url

    def clean_facebook_url(self):
        """Validate Facebook URL."""
        url = self.cleaned_data.get("facebook_url", "").strip()
        if url and "facebook.com" not in url.lower():
            raise forms.ValidationError(_("Please enter a valid Facebook URL."))
        return url

    def clean_avatar(self):
        """Validate avatar image with content-based verification."""
        avatar = self.cleaned_data.get("avatar")
        if avatar:
            # Check file size (2MB limit)
            if avatar.size > 2 * 1024 * 1024:
                raise forms.ValidationError(_("Image file size must be less than 2MB."))

            # Check file extension
            allowed_extensions = ["jpg", "jpeg", "png", "gif", "webp"]
            file_ext = avatar.name.split(".")[-1].lower()
            if file_ext not in allowed_extensions:
                raise forms.ValidationError(
                    _("Allowed image formats: %(formats)s")
                    % {"formats": ", ".join(allowed_extensions)}
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
                if img.format and img.format.lower() not in [
                    "jpeg",
                    "png",
                    "gif",
                    "webp",
                ]:
                    raise forms.ValidationError(
                        _(
                            "Invalid image content. Allowed formats: JPEG, PNG, GIF, WebP."
                        )
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
        user.full_name = self.cleaned_data.get("full_name_en", "").strip()

        # Sync legacy bio if both bilingual versions are empty
        bio_ar = self.cleaned_data.get("bio_ar", "").strip()
        bio_en = self.cleaned_data.get("bio_en", "").strip()
        if not bio_ar and not bio_en:
            user.bio = self.cleaned_data.get("bio", "").strip()

        if commit:
            user.save()
        return user


class EmailVerificationForm(forms.Form):
    code = forms.CharField(max_length=6, label=_("Verification code"))


class ExperienceForm(forms.ModelForm):
    institution_name = forms.CharField(required=False, widget=forms.HiddenInput())
    role_title = forms.CharField(required=False, widget=forms.HiddenInput())
    institution_choice = forms.CharField(required=False, widget=forms.HiddenInput())
    institution_name_ar_custom = forms.CharField(required=False)
    institution_name_en_custom = forms.CharField(required=False)
    role_choice = forms.CharField(required=False, widget=forms.HiddenInput())
    role_title_ar_custom = forms.CharField(required=False)
    role_title_en_custom = forms.CharField(required=False)

    class Meta:
        model = Experience
        fields = [
            "experience_type",
            "institution_name",
            "role_title",
            "project_url",
            "start_date",
            "end_date",
            "description",
        ]
        widgets = {
            "experience_type": forms.Select(attrs={"class": "form-select"}),
            "institution_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Institution")}
            ),
            "role_title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Role")}
            ),
            "project_url": forms.URLInput(
                attrs={"class": "form-control", "placeholder": _("Project link")}
            ),
            "start_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "end_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": _("Optional description"),
                }
            ),
        }

    def clean_institution_name(self):
        value = (self.cleaned_data.get("institution_name") or "").strip()
        return value

    def clean_role_title(self):
        value = (self.cleaned_data.get("role_title") or "").strip()
        return value

    def clean_project_url(self):
        return (self.cleaned_data.get("project_url") or "").strip()

    def clean(self):
        cleaned = super().clean()
        start_date = cleaned.get("start_date")
        end_date = cleaned.get("end_date")
        institution_choice = (cleaned.get("institution_choice") or "").strip()
        role_choice = (cleaned.get("role_choice") or "").strip()
        institution_name_ar_custom = (
            cleaned.get("institution_name_ar_custom") or ""
        ).strip()
        institution_name_en_custom = (
            cleaned.get("institution_name_en_custom") or ""
        ).strip()
        role_title_ar_custom = (cleaned.get("role_title_ar_custom") or "").strip()
        role_title_en_custom = (cleaned.get("role_title_en_custom") or "").strip()

        if institution_choice == "other":
            if not institution_name_ar_custom:
                self.add_error(
                    "institution_name_ar_custom",
                    _("Arabic institution name is required."),
                )
            if not institution_name_en_custom:
                self.add_error(
                    "institution_name_en_custom",
                    _("English institution name is required."),
                )
            cleaned["institution_name"] = " / ".join(
                part
                for part in [institution_name_ar_custom, institution_name_en_custom]
                if part
            )
        elif institution_choice:
            cleaned["institution_name"] = institution_choice

        if role_choice == "other":
            if not role_title_ar_custom:
                self.add_error(
                    "role_title_ar_custom", _("Arabic role title is required.")
                )
            if not role_title_en_custom:
                self.add_error(
                    "role_title_en_custom", _("English role title is required.")
                )
            cleaned["role_title"] = " / ".join(
                part for part in [role_title_ar_custom, role_title_en_custom] if part
            )
        elif role_choice:
            cleaned["role_title"] = role_choice

        if cleaned.get("experience_type") != Experience.ExperienceType.PROJECT:
            cleaned["project_url"] = ""

        if end_date and start_date and start_date > end_date:
            self.add_error(
                "end_date",
                _("End date must be greater than or equal to start date."),
            )

        if not end_date:
            cleaned["is_current"] = True
        else:
            cleaned["is_current"] = False

        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.institution_name = (
            self.cleaned_data.get("institution_name") or ""
        ).strip()
        instance.role_title = (self.cleaned_data.get("role_title") or "").strip()
        instance.project_url = (self.cleaned_data.get("project_url") or "").strip()
        instance.is_current = not bool(instance.end_date)
        if commit:
            instance.save()
        return instance

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        is_arabic = bool(get_language() and get_language().startswith("ar"))

        institution_choices = get_experience_institution_choices_localized()
        role_choices = get_experience_role_choices_localized()

        self.fields["experience_type"].widget.attrs.update({"class": "op-select"})
        self.fields["experience_type"].choices = [
            ("professional", "خبرة مهنية" if is_arabic else "Professional"),
            ("project", "مشروع" if is_arabic else "Project"),
            ("event", "فعالية" if is_arabic else "Event"),
            ("volunteer", "تطوعي" if is_arabic else "Volunteer"),
            ("internship", "تدريب" if is_arabic else "Internship"),
        ]
        self.fields["institution_name"].widget = forms.HiddenInput()
        self.fields["role_title"].widget = forms.HiddenInput()
        self.fields["project_url"].widget.attrs.update(
            {
                "class": "op-input",
                "type": "url",
                "dir": "ltr",
                "placeholder": "https://example.com/project"
                if is_arabic
                else _("https://example.com/project"),
            }
        )
        self.fields["start_date"].widget.attrs.update(
            {"class": "op-input", "type": "date"}
        )
        self.fields["end_date"].widget.attrs.update(
            {"class": "op-input", "type": "date"}
        )
        description_placeholder = (
            "وصف اختياري" if is_arabic else _("Optional description")
        )
        self.fields["description"].widget.attrs.update(
            {
                "class": "op-textarea",
                "rows": 4,
                "dir": "rtl" if is_arabic else "ltr",
                "placeholder": description_placeholder,
            }
        )

        self.institution_choice_options = (
            [("", "اختر المؤسسة" if is_arabic else _("Select institution"))]
            + institution_choices
            + [("other", "مؤسسة أخرى" if is_arabic else _("Other institution"))]
        )
        self.fields["institution_choice"].widget = forms.HiddenInput()
        self.fields["institution_choice"].label = _("Institution")

        self.fields["institution_name_ar_custom"].widget = forms.TextInput(
            attrs={
                "class": "op-input",
                "dir": "rtl",
                "placeholder": "اسم المؤسسة بالعربية"
                if is_arabic
                else _("Institution name in Arabic"),
            }
        )
        self.fields["institution_name_ar_custom"].label = (
            "اسم المؤسسة (بالعربية)" if is_arabic else _("Institution name (Arabic)")
        )

        self.fields["institution_name_en_custom"].widget = forms.TextInput(
            attrs={
                "class": "op-input",
                "placeholder": "Institution name in English"
                if is_arabic
                else _("Institution name in English"),
            }
        )
        self.fields["institution_name_en_custom"].label = (
            "اسم المؤسسة (بالإنجليزية)"
            if is_arabic
            else _("Institution name (English)")
        )

        self.role_choice_options = (
            [("", "اختر الدور" if is_arabic else _("Select role"))]
            + role_choices
            + [("other", "دور آخر" if is_arabic else _("Other role"))]
        )
        self.fields["role_choice"].widget = forms.HiddenInput()
        self.fields["role_choice"].label = _("Role")

        self.fields["role_title_ar_custom"].widget = forms.TextInput(
            attrs={
                "class": "op-input",
                "dir": "rtl",
                "placeholder": "المسمى الوظيفي بالعربية"
                if is_arabic
                else _("Role title in Arabic"),
            }
        )
        self.fields["role_title_ar_custom"].label = (
            "المسمى الوظيفي (بالعربية)" if is_arabic else _("Role title (Arabic)")
        )

        self.fields["role_title_en_custom"].widget = forms.TextInput(
            attrs={
                "class": "op-input",
                "placeholder": "Role title in English"
                if is_arabic
                else _("Role title in English"),
            }
        )
        self.fields["role_title_en_custom"].label = (
            "المسمى الوظيفي (بالإنجليزية)" if is_arabic else _("Role title (English)")
        )

        existing_institution = (self.instance.institution_name or "").strip()
        existing_role = (self.instance.role_title or "").strip()
        institution_values = {value for value, _label in institution_choices}
        role_values = {value for value, _label in role_choices}

        if existing_institution:
            if existing_institution in institution_values:
                self.initial["institution_choice"] = existing_institution
            else:
                self.initial["institution_choice"] = "other"
                if " / " in existing_institution:
                    ar_name, en_name = existing_institution.split(" / ", 1)
                    self.initial["institution_name_ar_custom"] = ar_name
                    self.initial["institution_name_en_custom"] = en_name
                else:
                    self.initial["institution_name_en_custom"] = existing_institution

        if existing_role:
            if existing_role in role_values:
                self.initial["role_choice"] = existing_role
            else:
                self.initial["role_choice"] = "other"
                if " / " in existing_role:
                    ar_role, en_role = existing_role.split(" / ", 1)
                    self.initial["role_title_ar_custom"] = ar_role
                    self.initial["role_title_en_custom"] = en_role
                else:
                    self.initial["role_title_en_custom"] = existing_role

        self.fields["project_url"].label = (
            "رابط المشروع" if is_arabic else _("Project link")
        )
