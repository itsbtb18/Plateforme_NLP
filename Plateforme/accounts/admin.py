from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import CustomUser, Institution
from .two_factor_models import TwoFactorAuth
from .forms import CustomUserCreationForm, CustomUserChangeForm

class TwoFactorAuthAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_enabled', 'created_at', 'updated_at')
    list_filter = ('is_enabled', 'created_at')
    search_fields = ('user__email', 'user__full_name')
    readonly_fields = ('id', 'created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('user', 'is_enabled')
        }),
        ('Backup Codes', {
            'fields': ('backup_codes',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser

    # Order by email instead of username
    ordering = ('email',)

    # Fields displayed in list
    list_display = ('email', 'get_localized_name', 'is_staff', 'institution', 'is_verified', 'status')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'institution', 'is_verified', 'status')

    # Fields for editing
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal Information'), {
            'fields': ('full_name', 'institution', 'bio', 'avatar', 'speciality')
        }),
        (_('Bilingual Name Fields'), {
            'fields': ('full_name_ar', 'full_name_en', 'bio_ar', 'bio_en'),
            'classes': ('collapse',),
            'description': _('Arabic and English versions of name and bio.')
        }),
        (_('Social Links'), {
            'fields': ('linkedin_url', 'twitter_url', 'facebook_url'),
            'classes': ('collapse',),
        }),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'is_verified', 'is_email_verified',
                      'status', 'groups', 'user_permissions'),
        }),
        (_('Important Dates'), {'fields': ('last_login', 'date_joined')}),
    )

    # Fields for adding new user
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email',
                'password1',
                'password2',
                'full_name',
                'full_name_ar',
                'full_name_en',
                'institution'
            ),
        }),
    )

    # Search by email
    search_fields = ('email', 'full_name', 'full_name_ar', 'full_name_en')
    filter_horizontal = ('groups', 'user_permissions',)

    def get_localized_name(self, obj):
        """Display the localized full name."""
        return obj.get_localized_full_name()
    get_localized_name.short_description = _('Full Name')


admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(TwoFactorAuth, TwoFactorAuthAdmin)
