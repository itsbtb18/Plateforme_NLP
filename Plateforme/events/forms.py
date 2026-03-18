from django import forms
from django.core.exceptions import ValidationError
from .models import Event
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

        # Convert stored CSV domains to list so multiselect is prefilled on edit.
        if instance and instance.domains and not self.is_bound:
            self.initial['domains'] = [d.strip() for d in instance.domains.split(',') if d.strip()]

        # Add explicit "Other" choice to organizer list.
        organizer_field = self.fields.get('organizer')
        if organizer_field is not None and hasattr(organizer_field, "queryset"):
            organizer_qs = organizer_field.queryset
            organizer_choices = [(str(obj.pk), str(obj)) for obj in organizer_qs]
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
        
        # Save to bilingual fields based on active language
        lang = get_active_language()
        for generic_field, (ar_field, en_field) in self.BILINGUAL_FIELDS.items():
            target_field = ar_field if lang == 'ar' else en_field
            value = self.cleaned_data.get(generic_field, '')
            # Set both the base field and the language-specific field
            setattr(instance, generic_field, value)
            setattr(instance, target_field, value)
        
        if commit:
            instance.save()
        return instance

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
