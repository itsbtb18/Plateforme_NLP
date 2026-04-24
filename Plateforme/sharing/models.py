from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
import uuid

User = get_user_model()


class Share(models.Model):
    """A user shares any platform content with another registered user."""

    class Status(models.TextChoices):
        SENT = 'sent', _('Sent')
        SEEN = 'seen', _('Seen')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    sender = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='shares_sent',
        verbose_name=_('Sender'),
    )
    receiver = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='shares_received',
        verbose_name=_('Receiver'),
    )

    # Generic relation – works with any model
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE,
        verbose_name=_('Content Type'),
    )
    object_id = models.CharField(max_length=255, verbose_name=_('Object ID'))
    content_object = GenericForeignKey('content_type', 'object_id')

    # Human-readable snapshot stored at share time (survives object deletion)
    content_title = models.CharField(max_length=500, blank=True, default='', verbose_name=_('Content Title'))
    content_url = models.CharField(max_length=1000, blank=True, default='', verbose_name=_('Content URL'))

    message = models.TextField(blank=True, default='', verbose_name=_('Message'))
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.SENT,
        verbose_name=_('Status'),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created At'))
    seen_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Seen At'))

    class Meta:
        verbose_name = _('Share')
        verbose_name_plural = _('Shares')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['receiver', '-created_at']),
            models.Index(fields=['sender', '-created_at']),
            models.Index(fields=['content_type', 'object_id']),
        ]
        # Prevent the same sender sharing the same item to the same receiver twice
        constraints = [
            models.UniqueConstraint(
                fields=['sender', 'receiver', 'content_type', 'object_id'],
                name='unique_share_per_pair',
            )
        ]

    def __str__(self):
        return (
            f"{self.sender} \u2192 {self.receiver}: "
            f"{self.content_type.model} ({self.object_id})"
        )

    @property
    def is_seen(self):
        return self.status == self.Status.SEEN


class ShareReply(models.Model):
    """Threaded private discussion attached to a Share.
    Only the original sender and receiver may read/write replies.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    share = models.ForeignKey(
        Share, on_delete=models.CASCADE,
        related_name='replies',
        verbose_name=_('Share'),
    )
    author = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='share_replies',
        verbose_name=_('Author'),
    )
    content = models.TextField(verbose_name=_('Content'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created At'))

    class Meta:
        verbose_name = _('Share Reply')
        verbose_name_plural = _('Share Replies')
        ordering = ['created_at']

    def __str__(self):
        return f"Reply by {self.author} on share {self.share_id}"
