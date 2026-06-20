from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import inlineformset_factory
from .models import Event, Speaker
from django.utils.translation import gettext_lazy as _, get_language
from institutions.models import Institution


def get_active_language():
    """Get the current language, normalizing to 'ar' or 'en'."""
    lang = get_language()
    if lang and lang.startswith('ar'):
        return 'ar'
    return 'en'


class EventForm(forms.ModelForm):
    """
    Context-aware event form that shows language-specific fields.
    
    - Title, Description, Location are shown with the current language label
    - Data is saved to the appropriate _ar or _en field based on active language
    """
    
    # Bilingual field mappings: generic_field -> (ar_field, en_field)
    BILINGUAL_FIELDS = {
        'title': ('title_ar', 'title_en'),
        'description': ('description_ar', 'description_en'),
        'location': ('location_ar', 'location_en'),
    }
    OTHER_ORGANIZER_VALUE = "__other__"

    # Store domains as a comma-separated string in the model, but expose
    # them as a multiselect in the form.
    domains = forms.MultipleChoiceField(
        choices=Event.DOMAIN_CHOICES,
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
    )
    title_en = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    title_ar = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'dir': 'rtl'}),
    )
    description_en = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
    )
    description_ar = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'dir': 'rtl'}),
    )
    location_en = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    location_ar = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'dir': 'rtl'}),
    )
    
    class Meta:
        model = Event
        fields = [
            'title', 'description', 'event_type', 'domains',
            'location', 'start_date', 'end_date',
            'submission_deadline', 'website', 'organizer',
            'contact_email', 'attachment'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ('Event Title')}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'event_type': forms.Select(attrs={'class': 'form-select'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ('Leave blank for virtual events')}),
            'start_date': forms.DateInput(attrs={'type': 'text', 'class': 'form-control', 'placeholder': ''}),
            'end_date': forms.DateInput(attrs={'type': 'text', 'class': 'form-control', 'placeholder': ''}),
            'submission_deadline': forms.DateInput(attrs={'type': 'text', 'class': 'form-control', 'placeholder': ''}),
            'website': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://'}),
            'organizer': forms.Select(attrs={'class': 'form-select'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'contact@example.com'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        instance = kwargs.get('instance', None)

        if instance:
            if 'initial' not in kwargs:
                kwargs['initial'] = {}
            for generic_field, (ar_field, en_field) in self.BILINGUAL_FIELDS.items():
                kwargs['initial'][en_field] = getattr(instance, en_field, '') or ''
                kwargs['initial'][ar_field] = getattr(instance, ar_field, '') or ''
                kwargs['initial'][generic_field] = getattr(instance, en_field, '') or getattr(instance, ar_field, '') or getattr(instance, generic_field, '')

        super().__init__(*args, **kwargs)

        # The template edits bilingual fields directly, so the legacy base fields
        # must not block validation when they are omitted from POST.
        self.fields['title'].required = False
        self.fields['description'].required = False
        self.fields['location'].required = False

        # Convert stored CSV domains to list so multiselect is prefilled on edit.
        if instance and instance.domains and not self.is_bound:
            self.initial['domains'] = [d.strip() for d in instance.domains.split(',') if d.strip()]

        # Add explicit "Other" choice to organizer list.
        organizer_field = self.fields.get('organizer')
        if organizer_field is not None:
            organizer_qs = self._get_visible_organizers_queryset()
            organizer_choices = [(str(obj.pk), str(obj)) for obj in organizer_qs]

            has_real_other = organizer_qs.filter(type='Other').exists()
            if not has_real_other:
                organizer_choices.append((self.OTHER_ORGANIZER_VALUE, _("Other")))

            self.fields['organizer'] = forms.ChoiceField(
                choices=organizer_choices,
                required=True,
                widget=forms.Select(attrs={'class': 'form-select'}),
                label=_("Organizer"),
            )
            if instance and instance.organizer_id and not self.is_bound:
                self.initial['organizer'] = str(instance.organizer_id)

        self._setup_bilingual_labels()

    def _get_visible_organizers_queryset(self):
        """Return organizers visible to the current user with a safe fallback."""
        base_qs = Institution.objects.order_by('name')

        if self.user and not getattr(self.user, 'is_staff', False):
            visible_qs = base_qs.filter(
                Q(approval_status='approved') | Q(created_by=self.user)
            )
        else:
            visible_qs = base_qs

        if visible_qs.exists():
            return visible_qs
        return base_qs
    
    def _setup_bilingual_labels(self):
        """Set context-aware labels for bilingual fields."""
        lang = get_active_language()
        
        if lang == 'ar':
            self.fields['title'].label = _("Title (Arabic / العنوان)")
            self.fields['title'].help_text = _("Enter the event title in Arabic")
            self.fields['description'].label = _("Description (Arabic / الوصف)")
            self.fields['description'].help_text = _("Enter the description in Arabic")
            self.fields['location'].label = _("Location (Arabic / المكان)")
            self.fields['location'].help_text = _("Enter the location in Arabic")
        else:
            self.fields['title'].label = _("Title (English)")
            self.fields['title'].help_text = _("Enter the event title in English")
            self.fields['description'].label = _("Description (English)")
            self.fields['description'].help_text = _("Enter the description in English")
            self.fields['location'].label = _("Location (English)")
            self.fields['location'].help_text = _("Enter the location in English")
    
    def save(self, commit=True):
        instance = super().save(commit=False)

        title_en = (self.cleaned_data.get('title_en') or '').strip()
        title_ar = (self.cleaned_data.get('title_ar') or '').strip()
        description_en = (self.cleaned_data.get('description_en') or '').strip()
        description_ar = (self.cleaned_data.get('description_ar') or '').strip()
        location_en = (self.cleaned_data.get('location_en') or '').strip()
        location_ar = (self.cleaned_data.get('location_ar') or '').strip()

        instance.title_en = title_en
        instance.title_ar = title_ar
        instance.description_en = description_en
        instance.description_ar = description_ar
        instance.location_en = location_en
        instance.location_ar = location_ar

        instance.title = title_en or title_ar
        instance.description = description_en or description_ar
        instance.location = location_en or location_ar
        
        if commit:
            instance.save()
        return instance

    def clean(self):
        cleaned_data = super().clean()

        title_en = (cleaned_data.get('title_en') or '').strip()
        title_ar = (cleaned_data.get('title_ar') or '').strip()
        description_en = (cleaned_data.get('description_en') or '').strip()
        description_ar = (cleaned_data.get('description_ar') or '').strip()
        location_en = (cleaned_data.get('location_en') or '').strip()
        location_ar = (cleaned_data.get('location_ar') or '').strip()

        if not title_en and not title_ar:
            message = _("Please provide a title in English or Arabic.")
            self.add_error('title_en', message)
            self.add_error('title_ar', message)

        if not description_en and not description_ar:
            message = _("Please provide a description in English or Arabic.")
            self.add_error('description_en', message)
            self.add_error('description_ar', message)

        cleaned_data['title'] = title_en or title_ar
        cleaned_data['description'] = description_en or description_ar
        cleaned_data['location'] = location_en or location_ar
        return cleaned_data

    def clean_domains(self):
        domains = self.cleaned_data.get('domains', [])
        return ",".join(domains)

    def clean_organizer(self):
        organizer_value = self.cleaned_data.get('organizer')

        if organizer_value == self.OTHER_ORGANIZER_VALUE:
            other_institution = Institution.objects.filter(type='Other').order_by('name').first()
            if other_institution:
                return other_institution
            raise ValidationError(
                _("No organizer of type 'Other' exists yet. Please add one in institutions first.")
            )

        try:
            return Institution.objects.get(pk=organizer_value)
        except (Institution.DoesNotExist, ValueError, TypeError):
            raise ValidationError(_("Please select a valid organizer."))


class EventSearchForm(forms.Form):
    """Form for searching events."""
    
    # Support both 'q' (standard) and 'keyword' (legacy) for search
    q = forms.CharField(
        required=False, 
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': ('Search by title, description, or organizer'),
            'name': 'q'
        })
    )
    keyword = forms.CharField(
        required=False, 
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': ('Search by title, description, or organizer')
        })
    )
    event_type = forms.ChoiceField(
        choices=[('', _('All Types'))] + list(Event.TYPE_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    domain = forms.ChoiceField(
        choices=[('', _('All Domains'))] + list(Event.DOMAIN_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'text',
            'class': 'form-control',
            'placeholder': 'dd/mm/yyyy'
        })
    )
    include_past = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        # Merge q and keyword fields - q takes precedence
        q = cleaned_data.get('q', '')
        keyword = cleaned_data.get('keyword', '')
        cleaned_data['keyword'] = q or keyword
        return cleaned_data


SpeakerFormSet = inlineformset_factory(
    Event,
    Speaker,
    fields=[
        "name",
        "affiliation",
        "bio",
        "talk_title",
        "website",
        "avatar",
        "order",
    ],
    extra=1,
    can_delete=True,
)
