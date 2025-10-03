from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Institution, Country, Specialty


class InstitutionFilterForm(forms.Form):
    INSTITUTION_TYPE_CHOICES = [('', _('All'))] + Institution.TYPE

    institution_type = forms.ChoiceField(
        choices=INSTITUTION_TYPE_CHOICES,
        required=False,
        label=_('Institution Type'),
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )
    country = forms.ModelChoiceField(
        queryset=Country.objects.all(),
        required=False,
        empty_label=_('All'),
        label=_('Country'),
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )
    specialty = forms.ModelChoiceField(
        queryset=Specialty.objects.all(),
        required=False,
        empty_label=_('All'),
        label=_('Specialty'),
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )
    search_term = forms.CharField(
        required=False,
        label=_('Search Term'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Enter institution name or keyword...'),
            'type': 'search',
        })
    )


class CustomSpecialtyField(forms.ModelMultipleChoiceField):
    """
    Champ personnalisé pour permettre la création de nouvelles spécialités
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.created_specialties = []

    def validate(self, value):
        """
        Validation personnalisée qui permet les nouvelles spécialités
        """
        if self.required and not value:
            raise forms.ValidationError(self.error_messages['required'], code='required')
        
        # On ne fait pas la validation normale pour permettre les nouvelles spécialités
        # La validation se fera dans clean_specialties()

    def clean(self, value):
        """
        Nettoie et traite les valeurs des spécialités
        """
        if not value:
            return []
        
        final_specialties = []
        self.created_specialties = []
        
        for item in value:
            item_str = str(item).strip()
            
            # Ignorer les entrées vides
            if not item_str:
                continue
                
            if item_str.isdigit():
                # Spécialité existante (ID)
                try:
                    specialty = Specialty.objects.get(pk=int(item_str))
                    final_specialties.append(specialty)
                except Specialty.DoesNotExist:
                    continue
            else:
                # Nouvelle spécialité (nom)
                # Vérifier si la spécialité existe déjà (insensible à la casse)
                existing_specialty = Specialty.objects.filter(
                    name__iexact=item_str.lower()
                ).first()
                
                if existing_specialty:
                    final_specialties.append(existing_specialty)
                else:
                    # Validation du nom de la spécialité
                    if len(item_str) < 2:
                        raise forms.ValidationError(
                            _('Le nom de la spécialité doit contenir au moins 2 caractères.')
                        )
                    
                    if len(item_str) > 100:
                        raise forms.ValidationError(
                            _('Le nom de la spécialité ne peut pas dépasser 100 caractères.')
                        )
                    
                    # Créer la nouvelle spécialité
                    specialty, created = Specialty.objects.get_or_create(
                        name=item_str.strip().title()  # Capitaliser le nom
                    )
                    final_specialties.append(specialty)
                    
                    if created:
                        self.created_specialties.append(specialty.name)

        return final_specialties

    def get_created_specialties(self):
        """
        Retourne la liste des spécialités créées
        """
        return self.created_specialties


class InstitutionForm(forms.ModelForm):
    # Définir explicitement les champs pour avoir plus de contrôle
    name = forms.CharField(
        label=_('Nom de l\'institution'), 
        widget=forms.TextInput(attrs={'class': 'form-control', 'required': True})
    )
    acronym = forms.CharField(
        label=_('Sigle'), 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    type = forms.ChoiceField(
        label=_('Type d\'institution'), 
        choices=Institution.TYPE, 
        widget=forms.Select(attrs={'class': 'form-control', 'required': True})
    )
    country = forms.ModelChoiceField(
        label=_('Pays'), 
        queryset=Country.objects.all(), 
        widget=forms.Select(attrs={'class': 'form-control', 'required': True})
    )
    city = forms.CharField(
        label=_('Ville'), 
        widget=forms.TextInput(attrs={'class': 'form-control', 'required': True})
    )
    
    # Utiliser le champ personnalisé
    specialties = CustomSpecialtyField(
        queryset=Specialty.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control select2',
            'data-placeholder': _('Sélectionnez ou ajoutez des spécialités...')
        }),
        label=_('Spécialités')
    )
    
    logo = forms.ImageField(
        label=_('Logo'), 
        required=False, 
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )
    website = forms.URLField(
        label=_('Site web'), 
        required=False, 
        widget=forms.URLInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        label=_('Email'), 
        required=False, 
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    phone = forms.CharField(
        label=_('Téléphone'), 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    address = forms.CharField(
        label=_('Adresse'), 
        required=False, 
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )
    description = forms.CharField(
        label=_('Description'), 
        required=False, 
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5})
    )

    class Meta:
        model = Institution
        fields = [
            'name', 'acronym', 'type', 'country', 'city', 'specialties',
            'logo', 'website', 'email', 'phone', 'address', 'description'
        ]

    def clean(self):
        """
        Validation générale du formulaire.
        """
        cleaned_data = super().clean()
        website = cleaned_data.get('website')
        email = cleaned_data.get('email')
        phone = cleaned_data.get('phone')

        # Au moins un moyen de contact doit être fourni
        if not any([website, email, phone]):
            raise forms.ValidationError(
                _("Veuillez fournir au moins un moyen de contact (site web, email ou téléphone).")
            )

        return cleaned_data

    def save(self, commit=True):
        """
        Sauvegarde personnalisée pour gérer les spécialités.
        """
        instance = super().save(commit=False)
        
        if commit:
            instance.save()
            
            # Gérer les spécialités
            specialties = self.cleaned_data.get('specialties', [])
            instance.specialties.set(specialties)
            
            # Sauvegarder les relations many-to-many
            self.save_m2m()
            
        return instance

    def get_created_specialties(self):
        """
        Retourne la liste des spécialités créées lors de la validation.
        """
        return self.fields['specialties'].get_created_specialties()