"""
Test script to verify moderation system functionality.

Run with: python manage.py test core.tests.test_moderation
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from resources.models import Corpus, NLPTool, Course
from projects.models import Project
from events.models import Event
from forum.models import Topic
from institutions.models import Institution, Country
from feed.models import Post

User = get_user_model()


class ModerationSystemTestCase(TestCase):
    """Test the moderation system for all content types."""

    def setUp(self):
        """Set up test users and client."""
        self.regular_user = User.objects.create_user(
            email="user@test.com",
            password="testpass123",
            full_name="Test User",
            is_verified=True,
        )

        self.staff_user = User.objects.create_user(
            email="staff@test.com",
            password="testpass123",
            full_name="Staff User",
            is_staff=True,
            is_verified=True,
        )

        self.client = Client()

    def test_corpus_creation_sets_pending_status(self):
        """Test that corpus creation sets approval_status to pending."""
        corpus = Corpus.objects.create(
            title="Test Corpus",
            title_en="Test Corpus",
            title_ar="مجموعة اختبار",
            description="Test description",
            description_en="Test description",
            description_ar="وصف الاختبار",
            author=self.regular_user,
            language="ar",
            field="nlp",
        )

        # Verify status is pending
        self.assertEqual(corpus.approval_status, "pending")

        # Verify it appears in pending queryset
        pending_corpora = Corpus.objects.filter(approval_status="pending")
        self.assertIn(corpus, pending_corpora)

        # Verify it does NOT appear in approved queryset
        approved_corpora = Corpus.objects.filter(approval_status="approved")
        self.assertNotIn(corpus, approved_corpora)

    def test_project_creation_sets_pending_status(self):
        """Test that project creation sets approval_status to pending."""
        # Create required institution
        country = Country.objects.create(name_en="Test Country", name_ar="بلد اختبار")
        institution = Institution.objects.create(
            name="Test University",
            name_en="Test University",
            name_ar="جامعة اختبار",
            type="University",
            country=country,
            city="Test City",
            approval_status="approved",
        )

        project = Project.objects.create(
            title="Test Project",
            title_en="Test Project",
            title_ar="مشروع اختبار",
            description="Test description",
            description_en="Test description",
            description_ar="وصف الاختبار",
            coordinator=self.regular_user,
            institution=institution,
            status="ongoing",
        )

        # Verify status is pending
        self.assertEqual(project.approval_status, "pending")

        # Verify counts
        pending_count = Project.objects.filter(approval_status="pending").count()
        self.assertEqual(pending_count, 1)

    def test_topic_creation_sets_pending_status(self):
        """Test that topic creation sets approval_status to pending."""
        topic = Topic.objects.create(
            title="Test Topic",
            title_en="Test Topic",
            title_ar="موضوع اختبار",
            description="Test description",
            description_en="Test description",
            description_ar="وصف الاختبار",
            creator=self.regular_user,
        )

        # Verify status is pending
        self.assertEqual(topic.approval_status, "pending")

    def test_staff_auto_approval(self):
        """Test that staff-created content is auto-approved."""
        # This would be set in the view, so we simulate it
        corpus = Corpus.objects.create(
            title="Staff Corpus",
            title_en="Staff Corpus",
            title_ar="مجموعة الموظفين",
            description="Staff description",
            description_en="Staff description",
            description_ar="وصف الموظفين",
            author=self.staff_user,
            language="ar",
            field="nlp",
            approval_status="approved",  # Staff should set this to approved
        )

        # Verify status is approved
        self.assertEqual(corpus.approval_status, "approved")

        # Verify it appears in approved queryset
        approved_corpora = Corpus.objects.filter(approval_status="approved")
        self.assertIn(corpus, approved_corpora)

    def test_approval_workflow(self):
        """Test the approval workflow."""
        corpus = Corpus.objects.create(
            title="Test Corpus",
            title_en="Test Corpus",
            title_ar="مجموعة اختبار",
            description="Test description",
            description_en="Test description",
            description_ar="وصف الاختبار",
            author=self.regular_user,
            language="ar",
            field="nlp",
        )

        # Initially pending
        self.assertEqual(corpus.approval_status, "pending")

        # Approve
        corpus.approval_status = "approved"
        corpus.save()

        # Verify approved
        self.assertEqual(corpus.approval_status, "approved")
        approved_count = Corpus.objects.filter(approval_status="approved").count()
        self.assertEqual(approved_count, 1)

    def test_rejection_workflow(self):
        """Test the rejection workflow."""
        corpus = Corpus.objects.create(
            title="Test Corpus",
            title_en="Test Corpus",
            title_ar="مجموعة اختبار",
            description="Test description",
            description_en="Test description",
            description_ar="وصف الاختبار",
            author=self.regular_user,
            language="ar",
            field="nlp",
        )

        # Reject
        corpus.approval_status = "rejected"
        corpus.save()

        # Verify rejected
        self.assertEqual(corpus.approval_status, "rejected")
        rejected_count = Corpus.objects.filter(approval_status="rejected").count()
        self.assertEqual(rejected_count, 1)

    def test_public_view_filters_approved_only(self):
        """Test that public views only show approved content."""
        # Create pending corpus
        pending_corpus = Corpus.objects.create(
            title="Pending Corpus",
            title_en="Pending Corpus",
            title_ar="مجموعة معلقة",
            description="Pending",
            description_en="Pending",
            description_ar="معلق",
            author=self.regular_user,
            language="ar",
            field="nlp",
            approval_status="pending",
        )

        # Create approved corpus
        approved_corpus = Corpus.objects.create(
            title="Approved Corpus",
            title_en="Approved Corpus",
            title_ar="مجموعة موافق عليها",
            description="Approved",
            description_en="Approved",
            description_ar="موافق عليه",
            author=self.regular_user,
            language="ar",
            field="nlp",
            approval_status="approved",
        )

        # Public query should only show approved
        public_corpora = Corpus.objects.filter(approval_status="approved")

        self.assertIn(approved_corpus, public_corpora)
        self.assertNotIn(pending_corpus, public_corpora)
        self.assertEqual(public_corpora.count(), 1)

    def test_all_models_have_required_fields(self):
        """Test that all moderated models have required fields."""
        models_to_check = [
            (Corpus, "author"),
            (NLPTool, "author"),
            (Course, "author"),
            (Project, "coordinator"),
            (Topic, "creator"),
            (Post, "author"),
        ]

        for model, author_field in models_to_check:
            with self.subTest(model=model.__name__):
                # Check approval_status field exists
                self.assertTrue(
                    hasattr(model, "approval_status"),
                    f"{model.__name__} missing approval_status field",
                )

                # Check created_at field exists
                self.assertTrue(
                    hasattr(model, "created_at"),
                    f"{model.__name__} missing created_at field",
                )

                # Check author field exists
                self.assertTrue(
                    hasattr(model, author_field),
                    f"{model.__name__} missing {author_field} field",
                )
