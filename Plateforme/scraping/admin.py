from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import ScrapingSource, ScrapingRun


@admin.register(ScrapingSource)
class ScrapingSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "category_badge", "base_url", "is_active", "last_scraped")
    list_filter = ("category", "is_active")
    search_fields = ("name", "base_url")
    readonly_fields = ("id", "created_at", "last_scraped")

    def category_badge(self, obj):
        colours = {
            "events": "#6366f1",
            "tools": "#10b981",
            "news": "#f59e0b",
            "courses": "#3b82f6",
            "institutions": "#8b5cf6",
        }
        colour = colours.get(obj.category, "#64748b")
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;'
            'border-radius:12px;font-size:11px;">{}</span>',
            colour,
            obj.get_category_display(),
        )

    category_badge.short_description = _("Category")


@admin.register(ScrapingRun)
class ScrapingRunAdmin(admin.ModelAdmin):
    list_display = (
        "category",
        "status_badge",
        "items_found",
        "items_created",
        "items_skipped",
        "started_at",
        "duration_display",
        "triggered_by",
    )
    list_filter = ("category", "status")
    readonly_fields = (
        "id",
        "category",
        "status",
        "items_found",
        "items_created",
        "items_skipped",
        "errors",
        "started_at",
        "completed_at",
        "triggered_by",
    )
    ordering = ("-started_at",)

    def status_badge(self, obj):
        colours = {
            "running": "#f59e0b",
            "completed": "#10b981",
            "failed": "#ef4444",
        }
        colour = colours.get(obj.status, "#64748b")
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;'
            'border-radius:12px;font-size:11px;">{}</span>',
            colour,
            obj.get_status_display(),
        )

    status_badge.short_description = _("Status")

    def duration_display(self, obj):
        d = obj.duration
        if d is None:
            return "—"
        return f"{d:.1f}s"

    duration_display.short_description = _("Duration")
