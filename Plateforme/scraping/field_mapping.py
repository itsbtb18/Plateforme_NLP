"""
Field mapping and completeness scoring for scraped items.
"""

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
            "content_en": {
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
            "content_ar": {
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
        },
    },
}


COMPLETENESS_WEIGHTS = {
    "events": {
        "title_en": 16,
        "description_en": 16,
        "start_date": 12,
        "event_type": 10,
        "title_ar": 8,
        "description_ar": 8,
        "location_en": 8,
        "website": 7,
        "research_domains": 7,
        "submission_deadline": 4,
        "contact_email": 4,
    },
    "tools": {
        "title_en": 16,
        "description_en": 16,
        "tool_type": 12,
        "access_link": 14,
        "title_ar": 8,
        "description_ar": 8,
        "keywords": 8,
        "supported_languages": 8,
        "documentation_url": 5,
        "version": 5,
    },
    "news": {
        "title_en": 20,
        "content_en": 30,
        "title_ar": 10,
        "content_ar": 15,
        "published_date": 10,
        "keywords": 8,
        "authors": 7,
    },
    "courses": {
        "title_en": 15,
        "description_en": 15,
        "field_of_study": 12,
        "academic_level": 10,
        "teaching_language": 8,
        "course_url": 8,
        "title_ar": 8,
        "description_ar": 8,
        "keywords": 8,
        "syllabus": 8,
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
        if min_len is not None and len(text) < int(min_len):
            return False
        return True

    if isinstance(value, (list, tuple, set)):
        return len(value) > 0

    if isinstance(value, dict):
        return len(value) > 0

    return True


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

    for field_key, field_config in all_fields.items():
        weight = float(weights.get(field_key, 1))
        total_weight += weight
        if _is_value_filled(item.get(field_key), field_config):
            earned_weight += weight

    if total_weight <= 0:
        return 0.0

    score = (earned_weight / total_weight) * 100.0
    return round(score, 1)
