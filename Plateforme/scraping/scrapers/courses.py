"""
NLP Courses scraper — sources: MIT OpenCourseWare API, Coursera catalog,
YouTube NLP playlists, and curated list of well-known NLP courses
from top universities.

Each scraped course is stored as a ``resources.Course`` instance with
``approval_status='pending'``.
"""

import logging
import re
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
        self._scrape_coursera()
        self._import_youtube_playlists()
        self._import_curated_courses()

    # ── MIT OpenCourseWare (via MIT Open Learning API) ──────────────
    MIT_API_BASE = "https://api.learn.mit.edu/api/v1/courses/"

    # Targeted queries to find NLP / AI / computational-linguistics courses
    MIT_QUERIES = [
        {"q": "natural language processing", "topic": "AI", "limit": 10},
        {"q": "computational linguistics", "offered_by": "ocw", "limit": 5},
        {"q": "deep learning", "topic": "AI", "limit": 10},
        {"q": "machine learning NLP", "topic": "AI", "limit": 5},
        {"q": "text mining information retrieval", "offered_by": "ocw", "limit": 5},
    ]

    def _scrape_mit_ocw(self):
        """Scrape NLP-related courses from the MIT Open Learning API."""
        seen_ids: set[int] = set()

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

        for query_params in self.MIT_QUERIES:
            params = {"offered_by": "ocw", **query_params}
            resp = self.safe_request(
                self.MIT_API_BASE,
                params=params,
                headers={"Accept": "application/json"},
            )
            if resp is None:
                continue

            try:
                data = resp.json()
                results = data.get("results", [])
                if not isinstance(results, list):
                    continue

                for course in results:
                    course_id = course.get("id")
                    if course_id in seen_ids:
                        continue
                    seen_ids.add(course_id)

                    title = course.get("title", "")
                    if not title:
                        continue

                    desc = self.clean_text(
                        course.get("description", "")
                    )
                    course_url = course.get("url", "")
                    if course_url and not course_url.startswith("http"):
                        course_url = f"https://ocw.mit.edu{course_url}"

                    # Resolve level from first run
                    level = "master"
                    runs = course.get("runs", [])
                    if runs:
                        levels = runs[0].get("level", [])
                        if levels:
                            code = levels[0].get("code", "")
                            if code == "undergraduate":
                                level = "bachelor"
                            elif code == "graduate":
                                level = "master"

                    self._create_course(
                        title=title,
                        description=desc,
                        institution=mit_inst,
                        website=course_url,
                        field="nlp",
                        level=level,
                    )
            except Exception as exc:
                self.errors.append(f"MIT OCW parse error: {exc}")
                logger.error("MIT OCW parse error: %s", exc)

    # ── Coursera NLP Courses ────────────────────────────────────────
    COURSERA_COURSES = [
        {
            "title": "Natural Language Processing Specialization",
            "instructor": "Younes Bensouda Mourri, Łukasz Kaiser",
            "duration": "4 months",
            "level": "bachelor",
            "language": "en",
            "link": "https://www.coursera.org/specializations/natural-language-processing",
            "description": (
                "DeepLearning.AI specialization on Coursera covering classification, "
                "vector spaces, sequence models, attention mechanisms, and transformers "
                "for NLP. Taught by Younes Bensouda Mourri and Łukasz Kaiser."
            ),
            "institution": "DeepLearning.AI",
            "country": "US",
        },
        {
            "title": "Machine Learning with Python",
            "instructor": "Joseph Santarcangelo",
            "duration": "5 weeks",
            "level": "bachelor",
            "language": "en",
            "link": "https://www.coursera.org/learn/machine-learning-with-python",
            "description": (
                "IBM course on Coursera covering supervised and unsupervised ML, "
                "regression, classification, and clustering with Python and scikit-learn."
            ),
            "institution": "IBM",
            "country": "US",
        },
        {
            "title": "Deep Learning Specialization",
            "instructor": "Andrew Ng",
            "duration": "5 months",
            "level": "bachelor",
            "language": "en",
            "link": "https://www.coursera.org/specializations/deep-learning",
            "description": (
                "DeepLearning.AI specialization teaching neural networks, "
                "hyperparameter tuning, CNNs, RNNs, and sequence models. "
                "Essential foundation for NLP deep learning."
            ),
            "institution": "DeepLearning.AI",
            "country": "US",
        },
        {
            "title": "Introduction to Large Language Models",
            "instructor": "Google Cloud",
            "duration": "1 hour",
            "level": "bachelor",
            "language": "en",
            "link": "https://www.coursera.org/learn/introduction-to-large-language-models",
            "description": (
                "Google Cloud introductory course on LLMs covering what they are, "
                "use cases, prompt tuning, and Google tools for LLM development."
            ),
            "institution": "Google Cloud",
            "country": "US",
        },
        {
            "title": "Applied Text Mining in Python",
            "instructor": "V.G. Vinod Vydiswaran",
            "duration": "5 weeks",
            "level": "bachelor",
            "language": "en",
            "link": "https://www.coursera.org/learn/python-text-mining",
            "description": (
                "University of Michigan course covering text mining, NLP with NLTK, "
                "topic modeling, text classification, and information extraction."
            ),
            "institution": "University of Michigan",
            "country": "US",
        },
        {
            "title": "Prompt Engineering for ChatGPT",
            "instructor": "Dr. Jules White",
            "duration": "18 hours",
            "level": "bachelor",
            "language": "en",
            "link": "https://www.coursera.org/learn/prompt-engineering",
            "description": (
                "Vanderbilt University course on prompt engineering patterns, "
                "chain-of-thought, few-shot learning, and effective interaction "
                "with large language models."
            ),
            "institution": "Vanderbilt University",
            "country": "US",
        },
        {
            "title": "Arabic for Beginners (with NLP Context)",
            "instructor": "Hanan Khallaf",
            "duration": "10 weeks",
            "level": "bachelor",
            "language": "ar",
            "link": "https://www.coursera.org/learn/arabic-language",
            "description": (
                "Introductory Arabic language course valuable for NLP practitioners "
                "working with Arabic text processing, morphology, and tokenization."
            ),
            "institution": "Al-Azhar University",
            "country": "EG",
            "city": "Cairo",
        },
    ]

    def _scrape_coursera(self):
        """Import Coursera NLP-related courses from curated catalog."""
        for item in self.COURSERA_COURSES:
            country = self.get_or_create_country(
                item["institution"][:30], item.get("country", "US"),
            )
            institution = self.get_or_create_institution(
                item["institution"],
                country=country,
                city=item.get("city", ""),
                website=item.get("link", ""),
                inst_type="Other",
            )
            if institution is None:
                self.items_skipped += 1
                continue

            desc = item["description"]
            if item.get("instructor"):
                desc += f"\n\nInstructor: {item['instructor']}"
            if item.get("duration"):
                desc += f"\nDuration: {item['duration']}"

            self._create_course(
                title=item["title"],
                description=desc,
                institution=institution,
                website=item["link"],
                field="nlp",
                level=item.get("level", "bachelor"),
            )

    # ── YouTube NLP Playlists ─────────────────────────────────────────
    YOUTUBE_PLAYLISTS = [
        {
            "title": "Arabic NLP — Full Course (Arabic)",
            "instructor": "Moustafa Alzantot",
            "duration": "15+ videos",
            "level": "bachelor",
            "language": "ar",
            "link": "https://www.youtube.com/playlist?list=PLvLvlVqNQGHC3uV0T6TTndqNDDR69tN3t",
            "description": (
                "Comprehensive Arabic-language YouTube playlist covering NLP "
                "fundamentals including tokenization, stemming, POS tagging, "
                "and Arabic text processing techniques."
            ),
        },
        {
            "title": "Stanford CS224N: NLP with Deep Learning (2023)",
            "instructor": "Christopher Manning",
            "duration": "20 lectures",
            "level": "master",
            "language": "en",
            "link": "https://www.youtube.com/playlist?list=PLoROMvodv4rMFqRtEuo6SGjY4XbRIVRd4",
            "description": (
                "Full Stanford CS224N course lectures covering word vectors, "
                "neural networks for NLP, transformers, pre-trained models, "
                "and current NLP research."
            ),
        },
        {
            "title": "Hugging Face NLP Course",
            "instructor": "Hugging Face Team",
            "duration": "10+ videos",
            "level": "bachelor",
            "language": "en",
            "link": "https://www.youtube.com/playlist?list=PLo2EIpI_JMQvWfQndUesu0nPBAtZ9gP1o",
            "description": (
                "Official Hugging Face course covering transformers, "
                "tokenizers, fine-tuning, and the Hugging Face ecosystem "
                "for practical NLP tasks."
            ),
        },
        {
            "title": "NLP Zero to Hero — TensorFlow (Arabic Subtitles)",
            "instructor": "Laurence Moroney",
            "duration": "4 videos",
            "level": "bachelor",
            "language": "ar",
            "link": "https://www.youtube.com/playlist?list=PLQY2H8rRoyvzDbLUZkbudP-MFQZwNmU4S",
            "description": (
                "TensorFlow NLP series covering text tokenization, "
                "sequence padding, word embeddings, and LSTMs. "
                "Available with Arabic subtitles."
            ),
        },
        {
            "title": "Machine Learning in Arabic — Complete Course",
            "instructor": "Hesham Asem",
            "duration": "40+ videos",
            "level": "bachelor",
            "language": "ar",
            "link": "https://www.youtube.com/playlist?list=PLtsZ69x5q-Xc-ov4-rrFcFgYAprpjwi3Z",
            "description": (
                "Comprehensive machine learning course in Arabic covering "
                "regression, classification, clustering, neural networks, "
                "and practical implementation with Python."
            ),
        },
        {
            "title": "Deep Learning for NLP — CMU CS 11-747",
            "instructor": "Graham Neubig",
            "duration": "25 lectures",
            "level": "master",
            "language": "en",
            "link": "https://www.youtube.com/playlist?list=PL8PYTP1V4I8DZprnWryM4nR8Ik1QuJCBN",
            "description": (
                "Carnegie Mellon advanced NLP course covering cutting-edge "
                "methods in text generation, structured prediction, "
                "low-resource NLP, and multilingual models."
            ),
        },
        {
            "title": "Arabic AI and Deep Learning",
            "instructor": "Ahmed El-Deeb",
            "duration": "20+ videos",
            "level": "bachelor",
            "language": "ar",
            "link": "https://www.youtube.com/playlist?list=PLyhJeMedQd9QnbJIo_UAOHYz2u_4XSGaE",
            "description": (
                "Arabic-language deep learning playlist covering neural "
                "networks, CNNs, RNNs, and their applications in NLP "
                "and computer vision."
            ),
        },
    ]

    def _import_youtube_playlists(self):
        """Import YouTube NLP playlists as courses."""
        yt_country = self.get_or_create_country("International", "XX")
        yt_inst = self.get_or_create_institution(
            "YouTube Educational Content",
            country=yt_country,
            website="https://www.youtube.com",
            inst_type="Other",
        )
        if yt_inst is None:
            return

        for item in self.YOUTUBE_PLAYLISTS:
            desc = item["description"]
            if item.get("instructor"):
                desc += f"\n\nInstructor: {item['instructor']}"
            if item.get("duration"):
                desc += f"\nDuration: {item['duration']}"

            self._create_course(
                title=item["title"],
                description=desc,
                institution=yt_inst,
                website=item["link"],
                field="nlp",
                level=item.get("level", "bachelor"),
            )

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
