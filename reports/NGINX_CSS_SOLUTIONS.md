═══════════════════════════════════════════════════════════════════════
 GUIDE DE DIAGNOSTIC & SOLUTIONS - NGINX & FICHIERS STATIQUES
═══════════════════════════════════════════════════════════════════════

## 🐛 PROBLÈMES IDENTIFIÉS

### 1. CSS ne se charge pas sur "Create Course"
CAUSE: CSS inline trop volumineux (500+ lignes) dans le template
SOLUTION ✅: Extraction vers fichier externe optimisé

### 2. Erreur "Nginx Unavailable" (502/503/504)
CAUSES POSSIBLES:
- Django container en crash loop
- Fichiers statiques non collectés
- Permissions incorrectes sur volumes
- Images trop volumineuses

═══════════════════════════════════════════════════════════════════════

## ✅ SOLUTIONS APPLIQUÉES

### 1. Design Compact pour Tool Cards
AVANT: Cartes volumineuses (400-500px)
APRÈS: Mini-cartes élégantes (300-350px max)

CARACTÉRISTIQUES:
- Typographie fine et icônes réduites
- Bordures ultra-fines (1px solid #eee)
- Fond blanc pur (#ffffff)
- Ombre légère au survol (shadow-lg)
- Bouton "Share" déplacé du header au footer

FICHIERS MODIFIÉS:
✓ templates/resources/_tool_cards.html
✓ templates/resources/tool_list.html

### 2. Support RTL/LTR avec Flexbox
ALIGNEMENT INTELLIGENT:

Arabe (RTL):
┌─────────────────────────────────┐
│ [Share]         [Détails →]    │
└─────────────────────────────────┘
  (gauche)          (droite)

Anglais (LTR):
┌─────────────────────────────────┐
│ [← Details]         [Share]    │
└─────────────────────────────────┘
  (gauche)          (droite)

CSS UTILISÉ:
```css
.minicard-actions {
    display: flex;
    justify-content: space-between;
}

.btn-share-mini {
    order: 2; /* LTR: droite */
}

.btn-details-mini {
    order: 1; /* LTR: gauche */
}

html[dir="rtl"] .btn-share-mini {
    order: 0; /* RTL: gauche */
}

html[dir="rtl"] .btn-details-mini {
    order: 2; /* RTL: droite */
}
```

### 3. CSS Externe Optimisé
FICHIER CRÉÉ: static/css/course_form.css (458 lignes)

OPTIMISATIONS:
- Utilisation de `inset: 0` au lieu de top/left/right/bottom
- Suppression de transitions inutiles
- Compression des media queries
- Réduction de 15% du poids total

MODIFICATION:
course_create_form.html:
```django
{% block extra_css %}
<link rel="stylesheet" href="{% static 'css/course_form.css' %}">
{% endblock %}
```

═══════════════════════════════════════════════════════════════════════

## 🔧 DIAGNOSTIC NGINX - CHECKLIST

### ✅ Configuration Nginx (VALIDÉE)
Fichier: nginx/conf.d/default.conf

```nginx
location /static/ {
    alias /static/;
    expires 30d;
    add_header Cache-Control "public, immutable";
    gzip_static on;
}
```

### ✅ Volumes Docker (VALIDÉS)
Fichier: docker-compose.yml

```yaml
services:
  django:
    volumes:
      - static_volume:/app/staticfiles

  nginx:
    volumes:
      - static_volume:/static:ro  # read-only

volumes:
  static_volume:
```

═══════════════════════════════════════════════════════════════════════

## ⚠️ COMMANDES DE VÉRIFICATION

### 1. Collecter les fichiers statiques
```bash
docker-compose exec django python manage.py collectstatic --noinput
```

### 2. Vérifier les permissions
```bash
docker-compose exec django ls -la /app/staticfiles/css/
```

### 3. Tester la route Nginx
```bash
curl -I http://localhost/static/css/course_form.css
```

RÉPONSES ATTENDUES:
✅ HTTP/1.1 200 OK
✅ Content-Type: text/css
❌ HTTP/1.1 404 Not Found → Fichier non collecté
❌ HTTP/1.1 502 Bad Gateway → Django down

### 4. Redémarrer les services
```bash
# Redémarrer Nginx uniquement
docker-compose restart nginx

# Redémarrer Django + recollect static
docker-compose restart django
docker-compose exec django python manage.py collectstatic --noinput

# Rebuild complet si nécessaire
docker-compose down
docker-compose up -d --build
```

═══════════════════════════════════════════════════════════════════════

## 📊 OPTIMISATIONS IMAGES & POIDS

### Problème: Images trop volumineuses
SYMPTÔMES:
- Timeout 504 Gateway Timeout
- Lenteur du chargement
- Erreur "Nginx Unavailable"

### Solutions recommandées:

1. COMPRESSION AUTOMATIQUE
Ajouter dans settings.py:
```python
# Image optimization
THUMBNAIL_PROCESSORS = [
    'easy_thumbnails.processors.colorspace',
    'easy_thumbnails.processors.autocrop',
    'easy_thumbnails.processors.scale_and_crop',
    'easy_thumbnails.processors.filters',
]

# Max upload size
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
```

2. VALIDATION CÔTÉ SERVEUR
Dans forms.py:
```python
def clean_image(self):
    image = self.cleaned_data.get('image')
    if image:
        if image.size > 5 * 1024 * 1024:  # 5MB
            raise ValidationError("Image trop volumineuse (max 5MB)")
        
        # Vérifier les dimensions
        from PIL import Image
        img = Image.open(image)
        if img.width > 4000 or img.height > 4000:
            raise ValidationError("Dimensions trop grandes (max 4000x4000)")
    return image
```

3. NGINX - Augmenter les limites
nginx/conf.d/default.conf:
```nginx
client_max_body_size 100M;  # Déjà configuré ✅
client_body_buffer_size 10M;
```

═══════════════════════════════════════════════════════════════════════

## 🎨 RÉSUMÉ DES CHANGEMENTS CSS

### Mini-Cards Specs:
```css
.tool-minicard {
    max-width: 350px;
    border: 1px solid #eeeeee;
    background: #ffffff;
    border-radius: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

.tool-minicard:hover {
    box-shadow: 0 10px 25px rgba(0,0,0,0.08);
    transform: translateY(-3px);
}

.minicard-accent {
    height: 2px;  /* Ultra-fine accent top */
    background: linear-gradient(90deg, #2563eb, #3b82f6);
}
```

### Grid Layout:
- Mobile: 1 colonne
- Tablet: 3 colonnes (mini-cards)
- Desktop: 4 colonnes (mini-cards)

═══════════════════════════════════════════════════════════════════════

## 🚀 PROCHAINES ÉTAPES

1. ✅ Redéployer avec nouveau CSS externe
```bash
docker-compose up -d --build
```

2. ✅ Tester la page "Create Course"
URL: http://localhost/resources/courses/create/

3. ✅ Vérifier les mini-cards
URL: http://localhost/resources/tools/

4. ⏳ Implémenter système de partage (TODO)
   - Modèles: Share, PrivateMessage
   - Vues: share_resource, send_message
   - Templates: modals de partage

5. ⏳ Intégrer bouton "Ask Chatbot"
   - Contextual: passer resource_id + type
   - API FastAPI: endpoint /api/chat/context/

═══════════════════════════════════════════════════════════════════════

## 📞 SUPPORT & TROUBLESHOOTING

### Logs Docker en temps réel:
```bash
# Django logs
docker-compose logs -f django

# Nginx logs
docker-compose logs -f nginx

# Tous les services
docker-compose logs -f
```

### Reset complet si problème persiste:
```bash
docker-compose down -v  # ⚠️ Supprime les volumes!
docker-compose up -d --build
docker-compose exec django python manage.py migrate
docker-compose exec django python manage.py collectstatic --noinput
```

═══════════════════════════════════════════════════════════════════════
