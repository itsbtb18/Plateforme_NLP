from django.contrib import admin

from .models import AdminActivityLog, ContactMessage, SecurityLog, Stats, UserStatusHistory


@admin.register(AdminActivityLog)
class AdminActivityLogAdmin(admin.ModelAdmin):
    list_display = (
        "occurred_at",
        "admin_user",
        "role_snapshot",
        "action",
        "path",
        "http_method",
        "ip_address",
    )
    list_filter = ("role_snapshot", "http_method", "occurred_at")
    search_fields = ("admin_user__email", "action", "path", "target_type", "target_id", "details", "ip_address")
    ordering = ("-occurred_at",)
    readonly_fields = [f.name for f in AdminActivityLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


admin.site.register(Stats)
admin.site.register(UserStatusHistory)
admin.site.register(ContactMessage)


@admin.register(SecurityLog)
class SecurityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "role", "action", "method", "ip_address", "path")
    list_filter = ("action", "method", "role", "created_at")
    search_fields = ("user__email", "action", "path", "ip_address")
    ordering = ("-created_at",)
