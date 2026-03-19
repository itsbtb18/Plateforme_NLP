# Research Card System - Architecture & Data Flow

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ADMIN REVIEW POST PAGE                       │
│                   (templates/admin/news_view.html)              │
└────────────────────────────┬──────────────────────────────────┘
                             │
                             ↓
                    ┌─────────────────┐
                    │  Flask/Django   │
                    │  View Function  │
                    │(admin_news_view)│
                    └────────┬────────┘
                             │
                    ┌────────▼─────────┐
                    │ Post.content     │
                    │ (Raw scraped     │
                    │  text with **    │
                    │  markdown)       │
                    └────────┬─────────┘
                             │
        ┌────────────────────▼─────────────────────┐
        │   Content Parser Module                  │
        │   (pages/content_parser.py)              │
        │                                          │
        │   extract_structured_content()           │
        │   - Regex pattern matching               │
        │   - URL extraction                       │
        │   - Field isolation                      │
        └────────┬─────────────────────────────────┘
                 │
        ┌────────▼────────────────────┐
        │   Structured Data Dict      │
        │  {                          │
        │    title: "...",           │
        │    authors: "...",         │
        │    year: "2024",           │
        │    abstract: "...",        │
        │    link: "https://...",    │
        │  }                          │
        └────────┬───────────────────┘
                 │
        ┌────────▼──────────────────────────────┐
        │   Django Template Renderer            │
        │   (templates/admin/news_view.html)    │
        │                                       │
        │   {% if parsed_content.title %}       │
        │   <h1>{{ parsed_content.title }}</h1> │
        │   ...                                 │
        └────────┬──────────────────────────────┘
                 │
        ┌────────▼────────────────────────────────┐
        │   CSS Styling (design tokens)           │
        │   (static/css/admin.css)                │
        │   - Colors: --n-blue, --n-text         │
        │   - Spacing, typography                │
        │   - RTL support                        │
        └────────┬────────────────────────────────┘
                 │
        ┌────────▼────────────────────┐
        │   Rendered HTML             │
        │   (Beautiful research card) │
        └────────────────────────────┘
                 │
                 ↓
        ┌────────────────────────────┐
        │   Browser (User) Sees:     │
        │   ┌──────────────────────┐ │
        │   │ 📄 Title             │ │
        │   │ 👤 Authors           │ │
        │   │ 📅 Year [badge]      │ │
        │   │ Abstract text...     │ │
        │   │ [View Source] link   │ │
        │   │ [Actions...]         │ │
        │   └──────────────────────┘ │
        └────────────────────────────┘
```

## Data Flow Sequence

```
Raw Content Input
    │
    ├─ "**Authors:** John Doe"
    ├─ "**Year:** 2024"
    ├─ "**Abstract:** Paper summary..."
    └─ "[Link](https://example.com)"
         │
         ▼
    ┌─────────────────────────────────┐
    │  Regex Pattern Matching         │
    │  ─────────────────────────────  │
    │  Pattern: \*\*Authors?:...\*\*  │
    │  Result: "John Doe"             │
    │                                 │
    │  Pattern: \*\*Year:\*\*(\d{4})  │
    │  Result: "2024"                 │
    │                                 │
    │  Pattern: \[text\](url)         │
    │  Result: "https://example.com"  │
    └─────────────────────────┬───────┘
            │
            ▼
    ┌─────────────────────────────────┐
    │  Structured Output              │
    │  ─────────────────────────────  │
    │ {                               │
    │   'title': None,                │
    │   'authors': 'John Doe',        │
    │   'year': '2024',               │
    │   'abstract': 'summary...',     │
    │   'link': 'https://example.com' │
    │ }                               │
    └─────────────┬───────────────────┘
            │
            ▼
    ┌──────────────────────────────────┐
    │  Template Rendering              │
    │  ──────────────────────────────  │
    │  {% if parsed_content.authors %} │
    │    <div class="authors">        │
    │      {{ parsed_content.authors }}│
    │    </div>                        │
    │  {% endif %}                     │
    └────────────┬────────────────────┘
            │
            ▼
    ┌──────────────────────────────────┐
    │  HTML Output                     │
    │  ──────────────────────────────  │
    │  <div class="authors">           │
    │    John Doe                      │
    │  </div>                          │
    └────────────┬────────────────────┘
            │
            ▼
    ┌──────────────────────────────────┐
    │  CSS Applied                     │
    │  ──────────────────────────────  │
    │  .research-authors {             │
    │    color: var(--n-text-2);      │
    │    font-size: 0.95rem;          │
    │  }                               │
    └────────────┬────────────────────┘
            │
            ▼
    ┌──────────────────────────────────┐
    │  User Sees Beautiful Card        │
    │  ──────────────────────────────  │
    │  👤 John Doe                     │
    │  📅 2024                          │
    │  Abstract text...                │
    │                                  │
    │  [View Paper] [More info]        │
    └──────────────────────────────────┘
```

## Parser Decision Tree

```
┌──────────────────────────────────────┐
│  Has Raw Content?                    │
└────────┬─────────────────────────────┘
         │
    ┌────┴────┐
    │    No   │ → Return empty dict
    │         │
    │    Yes  │
    │         │
    └────┬────┘
         │
         ▼
┌──────────────────────────────────────┐
│  Match Pattern: **Authors:**          │
└────────┬─────────────────────────────┘
         │
    ┌────┴────┐
    │  Found  │ → Extract and trim
    │    │    │
    │   No   │ → Set to None
    └────┬────┘
         │
         ▼
┌──────────────────────────────────────┐
│  Match Pattern: **Year:**             │
│  (must be 4-digit number)             │
└────────┬─────────────────────────────┘
         │
    ┌────┴────┐
    │  Found  │ → Extract year
    │    │    │
    │   No   │ → Set to None
    └────┬────┘
         │
         ▼
┌──────────────────────────────────────┐
│  Match Pattern: **Abstract:**         │
│  (Can be multiple lines)              │
└────────┬─────────────────────────────┘
         │
    ┌────┴────┐
    │  Found  │ → Extract and clean
    │    │    │
    │   No   │ → Set to None
    └────┬────┘
         │
         ▼
┌──────────────────────────────────────┐
│  Match URL Pattern:                  │
│  1. [text](url)                      │
│  2. https://... plain URL            │
└────────┬─────────────────────────────┘
         │
    ┌────┴────┐
    │  Found  │ → Extract URL
    │    │    │
    │   No   │ → Set to None
    └────────┘
         │
         ▼
┌──────────────────────────────────────┐
│  Return Structured Dict              │
└──────────────────────────────────────┘
```

## Template Conditional Logic

```
Template Rendering Algorithm:

1. Get parsed_content dict from view
   
2. IF parsed_content.title exists
   THEN display it as <h1> (large, bold)
   ELSE use post.get_localized_title() as fallback

3. IF parsed_content.authors exists
   THEN display with 👤 icon
   ELSE skip this section

4. IF parsed_content.year exists
   THEN display in blue badge with 📅 icon
   ELSE skip badge

5. IF parsed_content.abstract exists
   THEN display in highlighted box with border
   ELSE display full post.content as fallback

6. IF parsed_content.link exists
   THEN create clickable button
        - URL: sanitized and validated
        - Target: _blank (new tab)
        - Rel: noopener noreferrer (security)
   ELSE skip link section

7. Always display action buttons:
   - Edit Form
   - Refuse (with confirmation)
   - Approve & Publish (with confirmation)
```

## RTL (Arabic) Transformation

```
LTR (English) Mode:
┌─────────────────┐
│ Title           │
│ 👤 Authors      │ ← Icon on left
│ Abstract text   │
│ left border ▌   │ ← Border on left
│ [Button] Link   │ ← Button on left
└─────────────────┘


RTL (Arabic) Mode:
[CSS selector: [dir="rtl"]]
┌─────────────────┐
│           عنوان │  ← Aligned right
│   المؤلفون 👤   │  ← Icon on right
│            نص   │  ← Aligned right
│   ▐ نص مقتطف   │  ← Border on right
│   رابط [زر]     │  ← Button on right
└─────────────────┘

Transform Rules:
- flex-direction: row → row-reverse
- border-left → border-right
- text-align: left → right
- margin-left ↔ margin-right
- padding-left ↔ padding-right
- transform: translateX(right) → translateX(left)
```

## CSS-to-Visual Map

```
Design Token → CSS Variable → Visual Result

--n-text (dark gray) 
  ├─ .research-title
  ├─ .research-meta
  └─ Labels

--n-text-2 (lighter gray)
  ├─ .research-authors
  ├─ Abstract intro text
  └─ Dates

--n-blue (accent blue)
  ├─ .year-badge (text color)
  ├─ Button hover state
  └─ Abstract left border

--n-blue-soft (light blue)
  ├─ .year-badge (background)
  └─ Hover effects

--n-bg (light background)
  └─ .research-abstract (container bg)

--n-border-s (subtle border)
  ├─ Card dividing lines
  └─ Section separators
```

