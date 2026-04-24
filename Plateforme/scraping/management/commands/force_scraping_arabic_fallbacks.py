from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


FALLBACK_MAP: dict[str, str] = {
    "Scraping navigation": "تنقل الاستخراج",
    "Scraping Admin": "إدارة الاستخراج",
    "Pending Queue": "قائمة المراجعة",
    "Toggle menu": "تبديل القائمة",
    "Category:": "الفئة:",
    "Category navigation tabs": "تبويبات تنقل الفئة",
    "Scraping Settings Overview": "نظرة عامة على إعدادات الاستخراج",
    "Category Sources": "مصادر الفئة",
    "Validation Status": "حالة التحقق",
    "Quick Actions": "إجراءات سريعة",
    "Scraping Analytics": "تحليلات الاستخراج",
    "Last 30 days": "آخر 30 يوما",
    "Auto refresh: Off": "التحديث التلقائي: متوقف",
    "Auto refresh: On": "التحديث التلقائي: يعمل",
    "Export CSV": "تصدير CSV",
    "Total Scraped": "إجمالي المستخرج",
    "Scraping": "الاستخراج",
    "Hub": "المركز",
    "Results": "النتائج",
    "Analytics": "التحليلات",
    "Settings": "الإعدادات",
}


def _replace_token(content: str, english: str, arabic: str) -> tuple[str, int]:
    replacements = 0

    # Double-quoted translation tag
    old_double = f'{{% trans "{english}" %}}'
    new_double = (
        f'{{% if scraping_is_rtl %}}{arabic}{{% else %}}'
        f'{{% trans "{english}" %}}'
        f'{{% endif %}}'
    )
    count_double = content.count(old_double)
    if count_double:
        content = content.replace(old_double, new_double)
        replacements += count_double

    # Single-quoted translation tag
    old_single = f"{{% trans '{english}' %}}"
    new_single = (
        f"{{% if scraping_is_rtl %}}{arabic}{{% else %}}"
        f"{{% trans '{english}' %}}"
        f"{{% endif %}}"
    )
    count_single = content.count(old_single)
    if count_single:
        content = content.replace(old_single, new_single)
        replacements += count_single

    return content, replacements


class Command(BaseCommand):
    help = (
        "Enforce Arabic fallback wrappers for common scraping template labels "
        "in one pass."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many replacements would be applied without writing files.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        templates_dir = Path(settings.BASE_DIR) / "templates" / "scraping"
        template_files = sorted(templates_dir.glob("*.html"))

        if not template_files:
            self.stdout.write(self.style.WARNING("No scraping templates found."))
            return

        touched_files = 0
        total_replacements = 0

        for file_path in template_files:
            original = file_path.read_text(encoding="utf-8")
            updated = original
            replacements = 0

            for english, arabic in FALLBACK_MAP.items():
                updated, changed = _replace_token(updated, english, arabic)
                replacements += changed

            if replacements <= 0:
                continue

            touched_files += 1
            total_replacements += replacements

            if not dry_run:
                file_path.write_text(updated, encoding="utf-8")

            self.stdout.write(
                f"{file_path.name}: replacements={replacements}"
            )

        mode = "Dry run" if dry_run else "Applied"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}: files={touched_files}, replacements={total_replacements}"
            )
        )