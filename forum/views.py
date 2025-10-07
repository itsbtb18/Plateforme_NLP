from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from .models import Topic, ChatRoom, Message, BannedUser
from django.contrib.auth.mixins import UserPassesTestMixin
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from notifications.services import NotificationService
from accounts.views import LoginAndVerifiedRequiredMixin
from django.utils import timezone
from django.http import HttpResponseForbidden, JsonResponse

class TopicListView(LoginAndVerifiedRequiredMixin, ListView):
        model = Topic
        template_name = 'forum/topic_list.html'  # Ajout du préfixe 'forum/'
        context_object_name = 'topics'
        ordering = ['-created_at']  # Tri par date de création décroissante

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context['page'] = 'community'  
            return context

       
        

class TopicCreateView(LoginAndVerifiedRequiredMixin, CreateView):
    model = Topic
    fields = ['title', 'description']
    template_name = 'forum/topic_new.html'  # Ajout du préfixe 'forum/'
    success_url = reverse_lazy('forum:topic-list')
    context_object_name = 'topic'
      
    def form_valid(self, form):
        form.instance.creator = self.request.user
        response = super().form_valid(form)
        # NOTIFICATION à tous les utilisateurs actifs via le service
        User = get_user_model()
        for user in User.objects.filter(is_active=True):
            # Évite d'envoyer la notification à l'utilisateur qui vient de créer le topic
            if user != self.request.user:
                NotificationService.create_notification(
                    recipient=user,
                    notification_type='SYSTEM', # Ou un type spécifique si tu en crées un pour le forum
                    title="New topic in the forum",
                    message=f"{self.request.user.username} created a new topic : {form.instance.title}",
                    related_object=form.instance # Optionnel: lie la notification à l'objet Topic créé
                )
        return response
    def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context['page'] = 'community'  
            return context

class TopicUpdateView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Topic
    fields = ['title', 'description']
    template_name = 'forum/topic_update.html'  # Ajout du préfixe 'forum/'
    success_url = reverse_lazy('forum:topic-list')
    context_object_name = 'topic'
    
    def test_func(self):
        topic = self.get_object()
        return topic.creator == self.request.user or self.request.user.is_staff or self.request.user.is_superuser
    def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context['page'] = 'community'  
            return context

class TopicDeleteView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Topic
    success_url = reverse_lazy('forum:topic-list')
    template_name = 'forum/topic_delete.html'  # Ajout du préfixe 'forum/'
    context_object_name = 'topic'
    
    def test_func(self):
        topic = self.get_object()
        return topic.creator == self.request.user or self.request.user.is_staff or self.request.user.is_superuser
    def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context['page'] = 'community'  
            return context

class TopicDetailView(LoginAndVerifiedRequiredMixin, DetailView):
    model = Topic
    template_name = 'forum/topic_detail.html' 
    context_object_name = 'topic'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['chatrooms'] = self.object.chatrooms.all()
        context['page'] = 'community'  
        return context

class ChatRoomListView(LoginAndVerifiedRequiredMixin, ListView):
    model = ChatRoom
    template_name = 'forum/chatroom_list.html'  # Ajout du préfixe 'forum/'
    context_object_name = 'chatrooms'
    ordering = ['-created_at']  # Tri par date de création décroissante
    def get_queryset(self):
        topic_id = self.kwargs.get('topic_id')  # récupérer l'id du topic depuis l'URL
        return ChatRoom.objects.filter(topic_id=topic_id).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['topic_id'] = Topic.objects.get(id=self.kwargs.get('topic_id'))  # pour afficher le nom du topic si besoin

        context['page'] = 'community'

        
        return context

class ChatRoomDetailView(LoginAndVerifiedRequiredMixin, DetailView):
    model = ChatRoom
    template_name = 'forum/chatroom_detail.html'
    context_object_name = 'chatroom'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['messages'] = Message.objects.filter(chatroom=self.object).order_by('timestamp')
        context['banned_users'] = BannedUser.objects.filter(chatroom=self.object)
        context['page'] = 'community'
        return context
    
    def dispatch(self, request, *args, **kwargs):
        chatroom = self.get_object()
        # Vérifier si l'utilisateur est banni
        if BannedUser.objects.filter(chatroom=chatroom, user=request.user).exists():
            return HttpResponseForbidden("Vous avez été banni de cette salle de discussion.")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # on récupère la salle et on crée le message
        self.object = self.get_object()
        content = request.POST.get('message', '').strip()
        if content:
            message = Message.objects.create(
                chatroom=self.object,
                user=request.user,
                content=content
            )
            # Utiliser NotificationService pour les notifications de nouveau message dans une chatroom
            if self.object.topic: # S'assurer que la chatroom est liée à un topic
                # Notifier le créateur du topic si ce n'est pas l'utilisateur actuel
                if self.object.topic.creator and self.object.topic.creator != request.user:
                    NotificationService.create_notification(
                        recipient=self.object.topic.creator,
                        notification_type='FORUM_REPLY', # Utiliser un type spécifique si possible
                        title=f"Nouvelle réponse dans le sujet « {self.object.topic.title} »",
                        message=f"{request.user.username} a répondu dans la salle de discussion « {self.object.name} » liée à votre sujet.",
                        related_object=self.object.topic,
                        action_url=self.object.get_absolute_url() # Lien vers la chatroom/le message si possible
                    )
                # Tu pourrais aussi vouloir notifier d'autres participants de la chatroom si nécessaire
                # for participant in self.object.participants.exclude(id=request.user.id).exclude(id=self.object.topic.creator.id):
                #     NotificationService.create_notification(...)

        else:
            return HttpResponse(status=204)  # pas de contenu à créer
        
        # si c'est une requête HTMX, on renvoie juste le fragment du nouveau message
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
        
        # sinon on redirige normalement
        return redirect('forum:chatroom-detail', pk=self.object.pk)

class ChatRoomCreateView(LoginAndVerifiedRequiredMixin, CreateView):
    model = ChatRoom
    fields = ['name', 'description']
    template_name = 'forum/chatroom_new.html'  # Ajout du préfixe 'forum/'
    context_object_name = 'chatroom'
    
    def form_valid(self, form):
        topic_id = self.kwargs.get('topic_id')
        form.instance.topic = get_object_or_404(Topic, id=topic_id)
        form.instance.creator = self.request.user  # Ajout de l'attribution du créateur
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('forum:chatroom-detail', kwargs={'pk': self.object.pk})
    def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context['page'] = 'community'  
            return context

class ChatRoomUpdateView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, UpdateView):
    model = ChatRoom
    fields = ['name', 'description']
    template_name = 'forum/chatroom_update.html'
    context_object_name = 'chatroom'
    
    def test_func(self):
        chatroom = self.get_object()
        return self.request.user.is_staff or chatroom.creator == self.request.user
    
    def get_success_url(self):
        return reverse_lazy('forum:chatroom-detail', kwargs={'pk': self.object.pk})
    def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context['page'] = 'community'  
            return context

class ChatRoomDeleteView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, DeleteView):
    model = ChatRoom
    template_name = 'forum/chatroom_delete.html'
    context_object_name = 'chatroom'
    
    def test_func(self):
        chatroom = self.get_object()
        return self.request.user.is_staff or chatroom.creator == self.request.user
    
    def get_success_url(self):
        # Rediriger vers la liste des chatrooms du topic parent
        return reverse_lazy('forum:chatroom-list', kwargs={'topic_id': self.object.topic.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page'] = 'community'  
        return context

class MessageDeleteView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Message
    template_name = 'forum/message_delete.html'  # Ajout du template manquant
    context_object_name = 'message'
    
    def test_func(self):
        return self.get_object().user == self.request.user
    
    def get_success_url(self):
        return reverse_lazy('forum:chatroom-detail', kwargs={'pk': self.object.chatroom.pk})

class MessageUpdateView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Message
    template_name = 'forum/message_update.html'
    fields = ['content']
    
    def test_func(self):
        return self.get_object().user == self.request.user
    
    def form_valid(self, form):
        form.instance.is_edited = True
        form.instance.edited_at = timezone.now()
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('forum:chatroom-detail', kwargs={'pk': self.object.chatroom.pk})

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
            title=f"Vous avez été banni de la salle {chatroom.name}",
            message=f"Vous avez été banni de la salle de discussion {chatroom.name} par {self.request.user.username}.",
            related_object=chatroom
        )
        
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('forum:chatroom-detail', kwargs={'pk': self.kwargs['chatroom_pk']})

class UnbanUserView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, DeleteView):
    model = BannedUser
    template_name = 'forum/unban_user.html'
    
    def test_func(self):
        banned_user = self.get_object()
        return self.request.user.is_staff or banned_user.chatroom.creator == self.request.user
    
    def get_success_url(self):
        return reverse_lazy('forum:chatroom-detail', kwargs={'pk': self.object.chatroom.pk})

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
                title=f"Sujet {'fermé' if topic.is_closed else 'rouvert'}",
                message=f"Votre sujet '{topic.title}' a été {'fermé' if topic.is_closed else 'rouvert'} par un administrateur.",
                related_object=topic
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