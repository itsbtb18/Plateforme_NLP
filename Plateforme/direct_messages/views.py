from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from datetime import timedelta

from accounts.models import Friendship

from .forms import GroupCreateForm, MessageCreateForm
from .models import Conversation, ConversationParticipant, Message, _pair_order
from projects.models import Project, ProjectChatRoom

User = get_user_model()


def _display_name(user):
    if not user:
        return _("User")
    name = getattr(user, "get_full_name_display", "") or ""
    name = str(name).strip()
    if name and name != getattr(user, "email", ""):
        return name
    short_name = ""
    short_getter = getattr(user, "get_short_name", None)
    if callable(short_getter):
        short_name = (short_getter() or "").strip()
    if short_name:
        return short_name
    email = (getattr(user, "email", "") or "").strip()
    if email:
        return email.split("@")[0]
    return _("User")


def _create_group_system_message(conversation, sender, event, actor_name="", target_name="", content=""):
    if not conversation or conversation.conversation_type != Conversation.ConversationType.GROUP:
        return
    Message.objects.create(
        conversation=conversation,
        sender=sender,
        message_type=Message.MessageType.SYSTEM,
        system_event=event,
        system_actor=actor_name,
        system_target=target_name,
        content=content,
        is_read=False,
    )


def _friendship(user_a, user_b):
    return Friendship.between(user_a, user_b)


def _is_blocked(user_a, user_b):
    rel = _friendship(user_a, user_b)
    return bool(rel and rel.status == Friendship.Status.BLOCKED)


def _is_accepted_friend(user_a, user_b):
    rel = _friendship(user_a, user_b)
    return bool(rel and rel.status == Friendship.Status.ACCEPTED)


def _friend_candidates(user):
    accepted = Friendship.objects.filter(
        status=Friendship.Status.ACCEPTED
    ).filter(Q(requester=user) | Q(addressee=user))
    ids = set()
    for row in accepted:
        ids.add(row.addressee_id if row.requester_id == user.id else row.requester_id)
    return User.objects.filter(id__in=ids, is_active=True).exclude(id=user.id).order_by("email")


def _conversation_display(conversation, viewer):
    lang = (get_language() or "").lower()
    is_ar = lang.startswith("ar")
    if conversation.conversation_type == Conversation.ConversationType.GROUP:
        title = conversation.group_name or _("Group")
        avatar_url = conversation.group_image.url if conversation.group_image else ""
        subtitle = "دردشة جماعية" if is_ar else "Group chat"
        return title, avatar_url, subtitle, None
    other = conversation.other_participant(viewer)
    if not other:
        return _("Unknown user"), "", "", None
    title = (other.get_full_name_display or "").strip()
    if not title or title == other.email:
        title = (other.email or "").split("@")[0] or _("User")
    avatar_url = other.avatar.url if getattr(other, "avatar", None) else ""
    is_visible_online = bool(getattr(other, "show_online_status", True))
    is_active_state = getattr(other, "status", "") == "active"
    subtitle = ("متصل" if is_ar else "Online") if (is_visible_online and is_active_state) else ("غير متصل" if is_ar else "Offline")
    return title, avatar_url, subtitle, other


def _ensure_conversation_access(conversation, user):
    if not conversation.has_participant(user):
        raise Http404
    if conversation.conversation_type == Conversation.ConversationType.PRIVATE:
        other = conversation.other_participant(user)
        if not other:
            raise Http404
        if _is_blocked(user, other):
            return False, other
        return True, other
    return True, None


def _can_manage_group(conversation, user):
    if conversation.conversation_type != Conversation.ConversationType.GROUP:
        return False
    if conversation.group_admin_id == user.id:
        return True
    return conversation.participant_links.filter(user=user, is_admin=True).exists()


@login_required
@require_GET
def inbox(request):
    rows = (
        Conversation.objects.filter(participant_links__user=request.user)
        .distinct()
        .annotate(last_message_at=Max("messages__created_at"))
        .order_by("-last_message_at", "-created_at")
    )

    primary_conversations = []
    request_conversations = []

    for conv in rows:
        title, avatar_url, subtitle, other = _conversation_display(conv, request.user)
        last_msg = conv.messages.select_related("sender").order_by("-created_at").first()
        unread_count = conv.messages.filter(is_read=False).exclude(sender=request.user).count()
        row = {
            "conversation": conv,
            "title": title,
            "avatar_url": avatar_url,
            "subtitle": subtitle,
            "other": other,
            "last_message": last_msg,
            "last_activity": (last_msg.created_at if last_msg else conv.created_at),
            "unread_count": unread_count,
            "is_group": conv.is_group,
            "is_project_chat": False,
            "thread_url": reverse("direct_messages:thread", kwargs={"conversation_id": conv.id}),
        }
        if conv.is_request_for(request.user):
            request_conversations.append(row)
        else:
            primary_conversations.append(row)

    # Include project group discussions in the global discussions inbox.
    member_projects = (
        Project.objects.filter(
            Q(coordinator=request.user) | Q(members__member=request.user, members__status='accepted')
        )
        .distinct()
        .order_by("-updated_at")
    )
    for project in member_projects:
        room, room_created = ProjectChatRoom.objects.get_or_create(project=project)
        last_project_msg = room.messages.filter(is_deleted=False).select_related("sender").order_by("-created_at").first()
        unread_project = (
            room.messages.filter(is_deleted=False)
            .exclude(sender=request.user)
            .exclude(seen_by=request.user)
            .count()
        )
        if last_project_msg:
            if last_project_msg.message_type == last_project_msg.MessageType.FILE:
                last_text = _("Attachment")
            else:
                last_text = (last_project_msg.content or "").strip()
        else:
            last_text = _("Group discussion")
        project_title = getattr(project, "get_localized_title", None)
        if callable(project_title):
            project_title = project_title()
        if not project_title:
            project_title = getattr(project, "title_display", None) or getattr(project, "title", "")

        primary_conversations.append(
            {
                "conversation": None,
                "title": project_title,
                "avatar_url": "",
                "subtitle": _("Project discussion"),
                "other": None,
                "last_message": None,
                "last_activity": (last_project_msg.created_at if last_project_msg else room.created_at),
                "last_message_text": last_text,
                "unread_count": unread_project,
                "is_group": True,
                "is_project_chat": True,
                "thread_url": reverse("projects:project_chatroom", kwargs={"pk": project.pk}),
            }
        )

    primary_conversations.sort(
        key=lambda row: row.get("last_activity") or timezone.now(),
        reverse=True,
    )

    group_form = GroupCreateForm(members_queryset=_friend_candidates(request.user))
    return render(
        request,
        "direct_messages/inbox.html",
        {
            "primary_conversations": primary_conversations,
            "request_conversations": request_conversations,
            "group_form": group_form,
            "active_tab": request.GET.get("tab", "primary"),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def start_conversation(request, user_id):
    other = get_object_or_404(User, pk=user_id, is_active=True)
    if other == request.user:
        if request.method == "GET":
            return redirect("direct_messages:inbox")
        return JsonResponse({"ok": False, "error": _("You cannot chat with yourself.")}, status=400)

    if _is_blocked(request.user, other):
        if request.method == "GET":
            return redirect("direct_messages:inbox")
        return JsonResponse({"ok": False, "error": _("Chat is forbidden because one user is blocked.")}, status=403)

    first, second = _pair_order(request.user, other)
    conversation, created = Conversation.objects.get_or_create(
        user1=first,
        user2=second,
        defaults={
            "conversation_type": Conversation.ConversationType.PRIVATE,
            "created_by": request.user,
            "status": Conversation.ConversationStatus.PRIMARY
            if _is_accepted_friend(request.user, other)
            else Conversation.ConversationStatus.REQUEST,
            "is_accepted": _is_accepted_friend(request.user, other),
            "requested_by": None if _is_accepted_friend(request.user, other) else request.user,
        },
    )
    if created:
        conversation.participants.add(first, second)

    thread_url = reverse("direct_messages:thread", kwargs={"conversation_id": conversation.id})
    if request.method == "GET":
        return redirect(thread_url)
    return JsonResponse({"ok": True, "conversation_id": str(conversation.id), "url": thread_url})


@login_required
@require_http_methods(["GET", "POST"])
def thread(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id)
    allowed_access, other = _ensure_conversation_access(conversation, request.user)
    if not allowed_access:
        return redirect("direct_messages:inbox")

    can_send = conversation.can_user_send(request.user)

    if request.method == "POST" and can_send:
        form = MessageCreateForm(
            request.POST,
            request.FILES,
            instance=Message(conversation=conversation, sender=request.user),
        )
        if form.is_valid():
            msg = form.save(commit=False)
            msg.conversation = conversation
            msg.sender = request.user
            if conversation.conversation_type == Conversation.ConversationType.PRIVATE and conversation.status == Conversation.ConversationStatus.REQUEST:
                if _is_accepted_friend(request.user, other):
                    conversation.status = Conversation.ConversationStatus.PRIMARY
                    conversation.is_accepted = True
                    conversation.requested_by = None
                    conversation.save(update_fields=["status", "is_accepted", "requested_by"])
            msg.save()
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                file_url = msg.file_path.url if msg.file_path else ""
                return JsonResponse(
                    {
                        "ok": True,
                        "message": {
                            "id": str(msg.id),
                            "sender_id": str(msg.sender_id),
                            "sender_name": _display_name(request.user),
                            "sender_avatar_url": request.user.avatar.url if getattr(request.user, "avatar", None) else "",
                            "message_type": msg.message_type,
                            "content": msg.content,
                            "file_url": file_url,
                            "created_at": timezone.localtime(msg.created_at).strftime("%H:%M"),
                        },
                    }
                )
            return redirect("direct_messages:thread", conversation_id=conversation.id)
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "errors": form.errors}, status=400)
    else:
        form = MessageCreateForm()

    conversation.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    title, avatar_url, subtitle, _ = _conversation_display(conversation, request.user)
    participants = conversation.participants.exclude(id=request.user.id) if conversation.is_group else []
    group_add_candidates = []
    if conversation.is_group and _can_manage_group(conversation, request.user):
        current_ids = set(conversation.participants.values_list("id", flat=True))
        group_add_candidates = list(_friend_candidates(request.user).exclude(id__in=current_ids))
    participant_link = conversation.participant_links.filter(user=request.user).first()
    mute_until_ms = None
    if participant_link and participant_link.muted_until and participant_link.muted_until > timezone.now():
        mute_until_ms = int(participant_link.muted_until.timestamp() * 1000)
    return render(
        request,
        "direct_messages/thread.html",
        {
            "conversation": conversation,
            "other": other,
            "conversation_title": title,
            "conversation_avatar_url": avatar_url,
            "conversation_subtitle": subtitle,
            "thread_messages": conversation.messages.select_related("sender"),
            "form": form,
            "chat_forbidden": not can_send,
            "is_message_request": conversation.is_request_for(request.user),
            "participants": participants,
            "can_manage_group": _can_manage_group(conversation, request.user),
            "group_add_candidates": group_add_candidates,
            "is_muted_indefinitely": bool(participant_link and participant_link.is_muted_indefinitely),
            "muted_until_ms": mute_until_ms,
        },
    )


@login_required
@require_POST
def accept_conversation(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id)
    if not conversation.has_participant(request.user):
        raise Http404
    if not conversation.is_request_for(request.user):
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": _("This request cannot be accepted.")}, status=400)
        return redirect("direct_messages:thread", conversation_id=conversation.id)
    conversation.accept_request(request.user)
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    return redirect("direct_messages:thread", conversation_id=conversation.id)


@login_required
@require_http_methods(["POST", "DELETE"])
def delete_conversation(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id)
    if not conversation.has_participant(request.user):
        raise Http404
    conversation.delete()
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    return redirect("direct_messages:inbox")


@login_required
@require_POST
def create_group(request):
    form = GroupCreateForm(request.POST, request.FILES, members_queryset=_friend_candidates(request.user))
    if not form.is_valid():
        return redirect(f"{reverse('direct_messages:inbox')}?tab=primary")

    conversation = Conversation.objects.create(
        conversation_type=Conversation.ConversationType.GROUP,
        status=Conversation.ConversationStatus.PRIMARY,
        is_accepted=True,
        group_name=form.cleaned_data["group_name"].strip(),
        group_image=form.cleaned_data.get("group_image"),
        created_by=request.user,
        group_admin=request.user,
    )
    ConversationParticipant.objects.get_or_create(conversation=conversation, user=request.user, defaults={"is_admin": True})
    for member in form.cleaned_data["members"]:
        ConversationParticipant.objects.get_or_create(
            conversation=conversation,
            user=member,
            defaults={"is_admin": False},
        )
    _create_group_system_message(
        conversation=conversation,
        sender=request.user,
        event=Message.SystemEventType.GROUP_CREATED,
        actor_name=_display_name(request.user),
    )
    return redirect("direct_messages:thread", conversation_id=conversation.id)


@login_required
@require_POST
def add_group_member(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, conversation_type=Conversation.ConversationType.GROUP)
    if not _can_manage_group(conversation, request.user):
        return JsonResponse({"ok": False, "error": _("Only group admins can add members.")}, status=403)
    user_id = request.POST.get("user_id")
    member = get_object_or_404(User, id=user_id, is_active=True)
    _, created = ConversationParticipant.objects.get_or_create(
        conversation=conversation,
        user=member,
        defaults={"is_admin": False},
    )
    if created:
        _create_group_system_message(
            conversation=conversation,
            sender=request.user,
            event=Message.SystemEventType.MEMBER_ADDED,
            actor_name=_display_name(request.user),
            target_name=_display_name(member),
        )
    return JsonResponse({"ok": True})


@login_required
@require_POST
def update_group_info(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, conversation_type=Conversation.ConversationType.GROUP)
    if not _can_manage_group(conversation, request.user):
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": _("Only group admins can edit group info.")}, status=403)
        return redirect("direct_messages:thread", conversation_id=conversation.id)

    new_name = (request.POST.get("group_name") or "").strip()
    new_image = request.FILES.get("group_image")

    changed_fields = []
    if new_name:
        conversation.group_name = new_name[:120]
        changed_fields.append("group_name")
    if new_image:
        conversation.group_image = new_image
        changed_fields.append("group_image")

    if changed_fields:
        conversation.save(update_fields=changed_fields)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(
            {
                "ok": True,
                "title": conversation.group_name or _("Group"),
                "avatar_url": conversation.group_image.url if conversation.group_image else "",
            }
        )
    return redirect("direct_messages:thread", conversation_id=conversation.id)


@login_required
@require_POST
def remove_group_member(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, conversation_type=Conversation.ConversationType.GROUP)
    if not _can_manage_group(conversation, request.user):
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": _("Only group admins can remove members.")}, status=403)
        return redirect("direct_messages:thread", conversation_id=conversation.id)
    user_id = request.POST.get("user_id")
    if not user_id:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": _("Missing user_id.")}, status=400)
        return redirect("direct_messages:thread", conversation_id=conversation.id)
    if str(request.user.id) == str(user_id):
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": _("Admin cannot remove themselves.")}, status=400)
        return redirect("direct_messages:thread", conversation_id=conversation.id)
    removed_user = User.objects.filter(id=user_id).first()
    removed_count, _ = ConversationParticipant.objects.filter(conversation=conversation, user_id=user_id).delete()
    if removed_count and removed_user:
        _create_group_system_message(
            conversation=conversation,
            sender=request.user,
            event=Message.SystemEventType.MEMBER_REMOVED,
            actor_name=_display_name(request.user),
            target_name=_display_name(removed_user),
        )
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    return redirect("direct_messages:thread", conversation_id=conversation.id)


@login_required
@require_POST
def leave_group(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, conversation_type=Conversation.ConversationType.GROUP)
    if not conversation.has_participant(request.user):
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": _("Access denied.")}, status=403)
        return redirect("direct_messages:inbox")

    _create_group_system_message(
        conversation=conversation,
        sender=request.user,
        event=Message.SystemEventType.MEMBER_LEFT,
        actor_name=_display_name(request.user),
    )
    ConversationParticipant.objects.filter(conversation=conversation, user=request.user).delete()

    if not conversation.participant_links.exists():
        conversation.delete()
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": True, "deleted": True})
        return redirect("direct_messages:inbox")

    if conversation.group_admin_id == request.user.id:
        next_admin_link = conversation.participant_links.select_related("user").order_by("joined_at").first()
        if next_admin_link:
            next_admin_link.is_admin = True
            next_admin_link.save(update_fields=["is_admin"])
            conversation.group_admin = next_admin_link.user
            conversation.save(update_fields=["group_admin"])

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "deleted": False})
    return redirect("direct_messages:inbox")


@login_required
@require_POST
def set_mute(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id)
    if not conversation.has_participant(request.user):
        return JsonResponse({"ok": False, "error": _("Access denied.")}, status=403)

    mode = (request.POST.get("mode") or "").strip().lower()
    link = get_object_or_404(ConversationParticipant, conversation=conversation, user=request.user)

    if mode == "off":
        link.is_muted_indefinitely = False
        link.muted_until = None
    elif mode == "forever":
        link.is_muted_indefinitely = True
        link.muted_until = None
    elif mode in {"1h", "8h", "24h"}:
        hours = int(mode.replace("h", ""))
        link.is_muted_indefinitely = False
        link.muted_until = timezone.now() + timedelta(hours=hours)
    else:
        return JsonResponse({"ok": False, "error": _("Invalid mute mode.")}, status=400)

    link.save(update_fields=["is_muted_indefinitely", "muted_until"])
    return JsonResponse(
        {
            "ok": True,
            "mode": mode,
            "muted_until": link.muted_until.isoformat() if link.muted_until else None,
            "is_muted_indefinitely": link.is_muted_indefinitely,
        }
    )


@login_required
@require_POST
def mark_as_read(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id)
    if not conversation.has_participant(request.user):
        return JsonResponse({"ok": False, "error": _("Access denied.")}, status=403)
    updated = conversation.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
    return JsonResponse({"ok": True, "updated": updated})


@login_required
@require_GET
def unread_count(request):
    excluded_requests = Q(
        conversation__status=Conversation.ConversationStatus.REQUEST,
        conversation__is_accepted=False,
    ) & ~Q(conversation__requested_by=request.user)
    now = timezone.now()
    muted_filter = Q(
        conversation__participant_links__user=request.user,
        conversation__participant_links__is_muted_indefinitely=True,
    ) | Q(
        conversation__participant_links__user=request.user,
        conversation__participant_links__muted_until__gt=now,
    )
    count = (
        Message.objects.filter(
            is_read=False,
            conversation__participant_links__user=request.user,
        )
        .exclude(sender=request.user)
        .exclude(excluded_requests)
        .exclude(muted_filter)
        .distinct()
        .count()
    )
    return JsonResponse({"count": count})


@login_required
@require_GET
def unread_map(request):
    """Unread message count per conversation for inbox live badges."""
    counts = (
        Conversation.objects.filter(participant_links__user=request.user)
        .annotate(
            unread_count=Count(
                "messages",
                filter=Q(messages__is_read=False) & ~Q(messages__sender=request.user),
                distinct=True,
            )
        )
        .values_list("id", "unread_count")
    )
    payload = {str(conv_id): int(unread or 0) for conv_id, unread in counts}
    return JsonResponse({"counts": payload})
