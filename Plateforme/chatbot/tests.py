import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import ChatMessage, ChatSession


class _FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self._payload = payload or {}
        self.status_code = status_code
        self.ok = status_code < 400
        self.text = json.dumps(self._payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.exceptions.HTTPError(response=self)


class _FakeStreamResponse:
    def __init__(self, chunks, status_code=200):
        self._chunks = chunks
        self.status_code = status_code
        self.ok = status_code < 400

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.exceptions.HTTPError(response=self)

    def iter_content(self, chunk_size=None):
        for c in self._chunks:
            yield c


class ChatbotGoalsTests(TestCase):
    def setUp(self):
        self.client = Client()
        user_model = get_user_model()
        username_field = user_model.USERNAME_FIELD
        user_kwargs = {
            username_field: "chatbot-goals-user@example.com",
            "password": "strong-pass-123",
        }
        if username_field != "email":
            user_kwargs["email"] = "chatbot-goals-user@example.com"
        self.user = user_model.objects.create_user(**user_kwargs)
        self.client.login(**{username_field: user_kwargs[username_field], "password": "strong-pass-123"})

    def test_goal_d_list_sessions_only_after_first_user_query(self):
        hidden_session = ChatSession.objects.create(user=self.user, fastapi_session_id="hidden-session")
        visible_session = ChatSession.objects.create(user=self.user, fastapi_session_id="visible-session")
        ChatMessage.objects.create(
            session=visible_session,
            message_type="user",
            content="First real query",
            source="conversation",
            language="en",
        )
        ChatMessage.objects.create(
            session=hidden_session,
            message_type="bot",
            content="System created this session first",
            source="system",
            language="en",
        )

        resp = self.client.get(reverse("chatbot:list_sessions"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        session_ids = [item["session_id"] for item in data["sessions"]]
        self.assertIn("visible-session", session_ids)
        self.assertNotIn("hidden-session", session_ids)

    @patch("chatbot.views.requests.post")
    def test_goal_d_web_mode_saves_user_message_once(self, mock_post):
        def _side_effect(url, *args, **kwargs):
            if url.endswith("/sessions"):
                return _FakeResponse({"session_id": "sid-web-1"})
            if url.endswith("/web/search"):
                return _FakeResponse({"answer": "ok", "source_urls": [], "results": []})
            raise AssertionError(f"Unexpected URL called: {url}")

        mock_post.side_effect = _side_effect

        resp = self.client.post(
            reverse("chatbot:ask"),
            data=json.dumps({"mode": "web", "question": "search this", "session_id": ""}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        session = ChatSession.objects.get(fastapi_session_id="sid-web-1")
        self.assertEqual(session.messages.filter(message_type="user").count(), 1)

    @patch("chatbot.views.requests.post")
    def test_web_mode_persists_results_for_refresh(self, mock_post):
        def _side_effect(url, *args, **kwargs):
            if url.endswith("/sessions"):
                return _FakeResponse({"session_id": "sid-web-refresh"})
            if url.endswith("/web/search"):
                return _FakeResponse(
                    {
                        "answer": "web answer",
                        "source_urls": ["https://example.com/a"],
                        "results": [
                            {
                                "url": "https://example.com/a",
                                "title": "Example A",
                                "content": "Snippet A",
                                "score": 0.92,
                            }
                        ],
                    }
                )
            raise AssertionError(f"Unexpected URL called: {url}")

        mock_post.side_effect = _side_effect
        resp = self.client.post(
            reverse("chatbot:ask"),
            data=json.dumps({"mode": "web", "question": "find source", "session_id": ""}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)

        history_resp = self.client.get(
            reverse("chatbot:session_history", kwargs={"session_id": "sid-web-refresh"})
        )
        self.assertEqual(history_resp.status_code, 200)
        history = history_resp.json()
        web_items = [m for m in history.get("messages", []) if m.get("type") == "web_results"]
        self.assertEqual(len(web_items), 1)
        self.assertEqual(web_items[0]["content"]["results"][0]["url"], "https://example.com/a")

    def test_goal_b_enter_key_handler_exists(self):
        resp = self.client.get(reverse("chatbot:chatbot_interface"))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        self.assertIn("chatInput.addEventListener('keydown'", html)
        self.assertIn("e.key==='Enter'&&!e.shiftKey&&!e.isComposing", html)

    def test_goal_c_reload_keeps_current_session_logic_present(self):
        resp = self.client.get(reverse("chatbot:chatbot_interface"))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        self.assertIn("SESSION_STORAGE_KEY", html)
        self.assertIn("persistCurrentSessionId()", html)
        self.assertIn("getPersistedSessionId()", html)

    def test_ask_ai_entity_flow_uses_platform_entity_mode(self):
        resp = self.client.get(reverse("chatbot:chatbot_interface"))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        self.assertIn("mode:'platform_entity'", html)
        self.assertNotIn(
            "Explain this selected content naturally and comprehensively",
            html,
        )
        # Regression: Ask AI from card must avoid duplicates by checking
        # already-loaded context cards from session history.
        self.assertIn("if(m.type==='context_card') addEntityContextCard(m.content);", html)
        self.assertIn("Reload case: if this card already exists in loaded history", html)

    @patch("chatbot.views.requests.post")
    def test_platform_entity_mode_registers_user_message(self, mock_post):
        def _side_effect(url, *args, **kwargs):
            if url.endswith("/sessions"):
                return _FakeResponse({"session_id": "sid-entity-1"})
            if url.endswith("/platform/entity_explain"):
                return _FakeResponse({"answer": "Entity answer", "source": "platform", "lang": "en"})
            raise AssertionError(f"Unexpected URL called: {url}")

        mock_post.side_effect = _side_effect
        resp = self.client.post(
            reverse("chatbot:ask"),
            data=json.dumps(
                {
                    "mode": "platform_entity",
                    "session_id": "",
                    "entity_context": {"title": "Applied AI Lab", "type": "institution"},
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        session = ChatSession.objects.get(fastapi_session_id="sid-entity-1")
        self.assertEqual(session.messages.filter(message_type="user").count(), 0)
        self.assertEqual(
            session.messages.filter(message_type="system", source="platform_context").count(),
            1,
        )
        self.assertEqual(session.messages.filter(message_type="bot").count(), 1)

    @patch("chatbot.views.requests.post")
    def test_platform_entity_history_restores_context_card(self, mock_post):
        def _side_effect(url, *args, **kwargs):
            if url.endswith("/sessions"):
                return _FakeResponse({"session_id": "sid-entity-ctx"})
            if url.endswith("/platform/entity_explain"):
                return _FakeResponse({"answer": "Entity answer", "source": "platform", "lang": "en"})
            raise AssertionError(f"Unexpected URL called: {url}")

        mock_post.side_effect = _side_effect
        ask_resp = self.client.post(
            reverse("chatbot:ask"),
            data=json.dumps(
                {
                    "mode": "platform_entity",
                    "session_id": "",
                    "entity_context": {
                        "title": "Applied AI Lab",
                        "type": "institution",
                        "description": "AI lab",
                        "category": "University",
                    },
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(ask_resp.status_code, 200)

        history_resp = self.client.get(
            reverse("chatbot:session_history", kwargs={"session_id": "sid-entity-ctx"})
        )
        self.assertEqual(history_resp.status_code, 200)
        history = history_resp.json()
        cards = [m for m in history.get("messages", []) if m.get("type") == "context_card"]
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["content"]["title"], "Applied AI Lab")

    @patch("chatbot.views.requests.post")
    def test_platform_entity_sets_session_title_from_card_title(self, mock_post):
        def _side_effect(url, *args, **kwargs):
            if url.endswith("/sessions"):
                return _FakeResponse({"session_id": "sid-entity-title"})
            if url.endswith("/platform/entity_explain"):
                return _FakeResponse({"answer": "Entity answer", "source": "platform", "lang": "en"})
            raise AssertionError(f"Unexpected URL called: {url}")

        mock_post.side_effect = _side_effect
        resp = self.client.post(
            reverse("chatbot:ask"),
            data=json.dumps(
                {
                    "mode": "platform_entity",
                    "session_id": "",
                    "entity_context": {"title": "AI Conference Series — MENA", "type": "institution"},
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        session = ChatSession.objects.get(fastapi_session_id="sid-entity-title")
        self.assertEqual(session.title, "AI Conference Series — MENA")

    @patch("chatbot.views.requests.post")
    def test_platform_search_sets_session_title_from_query(self, mock_post):
        def _side_effect(url, *args, **kwargs):
            if url.endswith("/sessions"):
                return _FakeResponse({"session_id": "sid-platform-title"})
            if url.endswith("/platform/search"):
                return _FakeResponse({"results": [], "total": 0})
            raise AssertionError(f"Unexpected URL called: {url}")

        mock_post.side_effect = _side_effect
        resp = self.client.post(
            reverse("chatbot:ask"),
            data=json.dumps({"mode": "platform", "question": "find arabic nlp tools", "session_id": ""}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        session = ChatSession.objects.get(fastapi_session_id="sid-platform-title")
        self.assertEqual(session.title, "find arabic nlp tools")

    @patch("chatbot.views.requests.post")
    def test_web_search_sets_session_title_from_query(self, mock_post):
        def _side_effect(url, *args, **kwargs):
            if url.endswith("/sessions"):
                return _FakeResponse({"session_id": "sid-web-title"})
            if url.endswith("/web/search"):
                return _FakeResponse({"answer": "ok", "source_urls": [], "results": []})
            raise AssertionError(f"Unexpected URL called: {url}")

        mock_post.side_effect = _side_effect
        resp = self.client.post(
            reverse("chatbot:ask"),
            data=json.dumps({"mode": "web", "question": "latest arabic llm news", "session_id": ""}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        session = ChatSession.objects.get(fastapi_session_id="sid-web-title")
        self.assertEqual(session.title, "latest arabic llm news")

    @patch("chatbot.views.requests.post")
    def test_upload_sets_session_title_from_filename_when_no_question(self, mock_post):
        def _side_effect(url, *args, **kwargs):
            if url.endswith("/sessions"):
                return _FakeResponse({"session_id": "sid-upload-title"})
            if url.endswith("/upload_document"):
                return _FakeResponse({"document_id": 10, "status": "processing"})
            raise AssertionError(f"Unexpected URL called: {url}")

        mock_post.side_effect = _side_effect

        from django.core.files.uploadedfile import SimpleUploadedFile

        file_obj = SimpleUploadedFile(
            "whitepaper.pdf",
            b"%PDF-1.4 fake content",
            content_type="application/pdf",
        )
        resp = self.client.post(
            reverse("chatbot:ask"),
            data={"mode": "upload", "session_id": "", "file": file_obj, "question": ""},
        )
        self.assertEqual(resp.status_code, 200)
        session = ChatSession.objects.get(fastapi_session_id="sid-upload-title")
        self.assertEqual(session.title, "whitepaper.pdf")

    @patch("chatbot.views.requests.post")
    def test_stream_conversation_persists_assistant_answer(self, mock_post):
        def _side_effect(url, *args, **kwargs):
            if url.endswith("/sessions"):
                return _FakeResponse({"session_id": "sid-stream-1"})
            if url.endswith("/conversation/stream"):
                return _FakeStreamResponse(
                    [
                        b'data: {"delta":"Hello","session_id":"sid-stream-1"}\n\n',
                        b'data: {"done":true,"answer":"Hello world","source":"memory","lang":"en","session_id":"sid-stream-1"}\n\n',
                    ]
                )
            raise AssertionError(f"Unexpected URL called: {url}")

        mock_post.side_effect = _side_effect
        resp = self.client.post(
            reverse("chatbot:ask_stream"),
            data=json.dumps({"mode": "conversation", "question": "translate last answer to arabic", "session_id": ""}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        body = b"".join(resp.streaming_content).decode("utf-8")
        self.assertIn('"done":true', body)
        session = ChatSession.objects.get(fastapi_session_id="sid-stream-1")
        self.assertTrue(
            session.messages.filter(
                message_type="bot",
                content__icontains="Hello world",
            ).exists()
        )


class ChatbotFeatureUpgradeTests(TestCase):
    """
    Tests for the 5 new chatbot features:
    1. Stop generation
    2. Retry
    3. Edit past queries
    4. Pin messages
    5. Syntax highlighting
    """

    def setUp(self):
        self.user = get_user_model().objects.create_user(email="test@example.com", password="123")
        self.client = Client()
        self.client.force_login(self.user)
        self.session = ChatSession.objects.create(user=self.user, fastapi_session_id="ft-sess-1", title="Feature Test")

    def test_frontend_infrastructure_present(self):
        """
        Verify that the chat template contains the CSS and JS structures
        for Stop, Retry, Edit, and Syntax Highlighting.
        """
        resp = self.client.get(reverse("chatbot:chatbot_interface"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")

        # 1. Stop feature
        self.assertIn("is-streaming", content)
        self.assertIn("AbortController", content)
        
        # 2. Retry feature
        self.assertIn("retryLast()", content)
        self.assertIn("retry-btn", content)

        # 3. Edit feature
        self.assertIn("msg-edit-btn", content)

        # 5. Syntax Highlighting
        self.assertIn("highlight.min.js", content)
        self.assertIn("atom-one-dark.min.css", content)
        self.assertIn("highlightCodeBlocks", content)

    def test_toggle_pin_endpoint_works(self):
        """
        Verify the message pinning backend toggles correctly (Feature 4).
        """
        message = ChatMessage.objects.create(
            session=self.session,
            message_type="user",
            content="Pin me please",
            is_pinned=False
        )

        url = reverse("chatbot:toggle_pin", kwargs={"message_id": message.id})
        
        # First toggle: False -> True
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["is_pinned"])
        message.refresh_from_db()
        self.assertTrue(message.is_pinned)

        # Second toggle: True -> False
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["is_pinned"])
        message.refresh_from_db()
        self.assertFalse(message.is_pinned)

    def test_cannot_pin_others_messages(self):
        other_user = get_user_model().objects.create_user(email="other@test.com", password="123")
        other_session = ChatSession.objects.create(user=other_user, fastapi_session_id="other-sess-1")
        other_message = ChatMessage.objects.create(
            session=other_session,
            message_type="user",
            content="Other pin",
            is_pinned=False
        )
        url = reverse("chatbot:toggle_pin", kwargs={"message_id": other_message.id})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 403)

    def test_pin_state_in_session_history(self):
        """
        Verify that is_pinned and message_id are serialized in the history endpoint.
        """
        message = ChatMessage.objects.create(
            session=self.session,
            message_type="bot",
            content="An answer",
            is_pinned=True
        )

        url = reverse("chatbot:session_history", kwargs={"session_id": "ft-sess-1"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        
        messages = data.get("messages", [])
        self.assertEqual(len(messages), 1)
        self.assertTrue(messages[0].get("is_pinned"))
        self.assertEqual(messages[0].get("message_id"), str(message.id))

    def test_toggle_pin_session_endpoint_works(self):
        """
        Verify the session pinning backend toggles correctly (Feature 6).
        """
        self.assertFalse(self.session.is_pinned)
        url = reverse("chatbot:toggle_pin_session", kwargs={"session_id": self.session.fastapi_session_id})
        
        # False -> True
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["is_pinned"])
        self.session.refresh_from_db()
        self.assertTrue(self.session.is_pinned)

        # True -> False
        resp = self.client.post(url)
        self.session.refresh_from_db()
        self.assertFalse(self.session.is_pinned)

    def test_cannot_pin_others_sessions(self):
        other_user = get_user_model().objects.create_user(email="othersess@test.com", password="123")
        other_session = ChatSession.objects.create(user=other_user, fastapi_session_id="other-sess-2")
        url = reverse("chatbot:toggle_pin_session", kwargs={"session_id": other_session.fastapi_session_id})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 403)
