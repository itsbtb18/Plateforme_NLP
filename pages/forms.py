
from django import forms
from django.utils.translation import gettext_lazy as _
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