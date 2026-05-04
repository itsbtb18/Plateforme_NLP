from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
import datetime
import os

W, H = A4
M = 2.1 * cm

# ─── palette ────────────────────────────────────────────────────
NAVY   = colors.HexColor("#0F2144")
BLUE   = colors.HexColor("#1D4ED8")
LBLUE  = colors.HexColor("#DBEAFE")
TEAL   = colors.HexColor("#0F766E")
LTEAL  = colors.HexColor("#CCFBF1")
GREEN  = colors.HexColor("#166534")
LGREEN = colors.HexColor("#DCFCE7")
AMBER  = colors.HexColor("#92400E")
LAMBER = colors.HexColor("#FEF3C7")
PURPLE = colors.HexColor("#5B21B6")
LPURPLE= colors.HexColor("#EDE9FE")
RED    = colors.HexColor("#991B1B")
LRED   = colors.HexColor("#FEE2E2")
SLATE  = colors.HexColor("#334155")
MUTED  = colors.HexColor("#64748B")
LIGHT  = colors.HexColor("#F8FAFC")
LINE   = colors.HexColor("#CBD5E1")
WHITE  = colors.white
BLACK  = colors.HexColor("#0F172A")

# ─── style factory ──────────────────────────────────────────────
def ps(name, **k):
    return ParagraphStyle(name, **k)

BODY  = ps("body",  fontSize=10, leading=16, textColor=BLACK,  fontName="Helvetica", alignment=TA_JUSTIFY, spaceAfter=7)
BODYL = ps("bodyl", fontSize=10, leading=16, textColor=BLACK,  fontName="Helvetica", alignment=TA_LEFT,    spaceAfter=5)
H1    = ps("h1",    fontSize=21, leading=28, textColor=NAVY,   fontName="Helvetica-Bold", spaceBefore=4,  spaceAfter=10)
H2    = ps("h2",    fontSize=14, leading=20, textColor=NAVY,   fontName="Helvetica-Bold", spaceBefore=16, spaceAfter=7)
H3    = ps("h3",    fontSize=11, leading=16, textColor=SLATE,  fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=5)
SMALL = ps("small", fontSize=8,  leading=12, textColor=MUTED,  fontName="Helvetica")
CHNUM = ps("chnum", fontSize=10, leading=14, textColor=BLUE,   fontName="Helvetica-Bold", spaceBefore=20, spaceAfter=3)
CAPT  = ps("capt",  fontSize=8.5,leading=12,textColor=MUTED,  fontName="Helvetica", alignment=TA_CENTER, spaceAfter=8)
BULL  = ps("bull",  fontSize=10, leading=16, textColor=BLACK,  fontName="Helvetica", leftIndent=16, firstLineIndent=-12, spaceAfter=3)
CODE  = ps("code",  fontSize=8.5,leading=13, textColor=colors.HexColor("#1E293B"),
           fontName="Courier", leftIndent=10, rightIndent=10, backColor=LIGHT, spaceAfter=6, spaceBefore=4)

def sp(h=8):   return Spacer(1, h)
def hr(c=LINE): return HRFlowable(width="100%", thickness=0.5, color=c, spaceAfter=8, spaceBefore=4)
def p(t):  return Paragraph(t, BODY)
def pl(t): return Paragraph(t, BODYL)
def h2(t): return Paragraph(t, H2)
def h3(t): return Paragraph(t, H3)
def bul(t): return Paragraph(f"<bullet>&#x25CF;</bullet>  {t}", BULL)
def code(t): return Paragraph(t.replace(" ","&nbsp;").replace("\n","<br/>"), CODE)

def box(text, bg, fg):
    t = Table([[Paragraph(text, ps("bx", fontSize=10, leading=15, textColor=fg,
               fontName="Helvetica", alignment=TA_LEFT))]],
              colWidths=[W - 2*M])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), bg),
        ("LEFTPADDING",  (0,0),(-1,-1), 12),
        ("RIGHTPADDING", (0,0),(-1,-1), 12),
        ("TOPPADDING",   (0,0),(-1,-1), 9),
        ("BOTTOMPADDING",(0,0),(-1,-1), 9),
    ]))
    return t

def info(text):  return box(f"<b>i</b>  {text}", LBLUE,  BLUE)
def tip(text):   return box(f"<b>+</b>  {text}", LGREEN, GREEN)
def concept(text): return box(text, LPURPLE, PURPLE)
def highlight(text): return box(text, LAMBER, AMBER)

def ch_header(num, title, subtitle=""):
    return [
        Paragraph(f"Chapter {num}", CHNUM),
        Paragraph(title, H1),
        (Paragraph(subtitle, ps("sub", fontSize=12, leading=18, textColor=MUTED,
                                fontName="Helvetica", spaceAfter=10)) if subtitle else sp(2)),
        hr(NAVY),
        sp(6),
    ]

def tbl(headers, rows, cws=None):
    usable = W - 2*M
    if cws is None:
        cws = [usable/len(headers)]*len(headers)
    hs = ps("th", fontSize=9, fontName="Helvetica-Bold", textColor=WHITE, alignment=TA_CENTER)
    ds = ps("td", fontSize=9, fontName="Helvetica",      textColor=BLACK, alignment=TA_LEFT, leading=13)
    data = [[Paragraph(h, hs) for h in headers]]
    for r in rows:
        data.append([Paragraph(str(c), ds) for c in r])
    t = Table(data, colWidths=cws)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  NAVY),
        ("ROWBACKGROUND", (0,1), (-1,-1), [WHITE, LIGHT]),
        ("GRID",          (0,0), (-1,-1), 0.3, LINE),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 7),
        ("RIGHTPADDING",  (0,0), (-1,-1), 7),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))
    return t

# ─── page callbacks ──────────────────────────────────────────────
def later(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, H-1.05*cm, W, 1.05*cm, fill=1, stroke=0)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(WHITE)
    canvas.drawString(M, H-0.68*cm, "Arabic NLP Platform — Web Scraping Module — Technical Guide")
    canvas.drawRightString(W-M, H-0.68*cm, "For Jury Presentation · April 2026")
    canvas.setFillColor(LINE)
    canvas.rect(M, 1.15*cm, W-2*M, 0.4, fill=1, stroke=0)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(M, 0.7*cm, "Confidential — Academic Submission")
    canvas.drawRightString(W-M, 0.7*cm, f"Page {doc.page}")
    canvas.restoreState()

def first(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#1E3A6E"))
    canvas.rect(0, 0, W, H*0.35, fill=1, stroke=0)
    canvas.restoreState()

# ─── chapters ────────────────────────────────────────────────────
def cover():
    def w(name, **k):
        if "textColor" not in k: k["textColor"] = WHITE
        return ps(name, **k)
    e = [sp(160)]
    e.append(Paragraph("Arabic NLP Platform", w("s1", fontSize=12, fontName="Helvetica",
             alignment=TA_CENTER, textColor=colors.HexColor("#93C5FD"), spaceAfter=10)))
    e.append(Paragraph("Web Scraping Module", w("s2", fontSize=32, fontName="Helvetica-Bold",
             alignment=TA_CENTER, leading=40, spaceAfter=5)))
    e.append(Paragraph("Complete Technical Guide", w("s3", fontSize=22, fontName="Helvetica",
             alignment=TA_CENTER, leading=30, spaceAfter=6,
             textColor=colors.HexColor("#93C5FD"))))
    e.append(hr(colors.HexColor("#3B82F6")))
    e.append(sp(12))
    e.append(Paragraph(
        "From beginner-friendly explanations to jury-ready technical depth —\n"
        "everything you need to understand and present this system.",
        w("s4", fontSize=12, fontName="Helvetica", alignment=TA_CENTER,
          leading=20, textColor=colors.HexColor("#CBD5E1"), spaceAfter=40)))
    e.append(Paragraph("April 2026  ·  Version 2.0  ·  ~14,900 lines of code",
        w("s5", fontSize=10, fontName="Helvetica", alignment=TA_CENTER,
          textColor=colors.HexColor("#94A3B8"))))
    e.append(PageBreak())
    return e

def toc():
    e = [sp(20)]
    e.append(Paragraph("Table of Contents", ps("toch", fontSize=22, fontName="Helvetica-Bold",
             textColor=NAVY, spaceAfter=20)))
    e.append(hr())
    chapters = [
        ("1",  "What Is This System? — The Big Picture",       "Platform overview and what problem it solves"),
        ("2",  "How the Internet Search Works (Tavily)",        "Discovery layer explained simply"),
        ("3",  "How the AI Reads Web Pages (LLM Extraction)",  "The intelligence behind content parsing"),
        ("4",  "How the System Avoids Duplicates",             "Three-tier deduplication explained"),
        ("5",  "How the System Scores Quality",                "Confidence scoring algorithm"),
        ("6",  "How Pages Are Filtered Before Processing",     "Pre-flight validation framework"),
        ("7",  "How the System Handles Failures",              "Resilience, circuit breakers, retries"),
        ("8",  "How Everything Runs in the Background",        "Celery task orchestration"),
        ("9",  "How the System Is Monitored in Real-Time",     "WebSockets and Prometheus metrics"),
        ("10", "The Tech Stack — Every Framework Explained",   "Django, Redis, PostgreSQL and more"),
        ("11", "Why This Is Better Than Other Scrapers",       "Competitive advantages"),
        ("12", "The Code Architecture — File by File",         "Module structure explained"),
        ("13", "Key Technical Concepts Glossary",              "Terms your jury will expect you to know"),
    ]
    usable = W - 2*M
    for num, title, desc in chapters:
        row = [[
            Paragraph(num, ps("tn", fontSize=11, fontName="Helvetica-Bold",
                      textColor=BLUE, alignment=TA_CENTER)),
            Paragraph(f"<b>{title}</b><br/><font color='#64748B' size='9'>{desc}</font>",
                      ps("tt", fontSize=10, fontName="Helvetica", textColor=BLACK, leading=16)),
        ]]
        t = Table(row, colWidths=[1.1*cm, usable-1.1*cm])
        t.setStyle(TableStyle([
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",    (0,0), (-1,-1), 7),
            ("BOTTOMPADDING", (0,0), (-1,-1), 7),
            ("LINEBELOW",     (0,0), (-1,-1), 0.3, LINE),
        ]))
        e.append(t)
    e.append(PageBreak())
    return e

def ch1():
    e = ch_header("1", "What Is This System?", "The big picture — what it does and why it matters")
    e.append(p(
        "Before diving into any code or technology, let us start with the fundamental question: "
        "<b>what problem does this system solve?</b>"
    ))
    e.append(h2("The Problem"))
    e.append(p(
        "Arabic Natural Language Processing (Arabic NLP) is a fast-growing field of computer science "
        "that teaches computers to understand and work with the Arabic language. New tools, datasets, "
        "research papers, academic events, courses, and job opportunities appear on the internet "
        "every single day — scattered across hundreds of different websites, in different languages, "
        "and in different formats."
    ))
    e.append(p(
        "If you wanted to keep a database of all Arabic NLP resources up-to-date <i>manually</i>, "
        "you would need a team of people browsing the web every day, reading pages, filling in "
        "forms, and avoiding adding the same resource twice. This does not scale. It is too slow, "
        "too expensive, and too error-prone."
    ))
    e.append(h2("The Solution"))
    e.append(p(
        "This Web Scraping Module is an <b>automated knowledge acquisition system</b>. "
        "It works 24/7 without human intervention to:"
    ))
    e.append(bul("Search the internet for relevant pages using AI-powered search APIs"))
    e.append(bul("Read and understand each page using Large Language Models (AI)"))
    e.append(bul("Extract structured information and fill it into a database automatically"))
    e.append(bul("Check for quality — rejecting spam, irrelevant pages, and incomplete data"))
    e.append(bul("Avoid storing the same resource twice using three different detection methods"))
    e.append(bul("Handle failures gracefully — if one source breaks, the rest keep working"))
    e.append(sp(6))
    e.append(info("Think of it like a robot librarian that continuously reads the internet, "
                  "decides what is relevant, fills in library catalog cards, and files them — "
                  "without ever sleeping."))
    e.append(sp(8))
    e.append(h2("The 6 Resource Categories"))
    e.append(p("The system collects 6 types of Arabic NLP resources:"))
    e.append(tbl(
        ["Category", "What It Collects", "Example"],
        [
            ["Events",        "Academic conferences, workshops, calls for papers", "ACL 2026, ArabicNLP Workshop"],
            ["Tools",         "Software libraries and AI tools for Arabic NLP",    "AraBERT, CAMeL Tools on GitHub"],
            ["News",          "Research papers and technical articles",             "arXiv papers on Arabic LLMs"],
            ["Courses",       "Online learning resources",                          "Coursera NLP Specialization"],
            ["Corpus",        "Datasets and language benchmarks",                   "ARCD dataset on HuggingFace"],
            ["Opportunities", "Research positions, PhD offers, grants",             "EURAXESS NLP researcher post"],
        ],
        cws=[2.8*cm, 5.5*cm, 7.6*cm]
    ))
    e.append(sp(10))
    e.append(h2("The 5-Stage Pipeline"))
    e.append(p("Every resource goes through 5 sequential stages before being saved:"))
    stages = [
        ("Stage 1 — DISCOVER", "BLUE", "The system searches the internet using queries like 'Arabic NLP conference 2026' and gets back a list of web page URLs."),
        ("Stage 2 — VALIDATE", "TEAL", "Before spending money on AI processing, cheap checks confirm the page is accessible and actually contains NLP content."),
        ("Stage 3 — EXTRACT",  "PURPLE", "An AI model reads the full page text and fills in a structured form: title, description, date, type, etc."),
        ("Stage 4 — SCORE",    "AMBER", "Each extracted item gets a quality score from 0 to 100. Items below 30 are rejected automatically."),
        ("Stage 5 — SAVE",     "GREEN", "Passing items are checked against the database for duplicates, then saved permanently."),
    ]
    color_map = {"BLUE": (LBLUE, BLUE), "TEAL": (LTEAL, TEAL), "PURPLE": (LPURPLE, PURPLE),
                 "AMBER": (LAMBER, AMBER), "GREEN": (LGREEN, GREEN)}
    for label, c, desc in stages:
        bg, fg = color_map[c]
        e.append(box(f"<b>{label}</b><br/>{desc}", bg, fg))
        e.append(sp(4))
    e.append(PageBreak())
    return e

def ch2():
    e = ch_header("2", "How the Internet Search Works", "Discovery Layer — Tavily Search API")
    e.append(h2("The Challenge of Finding Web Pages"))
    e.append(p(
        "Before the system can extract anything, it needs to know <i>which</i> web pages to look at. "
        "It cannot browse every website on the internet — that would take years. Instead, it uses "
        "a specialised search API called <b>Tavily</b>."
    ))
    e.append(h2("What Is an API?"))
    e.append(concept(
        "<b>API stands for Application Programming Interface.</b> Think of it as a waiter in a restaurant. "
        "You (the program) tell the waiter (the API) what you want. The waiter goes to the kitchen "
        "(the server) and brings back your order (the data). You never have to go to the kitchen yourself. "
        "In our case: the program sends a search query, Tavily searches the web, and sends back a list of URLs."
    ))
    e.append(sp(6))
    e.append(h2("What Is Tavily?"))
    e.append(p(
        "Tavily is a search API specifically designed for AI applications. Unlike Google Search "
        "(which gives back links for humans to click), Tavily returns <b>clean, structured content "
        "ready for machine processing</b> — including the full text of pages, not just snippets. "
        "It also supports 'advanced' search depth which crawls pages more deeply, finding content "
        "that regular search might miss."
    ))
    e.append(h2("Multi-Key Rotation — Never Running Out of Quota"))
    e.append(p(
        "Every API has a limit on how many requests you can make per day or per minute — this is called "
        "a <b>quota</b>. If you hit the limit, the API stops responding. To work around this, the system "
        "maintains <b>multiple Tavily API keys</b> and switches between them automatically:"
    ))
    e.append(bul("Primary key is used first for every request"))
    e.append(bul("If the primary key hits its quota limit (HTTP 429 error), the system instantly switches to the backup key"))
    e.append(bul("The user never notices — the pipeline continues without interruption"))
    e.append(sp(6))
    e.append(info("This is like having two prepaid phone credit balances — when one runs out, the call "
                  "automatically switches to the backup without the conversation dropping."))
    e.append(sp(8))
    e.append(h2("Smart Queries per Category"))
    e.append(p(
        "The system does not send the same generic query for everything. Each of the 6 categories "
        "has its own tailored search strategy:"
    ))
    e.append(tbl(
        ["Category", "Example Search Query", "Search Depth", "Max Results"],
        [
            ["Events",        "Arabic NLP conference 2026 call for papers",     "advanced", "10"],
            ["Tools",         "Arabic NLP open source library GitHub 2025",     "advanced", "10"],
            ["News",          "Arabic large language model research arXiv",     "advanced", "10"],
            ["Courses",       "Arabic NLP online course Coursera edX",          "advanced", "10"],
            ["Corpus",        "Arabic dataset NLP HuggingFace download",        "advanced", "10"],
            ["Opportunities", "NLP researcher position Arabic language 2026",   "advanced", "10"],
        ],
        cws=[2.8*cm, 6*cm, 2.8*cm, 2.8*cm]
    ))
    e.append(sp(8))
    e.append(h2("Query Deduplication"))
    e.append(p(
        "To avoid wasting API credits, the system normalizes all queries (lowercase, strip punctuation) "
        "and removes duplicates before sending them. For events, the system also automatically "
        "generates year-parameterized variants: 'Arabic NLP conference 2025', 'Arabic NLP conference 2026', etc."
    ))
    e.append(PageBreak())
    return e

def ch3():
    e = ch_header("3", "How the AI Reads Web Pages", "LLM-Based Content Extraction Engine")
    e.append(h2("What Is a Large Language Model (LLM)?"))
    e.append(concept(
        "<b>A Large Language Model (LLM) is an AI trained on billions of web pages, books, and articles. "
        "It can read a piece of text and answer questions about it, summarize it, translate it, or extract "
        "specific information from it — all without being explicitly programmed with rules.</b> Famous examples "
        "include ChatGPT (OpenAI), Gemini (Google), and Llama (Meta/Groq)."
    ))
    e.append(sp(6))
    e.append(p(
        "Instead of writing code like <i>\"find the text between the h1 tag and the comma\"</i> "
        "(which breaks on every different website layout), the system simply asks the AI: "
        "<i>\"Read this page and tell me the title, description, date, and type of this event.\"</i> "
        "The AI understands the content regardless of HTML structure."
    ))
    e.append(h2("Dual-Provider Architecture — Two AI Brains"))
    e.append(p(
        "The system uses <b>two different LLM providers</b> to ensure reliability. If one fails "
        "or hits its quota, the other takes over instantly:"
    ))
    e.append(tbl(
        ["Provider", "Model", "Role", "When Used"],
        [
            ["Google Gemini", "gemini-2.0-flash", "Primary", "First choice for every extraction"],
            ["Groq (Llama 3)", "llama-3.3-70b-versatile", "Fallback", "When Gemini fails or is rate-limited"],
        ],
        cws=[3*cm, 4.5*cm, 2.5*cm, 5.9*cm]
    ))
    e.append(sp(8))
    e.append(info("Groq is a hardware company that runs Meta's open-source Llama AI model on custom "
                  "silicon chips (called LPUs) that are 10x faster than regular GPUs for language tasks."))
    e.append(sp(8))
    e.append(h2("What Does 'Extraction' Mean in Practice?"))
    e.append(p(
        "When a web page passes validation, its full text is sent to the AI with a detailed prompt. "
        "The prompt tells the AI: <i>\"You are an expert in Arabic NLP. Read this page content and "
        "extract the following fields in JSON format...\"</i>"
    ))
    e.append(p("The AI responds with a structured JSON object like this:"))
    e.append(box(
        '{ "title_en": "ArabicNLP 2026 — Workshop on Arabic NLP", '
        '"title_ar": "workshop Arabic NLP 2026", '
        '"description_en": "Annual workshop co-located with ACL 2026...", '
        '"start_date": "2026-08-01", "end_date": "2026-08-02", '
        '"location_en": "Vienna, Austria", '
        '"event_type": "workshop", "is_relevant": true, "quality_score": 87 }',
        LIGHT, SLATE
    ))
    e.append(sp(8))
    e.append(h2("Why JSON Format?"))
    e.append(p(
        "JSON (JavaScript Object Notation) is a standard format for structured data that programming "
        "languages can read easily. By asking the AI to always respond in JSON, the system can "
        "automatically parse the answer and put each field into the right database column — no "
        "human interpretation needed."
    ))
    e.append(h2("API Key Rotation for LLMs"))
    e.append(p(
        "Just like Tavily, both LLM providers have usage limits. The system maintains "
        "<b>pools of multiple API keys</b> for each provider and rotates through them using "
        "a round-robin strategy (first key second key third key back to first...). "
        "For Gemini specifically, the system tracks:"
    ))
    e.append(bul("<b>RPM (Requests Per Minute)</b> — maximum calls per minute per key"))
    e.append(bul("<b>RPD (Requests Per Day)</b> — maximum calls per day per key"))
    e.append(bul("<b>429 Cooldown</b> — if a key gets rate-limited, it waits 65 seconds before trying again"))
    e.append(sp(6))
    e.append(h2("BeautifulSoup — Cleaning the HTML"))
    e.append(p(
        "Before sending a page to the AI, the system must clean the raw HTML. A typical web page "
        "contains navigation menus, cookie banners, JavaScript code, and footer links — none of "
        "which is useful. <b>BeautifulSoup</b> is a Python library that parses HTML and lets the "
        "system surgically remove noise:"
    ))
    e.append(bul("Removes all script, style, nav, footer, header tags"))
    e.append(bul("Extracts meaningful text from h1, h2, p, li tags"))
    e.append(bul("Truncates output to 18,000 characters to stay within the AI's context window"))
    e.append(sp(6))
    e.append(tip("This pre-cleaning step reduces token usage (and therefore cost) by up to 70%, "
                 "because the AI only reads the meaningful content, not hundreds of lines of JavaScript."))
    e.append(PageBreak())
    return e

def ch4():
    e = ch_header("4", "How the System Avoids Duplicates", "Three-Tier Deduplication Framework")
    e.append(p(
        "When scraping the internet continuously, the same resource appears multiple times. "
        "The same arXiv paper gets shared on Twitter, ResearchGate, LinkedIn, and 10 different "
        "news aggregators. Without deduplication, the database would be full of copies. "
        "The system uses <b>three completely different methods</b>, applied one after another — "
        "from cheapest to most expensive."
    ))
    e.append(concept(
        "<b>The cascade principle:</b> Run the fastest, cheapest check first. Only if it does not "
        "find a duplicate, run the next check. This saves computation time — most duplicates are "
        "caught by Tier 1 alone (exact URL match), so Tiers 2 and 3 are rarely needed."
    ))
    e.append(sp(8))
    e.append(h2("Tier 1 — Exact URL Match (Fastest)"))
    e.append(p(
        "The simplest check: does a record with this exact URL already exist in the database? "
        "The URL is first <b>normalized</b> — converting to lowercase, removing 'www.', stripping "
        "trailing slashes, removing query parameters — so that these two URLs are treated as the same:"
    ))
    e.append(box("https://WWW.arxiv.org/abs/2604.12345?utm_source=twitter  ==  https://arxiv.org/abs/2604.12345", LIGHT, SLATE))
    e.append(p(
        "For academic resources, special identifiers are also checked: <b>arXiv ID</b> "
        "(e.g., 2604.12345), <b>DOI</b> (Digital Object Identifier), and <b>ROR ID</b> "
        "(Research Organization Registry ID for institutions)."
    ))
    e.append(h2("Tier 2 — Fuzzy Title Matching (Medium)"))
    e.append(p(
        "Sometimes the same resource appears at two different URLs. The system then compares "
        "<b>titles</b> using a similarity algorithm called <b>SequenceMatcher</b>:"
    ))
    e.append(concept(
        "<b>SequenceMatcher</b> compares two strings character by character and calculates how "
        "similar they are, from 0.0 (completely different) to 1.0 (identical). For example:\n\n"
        '"ArabicBERT: A Pre-trained Language Model" and\n'
        '"ArabicBERT — Pre-trained Language Model for Arabic"\n'
        "might score 0.87 — above the threshold of 0.85, so they are treated as duplicates."
    ))
    e.append(sp(6))
    e.append(p("Different categories use different strictness thresholds:"))
    e.append(tbl(
        ["Category", "Threshold", "Rationale"],
        [
            ["General (events, news, corpus)", "0.85", "Titles can vary moderately across sources"],
            ["Strict (tools, courses)",        "0.90", "Tool names are more precise; avoid over-merging"],
        ],
        cws=[6*cm, 3*cm, 6.9*cm]
    ))
    e.append(sp(8))
    e.append(h2("Tier 3 — Semantic Vector Similarity (Most Sophisticated)"))
    e.append(p(
        "Two items can have very different titles but mean the same thing. For example:"
    ))
    e.append(box(
        '"A Pre-trained Transformer for Arabic Text"  vs  '
        '"AraBERT: Bidirectional Encoder Representations for Arabic Language"',
        LIGHT, SLATE
    ))
    e.append(p(
        "These titles are lexically very different — SequenceMatcher might score them 0.30. "
        "But <b>semantically</b> they describe the same thing. Tier 3 catches this using "
        "<b>vector embeddings</b> and <b>cosine similarity</b>."
    ))
    e.append(h3("What Is a Vector Embedding?"))
    e.append(concept(
        "<b>A vector embedding is a list of numbers (a vector) that represents the meaning of text.</b> "
        "The model 'paraphrase-multilingual-MiniLM-L12-v2' converts any sentence into a list of "
        "384 numbers. Sentences with similar meanings produce similar vectors, regardless of the "
        "exact words used. This model supports 50+ languages including Arabic."
    ))
    e.append(sp(6))
    e.append(h3("What Is Cosine Similarity?"))
    e.append(concept(
        "<b>Cosine similarity measures the angle between two vectors.</b> If two vectors point in "
        "almost the same direction (small angle), the cosine similarity is close to 1.0 — meaning "
        "the texts are semantically similar. If they point in completely different directions, "
        "it is close to 0.0. The system uses a threshold of 0.88 — anything above is a duplicate."
    ))
    e.append(sp(6))
    e.append(h3("Where Are Vectors Stored? — pgvector"))
    e.append(p(
        "These 384-dimensional vectors need a database that can search through millions of them "
        "efficiently. The system uses <b>pgvector</b> — an extension for PostgreSQL (the database) "
        "that adds vector storage and fast similarity search. When a new item arrives, its vector "
        "is computed and compared against all stored vectors in one database query."
    ))
    e.append(sp(6))
    e.append(tbl(
        ["Tier", "Method", "Speed", "Threshold", "What It Catches"],
        [
            ["1", "Exact URL / ID match", "Instant", "Exact",    "Same page scraped twice"],
            ["2", "SequenceMatcher ratio", "Fast",   "0.85-0.90","Same resource, slightly different title"],
            ["3", "Cosine similarity (pgvector)", "Slower", "0.88","Same meaning, completely different words"],
        ],
        cws=[1*cm, 4.2*cm, 1.8*cm, 2.5*cm, 6.4*cm]
    ))
    e.append(PageBreak())
    return e

def ch5():
    e = ch_header("5", "How the System Scores Quality", "Confidence Scoring — The ConfidenceCalculator")
    e.append(p(
        "Not every item extracted by the AI is equally complete or useful. Some pages have "
        "detailed descriptions, exact dates, and all fields filled. Others might only have a title "
        "and a broken URL. The <b>ConfidenceCalculator</b> automatically assigns a score from "
        "<b>0 to 100</b> to every extracted item."
    ))
    e.append(h2("Why Do We Need a Score?"))
    e.append(p(
        "The score serves as an automatic quality gate. Items scoring below 30 are rejected "
        "immediately. Items between 30 and 55 are saved but flagged for human review. Items "
        "above 55 are considered ready for public display on the platform."
    ))
    e.append(h2("How Is the Score Calculated?"))
    e.append(p(
        "The score is a <b>weighted average</b> across all fields. Each category defines which "
        "fields are important and how much weight they carry. The weights for all fields sum to 1.0."
    ))
    e.append(concept(
        "<b>Weighted average example:</b> If a news article has title_en (weight 0.30), "
        "description_en (weight 0.30), URL (weight 0.15), source_url (weight 0.10), and "
        "published_date (weight 0.15) — and the title is present (score 1.0) but the date "
        "is missing (score 0.0), the formula is:\n\n"
        "Score = (1.0x0.30 + 1.0x0.30 + 1.0x0.15 + 1.0x0.10 + 0.0x0.15) / 1.0 = 0.85\n"
        "Scaled to 100: 85 points"
    ))
    e.append(sp(6))
    e.append(h2("Field-Level Scoring Rules"))
    e.append(p("Each individual field gets its own sub-score based on what type of value it contains:"))
    e.append(tbl(
        ["Field Type", "Rule", "Score Given"],
        [
            ["Empty / null",        "Field has no value at all",                   "0.0"],
            ["Short text (< 10 chars)", "Value present but very short",            "0.5"],
            ["Substantial text (>=20 chars)", "Good text content",                 "1.0"],
            ["Valid URL (https://...)", "Proper web address",                      "1.0"],
            ["Invalid URL (missing http)", "Bad format",                           "0.5"],
            ["Valid date (parseable)", "Recognizable date format",                 "1.0"],
            ["List field (>=3 items)", "Rich list (tags, capabilities)",           "1.0"],
            ["List field (1-2 items)", "Short list",          "0.33 or 0.67"],
            ["Boolean (True)",        "Flag is set",                               "1.0"],
            ["Placeholder text",      "Contains 'N/A', '[needs research]', 'TBD'", "0.0"],
        ],
        cws=[4*cm, 5.5*cm, 2.5*cm]
    ))
    e.append(sp(8))
    e.append(h2("Coverage Bonus"))
    e.append(p(
        "After computing the weighted average, a <b>coverage bonus of up to +15 points</b> "
        "is added based on how many optional fields are filled. An item that fills every "
        "single field gets the maximum bonus; an item with only mandatory fields gets no bonus."
    ))
    e.append(h2("Translation Cap"))
    e.append(p(
        "Because this is a <b>bilingual platform</b> (Arabic + English), items without confirmed "
        "Arabic translations are capped at a maximum score of 85. This incentivizes complete "
        "bilingual content. Items with Arabic translations can reach 100."
    ))
    e.append(sp(6))
    e.append(tbl(
        ["Score Range", "Interpretation", "Platform Action"],
        [
            ["90-100", "Excellent — all fields, bilingual",          "Published immediately"],
            ["80-89",  "Good — minor optional fields missing",        "Published immediately"],
            ["70-79",  "Adequate — title, desc, URL present",         "Published with note"],
            ["55-69",  "Fair — some key fields missing",              "Published, flagged"],
            ["30-54",  "Poor — minimal content",                      "Saved, needs review"],
            ["0-29",   "Rejected — insufficient data",                "Discarded"],
        ],
        cws=[2.5*cm, 5.5*cm, 7.9*cm]
    ))
    e.append(PageBreak())
    return e

def ch6():
    e = ch_header("6", "How Pages Are Filtered Before Processing", "Pre-Flight Validation Framework")
    e.append(p(
        "Calling an AI model to read a web page costs money and takes time. Many pages found by "
        "the search engine are useless — error pages, login walls, e-commerce sites, or pages "
        "in the wrong language. The validation framework is a <b>cheap pre-screening system</b> "
        "that eliminates bad pages <i>before</i> spending money on AI."
    ))
    e.append(info("Result: 84% of useless pages are rejected by the validators, meaning only "
                  "16% of discovered pages actually require an LLM call. This reduces costs by 84%."))
    e.append(sp(8))
    e.append(h2("Layer 1 — Network Validator"))
    e.append(p("The Network Validator performs 5 technical probes on each URL, in order:"))
    e.append(tbl(
        ["Probe", "What It Does", "Timeout", "Why It Matters"],
        [
            ["1. DNS Resolution",  "Checks the domain name exists in the internet's address book", "5s",  "Catches typos and dead domains"],
            ["2. TCP Connect",     "Tries to open a network connection to the server",             "5s",  "Confirms server is online"],
            ["3. HTTP HEAD",       "Asks the server for page metadata without downloading content","10s", "Checks the page returns 200 OK"],
            ["4. HTTP GET",        "Downloads the full page if HEAD failed",                       "15s", "Fallback for servers that block HEAD"],
            ["5. Robots.txt",      "Checks if the website allows bots to access the page",        "5s",  "Respects web scraping etiquette"],
        ],
        cws=[2.5*cm, 5*cm, 1.8*cm, 6.6*cm]
    ))
    e.append(sp(8))
    e.append(p("Based on the results, the page is classified as:"))
    e.append(bul("<b>GREEN</b> — All checks pass. Proceed to content validation."))
    e.append(bul("<b>YELLOW</b> — Minor issues (e.g., robots.txt not found). Proceed with caution."))
    e.append(bul("<b>RED</b> — Critical failure (DNS error, 404, 403, timeout). Reject immediately."))
    e.append(sp(8))
    e.append(h2("Layer 2 — Content Validator"))
    e.append(p(
        "For pages that pass the network check, the Content Validator reads the HTML and decides "
        "if it is actually about Arabic NLP. It uses <b>keyword density analysis</b>:"
    ))
    e.append(concept(
        "<b>Keyword density analysis:</b> The validator has a dictionary of NLP-related keywords "
        "(e.g., 'natural language processing', 'transformer', 'Arabic', 'dataset', 'BERT'). "
        "Each keyword has a weight. The validator counts how many keywords appear in the page text, "
        "multiplies by their weights, and divides by the maximum possible score. "
        "If the result is below 0.15 (15%), the page is classified as IRRELEVANT and skipped."
    ))
    e.append(sp(6))
    e.append(p("Examples of pages that get rejected here:"))
    e.append(bul("An Amazon product page that happened to mention 'language' in a review"))
    e.append(bul("A cooking blog with a recipe that mentions 'Arabic spices'"))
    e.append(bul("A generic Wikipedia article about the Arabic alphabet (no NLP content)"))
    e.append(sp(8))
    e.append(h2("Layer 3 — Extraction Quality Validator"))
    e.append(p(
        "After the AI extracts data, a final quality check ensures the output makes sense:"
    ))
    e.append(tbl(
        ["Check", "Criterion", "Action if Failed"],
        [
            ["Title length",       "Title must be at least 5 characters",                   "Reject item"],
            ["Description length", "Description must be at least 20 characters",             "Reject item"],
            ["Boilerplate check",  "Title cannot contain 'cookie', 'login', 'navigation'",  "Reject item"],
            ["URL validity",       "Extracted URLs must start with http:// or https://",     "Log warning"],
            ["Date validity",      "Dates must be parseable to ISO 8601 format",             "Log warning"],
        ],
        cws=[3.5*cm, 5.5*cm, 4.9*cm]
    ))
    e.append(PageBreak())
    return e

def ch7():
    e = ch_header("7", "How the System Handles Failures", "Resilience Engineering & Circuit Breakers")
    e.append(p(
        "In a distributed system that calls external APIs (Tavily, Gemini, Groq) and scrapes "
        "hundreds of websites, failures are <i>normal</i> — not exceptional. A robust system "
        "must handle failures gracefully without crashing or wasting resources. "
        "This module implements <b>three levels of resilience</b>."
    ))
    e.append(h2("Level 1 — The Circuit Breaker Pattern"))
    e.append(concept(
        "<b>The circuit breaker pattern is borrowed from electrical engineering.</b> In your home, "
        "when too much current flows through a wire (a failure), the circuit breaker 'trips' and "
        "cuts the power to prevent a fire. When the problem is fixed, you reset it and power flows again. "
        "In software, a circuit breaker stops sending requests to a failing service, "
        "waits for it to recover, then cautiously resumes."
    ))
    e.append(sp(8))
    e.append(p("The circuit breaker has 3 states:"))
    e.append(tbl(
        ["State", "What Happens", "When It Applies"],
        [
            ["CLOSED (normal)", "All requests go through to the source",           "Source is healthy"],
            ["OPEN (blocked)",  "All requests are immediately rejected. No network calls made.", "After 5+ failures"],
            ["HALF-OPEN (testing)", "One probe request is allowed through to test recovery", "After 300s cooldown"],
        ],
        cws=[3.5*cm, 5.5*cm, 6.9*cm]
    ))
    e.append(sp(8))
    e.append(highlight(
        "Why is OPEN state important? If a website is down, sending 1000 requests to it wastes time, "
        "API credits, and network bandwidth. The circuit breaker stops immediately — saving all those resources "
        "for healthy sources that can actually return useful data."
    ))
    e.append(sp(8))
    e.append(h2("Level 2 — Health Score Decay"))
    e.append(p(
        "Each scraping source (website or API) has a <b>health score from 0 to 100</b>. "
        "When it fails, the score decreases exponentially — meaning repeated failures cause "
        "increasingly severe damage to the score. When it succeeds, the score slowly recovers (+5 per success)."
    ))
    e.append(tbl(
        ["Consecutive Failures", "Health Points Lost", "Cumulative Loss", "Health Remaining"],
        [
            ["1st failure",  "-5 points",   "-5",    "95"],
            ["2nd failure",  "-10 points",  "-15",   "85"],
            ["3rd failure",  "-20 points",  "-35",   "65"],
            ["4th failure",  "-40 points",  "-75",   "25"],
            ["5th failure",  "-50 points",  "-100",  "0 — QUARANTINE"],
        ],
        cws=[4*cm, 3.5*cm, 3.5*cm, 5*cm]
    ))
    e.append(sp(8))
    e.append(p(
        "The exponential decay is intentional: occasional failures (bad internet days) are tolerated, "
        "but consistently unreliable sources are quarantined for 24 hours automatically."
    ))
    e.append(h2("Level 3 — Dead Letter Queue"))
    e.append(p(
        "When an item fails at any stage of the pipeline (network error, AI crash, database problem), "
        "it is not simply lost. It is saved to a <b>Dead Letter Queue</b> — a folder of JSON files "
        "organized by category. Each file records:"
    ))
    e.append(bul("The item's data at the point of failure"))
    e.append(bul("Which stage it failed at (discovery, extraction, validation, saving)"))
    e.append(bul("The exact error message and timestamp"))
    e.append(sp(4))
    e.append(p(
        "Administrators can manually review these files and replay them when the issue is fixed. "
        "No data is ever permanently lost due to a temporary failure."
    ))
    e.append(h2("Retry Policies"))
    e.append(tbl(
        ["Level", "Mechanism", "Max Retries", "Delay"],
        [
            ["Celery Task",     "Task-level automatic retry",           "2",         "60 seconds"],
            ["LLM API Call",    "Client-level retry with next key",     "2",         "0.3 seconds"],
            ["API Key Rotation","Round-robin across all keys",          "N (pool)",  "Immediate"],
            ["Gemini 429",      "Per-key cooldown cache in Redis",      "1",         "65 seconds"],
        ],
        cws=[3.5*cm, 5*cm, 3*cm, 4.4*cm]
    ))
    e.append(PageBreak())
    return e

def ch8():
    e = ch_header("8", "How Everything Runs in the Background", "Celery Task Orchestration")
    e.append(p(
        "Scraping hundreds of websites takes time — sometimes minutes or hours for a full run. "
        "If scraping happened inside the web server (synchronously), every user request would "
        "have to wait until it finished. The solution is <b>asynchronous task processing</b> "
        "using <b>Celery</b>."
    ))
    e.append(h2("What Is Celery?"))
    e.append(concept(
        "<b>Celery is a distributed task queue for Python.</b> Instead of running a function "
        "immediately when called, Celery places the task in a queue (like a to-do list). "
        "Separate 'worker' processes pick tasks from the queue and execute them independently. "
        "The web server stays responsive while workers do the heavy lifting in the background."
    ))
    e.append(sp(6))
    e.append(h2("What Is Redis?"))
    e.append(concept(
        "<b>Redis is an ultra-fast in-memory database used as Celery's message broker.</b> "
        "When a scraping task is scheduled, it is written to Redis. Workers watch Redis and pick "
        "up tasks as soon as they appear. Redis is also used for: circuit breaker state storage, "
        "rate limit counters, API key cooldowns, and caching."
    ))
    e.append(sp(6))
    e.append(h2("The Task Lifecycle"))
    e.append(p("Each scraping task goes through these states:"))
    states_data = [
        ("PENDING", "Task has been queued but not yet picked up by a worker", LAMBER, AMBER),
        ("RUNNING", "Worker is actively executing the scraping pipeline",     LBLUE,  BLUE),
        ("COMPLETED", "Pipeline finished successfully — results saved",       LGREEN, GREEN),
        ("FAILED",  "An unrecoverable error occurred — dead letter saved",   LRED,   RED),
        ("CANCELLED","Task was manually stopped by an administrator",         LIGHT,  SLATE),
    ]
    for state, desc, bg, fg in states_data:
        e.append(box(f"<b>{state}</b>  —  {desc}", bg, fg))
        e.append(sp(3))
    e.append(sp(8))
    e.append(h2("What Gets Recorded"))
    e.append(p(
        "Every scraping run creates a <b>ScrapingRun</b> record in the database with full "
        "audit trail information:"
    ))
    e.append(tbl(
        ["Field", "Example Value", "Purpose"],
        [
            ["task_id",        "f4a2b8c1-...",    "Unique identifier to track this specific run"],
            ["category",       "events",          "Which of the 6 types was scraped"],
            ["status",         "completed",        "Current state of the task"],
            ["items_created",  "23",               "New resources added to the database"],
            ["items_updated",  "5",                "Existing resources refreshed with new data"],
            ["items_skipped",  "47",               "Duplicates or irrelevant pages rejected"],
            ["duration",       "142 seconds",      "How long the full pipeline took"],
        ],
        cws=[3*cm, 3.5*cm, 9.4*cm]
    ))
    e.append(sp(8))
    e.append(h2("Scheduled Automatic Scraping"))
    e.append(p(
        "Using <b>Celery Beat</b> (Celery's scheduler), the system automatically runs scraping "
        "tasks on a schedule without any human trigger:"
    ))
    e.append(bul("<b>Full platform refresh</b> — runs daily or weekly for all 6 categories"))
    e.append(bul("<b>Source health checks</b> — runs every 6 hours to monitor website availability"))
    e.append(bul("<b>Stale run cleanup</b> — daily cleanup of orphaned task records"))
    e.append(PageBreak())
    return e

def ch9():
    e = ch_header("9", "How the System Is Monitored in Real-Time", "WebSockets & Prometheus Metrics")
    e.append(h2("Real-Time Progress with WebSockets"))
    e.append(p(
        "When an administrator starts a scraping task from the dashboard, they see a live "
        "progress bar updating in real-time. This is powered by <b>WebSockets</b> — a technology "
        "that keeps a persistent connection open between the browser and the server, allowing "
        "the server to push updates instantly."
    ))
    e.append(concept(
        "<b>WebSockets vs. regular HTTP:</b> Normal web pages work like letters — you send a "
        "request, wait for a response, and the connection closes. WebSockets work like a phone "
        "call — once connected, both sides can send messages at any time. This is how chat apps, "
        "live sports scores, and trading platforms work. The system uses <b>Django Channels</b> "
        "to add WebSocket support to the Django web framework."
    ))
    e.append(sp(6))
    e.append(p("The progress messages sent over WebSocket include:"))
    e.append(tbl(
        ["Stage", "Progress Range", "What Is Reported"],
        [
            ["discovery",   "0% to 20%",  "How many URLs Tavily returned"],
            ["extracting",  "20% to 70%", "Which item is currently being processed by the AI"],
            ["validating",  "70% to 85%", "Quality checks on each extracted item"],
            ["persisting",  "85% to 95%", "Database saves and deduplication results"],
            ["completed",   "100%",       "Final counts: created, updated, skipped"],
        ],
        cws=[2.5*cm, 3*cm, 10.4*cm]
    ))
    e.append(sp(8))
    e.append(h2("Prometheus Metrics — System Health Dashboard"))
    e.append(p(
        "<b>Prometheus</b> is an open-source monitoring system used by major tech companies "
        "(Google, Netflix, Uber). The system exposes metrics at a /metrics endpoint that "
        "Prometheus scrapes every few seconds and stores in a time-series database. "
        "These can be visualized in a Grafana dashboard."
    ))
    e.append(p("The 8 key metrics tracked:"))
    e.append(tbl(
        ["Metric", "Type", "What It Measures"],
        [
            ["scraping_run_duration_seconds",   "Histogram", "How long each scrape takes (by category and outcome)"],
            ["scraping_items_total",            "Counter",   "Items created, updated, skipped, or failed"],
            ["scraping_source_health",          "Gauge",     "Current health score (0-100) of each source"],
            ["scraping_queue_lag_seconds",      "Gauge",     "Time since the last successful scrape per category"],
            ["scraping_circuit_breaker_state",  "Gauge",     "0=closed (healthy), 1=open (blocked), 2=half-open"],
            ["scraping_api_calls_total",        "Counter",   "LLM API calls by provider and HTTP status code"],
            ["scraping_dedup_matches_total",    "Counter",   "Duplicate detections by tier (URL/fuzzy/semantic)"],
            ["scraping_active_runs",            "Gauge",     "Number of scraping tasks currently running"],
        ],
        cws=[5*cm, 2.2*cm, 8.7*cm]
    ))
    e.append(sp(8))
    e.append(highlight(
        "Alert rules are configured for critical conditions: if the queue has not been refreshed "
        "in 24 hours, if a source health score drops below 20, or if a circuit breaker is open — "
        "the system generates automatic alerts to administrators."
    ))
    e.append(PageBreak())
    return e

def ch10():
    e = ch_header("10", "The Tech Stack — Every Framework Explained", "Technologies used and why each was chosen")
    e.append(p(
        "This chapter explains every technology in the stack — what it is, what it does in this "
        "project, and why it was chosen over alternatives."
    ))

    techs = [
        ("Django (Web Framework)", LBLUE, BLUE,
         "Django is a high-level Python web framework that handles routing, database models, "
         "authentication, and the admin interface. In this project, Django provides: the ORM "
         "(Object-Relational Mapper) that translates Python code into database queries; the Admin "
         "interface where administrators can trigger scrapes and review data; URL routing for the "
         "API endpoints; and the model definitions for all 15+ database tables. "
         "<b>Why Django?</b> It comes with a powerful admin interface out of the box, PostgreSQL "
         "support, and excellent ecosystem compatibility with Celery and Channels."),

        ("PostgreSQL (Database)", LTEAL, TEAL,
         "PostgreSQL is a powerful open-source relational database. It stores all scraped resources, "
         "scraping run histories, source configurations, and health scores. "
         "<b>Why PostgreSQL?</b> Unlike MySQL or SQLite, PostgreSQL supports the pgvector extension "
         "for vector similarity search — which is essential for Tier 3 semantic deduplication. "
         "It also has excellent full-text search, JSON storage, and transaction integrity."),

        ("pgvector (Vector Extension)", LPURPLE, PURPLE,
         "pgvector is a PostgreSQL extension that adds a new data type: 'vector'. It stores "
         "384-dimensional float arrays (the sentence embeddings) and provides operators for "
         "cosine distance, L2 distance, and inner product — enabling fast nearest-neighbor search "
         "directly inside the database. <b>Why pgvector?</b> It avoids the need for a separate "
         "vector database (like Pinecone or Weaviate), keeping the architecture simpler."),

        ("Redis (Cache & Message Broker)", LAMBER, AMBER,
         "Redis is an in-memory key-value store that operates at microsecond speeds. "
         "In this system it serves four roles: (1) Celery message broker — tasks are written "
         "and read from Redis queues; (2) Circuit breaker state — shared across all workers; "
         "(3) Rate limit counters — Gemini RPM/RPD tracking; (4) API key cooldown timers. "
         "<b>Why Redis?</b> Its speed (100,000+ operations/second) and TTL (time-to-live) "
         "feature make it ideal for temporary state that should auto-expire."),

        ("Celery (Task Queue)", LGREEN, GREEN,
         "Celery is a distributed task processing library for Python. It allows functions to "
         "be executed asynchronously in the background by separate worker processes. "
         "The scraping pipeline is defined as Celery tasks with retry policies, timeouts, "
         "and state tracking. <b>Why Celery?</b> It integrates natively with Django and Redis, "
         "supports distributed execution across multiple machines, and provides retry/failure handling."),

        ("Tavily (Search API)", LBLUE, BLUE,
         "Tavily is an AI-powered search API designed specifically for machine consumption "
         "(as opposed to human-readable Google results). It returns clean page content, "
         "supports advanced crawl depth, and provides structured metadata. "
         "<b>Why Tavily?</b> General web search APIs (Google, Bing) require complex parsing "
         "and have stricter terms of service for scraping. Tavily is explicitly designed for "
         "AI-powered discovery pipelines."),

        ("BeautifulSoup 4 (HTML Parsing)", LTEAL, TEAL,
         "BeautifulSoup is a Python library that parses HTML and XML documents. Given a raw "
         "HTML page, it creates a parse tree that allows surgical navigation: finding specific "
         "tags, extracting text, removing unwanted elements. The scraper uses it to clean pages "
         "before sending them to the LLM — removing scripts, navbars, footers, and ads. "
         "<b>Why BeautifulSoup?</b> It is the industry standard for HTML parsing in Python, "
         "handles malformed HTML gracefully, and has zero external dependencies."),

        ("SentenceTransformers (Embeddings)", LPURPLE, PURPLE,
         "SentenceTransformers is a Python library built on top of HuggingFace Transformers "
         "that provides pre-trained models for generating sentence embeddings. The model "
         "'paraphrase-multilingual-MiniLM-L12-v2' converts any text (in any of 50+ languages) "
         "into a 384-dimensional vector. <b>Why this model?</b> The 'multilingual' variant "
         "supports Arabic natively, 'MiniLM' means it is small enough to run without a GPU, "
         "and 'paraphrase' means it is trained to produce similar vectors for sentences with "
         "the same meaning but different words."),

        ("Django Channels (WebSockets)", LGREEN, GREEN,
         "Django Channels extends Django with support for WebSocket connections, long-polling, "
         "and other asynchronous protocols. The ScrapingProgressConsumer uses it to maintain "
         "persistent browser-server connections for live progress streaming. "
         "<b>Why Channels?</b> It integrates directly with Django's authentication and session "
         "system, and uses Redis as the channel layer backend for cross-worker message routing."),

        ("Prometheus Client (Monitoring)", LAMBER, AMBER,
         "The prometheus_client Python library exposes application metrics at a /metrics endpoint "
         "in Prometheus exposition format. Counters, gauges, and histograms are defined in "
         "metrics.py and updated throughout the pipeline. Prometheus scrapes this endpoint every "
         "15 seconds. <b>Why Prometheus?</b> It is the de-facto standard for cloud-native "
         "monitoring, integrates with Grafana for visualization, and supports powerful alerting rules."),
    ]

    for title, bg, fg, desc in techs:
        e.append(KeepTogether([
            box(f"<b>{title}</b><br/>{desc}", bg, fg),
            sp(6),
        ]))

    e.append(PageBreak())
    return e

def ch11():
    e = ch_header("11", "Why This Is Better Than Other Scrapers", "Competitive Advantages")
    e.append(p(
        "Traditional web scrapers are brittle tools that break every time a website changes its "
        "HTML structure. This system takes a fundamentally different approach. Here is a "
        "direct comparison:"
    ))
    e.append(tbl(
        ["Feature", "Traditional Scraper", "This System"],
        [
            ["Page parsing",        "CSS selectors / XPath rules that break on redesign", "LLM reads content semantically — no rules needed"],
            ["New website support", "Requires hours of manual selector engineering",      "Zero-shot: give it any URL, it extracts correctly"],
            ["Duplicate detection", "Simple URL comparison only",                         "3-tier cascade: URL + fuzzy title + semantic vectors"],
            ["Quality control",     "No quality assessment",                              "Confidence score 0-100, automatic rejection threshold"],
            ["Failure handling",    "Crash and stop",                                     "Circuit breakers, dead letters, exponential retries"],
            ["Multilingual",        "English only or requires separate pipeline",          "Extracts and translates Arabic/English simultaneously"],
            ["Monitoring",          "Log files only",                                     "Prometheus metrics, real-time WebSocket progress"],
            ["Scalability",         "Single process, blocking",                           "Celery workers, horizontally scalable across machines"],
            ["Cost control",        "No rate limiting awareness",                         "Per-key quotas, RPM/RPD tracking, proactive cooldowns"],
        ],
        cws=[3.5*cm, 5.5*cm, 6.9*cm]
    ))
    e.append(sp(10))
    e.append(h2("The Key Differentiator — Zero-Shot Extraction"))
    e.append(p(
        "The most important advantage is that this system requires <b>zero configuration per website</b>. "
        "A traditional scraper for Coursera would look like: "
        "<i>find h1 with class 'course-title', find div with class 'course-description'...</i>. "
        "When Coursera updates its HTML, the scraper breaks. Our system simply says to the AI: "
        "<i>\"This is a Coursera page. Extract the course title, description, provider, and price.\"</i> "
        "The AI understands the page regardless of HTML structure."
    ))
    e.append(sp(6))
    e.append(tip(
        "This means the system can scrape any new website, in any language, in any format, "
        "without a single line of new code. Add a new URL to the sources — the AI handles the rest."
    ))
    e.append(sp(8))
    e.append(h2("Domain Specialization"))
    e.append(p(
        "Unlike generic scrapers, this system is deeply specialized for Arabic NLP. The LLM prompts "
        "are engineered to understand domain-specific concepts: what makes an event a 'call for papers', "
        "how to identify an arXiv ID, how to distinguish a corpus license from a tool license. "
        "The keyword validation dictionaries are tailored to NLP terminology. The confidence weights "
        "are tuned for each category's specific requirements."
    ))
    e.append(PageBreak())
    return e

def ch12():
    e = ch_header("12", "The Code Architecture — File by File", "Module structure and what each file does")
    e.append(tbl(
        ["File / Folder", "Size", "What It Does"],
        [
            ["models.py",                  "~921 lines",  "Defines all database tables: ScrapingSource, ScrapingRun, ScrapingSourceHealth, ScrapedItemMeta, DeadLetterItem"],
            ["scrapers/base.py",           "~1,546 lines","The parent class all scrapers inherit from. Handles dedup dispatch, progress reporting, confidence scoring, and terminal status protection"],
            ["scrapers/events.py",         "~2,486 lines","EventScraper — the most complex. Adds CSS-based direct crawling, URL prioritization, and date range validation"],
            ["scrapers/tools.py",          "~368 lines",  "ToolScraper — GitHub URL extraction, license detection, capability parsing"],
            ["scrapers/news.py",           "~446 lines",  "NewsScraper — DOI/arXiv ID extraction, language detection, confidence delta logic"],
            ["scrapers/corpus.py",         "~509 lines",  "CorpusScraper — download URL validation, language variant parsing, size normalization"],
            ["scrapers/circuit_breaker.py","~110 lines",  "RedisCircuitBreaker — three-state machine backed by Redis TTL keys"],
            ["network/search_client.py",   "~352 lines",  "TavilySearchClient — multi-key rotation, category search methods, query dedup"],
            ["extractors/core/llm_validation.py","~1,083 lines","GroqLLMClient + LLMValidator — dual provider, key rotation, rate limiting, JSON parsing"],
            ["intelligence.py",            "~321 lines",  "ConfidenceCalculator — weighted field matrix, exponential text scoring, translation cap"],
            ["tasks.py",                   "~1,832 lines","All Celery task definitions — run_scraper_task, health checks, cleanup"],
            ["direct_scrape.py",           "~1,036 lines","On-demand single URL scraping pipeline with 7 stages"],
            ["validators/network_validator.py","~250 lines","5-probe network validation (DNS, TCP, HTTP, robots.txt)"],
            ["validators/content_validator.py","~232 lines","Keyword density NLP relevance scoring"],
            ["field_mapping.py",           "~1,027 lines","Maps LLM output fields to Django model fields for each category"],
            ["embeddings.py",              "~120 lines",  "SentenceTransformer singleton, pgvector cosine search"],
            ["metrics.py",                 "~250 lines",  "Prometheus metric definitions and update helpers"],
            ["consumers.py",               "~102 lines",  "Django Channels WebSocket consumer for live progress"],
            ["dead_letter.py",             "~119 lines",  "Failed item persistence to JSON files, organized by category"],
            ["constants.py",               "~456 lines",  "Single source of truth for all 456+ configuration constants"],
        ],
        cws=[5*cm, 2.2*cm, 8.7*cm]
    ))
    e.append(sp(8))
    e.append(h2("Class Hierarchy"))
    e.append(box(
        "BaseScraper (scrapers/base.py)\n"
        "  EventScraper       (scrapers/events.py)        — events category\n"
        "  ToolScraper        (scrapers/tools.py)         — tools category\n"
        "  NewsScraper        (scrapers/news.py)          — news/papers category\n"
        "  CourseScraper      (scrapers/courses.py)       — courses category\n"
        "  CorpusScraper      (scrapers/corpus.py)        — datasets category\n"
        "  OpportunityScraper (scrapers/opportunities.py) — jobs/PhD category\n"
        "  CustomDomainScraper(scrapers/custom_scraper.py)— user-defined sources",
        LIGHT, SLATE
    ))
    e.append(PageBreak())
    return e

def ch13():
    e = ch_header("13", "Key Technical Concepts Glossary", "Terms your jury will expect you to know")
    terms = [
        ("API (Application Programming Interface)",
         "A standardized way for programs to communicate. Like a menu in a restaurant — you request "
         "specific items (functions) and get results back without seeing the kitchen (implementation)."),
        ("LLM (Large Language Model)",
         "An AI model trained on massive text datasets that can understand and generate human language. "
         "Examples: GPT-4, Gemini, Llama 3. In this system, used to read web pages and extract structured data."),
        ("Web Scraping",
         "Automated extraction of data from websites. The system downloads a page's HTML, parses it, "
         "and extracts specific information — like a robot reading the page for you."),
        ("REST API / HTTP",
         "HTTP (HyperText Transfer Protocol) is how web browsers and servers communicate. "
         "Status codes: 200=OK, 404=Not Found, 429=Too Many Requests, 503=Service Unavailable."),
        ("JSON (JavaScript Object Notation)",
         "A text format for structured data using key-value pairs. The LLM responds in JSON "
         "so the system can automatically parse titles, dates, URLs, etc. into database fields."),
        ("ORM (Object-Relational Mapper)",
         "A programming technique that maps Python classes (objects) to database tables. "
         "Django's ORM lets you write Python code instead of SQL to query the database."),
        ("Asynchronous Processing",
         "Running tasks in the background without blocking the main program. Like ordering food "
         "and going about your day — the kitchen works independently, delivers when ready."),
        ("Vector Embedding",
         "A mathematical representation of text as a list of numbers (vector). Similar meanings "
         "produce similar vectors. The system uses 384-dimensional vectors for semantic deduplication."),
        ("Cosine Similarity",
         "A mathematical measure (0.0 to 1.0) of how similar two vectors are. "
         "1.0 = identical direction (same meaning). Used to find semantically duplicate content."),
        ("Circuit Breaker Pattern",
         "A software design pattern that stops sending requests to a failing service, "
         "waits for recovery, then cautiously resumes. Prevents cascading failures."),
        ("Rate Limiting",
         "APIs restrict how many requests you can make per minute/day. The system tracks these "
         "limits per key and proactively waits or switches keys to avoid being blocked."),
        ("Celery / Task Queue",
         "A system for running Python functions asynchronously in background worker processes. "
         "Tasks are queued in Redis and picked up by workers independently of the web server."),
        ("Redis",
         "An in-memory key-value database that operates at microsecond speed. "
         "Used as Celery's message broker, circuit breaker state store, and rate limit counter."),
        ("PostgreSQL / pgvector",
         "PostgreSQL is a powerful open-source relational database. pgvector is an extension "
         "that adds vector storage and similarity search, enabling semantic deduplication."),
        ("WebSocket",
         "A protocol for persistent, bidirectional browser-server communication. Unlike HTTP "
         "where you request and wait, WebSockets keep a live connection open for streaming updates."),
        ("Prometheus / Metrics",
         "Prometheus is a monitoring system that collects time-series metrics. Counters track "
         "cumulative values (items scraped), gauges track current values (health scores), "
         "and histograms track distributions (request durations)."),
        ("Jaccard Similarity / SequenceMatcher",
         "SequenceMatcher computes how similar two strings are character by character, "
         "returning a score from 0.0 to 1.0. Used in Tier 2 deduplication for title comparison."),
        ("Dead Letter Queue",
         "A storage location for messages or items that failed processing. Allows administrators "
         "to review failures and replay them when issues are fixed — nothing is permanently lost."),
        ("Zero-Shot Learning",
         "Using an AI model to perform tasks it was not explicitly trained for, by providing "
         "instructions in the prompt. Our system uses zero-shot extraction — no training data "
         "needed for new websites, just a well-engineered prompt."),
        ("Confidence Score",
         "A numerical measure (0-100) of how complete and trustworthy an extracted item is. "
         "Calculated using a weighted average of field presence and quality, with category-specific weights."),
    ]
    for term, definition in terms:
        e.append(KeepTogether([
            box(f"<b>{term}</b><br/>{definition}", LIGHT, SLATE),
            sp(5),
        ]))
    e.append(sp(10))
    e.append(hr())
    e.append(Paragraph(
        f"Document generated: {datetime.date.today().strftime('%B %d, %Y')}  ·  "
        "Arabic NLP Platform — Web Scraping Module  ·  Version 2.0  ·  ~14,900 lines of code",
        ps("foot", fontSize=9, fontName="Helvetica", textColor=MUTED, alignment=TA_CENTER, spaceBefore=8)
    ))
    return e

# ─── assemble ────────────────────────────────────────────────────
def build(path):
    # Ensure directory exists
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=M, rightMargin=M,
        topMargin=M + 0.5*cm, bottomMargin=M,
        title="Arabic NLP Platform — Web Scraping Module Technical Guide",
        author="Arabic NLP Platform",
    )
    story = []
    story += cover()
    story += toc()
    story += ch1()
    story += ch2()
    story += ch3()
    story += ch4()
    story += ch5()
    story += ch6()
    story += ch7()
    story += ch8()
    story += ch9()
    story += ch10()
    story += ch11()
    story += ch12()
    story += ch13()

    doc.build(story, onFirstPage=first, onLaterPages=later)
    print(f"Done: {path}")

# Adjusted path for project structure
build("evaluation/reports/WebScraping_Technical_Guide.pdf")
