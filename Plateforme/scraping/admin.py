from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import ScrapingSource, ScrapingRun, ScrapingSourceHealth, ScrapedItemMeta


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
        "task_id",
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


@admin.register(ScrapingSourceHealth)
class ScrapingSourceHealthAdmin(admin.ModelAdmin):
    list_display = (
        "source_name",
        "category_badge",
        "health_bar",
        "circuit_badge",
        "consecutive_failures",
        "total_attempts",
        "total_successes",
        "total_failures",
        "avg_response_display",
        "last_attempt_at",
    )
    list_filter = ("category", "circuit_state")
    search_fields = ("source_name", "base_url")
    readonly_fields = (
        "id",
        "total_attempts",
        "total_successes",
        "total_failures",
        "consecutive_failures",
        "health_score",
        "circuit_state",
        "circuit_opened_at",
        "last_attempt_at",
        "last_success_at",
        "last_failure_at",
        "avg_response_time",
        "last_error",
    )
    ordering = ("category", "source_name")

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
            obj.category.title(),
        )

    category_badge.short_description = _("Category")

    def health_bar(self, obj):
        score = obj.health_score
        if score >= 70:
            colour = "#10b981"
        elif score >= 40:
            colour = "#f59e0b"
        else:
            colour = "#ef4444"
        return format_html(
            '<div style="background:#e5e7eb;border-radius:4px;width:80px;height:14px;">'
            '<div style="background:{};width:{}%;height:100%;border-radius:4px;"></div>'
            '</div> <small>{:.0f}%</small>',
            colour,
            min(score, 100),
            score,
        )

    health_bar.short_description = _("Health")

    def circuit_badge(self, obj):
        colours = {
            "closed": "#10b981",
            "open": "#ef4444",
            "half_open": "#f59e0b",
        }
        colour = colours.get(obj.circuit_state, "#64748b")
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;'
            'border-radius:12px;font-size:11px;">{}</span>',
            colour,
            obj.get_circuit_state_display(),
        )

    circuit_badge.short_description = _("Circuit")

    def avg_response_display(self, obj):
        if obj.avg_response_time is None:
            return "—"
        return f"{obj.avg_response_time:.2f}s"

    avg_response_display.short_description = _("Avg Response")


@admin.register(ScrapedItemMeta)
class ScrapedItemMetaAdmin(admin.ModelAdmin):
    list_display = (
        "item_title_short",
        "category_badge",
        "primary_domain",
        "score_badge",
        "created_at",
    )
    list_filter = ("category", "primary_domain")
    search_fields = ("item_title",)
    readonly_fields = (
        "id", "category", "item_title", "item_id",
        "domain_scores", "primary_domain", "relevance_score",
        "created_at", "updated_at",
    )
    ordering = ("-relevance_score",)

    def item_title_short(self, obj):
        return obj.item_title[:80] + ("…" if len(obj.item_title) > 80 else "")

    item_title_short.short_description = _("Title")

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
            obj.category.title(),
        )

    category_badge.short_description = _("Category")

    def score_badge(self, obj):
        score = obj.relevance_score
        if score >= 70:
            colour = "#10b981"
        elif score >= 40:
            colour = "#f59e0b"
        else:
            colour = "#ef4444"
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;'
            'border-radius:12px;font-size:11px;font-weight:bold;">{:.0f}</span>',
            colour,
            score,
        )

    score_badge.short_description = _("Score")
