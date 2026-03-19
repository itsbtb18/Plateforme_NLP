"""
Institutions scraper — source: ROR (Research Organization Registry) API
and OpenAlex API.

Discovers universities and research centres active in NLP / computational
linguistics and stores them as ``institutions.Institution`` instances.
"""

import logging
from .base import BaseScraper
from scraping.enrichment_engine import enrich_scraped_item
from scraping.file_downloader import (
    try_download_image,
    attach_file_to_model,
)
from scraping.field_mapping import calculate_completeness_score

logger = logging.getLogger(__name__)

# Convert list to comma-separated string safely
def _safe_list_to_str(value):
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if v)
    if value is None:
        return ""
    return str(value)

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


import json
import os

def _load_curated_institutions():
    fixture_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'fixtures', 'curated_institutions.json'
    )
    try:
        with open(fixture_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

_institutions_data = _load_curated_institutions()

class InstitutionScraper(BaseScraper):
    """Scrape research institutions from ROR and OpenAlex APIs."""

    name = "NLP Research Institutions"
    category = "institutions"

    def scrape(self):
        self._scrape_ror()
        self._scrape_openalex()
        self._import_algerian_universities()
        self._import_african_nlp_labs()
        self._import_north_african_institutions()
        self._import_arabic_institutions()

    def _create_institution_with_enrichment(
        self,
        *,
        name_en,
        name_ar,
        acronym,
        institution_type,
        country,
        city_en,
        city_ar,
        description_en,
        description_ar,
        website,
        email,
        phone,
        address_en,
        address_ar,
        logo_url,
        research_specialties,
    ):
        from institutions.models import Institution

        item_dict = {
            "name_en": name_en,
            "name_ar": name_ar,
            "acronym": acronym,
            "institution_type": institution_type,
            "country": country,
            "city_en": city_en,
            "city_ar": city_ar,
            "description_en": description_en,
            "description_ar": description_ar,
            "website": website,
            "email": email,
            "phone": phone,
            "address_en": address_en,
            "address_ar": address_ar,
            "logo_url": logo_url,
            "research_specialties": research_specialties,
        }

        item_dict = enrich_scraped_item(item_dict, "institutions")
        completeness = calculate_completeness_score(item_dict, "institutions")

        if completeness < 35:
            self.items_skipped += 1
            return None, item_dict

        is_valid, item_dict, reason = self.validate_and_prepare(
            item_dict, "institutions"
        )
        if not is_valid:
            self.items_skipped += 1
            return None, item_dict

        type_map = {
            "university": "University",
            "research_center": "Research Center",
            "research center": "Research Center",
            "school": "School",
            "other": "Other",
            "University": "University",
            "Research Center": "Research Center",
            "School": "School",
            "Other": "Other",
        }
        model_type = type_map.get(
            str(item_dict.get("institution_type", "university")), "University"
        )

        country_obj = item_dict.get("country")
        if not hasattr(country_obj, "id"):
            country_name = str(country_obj or "Unknown")
            country_obj = self.get_or_create_country(country_name, "XX")

        try:
            institution = Institution.objects.create(
                name=item_dict.get("name_en", "")[:300],
                name_en=item_dict.get("name_en", "")[:300],
                name_ar=item_dict.get("name_ar", "")[:300],
                acronym=item_dict.get("acronym", "")[:20],
                type=model_type,
                country=country_obj,
                city=item_dict.get("city_en", "")[:100],
                city_en=item_dict.get("city_en", "")[:100],
                city_ar=item_dict.get("city_ar", "")[:100],
                description=item_dict.get("description_en", ""),
                description_en=item_dict.get("description_en", ""),
                description_ar=item_dict.get("description_ar", ""),
                website=item_dict.get("website", ""),
                email=item_dict.get("email", ""),
                phone=item_dict.get("phone", ""),
                address=item_dict.get("address_en", ""),
                address_en=item_dict.get("address_en", ""),
                address_ar=item_dict.get("address_ar", ""),
                research_specialties=_safe_list_to_str(item_dict.get("research_specialties", [])),
                approval_status="pending",
                created_by=self.get_system_user(),
            )

            # Try to download institution logo
            logo_url = item_dict.get("logo_url", "")
            if logo_url:
                img_file, filename = try_download_image([logo_url], "institutions")
                if img_file:
                    try:
                        attach_file_to_model(institution, "logo", img_file, filename)
                    except Exception:
                        pass

            return institution, item_dict
        except Exception as exc:
            self.errors.append(
                f"Failed to create institution '{item_dict.get('name_en', name_en)}': {exc}"
            )
            logger.error(
                "Failed to create institution %s: %s",
                item_dict.get("name_en", name_en),
                exc,
            )
            return None, item_dict

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

        name_en = name

        # Duplicate check
        if self.is_duplicate(name_en, "institutions", Institution):
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

        institution, enriched_item = self._create_institution_with_enrichment(
            name_en=name,
            name_ar=name_ar,
            acronym=acronym[:20] if acronym else "",
            institution_type=inst_type,
            country=country,
            city_en=city,
            city_ar=city,
            description_en=description,
            description_ar=description,
            website=website,
            email=email_domain,
            phone="",
            address_en=address,
            address_ar=address,
            logo_url="",
            research_specialties=[],
        )
        if institution is None:
            return

        self.items_created += 1
        self.results.append(
            {
                "title": self.truncate(enriched_item.get("name_en", name), 80),
                "type": inst_type,
                "country": country_name,
                "city": city,
                "url": enriched_item.get("website", website),
            }
        )

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

        name_en = name

        # Duplicate check
        if self.is_duplicate(name_en, "institutions", Institution):
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

        institution, enriched_item = self._create_institution_with_enrichment(
            name_en=name,
            name_ar=name,
            acronym=acronym[:20] if acronym else "",
            institution_type=inst_type,
            country=country,
            city_en=city,
            city_ar=city,
            description_en=description,
            description_ar=description,
            website=homepage,
            email=email_domain,
            phone="",
            address_en=address,
            address_ar=address,
            logo_url="",
            research_specialties=[],
        )
        if institution is None:
            return

        self.items_created += 1
        self.results.append(
            {
                "title": self.truncate(enriched_item.get("name_en", name), 80),
                "type": inst_type,
                "country": country_name,
                "city": city,
                "url": enriched_item.get("website", homepage),
            }
        )

    # ── Algerian Universities ────────────────────────────────────────
    ALGERIAN_UNIVERSITIES = _institutions_data.get('algerian_universities', [])

    def _import_algerian_universities(self):
        """Import curated Algerian universities and research centres."""
        from institutions.models import Institution

        dz_country = self.get_or_create_country("Algeria", "DZ", name_ar="الجزائر")

        for item in self.ALGERIAN_UNIVERSITIES:
            name = item["name"]
            name_en = name
            if self.is_duplicate(name_en, "institutions", Institution):
                self.items_skipped += 1
                continue

            city = item.get("city", "")
            address = f"{city}, Algeria" if city else "Algeria"

            institution, enriched_item = self._create_institution_with_enrichment(
                name_en=name,
                name_ar=item.get("name_ar", name),
                acronym=item.get("acronym", "")[:20],
                institution_type=item.get("type", "University"),
                country=dz_country,
                city_en=city,
                city_ar=item.get("city_ar", city),
                description_en=item.get("description", ""),
                description_ar=item.get("description", ""),
                website=item.get("website", ""),
                email=item.get("email", ""),
                phone=item.get("phone", ""),
                address_en=address,
                address_ar=f"{item.get('city_ar', city)}، الجزائر",
                logo_url=item.get("logo_url", ""),
                research_specialties=item.get("research_specialties", []),
            )
            if institution is None:
                continue

            self.items_created += 1
            self.results.append(
                {
                    "title": self.truncate(enriched_item.get("name_en", name), 80),
                    "type": item.get("type", "University"),
                    "country": "Algeria",
                    "city": city,
                    "url": enriched_item.get("website", item.get("website", "")),
                }
            )

    # ── African NLP Labs & Arabic-speaking Institutions ──────────────
    AFRICAN_NLP_LABS = _institutions_data.get('african_nlp_labs', [])

    def _import_african_nlp_labs(self):
        """Import curated African and Arabic-speaking NLP institutions."""
        from institutions.models import Institution

        for item in self.AFRICAN_NLP_LABS:
            name = item["name"]
            name_en = name
            if self.is_duplicate(name_en, "institutions", Institution):
                self.items_skipped += 1
                continue

            country = self.get_or_create_country(
                item["country_name"],
                item["country_code"],
            )
            city = item.get("city", "")
            address = (
                f"{city}, {item['country_name']}" if city else item["country_name"]
            )

            institution, enriched_item = self._create_institution_with_enrichment(
                name_en=name,
                name_ar=item.get("name_ar", name),
                acronym=item.get("acronym", "")[:20],
                institution_type=item.get("type", "University"),
                country=country,
                city_en=city,
                city_ar=city,
                description_en=item.get("description", ""),
                description_ar=item.get("description", ""),
                website=item.get("website", ""),
                email=item.get("email", ""),
                phone=item.get("phone", ""),
                address_en=address,
                address_ar=address,
                logo_url=item.get("logo_url", ""),
                research_specialties=item.get("research_specialties", []),
            )
            if institution is None:
                continue

            self.items_created += 1
            self.results.append(
                {
                    "title": self.truncate(enriched_item.get("name_en", name), 80),
                    "type": item.get("type", "University"),
                    "country": item["country_name"],
                    "city": city,
                    "url": enriched_item.get("website", item.get("website", "")),
                }
            )

    # ── North African Institutions (Morocco, Tunisia, Libya, Egypt) ──
    NORTH_AFRICAN_INSTITUTIONS = _institutions_data.get('north_african_institutions', [])

    # ── Arabic/Gulf Institutions ─────────────────────────────────────
    ARABIC_INSTITUTIONS = _institutions_data.get('arabic_institutions', [])

    def _import_north_african_institutions(self):
        """Import curated North African NLP institutions."""
        from institutions.models import Institution

        for item in self.NORTH_AFRICAN_INSTITUTIONS:
            name = item["name"]
            name_en = name
            if self.is_duplicate(name_en, "institutions", Institution):
                self.items_skipped += 1
                continue

            country = self.get_or_create_country(
                item["country_name"],
                item["country_code"],
            )
            city = item.get("city", "")
            address = (
                f"{city}, {item['country_name']}" if city else item["country_name"]
            )

            institution, enriched_item = self._create_institution_with_enrichment(
                name_en=name,
                name_ar=item.get("name_ar", name),
                acronym=item.get("acronym", "")[:20],
                institution_type=item.get("type", "University"),
                country=country,
                city_en=city,
                city_ar=city,
                description_en=item.get("description", ""),
                description_ar=item.get("description", ""),
                website=item.get("website", ""),
                email=item.get("email", ""),
                phone=item.get("phone", ""),
                address_en=address,
                address_ar=address,
                logo_url=item.get("logo_url", ""),
                research_specialties=item.get("research_specialties", []),
            )
            if institution is None:
                continue

            self.items_created += 1
            self.results.append(
                {
                    "title": self.truncate(enriched_item.get("name_en", name), 80),
                    "type": item.get("type", "University"),
                    "country": item["country_name"],
                    "city": city,
                    "url": enriched_item.get("website", item.get("website", "")),
                }
            )

    def _import_arabic_institutions(self):
        """Import curated Arabic/Gulf NLP institutions."""
        from institutions.models import Institution

        for item in self.ARABIC_INSTITUTIONS:
            name = item["name"]
            name_en = name
            if self.is_duplicate(name_en, "institutions", Institution):
                self.items_skipped += 1
                continue

            country = self.get_or_create_country(
                item["country_name"],
                item["country_code"],
            )
            city = item.get("city", "")
            address = (
                f"{city}, {item['country_name']}" if city else item["country_name"]
            )

            validation_item = {
                "name_en": name,
            }
            is_valid, validation_item, reason = self.validate_and_prepare(
                validation_item, "institutions"
            )
            if not is_valid:
                self.items_skipped += 1
                logger.debug(
                    "Skipping institution '%s' due to validation: %s", name, reason
                )
                continue
            name = validation_item.get("name_en") or name

            institution, enriched_item = self._create_institution_with_enrichment(
                name_en=name,
                name_ar=item.get("name_ar", name),
                acronym=item.get("acronym", "")[:20],
                institution_type=item.get("type", "University"),
                country=country,
                city_en=city,
                city_ar=city,
                description_en=item.get("description", ""),
                description_ar=item.get("description", ""),
                website=item.get("website", ""),
                email=item.get("email", ""),
                phone=item.get("phone", ""),
                address_en=address,
                address_ar=address,
                logo_url=item.get("logo_url", ""),
                research_specialties=item.get("research_specialties", []),
            )
            if institution is None:
                continue

            self.items_created += 1
            self.results.append(
                {
                    "title": self.truncate(enriched_item.get("name_en", name), 80),
                    "type": item.get("type", "University"),
                    "country": item["country_name"],
                    "city": city,
                    "url": enriched_item.get("website", item.get("website", "")),
                }
            )
