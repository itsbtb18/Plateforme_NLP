from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from feed.models import Post
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test post creation to diagnose database issues'

    def handle(self, *args, **options):
        self.stdout.write("=" * 60)
        self.stdout.write("[TEST] Post Creation Diagnostic")
        self.stdout.write("=" * 60)
        
        # Get test user
        try:
            user = User.objects.get(email='mina@gmail.com')
            self.stdout.write(self.style.SUCCESS(f"✓ Test user found: {user.email}"))
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR("✗ Test user not found"))
            return
        
        # Test 1: Basic Post Creation
        self.stdout.write("\n[TEST 1] Basic Post Creation")
        try:
            post = Post.objects.create(
                author=user,
                title='Test Post',
                title_en='Test Post EN',
                title_ar='منشور تجريبي',
                content='This is a test post',
                content_en='This is a test post',
                content_ar='هذا منشور تجريبي',
                approval_status='pending'
            )
            self.stdout.write(self.style.SUCCESS(f"✓ Post created successfully (ID: {post.id})"))
            self.stdout.write(f"  Title: {post.get_localized_title()}")
            self.stdout.write(f"  Status: {post.approval_status}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Post creation failed: {str(e)}"))
            logger.error(f"[TEST_POST] Error creating post", exc_info=True)
        
        # Test 2: Query Posts
        self.stdout.write("\n[TEST 2] Query Posts")
        try:
            posts = Post.objects.filter(author=user).order_by('-created_at')[:5]
            self.stdout.write(f"  Recent posts by test user: {posts.count()}")
            for post in posts:
                self.stdout.write(f"    - {post.get_localized_title()} ({post.approval_status})")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Query failed: {str(e)}"))
        
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("Test completed"))
        self.stdout.write("=" * 60)
