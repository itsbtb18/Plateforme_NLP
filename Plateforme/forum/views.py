from typing import Any, Dict, Optional, cast

from django.db.models import Q, QuerySet, Count
from django.http import HttpResponse, HttpRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
    View,
)
from .models import Topic, ChatRoom, Message, BannedUser
from .forms import TopicForm, ChatRoomForm
from django.contrib.auth.mixins import UserPassesTestMixin
from django.template.loader import render_to_string
from django.contrib.auth import get_user_model
from notifications.services import NotificationService, LocalizedValue
from accounts.views import LoginAndVerifiedRequiredMixin
from django.utils import timezone
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from accounts.blocking import exclude_hidden_users

class TopicListView(LoginAndVerifiedRequiredMixin, ListView):
        model = Topic
        template_name = 'forum/topic_list.html'  # Ajout du prefixe 'forum/'
        context_object_name = 'topics'
        ordering = ['-created_at']  # Tri par date de creation decroissante

        def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            """Handle both AJAX and regular requests."""
            # Check if this is an AJAX request
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            
            if is_ajax:
                return self._handle_ajax_request(request)
            
            # Regular HTML request
            return super().get(request, *args, **kwargs)

        def _handle_ajax_request(self, request: HttpRequest) -> HttpResponse:
            """Return partial HTML for AJAX requests."""
            # Get the queryset with all filters applied
            topics = self.get_queryset()
            
            # Build context for partial template
            context = {
                'topics': topics,
                'search_query': request.GET.get('q', ''),
                'current_sort': request.GET.get('sort', ''),
                'my_topics': request.GET.get('my_topics', ''),
                'user': request.user,
                'request': request,
            }
            
            # Render partial template
            html = render_to_string('forum/_topic_cards.html', context, request=request)
            
            # Also return the count for updating stats
            return HttpResponse(html)

        def get_queryset(self) -> QuerySet[Topic]:
            qs = cast(QuerySet[Topic], super().get_queryset())
            
            # STRICT: Only show APPROVED topics in the community section
            # Pending topics are only visible in the admin panel
            qs = qs.filter(approval_status='approved')
            qs = exclude_hidden_users(qs, self.request.user, ('creator',))
            
            # Filter: My Topics only - but still only approved ones
            if self.request.GET.get('my_topics') and self.request.user.is_authenticated:
                qs = qs.filter(creator=self.request.user)
            
            # Backend search filtering
            search_query = self.request.GET.get('q', '').strip()
            if search_query:
                qs = qs.filter(
                    Q(title__icontains=search_query) |
                    Q(title_ar__icontains=search_query) |
                    Q(title_en__icontains=search_query) |
                    Q(description__icontains=search_query) |
                    Q(description_ar__icontains=search_query) |
                    Q(description_en__icontains=search_query) |
                    Q(creator__username__icontains=search_query) |
                    Q(creator__full_name__icontains=search_query)
                )
            
            # Sort options
            sort = self.request.GET.get('sort', '')
            if sort == 'newest':
                qs = qs.order_by('-created_at')
            elif sort == 'active':
                # Sort by most chatrooms/activity
                qs = qs.annotate(chatroom_count=Count('chatrooms')).order_by('-chatroom_count', '-created_at')
            elif sort == 'popular':
                # Sort by views (fallback to chatroom count if views not available)
                qs = qs.annotate(chatroom_count=Count('chatrooms')).order_by('-views', '-chatroom_count', '-created_at')
            else:
                # Default: order by creation date
                qs = qs.order_by('-created_at')
            
            return qs

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context['page'] = 'community'
            context['search_query'] = self.request.GET.get('q', '')
            context['total_chatrooms'] = ChatRoom.objects.count()
            # Category filter context
            context['current_sort'] = self.request.GET.get('sort', '')
            context['my_topics'] = self.request.GET.get('my_topics', '')
            return context


class TopicCreateView(LoginAndVerifiedRequiredMixin, CreateView):
    model = Topic
    form_class = TopicForm
    template_name = 'forum/topic_new.html'  # Ajout du préfixe 'forum/'
    success_url = reverse_lazy('forum:topic-list')
    context_object_name = 'topic'
      
    def form_valid(self, form):
        import logging
        logger = logging.getLogger(__name__)
        
        form.instance.creator = self.request.user
        
        # Auto-approve for staff, pending for regular users
        if self.request.user.is_staff:
            form.instance.approval_status = 'approved'
            form.instance.is_approved = True  # Legacy field
            logger.info(f"[TOPIC_CREATE] Auto-approving topic by staff: {self.request.user.email}")
        else:
            form.instance.approval_status = 'pending'
            form.instance.is_approved = False  # Legacy field
            logger.info(f"[TOPIC_CREATE] Setting topic to pending by user: {self.request.user.email}")
        
        try:
            response = super().form_valid(form)
            logger.info(
                f"[TOPIC_CREATE] ✓ Topic created successfully "
                f"(ID: {form.instance.id}, Title: {form.instance.title}, Status: {form.instance.approval_status})"
            )
            
            if self.request.user.is_staff:
                messages.success(self.request, _("Your topic has been published."))
            else:
                messages.info(
                    self.request,
                    _("Your topic '%(title)s' has been submitted and is pending admin review.") % {'title': form.instance.title}
                )
            return response
            
        except Exception as e:
            logger.error(f"[TOPIC_CREATE] ✗ Error creating topic: {str(e)}", exc_info=True)
            messages.error(
                self.request,
                _("An error occurred while creating the topic. Please try again.")
            )
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"[TOPIC_CREATE] Form validation failed: {form.errors.as_json()}")
        
        # Log each field error for debugging
        for field, errors in form.errors.items():
            for error in errors:
                logger.warning(f"[TOPIC_CREATE] Field '{field}': {error}")
        
        # Create user-friendly error message
        error_summary = []
        for field, errors in form.errors.items():
            if field == '__all__':
                error_summary.extend(errors)
            else:
                field_label = form.fields.get(field).label if field in form.fields else field
                for error in errors:
                    error_summary.append(f"{field_label}: {error}")
        
        if error_summary:
            messages.error(
                self.request,
                _("Form validation failed:\n") + "\n".join(error_summary[:5])  # Show first 5 errors
            )
        else:
            messages.error(self.request, _('Please correct the errors in the form.'))
        
        return super().form_invalid(form)
    def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context['page'] = 'community'  
            return context

class TopicUpdateView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Topic
    form_class = TopicForm
    template_name = 'forum/topic_update.html'  # Ajout du préfixe 'forum/'
    success_url = reverse_lazy('forum:topic-list')
    context_object_name = 'topic'
    
    def test_func(self) -> bool:
        topic: Topic = cast(Topic, self.get_object())
        return topic.creator == self.request.user or self.request.user.is_staff or self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page'] = 'community'
        # Admin review mode - show bilingual fields
        review_mode = self.request.GET.get('review') == '1' and (
            self.request.user.is_staff or self.request.user.is_superuser
        )
        context['review_mode'] = review_mode
        context['is_pending'] = self.object.approval_status == 'pending'  # type: ignore[union-attr]
        context['topic'] = self.object
        return context

    def post(self, request, *args, **kwargs):
        """
        Handle POST - special handling for admin review mode.
        In review mode, form fields are different (bilingual) so we bypass normal form validation.
        """
        self.object = self.get_object()
        
        # Check if this is admin review mode
        is_admin = request.user.is_staff or request.user.is_superuser
        is_review_action = request.POST.get('action') == 'approve' or (
            request.POST.get('title_en') or request.POST.get('title_ar')
        )
        
        if is_admin and is_review_action:
            topic = self.object
            edit_only = request.GET.get('edit_only') == '1'
            review_model = request.GET.get('review_model')
            review_pk = request.GET.get('review_pk')
            
            # Update bilingual fields
            if request.POST.get('title_en'):
                topic.title_en = request.POST.get('title_en', '')
                topic.title = request.POST.get('title_en', topic.title)
            if request.POST.get('title_ar'):
                topic.title_ar = request.POST.get('title_ar', '')
            if request.POST.get('description_en'):
                topic.description_en = request.POST.get('description_en', '')
                topic.description = request.POST.get('description_en', topic.description)
            if request.POST.get('description_ar'):
                topic.description_ar = request.POST.get('description_ar', '')
            
            # Handle approval action
            if request.POST.get('action') == 'approve':
                topic.approval_status = 'approved'
                topic.save()
                messages.success(request, _("Topic has been approved and published."))
                return redirect('pages:admin_forum')
            
            # Just saving bilingual changes
            topic.save()
            messages.success(request, _("Topic updated successfully."))
            if edit_only and review_model and review_pk:
                return redirect('pages:admin_view_item', model_type=review_model, pk=review_pk)
            return redirect('pages:admin_forum')
        
        # Normal flow for non-admin or non-review mode
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        topic = form.save(commit=False)
        
        # Handle bilingual fields from admin review mode
        if self.request.POST.get('title_en'):
            topic.title_en = self.request.POST.get('title_en', '')
        if self.request.POST.get('title_ar'):
            topic.title_ar = self.request.POST.get('title_ar', '')
        if self.request.POST.get('description_en'):
            topic.description_en = self.request.POST.get('description_en', '')
        if self.request.POST.get('description_ar'):
            topic.description_ar = self.request.POST.get('description_ar', '')
        
        # Also update the main title/description with English version as default
        if self.request.POST.get('title_en'):
            topic.title = self.request.POST.get('title_en', topic.title)
        if self.request.POST.get('description_en'):
            topic.description = self.request.POST.get('description_en', topic.description)
        
        # Handle "Approve & Publish" action from admin review
        if self.request.POST.get('action') == 'approve' and (
            self.request.user.is_staff or self.request.user.is_superuser
        ):
            topic.approval_status = 'approved'
            topic.save()
            messages.success(self.request, _("Topic has been approved and published."))
            return redirect('pages:admin_forum')
        
        topic.save()
        return super().form_valid(form)

class TopicDeleteView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Topic
    success_url = reverse_lazy('forum:topic-list')
    template_name = 'forum/topic_delete.html'  # Ajout du préfixe 'forum/'
    context_object_name = 'topic'
    
    def test_func(self) -> bool:
        topic: Topic = cast(Topic, self.get_object())
        return topic.creator == self.request.user or self.request.user.is_staff or self.request.user.is_superuser

    def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context['page'] = 'community'  
            return context

class TopicDetailView(LoginAndVerifiedRequiredMixin, DetailView):
    model = Topic
    template_name = 'forum/topic_detail.html' 
    context_object_name = 'topic'

    def get_queryset(self) -> QuerySet[Topic]:
        qs = cast(QuerySet[Topic], super().get_queryset())
        # Only show approved topics (unless staff or creator)
        if not self.request.user.is_staff:
            qs = qs.filter(
                Q(approval_status='approved') | 
                Q(creator=self.request.user)
            )
        qs = exclude_hidden_users(qs, self.request.user, ('creator',))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        topic: Topic = cast(Topic, self.object)
        context['chatrooms'] = topic.chatrooms.all()
        context['page'] = 'community'  
        return context

class ChatRoomListView(LoginAndVerifiedRequiredMixin, ListView):
    model = ChatRoom
    template_name = 'forum/chatroom_list.html'  # Ajout du préfixe 'forum/'
    context_object_name = 'chatrooms'
    ordering = ['-created_at']  # Tri par date de création décroissante
    
    def dispatch(self, request: HttpRequest, *args, **kwargs):
        # Block access to chatrooms of unapproved topics (except for admins)
        topic = get_object_or_404(Topic, id=kwargs.get('topic_id'))
        if topic.approval_status != 'approved' and not (request.user.is_staff or request.user.is_superuser):
            from django.http import Http404
            raise Http404(_("Topic not found."))
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self) -> QuerySet[ChatRoom]:
        topic_id = self.kwargs.get('topic_id')  # récupérer l'id du topic depuis l'URL
        return ChatRoom.objects.filter(topic_id=topic_id).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        topic = get_object_or_404(Topic, id=self.kwargs.get('topic_id'))
        context['topic'] = topic
        context['page'] = 'community'
        return context

class ChatRoomDetailView(LoginAndVerifiedRequiredMixin, DetailView):
    model = ChatRoom
    template_name = 'forum/chatroom_detail.html'
    context_object_name = 'chatroom'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        chatroom: ChatRoom = cast(ChatRoom, self.object)
        context['messages'] = Message.objects.filter(chatroom=chatroom).order_by('timestamp')
        context['banned_users'] = BannedUser.objects.filter(chatroom=chatroom)
        context['page'] = 'community'
        return context
    
    def dispatch(self, request: HttpRequest, *args, **kwargs):
        chatroom: ChatRoom = cast(ChatRoom, self.get_object())
        
        # Block access to chatrooms of unapproved topics (except for admins)
        if chatroom.topic.approval_status != 'approved' and not (request.user.is_staff or request.user.is_superuser):
            from django.http import Http404
            raise Http404(_("Topic not found."))
        
        # Vérifier si l'utilisateur est banni
        if BannedUser.objects.filter(chatroom=chatroom, user=request.user).exists():
            return HttpResponseForbidden("Vous avez été banni de cette salle de discussion.")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args, **kwargs):
        chatroom: ChatRoom = cast(ChatRoom, self.get_object())
        self.object = chatroom
        content = request.POST.get('message', '').strip()
        if not content:
            return HttpResponse(status=204)

        message = Message.objects.create(
            chatroom=chatroom,
            user=request.user,
            content=content
        )
        if chatroom.topic and chatroom.topic.creator and chatroom.topic.creator != request.user:
            NotificationService.create_notification(
                recipient=chatroom.topic.creator,
                notification_type='FORUM_REPLY',
                title=_("New reply in topic %(title)s"),
                message=_("%(username)s replied in the chatroom %(name)s related to your topic."),
                related_object=chatroom.topic,
                action_url=chatroom.get_absolute_url(),
                title_kwargs={'title': chatroom.topic.title},
                message_kwargs={'username': LocalizedValue.from_user(request.user), 'name': chatroom.name}
            )

        if request.headers.get('HX-Request'):
            html = render_to_string(
                'forum/partials/message_item.html',
                {
                    'message': message,
                    'user': request.user
                },
                request=request
            )
            return HttpResponse(html)

        return redirect('forum:chatroom-detail', pk=chatroom.pk)

class ChatRoomCreateView(LoginAndVerifiedRequiredMixin, CreateView):
    model = ChatRoom
    form_class = ChatRoomForm
    template_name = 'forum/chatroom_new.html'
    context_object_name = 'chatroom'
    
    def form_valid(self, form):
        topic_id = self.kwargs.get('topic_id')
        form.instance.topic = get_object_or_404(Topic, id=topic_id)
        form.instance.creator = self.request.user
        return super().form_valid(form)
    
    def get_success_url(self):
        chatroom: ChatRoom = cast(ChatRoom, self.object)
        return reverse_lazy('forum:chatroom-detail', kwargs={'pk': chatroom.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page'] = 'community'
        topic_id = self.kwargs.get('topic_id')
        context['topic'] = get_object_or_404(Topic, id=topic_id)
        return context

class ChatRoomUpdateView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, UpdateView):
    model = ChatRoom
    form_class = ChatRoomForm
    template_name = 'forum/chatroom_update.html'
    context_object_name = 'chatroom'
    
    def test_func(self) -> bool:
        chatroom: ChatRoom = cast(ChatRoom, self.get_object())
        return self.request.user.is_staff or chatroom.creator == self.request.user
    
    def get_success_url(self):
        chatroom: ChatRoom = cast(ChatRoom, self.object)
        return reverse_lazy('forum:chatroom-detail', kwargs={'pk': chatroom.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page'] = 'community'
        return context

class ChatRoomDeleteView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, DeleteView):
    model = ChatRoom
    template_name = 'forum/chatroom_delete.html'
    context_object_name = 'chatroom'
    
    def test_func(self) -> bool:
        chatroom: ChatRoom = cast(ChatRoom, self.get_object())
        return self.request.user.is_staff or chatroom.creator == self.request.user
    
    def get_success_url(self):
        chatroom: ChatRoom = cast(ChatRoom, self.object)
        return reverse_lazy('forum:chatroom-list', kwargs={'topic_id': chatroom.topic.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page'] = 'community'  
        return context

class MessageDeleteView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Message
    template_name = 'forum/message_delete.html'  # Ajout du template manquant
    context_object_name = 'message'
    
    def test_func(self) -> bool:
        message: Message = cast(Message, self.get_object())
        return message.user == self.request.user
    
    def get_success_url(self):
        message: Message = cast(Message, self.object)
        return reverse_lazy('forum:chatroom-detail', kwargs={'pk': message.chatroom.pk})

class MessageUpdateView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Message
    template_name = 'forum/message_update.html'
    fields = ['content']
    
    def test_func(self) -> bool:
        message: Message = cast(Message, self.get_object())
        return message.user == self.request.user
    
    def form_valid(self, form):
        form.instance.is_edited = True
        form.instance.edited_at = timezone.now()
        return super().form_valid(form)
    
    def get_success_url(self):
        message: Message = cast(Message, self.object)
        return reverse_lazy('forum:chatroom-detail', kwargs={'pk': message.chatroom.pk})

class BanUserView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, CreateView):
    model = BannedUser
    fields = ['reason']
    template_name = 'forum/ban_user.html'
    
    def test_func(self):
        chatroom = get_object_or_404(ChatRoom, pk=self.kwargs['chatroom_pk'])
        return self.request.user.is_staff or chatroom.creator == self.request.user
    
    def form_valid(self, form):
        chatroom = get_object_or_404(ChatRoom, pk=self.kwargs['chatroom_pk'])
        user_to_ban = get_object_or_404(get_user_model(), pk=self.kwargs['user_pk'])
        
        # Vérifier que l'utilisateur n'est pas déjà banni
        if BannedUser.objects.filter(chatroom=chatroom, user=user_to_ban).exists():
            form.add_error(None, "Cet utilisateur est déjà banni de cette salle.")
            return self.form_invalid(form)
        
        form.instance.chatroom = chatroom
        form.instance.user = user_to_ban
        form.instance.banned_by = self.request.user
        
        # Créer une notification pour l'utilisateur banni
        NotificationService.create_notification(
            recipient=user_to_ban,
            notification_type='BAN',
            title=_("You have been banned from the chatroom %(name)s"),
            message=_("You have been banned from the chatroom %(name)s by %(username)s."),
            related_object=chatroom,
            title_kwargs={'name': chatroom.name},
            message_kwargs={'name': chatroom.name, 'username': LocalizedValue.from_user(self.request.user)}
        )
        
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('forum:chatroom-detail', kwargs={'pk': self.kwargs['chatroom_pk']})

class UnbanUserView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, DeleteView):
    model = BannedUser
    template_name = 'forum/unban_user.html'
    
    def test_func(self) -> bool:
        banned_user: BannedUser = cast(BannedUser, self.get_object())
        return self.request.user.is_staff or banned_user.chatroom.creator == self.request.user
    
    def get_success_url(self):
        banned_user: BannedUser = cast(BannedUser, self.object)
        return reverse_lazy('forum:chatroom-detail', kwargs={'pk': banned_user.chatroom.pk})

class TopicToggleStatusView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, View):
    """Vue pour basculer le statut d'un sujet (ouvert/fermé)"""
    
    def test_func(self):
        """Vérifie si l'utilisateur est un administrateur"""
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def post(self, request, pk):
        topic = get_object_or_404(Topic, pk=pk)
        topic.is_closed = not topic.is_closed
        topic.save()
        
        # Créer une notification pour le créateur du sujet
        if topic.creator != request.user:
            NotificationService.create_notification(
                recipient=topic.creator,
                notification_type='FORUM_TOPIC_STATUS',
                title=_("Topic closed") if topic.is_closed else _("Topic reopened"),
                message=_("Your topic '%(title)s' has been %(action)s by an administrator."),
                related_object=topic,
                message_kwargs={
                    'title': topic.title,
                    'action': str(_("closed")) if topic.is_closed else str(_("reopened"))
                }
            )
        
        # Retourner une réponse JSON pour les requêtes AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'is_closed': topic.is_closed,
                'message': f"Le sujet a été {'fermé' if topic.is_closed else 'rouvert'} avec succès."
            })
        
        # Redirection pour les requêtes non-AJAX
        return redirect('pages:admin_forum')

# Supprimer la fonction chatroom inutilisée ou la convertir en vue basée sur classe
