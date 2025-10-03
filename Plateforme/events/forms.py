from django import forms
from .models import Event

class EventForm(forms.ModelForm):
    """Form for creating and updating events."""
    
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
            'domains': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ('e.g., NLP, Speech Processing, Arabic Language')}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': ('Leave blank for virtual events')}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'submission_deadline': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'website': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://'}),
            'organizer': forms.Select(attrs={'class': 'form-select'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'contact@example.com'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
        }
    
  


class EventSearchForm(forms.Form):
    """Form for searching events."""
    
    keyword = forms.CharField(
        required=False, 
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': ('Search by title, description, or organizer')
        })
    )
    event_type = forms.ChoiceField(
        choices=[('', ('All Types'))] + list(Event.TYPE_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    domain = forms.ChoiceField(
        choices=[('', ('All Domains'))] + list(Event.DOMAIN_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    include_past = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
