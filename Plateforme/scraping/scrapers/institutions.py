"""
Institutions scraper — source: ROR (Research Organization Registry) API
and OpenAlex API.

Discovers universities and research centres active in NLP / computational
linguistics and stores them as ``institutions.Institution`` instances.
"""

import logging
from .base import BaseScraper

logger = logging.getLogger(__name__)

# Map ROR / OpenAlex institution types → platform's Institution.type choices
TYPE_MAP = {
    "Education": "University",
    "education": "University",
    "Facility": "Research Center",
    "facility": "Research Center",
    "Company": "Other",
    "company": "Other",
    "Nonprofit": "Other",
    "nonprofit": "Other",
    "Government": "Other",
    "government": "Other",
    "Healthcare": "Other",
    "healthcare": "Other",
    "Archive": "Other",
    "archive": "Other",
    "Other": "Other",
}


class InstitutionScraper(BaseScraper):
    """Scrape research institutions from ROR and OpenAlex APIs."""

    name = "NLP Research Institutions"
    category = "institutions"

    def scrape(self):
        self._scrape_ror()
        self._scrape_openalex()

    # ── ROR API ──────────────────────────────────────────────────────
    def _scrape_ror(self):
        """Search the Research Organization Registry for NLP-active institutions."""
        queries = [
            "natural language processing",
            "computational linguistics",
            "Arabic NLP",
            "artificial intelligence",
        ]
        seen_ids = set()

        for query in queries:
            url = "https://api.ror.org/organizations"
            params = {"query": query, "page": 1}
            resp = self.safe_request(url, params=params)
            if resp is None:
                continue

            try:
                data = resp.json()
                items = data.get("items", [])

                for item in items:
                    ror_id = item.get("id", "")
                    if ror_id in seen_ids:
                        continue
                    seen_ids.add(ror_id)
                    self._process_ror_item(item)

            except Exception as exc:
                self.errors.append(f"ROR API error for '{query}': {exc}")

    def _process_ror_item(self, item: dict):
        """Create an Institution from a ROR API result (v2 format)."""
        from institutions.models import Institution

        # Extract display name from 'names' array (v2 format)
        names_list = item.get("names", [])
        name = ""
        name_ar = ""
        acronym = ""
        for n in names_list:
            n_types = n.get("types", [])
            if "ror_display" in n_types or "label" in n_types:
                lang = n.get("lang")
                if lang in ("en", None):
                    name = n.get("value", "")
                elif lang == "ar":
                    name_ar = n.get("value", "")
            if "acronym" in n_types:
                acronym = n.get("value", "")
        if not name and names_list:
            name = names_list[0].get("value", "")
        if not name:
            return
        if not name_ar:
            name_ar = name

        # Duplicate check
        if Institution.objects.filter(name_en__iexact=name).exists():
            self.items_skipped += 1
            return

        # Country & city from 'locations' array (v2 format)
        locations = item.get("locations", [])
        country_name = "Unknown"
        country_code = "XX"
        city = ""
        if locations:
            geo = locations[0].get("geonames_details", {})
            country_name = geo.get("country_name", "Unknown")
            country_code = geo.get("country_code", "XX") or "XX"
            city = geo.get("name", "")
        country = self.get_or_create_country(country_name, country_code)

        # Type
        types = item.get("types", [])
        inst_type = "University"
        for t in types:
            if t in TYPE_MAP:
                inst_type = TYPE_MAP[t]
                break

        # Website & Wikipedia from 'links' array (v2 format)
        links_list = item.get("links", [])
        website = ""
        wikipedia = ""
        for link in links_list:
            if link.get("type") == "website":
                website = link.get("value", "")
            elif link.get("type") == "wikipedia":
                wikipedia = link.get("value", "")

        # Build detailed description
        description_parts = [
            f"{name} is a {inst_type.lower()} located in {city}, {country_name}."
            if city
            else f"{name} is a {inst_type.lower()} based in {country_name}.",
        ]
        if acronym:
            description_parts.append(f"Also known as {acronym}.")
        description_parts.append(
            "Active in research areas including natural language processing "
            "and computational linguistics."
        )
        if wikipedia:
            description_parts.append(f"More information: {wikipedia}")
        description = " ".join(description_parts)

        # Build address from location data
        address = f"{city}, {country_name}" if city else country_name

        # Extract email from 'links' if available
        email_domain = ""
        if website:
            # Derive contact email from website domain
            import re as _re

            domain_match = _re.search(r"https?://(?:www\.)?([^/]+)", website)
            if domain_match:
                email_domain = f"info@{domain_match.group(1)}"

        try:
            Institution.objects.create(
                name=name,
                name_en=name,
                name_ar=name_ar,
                acronym=acronym[:20] if acronym else "",
                type=inst_type,
                country=country,
                city=city,
                city_en=city,
                city_ar=city,
                website=website,
                email=email_domain,
                phone="",
                address=address,
                address_en=address,
                address_ar=address,
                description=description,
                description_en=description,
                description_ar=description,
                created_by=self.get_system_user(),
            )
            self.items_created += 1
            self.results.append(
                {
                    "title": self.truncate(name, 80),
                    "type": inst_type,
                    "country": country_name,
                    "city": city,
                    "url": website,
                }
            )
        except Exception as exc:
            self.errors.append(f"Failed to create institution '{name}': {exc}")
            logger.error("Failed to create institution %s: %s", name, exc)

    # ── OpenAlex API ─────────────────────────────────────────────────
    def _scrape_openalex(self):
        """Search OpenAlex for institutions with NLP research output."""
        # Concept ID for NLP in OpenAlex
        url = "https://api.openalex.org/institutions"
        params = {
            "search": "natural language processing arabic",
            "per_page": 15,
            "mailto": "platform@nlp-research.org",
        }
        resp = self.safe_request(url, params=params)
        if resp is None:
            return

        try:
            data = resp.json()
            results_list = data.get("results", [])

            for item in results_list:
                self._process_openalex_item(item)

        except Exception as exc:
            self.errors.append(f"OpenAlex API error: {exc}")

    def _process_openalex_item(self, item: dict):
        """Create an Institution from an OpenAlex API result."""
        from institutions.models import Institution

        name = item.get("display_name", "")
        if not name:
            return

        # Duplicate check
        if Institution.objects.filter(name_en__iexact=name).exists():
            self.items_skipped += 1
            return

        # Country
        geo = item.get("geo", {})
        country_code = geo.get("country_code", "XX") or "XX"
        country_name = geo.get("country", country_code)
        country = self.get_or_create_country(country_name, country_code)

        city = geo.get("city", "")

        # Type
        inst_type_raw = item.get("type", "education")
        inst_type = TYPE_MAP.get(inst_type_raw, "University")

        # Website
        homepage = item.get("homepage_url", "")

        # Acronym from display_name_acronyms
        acronyms = item.get("display_name_acronyms", [])
        acronym = acronyms[0] if acronyms else ""

        # Works count for description
        works_count = item.get("works_count", 0)
        cited_by = item.get("cited_by_count", 0)

        # Build detailed description
        description_parts = [
            f"{name} is a {inst_type.lower()} located in {city}, {country_name}."
            if city
            else f"{name} is a {inst_type.lower()} based in {country_name}.",
        ]
        if works_count:
            description_parts.append(
                f"It has {works_count:,} publications and {cited_by:,} citations "
                f"indexed in OpenAlex."
            )
        description_parts.append(
            "Active in research areas including natural language processing."
        )
        description = " ".join(description_parts)

        # Build address from geo data
        address = f"{city}, {country_name}" if city else country_name

        # Derive contact email from homepage domain
        email_domain = ""
        if homepage:
            import re as _re

            domain_match = _re.search(r"https?://(?:www\.)?([^/]+)", homepage)
            if domain_match:
                email_domain = f"info@{domain_match.group(1)}"

        try:
            Institution.objects.create(
                name=name,
                name_en=name,
                name_ar=name,
                acronym=acronym[:20] if acronym else "",
                type=inst_type,
                country=country,
                city=city,
                city_en=city,
                city_ar=city,
                website=homepage,
                email=email_domain,
                phone="",
                address=address,
                address_en=address,
                address_ar=address,
                description=description,
                description_en=description,
                description_ar=description,
                created_by=self.get_system_user(),
            )
            self.items_created += 1
            self.results.append(
                {
                    "title": self.truncate(name, 80),
                    "type": inst_type,
                    "country": country_name,
                    "city": city,
                    "url": homepage,
                }
            )
        except Exception as exc:
            self.errors.append(f"Failed to create institution '{name}': {exc}")
            logger.error("Failed to create institution %s: %s", name, exc)
