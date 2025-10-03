from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()

class Stats(models.Model):
    """Model for platform statistics"""
    date = models.DateField(_('date'), unique=True, default=timezone.now)
    users_count = models.IntegerField(_('nombre d\'utilisateurs'), default=0)
    publications_count = models.IntegerField(_('nombre de publications'), default=0)
    corpora_count = models.IntegerField(_('nombre de corpus'), default=0)
    tools_count = models.IntegerField(_('nombre d\'outils'), default=0)
    projects_count = models.IntegerField(_('nombre de projets'), default=0)
    forum_posts_count = models.IntegerField(_('nombre de messages forum'), default=0)
    visits_count = models.IntegerField(_('nombre de visites'), default=0)
    downloads_count = models.IntegerField(_('nombre de téléchargements'), default=0)
    
    class Meta:
        verbose_name = _('statistique')
        verbose_name_plural = _('statistiques')
        ordering = ['-date']
        
    def __str__(self):
        return f"Stats {self.date}"
    



class UserStatusHistory(models.Model):
    """
    Modèle pour suivre l'historique des changements de statut des utilisateurs.
    
    Ce modèle enregistre chaque modification du statut d'un utilisateur, incluant:
    - L'utilisateur concerné
    - L'ancien et le nouveau statut
    - L'administrateur qui a effectué le changement
    - La date et l'heure du changement
    - Une raison optionnelle pour le changement
    """
    
    # Statuts possibles pour référence (correspond aux statuts du modèle User)
    STATUS_CHOICES = (
        ('active', 'Actif'),
        ('pending', 'En attente'),
        ('blocked', 'Bloqué'),
        ('new', 'Nouveau'),  # Utilisé pour la création initiale
    )
    
    # Relation avec l'utilisateur dont le statut a été modifié
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,  # Si l'utilisateur est supprimé, son historique l'est aussi
        related_name='status_history',  # Permet d'accéder à l'historique depuis un utilisateur: user.status_history.all()
        verbose_name="Utilisateur"
    )
    
    # Ancien statut de l'utilisateur
    old_status = models.CharField(
        max_length=10,
        verbose_name="Ancien statut"
    )
    
    # Nouveau statut de l'utilisateur
    new_status = models.CharField(
        max_length=10,
        verbose_name="Nouveau statut"
    )
    
    # Administrateur qui a effectué le changement
    changed_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,  # Si l'admin est supprimé, on garde null comme référence
        null=True,
        related_name='status_changes_made',  # Permet d'accéder aux changements effectués par un admin: admin.status_changes_made.all()
        verbose_name="Modifié par"
    )
    
    # Date et heure du changement
    change_date = models.DateTimeField(
        default=timezone.now,  # Utilise la date/heure actuelle par défaut
        verbose_name="Date de modification"
    )
    
    # Raison du changement (optionnelle)
    reason = models.TextField(
        blank=True,
        null=True,
        verbose_name="Raison"
    )
    
    class Meta:
        verbose_name = "Historique de statut"
        verbose_name_plural = "Historiques de statut"
        ordering = ['-change_date']  # Tri par défaut: du plus récent au plus ancien
        
    def __str__(self):
        """Représentation textuelle de l'entrée d'historique."""
        return f"{self.user.username}: {self.old_status} → {self.new_status}"
    
    def get_old_status_display(self):
        """Retourne l'affichage formaté de l'ancien statut."""
        for status, display in self.STATUS_CHOICES:
            if status == self.old_status:
                return display
        return self.old_status
    
    def get_new_status_display(self):
        """Retourne l'affichage formaté du nouveau statut."""
        for status, display in self.STATUS_CHOICES:
            if status == self.new_status:
                return display
        return self.new_status
    
    @classmethod
    def log_change(cls, user, old_status, new_status, changed_by, reason=None):
        """
        Méthode de classe pour faciliter la création d'une entrée d'historique.
        
        Args:
            user (User): L'utilisateur dont le statut est modifié
            old_status (str): L'ancien statut
            new_status (str): Le nouveau statut
            changed_by (User): L'administrateur qui effectue le changement
            reason (str, optional): La raison du changement
            
        Returns:
            UserStatusHistory: L'entrée d'historique créée
        """
        return cls.objects.create(
            user=user,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by,
            reason=reason
        )


# Exemples d'utilisation:
"""
# 1. Création d'une entrée d'historique lors d'un changement de statut
def admin_user_activate(request, user_id):
    user = get_object_or_404(User, id=user_id)
    old_status = user.status
    user.status = 'active'
    user.save()
    
    # Enregistrer le changement dans l'historique
    UserStatusHistory.objects.create(
        user=user,
        old_status=old_status,
        new_status='active',
        changed_by=request.user
    )
    
    # Ou utiliser la méthode de classe
    UserStatusHistory.log_change(
        user=user,
        old_status=old_status,
        new_status='active',
        changed_by=request.user
    )
    
    return redirect('admin_users')


# 2. Obtenir l'historique complet d'un utilisateur
def user_history(request, user_id):
    user = get_object_or_404(User, id=user_id)
    history = user.status_history.all()  # Utilise le related_name défini dans le modèle
    
    context = {
        'user': user,
        'history': history
    }
    return render(request, 'user_history.html', context)


# 3. Obtenir les changements effectués par un administrateur
def admin_activity(request, admin_id):
    admin = get_object_or_404(User, id=admin_id, is_staff=True)
    changes_made = admin.status_changes_made.all()  # Utilise le related_name pour les changements effectués
    
    context = {
        'admin': admin,
        'changes_made': changes_made
    }
    return render(request, 'admin_activity.html', context)


# 4. Obtenir les statistiques des changements de statut
def status_change_stats():
    # Nombre total de changements par type
    activations = UserStatusHistory.objects.filter(new_status='active').count()
    blocks = UserStatusHistory.objects.filter(new_status='blocked').count()
    
    # Changements par période
    from django.utils import timezone
    from datetime import timedelta
    
    one_week_ago = timezone.now() - timedelta(days=7)
    recent_changes = UserStatusHistory.objects.filter(change_date__gte=one_week_ago).count()
    
    return {
        'activations': activations,
        'blocks': blocks,
        'recent_changes': recent_changes
    }
"""

class ContactMessage(models.Model):
    SUBJECT_CHOICES = [
        ('general', 'General Inquiry'),
        ('technical', 'Technical Support'),
        ('suggestion', 'Suggestion'),
        ('bug', 'Bug Report'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('read', 'Read'),
        ('replied', 'Replied'),
        ('closed', 'Closed'),
    ]
    
    # Utilisateur qui envoie le message (optionnel pour les non-connectés)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    # Informations de contact pour les utilisateurs non connectés
    name = models.CharField(max_length=100)
    email = models.EmailField()
    
    # Contenu du message
    subject = models.CharField(max_length=20, choices=SUBJECT_CHOICES, default='general')
    message = models.TextField()
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_response = models.TextField(blank=True, null=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    responded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='admin_responses')
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.name} - {self.get_subject_display()}"
    
    def save(self, *args, **kwargs):
        # Si l'utilisateur est connecté, préremplir les informations
        if self.user and not self.name:
            self.name = f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username
        if self.user and not self.email:
            self.email = self.user.email
        super().save(*args, **kwargs)



