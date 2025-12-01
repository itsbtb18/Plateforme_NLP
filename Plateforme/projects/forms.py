from django import forms
from .models import Project
from django.utils.translation import get_language

class ProjectForm(forms.ModelForm):
    
    class Meta:
        model = Project
        fields = ['title', 'institution', 'description', 
                  'status', 'date_start', 'date_end', 'attachment']
        widgets = {
            'date_start': forms.DateInput(attrs={'type': 'text'}),
            'date_end': forms.DateInput(attrs={'type': 'text'}),
            'description': forms.Textarea(attrs={'rows': 4}),
            'objectives': forms.Textarea(attrs={'rows': 4}),
        }