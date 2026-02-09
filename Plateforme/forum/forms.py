from django import forms
from .models import Topic, ChatRoom
from django.utils.translation import get_language, gettext_lazy as _


def get_active_language():
    """Get the current language, normalizing to 'ar' or 'en'."""
    lang = get_language()
    if lang and lang.startswith('ar'):
        return 'ar'
    return 'en'


class ChatRoomForm(forms.ModelForm):
    """
    Bilingual ChatRoom form with Arabic and English fields.
    """
    
    name_ar = forms.CharField(
        max_length=200,
        required=False,
        label=_("Arabic Name"),
        widget=forms.TextInput(attrs={'class': 'cn-input', 'placeholder': _('Enter Arabic name')})
    )
    name_en = forms.CharField(
        max_length=200,
        required=False,
        label=_("English Name"),
        widget=forms.TextInput(attrs={'class': 'cn-input', 'placeholder': _('Enter English name')})
    )
    description_ar = forms.CharField(
        required=False,
        label=_("Arabic Description"),
        widget=forms.Textarea(attrs={'class': 'cn-textarea', 'placeholder': _('Describe the purpose of this room...')})
    )
    description_en = forms.CharField(
        required=False,
        label=_("English Description"),
        widget=forms.Textarea(attrs={'class': 'cn-textarea', 'placeholder': _('Describe the purpose of this room...')})
    )
    
    class Meta:
        model = ChatRoom
        fields = ['name_ar', 'name_en', 'description_ar', 'description_en']
    
    def clean(self):
        cleaned_data = super().clean()
        name_ar = cleaned_data.get('name_ar', '').strip()
        name_en = cleaned_data.get('name_en', '').strip()
        
        # At least one name is required
        if not name_ar and not name_en:
            raise forms.ValidationError(_("Please provide at least one room name (Arabic or English)."))
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Set the main name field from whichever language is provided
        name_en = self.cleaned_data.get('name_en', '').strip()
        name_ar = self.cleaned_data.get('name_ar', '').strip()
        instance.name = name_en or name_ar
        
        # Set the main description field
        desc_en = self.cleaned_data.get('description_en', '').strip()
        desc_ar = self.cleaned_data.get('description_ar', '').strip()
        instance.description = desc_en or desc_ar or ''
        
        if commit:
            instance.save()
        return instance


class TopicForm(forms.ModelForm):
    """
    Context-aware topic form that shows language-specific fields.
    
    - Title and Description are shown with the current language label
    - Data is saved to the appropriate _ar or _en field based on active language
    """
    
    # Bilingual field mappings: generic_field -> (ar_field, en_field)
    BILINGUAL_FIELDS = {
        'title': ('title_ar', 'title_en'),
        'description': ('description_ar', 'description_en'),
    }
    
    class Meta:
        model = Topic
        fields = ['title', 'description']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
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
        self._setup_bilingual_labels()
    
    def _setup_bilingual_labels(self):
        """Set context-aware labels for bilingual fields."""
        lang = get_active_language()
        
        if lang == 'ar':
            self.fields['title'].label = _("Topic Title (Arabic / العنوان)")
            self.fields['title'].help_text = _("Enter the topic title in Arabic")
            self.fields['description'].label = _("Description (Arabic / الوصف)")
            self.fields['description'].help_text = _("Enter the description in Arabic")
        else:
            self.fields['title'].label = _("Topic Title (English)")
            self.fields['title'].help_text = _("Enter the topic title in English")
            self.fields['description'].label = _("Description (English)")
            self.fields['description'].help_text = _("Enter the description in English")
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Save to bilingual fields based on active language
        lang = get_active_language()
        for generic_field, (ar_field, en_field) in self.BILINGUAL_FIELDS.items():
            target_field = ar_field if lang == 'ar' else en_field
            value = self.cleaned_data.get(generic_field, '')
            setattr(instance, target_field, value)
        
        if commit:
            instance.save()
        return instance
