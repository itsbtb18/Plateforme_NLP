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
        self._import_algerian_universities()
        self._import_african_nlp_labs()
        self._import_north_african_institutions()
        self._import_arabic_institutions()

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

    # ── Algerian Universities ────────────────────────────────────────
    ALGERIAN_UNIVERSITIES = [
        {
            "name": "University of Science and Technology Houari Boumediene",
            "name_ar": "جامعة هواري بومدين للعلوم والتكنولوجيا",
            "acronym": "USTHB",
            "city": "Algiers",
            "city_ar": "الجزائر",
            "website": "https://www.usthb.dz",
            "description": (
                "Algeria's premier science and technology university, "
                "with active research in computer science, AI, and NLP. "
                "Hosts LRIA (Lab for Research in AI) with Arabic NLP focus."
            ),
        },
        {
            "name": "University of Algiers 1 Benyoucef Benkhedda",
            "name_ar": "جامعة الجزائر 1 بن يوسف بن خدة",
            "acronym": "UNIV-ALGER1",
            "city": "Algiers",
            "city_ar": "الجزائر",
            "website": "https://www.univ-alger.dz",
            "description": (
                "One of Algeria's oldest and most prestigious universities, "
                "with departments in computer science and linguistics."
            ),
        },
        {
            "name": "University of Oran 1 Ahmed Ben Bella",
            "name_ar": "جامعة وهران 1 أحمد بن بلة",
            "acronym": "UNIV-ORAN1",
            "city": "Oran",
            "city_ar": "وهران",
            "website": "https://www.univ-oran1.dz",
            "description": (
                "Major western Algerian university with computer science "
                "and AI research programs. Active in Arabic text processing."
            ),
        },
        {
            "name": "University of Constantine 1 Frères Mentouri",
            "name_ar": "جامعة قسنطينة 1 الإخوة منتوري",
            "acronym": "UMC1",
            "city": "Constantine",
            "city_ar": "قسنطينة",
            "website": "https://www.umc.edu.dz",
            "description": (
                "Leading eastern Algerian university with research in "
                "information systems, AI, and Arabic language processing."
            ),
        },
        {
            "name": "École nationale Supérieure d'Informatique",
            "name_ar": "المدرسة الوطنية العليا للإعلام الآلي",
            "acronym": "ESI",
            "city": "Algiers",
            "city_ar": "الجزائر",
            "website": "https://www.esi.dz",
            "description": (
                "Algeria's top CS engineering school (formerly INI). "
                "Research labs active in ML, NLP, and Arabic text mining."
            ),
        },
        {
            "name": "University of Tlemcen Abou Bekr Belkaïd",
            "name_ar": "جامعة تلمسان أبو بكر بلقايد",
            "acronym": "UNIV-TLEMCEN",
            "city": "Tlemcen",
            "city_ar": "تلمسان",
            "website": "https://www.univ-tlemcen.dz",
            "description": (
                "Major Algerian university active in Arabic NLP, "
                "machine translation, and information retrieval."
            ),
        },
        {
            "name": "University of Béjaïa Abderrahmane Mira",
            "name_ar": "جامعة بجاية عبد الرحمان ميرة",
            "acronym": "UNIV-BEJAIA",
            "city": "Béjaïa",
            "city_ar": "بجاية",
            "website": "https://www.univ-bejaia.dz",
            "description": (
                "Kabylie region university with research in multilingual NLP "
                "including Arabic, Amazigh, and French text processing."
            ),
        },
        {
            "name": "University of Batna 2 Mostefa Ben Boulaïd",
            "name_ar": "جامعة باتنة 2 مصطفى بن بولعيد",
            "acronym": "UNIV-BATNA2",
            "city": "Batna",
            "city_ar": "باتنة",
            "website": "https://www.univ-batna2.dz",
            "description": (
                "University in the Aures region with ICT and CS programs "
                "contributing to Arabic language technology."
            ),
        },
        {
            "name": "University of Blida 1 Saad Dahlab",
            "name_ar": "جامعة البليدة 1 سعد دحلب",
            "acronym": "UNIV-BLIDA1",
            "city": "Blida",
            "city_ar": "البليدة",
            "website": "https://www.univ-blida.dz",
            "description": (
                "Algerian university near Algiers with CS and AI research, "
                "including Arabic sentiment analysis and text classification."
            ),
        },
        {
            "name": "Centre de Recherche sur l'Information Scientifique et Technique",
            "name_ar": "مركز البحث في الإعلام العلمي والتقني",
            "acronym": "CERIST",
            "city": "Algiers",
            "city_ar": "الجزائر",
            "website": "https://www.cerist.dz",
            "description": (
                "Algeria's national research center for scientific and "
                "technical information. Active in NLP, Arabic IR, and text mining."
            ),
            "type": "Research Center",
        },
    ]

    def _import_algerian_universities(self):
        """Import curated Algerian universities and research centres."""
        from institutions.models import Institution

        dz_country = self.get_or_create_country("Algeria", "DZ", name_ar="الجزائر")

        for item in self.ALGERIAN_UNIVERSITIES:
            name = item["name"]
            if Institution.objects.filter(name_en__iexact=name).exists():
                self.items_skipped += 1
                continue

            city = item.get("city", "")
            address = f"{city}, Algeria" if city else "Algeria"

            try:
                Institution.objects.create(
                    name=name,
                    name_en=name,
                    name_ar=item.get("name_ar", name),
                    acronym=item.get("acronym", "")[:20],
                    type=item.get("type", "University"),
                    country=dz_country,
                    city=city,
                    city_en=city,
                    city_ar=item.get("city_ar", city),
                    website=item.get("website", ""),
                    address=address,
                    address_en=address,
                    address_ar=f"{item.get('city_ar', city)}، الجزائر",
                    description=item.get("description", ""),
                    description_en=item.get("description", ""),
                    description_ar=item.get("description", ""),
                    created_by=self.get_system_user(),
                )
                self.items_created += 1
                self.results.append({
                    "title": self.truncate(name, 80),
                    "type": item.get("type", "University"),
                    "country": "Algeria",
                    "city": city,
                    "url": item.get("website", ""),
                })
            except Exception as exc:
                self.errors.append(f"Failed to create institution '{name}': {exc}")
                logger.error("Failed to create institution %s: %s", name, exc)

    # ── African NLP Labs & Arabic-speaking Institutions ──────────────
    AFRICAN_NLP_LABS = [
        {
            "name": "Masakhane NLP",
            "name_ar": "مساخاني للمعالجة اللغوية",
            "acronym": "MASAKHANE",
            "city": "Pan-African",
            "country_code": "ZA",
            "country_name": "South Africa",
            "website": "https://www.masakhane.io",
            "type": "Research Center",
            "description": (
                "Grassroots community of African NLP researchers building "
                "datasets, models, and tools for African languages."
            ),
        },
        {
            "name": "InstaDeep AI Lab",
            "name_ar": "إنستاديب مختبر الذكاء الاصطناعي",
            "acronym": "INSTADEEP",
            "city": "Tunis",
            "country_code": "TN",
            "country_name": "Tunisia",
            "website": "https://www.instadeep.com",
            "type": "Research Center",
            "description": (
                "Tunisian-founded AI research lab working on decision-making AI, "
                "NLP, and biological sequence processing."
            ),
        },
        {
            "name": "Cairo University — Faculty of Computers & AI",
            "name_ar": "جامعة القاهرة — كلية الحاسبات والذكاء الاصطناعي",
            "acronym": "CU-FCAI",
            "city": "Cairo",
            "country_code": "EG",
            "country_name": "Egypt",
            "website": "https://fcai.cu.edu.eg",
            "type": "University",
            "description": (
                "Egypt's leading AI faculty with extensive Arabic NLP "
                "research including Arabic NER and AraBERT."
            ),
        },
        {
            "name": "King Abdulaziz City for Science and Technology",
            "name_ar": "مدينة الملك عبدالعزيز للعلوم والتقنية",
            "acronym": "KACST",
            "city": "Riyadh",
            "country_code": "SA",
            "country_name": "Saudi Arabia",
            "website": "https://www.kacst.edu.sa",
            "type": "Research Center",
            "description": (
                "Saudi Arabia's national science agency funding Arabic NLP research, "
                "speech recognition, and language computing standards."
            ),
        },
        {
            "name": "African Institute for Mathematical Sciences",
            "name_ar": "المعهد الأفريقي للعلوم الرياضية",
            "acronym": "AIMS",
            "city": "Kigali",
            "country_code": "RW",
            "country_name": "Rwanda",
            "website": "https://nexteinstein.org",
            "type": "Research Center",
            "description": (
                "Pan-African centres of excellence hosting ML and NLP research "
                "programs focused on African language technology."
            ),
        },
        {
            "name": "University of Cape Town — NLP Group",
            "name_ar": "جامعة كيب تاون — مجموعة المعالجة اللغوية",
            "acronym": "UCT-NLP",
            "city": "Cape Town",
            "country_code": "ZA",
            "country_name": "South Africa",
            "website": "https://www.cs.uct.ac.za",
            "type": "University",
            "description": (
                "NLP research covering African languages, low-resource NLP, "
                "and cross-lingual transfer learning."
            ),
        },
        {
            "name": "Mohammed VI Polytechnic University",
            "name_ar": "جامعة محمد السادس متعددة التخصصات التقنية",
            "acronym": "UM6P",
            "city": "Ben Guerir",
            "country_code": "MA",
            "country_name": "Morocco",
            "website": "https://www.um6p.ma",
            "type": "University",
            "description": (
                "Moroccan research university with AI and Data Science center, "
                "active in Arabic NLP and Amazigh language processing."
            ),
        },
        {
            "name": "Qatar Computing Research Institute",
            "name_ar": "معهد قطر لبحوث الحوسبة",
            "acronym": "QCRI",
            "city": "Doha",
            "country_code": "QA",
            "country_name": "Qatar",
            "website": "https://www.hbku.edu.qa/en/qcri",
            "type": "Research Center",
            "description": (
                "Leading Arabic NLP research institute producing FARASA "
                "and contributions in Arabic MT and dialect identification."
            ),
        },
        {
            "name": "New York University Abu Dhabi — CAMeL Lab",
            "name_ar": "جامعة نيويورك أبوظبي — مختبر كاميل",
            "acronym": "NYUAD-CAMEL",
            "city": "Abu Dhabi",
            "country_code": "AE",
            "country_name": "United Arab Emirates",
            "website": "https://nyuad.nyu.edu/en/research/faculty-labs-and-projects/camel-lab.html",
            "type": "Research Center",
            "description": (
                "CAMeL Lab producing CAMeLBERT, CAMeL Tools, and "
                "foundational Arabic NLP research."
            ),
        },
        {
            "name": "King Abdullah University of Science and Technology",
            "name_ar": "جامعة الملك عبدالله للعلوم والتقنية",
            "acronym": "KAUST",
            "city": "Thuwal",
            "country_code": "SA",
            "country_name": "Saudi Arabia",
            "website": "https://www.kaust.edu.sa",
            "type": "University",
            "description": (
                "Saudi research university with strong AI and NLP groups, "
                "including Arabic language models and cross-lingual NLP."
            ),
        },
    ]

    def _import_african_nlp_labs(self):
        """Import curated African and Arabic-speaking NLP institutions."""
        from institutions.models import Institution

        for item in self.AFRICAN_NLP_LABS:
            name = item["name"]
            if Institution.objects.filter(name_en__iexact=name).exists():
                self.items_skipped += 1
                continue

            country = self.get_or_create_country(
                item["country_name"], item["country_code"],
            )
            city = item.get("city", "")
            address = f"{city}, {item['country_name']}" if city else item["country_name"]

            try:
                Institution.objects.create(
                    name=name,
                    name_en=name,
                    name_ar=item.get("name_ar", name),
                    acronym=item.get("acronym", "")[:20],
                    type=item.get("type", "University"),
                    country=country,
                    city=city,
                    city_en=city,
                    city_ar=city,
                    website=item.get("website", ""),
                    address=address,
                    address_en=address,
                    address_ar=address,
                    description=item.get("description", ""),
                    description_en=item.get("description", ""),
                    description_ar=item.get("description", ""),
                    created_by=self.get_system_user(),
                )
                self.items_created += 1
                self.results.append({
                    "title": self.truncate(name, 80),
                    "type": item.get("type", "University"),
                    "country": item["country_name"],
                    "city": city,
                    "url": item.get("website", ""),
                })
            except Exception as exc:
                self.errors.append(f"Failed to create institution '{name}': {exc}")
                logger.error("Failed to create institution %s: %s", name, exc)

    # ── North African Institutions (Morocco, Tunisia, Libya, Egypt) ──
    NORTH_AFRICAN_INSTITUTIONS = [
        {
            "name": "Mohammed V University in Rabat",
            "name_ar": "جامعة محمد الخامس بالرباط",
            "acronym": "UM5",
            "city": "Rabat",
            "country_code": "MA",
            "country_name": "Morocco",
            "website": "https://www.um5.ac.ma",
            "type": "University",
            "description": (
                "Morocco's premier university with research in AI, NLP, "
                "and Arabic text processing. Home to several CS departments."
            ),
        },
        {
            "name": "Cadi Ayyad University",
            "name_ar": "جامعة القاضي عياض",
            "acronym": "UCA",
            "city": "Marrakech",
            "country_code": "MA",
            "country_name": "Morocco",
            "website": "https://www.uca.ma",
            "type": "University",
            "description": (
                "Major Moroccan university with CS and data science programs, "
                "active in Arabic and Amazigh language technology."
            ),
        },
        {
            "name": "International University of Rabat",
            "name_ar": "الجامعة الدولية بالرباط",
            "acronym": "UIR",
            "city": "Rabat",
            "country_code": "MA",
            "country_name": "Morocco",
            "website": "https://www.uir.ac.ma",
            "type": "University",
            "description": (
                "Private Moroccan university with AI and data science center, "
                "contributing to Arabic NLP and Darija processing research."
            ),
        },
        {
            "name": "University of Tunis El Manar",
            "name_ar": "جامعة تونس المنار",
            "acronym": "UTM",
            "city": "Tunis",
            "country_code": "TN",
            "country_name": "Tunisia",
            "website": "https://www.utm.rnu.tn",
            "type": "University",
            "description": (
                "Tunisia's leading research university with strong CS and AI programs. "
                "Active in Arabic text mining and information retrieval."
            ),
        },
        {
            "name": "University of Sfax",
            "name_ar": "جامعة صفاقس",
            "acronym": "US",
            "city": "Sfax",
            "country_code": "TN",
            "country_name": "Tunisia",
            "website": "https://www.uss.rnu.tn",
            "type": "University",
            "description": (
                "Major Tunisian university with active research in "
                "NLP, data mining, and Arabic language processing."
            ),
        },
        {
            "name": "University of Sousse",
            "name_ar": "جامعة سوسة",
            "acronym": "USSOUSSE",
            "city": "Sousse",
            "country_code": "TN",
            "country_name": "Tunisia",
            "website": "https://www.uc.rnu.tn",
            "type": "University",
            "description": (
                "Tunisian university with computer science faculty "
                "contributing to Arabic text classification and NLP."
            ),
        },
        {
            "name": "University of Tripoli",
            "name_ar": "جامعة طرابلس",
            "acronym": "UOT",
            "city": "Tripoli",
            "country_code": "LY",
            "country_name": "Libya",
            "website": "https://www.uot.edu.ly",
            "type": "University",
            "description": (
                "Libya's largest university with CS department, "
                "contributing to Arabic NLP and language technology."
            ),
        },
        {
            "name": "Nile University",
            "name_ar": "جامعة النيل",
            "acronym": "NU",
            "city": "Cairo",
            "country_code": "EG",
            "country_name": "Egypt",
            "website": "https://www.nu.edu.eg",
            "type": "University",
            "description": (
                "Egyptian research university with AI and NLP focus, "
                "active in Arabic language understanding and generation."
            ),
        },
        {
            "name": "Egypt-Japan University of Science and Technology",
            "name_ar": "الجامعة المصرية اليابانية للعلوم والتكنولوجيا",
            "acronym": "E-JUST",
            "city": "Alexandria",
            "country_code": "EG",
            "country_name": "Egypt",
            "website": "https://www.ejust.edu.eg",
            "type": "University",
            "description": (
                "Joint Egyptian-Japanese university with strong CS and AI programs, "
                "research in Arabic NLP and cross-lingual learning."
            ),
        },
        {
            "name": "Ain Shams University — Faculty of Computer & Information Sciences",
            "name_ar": "جامعة عين شمس — كلية الحاسبات والمعلومات",
            "acronym": "ASU-FCIS",
            "city": "Cairo",
            "country_code": "EG",
            "country_name": "Egypt",
            "website": "https://cis.asu.edu.eg",
            "type": "University",
            "description": (
                "Leading Egyptian CIS faculty with Arabic NLP research, "
                "including named entity recognition and sentiment analysis."
            ),
        },
    ]

    # ── Arabic/Gulf Institutions ─────────────────────────────────────
    ARABIC_INSTITUTIONS = [
        {
            "name": "King Saud University",
            "name_ar": "جامعة الملك سعود",
            "acronym": "KSU",
            "city": "Riyadh",
            "country_code": "SA",
            "country_name": "Saudi Arabia",
            "website": "https://www.ksu.edu.sa",
            "type": "University",
            "description": (
                "Saudi Arabia's first university with extensive Arabic NLP "
                "research including text mining, NER, and corpus development."
            ),
        },
        {
            "name": "King Fahd University of Petroleum and Minerals",
            "name_ar": "جامعة الملك فهد للبترول والمعادن",
            "acronym": "KFUPM",
            "city": "Dhahran",
            "country_code": "SA",
            "country_name": "Saudi Arabia",
            "website": "https://www.kfupm.edu.sa",
            "type": "University",
            "description": (
                "Top Saudi technical university with AI and NLP research "
                "including Arabic information retrieval and text processing."
            ),
        },
        {
            "name": "Khalifa University",
            "name_ar": "جامعة خليفة",
            "acronym": "KU",
            "city": "Abu Dhabi",
            "country_code": "AE",
            "country_name": "United Arab Emirates",
            "website": "https://www.ku.ac.ae",
            "type": "University",
            "description": (
                "UAE research university with AI and robotics center, "
                "contributing to Arabic NLP and language modeling."
            ),
        },
        {
            "name": "Mohamed bin Zayed University of Artificial Intelligence",
            "name_ar": "جامعة محمد بن زايد للذكاء الاصطناعي",
            "acronym": "MBZUAI",
            "city": "Abu Dhabi",
            "country_code": "AE",
            "country_name": "United Arab Emirates",
            "website": "https://mbzuai.ac.ae",
            "type": "University",
            "description": (
                "World's first graduate-level AI university. Key contributor "
                "to Jais Arabic LLM and Arabic NLP research."
            ),
        },
        {
            "name": "Qatar University",
            "name_ar": "جامعة قطر",
            "acronym": "QU",
            "city": "Doha",
            "country_code": "QA",
            "country_name": "Qatar",
            "website": "https://www.qu.edu.qa",
            "type": "University",
            "description": (
                "Qatar's national university with CS and engineering research "
                "in Arabic NLP, text mining, and information retrieval."
            ),
        },
        {
            "name": "American University of Beirut",
            "name_ar": "الجامعة الأمريكية في بيروت",
            "acronym": "AUB",
            "city": "Beirut",
            "country_code": "LB",
            "country_name": "Lebanon",
            "website": "https://www.aub.edu.lb",
            "type": "University",
            "description": (
                "Premier Lebanese university with CS faculty contributing to "
                "Arabic NLP, sentiment analysis, and Levantine dialect processing."
            ),
        },
        {
            "name": "Jordan University of Science and Technology",
            "name_ar": "جامعة العلوم والتكنولوجيا الأردنية",
            "acronym": "JUST",
            "city": "Irbid",
            "country_code": "JO",
            "country_name": "Jordan",
            "website": "https://www.just.edu.jo",
            "type": "University",
            "description": (
                "Jordan's top technical university with research in "
                "Arabic NLP, machine translation, and text mining."
            ),
        },
        {
            "name": "Sultan Qaboos University",
            "name_ar": "جامعة السلطان قابوس",
            "acronym": "SQU",
            "city": "Muscat",
            "country_code": "OM",
            "country_name": "Oman",
            "website": "https://www.squ.edu.om",
            "type": "University",
            "description": (
                "Oman's premier national university with CS department "
                "active in Arabic information retrieval and NLP."
            ),
        },
        {
            "name": "University of Khartoum",
            "name_ar": "جامعة الخرطوم",
            "acronym": "UofK",
            "city": "Khartoum",
            "country_code": "SD",
            "country_name": "Sudan",
            "website": "https://www.uofk.edu",
            "type": "University",
            "description": (
                "Sudan's oldest university with computer science research "
                "in Arabic text processing and Sudanese dialect NLP."
            ),
        },
        {
            "name": "KINDI Center for Computing Research",
            "name_ar": "مركز الكندي لأبحاث الحوسبة",
            "acronym": "KINDI",
            "city": "Doha",
            "country_code": "QA",
            "country_name": "Qatar",
            "website": "https://www.qu.edu.qa/research/kindi",
            "type": "Research Center",
            "description": (
                "Computing research center at Qatar University, "
                "focused on Arabic text analytics and cybersecurity NLP."
            ),
        },
    ]

    def _import_north_african_institutions(self):
        """Import curated North African NLP institutions."""
        from institutions.models import Institution

        for item in self.NORTH_AFRICAN_INSTITUTIONS:
            name = item["name"]
            if Institution.objects.filter(name_en__iexact=name).exists():
                self.items_skipped += 1
                continue

            country = self.get_or_create_country(
                item["country_name"], item["country_code"],
            )
            city = item.get("city", "")
            address = f"{city}, {item['country_name']}" if city else item["country_name"]

            try:
                Institution.objects.create(
                    name=name,
                    name_en=name,
                    name_ar=item.get("name_ar", name),
                    acronym=item.get("acronym", "")[:20],
                    type=item.get("type", "University"),
                    country=country,
                    city=city,
                    city_en=city,
                    city_ar=city,
                    website=item.get("website", ""),
                    address=address,
                    address_en=address,
                    address_ar=address,
                    description=item.get("description", ""),
                    description_en=item.get("description", ""),
                    description_ar=item.get("description", ""),
                    created_by=self.get_system_user(),
                )
                self.items_created += 1
                self.results.append({
                    "title": self.truncate(name, 80),
                    "type": item.get("type", "University"),
                    "country": item["country_name"],
                    "city": city,
                    "url": item.get("website", ""),
                })
            except Exception as exc:
                self.errors.append(f"Failed to create institution '{name}': {exc}")
                logger.error("Failed to create institution %s: %s", name, exc)

    def _import_arabic_institutions(self):
        """Import curated Arabic/Gulf NLP institutions."""
        from institutions.models import Institution

        for item in self.ARABIC_INSTITUTIONS:
            name = item["name"]
            if Institution.objects.filter(name_en__iexact=name).exists():
                self.items_skipped += 1
                continue

            country = self.get_or_create_country(
                item["country_name"], item["country_code"],
            )
            city = item.get("city", "")
            address = f"{city}, {item['country_name']}" if city else item["country_name"]

            try:
                Institution.objects.create(
                    name=name,
                    name_en=name,
                    name_ar=item.get("name_ar", name),
                    acronym=item.get("acronym", "")[:20],
                    type=item.get("type", "University"),
                    country=country,
                    city=city,
                    city_en=city,
                    city_ar=city,
                    website=item.get("website", ""),
                    address=address,
                    address_en=address,
                    address_ar=address,
                    description=item.get("description", ""),
                    description_en=item.get("description", ""),
                    description_ar=item.get("description", ""),
                    created_by=self.get_system_user(),
                )
                self.items_created += 1
                self.results.append({
                    "title": self.truncate(name, 80),
                    "type": item.get("type", "University"),
                    "country": item["country_name"],
                    "city": city,
                    "url": item.get("website", ""),
                })
            except Exception as exc:
                self.errors.append(f"Failed to create institution '{name}': {exc}")
                logger.error("Failed to create institution %s: %s", name, exc)
