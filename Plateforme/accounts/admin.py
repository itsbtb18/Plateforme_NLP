from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Institution
from .forms import CustomUserCreationForm, CustomUserChangeForm

class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    
    # Correction 1: Ordonner par email au lieu de username
    ordering = ('email',)
    
    # Correction 2: Champs affichés dans la liste
    list_display = ('email', 'full_name', 'is_staff', 'institution' , 'is_verified')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'institution' , 'is_verified')
    
    # Correction 3: Champs pour l'édition
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Informations personnelles', {'fields': ('full_name', 'institution')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Dates importantes', {'fields': ('last_login', 'date_joined')}),
    )
    
    # Correction 4: Champs pour l'ajout
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 
                'password1', 
                'password2',
                'full_name',
                'institution'
            ),
        }),
    )
    
    # Correction 5: Recherche par email
    search_fields = ('email', 'full_name')
    filter_horizontal = ('groups', 'user_permissions',)

admin.site.register(CustomUser, CustomUserAdmin)
