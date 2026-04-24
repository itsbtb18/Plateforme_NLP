from __future__ import annotations

from django.core.management.base import BaseCommand

from scraping.models import DiscoveredURL


class Command(BaseCommand):
    help = (
        "Prioritize discovered URLs for the next scraping run based on target keywords "
        "like 2026/2027, Call for Papers, and Conference."
    )

    KEYWORDS = ("2026", "2027", "call for papers", "conference")

    def add_arguments(self, parser):
        parser.add_argument(
            "--category", default="events", help="Category to prioritize"
        )
        parser.add_argument(
            "--limit", type=int, default=50, help="How many rows to score"
        )

    def handle(self, *args, **options):
        category = str(options.get("category") or "events").strip()
        limit = max(1, int(options.get("limit") or 50))

        queryset = DiscoveredURL.objects.filter(
            category=category,
            status="pending",
        )
        rows = list(queryset.order_by("-last_discovered_at")[:limit])

        if not rows:
            self.stdout.write(
                self.style.WARNING("No discovered URLs found to prioritize.")
            )
            return

        updated = 0
        for row in rows:
            text_blob = " ".join(
                [
                    str(row.url or ""),
                    str(row.section_label or ""),
                    " ".join(str(v) for v in (row.keywords_hit or [])),
                ]
            ).lower()

            matched = [kw for kw in self.KEYWORDS if kw in text_blob]
            score = 10 + (len(matched) * 25) + min(int(row.times_seen or 0), 10)

            row.priority_score = score
            row.keywords_hit = sorted(
                set([str(v).lower() for v in (row.keywords_hit or [])] + matched)
            )
            row.save(
                update_fields=["priority_score", "keywords_hit", "last_discovered_at"]
            )
            updated += 1

        top = list(
            DiscoveredURL.objects.filter(
                category=category,
                status="pending",
            ).order_by("-priority_score", "-times_seen", "-last_discovered_at")[:10]
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Prioritized {updated} discovered URL(s) for category '{category}'."
            )
        )
        self.stdout.write("Top queue for next run:")
        for idx, row in enumerate(top, start=1):
            self.stdout.write(
                f"{idx:02d}. score={row.priority_score:>3} seen={row.times_seen:>2} url={row.url}"
            )
