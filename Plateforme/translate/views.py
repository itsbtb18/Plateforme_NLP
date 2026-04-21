

import json
import re

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect
from django.utils import translation
from django.conf import settings
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST


# ── Language switcher (legacy, untouched) ──────────────────────

def switch_language(request):
    lang_code = request.GET.get('language')
    next_url = request.META.get('HTTP_REFERER', '/')

    if lang_code in dict(settings.LANGUAGES).keys():
        translation.activate(lang_code)

        # Replace the language prefix in the URL so i18n_patterns picks up the new language
        lang_codes = '|'.join(dict(settings.LANGUAGES).keys())
        next_url = re.sub(r'^(https?://[^/]+)?/(' + lang_codes + r')/', r'\1/' + lang_code + '/', next_url)

        response = HttpResponseRedirect(next_url)

        if hasattr(request, 'session'):
            request.session[settings.LANGUAGE_COOKIE_NAME] = lang_code

        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang_code)

        return response

    return HttpResponseRedirect(next_url)


# ── Translation / Summarization proxy API ──────────────────────

def _safe_text(value, max_len: int = 50_000) -> str:
    return str(value or "").strip()[:max_len]


@login_required
@require_POST
@csrf_protect
def api_translate(request):
    """POST /api/ts/translate/

    Body (JSON):
        text              – source text (required, min 1 char)
        source_language   – e.g. "en", "fr"  (required)
        target_language   – e.g. "ar"         (required)

    Returns JSON from the TS micro-service.
    """
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON."}, status=400)

    text = _safe_text(payload.get("text"))
    source_language = _safe_text(payload.get("source_language"), 10)
    target_language = _safe_text(payload.get("target_language"), 10)

    if not text:
        return JsonResponse({"ok": False, "error": "text is required."}, status=400)
    if not source_language or not target_language:
        return JsonResponse(
            {"ok": False, "error": "source_language and target_language are required."},
            status=400,
        )

    from translate.ts_client import ts_translate

    try:
        result = ts_translate(text, source_language, target_language)
    except RuntimeError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=502)

    return JsonResponse({"ok": True, **result})


@login_required
@require_POST
@csrf_protect
def api_summarize(request):
    """POST /api/ts/summarize/

    Body (JSON):
        text       – text to summarize (required, min 1 char)
        language   – e.g. "en", "ar"   (default "en")
        style      – "brief" | "detailed" (default "brief")
        max_words  – optional int 20..2000

    Returns JSON from the TS micro-service.
    """
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON."}, status=400)

    text = _safe_text(payload.get("text"))
    language = _safe_text(payload.get("language"), 10) or "en"
    style = _safe_text(payload.get("style"), 20) or "brief"
    max_words = payload.get("max_words")

    if not text:
        return JsonResponse({"ok": False, "error": "text is required."}, status=400)

    if max_words is not None:
        try:
            max_words = int(max_words)
            if max_words < 20 or max_words > 2000:
                max_words = None
        except (ValueError, TypeError):
            max_words = None

    from translate.ts_client import ts_summarize

    try:
        result = ts_summarize(text, language=language, style=style, max_words=max_words)
    except RuntimeError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=502)

    return JsonResponse({"ok": True, **result})


@login_required
def api_ts_health(request):
    """GET /api/ts/health/ — lightweight availability check."""
    from translate.ts_client import ts_health

    return JsonResponse(ts_health())