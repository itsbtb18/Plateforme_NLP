#!/usr/bin/env python3
# Transform tool_detail.html design into project_detail.html

# Read the tool_detail template
with open(r"d:\Plateforme_NLP\Plateforme\templates\resources\tool_detail.html", 'r', encoding='utf-8') as f:
    content = f.read()

# Perform replacements
replacements = {
    '.tool-detail-page': '.project-detail-page',
    '.tool-hero': '.project-hero',
    '.tool-action-card': '.project-action-card',
    '.tool-action': '.project-action',
    'tool_action': 'project_action',
    '– NLP Tool': '– Research Project',
    '{% trans "NLP Tool"': '{% trans "Research Project"',
    '{% trans "NLP Tools"': '{% trans "Research Projects"',
    '{{ object.get_localized_title }}': '{{ project.get_localized_title }}',
    '{{ object.get_localized_description': '{{ project.get_localized_description',
    '{{ object.author': '{{ project.coordinator',
    '{{ object.version': '{{ project.get_status_display',
    '{{ object.supported_languages_count': '{{ team_members.count|add:"1"',
    '{% if object.uploaded_file %}': '{% if project.attachment %}',
    '{{ object.uploaded_file.url }}': '{{ project.attachment.url }}',
    '{{ object.documentation_link }}': '{{ project.documentation_link }}',
    '{{ object.access_link }}': '{{ project.access_link }}',
    '{{ object.keywords }}': '{% if project.keywords %}',
    '{{ object.get_keywords_list }}': '{{ project.keywords }}',
    '{{ object.views_count }}': '{{ project.views_count }}',
    '{{ object.last_updated': '{{ project.updated_at',
    '{{ object.get_language_display }}': '{{ project.get_language_display }}',
    'object.': 'project.',
    'resources:tool_list': 'projects:project_list',
    'resources:resource-update': 'projects:project_update',
    'resources:resource-delete': 'projects:project_delete',
    '{% if request.user == project.author %}': '{% if request.user == project.coordinator %}',
}

for old, new in replacements.items():
    content = content.replace(old, new)

# Write the new project_detail template
with open(r"d:\Plateforme_NLP\Plateforme\projects\templates\project_detail.html", 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ project_detail.html created successfully with tool_detail.html design!")
print(f"File size: {len(content)} characters")
