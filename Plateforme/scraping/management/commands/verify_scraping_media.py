import os

from django.core.management.base import BaseCommand

from events.models import Event
from institutions.models import Institution
from QA.models import Post
from resources.models import Course, NLPTool
from scraping.file_downloader import attach_file_to_model


class Command(BaseCommand):
    help = "Verify scraping media file references and optionally re-download missing files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--redownload",
            action="store_true",
            help="Attempt to re-download missing media files.",
        )

    def handle(self, *args, **options):
        redownload = bool(options.get("redownload"))

        checks = [
            (
                "events",
                Event.objects.all(),
                [("banner_image", "image"), ("attachment", "pdf")],
            ),
            ("tools", NLPTool.objects.all(), [("thumbnail", "image")]),
            ("news", Post.objects.all(), [("thumbnail", "image"), ("file", "pdf")]),
            (
                "courses",
                Course.objects.all(),
                [("thumbnail", "image"), ("uploaded_file", "pdf")],
            ),
            ("institutions", Institution.objects.all(), [("logo", "image")]),
        ]

        missing_total = 0
        checked_total = 0
        redownloaded_total = 0

        for category, queryset, media_fields in checks:
            self.stdout.write(self.style.NOTICE(f"Checking category: {category}"))

            for obj in queryset.iterator():
                checked_total += 1
                missing_fields = []

                for field_name, _kind in media_fields:
                    file_obj = getattr(obj, field_name, None)
                    file_name = getattr(file_obj, "name", "") if file_obj else ""
                    if not file_name:
                        continue
                    try:
                        file_path = getattr(file_obj, "path", "")
                    except Exception:
                        file_path = ""

                    if not file_path or not os.path.exists(file_path):
                        missing_fields.append(field_name)

                if not missing_fields:
                    continue

                missing_total += len(missing_fields)
                self.stdout.write(
                    self.style.WARNING(
                        f"Missing media for {category} id={obj.pk}: {', '.join(missing_fields)}"
                    )
                )

                if not redownload:
                    continue

                redownloaded = self._try_redownload(category, obj, missing_fields)
                redownloaded_total += redownloaded

        self.stdout.write(
            self.style.SUCCESS(
                f"Verification completed. Checked={checked_total}, missing={missing_total}, redownloaded={redownloaded_total}"
            )
        )

    def _try_redownload(self, category: str, obj, missing_fields: list[str]) -> int:
        scraper = self._build_scraper(category)
        if scraper is None:
            return 0

        item_data = self._build_item_data(category, obj)
        item_data = scraper._download_media(item_data, category)

        redownloaded = 0
        for field_name in missing_fields:
            if field_name in {"banner_image", "thumbnail", "logo"}:
                local_path = item_data.get("image_local_path") or ""
                content_file = item_data.get("image_content_file")
            else:
                local_path = item_data.get("pdf_local_path") or ""
                content_file = item_data.get("pdf_content_file")

            if not local_path:
                continue

            try:
                attached = attach_file_to_model(
                    obj, field_name, content_file, local_path
                )
                if attached:
                    redownloaded += 1
            except Exception:
                continue

        return redownloaded

    @staticmethod
    def _build_scraper(category: str):
        try:
            if category == "events":
                from scraping.scrapers.events import EventScraper

                return EventScraper()
            if category == "tools":
                from scraping.scrapers.tools import ToolScraper

                return ToolScraper()
            if category == "news":
                from scraping.scrapers.news import NewsScraper

                return NewsScraper()
            if category == "courses":
                from scraping.scrapers.courses import CourseScraper

                return CourseScraper()
            if category == "institutions":
                from scraping.scrapers.institutions import InstitutionScraper

                return InstitutionScraper()
        except Exception:
            return None
        return None

    @staticmethod
    def _build_item_data(category: str, obj) -> dict:
        if category == "events":
            return {
                "title_en": getattr(obj, "title_en", "") or getattr(obj, "title", ""),
                "website": getattr(obj, "website", ""),
                "source_url": getattr(obj, "source_url", ""),
                "banner_image_url": "",
                "pdf_attachments": [],
            }

        if category == "tools":
            return {
                "title_en": getattr(obj, "title_en", "") or getattr(obj, "title", ""),
                "access_link": getattr(obj, "access_link", ""),
                "source_url": getattr(obj, "source_url", ""),
                "documentation_pdf_url": getattr(obj, "paper_url", "")
                or getattr(obj, "documentation_link", ""),
                "github_url": getattr(obj, "github_url", ""),
                "thumbnail_url": "",
            }

        if category == "news":
            return {
                "title_en": getattr(obj, "title_en", "") or getattr(obj, "title", ""),
                "source_url": getattr(obj, "source_url", ""),
                "arxiv_id": getattr(obj, "arxiv_id", ""),
                "pdf_url": "",
                "thumbnail_url": "",
            }

        if category == "courses":
            return {
                "title_en": getattr(obj, "title_en", "") or getattr(obj, "title", ""),
                "course_url": getattr(obj, "access_link", ""),
                "source_url": getattr(obj, "source_url", ""),
                "thumbnail_url": "",
                "syllabus_file_url": "",
            }

        if category == "institutions":
            return {
                "name_en": getattr(obj, "name_en", "") or getattr(obj, "name", ""),
                "website": getattr(obj, "website", ""),
                "source_url": getattr(obj, "source_url", ""),
                "logo_url": "",
            }

        return {}
