import uuid

from django.contrib.auth import get_user_model
from django.core.validators import (
    MaxValueValidator,
    MinLengthValidator,
    MinValueValidator,
)
from django.db import models
from django.utils import timezone
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class Stats(models.Model):
    """Model for platform statistics"""

    date = models.DateField(_("date"), unique=True, default=timezone.now)
    users_count = models.IntegerField(_("nombre d'utilisateurs"), default=0)
    publications_count = models.IntegerField(_("nombre de publications"), default=0)
    corpora_count = models.IntegerField(_("nombre de corpus"), default=0)
    tools_count = models.IntegerField(_("nombre d'outils"), default=0)
    projects_count = models.IntegerField(_("nombre de projets"), default=0)
    forum_posts_count = models.IntegerField(_("nombre de messages forum"), default=0)
    visits_count = models.IntegerField(_("nombre de visites"), default=0)
    downloads_count = models.IntegerField(_("nombre de téléchargements"), default=0)

    class Meta:
        verbose_name = _("statistique")
        verbose_name_plural = _("statistiques")
        ordering = ["-date"]

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
        ("active", "Actif"),
        ("pending", "En attente"),
        ("blocked", "Bloqué"),
        ("new", "Nouveau"),  # Utilisé pour la création initiale
    )

    # Relation avec l'utilisateur dont le statut a été modifié
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,  # Si l'utilisateur est supprimé, son historique l'est aussi
        related_name="status_history",  # Permet d'accéder à l'historique depuis un utilisateur: user.status_history.all()
        verbose_name="Utilisateur",
    )

    # Ancien statut de l'utilisateur
    old_status = models.CharField(max_length=10, verbose_name="Ancien statut")

    # Nouveau statut de l'utilisateur
    new_status = models.CharField(max_length=10, verbose_name="Nouveau statut")

    # Administrateur qui a effectué le changement
    changed_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,  # Si l'admin est supprimé, on garde null comme référence
        null=True,
        related_name="status_changes_made",  # Permet d'accéder aux changements effectués par un admin: admin.status_changes_made.all()
        verbose_name="Modifié par",
    )

    # Date et heure du changement
    change_date = models.DateTimeField(
        default=timezone.now,  # Utilise la date/heure actuelle par défaut
        verbose_name="Date de modification",
    )

    # Raison du changement (optionnelle)
    reason = models.TextField(blank=True, null=True, verbose_name="Raison")

    class Meta:
        verbose_name = "Historique de statut"
        verbose_name_plural = "Historiques de statut"
        ordering = ["-change_date"]  # Tri par défaut: du plus récent au plus ancien

    def __str__(self):
        """Représentation textuelle de l'entrée d'historique."""
        return f"{self.user.email}: {self.old_status} → {self.new_status}"

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
            reason=reason,
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
        ("general", "General Inquiry"),
        ("technical", "Technical Support"),
        ("suggestion", "Suggestion"),
        ("bug", "Bug Report"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("read", "Read"),
        ("replied", "Replied"),
        ("closed", "Closed"),
    ]

    # Utilisateur qui envoie le message (optionnel pour les non-connectés)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    # Informations de contact pour les utilisateurs non connectés
    name = models.CharField(max_length=100)
    email = models.EmailField()

    # Contenu du message
    subject = models.CharField(
        max_length=20, choices=SUBJECT_CHOICES, default="general"
    )
    message = models.TextField()

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    admin_response = models.TextField(blank=True, null=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    responded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_responses",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - {self.get_subject_display()}"

    def save(self, *args, **kwargs):
        # Si l'utilisateur est connecté, préremplir les informations
        if self.user and not self.name:
            self.name = (
                f"{self.user.first_name} {self.user.last_name}".strip()
                or self.user.email
            )
        if self.user and not self.email:
            self.email = self.user.email
        super().save(*args, **kwargs)


class AdminActivityLog(models.Model):
    """
    Security audit trail for custom admin panel actions.
    """

    admin_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="admin_activity_logs",
    )
    role_snapshot = models.CharField(max_length=32, default="user")
    action = models.CharField(max_length=120)
    path = models.CharField(max_length=255, blank=True, default="")
    http_method = models.CharField(max_length=10, blank=True, default="GET")
    target_type = models.CharField(max_length=80, blank=True, default="")
    target_id = models.CharField(max_length=64, blank=True, default="")
    details = models.TextField(blank=True, default="")
    ip_address = models.CharField(max_length=64, blank=True, default="")
    user_agent = models.CharField(max_length=255, blank=True, default="")
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["admin_user", "occurred_at"]),
            models.Index(fields=["action", "occurred_at"]),
        ]
        verbose_name = "Admin activity log"
        verbose_name_plural = "Admin activity logs"

    def __str__(self):
        who = getattr(self.admin_user, "email", "unknown")
        return f"{who} - {self.action} ({self.occurred_at:%Y-%m-%d %H:%M:%S})"


class BlockedUpload(models.Model):
    """
    Security record for blocked file uploads.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blocked_uploads",
    )
    file_name = models.CharField(max_length=255, blank=True, default="")
    reason = models.CharField(max_length=255, blank=True, default="")
    path = models.CharField(max_length=255, blank=True, default="")
    ip_address = models.CharField(max_length=64, blank=True, default="")
    blocked_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-blocked_at"]
        verbose_name = "Blocked upload"
        verbose_name_plural = "Blocked uploads"
        indexes = [
            models.Index(fields=["blocked_at"]),
            models.Index(fields=["ip_address", "blocked_at"]),
        ]

    def __str__(self):
        base = self.file_name or "upload"
        return f"{base} blocked at {self.blocked_at:%Y-%m-%d %H:%M:%S}"


class SecurityLog(models.Model):
    ACTION_CHOICES = [
        ("login", _("Login")),
        ("failed_login", _("Failed Login")),
        ("upload", _("Upload")),
        ("blocked_upload", _("Blocked Upload")),
        ("create", _("Create")),
        ("update", _("Update")),
        ("delete", _("Delete")),
        ("other", _("Other")),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="security_logs",
    )
    role = models.CharField(max_length=32, blank=True, default="member")
    action = models.CharField(max_length=32, choices=ACTION_CHOICES, default="other")
    method = models.CharField(max_length=10, blank=True, default="GET")
    ip_address = models.CharField(max_length=64, blank=True, default="")
    path = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Security Log")
        verbose_name_plural = _("Security Logs")
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["role", "created_at"]),
        ]

    def __str__(self):
        actor = getattr(self.user, "email", "anonymous")
        return f"{self.action} by {actor} at {self.created_at:%Y-%m-%d %H:%M:%S}"


class Opportunity(models.Model):
    TYPE_JOB = "job"
    TYPE_INTERNSHIP = "internship"
    TYPE_PFE = "pfe"
    TYPE_PHD = "phd"
    TYPE_COLLAB = "collab"

    MODE_REMOTE = "remote"
    MODE_HYBRID = "hybrid"
    MODE_ONSITE = "onsite"

    LEVEL_STUDENT = "student"
    LEVEL_JUNIOR = "junior"
    LEVEL_SENIOR = "senior"
    LEVEL_RESEARCHER = "researcher"

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    SCRAPE_STATUS_APPROVED = "APPROVED"
    SCRAPE_STATUS_PENDING_REVIEW = "PENDING_REVIEW"
    SCRAPE_STATUS_REJECTED = "REJECTED"

    TYPE_CHOICES = [
        (TYPE_JOB, _("Job")),
        (TYPE_INTERNSHIP, _("Internship")),
        (TYPE_PFE, _("PFE / Master")),
        (TYPE_PHD, _("PhD")),
        (TYPE_COLLAB, _("Collaboration")),
    ]

    MODE_CHOICES = [
        (MODE_REMOTE, _("Remote")),
        (MODE_HYBRID, _("Hybrid")),
        (MODE_ONSITE, _("On-site")),
    ]

    LEVEL_CHOICES = [
        (LEVEL_STUDENT, _("Student")),
        (LEVEL_JUNIOR, _("Junior")),
        (LEVEL_SENIOR, _("Senior")),
        (LEVEL_RESEARCHER, _("Researcher")),
    ]

    STATUS_CHOICES = [
        (STATUS_PENDING, _("Pending")),
        (STATUS_APPROVED, _("Approved")),
        (STATUS_REJECTED, _("Rejected")),
    ]

    SCRAPE_STATUS_CHOICES = [
        (SCRAPE_STATUS_APPROVED, _("Approved")),
        (SCRAPE_STATUS_PENDING_REVIEW, _("Pending review")),
        (SCRAPE_STATUS_REJECTED, _("Rejected")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, blank=True, default="")
    title_en = models.CharField(max_length=255)
    title_ar = models.CharField(max_length=255)
    opportunity_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    institution = models.ForeignKey(
        "institutions.Institution",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="opportunities",
    )
    organization_en = models.CharField(max_length=255, blank=True, default="")
    organization_ar = models.CharField(max_length=255, blank=True, default="")
    location = models.CharField(max_length=255)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES)
    description = models.TextField(validators=[MinLengthValidator(40)])
    skills = models.JSONField(default=list, blank=True)
    contact = models.CharField(max_length=255)
    deadline = models.DateField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True
    )
    scrape_status = models.CharField(
        max_length=20,
        choices=SCRAPE_STATUS_CHOICES,
        default=SCRAPE_STATUS_PENDING_REVIEW,
        db_index=True,
    )
    validation_notes = models.TextField(blank=True, default="")
    confidence_score = models.FloatField(null=True, blank=True, db_index=True)
    last_scraped_at = models.DateTimeField(null=True, blank=True, db_index=True)
    update_counter = models.PositiveIntegerField(default=0)
    approval_status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True
    )
    is_published = models.BooleanField(default=False, db_index=True)
    user_role = models.CharField(max_length=32, default="user")
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="opportunities_created",
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="opportunities_moderated",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "is_published"]),
            models.Index(fields=["approval_status", "created_at"]),
            models.Index(fields=["created_by", "status"]),
            models.Index(fields=["deadline"]),
        ]
        verbose_name = _("Opportunity")
        verbose_name_plural = _("Opportunities")

    def __str__(self):
        return self.title or self.title_en or self.title_ar or str(self.pk)

    def save(self, *args, **kwargs):
        self.title = (self.title_en or self.title_ar or self.title or "").strip()
        if self.status in {
            self.STATUS_PENDING,
            self.STATUS_APPROVED,
            self.STATUS_REJECTED,
        }:
            self.approval_status = self.status
        elif self.approval_status in {
            self.STATUS_PENDING,
            self.STATUS_APPROVED,
            self.STATUS_REJECTED,
        }:
            self.status = self.approval_status
        super().save(*args, **kwargs)

    def get_localized_title(self):
        lang = (get_language() or "").lower()
        if lang.startswith("ar") and self.title_ar:
            return self.title_ar
        return self.title_en or self.title_ar or self.title


def news_cover_upload_to(instance, filename):
    return f"news/covers/{timezone.now():%Y/%m}/{filename}"


def news_pdf_upload_to(instance, filename):
    return f"news/pdfs/{timezone.now():%Y/%m}/{filename}"


class NewsPublication(models.Model):
    TYPE_PAPER = "paper"
    TYPE_DATASET = "dataset"
    TYPE_TOOL = "tool"
    TYPE_EVENT = "event"
    TYPE_THESIS = "thesis"
    TYPE_NEWS = "news"

    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"

    TYPE_CHOICES = [
        (TYPE_PAPER, _("Paper")),
        (TYPE_DATASET, _("Dataset")),
        (TYPE_TOOL, _("Tool")),
        (TYPE_EVENT, _("Event")),
        (TYPE_THESIS, _("Thesis")),
        (TYPE_NEWS, _("News")),
    ]

    STATUS_CHOICES = [
        (STATUS_DRAFT, _("Draft")),
        (STATUS_PUBLISHED, _("Published")),
    ]

    title = models.CharField(max_length=120)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_NEWS)
    abstract = models.TextField(validators=[MinLengthValidator(150)])
    authors = models.JSONField(default=list, blank=True)
    affiliations = models.CharField(max_length=255, blank=True, default="")
    year = models.IntegerField(
        validators=[MinValueValidator(1900), MaxValueValidator(2100)],
        default=timezone.now().year,
    )
    venue = models.CharField(max_length=255, blank=True, default="")
    nlp_tasks = models.JSONField(default=list, blank=True)
    languages = models.JSONField(default=list, blank=True)
    keywords = models.JSONField(default=list, blank=True)
    doi = models.CharField(max_length=255, blank=True, null=True)
    pdf_url = models.URLField(blank=True, null=True)
    github_url = models.URLField(blank=True, null=True)
    dataset_url = models.URLField(blank=True, null=True)
    demo_url = models.URLField(blank=True, null=True)
    cover_image = models.ImageField(
        upload_to=news_cover_upload_to, blank=True, null=True
    )
    pdf_file = models.FileField(upload_to=news_pdf_upload_to, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PUBLISHED,
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="news_publications",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year", "-created_at"]
        indexes = [
            models.Index(fields=["type", "status"]),
            models.Index(fields=["year", "status"]),
            models.Index(fields=["created_at"]),
        ]
        verbose_name = _("News Publication")
        verbose_name_plural = _("News Publications")

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("pages:publication_detail", kwargs={"publication_id": self.pk})

    @property
    def authors_display(self):
        return ", ".join(self.authors or [])

    @property
    def cover_image_url(self):
        if self.cover_image:
            return self.cover_image.url
        return ""

    @property
    def pdf_file_url(self):
        if self.pdf_file:
            return self.pdf_file.url
        return ""

    @property
    def type_icon(self):
        return {
            self.TYPE_PAPER: "fa-file-lines",
            self.TYPE_DATASET: "fa-database",
            self.TYPE_TOOL: "fa-screwdriver-wrench",
            self.TYPE_EVENT: "fa-calendar-days",
            self.TYPE_THESIS: "fa-graduation-cap",
            self.TYPE_NEWS: "fa-newspaper",
        }.get(self.type, "fa-newspaper")

    @property
    def type_color(self):
        return {
            self.TYPE_PAPER: "#3B82F6",
            self.TYPE_DATASET: "#1D9E75",
            self.TYPE_TOOL: "#F59E0B",
            self.TYPE_EVENT: "#FF7F50",
            self.TYPE_THESIS: "#534AB7",
            self.TYPE_NEWS: "#6B7280",
        }.get(self.type, "#6B7280")
