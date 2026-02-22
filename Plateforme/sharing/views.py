import json
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .models import Share, ShareReply
from .services import ShareService


# ---------------------------------------------------------------------------
# AJAX: user search for the share modal autocomplete
# ---------------------------------------------------------------------------
@login_required
def user_search(request):
    """Return JSON list of users matching the 'q' query (excluding self)."""
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'users': []})
    from django.contrib.auth import get_user_model
    User = get_user_model()
    qs = (
        User.objects
        .filter(full_name__icontains=q, is_active=True)
        .exclude(pk=request.user.pk)[:10]
    )
    users = [
        {
            'id': str(u.pk),
            'name': u.full_name or u.email,
            'avatar': u.avatar.url if getattr(u, 'avatar', None) and u.avatar else None,
        }
        for u in qs
    ]
    return JsonResponse({'users': users})


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
