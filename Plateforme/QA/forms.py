from django import forms
from .models import Question, Answer, Post, Comment
from django.core.validators import FileExtensionValidator

class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['title', 'description']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Titre de votre question'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Détaillez votre question...'})
        }

class AnswerForm(forms.ModelForm):
    class Meta:
        model = Answer
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Votre réponse...'})
        }

class PostForm(forms.ModelForm):
    remove_image = forms.BooleanField(required=False, label="Supprimer l'image")
    remove_file = forms.BooleanField(required=False, label="Supprimer le fichier")

    class Meta:
        model = Post
        fields = ['content', 'image', 'file']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Share something...'
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '*/*'
            })
        }

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            # Vérifier l'extension du fichier
            allowed_extensions = ['jpg', 'jpeg', 'png', 'gif']
            ext = image.name.split('.')[-1].lower()
            if ext not in allowed_extensions:
                raise forms.ValidationError('Format de fichier non supporté. Utilisez JPG, JPEG, PNG ou GIF.')
            
            # Vérifier la taille du fichier (5MB max)
            if image.size > 5 * 1024 * 1024:
                raise forms.ValidationError('L\'image ne doit pas dépasser 5MB.')
        return image

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # Vérifier la taille du fichier (50MB max pour les fichiers)
            if file.size > 50 * 1024 * 1024:
                raise forms.ValidationError('Le fichier ne doit pas dépasser 50MB.')
        return file

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Votre commentaire...'
            })
        }
