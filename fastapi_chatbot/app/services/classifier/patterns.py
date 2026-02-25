"""
Trilingual regex pattern banks for intent classification.

Six intent categories: conceptual_question, platform_query, legal_query,
document_query, bug_query, metadata_query.
"""
import re

# --- Metadata queries (stats, counts, navigation) ---
METADATA_PATTERNS = [
    re.compile(r"\bhow many\b", re.I),
    re.compile(r"\bstatistics?\b", re.I),
    re.compile(r"\bstats\b", re.I),
    re.compile(r"\bcombien\b", re.I),
    re.compile(r"\bstatistiques?\b", re.I),
    re.compile(r"\bكم عدد\b"),
    re.compile(r"\bإحصائيات\b"),
    re.compile(r"\bnavigate\b", re.I),
    re.compile(r"\bwhere (?:is|are|can i find)\b", re.I),
    re.compile(r"\boù (?:est|se trouve|trouver)\b", re.I),
    re.compile(r"\bأين\b"),
]

# --- Platform / structured-data queries ---
PLATFORM_PATTERNS = [
    re.compile(r"\b(?:when was|published|date|year)\b", re.I),
    re.compile(r"\bquand\b", re.I),
    re.compile(r"\bمتى\b"),
    re.compile(r"\b(?:who (?:wrote|created|authored))\b", re.I),
    re.compile(r"\bqui a (?:écrit|créé)\b", re.I),
    re.compile(r"\bمن كتب\b"),
    re.compile(
        r"\b(?:list|show me|find)\b.*\b(?:courses?|articles?|thes[ei]s|"
        r"memoirs?|tools?|corpus|corpora|events?|institutions?|projects?|authors?)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:trouver|montrer|lister)\b.*\b(?:cours|articles?|thèses?|"
        r"mémoires?|outils?|corpus|événements?|institutions?|projets?)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:أعرض|اعثر|قائمة)\b.*\b(?:دورة|مقال|أطروحة|مذكرة|أداة|"
        r"مجموعة|حدث|مؤسسة|مشروع)\b",
    ),
]

PLATFORM_KEYWORDS = {
    # English
    "course", "courses", "article", "articles", "thesis", "theses",
    "memoir", "memoirs", "tool", "tools", "corpus", "corpora",
    "event", "events", "conference", "workshop", "seminar",
    "institution", "university", "project", "author", "researcher",
    # French
    "cours", "thèse", "thèses", "mémoire", "mémoires", "outil",
    "outils", "événement", "événements", "conférence", "atelier",
    "séminaire", "institution", "université", "projet", "auteur",
    "chercheur",
    # Arabic
    "دورة", "مقال", "أطروحة", "مذكرة", "أداة", "مجموعة بيانات",
    "حدث", "مؤتمر", "ورشة", "ندوة", "مؤسسة", "جامعة", "مشروع",
    "مؤلف", "باحث",
}

# --- Legal queries ---
LEGAL_PATTERNS = [
    re.compile(
        r"\b(?:legal|law|regulation|copyright|license|privacy|gdpr|compliance)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:juridique|loi|règlement|droit d'auteur|licence|"
        r"confidentialité|conformité)\b",
        re.I,
    ),
    re.compile(r"\b(?:قانون|تشريع|حقوق|ترخيص|خصوصية|لائحة)\b"),
    re.compile(r"\bis (?:it|this) legal\b", re.I),
    re.compile(r"\best[- ]ce (?:légal|autorisé)\b", re.I),
    re.compile(r"\bهل.*(?:قانوني|مشروع)\b"),
]

# --- Document queries (user-uploaded files) ---
DOCUMENT_PATTERNS = [
    re.compile(r"\b(?:my (?:file|document|upload|pdf))\b", re.I),
    re.compile(
        r"\b(?:uploaded|summarize|summarise)\b.*\b(?:file|document|pdf)\b",
        re.I,
    ),
    re.compile(r"\b(?:mon (?:fichier|document))\b", re.I),
    re.compile(
        r"\b(?:résumer|analyser) (?:mon|le) (?:fichier|document)\b",
        re.I,
    ),
    re.compile(r"\b(?:ملفي|مستندي|وثيقتي)\b"),
    re.compile(r"\bلخص\b.*\b(?:ملف|مستند)\b"),
]

# --- Bug queries ---
BUG_PATTERNS = [
    re.compile(
        r"\b(?:bug|error|crash|traceback|exception|issue|fix|debug|broken)\b",
        re.I,
    ),
    re.compile(r"\b(?:bogue|erreur|plantage|problème technique)\b", re.I),
    re.compile(r"\b(?:خطأ|عطل|مشكلة تقنية|إصلاح)\b"),
]

# --- General knowledge / advice queries (should go directly to LLM) ---
GENERAL_KNOWLEDGE_PATTERNS = [
    # English
    re.compile(
        r"\b(?:suggest|recommend|give me|create|make|build|design|write)\b"
        r".*\b(?:plan|roadmap|path|guide|schedule|curriculum|syllabus|strategy|steps)",
        re.I,
    ),
    re.compile(
        r"\b(?:how (?:to|do i|can i|should i))\b"
        r".*\b(?:learn|study|start|begin|master|improve|get into|get started)",
        re.I,
    ),
    re.compile(
        r"\b(?:tips?|advice|best (?:way|practice|approach)|tutorial)\b"
        r".*\b(?:learn|study|start|begin|master|improve)",
        re.I,
    ),
    re.compile(
        r"\b(?:learning|study) (?:plan|path|roadmap|guide|strategy)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:what (?:should i|do i need to)|where (?:should i|do i)) (?:learn|study|start|begin)\b",
        re.I,
    ),
    # French
    re.compile(
        r"\b(?:suggérer|recommander|proposer|créer|faire|donner)\b"
        r".*\b(?:plan|parcours|programme|stratégie|étapes|guide)",
        re.I,
    ),
    re.compile(
        r"\b(?:comment)\b.*\b(?:apprendre|étudier|commencer|maîtriser|améliorer)",
        re.I,
    ),
    re.compile(
        r"\b(?:conseils?|astuces?|meilleure? (?:façon|méthode|approche))\b"
        r".*\b(?:apprendre|étudier|commencer)",
        re.I,
    ),
    re.compile(
        r"\b(?:plan|parcours|programme) (?:d'apprentissage|d'étude|de formation)\b",
        re.I,
    ),
    # Arabic
    re.compile(
        r"\b(?:اقترح|أنشئ|صمم|ضع|اكتب|أعطني)\b"
        r".*\b(?:خطة|مسار|برنامج|استراتيجية|خطوات|دليل)",
    ),
    re.compile(
        r"\b(?:كيف)\b.*\b(?:أتعلم|أدرس|أبدأ|أتقن|أحسن)",
    ),
    re.compile(
        r"\b(?:نصائح|أفضل (?:طريقة|أسلوب|نهج))\b"
        r".*\b(?:تعلم|دراسة|بدء)",
    ),
    re.compile(
        r"\b(?:خطة|مسار|برنامج) (?:تعلم|دراسة|تدريب)\b",
    ),
]

# Soft document hints (used when session already has docs)
SOFT_DOCUMENT_PATTERN = re.compile(
    r"\b(?:summarize|summarise|explain|analyze|analyse|extract|"
    r"résumer|expliquer|analyser|لخص|اشرح)\b",
    re.I,
)
