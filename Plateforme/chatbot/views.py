from datetime import datetime
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from django.conf import settings
from django.utils.translation import gettext as _
import requests
from django.contrib.auth.decorators import login_required
import uuid
import json
import logging

from .models import ChatSession, ChatMessage
from .content_helpers import get_content_object, build_context_prompt, get_content_metadata

logger = logging.getLogger('chatbot')

# Configuration from settings
FASTAPI_URL = getattr(settings, 'FASTAPI_URL', 'http://localhost:8000')
FASTAPI_API_KEY = getattr(settings, 'FASTAPI_API_KEY', '')
CHATBOT_MAX_FILE_SIZE = getattr(settings, 'CHATBOT_MAX_FILE_SIZE', 10485760)
CHATBOT_TIMEOUT = getattr(settings, 'CHATBOT_TIMEOUT', 120)
CHATBOT_MAX_HISTORY = getattr(settings, 'CHATBOT_MAX_HISTORY', 20)
CHATBOT_MAX_TOKENS = getattr(settings, 'CHATBOT_MAX_TOKENS', 24000)


def check_rate_limit(user_id, limit=30, window=60):
    """Rate limiting: 30 requests per minute per user"""
    key = f'chatbot_rate_{user_id}'
    count = cache.get(key, 0)
    
    if count >= limit:
        return False, limit - count
    
    cache.set(key, count + 1, window)
    return True, limit - count


def get_api_headers():
    """Generate headers for FastAPI requests"""
    headers = {'Content-Type': 'application/json'}
    if FASTAPI_API_KEY:
        headers['Authorization'] = f'Bearer {FASTAPI_API_KEY}'
    return headers


def save_message(session_id, message_type, content, source='bot', language='en'):
    """Save chat message to database"""
    try:
        session = ChatSession.objects.get(fastapi_session_id=session_id)
        ChatMessage.objects.create(
            session=session,
            message_type=message_type,
            content=content,
            source=source,
            language=language
        )
    except ChatSession.DoesNotExist:
        logger.warning(f"Session {session_id} not found for message save")
    except Exception as e:
        logger.error(f"Error saving message: {str(e)}")

@login_required
def chatbot_interface(request):
    """Main chatbot interface with session management"""
    session_id = None
    content_metadata = None
    
    # Check for content context from URL parameters
    content_type = request.GET.get('type')
    object_id = request.GET.get('id')
    content_obj = None
    
    if content_type and object_id:
        # Fetch the content object
        content_obj, error = get_content_object(content_type, object_id)
        if content_obj:
            logger.info(f"Content context loaded: {content_type} #{object_id}")
            content_metadata = get_content_metadata(content_obj, content_type)
        else:
            logger.warning(f"Failed to load content context: {error}")
    
    try:
        # Warmup FastAPI models on first access (with extended timeout)
        try:
            warmup_response = requests.get(
                f"{FASTAPI_URL}/warmup",
                headers=get_api_headers(),
                timeout=60
            )
            if warmup_response.status_code == 200:
                logger.info("FastAPI models warmed up successfully")
        except Exception as warmup_error:
            logger.warning(f"Model warmup failed (non-critical): {str(warmup_error)}")
        
        # Try to get existing active session
        existing_session = ChatSession.objects.filter(
            user=request.user,
            is_active=True
        ).order_by('-updated_at').first()
        
        if existing_session:
            session_id = existing_session.fastapi_session_id
            
            # Update content context if provided
            if content_obj:
                existing_session.content_type = content_type
                existing_session.object_id = str(object_id)
                existing_session.content_title = content_metadata.get('title', '')
                existing_session.save(update_fields=['content_type', 'object_id', 'content_title', 'updated_at'])
                logger.info(f"Updated session {session_id} with content context")
            
            logger.info(f"Reusing existing session {session_id} for user {request.user.email}")
        else:
            # Create new session via FastAPI
            response = requests.post(
                f"{FASTAPI_URL}/start_conversation",
                headers=get_api_headers(),
                timeout=30
            )
            response.raise_for_status()
            session_id = response.json().get("session_id")
            
            # Store in database with content context
            session_data = {
                'user': request.user,
                'fastapi_session_id': session_id,
            }
            
            if content_obj:
                session_data['content_type'] = content_type
                session_data['object_id'] = str(object_id)
                session_data['content_title'] = content_metadata.get('title', '')
            
            ChatSession.objects.create(**session_data)
            logger.info(f"Created new session {session_id} for user {request.user.email}")
            
    except requests.RequestException as e:
        logger.error(f"FastAPI connection error: {str(e)}")
        # Create fallback session
        session_id = str(uuid.uuid4())
        try:
            session_data = {
                'user': request.user,
                'fastapi_session_id': session_id,
                'is_active': False  # Mark as fallback
            }
            
            if content_obj:
                session_data['content_type'] = content_type
                session_data['object_id'] = str(object_id)
                session_data['content_title'] = content_metadata.get('title', '')
            
            ChatSession.objects.create(**session_data)
        except Exception as db_error:
            logger.error(f"Database error creating fallback session: {str(db_error)}")
    
    context = {
        'session_id': session_id,
        'max_file_size': CHATBOT_MAX_FILE_SIZE,
        'user_name': request.user.get_full_name() or request.user.email,
        'content_metadata': json.dumps(content_metadata) if content_metadata else None,
    }
    return render(request, "chatbot/chatbot.html", context=context)

@csrf_exempt
@require_http_methods(["POST"])
def ask_bot(request):
    """Handle all chatbot interactions with improved error handling and tracking"""
    
    # Authentication check
    if not request.user.is_authenticated:
        return JsonResponse({
            "error": _("Authentication required"),
            "source": "error"
        }, status=401)
    
    # Rate limiting
    allowed, remaining = check_rate_limit(request.user.id)
    if not allowed:
        logger.warning(f"Rate limit exceeded for user {request.user.email}")
        return JsonResponse({
            "error": _("Too many requests. Please wait a moment before sending another message."),
            "source": "error"
        }, status=429)
    
    try:
        # Parse request data
        if 'multipart/form-data' in request.content_type:
            data = request.POST
            pdf_file = request.FILES.get('pdf')
        else:
            data = json.loads(request.body)
            pdf_file = None

        mode = data.get('mode', 'conversation')
        question = data.get('question', '')
        session_id = data.get('session_id')

        if mode == 'upload':
            if not session_id:
                return JsonResponse({
                    "error": _("Session ID required for PDF upload mode."),
                    "source": "error"
                }, status=400)

            upload_success_message = ""

            if pdf_file:
                # Validate file size
                if pdf_file.size > CHATBOT_MAX_FILE_SIZE:
                    max_mb = CHATBOT_MAX_FILE_SIZE / (1024 * 1024)
                    return JsonResponse({
                        "error": _(f"File too large (max {max_mb}MB)."),
                        "source": "error"
                    }, status=400)
                
                # Validate file type
                if not pdf_file.name.lower().endswith('.pdf'):
                    return JsonResponse({
                        "error": _("Invalid file type. PDF expected."),
                        "source": "error"
                    }, status=400)

                # Upload PDF to FastAPI
                files_payload = {'file': (pdf_file.name, pdf_file, 'application/pdf')}
                headers_upload = {'session-id': session_id}
                if FASTAPI_API_KEY:
                    headers_upload['Authorization'] = f'Bearer {FASTAPI_API_KEY}'
                
                upload_resp = requests.post(
                    f"{FASTAPI_URL}/upload_pdf",
                    files=files_payload,
                    headers=headers_upload,
                    timeout=CHATBOT_TIMEOUT
                )
                upload_resp.raise_for_status()
                upload_json = upload_resp.json()
                
                # Update session with PDF info
                try:
                    session = ChatSession.objects.get(fastapi_session_id=session_id)
                    session.pdf_uploaded = True
                    session.pdf_filename = pdf_file.name
                    session.save()
                except ChatSession.DoesNotExist:
                    logger.warning(f"Session {session_id} not found for PDF upload tracking")
                
                upload_success_message = _(f"PDF '{pdf_file.name}' uploaded successfully ({upload_json.get('pages', 'N/A')} pages).")
                logger.info(f"PDF uploaded for session {session_id}: {pdf_file.name}")
            
            # Handle question after PDF upload
            if question and question.strip():
                save_message(session_id, 'user', question, source='user')
                
                ask_payload = {"question": question}
                headers_ask = get_api_headers()
                headers_ask['session-id'] = session_id
                
                ask_resp = requests.post(
                    f"{FASTAPI_URL}/ask",
                    json=ask_payload,
                    headers=headers_ask,
                    timeout=CHATBOT_TIMEOUT
                )
                ask_resp.raise_for_status()
                response_data = ask_resp.json()
                response_data['session_id'] = session_id
                
                # Save bot response
                if response_data.get('answer'):
                    save_message(session_id, 'bot', response_data['answer'], 
                               source=response_data.get('source', 'bot'),
                               language=response_data.get('lang', 'en'))
                
                if upload_success_message:
                    response_data['system_message_after_upload'] = upload_success_message
                
                return JsonResponse(response_data)
            elif upload_success_message:
                msg = upload_success_message + " " + _("You can now ask questions about it.")
                save_message(session_id, 'system', msg, source='system')
                return JsonResponse({
                    "message": msg,
                    "session_id": session_id,
                    "source": "system"
                })
            else:
                msg = _("Please ask a question about the previously uploaded PDF or upload a new PDF.")
                save_message(session_id, 'system', msg, source='system')
                return JsonResponse({
                    "message": msg,
                    "session_id": session_id,
                    "source": "system"
                })


        elif mode == 'delete':
            # Deactivate old session
            if session_id:
                try:
                    ChatSession.objects.filter(fastapi_session_id=session_id).update(is_active=False)
                    requests.post(
                        f"{FASTAPI_URL}/end_conversation/{session_id}",
                        headers=get_api_headers(),
                        timeout=30
                    ).raise_for_status()
                    logger.info(f"Deleted session {session_id}")
                except requests.RequestException as e:
                    logger.warning(f"Failed to end FastAPI session {session_id}: {str(e)}")
                except Exception as e:
                    logger.error(f"Error deactivating session: {str(e)}")
            
            # Create new session
            new_session_resp = requests.post(
                f"{FASTAPI_URL}/start_conversation",
                headers=get_api_headers(),
                timeout=30
            )
            new_session_resp.raise_for_status()
            new_session_id = new_session_resp.json()['session_id']
            
            # Store new session
            ChatSession.objects.create(
                user=request.user,
                fastapi_session_id=new_session_id
            )
            
            # Send initial message
            initial_question = question.strip() if question.strip() else _("Hello")
            save_message(new_session_id, 'user', initial_question, source='user')
            
            conv_payload = {
                "question": initial_question,
                "session_id": new_session_id,
                "max_history": CHATBOT_MAX_HISTORY,
                "max_tokens": CHATBOT_MAX_TOKENS
            }
            conv_resp = requests.post(
                f"{FASTAPI_URL}/conversation",
                json=conv_payload,
                headers=get_api_headers(),
                timeout=CHATBOT_TIMEOUT
            )
            conv_resp.raise_for_status()
            
            response_data = conv_resp.json()
            if response_data.get('answer'):
                save_message(new_session_id, 'bot', response_data['answer'],
                           source=response_data.get('source', 'bot'),
                           language=response_data.get('lang', 'en'))
            
            return JsonResponse(response_data)

        elif mode == 'quick':
            if not question or not question.strip():
                return JsonResponse({
                    "error": _("Question required for Quick Question mode."),
                    "source": "error"
                }, status=400)
            
            save_message(session_id, 'user', question, source='user')
            
            quick_payload = {"question": question}
            resp = requests.post(
                f"{FASTAPI_URL}/query",
                json=quick_payload,
                headers=get_api_headers(),
                timeout=CHATBOT_TIMEOUT
            )
            resp.raise_for_status()
            
            response_data = resp.json()
            if response_data.get('answer'):
                save_message(session_id, 'bot', response_data['answer'],
                           source=response_data.get('source', 'bot'),
                           language=response_data.get('lang', 'en'))
            
            return JsonResponse(response_data)

        else:  # mode == 'conversation'
            if not question or not question.strip():
                return JsonResponse({
                    "error": _("Question required for conversation."),
                    "source": "error"
                }, status=400)
            
            # Ensure session exists
            if not session_id:
                new_session_resp = requests.post(
                    f"{FASTAPI_URL}/start_conversation",
                    headers=get_api_headers(),
                    timeout=30
                )
                new_session_resp.raise_for_status()
                session_id = new_session_resp.json()['session_id']
                
                # Store new session
                ChatSession.objects.create(
                    user=request.user,
                    fastapi_session_id=session_id
                )
            
            save_message(session_id, 'user', question, source='user')
            
            # Check for content context
            system_prompt = None
            try:
                chat_session = ChatSession.objects.get(fastapi_session_id=session_id)
                
                # If has content context and this is first real question
                if chat_session.content_type and chat_session.object_id:
                    message_count = ChatMessage.objects.filter(session=chat_session, message_type='user').count()
                    
                    if message_count <= 1:  # First question
                        # Fetch content and build system prompt
                        content_obj, error = get_content_object(
                            chat_session.content_type, 
                            chat_session.object_id
                        )
                        
                        if content_obj:
                            system_prompt = build_context_prompt(content_obj, chat_session.content_type)
                            logger.info(f"Injecting content context for {chat_session.content_type} #{chat_session.object_id}")
            except ChatSession.DoesNotExist:
                logger.warning(f"Session {session_id} not found in database")
            except Exception as e:
                logger.error(f"Error building content context: {str(e)}")
            
            conv_payload = {
                "question": question,
                "session_id": session_id,
                "max_history": CHATBOT_MAX_HISTORY,
                "max_tokens": CHATBOT_MAX_TOKENS
            }
            
            # Add system prompt if we have content context
            if system_prompt:
                conv_payload["system_prompt"] = system_prompt
            
            conv_resp = requests.post(
                f"{FASTAPI_URL}/conversation",
                json=conv_payload,
                headers=get_api_headers(),
                timeout=CHATBOT_TIMEOUT
            )
            conv_resp.raise_for_status()
            
            response_data = conv_resp.json()
            if response_data.get('answer'):
                save_message(session_id, 'bot', response_data['answer'],
                           source=response_data.get('source', 'bot'),
                           language=response_data.get('lang', 'en'))
            
            return JsonResponse(response_data)

    except requests.exceptions.HTTPError as e:
        error_message = _("API Error")
        try:
            error_detail = e.response.json().get("detail", e.response.text[:200])
            logger.error(f"FastAPI HTTP Error {e.response.status_code}: {error_detail}")
        except ValueError:
            error_detail = e.response.text[:200]
            logger.error(f"FastAPI HTTP Error {e.response.status_code}: {error_detail}")
        
        return JsonResponse({
            "error": _("An error occurred processing your request. Please try again."),
            "source": "error"
        }, status=500)
    
    except requests.exceptions.Timeout:
        logger.error("FastAPI request timeout")
        return JsonResponse({
            "error": _("Request timeout. The server took too long to respond. Please try again."),
            "source": "error"
        }, status=504)
    
    except requests.exceptions.RequestException as e:
        logger.error(f"FastAPI connection error: {str(e)}")
        return JsonResponse({
            "error": _("Unable to connect to the chatbot service. Please try again later."),
            "source": "error"
        }, status=503)
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return JsonResponse({
            "error": _("Invalid request format."),
            "source": "error"
        }, status=400)
    
    except Exception as e:
        logger.exception(f"Unexpected error in chatbot: {str(e)}")
        return JsonResponse({
            "error": _("An unexpected error occurred. Please try again."),
            "source": "error"
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def start_new_session(request):
    """Create a new chat session"""
    if not request.user.is_authenticated:
        return JsonResponse({
            "error": _("Authentication required"),
            "source": "error"
        }, status=401)
    
    try:
        response = requests.post(
            f"{FASTAPI_URL}/start_conversation",
            headers=get_api_headers(),
            timeout=10
        )
        response.raise_for_status()
        session_id = response.json()["session_id"]
        
        # Store in database
        ChatSession.objects.create(
            user=request.user,
            fastapi_session_id=session_id
        )
        
        logger.info(f"Created new session {session_id} for user {request.user.email}")
        
        return JsonResponse({
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        })
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Error starting new session: {str(e)}")
        return JsonResponse({
            "error": _("Unable to start new session. Please try again."),
            "source": "error"
        }, status=503)


@login_required
def chatbot_interface(request):
    """
    Main chatbot interface/UI view
    """
    context = {
        'user': request.user,
        'page_title': _('Chatbot'),
    }
    return render(request, 'chatbot/chat.html', context)


@login_required
def chat_history(request):
    """
    Get all chat sessions for the current user
    """
    sessions = ChatSession.objects.filter(user=request.user).order_by('-created_at')
    
    data = {
        'sessions': [{
            'id': str(session.id),
            'title': session.title or f"Chat {session.created_at.strftime('%Y-%m-%d %H:%M')}",
            'created_at': session.created_at.isoformat(),
            'message_count': session.messages.count()
        } for session in sessions]
    }
    
    return JsonResponse(data)
