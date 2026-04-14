"""
Field mapping and completeness scoring for scraped items.
"""

from scraping.utils import translation_field_credit

FIELD_MAPPINGS = {
    "events": {
        "required": {
            "title_en": {
                "model_field": "title_en",
                "min_length": 5,
                "max_length": 300,
                "description": "Event title in English",
            },
            "description_en": {
                "model_field": "description_en",
                "min_length": 20,
                "max_length": 5000,
                "description": "Event description in English",
            },
            "start_date": {
                "model_field": "start_date",
                "type": "date",
                "description": "Event start date",
            },
            "event_type": {
                "model_field": "event_type",
                "choices": [
                    "conference",
                    "workshop",
                    "seminar",
                    "call_for_papers",
                    "hackathon",
                    "other",
                ],
                "default": "conference",
                "description": "Event type",
            },
        },
        "optional": {
            "title_ar": {
                "model_field": "title_ar",
                "min_length": 5,
                "max_length": 300,
                "auto_translate": True,
                "description": "Event title in Arabic",
            },
            "description_ar": {
                "model_field": "description_ar",
                "min_length": 20,
                "max_length": 5000,
                "auto_translate": True,
                "description": "Event description in Arabic",
            },
            "end_date": {
                "model_field": "end_date",
                "type": "date",
                "description": "Event end date",
            },
            "submission_deadline": {
                "model_field": "submission_deadline",
                "type": "date",
                "description": "Submission deadline",
            },
            "location_en": {
                "model_field": "location_en",
                "min_length": 2,
                "max_length": 200,
                "description": "Location in English",
            },
            "location_ar": {
                "model_field": "location_ar",
                "min_length": 2,
                "max_length": 200,
                "auto_translate": True,
                "description": "Location in Arabic",
            },
            "website": {
                "model_field": "website",
                "type": "url",
                "max_length": 500,
                "description": "Event website",
            },
            "contact_email": {
                "model_field": "contact_email",
                "type": "email",
                "max_length": 254,
                "description": "Contact email",
            },
            "research_domains": {
                "model_field": "research_domains",
                "type": "list",
                "auto_generate": True,
                "description": "Related research domains",
            },
            "poster_url": {
                "model_field": "poster_url",
                "type": "url",
                "max_length": 500,
                "description": "Poster file URL",
            },
            "notification_date": {
                "model_field": "notification_date",
                "type": "date",
                "description": "Notification date",
            },
            "registration_link": {
                "model_field": "registration_link",
                "type": "url",
                "max_length": 500,
                "description": "Registration URL",
            },
            "is_online": {
                "model_field": "is_online",
                "description": "Online event indicator",
            },
            "is_hybrid": {
                "model_field": "is_hybrid",
                "description": "Hybrid event indicator",
            },
            "source_url": {
                "model_field": "source_url",
                "type": "url",
                "max_length": 500,
                "description": "Source page URL",
            },
            "source_name": {
                "model_field": "source_name",
                "max_length": 120,
                "description": "Human source label",
            },
            "language": {
                "model_field": "language",
                "choices": ["ar", "fr", "en", "other"],
                "default": "en",
                "description": "Detected event language",
            },
            "banner_url": {
                "model_field": "banner_image",
                "type": "url",
                "max_length": 500,
                "description": "Banner image URL",
            },
            "tags": {
                "model_field": "tags",
                "type": "list",
                "description": "Event tags",
            },
        },
    },
    "tools": {
        "required": {
            "title_en": {
                "model_field": "title_en",
                "min_length": 3,
                "max_length": 200,
                "description": "Tool title in English",
            },
            "description_en": {
                "model_field": "description_en",
                "min_length": 20,
                "max_length": 3000,
                "description": "Tool description in English",
            },
            "tool_type": {
                "model_field": "tool_type",
                "choices": [
                    "tokenization",
                    "stemming",
                    "ner",
                    "pos_tagging",
                    "sentiment_analysis",
                    "machine_translation",
                    "other",
                ],
                "default": "other",
                "description": "Tool category",
            },
            "access_link": {
                "model_field": "access_link",
                "type": "url",
                "max_length": 500,
                "description": "Primary access URL",
            },
        },
        "optional": {
            "title_ar": {
                "model_field": "title_ar",
                "min_length": 3,
                "max_length": 200,
                "auto_translate": True,
                "description": "Tool title in Arabic",
            },
            "description_ar": {
                "model_field": "description_ar",
                "min_length": 20,
                "max_length": 3000,
                "auto_translate": True,
                "description": "Tool description in Arabic",
            },
            "documentation_url": {
                "model_field": "documentation_url",
                "type": "url",
                "max_length": 500,
                "description": "Documentation URL",
            },
            "version": {
                "model_field": "version",
                "max_length": 50,
                "default": "latest",
                "description": "Tool version",
            },
            "keywords": {
                "model_field": "keywords",
                "type": "list",
                "auto_generate": True,
                "description": "Keywords",
            },
            "supported_languages": {
                "model_field": "supported_languages",
                "type": "list",
                "auto_generate": True,
                "description": "Supported natural languages",
            },
            "primary_language": {
                "model_field": "primary_language",
                "choices": ["arabic", "english", "french", "multilingual"],
                "default": "arabic",
                "description": "Primary language",
            },
            "thumbnail_url": {
                "model_field": "thumbnail_url",
                "type": "url",
                "max_length": 500,
                "description": "Thumbnail URL",
            },
            "demo_url": {
                "model_field": "demo_url",
                "type": "url",
                "max_length": 500,
                "description": "Demo URL",
            },
            "paper_url": {
                "model_field": "paper_url",
                "type": "url",
                "max_length": 500,
                "description": "Paper URL",
            },
            "license": {
                "model_field": "license",
                "max_length": 100,
                "description": "Tool license",
            },
            "stars_count": {
                "model_field": "stars_count",
                "description": "GitHub stars count",
            },
            "last_updated": {
                "model_field": "last_updated",
                "type": "date",
                "description": "Last update date",
            },
            "installation_instructions": {
                "model_field": "installation_instructions",
                "min_length": 10,
                "max_length": 5000,
                "description": "Installation instructions",
            },
            "use_cases": {
                "model_field": "use_cases",
                "type": "list",
                "description": "Primary use-cases",
            },
            "author_organization": {
                "model_field": "author_organization",
                "max_length": 255,
                "description": "Author organization",
            },
            "source_url": {
                "model_field": "source_url",
                "type": "url",
                "max_length": 500,
                "description": "Source URL",
            },
            "source_name": {
                "model_field": "source_name",
                "max_length": 120,
                "description": "Source label",
            },
        },
    },
    "news": {
        "required": {
            "title_en": {
                "model_field": "title_en",
                "min_length": 10,
                "max_length": 300,
                "description": "Post title in English",
            },
            "description_en": {
                "model_field": "content_en",
                "min_length": 50,
                "max_length": 50000,
                "description": "Post content in English",
            },
        },
        "optional": {
            "title_ar": {
                "model_field": "title_ar",
                "min_length": 10,
                "max_length": 300,
                "auto_translate": True,
                "description": "Post title in Arabic",
            },
            "description_ar": {
                "model_field": "content_ar",
                "min_length": 50,
                "max_length": 50000,
                "auto_translate": True,
                "description": "Post content in Arabic",
            },
            "published_date": {
                "model_field": "published_date",
                "type": "date",
                "description": "Publication date",
            },
            "publication_date": {
                "model_field": "publication_date",
                "type": "date",
                "description": "Publication date alias",
            },
            "date": {
                "model_field": "date",
                "type": "date",
                "description": "Generic date field",
            },
            "pdf_url": {
                "model_field": "pdf_url",
                "type": "url",
                "max_length": 500,
                "description": "Research paper PDF URL",
            },
            "keywords": {
                "model_field": "keywords",
                "type": "list",
                "auto_generate": True,
                "description": "Keywords",
            },
            "authors": {
                "model_field": "authors",
                "type": "list",
                "description": "Authors list",
            },
            "doi": {
                "model_field": "doi",
                "max_length": 255,
                "description": "DOI",
            },
            "arxiv_id": {
                "model_field": "arxiv_id",
                "max_length": 50,
                "description": "arXiv identifier",
            },
            "source_name": {
                "model_field": "source_name",
                "max_length": 120,
                "description": "Source label",
            },
            "source_url": {
                "model_field": "source_url",
                "type": "url",
                "max_length": 500,
                "description": "Source URL",
            },
            "relevance_score": {
                "model_field": "relevance_score",
                "description": "Relevance score",
            },
            "thumbnail_url": {
                "model_field": "thumbnail",
                "type": "url",
                "max_length": 500,
                "description": "Thumbnail URL",
            },
            "news_category": {
                "model_field": "news_category",
                "choices": ["paper", "news", "announcement", "blog"],
                "default": "paper",
                "description": "News category",
            },
        },
    },
    "courses": {
        "required": {
            "title_en": {
                "model_field": "title_en",
                "min_length": 5,
                "max_length": 300,
                "description": "Course title in English",
            },
            "description_en": {
                "model_field": "description_en",
                "min_length": 30,
                "max_length": 5000,
                "description": "Course description in English",
            },
            "field_of_study": {
                "model_field": "field_of_study",
                "choices": [
                    "computer_science",
                    "linguistics",
                    "ai",
                    "nlp",
                    "machine_learning",
                    "data_science",
                    "computational_linguistics",
                    "speech_processing",
                    "other",
                ],
                "default": "nlp",
                "description": "Field of study",
            },
            "academic_level": {
                "model_field": "academic_level",
                "choices": ["bachelor", "master", "doctorate", "professional"],
                "default": "master",
                "description": "Academic level",
            },
            "teaching_language": {
                "model_field": "teaching_language",
                "choices": ["arabic", "english", "french", "bilingual"],
                "default": "english",
                "description": "Teaching language",
            },
        },
        "optional": {
            "title_ar": {
                "model_field": "title_ar",
                "min_length": 5,
                "max_length": 300,
                "auto_translate": True,
                "description": "Course title in Arabic",
            },
            "description_ar": {
                "model_field": "description_ar",
                "min_length": 30,
                "max_length": 5000,
                "auto_translate": True,
                "description": "Course description in Arabic",
            },
            "course_url": {
                "model_field": "course_url",
                "type": "url",
                "max_length": 500,
                "description": "Course URL",
            },
            "keywords": {
                "model_field": "keywords",
                "type": "list",
                "auto_generate": True,
                "description": "Course keywords",
            },
            "prerequisites": {
                "model_field": "prerequisites",
                "min_length": 5,
                "max_length": 2000,
                "auto_generate": True,
                "description": "Prerequisites",
            },
            "syllabus": {
                "model_field": "syllabus",
                "min_length": 10,
                "max_length": 5000,
                "auto_generate": True,
                "description": "Syllabus summary",
            },
            "academic_year": {
                "model_field": "academic_year",
                "max_length": 20,
                "description": "Academic year",
            },
            "syllabus_file_url": {
                "model_field": "syllabus_file_url",
                "type": "url",
                "max_length": 500,
                "description": "Syllabus file URL",
            },
            "instructor": {
                "model_field": "instructor",
                "max_length": 255,
                "description": "Course instructor",
            },
            "duration": {
                "model_field": "duration",
                "max_length": 100,
                "description": "Course duration",
            },
            "platform": {
                "model_field": "platform",
                "choices": [
                    "coursera",
                    "youtube",
                    "mit",
                    "edx",
                    "university",
                    "other",
                ],
                "default": "other",
                "description": "Course platform",
            },
            "enrollment_url": {
                "model_field": "enrollment_url",
                "type": "url",
                "max_length": 500,
                "description": "Enrollment URL",
            },
            "thumbnail_url": {
                "model_field": "thumbnail",
                "type": "url",
                "max_length": 500,
                "description": "Thumbnail URL",
            },
            "is_free": {
                "model_field": "is_free",
                "description": "Whether the course is free",
            },
            "price": {
                "model_field": "price",
                "description": "Course price",
            },
            "certificate_available": {
                "model_field": "certificate_available",
                "description": "Certificate availability",
            },
            "start_date": {
                "model_field": "start_date",
                "type": "date",
                "description": "Course start date",
            },
            "source_url": {
                "model_field": "source_url",
                "type": "url",
                "max_length": 500,
                "description": "Source URL",
            },
            "source_name": {
                "model_field": "source_name",
                "max_length": 120,
                "description": "Source name",
            },
            "level": {
                "model_field": "academic_level",
                "max_length": 80,
                "description": "Course level alias",
            },
        },
    },
    "opportunities": {
        "required": {
            "job_title": {
                "model_field": "job_title",
                "min_length": 5,
                "max_length": 300,
                "description": "Opportunity title in English",
            },
            "description": {
                "model_field": "description",
                "min_length": 20,
                "max_length": 5000,
                "description": "Opportunity description in English",
            },
            "opportunity_type": {
                "model_field": "opportunity_type",
                "max_length": 50,
                "description": "Opportunity type",
            },
            "url": {
                "model_field": "url",
                "type": "url",
                "max_length": 500,
                "description": "Opportunity URL",
            },
        },
        "optional": {
            "title_ar": {
                "model_field": "title_ar",
                "min_length": 5,
                "max_length": 300,
                "auto_translate": True,
                "description": "Opportunity title in Arabic",
            },
            "description_ar": {
                "model_field": "description_ar",
                "min_length": 20,
                "max_length": 5000,
                "auto_translate": True,
                "description": "Opportunity description in Arabic",
            },
            "institution_name": {
                "model_field": "institution_name",
                "max_length": 255,
                "description": "Institution name",
            },
            "deadline": {
                "model_field": "deadline",
                "type": "date",
                "description": "Opportunity deadline",
            },
            "location": {
                "model_field": "location",
                "max_length": 255,
                "description": "Opportunity location",
            },
            "source_name": {
                "model_field": "source_name",
                "max_length": 120,
                "description": "Source name",
            },
            "source_url": {
                "model_field": "source_url",
                "type": "url",
                "max_length": 500,
                "description": "Source URL",
            },
        },
    },
    "corpus": {
        "required": {
            "dataset_name": {
                "model_field": "dataset_name",
                "min_length": 5,
                "max_length": 300,
                "description": "Corpus or dataset name in English",
            },
            "description_en": {
                "model_field": "description_en",
                "min_length": 20,
                "max_length": 5000,
                "description": "Corpus description in English",
            },
        },
        "optional": {
            "title_ar": {
                "model_field": "title_ar",
                "min_length": 5,
                "max_length": 300,
                "auto_translate": True,
                "description": "Corpus title in Arabic",
            },
            "description_ar": {
                "model_field": "description_ar",
                "min_length": 20,
                "max_length": 5000,
                "auto_translate": True,
                "description": "Corpus description in Arabic",
            },
            "download_url": {
                "model_field": "download_url",
                "type": "url",
                "max_length": 500,
                "description": "Primary download URL",
            },
            "paper_url": {
                "model_field": "paper_url",
                "type": "url",
                "max_length": 500,
                "description": "Paper or reference URL",
            },
            "language_variants": {
                "model_field": "language_variants",
                "type": "list",
                "description": "Language variants covered by the corpus",
            },
            "size_estimate": {
                "model_field": "size_estimate",
                "max_length": 120,
                "description": "Dataset size estimate",
            },
            "source_name": {
                "model_field": "source_name",
                "max_length": 120,
                "description": "Source name",
            },
            "source_url": {
                "model_field": "source_url",
                "type": "url",
                "max_length": 500,
                "description": "Source URL",
            },
        },
    },
    "institutions": {
        "required": {
            "name_en": {
                "model_field": "name_en",
                "min_length": 3,
                "max_length": 300,
                "description": "Institution name in English",
            },
            "institution_type": {
                "model_field": "institution_type",
                "choices": ["university", "research_center", "school", "other"],
                "default": "university",
                "description": "Institution type",
            },
            "country": {
                "model_field": "country",
                "description": "Country",
            },
            "city_en": {
                "model_field": "city_en",
                "min_length": 2,
                "max_length": 100,
                "description": "City in English",
            },
        },
        "optional": {
            "name_ar": {
                "model_field": "name_ar",
                "min_length": 3,
                "max_length": 300,
                "auto_translate": True,
                "description": "Institution name in Arabic",
            },
            "acronym": {
                "model_field": "acronym",
                "max_length": 20,
                "description": "Institution acronym",
            },
            "description_en": {
                "model_field": "description_en",
                "min_length": 20,
                "max_length": 5000,
                "auto_generate": True,
                "description": "Institution description in English",
            },
            "description_ar": {
                "model_field": "description_ar",
                "min_length": 20,
                "max_length": 5000,
                "auto_translate": True,
                "description": "Institution description in Arabic",
            },
            "city_ar": {
                "model_field": "city_ar",
                "min_length": 2,
                "max_length": 100,
                "auto_translate": True,
                "description": "City in Arabic",
            },
            "website": {
                "model_field": "website",
                "type": "url",
                "max_length": 500,
                "description": "Website URL",
            },
            "email": {
                "model_field": "email",
                "type": "email",
                "max_length": 254,
                "description": "Contact email",
            },
            "phone": {
                "model_field": "phone",
                "max_length": 80,
                "description": "Contact phone",
            },
            "address_en": {
                "model_field": "address_en",
                "min_length": 5,
                "max_length": 500,
                "auto_generate": True,
                "description": "Address in English",
            },
            "address_ar": {
                "model_field": "address_ar",
                "min_length": 5,
                "max_length": 500,
                "auto_translate": True,
                "description": "Address in Arabic",
            },
            "logo_url": {
                "model_field": "logo_url",
                "type": "url",
                "max_length": 500,
                "description": "Logo URL",
            },
            "research_specialties": {
                "model_field": "research_specialties",
                "type": "list",
                "auto_generate": True,
                "description": "Research specialties",
            },
            "founding_year": {
                "model_field": "founding_year",
                "description": "Founding year",
            },
            "director": {
                "model_field": "director",
                "max_length": 255,
                "description": "Director name",
            },
            "affiliated_researchers_count": {
                "model_field": "affiliated_researchers_count",
                "description": "Affiliated researchers count",
            },
            "notable_publications": {
                "model_field": "notable_publications",
                "type": "list",
                "description": "Notable publications",
            },
            "ror_id": {
                "model_field": "ror_id",
                "max_length": 100,
                "description": "ROR identifier",
            },
            "social_links": {
                "model_field": "social_links",
                "type": "dict",
                "description": "Social links",
            },
            "source_url": {
                "model_field": "source_url",
                "type": "url",
                "max_length": 500,
                "description": "Source URL",
            },
            "source_name": {
                "model_field": "source_name",
                "max_length": 120,
                "description": "Source name",
            },
        },
    },
}


COMPLETENESS_WEIGHTS = {
    "events": {
        "title_en": 20,
        "title_ar": 15,
        "description_en": 15,
        "description_ar": 10,
        "start_date": 15,
        "website": 10,
        "location_en": 8,
        "end_date": 5,
        "event_type": 2,
    },
    "tools": {
        "title_en": 20,
        "title_ar": 15,
        "description_en": 20,
        "description_ar": 10,
        "access_link": 15,
        "keywords": 10,
        "supported_languages": 10,
    },
    "news": {
        "title_en": 25,
        "title_ar": 15,
        "description_en": 20,
        "description_ar": 10,
        "published_date": 15,
        "source_url": 10,
        "source_name": 5,
    },
    "courses": {
        "title_en": 20,
        "title_ar": 15,
        "description_en": 20,
        "description_ar": 10,
        "platform": 15,
        "course_url": 10,
        "level": 5,
        "price": 5,
    },
    "opportunities": {
        "job_title": 22,
        "title_ar": 14,
        "description": 18,
        "description_ar": 10,
        "opportunity_type": 14,
        "deadline": 10,
        "url": 7,
        "institution_name": 5,
    },
    "corpus": {
        "dataset_name": 22,
        "title_ar": 12,
        "description_en": 20,
        "description_ar": 10,
        "download_url": 15,
        "paper_url": 8,
        "language_variants": 8,
        "size_estimate": 5,
    },
    "institutions": {
        "name_en": 18,
        "institution_type": 12,
        "country": 12,
        "city_en": 10,
        "description_en": 10,
        "website": 10,
        "name_ar": 8,
        "description_ar": 8,
        "address_en": 6,
        "research_specialties": 6,
        "founding_year": 4,
        "director": 4,
        "affiliated_researchers_count": 4,
        "notable_publications": 3,
        "ror_id": 5,
        "social_links": 3,
        "source_url": 3,
        "source_name": 2,
    },
}


def _is_value_filled(value, field_config):
    if value is None:
        return False

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return False
        min_len = field_config.get("min_length")
        return not (min_len is not None and len(text) < int(min_len))

    if isinstance(value, (list, tuple, set)):
        return len(value) > 0

    if isinstance(value, dict):
        return len(value) > 0

    return True


def _normalize_compare_text(value) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _score_arabic_field(ar_value, en_value, field_name):
    del field_name

    ar_text = str(ar_value or "").strip()
    en_text = str(en_value or "").strip()
    if not ar_text:
        return 0.0

    if en_text and _normalize_compare_text(ar_text) == _normalize_compare_text(en_text):
        return 0.3

    arabic_chars = sum(1 for ch in ar_text if "\u0600" <= ch <= "\u06ff")
    if arabic_chars < len(ar_text) * 0.3:
        return 0.2

    return 1.0


def calculate_completeness_score(item, category):
    """
    Calculate weighted completeness score for a scraped item.

    Returns a score in the range 0..100.
    """
    category_map = FIELD_MAPPINGS.get(category, {})
    required_fields = category_map.get("required", {})
    optional_fields = category_map.get("optional", {})

    all_fields = {}
    all_fields.update(required_fields)
    all_fields.update(optional_fields)

    if not all_fields:
        return 0.0

    weights = COMPLETENESS_WEIGHTS.get(category, {})
    total_weight = 0.0
    earned_weight = 0.0
    arabic_fields = {"title_ar", "description_ar", "short_description_ar"}

    for field_key, field_config in all_fields.items():
        weight = float(weights.get(field_key, 0.0))
        if weight <= 0:
            continue

        total_weight += weight
        field_value = item.get(field_key)
        if _is_value_filled(field_value, field_config):
            if field_key in arabic_fields:
                english_key = f"{field_key[:-3]}_en"
                english_value = item.get(english_key) or item.get(field_key[:-3])
                earned_weight += weight * _score_arabic_field(
                    field_value,
                    english_value,
                    field_key,
                )
            else:
                earned_weight += weight * translation_field_credit(item, field_key)

    if total_weight <= 0:
        return 0.0

    score = (earned_weight / total_weight) * 100.0
    return round(score, 1)


def get_auto_translate_fields(category: str) -> list[str]:
    """Return optional field keys that require automatic Arabic translation."""
    mapping = FIELD_MAPPINGS.get((category or "").strip().lower(), {})
    optional = mapping.get("optional", {})
    if not isinstance(optional, dict):
        return []

    fields: list[str] = []
    for field_key, config in optional.items():
        if not isinstance(config, dict):
            continue
        if bool(config.get("auto_translate")):
            fields.append(str(field_key))

    return fields
