"""
Management command to test resource creation and database connectivity.
Usage: python manage.py test_resource_creation
"""

from django.core.management.base import BaseCommand
from django.db import connection
from django.contrib.auth import get_user_model
from resources.models import Corpus, NLPTool, Course
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Test database connectivity and resource creation"

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 60))
        self.stdout.write(
            self.style.MIGRATE_HEADING("  RESOURCE CREATION DIAGNOSTIC TEST")
        )
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 60))
        self.stdout.write("")

        # Test 1: Database Connection
        self.test_database_connection()

        # Test 2: User Availability
        user = self.test_user_availability()

        if user:
            # Test 3: Create Test Corpus
            self.test_corpus_creation(user)

            # Test 4: Create Test NLP Tool
            self.test_tool_creation(user)

            # Test 5: Create Test Course
            self.test_course_creation(user)

        # Test 6: Query Test
        self.test_query_resources()

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("  All tests completed!"))
        self.stdout.write(self.style.SUCCESS("=" * 60))

    def test_database_connection(self):
        """Test 1: Verify database connection"""
        self.stdout.write(self.style.MIGRATE_LABEL("\n[TEST 1] Database Connection"))
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                if result[0] == 1:
                    self.stdout.write(
                        self.style.SUCCESS("  ✓ Database connection is working")
                    )
                    self.stdout.write(f"  Database: {connection.settings_dict['NAME']}")
                else:
                    self.stdout.write(
                        self.style.ERROR("  ✗ Database connection test failed")
                    )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"  ✗ Database connection error: {str(e)}")
            )

    def test_user_availability(self):
        """Test 2: Check if we have a user to test with"""
        self.stdout.write(self.style.MIGRATE_LABEL("\n[TEST 2] User Availability"))
        try:
            user = User.objects.filter(is_staff=True).first()
            if not user:
                user = User.objects.first()

            if user:
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ Test user found: {user.email}")
                )
                return user
            else:
                self.stdout.write(self.style.ERROR("  ✗ No users found in database"))
                return None
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Error finding user: {str(e)}"))
            return None

    def test_corpus_creation(self, user):
        """Test 3: Try to create a corpus"""
        self.stdout.write(self.style.MIGRATE_LABEL("\n[TEST 3] Corpus Creation"))
        try:
            # Temporarily disable signals to avoid Elasticsearch issues
            from django.db.models.signals import post_save
            from resources.models import index_resource

            post_save.disconnect(index_resource, sender=Corpus)

            corpus = Corpus.objects.create(
                title="Test Corpus DEBUG",
                title_en="Test Corpus DEBUG",
                title_ar="مجموعة اختبار",
                description="This is a test corpus for debugging",
                description_en="This is a test corpus for debugging",
                description_ar="هذه مجموعة اختبار للتحليل",
                author=user,
                field="nlp",
                language="ar",
                keywords="test,debug",
                approval_status="pending",
                is_approved=False,
            )

            # Reconnect signal
            post_save.connect(index_resource, sender=Corpus)

            self.stdout.write(
                self.style.SUCCESS(f"  ✓ Corpus created successfully (ID: {corpus.id})")
            )
            self.stdout.write(f"  Title: {corpus.title}")
            self.stdout.write(f"  Status: {corpus.approval_status}")
            self.stdout.write(f"  Author: {corpus.author.email}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Corpus creation failed: {str(e)}"))
            import traceback

            self.stdout.write(
                self.style.ERROR(f"  Stack trace:\n{traceback.format_exc()}")
            )

    def test_tool_creation(self, user):
        """Test 4: Try to create an NLP tool"""
        self.stdout.write(self.style.MIGRATE_LABEL("\n[TEST 4] NLP Tool Creation"))
        try:
            # Temporarily disable signals to avoid Elasticsearch issues
            from django.db.models.signals import post_save
            from resources.models import index_resource

            post_save.disconnect(index_resource, sender=NLPTool)

            tool = NLPTool.objects.create(
                title="Test Tool DEBUG",
                title_en="Test Tool DEBUG",
                title_ar="أداة اختبار",
                description="This is a test NLP tool for debugging",
                description_en="This is a test NLP tool for debugging",
                description_ar="هذه أداة اختبار للتحليل",
                author=user,
                tool_type="tokenization",
                version="1.0.0",
                supported_languages="ar",
                language="ar",
                keywords="test,debug,nlp",
                approval_status="pending",
                is_approved=False,
            )

            # Reconnect signal
            post_save.connect(index_resource, sender=NLPTool)

            self.stdout.write(
                self.style.SUCCESS(f"  ✓ NLP Tool created successfully (ID: {tool.id})")
            )
            self.stdout.write(f"  Title: {tool.title}")
            self.stdout.write(f"  Tool Type: {tool.tool_type}")
            self.stdout.write(f"  Status: {tool.approval_status}")
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"  ✗ NLP Tool creation failed: {str(e)}")
            )
            import traceback

            self.stdout.write(
                self.style.ERROR(f"  Stack trace:\n{traceback.format_exc()}")
            )

    def test_course_creation(self, user):
        """Test 5: Try to create a course"""
        self.stdout.write(self.style.MIGRATE_LABEL("\n[TEST 5] Course Creation"))
        try:
            # Temporarily disable signals to avoid Elasticsearch issues
            from django.db.models.signals import post_save
            from resources.models import index_resource

            post_save.disconnect(index_resource, sender=Course)

            course = Course.objects.create(
                title="Test Course DEBUG",
                title_en="Test Course DEBUG",
                title_ar="دورة اختبار",
                description="This is a test course for debugging",
                description_en="This is a test course for debugging",
                description_ar="هذه دورة اختبار للتحليل",
                author=user,
                teacher=user,
                field="nlp",
                academic_level="undergraduate",
                institution="Test University",
                academic_year="2025-2026",
                language="ar",
                keywords="test,debug,course",
                approval_status="pending",
                is_approved=False,
            )

            # Reconnect signal
            post_save.connect(index_resource, sender=Course)

            self.stdout.write(
                self.style.SUCCESS(f"  ✓ Course created successfully (ID: {course.id})")
            )
            self.stdout.write(f"  Title: {course.title}")
            self.stdout.write(f"  Level: {course.academic_level}")
            self.stdout.write(f"  Status: {course.approval_status}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Course creation failed: {str(e)}"))
            import traceback

            self.stdout.write(
                self.style.ERROR(f"  Stack trace:\n{traceback.format_exc()}")
            )

    def test_query_resources(self):
        """Test 6: Query created resources"""
        self.stdout.write(self.style.MIGRATE_LABEL("\n[TEST 6] Query Resources"))

        try:
            corpus_count = Corpus.objects.filter(title__contains="DEBUG").count()
            tool_count = NLPTool.objects.filter(title__contains="DEBUG").count()
            course_count = Course.objects.filter(title__contains="DEBUG").count()

            self.stdout.write(f"  Test Corpora found: {corpus_count}")
            self.stdout.write(f"  Test Tools found: {tool_count}")
            self.stdout.write(f"  Test Courses found: {course_count}")

            # Show approval status breakdown
            pending_corpus = Corpus.objects.filter(approval_status="pending").count()
            approved_corpus = Corpus.objects.filter(approval_status="approved").count()

            self.stdout.write(f"\n  Corpus approval status:")
            self.stdout.write(f"    Pending: {pending_corpus}")
            self.stdout.write(f"    Approved: {approved_corpus}")

            if corpus_count + tool_count + course_count > 0:
                self.stdout.write(self.style.SUCCESS("\n  ✓ Query test successful"))
            else:
                self.stdout.write(self.style.WARNING("\n  ⚠ No test resources found"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Query test failed: {str(e)}"))
