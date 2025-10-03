from datetime import datetime
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import requests
from django.contrib.auth.decorators import login_required
import uuid
import json
import os

FASTAPI_URL = os.getenv("FASTAPI_URL", "http://localhost:8000")

@login_required
def chatbot_interface(request):
    session_id = None
    try:
        response = requests.post(f"{FASTAPI_URL}/start_conversation", timeout=10)
        response.raise_for_status()
        session_id = response.json().get("session_id")
    except requests.RequestException as e:
        print(f"Erreur de connexion à FastAPI pour start_conversation: {str(e)}")
        session_id = str(uuid.uuid4())
    return render(request, "chatbot/chatbot.html", context={'session_id': session_id})

@csrf_exempt
@require_http_methods(["POST"])
def ask_bot(request):
    try:
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
            # En mode 'upload', un session_id est indispensable.
            if not session_id:
                 return JsonResponse({"error": "Session ID manquant pour le mode upload.", "source": "error"}, status=400)

            upload_success_message = ""

            if pdf_file: # Traitement s'il y a un nouveau fichier PDF
                if pdf_file.size > 10 * 1024 * 1024: # 10MB max
                    return JsonResponse({"error": "Fichier trop volumineux (max 10MB).", "source": "error"}, status=400)
                if not pdf_file.name.lower().endswith('.pdf') or pdf_file.content_type != 'application/pdf':
                    return JsonResponse({"error": "Type de fichier invalide, PDF attendu.", "source": "error"}, status=400)

                files_payload = {'file': (pdf_file.name, pdf_file, 'application/pdf')}
                headers_upload = {'session-id': session_id}
                upload_resp = requests.post(
                    f"{FASTAPI_URL}/upload_pdf",
                    files=files_payload,
                    headers=headers_upload,
                    timeout=300
                )
                upload_resp.raise_for_status()
                upload_json = upload_resp.json()
                upload_success_message = f"PDF '{pdf_file.name}' uploadé avec succès ({upload_json.get('pages', 'N/A')} pages)."
            
            # Après un upload (même si c'est juste une question sur un PDF déjà uploadé sans nouveau fichier)
            # Si une question est posée, la transmettre à FastAPI /ask
            if question and question.strip():
                ask_payload = {"question": question}
                headers_ask = {'session-id': session_id, 'Content-Type': 'application/json'}
                ask_resp = requests.post(
                    f"{FASTAPI_URL}/ask",
                    json=ask_payload,
                    headers=headers_ask,
                    timeout=300
                )
                ask_resp.raise_for_status()
                response_data = ask_resp.json()
                response_data['session_id'] = session_id # Assurer la continuité
                if upload_success_message: # Si un fichier venait d'être uploadé
                    response_data['system_message_after_upload'] = upload_success_message
                return JsonResponse(response_data)
            elif upload_success_message: # Si upload mais pas de question immédiate
                return JsonResponse({
                    "message": upload_success_message + " Vous pouvez maintenant poser des questions à son sujet.",
                    "session_id": session_id,
                    "source": "system"
                })
            else: # Pas de nouveau PDF, pas de question -> erreur ou instruction
                 return JsonResponse({
                    "message": "Veuillez poser une question concernant le PDF précédemment uploadé ou uploader un nouveau PDF.",
                    "session_id": session_id,
                    "source": "system"
                })


        elif mode == 'delete':
            if session_id:
                try:
                    requests.post(f"{FASTAPI_URL}/end_conversation/{session_id}", timeout=60).raise_for_status()
                except requests.RequestException as e:
                    print(f"Warning: Échec de la terminaison de la session {session_id}: {str(e)}")
            new_session_resp = requests.post(f"{FASTAPI_URL}/start_conversation", timeout=60)
            new_session_resp.raise_for_status()
            new_session_id = new_session_resp.json()['session_id']
            initial_question = question.strip() if question.strip() else "Bonjour"
            conv_payload = {"question": initial_question, "session_id": new_session_id, "max_history": 20, "max_tokens": 24000}
            conv_resp = requests.post(f"{FASTAPI_URL}/conversation", json=conv_payload, headers={'Content-Type': 'application/json'}, timeout=300)
            conv_resp.raise_for_status()
            return JsonResponse(conv_resp.json())

        elif mode == 'quick':
            if not question or not question.strip():
                return JsonResponse({"error": "Question manquante pour le mode Quick Question.", "source": "error"}, status=400)
            quick_payload = {"question": question}
            resp = requests.post(f"{FASTAPI_URL}/query", json=quick_payload, headers={'Content-Type': 'application/json'}, timeout=300)
            resp.raise_for_status()
            return JsonResponse(resp.json())

        else: # mode == 'conversation'
            if not question or not question.strip():
                return JsonResponse({"error": "Question manquante pour la conversation.", "source": "error"}, status=400)
            if not session_id:
                new_session_resp = requests.post(f"{FASTAPI_URL}/start_conversation", timeout=60)
                new_session_resp.raise_for_status()
                session_id = new_session_resp.json()['session_id']
            conv_payload = {"question": question, "session_id": session_id, "max_history": 20, "max_tokens": 24000}
            conv_resp = requests.post(f"{FASTAPI_URL}/conversation", json=conv_payload, headers={'Content-Type': 'application/json'}, timeout=300)
            conv_resp.raise_for_status()
            return JsonResponse(conv_resp.json())

    except requests.exceptions.HTTPError as e:
        error_message = f"Erreur API: {e.response.status_code}"
        try: error_detail = e.response.json().get("detail", e.response.text); error_message += f" - {error_detail}"
        except ValueError: error_message += f" - {e.response.text[:200]}"
        print(f"ERROR: {error_message}")
        return JsonResponse({"error": error_message, "source": "error"}, status=e.response.status_code if e.response is not None else 00)
    except requests.exceptions.RequestException as e:
        error_msg = f"Erreur de connexion API: {str(e)}"; print(f"ERROR: {error_msg}")
        return JsonResponse({"error": error_msg, "source": "error"}, status=503)
    except json.JSONDecodeError as e:
        error_msg = f"Erreur JSON Req: {str(e)}"; print(f"ERROR: {error_msg}")
        return JsonResponse({"error": error_msg, "source": "error"}, status=400)
    except Exception as e:
        error_msg = f"Erreur Interne Django: {str(e)}"; print(f"ERROR: {error_msg}")
        return JsonResponse({"error": error_msg, "source": "error"}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def start_new_session(request):
    try:
        response = requests.post(f"{FASTAPI_URL}/start_conversation", timeout=10)
        response.raise_for_status()
        return JsonResponse({"session_id": response.json()["session_id"], "timestamp": datetime.now().isoformat()})
    except requests.exceptions.RequestException as e:
        print(f"Erreur start_new_session (FastAPI): {str(e)}")
        return JsonResponse({"error": str(e), "source": "error"}, status=503)