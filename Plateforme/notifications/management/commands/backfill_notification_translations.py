"""
Management command to backfill Arabic translations for existing notifications.
Fixes notifications that have English text in Arabic fields due to legacy data.
"""
from django.core.management.base import BaseCommand
from notifications.models import Notification
import re


# Title translations - handles exact matches and common variants
TITLE_TRANSLATIONS = {
    # Likes (including typos)
    'New like': 'إعجاب جديد',
    'New Like': 'إعجاب جديد',
    'New I like': 'إعجاب جديد',  # Common typo
    
    # Comments
    'New comment': 'تعليق جديد',
    'New Comment': 'تعليق جديد',
    'New reply': 'رد جديد',
    'New Reply': 'رد جديد',
    'New reply to your comment': 'رد جديد على تعليقك',
    
    # Q&A
    'New answer': 'إجابة جديدة',
    'New Answer': 'إجابة جديدة',
    'New answer to your question': 'إجابة جديدة على سؤالك',
    'Answer accepted': 'تم قبول الإجابة',
    'Answer Accepted': 'تم قبول الإجابة',
    'New question': 'سؤال جديد',
    'New Question': 'سؤال جديد',
    
    # Resources
    'New resource': 'مورد جديد',
    'New Resource': 'مورد جديد',
    'New contribution to your resource': 'مساهمة جديدة في موردك',
    
    # Submissions
    'Submission approved': 'تمت الموافقة على مساهمتك',
    'Submission Approved': 'تمت الموافقة على مساهمتك',
    'Your submission has been approved': 'تمت الموافقة على مساهمتك',
    'Submission rejected': 'تم رفض مساهمتك',
    'Submission Rejected': 'تم رفض مساهمتك',
    'Your submission has been rejected': 'تم رفض مساهمتك',
    
    # Account
    'Account activated': 'تم تفعيل الحساب',
    'Account Activated': 'تم تفعيل الحساب',
    'Welcome': 'مرحباً',
    
    # Projects
    'Project Invitation': 'دعوة لمشروع',
    'Invitation Accepted': 'تم قبول الدعوة',
    'Invitation Declined': 'تم رفض الدعوة',
    'Invitation to join a project': 'دعوة للانضمام إلى مشروع',
    'Leave Request': 'طلب مغادرة',
    'Leave request': 'طلب مغادرة',
    'Leave request approved': 'تمت الموافقة على طلب المغادرة',
    'Leave request rejected': 'تم رفض طلب المغادرة',
    'New membership application': 'طلب عضوية جديد',
    'Membership application accepted': 'تم قبول طلب العضوية',
    'Membership application refused': 'تم رفض طلب العضوية',
    'Removed from project': 'تمت إزالتك من المشروع',
    'Project Request Accepted': 'تم قبول طلب المشروع',
    'Project Request Rejected': 'تم رفض طلب المشروع',
    
    # Forum
    'Topic closed': 'تم إغلاق الموضوع',
    'Topic reopened': 'تم إعادة فتح الموضوع',
    'New mention': 'إشارة جديدة',
    'New Mention': 'إشارة جديدة',
    'New follower': 'متابع جديد',
    'New Follower': 'متابع جديد',
    
    # Events
    'New event': 'حدث جديد',
    'New Event': 'حدث جديد',
    'Event updated': 'تم تحديث الحدث',
    'Event Updated': 'تم تحديث الحدث',
    'Event cancelled': 'تم إلغاء الحدث',
    'Event Cancelled': 'تم إلغاء الحدث',
    'Your event is awaiting approval': 'حدثك بانتظار الموافقة',
    'Your event has been approved': 'تمت الموافقة على حدثك',
    
    # System
    'System': 'النظام',
}

# Message phrase translations - ORDER MATTERS (longer/more specific phrases first)
# These are applied sequentially via string replacement
MESSAGE_PHRASE_REPLACEMENTS = [
    # Account activation - full phrases first
    ("Your account has been activated", "تم تفعيل حسابك"),
    ("You can now access all features.", "يمكنك الآن الوصول إلى جميع الميزات."),
    ("You can now access all features", "يمكنك الآن الوصول إلى جميع الميزات"),
    ("by an administrator.", "من قبل مسؤول."),
    ("by an administrator", "من قبل مسؤول"),
    
    # Resources
    ("The resource «", "المورد «"),
    ("The resource", "المورد"),
    ("» has been added to the platform.", "» تمت إضافته إلى المنصة."),
    ("» has been added to the platform", "» تمت إضافته إلى المنصة"),
    ("has been added to the platform.", "تمت إضافته إلى المنصة."),
    ("has been added to the platform", "تمت إضافته إلى المنصة"),
    
    # Submissions
    ("Your submission", "مساهمتك"),
    ("has been approved and is now visible to the public.", "تمت الموافقة عليها وهي الآن مرئية للجمهور."),
    ("has been approved and is now visible to the public", "تمت الموافقة عليها وهي الآن مرئية للجمهور"),
    ("and is now visible to the public.", "وهي الآن مرئية للجمهور."),
    ("and is now visible to the public", "وهي الآن مرئية للجمهور"),
    ("has been rejected and removed.", "تم رفضها وإزالتها."),
    ("has been rejected and removed", "تم رفضها وإزالتها"),
    
    # Likes
    ("liked your post.", "أعجب بمنشورك."),
    ("liked your post", "أعجب بمنشورك"),
    ("liked your comment.", "أعجب بتعليقك."),
    ("liked your comment", "أعجب بتعليقك"),
    
    # Comments
    ("commented on your post.", "علق على منشورك."),
    ("commented on your post", "علق على منشورك"),
    ("replied to your comment.", "رد على تعليقك."),
    ("replied to your comment", "رد على تعليقك"),
    
    # Mentions
    ("mentioned you in a post.", "أشار إليك في منشور."),
    ("mentioned you in a post", "أشار إليك في منشور"),
    ("mentioned you in a comment.", "أشار إليك في تعليق."),
    ("mentioned you in a comment", "أشار إليك في تعليق"),
    
    # Following
    ("started following you.", "بدأ بمتابعتك."),
    ("started following you", "بدأ بمتابعتك"),
    ("is now following you.", "يتابعك الآن."),
    ("is now following you", "يتابعك الآن"),
    
    # Q&A
    ("answered your question.", "أجاب على سؤالك."),
    ("answered your question", "أجاب على سؤالك"),
    ("Your answer has been accepted.", "تم قبول إجابتك."),
    ("Your answer has been accepted", "تم قبول إجابتك"),
    
    # Projects
    ("has accepted the invitation to join the project", "قبل الدعوة للانضمام إلى المشروع"),
    ("has declined the invitation to join the project", "رفض الدعوة للانضمام إلى المشروع"),
    ("You have been invited to join the project", "تمت دعوتك للانضمام إلى المشروع"),
    ("would like to leave your project", "يرغب في مغادرة مشروعك"),
    ("would like to join your project", "يرغب في الانضمام إلى مشروعك"),
    ("Your request to join the project", "طلبك للانضمام إلى المشروع"),
    ("was accepted.", "تم قبوله."),
    ("was accepted", "تم قبوله"),
    ("was refused.", "تم رفضه."),
    ("was refused", "تم رفضه"),
    ("has been approved.", "تمت الموافقة عليه."),
    ("has been approved", "تمت الموافقة عليه"),
    ("has been rejected by the coordinator.", "تم رفضه من قبل المنسق."),
    ("has been rejected by the coordinator", "تم رفضه من قبل المنسق"),
    ("You have been removed from the project", "تمت إزالتك من المشروع"),
    ("by the coordinator.", "من قبل المنسق."),
    ("by the coordinator", "من قبل المنسق"),
    
    # Events
    ("is awaiting approval.", "بانتظار الموافقة."),
    ("is awaiting approval", "بانتظار الموافقة"),
    ("is now visible.", "مرئي الآن."),
    ("is now visible", "مرئي الآن"),
    ("has been created.", "تم إنشاؤه."),
    ("has been created", "تم إنشاؤه"),
    ("has been updated.", "تم تحديثه."),
    ("has been updated", "تم تحديثه"),
    ("has been cancelled.", "تم إلغاؤه."),
    ("has been cancelled", "تم إلغاؤه"),
    
    # Forum
    ("replied in the chatroom", "رد في غرفة الدردشة"),
    ("related to your topic.", "المتعلقة بموضوعك."),
    ("related to your topic", "المتعلقة بموضوعك"),
    
    # Generic
    ("has been removed.", "تمت إزالتها."),
    ("has been removed", "تمت إزالتها"),
    ("has been rejected.", "تم رفضها."),
    ("has been rejected", "تم رفضها"),
]


class Command(BaseCommand):
    help = 'Backfill Arabic translations for existing notifications'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )

    def translate_title(self, title_ar):
        """Translate title from English to Arabic if needed."""
        if not title_ar:
            return None
        
        # Check if already Arabic (has Arabic characters)
        if self.is_mostly_arabic(title_ar):
            return None
        
        # Try exact match first
        if title_ar in TITLE_TRANSLATIONS:
            return TITLE_TRANSLATIONS[title_ar]
        
        # Try case-insensitive match
        title_lower = title_ar.lower().strip()
        for en, ar in TITLE_TRANSLATIONS.items():
            if en.lower() == title_lower:
                return ar
        
        # Try partial match for titles like "New I like" that should match "New like"
        for en, ar in TITLE_TRANSLATIONS.items():
            if en.lower() in title_lower or title_lower in en.lower():
                return ar
        
        return None

    def translate_message(self, message_ar):
        """Translate English phrases in message to Arabic."""
        if not message_ar:
            return None
        
        # If already fully Arabic, skip
        if self.is_mostly_arabic(message_ar):
            return None
        
        translated = message_ar
        changed = False
        
        for en, ar in MESSAGE_PHRASE_REPLACEMENTS:
            if en in translated:
                translated = translated.replace(en, ar)
                changed = True
        
        return translated if changed else None

    def is_mostly_arabic(self, text):
        """Check if text is mostly Arabic characters."""
        if not text:
            return False
        arabic_count = sum(1 for c in text if '\u0600' <= c <= '\u06FF' or '\u0750' <= c <= '\u077F')
        total_letters = sum(1 for c in text if c.isalpha())
        if total_letters == 0:
            return False
        return arabic_count / total_letters > 0.7

    def contains_english(self, text):
        """Check if text contains English words that need translation."""
        if not text:
            return False
        english_keywords = [
            'your', 'has', 'been', 'the', 'to', 'is', 'and', 'by', 'you',
            'added', 'approved', 'rejected', 'activated', 'can now',
            'submission', 'resource', 'account', 'features', 'platform',
            'liked', 'commented', 'replied', 'removed', 'visible',
            'new', 'like', 'comment', 'reply', 'answer', 'question',
            'event', 'project', 'topic', 'welcome', 'system'
        ]
        text_lower = text.lower()
        return any(kw in text_lower for kw in english_keywords)

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbosity = options['verbosity']
        
        # Get all notifications
        notifications = Notification.objects.all()
        total = notifications.count()
        
        self.stdout.write(f"Found {total} notifications to check")
        
        updated_count = 0
        
        for notification in notifications:
            needs_update = False
            new_title_ar = notification.title_ar
            new_message_ar = notification.message_ar
            
            # Check if title_ar needs translation (contains English)
            if notification.title_ar and self.contains_english(notification.title_ar):
                translated = self.translate_title(notification.title_ar)
                if translated:
                    new_title_ar = translated
                    needs_update = True
            
            # Check if message_ar needs translation (contains English)
            if notification.message_ar and self.contains_english(notification.message_ar):
                translated = self.translate_message(notification.message_ar)
                if translated and translated != notification.message_ar:
                    new_message_ar = translated
                    needs_update = True
            
            if needs_update:
                if verbosity >= 2:
                    self.stdout.write("-" * 60)
                    self.stdout.write(f"ID: {notification.id}")
                    if new_title_ar != notification.title_ar:
                        self.stdout.write(f"  Title: {notification.title_ar} -> {new_title_ar}")
                    if new_message_ar != notification.message_ar:
                        old_msg = notification.message_ar[:60] + "..." if len(notification.message_ar) > 60 else notification.message_ar
                        new_msg = new_message_ar[:60] + "..." if len(new_message_ar) > 60 else new_message_ar
                        self.stdout.write(f"  Message: {old_msg}")
                        self.stdout.write(f"       ->: {new_msg}")
                
                if not dry_run:
                    notification.title_ar = new_title_ar
                    notification.message_ar = new_message_ar
                    notification.save(update_fields=['title_ar', 'message_ar'])
                
                updated_count += 1
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'\nDRY RUN: Would update {updated_count} notifications')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'\nSuccessfully updated {updated_count} notifications')
            )
