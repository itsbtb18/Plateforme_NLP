from datetime import datetime
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Exists, OuterRef
from django.db.models import Q
from django.core.cache import cache
from django.conf import settings
from django.utils.translation import gettext as _
import requests
from django.contrib.auth.decorators import login_required
import uuid
import json
import logging
import time
import re

from .models import ChatSession, ChatMessage
from .content_helpers import get_content_object, build_context_prompt, get_content_metadata

logger = logging.getLogger("chatbot")

CARD_CONTEXT_PREFIX = "__CARD_CONTEXT__:"
WEB_RESULTS_PREFIX = "__WEB_RESULTS__:"

# Configuration from settings
FASTAPI_URL = getattr(settings, "FASTAPI_URL", "http://localhost:8000")
FASTAPI_API_KEY = getattr(settings, "FASTAPI_API_KEY", "")
CHATBOT_MAX_FILE_SIZE = getattr(settings, "CHATBOT_MAX_FILE_SIZE", 20971520)
CHATBOT_TIMEOUT = getattr(settings, "CHATBOT_TIMEOUT", 180)
CHATBOT_MAX_HISTORY = getattr(settings, "CHATBOT_MAX_HISTORY", 20)
CHATBOT_MAX_TOKENS = getattr(settings, "CHATBOT_MAX_TOKENS", 8192)

ALLOWED_FILE_TYPES = {".pdf", ".doc", ".docx", ".txt", ".xlsx"}


def check_rate_limit(user_id, limit=30, window=60):
    try:
        key = f"chatbot_rate_{user_id}"
        count = cache.get(key, 0)
        if count >= limit:
            return False, limit - count
        cache.set(key, count + 1, window)
        return True, limit - count
    except Exception:
        # Redis unavailable — allow the request rather than crash
        return True, limit


def get_api_headers():
    headers = {"Content-Type": "application/json"}
    if FASTAPI_API_KEY:
        headers["Authorization"] = f"Bearer {FASTAPI_API_KEY}"
    return headers


def save_message(session_id, message_type, content, source="bot", language="en"):
    try:
        session = ChatSession.objects.get(fastapi_session_id=session_id)
        ChatMessage.objects.create(
            session=session,
            message_type=message_type,
            content=content,
            source=source,
            language=language,
        )
        session.save()  # touch updated_at
    except ChatSession.DoesNotExist:
        logger.warning(f"Session {session_id} not found for message save")
    except Exception as e:
        logger.error(f"Error saving message: {str(e)}")


def save_card_context(session_id, context, language="en"):
    """Persist selected entity card context so it can be restored on reload."""
    if not isinstance(context, dict):
        return

    clean = {
        "type": str(context.get("type", "resource"))[:50],
        "title": str(context.get("title", ""))[:500],
        "description": str(context.get("description", ""))[:5000],
        "category": str(context.get("category", ""))[:200],
        "author": str(context.get("author", ""))[:200],
        "url": str(context.get("url", ""))[:500],
    }
    if not clean["title"]:
        return

    payload = CARD_CONTEXT_PREFIX + json.dumps(clean, ensure_ascii=False)
    save_message(
        session_id,
        "system",
        payload,
        source="platform_context",
        language=language,
    )


def save_web_results(session_id, results, source_urls=None, language="en"):
    """Persist Tavily results so source cards/links survive refresh."""
    if not isinstance(results, list) or not results:
        return

    cleaned_results = []
    for r in results[:10]:
        if not isinstance(r, dict):
            continue
        url = str(r.get("url", "")).strip()[:1000]
        if not url:
            continue
        cleaned_results.append(
            {
                "url": url,
                "title": str(r.get("title", "")).strip()[:500],
                "content": str(r.get("content", "")).strip()[:2000],
                "score": r.get("score"),
            }
        )

    if not cleaned_results:
        return

    payload = {
        "results": cleaned_results,
        "source_urls": [str(u)[:1000] for u in (source_urls or []) if u],
    }
    save_message(
        session_id,
        "system",
        WEB_RESULTS_PREFIX + json.dumps(payload, ensure_ascii=False),
        source="web_results",
        language=language,
    )


def _get_user_id(user):
    return str(user.id)


def _build_card_context_prompt(context):
    """Build a compact prompt from selected card/resource context."""
    if not isinstance(context, dict):
        return ""

    title = str(context.get("title", "")).strip()
    category = str(context.get("category", "")).strip()
    author = str(context.get("author", "")).strip()
    description = str(context.get("description", "")).strip()
    content_type = str(context.get("type", "")).strip()
    content_url = str(context.get("url", "")).strip()

    if not any([title, category, author, description, content_type]):
        return ""

    prompt_parts = ["The user is asking about a specific platform content item."]
    if content_type:
        prompt_parts.append(f"Content type: {content_type}")
    if title:
        prompt_parts.append(f"Title: {title}")
    if category:
        prompt_parts.append(f"Category: {category}")
    if author:
        prompt_parts.append(f"Author/Owner: {author}")
    if description:
        prompt_parts.append(f"Description: {description[:800]}")
    if content_url:
        prompt_parts.append(f"URL: {content_url}")
    prompt_parts.append(
        "Use this context as ground truth and answer specifically about this item when relevant."
    )
    return "\n".join(prompt_parts)


def _get_request_content_context(request):
    """
    Resolve content context from query params (?context|type + id),
    then fallback to session context from set_card_context.
    """
    content_type = (request.GET.get("context") or request.GET.get("type") or "").strip()
    object_id = (request.GET.get("id") or request.GET.get("object_id") or "").strip()

    if content_type and object_id:
        obj, err = get_content_object(content_type, object_id)
        if not err and obj:
            metadata = get_content_metadata(obj, content_type)
            prompt = build_context_prompt(obj, content_type)
            request.session["chatbot_card_context"] = metadata
            request.session["chatbot_context_prompt"] = prompt
            request.session.modified = True
            return prompt, metadata

    session_prompt = request.session.get("chatbot_context_prompt")
    session_context = request.session.get("chatbot_card_context")
    if session_prompt:
        return str(session_prompt), session_context if isinstance(session_context, dict) else {}

    if isinstance(session_context, dict):
        return _build_card_context_prompt(session_context), session_context

    return "", {}


def _inject_context_into_question(question, context_prompt):
    """Prefix question with resource context before forwarding to FastAPI."""
    if not question or not context_prompt:
        return question
    return (
        "[CONTEXT]\n"
        f"{context_prompt}\n\n"
        "[USER QUESTION]\n"
        f"{question}"
    )


def _create_fastapi_session(user):
    """Create a new session via FastAPI and store in Django DB."""
    resp = requests.post(
        f"{FASTAPI_URL}/sessions",
        params={
            "user_id": _get_user_id(user),
            "user_country": getattr(user, "country", None) or "",
            "user_city": getattr(user, "city", None) or "",
        },
        headers=get_api_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    session_id = resp.json()["session_id"]

    ChatSession.objects.create(
        user=user,
        fastapi_session_id=session_id,
    )
    logger.info(f"Created session {session_id} for user {user.email}")
    return session_id


# ------------------------------------------------------------------
# Main UI view
# ------------------------------------------------------------------


@login_required
def chatbot_interface(request):
    # Persist context when opening chatbot from detail/card links.
    _get_request_content_context(request)

    # If entity context exists, pass it to the template so the JS can
    # auto-fire a platform_entity explain request on page load.
    entity_context_json = "{}"
    session_ctx = request.session.get("chatbot_card_context")
    if isinstance(session_ctx, dict) and session_ctx.get("title"):
        import json as _json
        entity_context_json = _json.dumps(session_ctx)

    # Feature 2: document context from query params
    # e.g. ?doc_action=analyse&doc_id=55&doc_title=...&doc_file=/media/...
    document_context_json = "{}"
    doc_action = request.GET.get("doc_action", "").strip()
    doc_id = request.GET.get("doc_id", "").strip()
    doc_title = request.GET.get("doc_title", "").strip()
    doc_file = request.GET.get("doc_file", "").strip()
    if doc_action == "analyse" and doc_id and doc_file:
        import json as _json
        document_context_json = _json.dumps({
            "document_id": doc_id,
            "document_title": doc_title or "Document",
            "document_file_url": doc_file,
        })

    context = {
        "user": request.user,
        "page_title": _("Chatbot"),
        "max_file_size": CHATBOT_MAX_FILE_SIZE,
        "entity_context_json": entity_context_json,
        "document_context_json": document_context_json,
    }
    return render(request, "chatbot/chat.html", context)


# ------------------------------------------------------------------
# Session management
# ------------------------------------------------------------------


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def create_session(request):
    try:
        session_id = _create_fastapi_session(request.user)
        return JsonResponse(
            {
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except requests.RequestException as e:
        logger.error(f"Error creating session: {e}")
        return JsonResponse({"error": _("Unable to create session.")}, status=503)


@login_required
def list_sessions(request):
    user_message_exists = ChatMessage.objects.filter(
        session=OuterRef("pk"),
        message_type="user",
    )
    context_card_exists = ChatMessage.objects.filter(
        session=OuterRef("pk"),
        message_type="system",
        source="platform_context",
    )
    sessions = (
        ChatSession.objects.filter(user=request.user)
        .annotate(has_user_messages=Exists(user_message_exists))
        .annotate(has_context_cards=Exists(context_card_exists))
        .filter(Q(has_user_messages=True) | Q(has_context_cards=True))
        .order_by("-is_pinned", "-updated_at")
    )

    data = {
        "sessions": [
            {
                "id": str(s.id),
                "session_id": s.fastapi_session_id,
                "title": s.title or f"Chat {s.created_at.strftime('%Y-%m-%d %H:%M')}",
                "created_at": s.created_at.isoformat(),
                "is_pinned": s.is_pinned,
                "updated_at": s.updated_at.isoformat(),
                "is_active": s.is_active,
                "message_count": s.messages.count(),
            }
            for s in sessions
        ]
    }
    return JsonResponse(data)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def rename_session(request):
    try:
        body = json.loads(request.body)
        session_id = body.get("session_id")
        title = body.get("title", "").strip()

        if not session_id or not title:
            return JsonResponse(
                {"error": _("Session ID and title required.")}, status=400
            )

        session = ChatSession.objects.get(
            fastapi_session_id=session_id,
            user=request.user,
        )
        session.title = title[:200]
        session.save()

        # Also rename on FastAPI side
        try:
            requests.patch(
                f"{FASTAPI_URL}/sessions/{session_id}/title",
                json={"title": title[:200]},
                headers=get_api_headers(),
                timeout=10,
            )
        except requests.RequestException:
            pass  # non-critical

        return JsonResponse({"status": "ok", "title": session.title})

    except ChatSession.DoesNotExist:
        return JsonResponse({"error": _("Session not found.")}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({"error": _("Invalid request.")}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def delete_session(request):
    try:
        body = json.loads(request.body)
        session_id = body.get("session_id")

        session = ChatSession.objects.get(
            fastapi_session_id=session_id,
            user=request.user,
        )

        # End on FastAPI side
        try:
            requests.delete(
                f"{FASTAPI_URL}/sessions/{session_id}",
                headers=get_api_headers(),
                timeout=10,
            )
        except requests.RequestException:
            pass

        session.delete()
        return JsonResponse({"status": "ok"})

    except ChatSession.DoesNotExist:
        return JsonResponse({"error": _("Session not found.")}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({"error": _("Invalid request.")}, status=400)


@login_required
def session_history(request, session_id):
    """Get messages for a specific session."""
    try:
        session = ChatSession.objects.get(
            fastapi_session_id=session_id,
            user=request.user,
        )
    except ChatSession.DoesNotExist:
        return JsonResponse({"error": _("Session not found.")}, status=404)

    messages = session.messages.order_by("timestamp")[:200]
    serialized_messages = []
    for m in messages:
        if (
            m.message_type == "user"
            and (m.source or "") == "platform"
            and isinstance(m.content, str)
            and m.content.startswith("Ask AI about:")
        ):
            # Synthetic helper line used internally for card explain.
            # Keep it in DB if present, but do not replay in chat history UI.
            continue

        if (
            m.message_type == "system"
            and m.content
            and m.content.startswith(CARD_CONTEXT_PREFIX)
        ):
            ctx_raw = m.content[len(CARD_CONTEXT_PREFIX):]
            try:
                ctx = json.loads(ctx_raw)
            except json.JSONDecodeError:
                ctx = None
            if isinstance(ctx, dict) and ctx.get("title"):
                serialized_messages.append(
                    {
                        "type": "context_card",
                        "content": ctx,
                        "source": "platform_context",
                        "language": m.language,
                        "timestamp": m.timestamp.isoformat(),
                        "message_id": str(m.id),
                        "is_pinned": m.is_pinned,
                    }
                )
                continue

        if (
            m.message_type == "system"
            and m.content
            and m.content.startswith(WEB_RESULTS_PREFIX)
        ):
            web_raw = m.content[len(WEB_RESULTS_PREFIX):]
            try:
                web_payload = json.loads(web_raw)
            except json.JSONDecodeError:
                web_payload = None
            if isinstance(web_payload, dict) and isinstance(web_payload.get("results"), list):
                serialized_messages.append(
                    {
                        "type": "web_results",
                        "content": web_payload,
                        "source": "web_results",
                        "language": m.language,
                        "timestamp": m.timestamp.isoformat(),
                        "message_id": str(m.id),
                        "is_pinned": m.is_pinned,
                    }
                )
                continue

        serialized_messages.append(
            {
                "type": m.message_type,
                "content": m.content,
                "source": m.source or "bot",
                "language": m.language,
                "timestamp": m.timestamp.isoformat(),
                "message_id": str(m.id),
                "is_pinned": m.is_pinned,
            }
        )

    data = {
        "session_id": session_id,
        "title": session.title or "",
        "messages": serialized_messages,
    }
    return JsonResponse(data)


# ------------------------------------------------------------------
# Pin / Unpin messages
# ------------------------------------------------------------------


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def toggle_pin_message(request, message_id):
    """Toggle the is_pinned flag on a ChatMessage owned by the user."""
    try:
        message = ChatMessage.objects.select_related("session").get(id=message_id)
    except ChatMessage.DoesNotExist:
        return JsonResponse({"error": _("Message not found.")}, status=404)

    if message.session.user != request.user:
        return JsonResponse({"error": _("Permission denied.")}, status=403)

    message.is_pinned = not message.is_pinned
    message.save(update_fields=["is_pinned"])
    return JsonResponse({"status": "ok", "is_pinned": message.is_pinned, "message_id": str(message.id)})

@csrf_exempt
@require_http_methods(["POST"])
@login_required
def toggle_pin_session(request, session_id):
    """Toggle the is_pinned flag on a ChatSession owned by the user."""
    try:
        session = ChatSession.objects.get(fastapi_session_id=session_id)
    except ChatSession.DoesNotExist:
        return JsonResponse({"error": _("Session not found.")}, status=404)

    if session.user != request.user:
        return JsonResponse({"error": _("Permission denied.")}, status=403)

    session.is_pinned = not session.is_pinned
    session.save(update_fields=["is_pinned"])
    return JsonResponse({"status": "ok", "is_pinned": session.is_pinned, "session_id": str(session.fastapi_session_id)})


# ------------------------------------------------------------------
# Ask bot — main interaction endpoint
# ------------------------------------------------------------------


@csrf_exempt
@require_http_methods(["POST"])
def ask_bot(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": _("Authentication required"), "source": "error"}, status=401
        )

    allowed, remaining = check_rate_limit(request.user.id)
    if not allowed:
        return JsonResponse(
            {
                "error": _("Too many requests. Please wait a moment."),
                "source": "error",
            },
            status=429,
        )

    try:
        # Parse request
        if request.content_type and "multipart/form-data" in request.content_type:
            data = request.POST
            uploaded_file = request.FILES.get("file")
        else:
            data = json.loads(request.body)
            uploaded_file = None

        mode = data.get("mode", "conversation")
        question = data.get("question", "").strip()
        session_id = data.get("session_id", "")
        user_id = _get_user_id(request.user)
        context_prompt = ""
        context_metadata = {}

        payload_context = data.get("context")
        if isinstance(payload_context, dict):
            context_prompt = _build_card_context_prompt(payload_context)
            context_metadata = payload_context
        else:
            context_prompt, context_metadata = _get_request_content_context(request)

        # Clear session context after consuming it so it doesn't
        # persist into subsequent messages (prevents stale card
        # context like "AIntelia" from leaking into greetings).
        request.session.pop("chatbot_card_context", None)
        request.session.pop("chatbot_context_prompt", None)
        request.session.modified = True

        # Auto-create session if missing
        if not session_id:
            session_id = _create_fastapi_session(request.user)

        # Build user profile context for the LLM
        user_profile = _build_user_profile(request.user)

        # ----- Mode: conversation -----
        if mode == "conversation":
            if not question:
                return JsonResponse(
                    {"error": _("Please type a message."), "source": "error"},
                    status=400,
                )
            save_message(session_id, "user", question)
            effective_question = _inject_context_into_question(question, context_prompt)

            resp = requests.post(
                f"{FASTAPI_URL}/conversation",
                json={
                    "question": effective_question,
                    "session_id": session_id,
                    "user_id": user_id,
                    "max_history": CHATBOT_MAX_HISTORY,
                    "max_tokens": min(CHATBOT_MAX_TOKENS, 8192),
                    **({
                        "mode": data.get("chatbot_mode"),
                    } if data.get("chatbot_mode") else {}),
                    **user_profile,
                },
                headers=get_api_headers(),
                timeout=CHATBOT_TIMEOUT,
            )
            resp.raise_for_status()
            response_data = resp.json()

            if response_data.get("answer"):
                save_message(
                    session_id,
                    "bot",
                    response_data["answer"],
                    source=response_data.get("source", "bot"),
                    language=response_data.get("lang", "en"),
                )

            # Auto-title session on first message
            _auto_title_session(session_id, question)

            response_data["session_id"] = session_id
            response_data["context_applied"] = bool(context_prompt)
            response_data["context_metadata"] = context_metadata
            return JsonResponse(response_data)

        # ----- Mode: quick -----
        elif mode == "quick":
            if not question:
                return JsonResponse(
                    {"error": _("Please type a question."), "source": "error"},
                    status=400,
                )
            save_message(session_id, "user", question)
            effective_question = _inject_context_into_question(question, context_prompt)

            resp = requests.post(
                f"{FASTAPI_URL}/query",
                json={"question": effective_question},
                headers=get_api_headers(),
                timeout=CHATBOT_TIMEOUT,
            )
            resp.raise_for_status()
            response_data = resp.json()

            if response_data.get("answer"):
                save_message(
                    session_id,
                    "bot",
                    response_data["answer"],
                    source=response_data.get("source", "bot"),
                    language=response_data.get("lang", "en"),
                )

            response_data["session_id"] = session_id
            response_data["context_applied"] = bool(context_prompt)
            response_data["context_metadata"] = context_metadata
            _auto_title_session(session_id, question)
            return JsonResponse(response_data)

        # ----- Mode: legal -----
        elif mode == "legal":
            if not question:
                return JsonResponse(
                    {"error": _("Please type a legal question."), "source": "error"},
                    status=400,
                )
            save_message(session_id, "user", question)

            resp = requests.post(
                f"{FASTAPI_URL}/legal_search",
                json={
                    "question": question,
                    "language": data.get("language"),
                    "jurisdiction": data.get("jurisdiction"),
                    "category": data.get("category"),
                },
                headers=get_api_headers(),
                timeout=CHATBOT_TIMEOUT,
            )
            resp.raise_for_status()
            response_data = resp.json()

            if response_data.get("answer"):
                save_message(
                    session_id,
                    "bot",
                    response_data["answer"],
                    source="legal",
                    language=response_data.get("lang", "en"),
                )

            response_data["session_id"] = session_id
            _auto_title_session(session_id, question)
            return JsonResponse(response_data)

        # ----- Mode: platform -----
        elif mode == "platform":
            if not question:
                return JsonResponse(
                    {"error": _("Please type a search query."), "source": "error"},
                    status=400,
                )
            save_message(session_id, "user", question)

            resp = requests.post(
                f"{FASTAPI_URL}/platform/search",
                json={
                    "query": question,
                    "resource_type": data.get("resource_type"),
                    "language": data.get("language"),
                    "limit": 10,
                },
                headers=get_api_headers(),
                timeout=CHATBOT_TIMEOUT,
            )
            resp.raise_for_status()
            platform_data = resp.json()
            platform_data["session_id"] = session_id
            _auto_title_session(session_id, question)
            return JsonResponse(platform_data)

        # ----- Mode: platform_entity (explain a specific entity) -----
        elif mode == "platform_entity":
            entity_ctx = data.get("entity_context")
            if not isinstance(entity_ctx, dict) or not entity_ctx.get("title"):
                return JsonResponse(
                    {"error": _("Entity context required."), "source": "error"},
                    status=400,
                )
            save_card_context(session_id, entity_ctx, language=data.get("language") or "en")

            resp = requests.post(
                f"{FASTAPI_URL}/platform/entity_explain",
                json={
                    "entity_type": str(entity_ctx.get("type", "resource"))[:50],
                    "entity_title": str(entity_ctx.get("title", ""))[:500],
                    "entity_description": str(entity_ctx.get("description", ""))[:5000],
                    "entity_metadata": {
                        k: str(v)[:200]
                        for k, v in entity_ctx.items()
                        if k not in ("type", "title", "description") and v
                    },
                    "session_id": session_id,
                    "user_id": user_id,
                    "language": data.get("language"),
                },
                headers=get_api_headers(),
                timeout=CHATBOT_TIMEOUT,
            )
            resp.raise_for_status()
            response_data = resp.json()

            if response_data.get("answer"):
                save_message(
                    session_id,
                    "bot",
                    response_data["answer"],
                    source=response_data.get("source", "platform"),
                    language=response_data.get("lang", "en"),
                )

            response_data["session_id"] = session_id
            entity_title = str(entity_ctx.get("title", "")).strip()
            if entity_title:
                _auto_title_session(session_id, entity_title)
            return JsonResponse(response_data)

        # ----- Mode: platform_document (ingest & analyse a platform PDF) --
        elif mode == "platform_document":
            doc_ctx = data.get("document_context")
            if not isinstance(doc_ctx, dict) or not doc_ctx.get("document_id"):
                return JsonResponse(
                    {"error": _("Document context required."), "source": "error"},
                    status=400,
                )

            platform_doc_id = doc_ctx["document_id"]
            doc_title = str(doc_ctx.get("document_title", ""))[:300]
            doc_file_url = str(doc_ctx.get("document_file_url", ""))

            # Resolve file from Django's media storage
            import os
            from django.conf import settings as django_settings

            if not doc_file_url:
                return JsonResponse(
                    {"error": _("No file attached to this document."), "source": "error"},
                    status=400,
                )

            # doc_file_url is a relative media path like "/media/resources/files/2025/01/paper.pdf"
            # Convert to absolute filesystem path inside the container
            media_root = getattr(django_settings, "MEDIA_ROOT", "/app/media")
            # Strip leading /media/ prefix if present
            relative_path = doc_file_url
            if relative_path.startswith("/media/"):
                relative_path = relative_path[len("/media/"):]
            elif relative_path.startswith("media/"):
                relative_path = relative_path[len("media/"):]
            file_path = os.path.join(media_root, relative_path)

            if not os.path.isfile(file_path):
                return JsonResponse(
                    {"error": _("Document file not found on server."), "source": "error"},
                    status=400,
                )

            filename = os.path.basename(file_path)
            content_type = "application/pdf"
            if filename.lower().endswith(".docx"):
                content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            elif filename.lower().endswith(".txt"):
                content_type = "text/plain"

            # Upload to FastAPI via the platform document ingest endpoint
            upload_headers = {}
            if FASTAPI_API_KEY:
                upload_headers["Authorization"] = f"Bearer {FASTAPI_API_KEY}"

            with open(file_path, "rb") as f:
                upload_resp = requests.post(
                    f"{FASTAPI_URL}/platform/document_ingest",
                    files={"file": (filename, f, content_type)},
                    data={
                        "session_id": session_id,
                        "user_id": user_id,
                        "platform_document_id": str(platform_doc_id),
                    },
                    headers=upload_headers,
                    timeout=CHATBOT_TIMEOUT,
                )

            if not upload_resp.ok:
                err = upload_resp.json().get("detail", "Upload failed")
                return JsonResponse(
                    {"error": str(err), "source": "error"}, status=upload_resp.status_code,
                )

            upload_data = upload_resp.json()
            fastapi_doc_id = upload_data.get("document_id")

            # Poll until document is processed (max 120s)
            doc_ready = False
            for _attempt in range(60):
                time.sleep(2)
                try:
                    status_resp = requests.get(
                        f"{FASTAPI_URL}/document_status/{fastapi_doc_id}",
                        params={"user_id": user_id},
                        headers=get_api_headers(),
                        timeout=10,
                    )
                    if status_resp.ok:
                        status_data = status_resp.json()
                        if status_data.get("status") == "completed":
                            doc_ready = True
                            break
                        elif status_data.get("status") == "failed":
                            return JsonResponse(
                                {"error": _("Document processing failed."), "source": "error"},
                                status=500,
                            )
                except requests.RequestException:
                    pass

            if not doc_ready:
                return JsonResponse({
                    "answer": _(
                        "Document is still being processed. "
                        "Please ask your question again in a few seconds."
                    ),
                    "source": "system",
                    "session_id": session_id,
                    "document_id": fastapi_doc_id,
                    "document_status": "processing",
                })

            # Document ready — send initial analysis prompt
            initial_prompt = (
                f"Please analyse this document titled '{doc_title}' "
                f"and explain its key ideas, main findings, and structure."
            )
            ask_resp = requests.post(
                f"{FASTAPI_URL}/ask_document",
                json={
                    "question": initial_prompt,
                    "session_id": session_id,
                    "user_id": user_id,
                    "document_ids": [fastapi_doc_id] if fastapi_doc_id else None,
                },
                headers=get_api_headers(),
                timeout=CHATBOT_TIMEOUT,
            )
            ask_resp.raise_for_status()
            response_data = ask_resp.json()

            if response_data.get("answer"):
                save_message(
                    session_id,
                    "bot",
                    response_data["answer"],
                    source="document",
                    language=response_data.get("lang", "en"),
                )

            response_data["session_id"] = session_id
            response_data["document_id"] = fastapi_doc_id
            response_data["document_status"] = "completed"
            if doc_title:
                _auto_title_session(session_id, doc_title)
            return JsonResponse(response_data)

        # ----- Mode: upload -----
        elif mode == "upload":
            if not uploaded_file:
                return JsonResponse(
                    {
                        "error": _("Please select a file to upload."),
                        "source": "error",
                    },
                    status=400,
                )

            # Validate size
            if uploaded_file.size > CHATBOT_MAX_FILE_SIZE:
                max_mb = CHATBOT_MAX_FILE_SIZE / (1024 * 1024)
                return JsonResponse(
                    {
                        "error": _(f"File too large (max {max_mb:.0f}MB)."),
                        "source": "error",
                    },
                    status=400,
                )

            # Validate extension
            import os

            ext = os.path.splitext(uploaded_file.name)[1].lower()
            if ext not in ALLOWED_FILE_TYPES:
                return JsonResponse(
                    {
                        "error": _(
                            "Unsupported file type. Allowed: PDF, DOC, DOCX, TXT, XLSX."
                        ),
                        "source": "error",
                    },
                    status=400,
                )

            # Upload to FastAPI
            upload_headers = {}
            if FASTAPI_API_KEY:
                upload_headers["Authorization"] = f"Bearer {FASTAPI_API_KEY}"

            upload_resp = requests.post(
                f"{FASTAPI_URL}/upload_document",
                files={
                    "file": (
                        uploaded_file.name,
                        uploaded_file,
                        uploaded_file.content_type,
                    )
                },
                data={"session_id": session_id, "user_id": user_id},
                headers=upload_headers,
                timeout=CHATBOT_TIMEOUT,
            )
            upload_resp.raise_for_status()
            upload_data = upload_resp.json()

            # Update session record
            try:
                session = ChatSession.objects.get(fastapi_session_id=session_id)
                session.has_documents = True
                session.document_filename = uploaded_file.name
                session.save()
            except ChatSession.DoesNotExist:
                pass

            result = {
                "answer": _(
                    f"Document '{uploaded_file.name}' uploaded successfully. "
                    f"You can now ask questions about it."
                ),
                "source": "system",
                "session_id": session_id,
                "document_id": upload_data.get("document_id"),
                "document_status": upload_data.get("status", "processing"),
            }

            # If user also asked a question, wait for processing then forward it
            if question:
                doc_id = upload_data.get("document_id")
                try:
                    # Poll until document is processed (max 90s)
                    doc_ready = False
                    for _attempt in range(45):
                        time.sleep(2)
                        try:
                            status_resp = requests.get(
                                f"{FASTAPI_URL}/document_status/{doc_id}",
                                params={"user_id": user_id},
                                headers=get_api_headers(),
                                timeout=10,
                            )
                            if status_resp.ok:
                                status_data = status_resp.json()
                                if status_data.get("status") == "completed":
                                    doc_ready = True
                                    break
                                elif status_data.get("status") == "failed":
                                    break
                        except requests.RequestException:
                            pass

                    if not doc_ready:
                        result["answer"] = _(
                            "Document uploaded. It's still being processed — "
                            "please ask your question again in a few seconds."
                        )
                    else:
                        save_message(session_id, "user", question)
                        ask_resp = requests.post(
                            f"{FASTAPI_URL}/ask_document",
                            json={
                                "question": question,
                                "session_id": session_id,
                                "user_id": user_id,
                                "document_ids": [doc_id] if doc_id else None,
                            },
                            headers=get_api_headers(),
                            timeout=CHATBOT_TIMEOUT,
                        )
                        ask_resp.raise_for_status()
                        ask_data = ask_resp.json()
                        # Return ONLY the document answer (not the upload confirmation)
                        if ask_data.get("answer"):
                            result["answer"] = ask_data["answer"]
                            result["source"] = ask_data.get("source", "document")
                            result["lang"] = ask_data.get("lang", "en")
                            save_message(
                                session_id,
                                "bot",
                                ask_data["answer"],
                                source="document",
                                language=ask_data.get("lang", "en"),
                            )
                except requests.RequestException as e:
                    logger.error(f"Ask document error: {e}")
                    result["answer"] = _(
                        "Document uploaded but the question failed. Please try asking again."
                    )

            title_seed = question or uploaded_file.name
            _auto_title_session(session_id, title_seed)

            return JsonResponse(result)

        # ----- Mode: ask_document -----
        elif mode == "ask_document":
            if not question:
                return JsonResponse(
                    {
                        "error": _("Please type a question about the document."),
                        "source": "error",
                    },
                    status=400,
                )
            save_message(session_id, "user", question)

            # Wait for any pending documents to finish processing
            try:
                docs_resp = requests.get(
                    f"{FASTAPI_URL}/documents/{session_id}",
                    params={"user_id": user_id},
                    headers=get_api_headers(),
                    timeout=10,
                )
                if docs_resp.ok:
                    docs_data = docs_resp.json()
                    pending_docs = [
                        d
                        for d in docs_data.get("documents", [])
                        if d.get("status") in ("pending", "processing")
                    ]
                    if pending_docs:
                        # Poll until all docs are processed (max 120s)
                        for _attempt in range(60):
                            time.sleep(2)
                            try:
                                check = requests.get(
                                    f"{FASTAPI_URL}/documents/{session_id}",
                                    params={"user_id": user_id},
                                    headers=get_api_headers(),
                                    timeout=10,
                                )
                                if check.ok:
                                    check_data = check.json()
                                    still_pending = [
                                        d
                                        for d in check_data.get("documents", [])
                                        if d.get("status") in ("pending", "processing")
                                    ]
                                    if not still_pending:
                                        break
                            except requests.RequestException:
                                pass
            except requests.RequestException:
                pass

            # Build document filter — document_ids (list) takes precedence
            effective_question = _inject_context_into_question(question, context_prompt)
            doc_ids = data.get("document_ids")  # list from frontend
            single_id = data.get("document_id")  # legacy single ID
            ask_payload = {
                "question": effective_question,
                "session_id": session_id,
                "user_id": user_id,
            }
            if doc_ids:
                ask_payload["document_ids"] = doc_ids
            elif single_id:
                ask_payload["document_id"] = single_id

            resp = requests.post(
                f"{FASTAPI_URL}/ask_document",
                json=ask_payload,
                headers=get_api_headers(),
                timeout=CHATBOT_TIMEOUT,
            )
            resp.raise_for_status()
            response_data = resp.json()

            if response_data.get("answer"):
                save_message(
                    session_id,
                    "bot",
                    response_data["answer"],
                    source="document",
                    language=response_data.get("lang", "en"),
                )

            response_data["session_id"] = session_id
            response_data["context_applied"] = bool(context_prompt)
            response_data["context_metadata"] = context_metadata
            _auto_title_session(session_id, question)
            return JsonResponse(response_data)

        # ----- Mode: web (user-triggered web search via Tavily) -----
        elif mode == "web":
            if not question:
                return JsonResponse(
                    {
                        "error": _("Please type a question to search the web."),
                        "source": "error",
                    },
                    status=400,
                )

            save_message(session_id, "user", question)

            resp = requests.post(
                f"{FASTAPI_URL}/web/search",
                json={
                    "question": question,
                    "session_id": session_id,
                },
                headers=get_api_headers(),
                timeout=CHATBOT_TIMEOUT,
            )
            resp.raise_for_status()
            web_data = resp.json()

            # Build response with web source info
            answer = web_data.get("answer", "")
            source_urls = web_data.get("source_urls", [])
            results = web_data.get("results", [])

            # Format answer with source citations if available
            if answer and source_urls:
                citation_lines = "\n\n**Sources:**\n"
                for i, r in enumerate(results[:5], 1):
                    title = r.get("title", r.get("url", ""))
                    url = r.get("url", "")
                    if url:
                        citation_lines += f"{i}. [{title}]({url})\n"
                answer += citation_lines

            if answer:
                save_message(
                    session_id,
                    "bot",
                    answer,
                    source="web",
                    language="en",
                )
            if results:
                save_web_results(session_id, results, source_urls, language="en")

            result = {
                "answer": answer,
                "source": "web_tavily",
                "session_id": session_id,
                "web_results": results,
                "source_urls": source_urls,
                "response_time": web_data.get("response_time", 0),
            }
            _auto_title_session(session_id, question)
            return JsonResponse(result)

        else:
            return JsonResponse(
                {"error": _("Unknown mode."), "source": "error"}, status=400
            )

    except requests.exceptions.HTTPError as e:
        error_detail = ""
        try:
            error_detail = e.response.json().get("detail", e.response.text[:200])
        except (ValueError, AttributeError):
            error_detail = getattr(e.response, "text", str(e))[:200]
        logger.error(
            f"FastAPI HTTP Error {getattr(e.response, 'status_code', '?')}: {error_detail}"
        )
        return JsonResponse(
            {
                "error": _(
                    "An error occurred processing your request. Please try again."
                ),
                "source": "error",
            },
            status=500,
        )

    except requests.exceptions.Timeout:
        logger.error("FastAPI request timeout")
        return JsonResponse(
            {
                "error": _("Request timeout. Please try again."),
                "source": "error",
            },
            status=504,
        )

    except requests.exceptions.RequestException as e:
        logger.error(f"FastAPI connection error: {e}")
        return JsonResponse(
            {
                "error": _(
                    "Unable to connect to the chatbot service. Please try again later."
                ),
                "source": "error",
            },
            status=503,
        )

    except json.JSONDecodeError:
        return JsonResponse(
            {"error": _("Invalid request format."), "source": "error"}, status=400
        )

    except Exception as e:
        logger.exception(f"Unexpected error in chatbot: {e}")
        return JsonResponse(
            {
                "error": _("An unexpected error occurred. Please try again."),
                "source": "error",
            },
            status=500,
        )


@csrf_exempt
@require_http_methods(["POST"])
def ask_bot_stream(request):
    """Stream response (SSE) — supports conversation, web, and platform modes."""
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": _("Authentication required"), "source": "error"}, status=401
        )

    allowed, remaining = check_rate_limit(request.user.id)
    if not allowed:
        return JsonResponse(
            {
                "error": _("Too many requests. Please wait a moment."),
                "source": "error",
            },
            status=429,
        )

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse(
            {"error": _("Invalid request format."), "source": "error"}, status=400
        )

    mode = data.get("mode", "conversation")
    question = data.get("question", "").strip()
    session_id = data.get("session_id", "")
    user_id = _get_user_id(request.user)
    context_prompt = ""
    context_metadata = {}

    payload_context = data.get("context")
    if isinstance(payload_context, dict):
        context_prompt = _build_card_context_prompt(payload_context)
        context_metadata = payload_context
    else:
        context_prompt, context_metadata = _get_request_content_context(request)

    request.session.pop("chatbot_card_context", None)
    request.session.pop("chatbot_context_prompt", None)
    request.session.modified = True

    try:
        if not session_id:
            session_id = _create_fastapi_session(request.user)
    except requests.exceptions.RequestException as e:
        logger.error("FastAPI unreachable for session creation: %s", e)
        return JsonResponse(
            {
                "error": _(
                    "Chatbot service is temporarily unavailable. Please try again in a moment."
                ),
                "source": "error",
            },
            status=503,
        )

    user_profile = _build_user_profile(request.user)

    if not question:
        return JsonResponse(
            {"error": _("Please type a message."), "source": "error"},
            status=400,
        )

    # ----- Mode: web (Tavily streaming) -----
    if mode == "web":
        save_message(session_id, "user", question)
        _auto_title_session(session_id, question)

        def web_stream_generator():
            try:
                resp = requests.post(
                    f"{FASTAPI_URL}/web/search/stream",
                    json={
                        "question": question,
                        "session_id": session_id,
                    },
                    headers=get_api_headers(),
                    stream=True,
                    timeout=CHATBOT_TIMEOUT,
                )
                resp.raise_for_status()

                full_answer = ""
                final_payload = None
                for line in resp.iter_lines(chunk_size=1):
                    if line:
                        decoded = line.decode("utf-8", errors="replace")
                        if decoded.startswith("data: "):
                            try:
                                obj = json.loads(decoded[6:])
                                if obj.get("done") and obj.get("answer"):
                                    full_answer = obj["answer"]
                                    final_payload = obj
                            except (json.JSONDecodeError, TypeError):
                                pass
                        yield line + b"\n\n"

                if full_answer:
                    save_message(
                        session_id, "bot", full_answer,
                        source="web", language="en",
                    )
                if final_payload and isinstance(final_payload.get("web_results"), list):
                    save_web_results(
                        session_id,
                        final_payload.get("web_results") or [],
                        final_payload.get("source_urls") or [],
                        language="en",
                    )

            except requests.exceptions.RequestException as e:
                logger.error("Web stream error: %s", e)
                err_msg = _(
                    "Web search is temporarily unavailable. Please try again."
                )
                yield f"data: {json.dumps({'error': err_msg})}\n\n".encode("utf-8")

        response = StreamingHttpResponse(
            web_stream_generator(),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response

    # ----- Mode: platform (streaming) -----
    if mode == "platform":
        save_message(session_id, "user", question)
        _auto_title_session(session_id, question)

        def platform_stream_generator():
            try:
                resp = requests.post(
                    f"{FASTAPI_URL}/platform/search",
                    json={
                        "query": question,
                        "resource_type": data.get("resource_type"),
                        "language": data.get("language"),
                        "limit": 10,
                    },
                    headers=get_api_headers(),
                    timeout=CHATBOT_TIMEOUT,
                )
                resp.raise_for_status()
                platform_data = resp.json()

                results = platform_data.get("results", [])
                total = platform_data.get("total", len(results))

                # Build a summary message to stream
                if results:
                    result_types = {}
                    for r in results:
                        t = r.get("type", "item")
                        result_types[t] = result_types.get(t, 0) + 1

                    summary_parts = []
                    for t, count in result_types.items():
                        summary_parts.append(f"{count} {t}{'s' if count > 1 else ''}")
                    summary = f"Found {total} results: " + ", ".join(summary_parts) + "."
                else:
                    summary = "No results found for your search."

                # Stream the summary
                words = summary.split(" ")
                chunk_size = 3
                for i in range(0, len(words), chunk_size):
                    chunk = " ".join(words[i:i + chunk_size])
                    if i > 0:
                        chunk = " " + chunk
                    yield f"data: {json.dumps({'delta': chunk})}\n\n".encode("utf-8")

                if summary:
                    save_message(
                        session_id, "bot", summary,
                        source="platform", language="en",
                    )

                # Send final event with full platform data
                platform_data["session_id"] = session_id
                yield f"data: {json.dumps({'done': True, 'answer': summary, 'source': 'platform', 'session_id': session_id, 'platform_results': results, 'total': total})}\n\n".encode("utf-8")

            except requests.exceptions.RequestException as e:
                logger.error("Platform stream error: %s", e)
                err_msg = _(
                    "Platform search is temporarily unavailable. Please try again."
                )
                yield f"data: {json.dumps({'error': err_msg})}\n\n".encode("utf-8")

        response = StreamingHttpResponse(
            platform_stream_generator(),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response

    # ----- Mode: conversation (original streaming) -----
    # Phase 6: accept chatbot_mode for mode-aware routing, but only
    # for the conversation stream (web/platform have their own paths)
    chatbot_mode = data.get("chatbot_mode")  # nlp_ai | legal | platform | None
    if mode != "conversation":
        return JsonResponse(
            {"error": _("Streaming is only available for conversation, web, and platform modes."), "source": "error"},
            status=400,
        )

    if question:
        save_message(session_id, "user", question)
        _auto_title_session(session_id, question)

    effective_question = _inject_context_into_question(question, context_prompt)

    def stream_generator():
        full_answer = ""
        sse_buffer = ""
        done_payload = None

        def _consume_sse_and_capture(chunk_bytes):
            nonlocal sse_buffer, full_answer, done_payload
            try:
                sse_buffer += chunk_bytes.decode("utf-8", errors="replace")
            except Exception:
                return
            events = re.split(r"\r?\n\r?\n", sse_buffer)
            sse_buffer = events.pop() if events else ""
            for evt in events:
                if not evt:
                    continue
                m = re.search(r"^data:\s*(.+)$", evt, re.MULTILINE)
                if not m:
                    continue
                try:
                    obj = json.loads(m.group(1))
                except (TypeError, ValueError):
                    continue
                delta = obj.get("delta")
                if isinstance(delta, str):
                    full_answer += delta
                if obj.get("done"):
                    done_payload = obj

        try:
            resp = requests.post(
                f"{FASTAPI_URL}/conversation/stream",
                json={
                    "question": effective_question,
                    "session_id": session_id,
                    "user_id": user_id,
                    "max_history": CHATBOT_MAX_HISTORY,
                    "max_tokens": min(CHATBOT_MAX_TOKENS, 8192),
                    **({
                        "mode": chatbot_mode,
                    } if chatbot_mode else {}),
                    **user_profile,
                },
                headers=get_api_headers(),
                stream=True,
                timeout=CHATBOT_TIMEOUT,
            )
            resp.raise_for_status()
            for chunk in resp.iter_content(chunk_size=None):
                if chunk:
                    _consume_sse_and_capture(chunk)
                    yield chunk
            if done_payload and isinstance(done_payload.get("answer"), str) and done_payload.get("answer").strip():
                full_answer = done_payload.get("answer").strip()
            if full_answer.strip():
                save_message(
                    session_id,
                    "bot",
                    full_answer.strip(),
                    source=(done_payload or {}).get("source", "bot"),
                    language=(done_payload or {}).get("lang", "en"),
                )
        except requests.exceptions.RequestException as e:
            logger.error("Stream proxy error: %s", e)
            err_msg = _(
                "Chatbot service is temporarily unavailable. Please try again in a moment."
            )
            yield f"data: {json.dumps({'error': err_msg})}\n\n".encode("utf-8")

    response = StreamingHttpResponse(
        stream_generator(),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def set_card_context(request):
    """
    Store the currently selected card/resource context in user session.
    This is used by the chatbot bridge from cards without reloading the page.
    """
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": _("Invalid request format.")}, status=400)

    # Accept both {"context": {...}} and flat payload {...}
    raw_context = payload.get("context") if isinstance(payload.get("context"), dict) else payload
    if isinstance(raw_context, str):
        try:
            raw_context = json.loads(raw_context)
        except json.JSONDecodeError:
            raw_context = {"title": raw_context}

    if not isinstance(raw_context, dict):
        return JsonResponse({"ok": False, "error": _("Invalid context payload.")}, status=400)

    context = {
        "title": str(raw_context.get("title", "")).strip()[:500],
        "author": str(raw_context.get("author", "")).strip()[:255],
        "category": str(raw_context.get("category", "")).strip()[:255],
        "description": str(raw_context.get("description", "")).strip()[:2000],
        "type": str(raw_context.get("type", "")).strip()[:100],
        "id": str(raw_context.get("id", "")).strip()[:255],
        "url": str(raw_context.get("url", "")).strip()[:1000],
    }

    request.session["chatbot_card_context"] = context
    request.session["chatbot_context_prompt"] = _build_card_context_prompt(context)
    request.session.modified = True
    return JsonResponse({"ok": True, "context": context})


def _build_user_profile(user):
    """Serialize the current user's profile for the LLM context."""
    profile = {}
    name = (
        getattr(user, "full_name_en", "")
        or getattr(user, "full_name_ar", "")
        or getattr(user, "full_name", "")
        or ""
    )
    if name:
        profile["user_name"] = name
    email = getattr(user, "email", "")
    if email:
        profile["user_email"] = email
    bio = (
        getattr(user, "bio_en", "")
        or getattr(user, "bio_ar", "")
        or getattr(user, "bio", "")
        or ""
    )
    if bio:
        profile["user_bio"] = bio[:500]
    institution = getattr(user, "institution", None)
    if institution:
        inst_name = (
            getattr(institution, "name_en", "")
            or getattr(institution, "name_ar", "")
            or getattr(institution, "name", "")
        )
        if inst_name:
            profile["user_institution"] = inst_name
    speciality = getattr(user, "speciality", "")
    if speciality:
        profile["user_speciality"] = speciality.replace("_", " ").title()
    country = getattr(user, "country", None) or ""
    if country:
        profile["user_country"] = str(country)
    city = getattr(user, "city", None) or ""
    if city:
        profile["user_city"] = str(city)
    return profile


def _auto_title_session(session_id, question):
    """Auto-set session title from first question if untitled."""
    try:
        session = ChatSession.objects.get(fastapi_session_id=session_id)
        seed = (question or "").strip()
        if not session.title and seed:
            session.title = seed[:100]
            session.save()
    except ChatSession.DoesNotExist:
        pass
