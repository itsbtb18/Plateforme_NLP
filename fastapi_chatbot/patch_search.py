import re

file_path = '/home/dahmane/dev/Plateforme_NLP/fastapi_chatbot/app/services/platform_queries.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# The replacement logic we want to inject
replacement = '''        STOP_WORDS = {
            "show", "me", "find", "list", "give", "get", "the", "a", "an", "is", "are",
            "about", "for", "in", "on", "of", "to", "and", "or", "with", "what",
            "which", "how", "my", "all", "any", "search", "tool", "tools", "document",
            "documents", "course", "courses", "corpus", "corpora", "event", "events",
            "project", "projects", "institution", "institutions",
            "montrer", "trouver", "lister", "les", "des", "un", "une", "le", "la", "du", "de",
            "sur", "pour", "dans", "et", "ou",
            "عن", "في", "على", "من", "الى", "إلى", "و", "أو", "ابحث", "بحث", "أدوات", "أداة"
        }
        if keyword:
            words = [w for w in keyword.lower().split() if w not in STOP_WORDS and len(w) > 2]
            if words:
                sub_conds = []
                for i, word in enumerate(words[:5]):
                    sub_conds.append(
                        f"({cond_template.replace('{i}', str(i))})"
                    )
                    params[f"{param_prefix}{i}"] = f"%{{word}}%"
                conditions.append("(" + " OR ".join(sub_conds) + ")")'''

# We have different templates in different methods:
replacements = [
    (
        r'        if keyword:\n            words = keyword\.split\(\)\n            for i, word in enumerate\(words\):\n                conditions\.append\(\n                    f"\(title ILIKE :kw_course\{i\} OR title_ar ILIKE :kw_course\{i\} OR title_en ILIKE :kw_course\{i\} "\\n                    f"OR description ILIKE :kw_course\{i\}\)"\n                \)\n                params\[f"kw_course\{i\}"\] = f"%\{word\}%"',
        replacement.replace('cond_template', r'title ILIKE :kw_course{i} OR title_ar ILIKE :kw_course{i} OR title_en ILIKE :kw_course{i} OR description ILIKE :kw_course{i}').replace('param_prefix', 'kw_course')
    ),
    (
        r'        if keyword:\n            words = keyword\.split\(\)\n            for i, word in enumerate\(words\):\n                conditions\.append\(\n                    f"\(title ILIKE :kw\{i\} OR title_ar ILIKE :kw\{i\} OR title_en ILIKE :kw\{i\} "\\n                    f"OR description ILIKE :kw\{i\}\)"\n                \)\n                params\[f"kw\{i\}"\] = f"%\{word\}%"',
        replacement.replace('cond_template', r'title ILIKE :kw{i} OR title_ar ILIKE :kw{i} OR title_en ILIKE :kw{i} OR description ILIKE :kw{i}').replace('param_prefix', 'kw')
    ),
    (
        r'        if keyword:\n            words = keyword\.split\(\)\n            for i, word in enumerate\(words\):\n                conditions\.append\(\n                    f"\(title ILIKE :kw_tool\{i\} OR title_ar ILIKE :kw_tool\{i\} OR title_en ILIKE :kw_tool\{i\} "\\n                    f"OR description ILIKE :kw_tool\{i\}\)"\n                \)\n                params\[f"kw_tool\{i\}"\] = f"%\{word\}%"',
        replacement.replace('cond_template', r'title ILIKE :kw_tool{i} OR title_ar ILIKE :kw_tool{i} OR title_en ILIKE :kw_tool{i} OR description ILIKE :kw_tool{i}').replace('param_prefix', 'kw_tool')
    ),
    (
        r'        if keyword:\n            words = keyword\.split\(\)\n            for i, word in enumerate\(words\):\n                conditions\.append\(\n                    f"\(title ILIKE :kw_corp\{i\} OR title_ar ILIKE :kw_corp\{i\} OR title_en ILIKE :kw_corp\{i\} "\\n                    f"OR description ILIKE :kw_corp\{i\}\)"\n                \)\n                params\[f"kw_corp\{i\}"\] = f"%\{word\}%"',
        replacement.replace('cond_template', r'title ILIKE :kw_corp{i} OR title_ar ILIKE :kw_corp{i} OR title_en ILIKE :kw_corp{i} OR description ILIKE :kw_corp{i}').replace('param_prefix', 'kw_corp')
    ),
    (
        r'        if keyword:\n            words = keyword\.split\(\)\n            for i, word in enumerate\(words\):\n                conditions\.append\(\n                    f"\(title ILIKE :kw_event\{i\} OR title_ar ILIKE :kw_event\{i\} OR title_en ILIKE :kw_event\{i\} "\\n                    f"OR description ILIKE :kw_event\{i\} OR domains ILIKE :kw_event\{i\}\)"\n                \)\n                params\[f"kw_event\{i\}"\] = f"%\{word\}%"',
        replacement.replace('cond_template', r'title ILIKE :kw_event{i} OR title_ar ILIKE :kw_event{i} OR title_en ILIKE :kw_event{i} OR description ILIKE :kw_event{i} OR domains ILIKE :kw_event{i}').replace('param_prefix', 'kw_event')
    ),
    (
        r'        if keyword:\n            words = keyword\.split\(\)\n            for i, word in enumerate\(words\):\n                conditions\.append\(\n                    f"\(i\.name ILIKE :kw\{i\} OR i\.name_ar ILIKE :kw\{i\} OR i\.name_en ILIKE :kw\{i\} "\\n                    f"OR i\.description ILIKE :kw\{i\} OR i\.city ILIKE :kw\{i\}\)"\n                \)\n                params\[f"kw\{i\}"\] = f"%\{word\}%"',
        replacement.replace('cond_template', r'i.name ILIKE :kw{i} OR i.name_ar ILIKE :kw{i} OR i.name_en ILIKE :kw{i} OR i.description ILIKE :kw{i} OR i.city ILIKE :kw{i}').replace('param_prefix', 'kw')
    ),
    (
        r'        if keyword:\n            words = keyword\.split\(\)\n            for i, word in enumerate\(words\):\n                conditions\.append\(\n                    f"\(p\.title ILIKE :kw_proj\{i\} OR p\.title_ar ILIKE :kw_proj\{i\} OR p\.title_en ILIKE :kw_proj\{i\} "\\n                    f"OR p\.description ILIKE :kw_proj\{i\}\)"\n                \)\n                params\[f"kw_proj\{i\}"\] = f"%\{word\}%"',
        replacement.replace('cond_template', r'p.title ILIKE :kw_proj{i} OR p.title_ar ILIKE :kw_proj{i} OR p.title_en ILIKE :kw_proj{i} OR p.description ILIKE :kw_proj{i}').replace('param_prefix', 'kw_proj')
    ),
]

for pat, rep in replacements:
    content = re.sub(pat, rep, content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Replacement done.")
