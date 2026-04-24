from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings

# Configurer la durée maximale d'inactivité avant qu'un utilisateur soit considéré comme déconnecté
ONLINE_THRESHOLD = getattr(settings, 'ONLINE_THRESHOLD', 300)  # 5 minutes en secondes

class UserActivityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Code exécuté à chaque requête
        response = self.get_response(request)
        
        # Mettre à jour le timestamp de dernière activité pour les utilisateurs authentifiés
        if request.user.is_authenticated:
            # Stocker la date/heure de dernière activité dans la session
            request.session['last_activity'] = timezone.now().isoformat()
            
            # Mise à jour moins fréquente de la base de données (optionnel)
            # Cela réduit les écritures en base de données tout en maintenant l'exactitude
            last_db_update = request.session.get('last_db_activity_update')
            if not last_db_update or (timezone.now() - datetime.fromisoformat(last_db_update)) > timedelta(minutes=1):
                # Mettre à jour le profil utilisateur si vous avez un modèle de profil
                if hasattr(request.user, 'profile'):
                    request.user.profile.last_active = timezone.now()
                    request.user.profile.save(update_fields=['last_active'])
                
                # Stocker la dernière mise à jour en base
                request.session['last_db_activity_update'] = timezone.now().isoformat()
        
        return response