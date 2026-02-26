"""
NLP Courses scraper — sources: MIT OpenCourseWare API + curated list of
well-known NLP courses from top universities.

Each scraped course is stored as a ``resources.Course`` instance with
``approval_status='pending'``.
"""

import logging
from datetime import date
from .base import BaseScraper

logger = logging.getLogger(__name__)

# ── Field keyword → FieldChoices mapping ─────────────────────────────
FIELD_MAP = {
    "nlp": "nlp",
    "natural language": "nlp",
    "computational linguistics": "comp_linguistics",
    "machine learning": "ml",
    "deep learning": "ml",
    "artificial intelligence": "ai",
    "speech": "speech_processing",
    "information retrieval": "ir",
    "text mining": "text_mining",
    "data science": "data_science",
    "linguistics": "linguistics",
    "sentiment": "sentiment_analysis",
    "translation": "translation",
    "named entity": "named_entity",
    "arabic": "arabic_linguistics",
}

# ── Curated NLP courses from top universities ────────────────────────
CURATED_COURSES = [
    {
        "title": "CS224N: Natural Language Processing with Deep Learning",
        "description": (
            "Stanford's flagship NLP course covering word vectors, neural "
            "networks for NLP, dependency parsing, RNNs, attention, "
            "transformers, pretraining (BERT, GPT), and current research "
            "topics including large language models."
        ),
        "institution_name": "Stanford University",
        "institution_country": "US",
        "institution_city": "Stanford, California",
        "field": "nlp",
        "level": "master",
        "website": "https://web.stanford.edu/class/cs224n/",
        "prerequisites": "Machine Learning (CS229 or equivalent), Python, calculus, linear algebra",
        "syllabus": (
            "1. Word Vectors & Word2Vec\n2. Neural Classifiers\n"
            "3. Backpropagation\n4. Dependency Parsing\n"
            "5. Language Models & RNNs\n6. Seq2Seq & Attention\n"
            "7. Transformers\n8. Pretraining (BERT, GPT)\n"
            "9. Question Answering\n10. Text Generation\n"
            "11. Coreference Resolution\n12. Large Language Models"
        ),
    },
    {
        "title": "CS11-711: Advanced NLP",
        "description": (
            "Carnegie Mellon advanced NLP course covering state-of-the-art "
            "methods in NLP including text generation, structured prediction, "
            "low-resource NLP, and multilingual models. Emphasis on reading "
            "and understanding current research papers."
        ),
        "institution_name": "Carnegie Mellon University",
        "institution_country": "US",
        "institution_city": "Pittsburgh, Pennsylvania",
        "field": "nlp",
        "level": "master",
        "website": "http://phontron.com/class/anlp2024/",
        "prerequisites": "Introduction to NLP or equivalent, deep learning fundamentals",
        "syllabus": (
            "1. Text Classification\n2. Language Modeling\n"
            "3. Sequence Labeling\n4. Machine Translation\n"
            "5. Structured Prediction\n6. Transfer Learning\n"
            "7. Interpretability\n8. Low-Resource NLP\n"
            "9. Multilinguality\n10. Text Generation"
        ),
    },
    {
        "title": "6.8610: Quantitative Methods for NLP",
        "description": (
            "MIT course on quantitative and computational approaches to "
            "natural language processing. Covers probabilistic models, "
            "neural approaches, and evaluation methodology for NLP systems."
        ),
        "institution_name": "Massachusetts Institute of Technology",
        "institution_country": "US",
        "institution_city": "Cambridge, Massachusetts",
        "field": "nlp",
        "level": "master",
        "website": "https://mit-6861.github.io/",
        "prerequisites": "Probability, linear algebra, programming (Python)",
        "syllabus": (
            "1. Introduction to NLP\n2. Language Models\n"
            "3. Text Classification\n4. Sequence Models\n"
            "5. Parsing\n6. Semantics\n7. Machine Translation\n"
            "8. Question Answering\n9. Dialogue Systems\n"
            "10. Ethics in NLP"
        ),
    },
    {
        "title": "COMP 550: Natural Language Processing",
        "description": (
            "McGill University course providing a broad introduction to "
            "NLP covering tokenization, POS tagging, parsing, semantics, "
            "discourse, machine translation, and applications."
        ),
        "institution_name": "McGill University",
        "institution_country": "CA",
        "institution_city": "Montreal, Quebec",
        "field": "nlp",
        "level": "master",
        "website": "https://www.cs.mcgill.ca/~jchelou/comp550/",
        "prerequisites": "Data structures, algorithms, probability, linear algebra",
        "syllabus": (
            "1. Text Processing\n2. Language Modeling\n"
            "3. POS Tagging\n4. Syntax & Parsing\n"
            "5. Semantics\n6. Information Extraction\n"
            "7. Machine Translation\n8. Sentiment Analysis\n"
            "9. Question Answering\n10. Summarization"
        ),
    },
    {
        "title": "Deep Learning for Natural Language Processing",
        "description": (
            "University of Oxford course on deep learning methods for NLP. "
            "Covers word embeddings, RNNs, CNNs for text, attention mechanisms, "
            "and transformer architectures."
        ),
        "institution_name": "University of Oxford",
        "institution_country": "GB",
        "institution_city": "Oxford",
        "field": "nlp",
        "level": "master",
        "website": "https://www.cs.ox.ac.uk/teaching/courses/2024-2025/dlnlp/",
        "prerequisites": "Machine learning, linear algebra, Python programming",
        "syllabus": (
            "1. Word Embeddings\n2. Recurrent Neural Networks\n"
            "3. Convolutional Models for Text\n4. Attention Mechanisms\n"
            "5. Transformer Architecture\n6. Pre-trained Models\n"
            "7. Text Generation\n8. Language Understanding"
        ),
    },
    {
        "title": "Arabic Natural Language Processing",
        "description": (
            "Specialised course on computational processing of Arabic language, "
            "covering morphological analysis, dialectal Arabic processing, "
            "Arabic text classification, sentiment analysis, and machine "
            "translation for Arabic."
        ),
        "institution_name": "New York University Abu Dhabi",
        "institution_country": "AE",
        "institution_city": "Abu Dhabi",
        "field": "nlp",
        "level": "master",
        "website": "https://nyuad.nyu.edu/en/academics/divisions/science/arabic-nlp.html",
        "prerequisites": "Introduction to NLP, Arabic language skills (helpful but not required)",
        "syllabus": (
            "1. Arabic Morphology & Tokenization\n"
            "2. Arabic POS Tagging\n"
            "3. Arabic Named Entity Recognition\n"
            "4. Dialectal Arabic Processing\n"
            "5. Arabic Sentiment Analysis\n"
            "6. Arabic Machine Translation\n"
            "7. Arabic Text Summarization\n"
            "8. Arabic Language Models (CAMeLBERT, AraBERT)"
        ),
    },
    {
        "title": "Introduction to NLP with Transformers",
        "description": (
            "Practical course from Hugging Face covering the transformer "
            "architecture, tokenizers, fine-tuning pre-trained models, "
            "and deploying NLP solutions. Free and open access."
        ),
        "institution_name": "Hugging Face",
        "institution_country": "US",
        "institution_city": "New York",
        "field": "nlp",
        "level": "bachelor",
        "website": "https://huggingface.co/learn/nlp-course/",
        "prerequisites": "Python programming, basic machine learning concepts",
        "syllabus": (
            "1. Transformer Models\n2. Using Transformers\n"
            "3. Fine-Tuning Pretrained Models\n4. Sharing Models\n"
            "5. The Datasets Library\n6. The Tokenizers Library\n"
            "7. Main NLP Tasks\n8. Building NLP Demos"
        ),
    },
    {
        "title": "Speech and Language Processing",
        "description": (
            "Comprehensive online textbook and course materials by Dan "
            "Jurafsky and James H. Martin covering the full spectrum of "
            "NLP: regular expressions, language models, sequence labeling, "
            "parsing, semantics, discourse, dialogue, and MT."
        ),
        "institution_name": "Stanford University",
        "institution_country": "US",
        "institution_city": "Stanford, California",
        "field": "nlp",
        "level": "bachelor",
        "website": "https://web.stanford.edu/~jurafsky/slp3/",
        "prerequisites": "Basic programming, introductory linguistics helpful",
        "syllabus": (
            "1. Regular Expressions & Automata\n"
            "2. N-gram Language Models\n"
            "3. Naive Bayes & Sentiment\n"
            "4. Logistic Regression\n"
            "5. Neural Networks\n"
            "6. POS Tagging\n"
            "7. Constituency & Dependency Parsing\n"
            "8. Semantics & Word Senses\n"
            "9. Machine Translation\n"
            "10. Question Answering & Chatbots"
        ),
    },
    {
        "title": "Multilingual NLP",
        "description": (
            "Course focused on NLP techniques for multilingual and "
            "cross-lingual settings. Covers language-agnostic representations, "
            "cross-lingual transfer, multilingual transformers, and "
            "evaluation across languages including Arabic."
        ),
        "institution_name": "ETH Zurich",
        "institution_country": "CH",
        "institution_city": "Zurich",
        "field": "nlp",
        "level": "master",
        "website": "https://rycolab.io/classes/multilingual-nlp-f23/",
        "prerequisites": "NLP fundamentals, deep learning, linear algebra",
        "syllabus": (
            "1. Multilingual Representations\n"
            "2. Cross-lingual Transfer\n"
            "3. Multilingual Transformers (mBERT, XLM-R)\n"
            "4. Machine Translation\n"
            "5. Morphological Typology\n"
            "6. Low-Resource Languages\n"
            "7. Evaluation Across Languages\n"
            "8. Arabic & Semitic Language Processing"
        ),
    },
    {
        "title": "Text Mining and Analytics",
        "description": (
            "Course from UIUC covering text mining, information retrieval, "
            "topic modeling, text clustering, sentiment analysis, and "
            "opinion mining with applications to real-world datasets."
        ),
        "institution_name": "University of Illinois Urbana-Champaign",
        "institution_country": "US",
        "institution_city": "Champaign, Illinois",
        "field": "text_mining",
        "level": "master",
        "website": "https://www.coursera.org/learn/cs-410",
        "prerequisites": "Programming, basic probability, linear algebra",
        "syllabus": (
            "1. Natural Language Content Analysis\n"
            "2. Text Representation\n"
            "3. Word Association Mining\n"
            "4. Topic Modeling (PLSA, LDA)\n"
            "5. Text Clustering\n"
            "6. Text Categorization\n"
            "7. Sentiment Analysis & Opinion Mining\n"
            "8. Text-Based Prediction"
        ),
    },
]


class CourseScraper(BaseScraper):
    """Scrape / import NLP courses from curated list and MIT OCW API."""

    name = "NLP Courses"
    category = "courses"

    def scrape(self):
        self._scrape_mit_ocw()
        self._import_curated_courses()

    # ── MIT OpenCourseWare ────────────────────────────────────────────
    def _scrape_mit_ocw(self):
        """Try to scrape NLP-related courses from MIT OCW search API."""
        url = "https://ocw.mit.edu/api/v0/search/"
        params = {
            "q": "natural language processing",
            "limit": 10,
        }
        resp = self.safe_request(url, params=params)
        if resp is None:
            # MIT OCW API may not be available — that's fine, curated list
            # will cover famous courses.
            return

        try:
            data = resp.json()
            results = data.get("results", data.get("hits", []))
            if not isinstance(results, list):
                return

            mit_country = self.get_or_create_country("United States", "US")
            mit_inst = self.get_or_create_institution(
                "Massachusetts Institute of Technology",
                acronym="MIT",
                country=mit_country,
                city="Cambridge, Massachusetts",
                website="https://ocw.mit.edu",
                inst_type="University",
            )
            if mit_inst is None:
                return

            for hit in results:
                title = hit.get("title", "") or hit.get("name", "")
                desc = hit.get("description", "") or hit.get("short_description", "")
                course_url = hit.get("url", "") or hit.get("link", "")
                if course_url and not course_url.startswith("http"):
                    course_url = f"https://ocw.mit.edu{course_url}"

                if title:
                    self._create_course(
                        title=title,
                        description=desc,
                        institution=mit_inst,
                        website=course_url,
                        field="nlp",
                        level="master",
                    )
        except Exception as exc:
            self.errors.append(f"MIT OCW parse error: {exc}")

    # ── Curated courses ───────────────────────────────────────────────
    def _import_curated_courses(self):
        """Import well-known NLP courses from the curated list."""
        for item in CURATED_COURSES:
            country = self.get_or_create_country(
                item["institution_name"][:30],
                item.get("institution_country", "US"),
            )
            institution = self.get_or_create_institution(
                item["institution_name"],
                country=country,
                city=item.get("institution_city", ""),
                website=item.get("website", ""),
                inst_type="University",
            )
            if institution is None:
                self.items_skipped += 1
                continue

            self._create_course(
                title=item["title"],
                description=item["description"],
                institution=institution,
                website=item.get("website", ""),
                field=item.get("field", "nlp"),
                level=item.get("level", "master"),
                prerequisites=item.get("prerequisites", ""),
                syllabus=item.get("syllabus", ""),
            )

    # ── Helper ────────────────────────────────────────────────────────
    def _create_course(
        self,
        *,
        title,
        description,
        institution,
        website="",
        field="nlp",
        level="master",
        prerequisites="",
        syllabus="",
    ):
        from resources.models import Course

        # Duplicate check
        if Course.objects.filter(title_en__iexact=title).exists():
            self.items_skipped += 1
            return

        current_year = date.today().year
        academic_year = f"{current_year}-{current_year + 1}"

        try:
            Course.objects.create(
                title=title,
                title_en=title,
                title_ar=title,
                description=description,
                description_en=description,
                description_ar=description,
                field=field,
                academic_level=level,
                teacher=self.get_system_user(),
                institution=institution,
                academic_year=academic_year,
                access_link=website,
                language="en",
                keywords="NLP,natural language processing,deep learning",
                prerequisites=prerequisites,
                syllabus=syllabus,
                author=self.get_system_user(),
                approval_status="pending",
            )
            self.items_created += 1
            self.results.append(
                {
                    "title": self.truncate(title, 100),
                    "institution": institution.name_en,
                    "level": level,
                    "url": website,
                }
            )
        except Exception as exc:
            self.errors.append(f"Failed to create course '{title}': {exc}")
            logger.error("Failed to create Course %s: %s", title, exc)
