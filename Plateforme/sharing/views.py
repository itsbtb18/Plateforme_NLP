import json
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.urls import reverse

from .models import Share, ShareReply
from .services import ShareService
from accounts.models import Friendship
from direct_messages.models import Conversation, Message


# ---------------------------------------------------------------------------
# AJAX: user search for the share modal autocomplete
# ---------------------------------------------------------------------------
@login_required
def user_search(request):
    """Return the current user's accepted friends, optionally filtered by query."""
    q = request.GET.get('q', '').strip()

    # Build the accepted friendship graph for the current user.
    accepted_links = Friendship.objects.filter(
        Q(requester=request.user) | Q(addressee=request.user),
        status=Friendship.Status.ACCEPTED,
    ).values_list('requester_id', 'addressee_id')

    friend_ids = set()
    for requester_id, addressee_id in accepted_links:
        friend_ids.add(addressee_id if requester_id == request.user.id else requester_id)

    if not friend_ids:
        return JsonResponse({'users': []})

    from django.contrib.auth import get_user_model
    User = get_user_model()
    qs = User.objects.filter(pk__in=friend_ids, is_active=True)

    # When query exists, filter by common identity fields. Without query:
    # return the latest friends directly so the modal is populated on open.
    if q:
        qs = qs.filter(
            Q(full_name__icontains=q)
            | Q(full_name_ar__icontains=q)
            | Q(full_name_en__icontains=q)
            | Q(email__icontains=q)
        )

    qs = qs.order_by('-date_joined')[:50]
    users = [
        {
            'id': str(u.pk),
            'name': u.get_full_name_display if hasattr(u, 'get_full_name_display') else (u.full_name or u.email),
            'email': u.email or '',
            'avatar': u.avatar.url if getattr(u, 'avatar', None) and u.avatar else None,
            'profile_url': reverse('accounts:profile', kwargs={'pk': u.pk}),
        }
        for u in qs
    ]
    return JsonResponse({'users': users})


@login_required
def group_search(request):
    """Return groups joined by the current user, optionally filtered by query."""
    q = request.GET.get('q', '').strip()
    qs = (
        Conversation.objects
        .filter(conversation_type=Conversation.ConversationType.GROUP, participants=request.user)
        .order_by('-created_at')
    )
    if q:
        qs = qs.filter(group_name__icontains=q)
    qs = qs[:50]
    groups = [
        {
            'id': str(conv.id),
            'name': (conv.group_name or _("Group chat")),
            'avatar': conv.group_image.url if conv.group_image else None,
        }
        for conv in qs
    ]
    return JsonResponse({'groups': groups})


# ---------------------------------------------------------------------------
# Create a share (AJAX POST from the modal)
# ---------------------------------------------------------------------------
@login_required
@require_POST
def create_share(request):
    """Accept JSON body or form-data; return JSON result."""
    try:
        if request.content_type and 'application/json' in request.content_type:
            data = json.loads(request.body)
        else:
            data = request.POST

        receiver_id = data.get('receiver_id')
        content_type_str = data.get('content_type')   # e.g. 'tool', 'resource'
        object_id = data.get('object_id')
        message = data.get('message', '').strip()

        if not all([receiver_id, content_type_str, object_id]):
            return JsonResponse({'success': False, 'error': _('Missing required fields.')}, status=400)

        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            receiver = User.objects.get(pk=receiver_id)
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': _('User not found.')}, status=404)

        if receiver == request.user:
            return JsonResponse({'success': False, 'error': _('You cannot share with yourself.')}, status=400)

        share, created = ShareService.create_share(
            sender=request.user,
            receiver=receiver,
            content_type_str=content_type_str,
            object_id=str(object_id),
            message=message,
        )
        if not created:
            return JsonResponse({'success': False, 'error': _('You already shared this item with that user.')}, status=409)

        return JsonResponse({'success': True, 'share_id': str(share.id)})

    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)


@login_required
@require_POST
def create_group_share(request):
    """Share platform content into a group conversation joined by the sender."""
    try:
        if request.content_type and 'application/json' in request.content_type:
            data = json.loads(request.body)
        else:
            data = request.POST

        conversation_id = data.get('conversation_id')
        content_type_str = data.get('content_type')
        object_id = data.get('object_id')
        user_note = (data.get('message', '') or '').strip()

        if not all([conversation_id, content_type_str, object_id]):
            return JsonResponse({'success': False, 'error': _('Missing required fields.')}, status=400)

        conversation = get_object_or_404(Conversation, id=conversation_id)
        if conversation.conversation_type != Conversation.ConversationType.GROUP:
            return JsonResponse({'success': False, 'error': _('Invalid group conversation.')}, status=400)
        if not conversation.has_participant(request.user):
            return JsonResponse({'success': False, 'error': _('You are not a participant in this group.')}, status=403)
        if not conversation.can_user_send(request.user):
            return JsonResponse({'success': False, 'error': _('You cannot send messages in this group.')}, status=403)

        _, title, url = ShareService.get_share_snapshot(content_type_str, str(object_id))
        if url and url.startswith("/"):
            url = request.build_absolute_uri(url)
        is_ar = request.LANGUAGE_CODE.startswith('ar')
        header = _("Shared item") if not title else title
        if is_ar:
            intro = f"مشاركة: {header}"
        else:
            intro = f"Shared: {header}"
        parts = [intro]
        if url:
            parts.append(url)
        if user_note:
            parts.append(user_note)
        content = "\n".join(parts).strip()

        msg_type = Message.MessageType.LINK if (url and (url.startswith("http://") or url.startswith("https://"))) else Message.MessageType.TEXT
        msg = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            message_type=msg_type,
            content=content,
        )
        return JsonResponse({'success': True, 'message_id': str(msg.id)})
    except ValueError as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)


# ---------------------------------------------------------------------------
# Inbox + sent
# ---------------------------------------------------------------------------
@login_required
def inbox(request):
    """All shares received by the current user."""
    shares = (
        Share.objects
        .filter(receiver=request.user)
        .select_related('sender', 'content_type')
        .prefetch_related('replies')
        .order_by('-created_at')
    )
    # Mark all unseen as seen on open
    unseen = shares.filter(status=Share.Status.SENT)
    unseen.update(status=Share.Status.SEEN, seen_at=timezone.now())

    return render(request, 'sharing/inbox.html', {'shares': shares, 'tab': 'inbox'})


@login_required
def sent(request):
    """All shares sent by the current user."""
    shares = (
        Share.objects
        .filter(sender=request.user)
        .select_related('receiver', 'content_type')
        .prefetch_related('replies')
        .order_by('-created_at')
    )
    return render(request, 'sharing/inbox.html', {'shares': shares, 'tab': 'sent'})


# ---------------------------------------------------------------------------
# Thread detail (private discussion for a share)
# ---------------------------------------------------------------------------
@login_required
def share_detail(request, share_id):
    """View a share + its reply thread. Only accessible by sender/receiver."""
    share = get_object_or_404(Share, id=share_id)
    if request.user not in (share.sender, share.receiver):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    # Mark as seen when receiver opens the thread
    if request.user == share.receiver and share.status == Share.Status.SENT:
        share.status = Share.Status.SEEN
        share.seen_at = timezone.now()
        share.save(update_fields=['status', 'seen_at'])

    replies = share.replies.select_related('author').order_by('created_at')
    return render(request, 'sharing/share_detail.html', {
        'share': share,
        'replies': replies,
    })


# ---------------------------------------------------------------------------
# Add reply (AJAX or form POST)
# ---------------------------------------------------------------------------
@login_required
@require_POST
def add_reply(request, share_id):
    share = get_object_or_404(Share, id=share_id)
    if request.user not in (share.sender, share.receiver):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    try:
        if request.content_type and 'application/json' in request.content_type:
            data = json.loads(request.body)
        else:
            data = request.POST
        content = data.get('content', '').strip()
    except Exception:
        content = ''

    if not content:
        return JsonResponse({'success': False, 'error': _('Reply cannot be empty.')}, status=400)

    reply = ShareReply.objects.create(share=share, author=request.user, content=content)
    # Notify the other party
    other = share.receiver if request.user == share.sender else share.sender
    ShareService.notify_reply(reply, other)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
       (request.content_type and 'application/json' in request.content_type):
        return JsonResponse({
            'success': True,
            'reply': {
                'id': str(reply.id),
                'author': reply.author.full_name or reply.author.email,
                'content': reply.content,
                'created_at': reply.created_at.isoformat(),
            }
        })
    return redirect('sharing:share_detail', share_id=share_id)


# ---------------------------------------------------------------------------
# Unread count (badge in navbar) - AJAX
# ---------------------------------------------------------------------------
@login_required
def unread_count(request):
    count = Share.objects.filter(receiver=request.user, status=Share.Status.SENT).count()
    return JsonResponse({'count': count})
