from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser, Follow, Friendship

from .models import Conversation, MAX_CHAT_FILE_SIZE, Message


class DirectMessagesRulesTests(TestCase):
    def setUp(self):
        self.u1 = CustomUser.objects.create_user(email="u1@test.com", password="Pass12345")
        self.u2 = CustomUser.objects.create_user(email="u2@test.com", password="Pass12345")
        self.client.force_login(self.u1)

    def test_start_conversation_without_follow_creates_request(self):
        url = reverse("direct_messages:start_conversation", kwargs={"user_id": self.u2.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Conversation.objects.count(), 1)
        conv = Conversation.objects.first()
        self.assertIsNotNone(conv)
        self.assertEqual(conv.status, Conversation.ConversationStatus.REQUEST)
        self.assertFalse(conv.is_accepted)

    def test_start_conversation_allowed_when_following(self):
        Follow.objects.create(follower=self.u1, following=self.u2)
        url = reverse("direct_messages:start_conversation", kwargs={"user_id": self.u2.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Conversation.objects.count(), 1)
        conv = Conversation.objects.first()
        self.assertIsNotNone(conv)
        self.assertEqual(conv.status, Conversation.ConversationStatus.PRIMARY)
        self.assertTrue(conv.is_accepted)

    def test_start_conversation_blocked_is_forbidden(self):
        Friendship.objects.create(
            requester=self.u1,
            addressee=self.u2,
            status=Friendship.Status.BLOCKED,
        )
        url = reverse("direct_messages:start_conversation", kwargs={"user_id": self.u2.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Conversation.objects.count(), 0)


class DirectMessagesSecurityTests(TestCase):
    def setUp(self):
        self.u1 = CustomUser.objects.create_user(email="a@test.com", password="Pass12345")
        self.u2 = CustomUser.objects.create_user(email="b@test.com", password="Pass12345")
        self.conversation = Conversation.get_or_create_for_users(self.u1, self.u2)

    def test_auto_detect_link_message_type(self):
        msg = Message.objects.create(
            conversation=self.conversation,
            sender=self.u1,
            message_type=Message.MessageType.TEXT,
            content="check https://example.com now",
        )
        self.assertEqual(msg.message_type, Message.MessageType.LINK)

    def test_strip_html_from_message_content(self):
        msg = Message.objects.create(
            conversation=self.conversation,
            sender=self.u1,
            message_type=Message.MessageType.TEXT,
            content="<script>alert(1)</script>Hello",
        )
        self.assertNotIn("<script>", msg.content)
        self.assertIn("Hello", msg.content)

    def test_file_size_limit_5mb(self):
        too_big = SimpleUploadedFile(
            "big.pdf",
            b"x" * (MAX_CHAT_FILE_SIZE + 1),
            content_type="application/pdf",
        )
        msg = Message(
            conversation=self.conversation,
            sender=self.u1,
            message_type=Message.MessageType.FILE,
            file_path=too_big,
        )
        with self.assertRaises(Exception):
            msg.save()

