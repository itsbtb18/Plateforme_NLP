"""
Trilingual regex pattern banks for intent classification.

Seven intent categories: conceptual_question, platform_query, legal_query,
document_query, bug_query, metadata_query, user_query.
"""

import re

# --- User identity / profile queries ---
USER_QUERY_PATTERNS = [
    # English: "what is my name", "who am I", "my profile", "my info"
    re.compile(
        r"\b(?:what(?:'?s| is) my (?:name|email|bio|profile|info|institution|speciality|specialization))\b",
        re.I,
    ),
    re.compile(r"\bwho am i\b", re.I),
    re.compile(r"\b(?:my (?:name|profile|account|details|information))\b", re.I),
    re.compile(r"\btell me about (?:myself|me)\b", re.I),
    re.compile(r"\bwhats my\b", re.I),
    # "my tools/posts/resources/courses" — asking about own contributions
    re.compile(
        r"\b(?:my |i (?:posted|shared|created|published|uploaded|wrote|made))\b.*"
        r"(?:tool|post|resource|course|document|article|corpus|corpora|project|event|question|answer|topic|contribution|publication)",
        re.I,
    ),
    re.compile(
        r"\b(?:tool|post|resource|course|document|article|corpus|corpora|project|event|topic|contribution)"
        r"s?\b.*\b(?:(?:created|posted|shared|published|uploaded|made|written) by me|by me|that i |i (?:created|posted|shared|published|uploaded|made|wrote))",
        re.I,
    ),
    re.compile(
        r"\b(?:give|show|list|tell|get)\b.*\bmy\b.*(?:tool|post|resource|course|document|project|event|question|answer|contribution|publication)",
        re.I,
    ),
    # "give me all the tools created by me" — requires "by me" or "i" self-ref
    re.compile(
        r"\b(?:give|show|list|tell|get)\b.*(?:tool|post|resource|course|document|project|event|question|answer|contribution|publication)"
        r"s?\b.*\b(?:(?:created|posted|shared|published|uploaded|made|written) by me|by me|that i |i (?:created|posted|shared|published|uploaded|made|wrote))",
        re.I,
    ),
    re.compile(
        r"\b(?:what|which)\b.*\b(?:did i|have i|i(?:'ve| have))\b.*\b(?:post|share|create|publish|upload|write)",
        re.I,
    ),
    # French: "mes outils", "mes publications"
    re.compile(
        r"\bmes (?:outils|publications|ressources|cours|projets|articles|posts)", re.I
    ),
    re.compile(r"\bque j'ai (?:posté|partagé|publié|créé)", re.I),
    # Arabic: "أدواتي", "منشوراتي", "مواردي"
    re.compile(r"(?:أدواتي|منشوراتي|مواردي|مشاريعي|دوراتي|مقالاتي|مساهماتي)"),
    re.compile(r"(?:التي نشرتها|التي شاركتها|التي أنشأتها)"),
    # French self-only
    re.compile(r"\bquel est mon (?:nom|profil|email)\b", re.I),
    re.compile(r"\bqui suis[- ]je\b", re.I),
    re.compile(r"\bmon (?:nom|profil|compte)\b", re.I),
    # Arabic self-only
    re.compile(r"\b(?:ما (?:هو )?اسمي|من أنا)\b"),
    re.compile(r"\bمعلوماتي\b"),
    re.compile(r"\bملفي الشخصي\b"),
    re.compile(r"\bحسابي\b"),
]

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
        r"\b(?:list|show me|find|give|get)\b.*\b(?:courses?|articles?|thes[ei]s|"
        r"memoirs?|tools?|corpus|corpora|events?|institutions?|projects?|authors?|resources?|forum|topics?)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:trouver|montrer|lister)\b.*\b(?:cours|articles?|thèses?|"
        r"mémoires?|outils?|corpus|événements?|institutions?|projets?|forum|sujets?)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:أعرض|اعثر|قائمة)\b.*\b(?:دورة|مقال|أطروحة|مذكرة|أداة|"
        r"مجموعة|حدث|مؤسسة|مشروع|منتدى|موضوع)\b",
    ),
]

PLATFORM_KEYWORDS = {
    # English
    "course",
    "courses",
    "article",
    "articles",
    "thesis",
    "theses",
    "memoir",
    "memoirs",
    "tool",
    "tools",
    "corpus",
    "corpora",
    "event",
    "events",
    "conference",
    "workshop",
    "seminar",
    "institution",
    "university",
    "project",
    "author",
    "researcher",
    "resource",
    "resources",
    # French
    "cours",
    "thèse",
    "thèses",
    "mémoire",
    "mémoires",
    "outil",
    "outils",
    "événement",
    "événements",
    "conférence",
    "atelier",
    "séminaire",
    "institution",
    "université",
    "projet",
    "auteur",
    "chercheur",
    # Arabic
    "دورة",
    "مقال",
    "أطروحة",
    "مذكرة",
    "أداة",
    "مجموعة بيانات",
    "حدث",
    "مؤتمر",
    "ورشة",
    "ندوة",
    "مؤسسة",
    "جامعة",
    "مشروع",
    "مؤلف",
    "باحث",
    # Forum
    "forum",
    "topic",
    "topics",
    "discussion",
    "discussions",
    "sujet",
    "sujets",
    "منتدى",
    "موضوع",
    "مواضيع",
    "نقاش",
}

# --- Specific contributor search patterns (prevents 'researcher' from hijacking RAG) ---
CONTRIBUTOR_SEARCH_PATTERNS = [
    re.compile(r"\b(?:list|show|find|search|get|who is)\b.*\b(?:researcher|chercheur|باحث|author|auteur|مؤلف)\b", re.I),
    re.compile(r"\b(?:profiles?|biographies?|bio)\b.*\b(?:researcher|chercheur|باحث|author|auteur|مؤلف)\b", re.I),
]

# --- Legal queries ---
LEGAL_PATTERNS = [
    re.compile(
        r"\b(?:legal|laws?|regulations?|decrees?|provisions?|articles?|copyright|licens?e|privacy|gdpr|compliance)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:juridiques?|lois?|règlements?|décrets?|dispositions?|articles?|droit d'auteur|licence|"
        r"confidentialité|conformité)\b",
        re.I,
    ),
    re.compile(r"\b(?:قانون|قوانين|تشريع|تشريعات|مرسوم|مراسيم|مادة|مواد|بند|بنود|تنظيم|حقوق|ترخيص|خصوصية|لائحة|لوائح|بيانات|حماية|شروط|إجراءات|نظام|أحكام)\w*\b"),
    re.compile(r"\bis (?:it|this) legal\b", re.I),
    re.compile(r"\best[- ]ce (?:légal|autorisé)\b", re.I),
    re.compile(r"\bهل.*(?:قانوني|مشروع)\b"),
]

# --- Document queries (user-uploaded files) ---
# ONLY explicit document references trigger this intent.
# Generic verbs (explain, summarize) without document words do NOT match.
DOCUMENT_PATTERNS = [
    # English — explicit document references
    re.compile(r"\b(?:my (?:file|document|upload|pdf))\b", re.I),
    re.compile(r"\b(?:uploaded|summarize|summarise)\b.*\b(?:file|document|pdf)\b", re.I),
    re.compile(r"\bin (?:this|the|my) (?:document|file|pdf|paper|upload)\b", re.I),
    re.compile(r"\b(?:what does|according to) (?:this|the|my) (?:document|file|pdf|paper)\b", re.I),
    re.compile(r"\b(?:from|in) (?:the )?uploaded (?:file|document|pdf)\b", re.I),
    re.compile(r"\bsummarize my (?:pdf|document|file|paper)\b", re.I),
    re.compile(r"\bexplain (?:this|the) (?:document|paper|pdf|file)\b", re.I),
    # French — explicit document references
    re.compile(r"\b(?:mon (?:fichier|document|pdf))\b", re.I),
    re.compile(r"\b(?:résumer|analyser) (?:mon|le|ce) (?:fichier|document|pdf)\b", re.I),
    re.compile(r"\bdans (?:ce|le|mon) (?:document|fichier|pdf)\b", re.I),
    re.compile(r"\bque dit (?:ce|le|mon) (?:document|fichier)\b", re.I),
    re.compile(r"\bselon (?:ce|le|mon) (?:document|fichier|pdf)\b", re.I),
    # Arabic — explicit document references
    re.compile(r"\b(?:ملفي|مستندي|وثيقتي)\b"),
    re.compile(r"\bلخص\b.*\b(?:ملف|مستند|وثيقة)\b"),
    re.compile(r"\b(?:في|من|حسب) (?:هذا |هذه )?(?:الملف|المستند|الوثيقة|الـ ?pdf)\b"),
    re.compile(r"\bماذا (?:يقول|يذكر|يحتوي) (?:هذا )?(?:الملف|المستند)\b"),
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
    # Greetings — short social messages that need no context/profile injection
    re.compile(
        r"^\s*(?:hi|hello|hey|yo|hiya|howdy|greetings|good\s*(?:morning|afternoon|evening|day)|thanks?(?:\s*you)?|thank\s*u|welcome)\s*[!?.]*\s*$",
        re.I,
    ),
    re.compile(
        r"^\s*(?:bonjour|salut|bonsoir|coucou|bonne\s*(?:journée|soirée)|merci)\s*[!?.]*\s*$",
        re.I,
    ),
    re.compile(
        r"^\s*(?:مرحبا|مرحبًا|سلام|أهلا|السلام عليكم|صباح الخير|مساء الخير|أهلاً|هلا|شكرا|شكراً)\s*[!?.]*\s*$"
    ),
    # Chatbot self-identity ("who are you", "what are you", etc.)
    re.compile(r"\bwho are you\b", re.I),
    re.compile(r"\bwhat are you\b", re.I),
    re.compile(r"\btell me about yourself\b", re.I),
    re.compile(r"\bintroduce yourself\b", re.I),
    re.compile(r"\bqui es[- ]tu\b", re.I),
    re.compile(r"\bqu'es[- ]tu\b", re.I),
    re.compile(r"\bprésentez?[- ](?:toi|vous)\b", re.I),
    re.compile(r"(?:من أنت|ما أنت|عرّف (?:عن )?نفسك)"),
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
    # Conversational / advisory — no retrieval needed
    re.compile(
        r"\b(?:how (?:to|do i|can i|should i))\b"
        r".*\b(?:build|create|make|design|develop|implement|write|set up|deploy)",
        re.I,
    ),
    re.compile(
        r"\b(?:brainstorm|ideate|ideas? for|think of|come up with)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:what is|what are|what's|explain|define|describe)\b"
        r".*\b(?:the (?:difference|concept|idea|purpose|role|meaning|definition))\b",
        re.I,
    ),
    re.compile(
        r"\b(?:compare|pros? and cons?|advantages?|disadvantages?|trade-?offs?)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:can you|could you|help me)\b.*\b(?:explain|understand|clarify|elaborate)\b",
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
    # Arabic conversational / advisory
    re.compile(r"\b(?:كيف (?:أبني|أصمم|أنشئ|أطور|أكتب))\b"),
    re.compile(r"\b(?:أفكار|اقتراحات|عصف ذهني)\b"),
    # French conversational / advisory
    re.compile(
        r"\b(?:comment)\b.*\b(?:construire|créer|développer|concevoir|implémenter|déployer)",
        re.I,
    ),
    re.compile(
        r"\b(?:idées?|brainstorm|réfléchir)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:comparer|avantages?|inconvénients?|différences?)\b",
        re.I,
    ),
    # Advisory / rule-based / theoretical — prevents platform keyword leak
    # English
    re.compile(
        r"\b(?:what|which)\b.*\b(?:rules?|principles?|guidelines?|best practices?|standards?|criteria|ethics?|norms?)\b",
        re.I,
    ),
    re.compile(r"\b(?:how|why)\s+should\b", re.I),
    # French
    re.compile(
        r"\b(?:quelles?|quels?)\b.*\b(?:règles?|principes?|lignes directrices|bonnes pratiques|normes?|critères?|éthiques?)\b",
        re.I,
    ),
    re.compile(r"\b(?:comment|pourquoi)\s+(?:devrait|faut[- ]il|doit[- ]on)\b", re.I),
    # Arabic
    re.compile(r"\b(?:ما هي|ما)\b.*\b(?:قواعد|مبادئ|إرشادات|معايير|أخلاقيات|ممارسات)\b"),
    re.compile(r"\b(?:كيف|لماذا)\s+(?:يجب|ينبغي)\b"),
]

# --- Conceptual / educational questions (should go to Qdrant RAG) ---
# Broad definitional, explanatory, or "how does X work" queries that
# benefit from NLP-knowledge retrieval rather than LLM-direct answers.
CONCEPTUAL_QUESTION_PATTERNS = [
    # English — "what is X", "explain X", "define X", "how does X work"
    re.compile(
        r"\b(?:what is|what are|what's)\b(?!\s+(?:my|your)\b)",
        re.I,
    ),
    re.compile(r"\b(?:define|definition of)\b", re.I),
    re.compile(
        r"\b(?:explain|describe)\b(?!.*\b(?:document|file|pdf|paper|upload)\b)",
        re.I,
    ),
    re.compile(r"\bhow does\b.*\bwork\b", re.I),
    re.compile(r"\bwhat does\b.*\bmean\b", re.I),
    re.compile(r"\btell me about\b(?!\s+(?:myself|me)\b)", re.I),
    # French — "qu'est-ce que", "c'est quoi", "expliquer", "définir"
    re.compile(r"\bqu'est[- ]ce que?\b", re.I),
    re.compile(r"\bc'est quoi\b", re.I),
    re.compile(
        r"\b(?:expliquer?|définir?|décrire?)\b(?!.*\b(?:fichier|document|pdf)\b)",
        re.I,
    ),
    re.compile(r"\bcomment fonctionne\b", re.I),
    re.compile(r"\bque (?:signifie|veut dire)\b", re.I),
    re.compile(r"\bparle[- ]moi de\b", re.I),
    # Arabic — "ما هو", "ما هي", "اشرح", "عرّف"
    re.compile(r"\bما (?:هو|هي|هم|المقصود بـ?)\b"),
    re.compile(r"\b(?:اشرح|عرّف|صف)\b(?!.*\b(?:ملف|مستند|وثيقة)\b)"),
    re.compile(r"\bكيف (?:يعمل|تعمل)\b"),
    re.compile(r"\bما (?:معنى|مفهوم)\b"),
    re.compile(r"\bحدثني عن\b"),
]

# Soft document hints — DISABLED.
# Was causing false positives: generic verbs like "explain" or "summarize"
# triggered document_query even for conceptual questions.
# SOFT_DOCUMENT_PATTERN = re.compile(
#     r"\b(?:summarize|summarise|explain|analyze|analyse|extract|"
#     r"résumer|expliquer|analyser|لخص|اشرح)\b",
#     re.I,
# )


# ---------------------------------------------------------------------------
# Resource type extraction — maps query keywords to platform resource types
# ---------------------------------------------------------------------------

RESOURCE_TYPE_MAP = {
    # English
    "tool": "tool",
    "tools": "tool",
    "nlp tool": "tool",
    "nlp tools": "tool",
    "course": "course",
    "courses": "course",
    "article": "article",
    "articles": "article",
    "paper": "article",
    "papers": "article",
    "thesis": "thesis",
    "theses": "thesis",
    "memoir": "memoir",
    "memoirs": "memoir",
    "corpus": "corpus",
    "corpora": "corpus",
    "dataset": "corpus",
    "datasets": "corpus",
    "event": "event",
    "events": "event",
    "conference": "event",
    "conferences": "event",
    "workshop": "event",
    "workshops": "event",
    "seminar": "event",
    "seminars": "event",
    "institution": "institution",
    "institutions": "institution",
    "university": "institution",
    "universities": "institution",
    "project": "project",
    "projects": "project",
    "researcher": "author",
    "researchers": "author",
    "author": "author",
    "authors": "author",
    "user": "author",
    "users": "author",
    "member": "author",
    "members": "author",
    # French
    "outil": "tool",
    "outils": "tool",
    "cours": "course",
    "thèse": "thesis",
    "thèses": "thesis",
    "mémoire": "memoir",
    "mémoires": "memoir",
    "événement": "event",
    "événements": "event",
    "conférence": "event",
    "atelier": "event",
    "séminaire": "event",
    "projet": "project",
    "projets": "project",
    "auteur": "author",
    "chercheur": "author",
    # Arabic
    "أداة": "tool",
    "أدوات": "tool",
    "دورة": "course",
    "دورات": "course",
    "مقال": "article",
    "مقالات": "article",
    "أطروحة": "thesis",
    "مذكرة": "memoir",
    "مجموعة بيانات": "corpus",
    "حدث": "event",
    "أحداث": "event",
    "مؤتمر": "event",
    "ورشة": "event",
    "ندوة": "event",
    "مؤسسة": "institution",
    "جامعة": "institution",
    "مشروع": "project",
    "مشاريع": "project",
    "باحث": "author",
    "مؤلف": "author",
    # Forum / Topics
    "forum": "topic",
    "topic": "topic",
    "topics": "topic",
    "discussion": "topic",
    "discussions": "topic",
    "sujet": "topic",
    "sujets": "topic",
    "منتدى": "topic",
    "موضوع": "topic",
    "مواضيع": "topic",
    "نقاش": "topic",
}


def extract_resource_type(query: str) -> str | None:
    """Extract the target resource type from a user query.

    Returns one of: tool, course, article, thesis, memoir, corpus,
    event, institution, project, author, or None.
    """
    q = query.lower().strip()
    # Check longer phrases first, then single words
    for phrase in sorted(RESOURCE_TYPE_MAP.keys(), key=len, reverse=True):
        if phrase in q:
            return RESOURCE_TYPE_MAP[phrase]
    return None
