"""
Helper functions to fetch content from database for chatbot context
"""
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext as _
import logging

logger = logging.getLogger('chatbot')

# Map of content types to their model paths
CONTENT_TYPE_MAP = {
    'tool': ('resources', 'Tool'),
    'corpus': ('resources', 'Corpus'),
    'course': ('resources', 'Course'),
    'article': ('resources', 'Article'),
    'thesis': ('resources', 'Thesis'),
    'memoir': ('resources', 'Memoir'),
    'institution': ('institutions', 'Institution'),
    'project': ('projects', 'Project'),
    'topic': ('forum', 'Topic'),
    'event': ('events', 'Event'),
}

def _safe_person_display(person):
    """
    Return a display name for a user/person object whether
    get_full_name_display is a method or a plain attribute.
    """
    if not person:
        return ''

    display = getattr(person, 'get_full_name_display', None)
    if callable(display):
        try:
            value = display()
            if value:
                return str(value)
        except Exception:
            pass
    elif display:
        return str(display)

    full_name = getattr(person, 'get_full_name', None)
    if callable(full_name):
        try:
            value = full_name()
            if value:
                return str(value)
        except Exception:
            pass

    return str(person)


def get_content_object(content_type, object_id):
    """
    Fetch content object from database based on type and ID
    
    Args:
        content_type (str): Type of content (tool, corpus, course, etc.)
        object_id (str): The object's primary key
        
    Returns:
        tuple: (object, error_message) - object is None if error
    """
    try:
        # Normalize content type
        content_type = content_type.lower()
        
        if content_type not in CONTENT_TYPE_MAP:
            return None, f"Unknown content type: {content_type}"
        
        app_label, model_name = CONTENT_TYPE_MAP[content_type]
        
        # Get the content type
        try:
            ct = ContentType.objects.get(app_label=app_label, model=model_name.lower())
        except ContentType.DoesNotExist:
            logger.error(f"ContentType not found: {app_label}.{model_name}")
            return None, f"Content type configuration error"
        
        # Get the model class
        model_class = ct.model_class()
        
        # Fetch the object
        try:
            obj = model_class.objects.get(pk=object_id)
            return obj, None
        except model_class.DoesNotExist:
            return None, f"{model_name} with ID {object_id} not found"
        except Exception as e:
            logger.error(f"Error fetching {model_name} {object_id}: {str(e)}")
            return None, f"Error fetching content: {str(e)}"
            
    except Exception as e:
        logger.error(f"Unexpected error in get_content_object: {str(e)}")
        return None, f"Unexpected error: {str(e)}"


def build_context_prompt(content_obj, content_type):
    """
    Build a system prompt with content context
    
    Args:
        content_obj: The Django model instance
        content_type (str): Type of content
        
    Returns:
        str: Formatted system prompt
    """
    try:
        # Get title (try different field names)
        title = None
        for attr in ['get_localized_title', 'title', 'get_localized_name', 'name']:
            if hasattr(content_obj, attr):
                val = getattr(content_obj, attr)
                title = val() if callable(val) else val
                if title:
                    break
        
        # Get description
        description = None
        for attr in ['get_localized_description', 'description', 'get_localized_summary', 'summary']:
            if hasattr(content_obj, attr):
                val = getattr(content_obj, attr)
                description = val() if callable(val) else val
                if description:
                    break
        
        # Build prompt
        prompt_parts = [
            f"You are answering questions about the following {content_type}:",
            f"Title: {title or 'N/A'}",
        ]
        
        if description:
            prompt_parts.append(f"Description: {description}")
        
        # Add type-specific fields
        if content_type == 'tool':
            if hasattr(content_obj, 'tool_type'):
                prompt_parts.append(f"Type: {content_obj.get_tool_type_display() if hasattr(content_obj, 'get_tool_type_display') else content_obj.tool_type}")
            if hasattr(content_obj, 'supported_languages'):
                prompt_parts.append(f"Supported Languages: {content_obj.supported_languages}")
            if hasattr(content_obj, 'version'):
                prompt_parts.append(f"Version: {content_obj.version}")
                
        elif content_type == 'corpus':
            if hasattr(content_obj, 'field'):
                prompt_parts.append(f"Field: {content_obj.get_field_display() if hasattr(content_obj, 'get_field_display') else content_obj.field}")
            if hasattr(content_obj, 'language'):
                prompt_parts.append(f"Language: {content_obj.get_language_display() if hasattr(content_obj, 'get_language_display') else content_obj.language}")
            if hasattr(content_obj, 'file_format'):
                prompt_parts.append(f"Format: {content_obj.file_format}")
                
        elif content_type == 'course':
            if hasattr(content_obj, 'academic_level'):
                prompt_parts.append(f"Level: {content_obj.get_academic_level_display() if hasattr(content_obj, 'get_academic_level_display') else content_obj.academic_level}")
            if hasattr(content_obj, 'academic_year'):
                prompt_parts.append(f"Year: {content_obj.academic_year}")
            if hasattr(content_obj, 'teacher'):
                prompt_parts.append(f"Instructor: {_safe_person_display(content_obj.teacher)}")
                
        elif content_type == 'project':
            if hasattr(content_obj, 'status'):
                prompt_parts.append(f"Status: {content_obj.get_status_display() if hasattr(content_obj, 'get_status_display') else content_obj.status}")
            if hasattr(content_obj, 'institution'):
                prompt_parts.append(f"Institution: {content_obj.institution}")
                
        elif content_type == 'event':
            if hasattr(content_obj, 'event_type'):
                prompt_parts.append(f"Type: {content_obj.get_event_type_display() if hasattr(content_obj, 'get_event_type_display') else content_obj.event_type}")
            if hasattr(content_obj, 'start_date'):
                prompt_parts.append(f"Start Date: {content_obj.start_date}")
            if hasattr(content_obj, 'organizer'):
                prompt_parts.append(f"Organizer: {content_obj.organizer}")
        
        prompt_parts.append("\nPlease answer user questions specifically about this content. Provide helpful, accurate, and contextual responses.")
        
        return "\n".join(prompt_parts)
        
    except Exception as e:
        logger.error(f"Error building context prompt: {str(e)}")
        return f"Answering questions about {content_type}: {getattr(content_obj, 'title', str(content_obj))}"


def get_content_metadata(content_obj, content_type):
    """
    Extract metadata from content object for display
    
    Returns:
        dict: Metadata dictionary
    """
    metadata = {
        'contentType': content_type,
        'objectId': str(content_obj.pk),
        'title': 'Untitled',
        'link': '',
        'category': '',
        'author': '',
        'description': ''
    }
    
    # Get title
    for attr in ['get_localized_title', 'title', 'get_localized_name', 'name']:
        if hasattr(content_obj, attr):
            val = getattr(content_obj, attr)
            title = val() if callable(val) else val
            if title:
                metadata['title'] = title
                break
    
    # Get URL
    if hasattr(content_obj, 'get_absolute_url'):
        try:
            metadata['link'] = content_obj.get_absolute_url()
        except:
            pass

    # Get description
    for attr in ['get_localized_description', 'description', 'get_localized_summary', 'summary']:
        if hasattr(content_obj, attr):
            val = getattr(content_obj, attr)
            description = val() if callable(val) else val
            if description:
                metadata['description'] = str(description)[:500]
                break

    # Get category/type display (best effort)
    if hasattr(content_obj, 'get_tool_type_display'):
        metadata['category'] = content_obj.get_tool_type_display()
    elif hasattr(content_obj, 'get_field_display'):
        metadata['category'] = content_obj.get_field_display()
    elif hasattr(content_obj, 'get_event_type_display'):
        metadata['category'] = content_obj.get_event_type_display()
    elif hasattr(content_obj, 'get_status_display'):
        metadata['category'] = content_obj.get_status_display()
    elif hasattr(content_obj, 'get_type_display'):
        metadata['category'] = content_obj.get_type_display()
    elif hasattr(content_obj, 'resource_type'):
        metadata['category'] = str(content_obj.resource_type)

    # Get author/owner (best effort)
    if hasattr(content_obj, 'author') and getattr(content_obj, 'author', None):
        author_obj = getattr(content_obj, 'author')
        metadata['author'] = _safe_person_display(author_obj)
    elif hasattr(content_obj, 'coordinator') and getattr(content_obj, 'coordinator', None):
        coordinator = getattr(content_obj, 'coordinator')
        metadata['author'] = _safe_person_display(coordinator)
    elif hasattr(content_obj, 'organizer'):
        metadata['author'] = str(getattr(content_obj, 'organizer'))
    
    return metadata
