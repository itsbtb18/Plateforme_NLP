


# --------------------------
# CV Extraction Proxy (for Signup Auto-fill)
# --------------------------

import logging
import os
import re
import unicodedata
from json import JSONDecodeError

import json

import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

ARABIC_CHAR_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
NAME_TOKEN_RE = re.compile(r"[A-Za-z]+")


NAME_OVERRIDES = {
    "mohamed": "محمد",
    "mohammad": "محمد",
    "muhammad": "محمد",
    "ahmed": "أحمد",
    "ahmad": "أحمد",
    "ali": "علي",
    "omar": "عمر",
    "amr": "عمرو",
    "youssef": "يوسف",
    "yusuf": "يوسف",
    "hassan": "حسن",
    "hussein": "حسين",
    "hussain": "حسين",
    "abdullah": "عبدالله",
    "abdallah": "عبدالله",
    "ibrahim": "إبراهيم",
    "ismail": "إسماعيل",
    "ismael": "إسماعيل",
    "khaled": "خالد",
    "khalid": "خالد",
    "faisal": "فيصل",
    "faissal": "فيصل",
    "karim": "كريم",
    "rahman": "رحمن",
    "abdelrahman": "عبدالرحمن",
    "abdurrahman": "عبدالرحمن",
    "john": "جون",
    "jane": "جين",
    "michael": "مايكل",
    "david": "ديفيد",
    "robert": "روبرت",
    "sarah": "سارة",
    "maria": "ماريا",
    "anna": "آنا",
    "chris": "كريس",
}


MULTI_CHAR_MAP = {
    "sch": "ش",
    "sh": "ش",
    "kh": "خ",
    "th": "ث",
    "dh": "ذ",
    "gh": "غ",
    "ph": "ف",
    "ch": "تش",
    "ck": "ك",
    "qu": "كو",
    "aa": "ا",
    "ee": "ي",
    "oo": "و",
    "ou": "و",
    "ai": "اي",
    "ay": "اي",
    "ei": "اي",
    "ey": "اي",
    "ow": "او",
    "aw": "او",
}


SINGLE_CHAR_MAP = {
    "a": "ا",
    "b": "ب",
    "c": "ك",
    "d": "د",
    "e": "ي",
    "f": "ف",
    "g": "ج",
    "h": "ه",
    "i": "ي",
    "j": "ج",
    "k": "ك",
    "l": "ل",
    "m": "م",
    "n": "ن",
    "o": "و",
    "p": "ب",
    "q": "ق",
    "r": "ر",
    "s": "س",
    "t": "ت",
    "u": "و",
    "v": "ف",
    "w": "و",
    "x": "كس",
    "y": "ي",
    "z": "ز",
}


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _contains_arabic(value: str) -> bool:
    return bool(ARABIC_CHAR_RE.search(value or ""))


def _ascii_fold(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def _transliterate_token(token: str) -> str:
    lowered = _ascii_fold(token).lower()
    lowered = re.sub(r"[^a-z]", "", lowered)

    if not lowered:
        return ""

    if lowered in NAME_OVERRIDES:
        return NAME_OVERRIDES[lowered]

    out = []
    i = 0
    while i < len(lowered):
        matched = False
        for size in (3, 2):
            if i + size <= len(lowered):
                piece = lowered[i:i + size]
                mapped = MULTI_CHAR_MAP.get(piece)
                if mapped:
                    out.append(mapped)
                    i += size
                    matched = True
                    break

        if matched:
            continue

        out.append(SINGLE_CHAR_MAP.get(lowered[i], lowered[i]))
        i += 1

    transliterated = "".join(out)
    transliterated = re.sub(r"(.)\1{2,}", r"\1\1", transliterated)
    return transliterated


def _transliterate_full_name(full_name_en: str) -> str:
    parts = NAME_TOKEN_RE.findall(full_name_en or "")
    transliterated_parts = [_transliterate_token(part) for part in parts]
    transliterated_parts = [part for part in transliterated_parts if part]
    return " ".join(transliterated_parts)


@require_POST
@csrf_exempt
def extract_cv_signup(request):
    """
    Proxy endpoint to extract CV information.
    Relays file upload to FastAPI service and returns structured CV data.

    This avoids CORS issues by routing through Django.
    """
    if "file" not in request.FILES:
        return JsonResponse({"detail": "No file provided"}, status=400)

    file = request.FILES["file"]

    allowed_mimetypes = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }

    if file.content_type not in allowed_mimetypes:
        return JsonResponse(
            {"detail": "Invalid file type. Allowed: PDF, DOCX"},
            status=400,
        )

    max_size = 20 * 1024 * 1024
    if file.size > max_size:
        return JsonResponse(
            {"detail": "File too large. Maximum size: 20MB"},
            status=413,
        )

    file_bytes = file.read()
    if not file_bytes:
        return JsonResponse({"detail": "Uploaded file is empty"}, status=400)

    configured_host = os.getenv("CV_PROCESSING_HOST", "").rstrip("/")
    service_bases = []

    if configured_host:
        service_bases.append(configured_host)

    service_bases.extend(
        [
            "http://cv_processing:8002",
            "http://localhost:8002",
            "http://127.0.0.1:8002",
        ]
    )

    endpoint_suffixes = ["/extract-cv-sync/", "/extract-cv-signup/"]

    last_error = None

    for base_url in service_bases:
        for suffix in endpoint_suffixes:
            url = f"{base_url}{suffix}"

            try:
                logger.info("Trying CV Processing endpoint: %s", url)

                upstream_response = requests.post(
                    url,
                    files={
                        "file": (
                            file.name,
                            file_bytes,
                            file.content_type,
                        )
                    },
                    timeout=60,
                    headers={"Accept": "application/json"},
                )

                raw_body = (upstream_response.text or "").strip()

                if not upstream_response.ok:
                    last_error = (
                        f"Status {upstream_response.status_code}: "
                        f"{raw_body or '[empty response body]'}"
                    )
                    logger.warning("CV Processing endpoint returned error: %s", last_error)

                    # If the upstream service is reachable but failed (5xx),
                    # return that error immediately instead of masking it with
                    # later fallback connection errors.
                    if upstream_response.status_code >= 500:
                        upstream_detail = None
                        try:
                            upstream_json = upstream_response.json()
                            upstream_detail = upstream_json.get("detail") if isinstance(upstream_json, dict) else None
                        except ValueError:
                            upstream_detail = None

                        return JsonResponse(
                            {
                                "detail": upstream_detail or raw_body or "CV processing failed",
                                "error": "UPSTREAM_PROCESSING_ERROR",
                            },
                            status=upstream_response.status_code,
                        )

                    continue

                if not raw_body:
                    last_error = f"Status 200 with empty body from {url}"
                    logger.warning(last_error)
                    continue

                try:
                    payload = upstream_response.json()
                except ValueError:
                    last_error = f"Status 200 with invalid JSON from {url}: {raw_body[:300]}"
                    logger.warning(last_error)
                    continue

                logger.info("Success with CV Processing endpoint: %s", url)
                return JsonResponse(payload, safe=isinstance(payload, dict))

            except requests.exceptions.ConnectionError as exc:
                last_error = f"Connection error: {exc}"
                logger.warning("CV Processing endpoint %s connection failed: %s", url, last_error)
            except requests.exceptions.Timeout as exc:
                last_error = f"Timeout: {exc}"
                logger.warning("CV Processing endpoint %s timed out: %s", url, last_error)
            except Exception as exc:
                last_error = str(exc)
                logger.exception("CV Processing endpoint %s unexpected error: %s", url, last_error)

    logger.error("All CV Processing endpoints failed. Last error: %s", last_error)
    return JsonResponse(
        {
            "detail": f"CV Processing service is unavailable. Error: {last_error}",
            "error": "SERVICE_UNAVAILABLE"
        },
        status=503
    )


@require_POST
@csrf_exempt
def transliterate_name_ar(request):
    """
    Transliterate a full name from Latin script into Arabic script.

    This endpoint is intentionally additive and isolated from signup logic.
    """
    full_name_en = ""

    if request.content_type and "application/json" in request.content_type:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"detail": "Invalid JSON payload"}, status=400)
        full_name_en = _normalize_spaces(str(payload.get("full_name_en", "")))
    else:
        full_name_en = _normalize_spaces(request.POST.get("full_name_en", ""))

    if not full_name_en:
        return JsonResponse({"detail": "full_name_en is required"}, status=400)

    if len(full_name_en) < 2:
        return JsonResponse({"detail": "Name is too short"}, status=400)

    if _contains_arabic(full_name_en):
        return JsonResponse(
            {
                "full_name_ar": full_name_en,
                "confidence": "high",
                "source": "passthrough",
            }
        )

    full_name_ar = _transliterate_full_name(full_name_en)

    if not full_name_ar or not _contains_arabic(full_name_ar):
        return JsonResponse(
            {
                "full_name_ar": "",
                "confidence": "none",
                "source": "manual_required",
                "detail": "Unable to transliterate automatically",
            },
            status=200,
        )

    return JsonResponse(
        {
            "full_name_ar": full_name_ar,
            "confidence": "medium",
            "source": "rule_based",
        }
    )
