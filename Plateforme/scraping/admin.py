import csv
import logging

from django.contrib import admin, messages
from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import ScrapedItemMeta, ScrapingRun, ScrapingSource, ScrapingSourceHealth

try:
    from .selector_discovery import SelectorDiscoveryEngine
except Exception:
    SelectorDiscoveryEngine = None

logger = logging.getLogger(__name__)


class ValidationStatusFilter(admin.SimpleListFilter):
    title = _("Validation")
    parameter_name = "validation_status_filter"

    def lookups(self, request, model_admin):
        return (
            ("red_only", _("Afficher les sources RED")),
            ("green", _("Sources GREEN")),
            ("yellow", _("Sources YELLOW")),
            ("pending", _("Sources PENDING")),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == "red_only":
            return queryset.filter(validation_status="RED")
        if value == "green":
            return queryset.filter(validation_status="GREEN")
        if value == "yellow":
            return queryset.filter(validation_status="YELLOW")
        if value == "pending":
            return queryset.filter(validation_status="PENDING")
        return queryset


@admin.register(ScrapingSource)
class ScrapingSourceAdmin(admin.ModelAdmin):
    actions = ("auto_discover_selectors",)
    list_display = (
        "name",
        "category_badge",
        "base_url",
        "is_active",
        "schedule_tier",
        "schedule_interval_hours",
        "items_per_day_display",
        "use_rss",
        "use_llm_extraction",
        "validation_badge",
        "run_status_badge",
        "last_run_items_created",
        "last_scraped",
        "run_now_button",
    )
    list_filter = (
        "category",
        "is_active",
        "last_run_status",
        "validation_status",
        "use_rss",
        "use_llm_extraction",
        ValidationStatusFilter,
    )
    search_fields = ("name", "base_url")
    readonly_fields = (
        "id",
        "created_at",
        "last_scraped",
        "last_run_status",
        "last_run_error",
        "last_run_items_created",
        "last_validated_at",
        "pretty_validation_detail",
        "manual_validate_button",
        "selector_confidence",
        "selector_image_selector",
        "pretty_selector_recommendations",
    )

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "id",
                    "name",
                    "category",
                    "url",
                    "base_url",
                    "description",
                    "is_active",
                ),
            },
        ),
        (
            _("Scraping Options"),
            {
                "fields": (
                    "use_rss",
                    "use_llm_extraction",
                    "verify_ssl",
                    "proxy_url",
                    "force_playwright",
                    "scrape_config",
                ),
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
            _("Validation"),
            {
                "fields": (
                    "validation_status",
                    "last_validated_at",
                    "pretty_validation_detail",
                    "manual_validate_button",
                ),
            },
        ),
        (
            _("Selector Discovery"),
            {
                "fields": (
                    "selector_confidence",
                    "selector_image_selector",
                    "css_selectors",
                    "pretty_selector_recommendations",
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

    def validation_badge(self, obj):
        colours = {
            "GREEN": "#10b981",
            "YELLOW": "#f59e0b",
            "RED": "#ef4444",
            "PENDING": "#3b82f6",
            "UNKNOWN": "#64748b",
        }
        labels = {
            "GREEN": "GREEN",
            "YELLOW": "YELLOW",
            "RED": "RED",
            "PENDING": "PENDING",
            "UNKNOWN": "UNKNOWN",
        }
        status = obj.validation_status or "UNKNOWN"
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;'
            'border-radius:12px;font-size:11px;">{}</span>',
            colours.get(status, "#64748b"),
            labels.get(status, status),
        )

    validation_badge.short_description = _("Validation")

    def pretty_validation_detail(self, obj):
        detail = obj.validation_detail
        if not detail:
            return "—"
        return format_html(
            '<pre style="white-space:pre-wrap;max-width:850px;">{}</pre>',
            str(detail),
        )

    pretty_validation_detail.short_description = _("Validation Detail")

    def manual_validate_button(self, obj):
        endpoint = reverse("scraping:validate_source")
        return format_html(
            '<button type="button" class="button" '
            'style="background:#0ea5e9;color:#fff;border:none;padding:6px 12px;border-radius:6px;cursor:pointer;" '
            "onclick=\"return runSourceValidation(this, '{url}');\">Tester cette URL</button>"
            '<div id="validation-result" style="margin-top:8px;font-size:12px;"></div>'
            "<script>"
            "function runSourceValidation(el, url) {{"
            "  const urlField = document.getElementById('id_url') || document.getElementById('id_base_url');"
            "  const categoryField = document.getElementById('id_category');"
            "  const resultBox = document.getElementById('validation-result');"
            "  if (!urlField || !categoryField) {{ alert('URL/category fields not found'); return false; }}"
            "  const csrf = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';"
            "  const formData = new FormData();"
            "  formData.append('url', urlField.value || '');"
            "  formData.append('category', categoryField.value || '');"
            "  el.disabled = true; el.textContent = 'Validation...';"
            "  fetch(url, {{method:'POST', headers:{{'X-CSRFToken': csrf}}, body: formData}})"
            "    .then(r => r.json())"
            "    .then(data => {{"
            "      const ok = !!data.valid;"
            "      resultBox.style.color = ok ? '#065f46' : '#991b1b';"
            "      resultBox.textContent = data.message || (ok ? 'Validation OK' : 'Validation failed');"
            "    }})"
            "    .catch(() => {{"
            "      resultBox.style.color = '#991b1b';"
            "      resultBox.textContent = 'Erreur de validation';"
            "    }})"
            "    .finally(() => {{"
            "      el.disabled = false;"
            "      el.textContent = 'Tester cette URL';"
            "    }});"
            "  return false;"
            "}}"
            "</script>",
            url=endpoint,
        )

    manual_validate_button.short_description = _("Validation manuelle")

    def pretty_selector_recommendations(self, obj):
        if not obj.selector_recommendations:
            return "-"
        return format_html(
            '<pre style="white-space:pre-wrap;max-width:850px;">{}</pre>',
            str(obj.selector_recommendations),
        )

    pretty_selector_recommendations.short_description = _("Selector Recommendations")

    def selector_image_selector(self, obj):
        selectors = dict(getattr(obj, "css_selectors", {}) or {})
        return selectors.get("image_selector") or "-"

    selector_image_selector.short_description = _("image_selector")

    def items_per_day_display(self, obj):
        from .adaptive_scheduler import AdaptiveScheduler

        scheduler = AdaptiveScheduler()
        items_per_day = scheduler.estimate_items_per_day(obj.id)
        tier_colors = {
            "very_high": "#22c55e",
            "high": "#84cc16",
            "medium": "#eab308",
            "low": "#f97316",
            "dormant": "#ef4444",
        }
        color = tier_colors.get(obj.schedule_tier, "#888")
        return format_html(
            '<span style="color:{}">{} ({}/day)</span>',
            color,
            obj.schedule_tier,
            items_per_day,
        )

    items_per_day_display.short_description = "Schedule tier"

    @admin.action(description="Auto-discover CSS selectors for selected sources")
    def auto_discover_selectors(self, request, queryset):
        if SelectorDiscoveryEngine is None:
            self.message_user(
                request,
                _("Selector discovery dependencies are not installed in this environment."),
                level=messages.ERROR,
            )
            return

        engine = SelectorDiscoveryEngine()
        results = []

        for source in queryset:
            try:
                source_url = (source.url or source.base_url or "").strip()
                if not source_url:
                    results.append(f"[ERROR] {source.name}: missing URL")
                    continue

                discovery = engine.discover(source_url)
                source.selector_recommendations = discovery["recommendations"]
                source.selector_confidence = discovery["confidence"]
                source.save(
                    update_fields=[
                        "selector_recommendations",
                        "selector_confidence",
                    ]
                )
                results.append(
                    f"[OK] {source.name}: {discovery['confidence']:.0%} confidence"
                )
            except Exception as exc:
                logger.exception("Selector discovery failed for source=%s", source.pk)
                results.append(f"[ERROR] {source.name}: {exc}")

        level = (
            messages.SUCCESS
            if any(msg.startswith("[OK]") for msg in results)
            else messages.WARNING
        )
        self.message_user(request, "\n".join(results), level=level)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.validation_status == "RED":
            self.message_user(
                request,
                _(
                    "Avertissement: cette source est marquee RED, mais la sauvegarde est autorisee."
                ),
                level=messages.WARNING,
            )
        elif obj.validation_status == "PENDING":
            self.message_user(
                request,
                _("Validation en cours. Le statut sera mis a jour automatiquement."),
                level=messages.INFO,
            )

    def response_add(self, request, obj, post_url_continue=None):
        response = super().response_add(request, obj, post_url_continue)
        if obj.validation_status in {"PENDING", "UNKNOWN"}:
            self.message_user(
                request,
                _("Source enregistree. Validation automatique lancee en arriere-plan."),
                level=messages.INFO,
            )
        return response

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context=extra_context)
        red_count = ScrapingSource.objects.filter(validation_status="RED").count()
        if red_count:
            self.message_user(
                request,
                _("Attention: %(count)s source(s) sont en statut RED.")
                % {"count": red_count},
                level=messages.WARNING,
            )
        return response

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
        "source_name",
        "category_badge",
        "primary_domain",
        "score_badge",
        "match_score",
        "enrichment_status",
        "completeness_badge",
        "created_at",
    )
    list_filter = (
        "category",
        "primary_domain",
        "source_name",
        "enrichment_status",
        "was_skipped",
    )
    search_fields = ("item_title", "source_name", "source_url")
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
            except (AttributeError, KeyError, ValueError, TypeError) as exc:
                logger.warning(
                    "admin_reenrich_item_skipped_due_to_error",
                    extra={
                        "error": str(exc),
                        "context": str(meta.pk),
                    },
                    exc_info=False,
                )
                continue

        self.message_user(
            request,
            f"Re-enriched {updated} item(s).",
            level=messages.SUCCESS if updated else messages.WARNING,
        )

    @admin.action(description="Re-download media")
    def redownload_media_selected(self, request, queryset):
        from scraping.file_downloader import (
            attach_file_to_model,
            try_download_document,
            try_download_image,
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
