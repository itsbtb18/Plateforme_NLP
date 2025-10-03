from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser

ALLOWED_EMAIL_DOMAINS = ["usthb.dz" , "gmail.com"] 

class CustomUserCreationForm(UserCreationForm):
    speciality = forms.ChoiceField(
        choices=CustomUser.SPECIALITY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
        label="Domaine de spécialisation en IA"
    )

    class Meta:
        model = CustomUser
        fields = ['full_name', 'email', 'institution', 'speciality']

    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower()
        domain = email.split('@')[-1]
        if domain not in ALLOWED_EMAIL_DOMAINS:
            raise forms.ValidationError(
                f"Votre e-mail doit se terminer par l’extension « {ALLOWED_EMAIL_DOMAINS[0]} »."
            )
        return email

    def try_save(self, request):
            """
            Méthode personnalisée qu'attend la vue SignupView modifiée
            """
            # Construire l'utilisateur sans l'enregistrer pour pouvoir lui affecter
            # tous les champs custom avant.
            user = super().save(commit=False)
            user.full_name   = self.cleaned_data.get('full_name')
            user.institution = self.cleaned_data.get('institution')
            user.speciality  = self.cleaned_data.get('speciality')
            user.save()

    # setup_user=True signifie : laisser allauth
    # gérer envoi e-mail de confirmation si activé.
            return user, True

    def save(self, request):
        """
        Méthode standard attendue par django-allauth par défaut
        """
        # On réutilise simplement la méthode try_save
        return self.try_save(request)

class CustomUserChangeForm(UserChangeForm):
    speciality = forms.ChoiceField(
        choices=CustomUser.SPECIALITY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
        label="Domaine de spécialisation en IA"
    )
    linkedin_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://linkedin.com/in/votre-profil'
        }),
        label="LinkedIn"
    )
    twitter_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://twitter.com/votre-compte'
        }),
        label="Twitter"
    )
    facebook_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://facebook.com/votre-profil'
        }),
        label="Facebook"
    )

    class Meta:
        model = CustomUser
        fields = [
            'full_name', 'email', 'institution', 'bio', 'avatar',
            'speciality', 'linkedin_url', 'twitter_url', 'facebook_url'
        ]


class EmailVerificationForm(forms.Form):
    code = forms.CharField(max_length=6, label="Code de vérification")
