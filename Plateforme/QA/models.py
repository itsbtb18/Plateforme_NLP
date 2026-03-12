from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from django.urls import reverse
from django.utils.translation import gettext_lazy as _, get_language
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager


class Question(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    if TYPE_CHECKING:
        answers: 'RelatedManager[Answer]'
    def __str__(self):
        return self.title


class Answer(models.Model):
    question = models.ForeignKey(Question, related_name='answers', on_delete=models.CASCADE)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Réponse par {self.author} à {self.question}"


class Post(models.Model):
    APPROVAL_STATUS_CHOICES = (
        ('pending', _('Pending')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='posts')
    
    # Title fields (bilingual)
    title = models.CharField(_("Title"), max_length=300, blank=True, default='')
    title_ar = models.CharField(_("Title (Arabic)"), max_length=300, blank=True, default='')
    title_en = models.CharField(_("Title (English)"), max_length=300, blank=True, default='')
    
    # Content fields (bilingual)
    content = models.TextField(verbose_name=_("Content"))
    content_ar = models.TextField(_("Content (Arabic)"), blank=True, default='')
    content_en = models.TextField(_("Content (English)"), blank=True, default='')
    
    image = models.ImageField(_('Image'), upload_to='posts/images/', null=True, blank=True)
    file = models.FileField(_('File'), upload_to='posts/files/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    likes = models.ManyToManyField(get_user_model(), related_name='liked_posts', blank=True)
    slug = models.SlugField(unique=True, blank=True, max_length=255)
    
    # Approval system
    approval_status = models.CharField(
        _("Approval Status"),
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default='pending'
    )
    rejection_reason = models.TextField(
        verbose_name=_("Rejection Reason"),
        blank=True,
        default='',
        help_text=_("Reason for rejection (only filled when status is rejected)")
    )
    approved_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_posts',
        verbose_name=_("Approved By")
    )
    approval_date = models.DateTimeField(
        verbose_name=_("Approval Date"),
        null=True,
        blank=True
    )
    view_count = models.PositiveIntegerField(
        verbose_name=_("View Count"),
        default=0
    )
    
    if TYPE_CHECKING:
        comments: 'RelatedManager[Comment]'

    class Meta:
        ordering = ['-created_at']
        verbose_name = _("Post")
        verbose_name_plural = _("Posts")

    def save(self, *args, **kwargs):
        # First save to get an ID if this is a new object
        if not self.pk:
            super().save(*args, **kwargs)
        # Now generate slug if needed (ID is now available)
        if not self.slug:
            self.slug = slugify(f"{self.author.full_name}-{self.pk}")  # type: ignore
        super().save(*args, **kwargs)

    def __str__(self):
        title = self.get_localized_title() or f"Post {self.id}"
        return f"{title} - {self.author.full_name}"  # type: ignore

    def get_absolute_url(self):
        return reverse('QA:post_detail', kwargs={'slug': self.slug})

    def get_localized_title(self):
        """Return title based on current language with fallback."""
        lang = get_language()
        if lang and lang.startswith('ar') and self.title_ar:
            return self.title_ar
        elif self.title_en:
            return self.title_en
        return self.title

    def get_localized_content(self):
        """Return content based on current language with fallback."""
        lang = get_language()
        if lang and lang.startswith('ar') and self.content_ar:
            return self.content_ar
        elif self.content_en:
            return self.content_en
        return self.content

    @property
    def is_approved(self):
        return self.approval_status == 'approved'

    @property
    def total_likes(self):
        return self.likes.count()

    @property
    def total_comments(self):
        return self.comments.count()


class Comment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='comments')
    content = models.TextField(verbose_name="Commentaire")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    likes = models.ManyToManyField(get_user_model(), related_name='liked_comments', blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')

    if TYPE_CHECKING:
        replies: 'RelatedManager[Comment]'

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Commentaire"
        verbose_name_plural = "Commentaires"

    def __str__(self):
        return f"Commentaire de {self.author.full_name} sur {self.post}"  # type: ignore

    @property
    def total_likes(self):
        return self.likes.count()

    @property
    def total_replies(self):
        return self.replies.count()