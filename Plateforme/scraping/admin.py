import csv

from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import ScrapingSource, ScrapingRun, ScrapingSourceHealth, ScrapedItemMeta


@admin.register(ScrapingSource)
class ScrapingSourceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category_badge",
        "base_url",
        "is_active",
        "use_rss",
        "use_llm_extraction",
        "run_status_badge",
        "last_run_items_created",
        "last_scraped",
        "run_now_button",
    )
    list_filter = (
        "category",
        "is_active",
        "last_run_status",
        "use_rss",
        "use_llm_extraction",
    )
    search_fields = ("name", "base_url")
    readonly_fields = (
        "id",
        "created_at",
        "last_scraped",
        "last_run_status",
        "last_run_error",
        "last_run_items_created",
    )

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "id",
                    "name",
                    "category",
                    "base_url",
                    "description",
                    "is_active",
                ),
            },
        ),
        (
            _("Scraping Options"),
            {
                "fields": ("use_rss", "use_llm_extraction", "scrape_config"),
            },
        ),
        (
            _("Last Run Info"),
            {
                "fields": (
                    "last_scraped",
                    "last_run_status",
                    "last_run_items_created",
                    "last_run_error",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Metadata"),
            {
                "fields": ("created_at",),
            },
        ),
    )

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

    def run_status_badge(self, obj):
        colours = {
            "success": "#10b981",
            "failed": "#ef4444",
            "pending": "#f59e0b",
        }
        colour = colours.get(obj.last_run_status, "#64748b")
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;'
            'border-radius:12px;font-size:11px;">{}</span>',
            colour,
            obj.get_last_run_status_display(),
        )

    run_status_badge.short_description = _("Status")

    def run_now_button(self, obj):
        url = reverse("scraping:run_custom_source", args=[obj.pk])
        return format_html(
            '<a class="button" style="background:#6366f1;color:#fff;'
            "padding:4px 12px;border-radius:6px;font-size:11px;"
            'text-decoration:none;cursor:pointer;" '
            "onclick=\"return runCustomSource(this, '{url}');\" "
            'href="#">▶ Run</a>'
            "<script>"
            "function runCustomSource(el, url) {{"
            '  el.textContent = "⏳ Running…";'
            '  fetch(url, {{method:"POST", headers:{{"X-CSRFToken":document.querySelector("[name=csrfmiddlewaretoken]")?.value || ""}} }})'
            "    .then(r => r.json())"
            '    .then(d => {{ el.textContent = d.success ? "✅ " + d.items_created + " items" : "❌ Failed"; }})'
            '    .catch(() => {{ el.textContent = "❌ Error"; }});'
            "  return false;"
            "}}"
            "</script>",
            url=url,
        )

    run_now_button.short_description = _("Action")


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
    actions = ("rerun_selected", "export_results_as_csv")

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

    @admin.action(description="Re-run selected")
    def rerun_selected(self, request, queryset):
        from .tasks import run_scraper_task

        started = 0
        for run in queryset:
            rerun = ScrapingRun.objects.create(
                category=run.category,
                status="running",
                triggered_by=request.user,
            )
            try:
                task = run_scraper_task.delay(
                    run.category,
                    run_id=str(rerun.pk),
                    user_id=request.user.pk,
                )
                rerun.task_id = task.id
                rerun.save(update_fields=["task_id"])
                started += 1
            except Exception as exc:
                rerun.status = "failed"
                rerun.errors = str(exc)
                rerun.save(update_fields=["status", "errors"])

        self.message_user(
            request,
            f"Started {started} re-run task(s).",
            level=messages.SUCCESS if started else messages.WARNING,
        )

    @admin.action(description="Export results as CSV")
    def export_results_as_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="scraping_runs.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "run_id",
                "category",
                "status",
                "items_found",
                "items_created",
                "items_skipped",
                "started_at",
                "completed_at",
                "duration_seconds",
                "errors",
            ]
        )

        for run in queryset.order_by("-started_at"):
            writer.writerow(
                [
                    str(run.id),
                    run.category,
                    run.status,
                    run.items_found,
                    run.items_created,
                    run.items_skipped,
                    run.started_at.isoformat() if run.started_at else "",
                    run.completed_at.isoformat() if run.completed_at else "",
                    run.duration if run.duration is not None else "",
                    run.errors,
                ]
            )
        return response


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
            "</div> <small>{:.0f}%</small>",
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
        "completeness_badge",
        "created_at",
    )
    list_filter = ("category", "primary_domain")
    search_fields = ("item_title",)
    readonly_fields = (
        "id",
        "category",
        "item_title",
        "item_id",
        "domain_scores",
        "primary_domain",
        "relevance_score",
        "completeness_score",
        "created_at",
        "updated_at",
    )
    ordering = ("-relevance_score",)
    actions = ("re_enrich_selected", "redownload_media_selected")

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

    def completeness_badge(self, obj):
        score = obj.completeness_score
        if score >= 80:
            colour = "#10b981"
        elif score >= 50:
            colour = "#f59e0b"
        else:
            colour = "#ef4444"
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;'
            'border-radius:12px;font-size:11px;font-weight:bold;">{:.0f}%</span>',
            colour,
            score,
        )

    completeness_badge.short_description = _("Completeness")

    def _get_model_instance_for_meta(self, meta_obj):
        category_map = {
            "events": ("events.models", "Event"),
            "news": ("QA.models", "Post"),
            "courses": ("resources.models", "Course"),
            "tools": ("resources.models", "NLPTool"),
            "institutions": ("institutions.models", "Institution"),
        }
        module_path, class_name = category_map.get(meta_obj.category, (None, None))
        if not module_path or not class_name or not meta_obj.item_id:
            return None

        try:
            module = __import__(module_path, fromlist=[class_name])
            model_cls = getattr(module, class_name)
            return model_cls.objects.filter(pk=meta_obj.item_id).first()
        except Exception:
            return None

    @admin.action(description="Re-enrich selected")
    def re_enrich_selected(self, request, queryset):
        from scraping.enrichment_engine import enrich_scraped_item

        updated = 0
        for meta in queryset:
            obj = self._get_model_instance_for_meta(meta)
            if obj is None:
                continue

            payload = {
                "title": getattr(obj, "title", "") or getattr(obj, "name", ""),
                "title_en": getattr(obj, "title_en", "") or getattr(obj, "name_en", ""),
                "description": getattr(obj, "description", "")
                or getattr(obj, "content", ""),
                "description_en": getattr(obj, "description_en", "")
                or getattr(obj, "content_en", ""),
                "source_url": getattr(obj, "source_url", ""),
            }
            try:
                enriched = enrich_scraped_item(payload, meta.category)
                if enriched:
                    meta.enrichment_status = "complete"
                    if meta.completeness_score <= 0:
                        meta.completeness_score = 1
                    meta.save(
                        update_fields=[
                            "enrichment_status",
                            "completeness_score",
                            "updated_at",
                        ]
                    )
                    updated += 1
            except Exception:
                continue

        self.message_user(
            request,
            f"Re-enriched {updated} item(s).",
            level=messages.SUCCESS if updated else messages.WARNING,
        )

    @admin.action(description="Re-download media")
    def redownload_media_selected(self, request, queryset):
        from scraping.file_downloader import (
            try_download_document,
            try_download_image,
            attach_file_to_model,
        )

        redownloaded = 0
        for meta in queryset:
            obj = self._get_model_instance_for_meta(meta)
            if obj is None:
                continue

            urls = [
                getattr(obj, "source_url", "") or "",
                getattr(obj, "website", "") or "",
                getattr(obj, "access_link", "") or "",
                getattr(obj, "registration_link", "") or "",
                getattr(obj, "paper_url", "") or "",
                getattr(obj, "demo_url", "") or "",
            ]
            urls = [u for u in urls if u]
            if not urls:
                continue

            item_name = getattr(obj, "title", "") or getattr(obj, "name", "") or "item"
            category = meta.category

            image_content, image_filename = try_download_image(
                urls, category, item_name
            )
            doc_content, doc_filename = try_download_document(urls, category, item_name)

            image_field = None
            for candidate in ("banner_image", "thumbnail", "logo", "image"):
                if hasattr(obj, candidate):
                    image_field = candidate
                    break

            doc_field = None
            for candidate in ("attachment", "uploaded_file", "file"):
                if hasattr(obj, candidate):
                    doc_field = candidate
                    break

            saved_any = False
            if image_field and image_filename:
                saved_any = (
                    attach_file_to_model(
                        obj, image_field, image_content, image_filename
                    )
                    or saved_any
                )
            if doc_field and doc_filename:
                saved_any = (
                    attach_file_to_model(obj, doc_field, doc_content, doc_filename)
                    or saved_any
                )

            if saved_any:
                redownloaded += 1

        self.message_user(
            request,
            f"Re-downloaded media for {redownloaded} item(s).",
            level=messages.SUCCESS if redownloaded else messages.WARNING,
        )
