from django.utils import timezone
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from .models import Project, ProjectMember, ProjectInvitation
from django.db.models import Q
from django.db.models import Exists, OuterRef
from django.urls import reverse, reverse_lazy
from django.core.paginator import Paginator
from .forms import ProjectForm
from django.contrib.auth import get_user_model
from notifications.models import Notification
from django.contrib import messages
from notifications.services import NotificationService, LocalizedValue
from accounts.views import LoginAndVerifiedRequiredMixin
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from typing import TYPE_CHECKING, Any
from django.db.models.query import QuerySet
from django.http import HttpRequest, HttpResponse
from django.http import JsonResponse, Http404, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from accounts.models import Friendship
import logging
import re
from accounts.blocking import exclude_hidden_users
from django.views.decorators.http import require_http_methods
from django.utils.html import escape
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .forms import ProjectChatMessageForm
from .models import ProjectChatRoom, ProjectChatMessage

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from django.forms import BaseModelForm


def detect_language(query: str) -> str:
    """Detect if query is primarily Arabic or English."""
    if not query:
        return "english"

    arabic_pattern = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+")
    arabic_chars = len(arabic_pattern.findall(query))
    total_chars = len(query.replace(" ", ""))

    if total_chars == 0:
        return "english"

    if arabic_chars / total_chars > 0.3:
        return "arabic"
    return "english"


def _can_manage_project_invitations(project: Project, user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user == project.coordinator:
        return True
    return ProjectMember.objects.filter(
        project=project,
        member=user,
        status="accepted",
        role__iexact="admin",
    ).exists()


def _ensure_project_chatroom(project: Project) -> ProjectChatRoom:
    room, _ = ProjectChatRoom.objects.get_or_create(project=project)
    return room


def _serialize_user(user, pending_ids):
    display_name = getattr(user, "get_full_name_display", None)
    if callable(display_name):
        display_name = display_name()
    display_name = (display_name or user.email or "").strip()
    avatar_url = ""
    try:
        if getattr(user, "avatar", None):
            avatar_url = user.avatar.url
    except Exception:
        avatar_url = ""
    return {
        "id": str(user.pk),
        "name": display_name,
        "username": getattr(user, "username", "") or "",
        "email": user.email,
        "avatar": avatar_url,
        "already_invited": str(user.pk) in pending_ids,
    }


class ProjectListView(LoginAndVerifiedRequiredMixin, ListView):
    model = Project
    template_name = "project_list.html"
    context_object_name = "projects"
    paginate_by = 10

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """Handle both AJAX and regular requests."""
        # Check if this is an AJAX request
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

        if is_ajax:
            return self._handle_ajax_request(request)

        # Regular HTML request
        return super().get(request, *args, **kwargs)

    def _handle_ajax_request(self, request: HttpRequest) -> HttpResponse:
        """Return partial HTML for AJAX search requests."""
        from django.http import JsonResponse

        # Get the search query and filters
        search_query = request.GET.get("q", "").strip()

        # Get projects using Elasticsearch if query exists, else use standard queryset
        if search_query:
            projects, highlights = self._search_with_elasticsearch(
                search_query, request
            )
        else:
            projects = list(self.get_queryset())
            highlights = {}

        page_number = request.GET.get("page") or 1
        paginator = Paginator(projects, self.paginate_by)
        page_obj = paginator.get_page(page_number)

        # Build context for partial template
        context = {
            "projects": page_obj,
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": page_obj.has_other_pages(),
            "highlights": highlights,
            "search_query": search_query,
            "request": request,
        }

        # Render partial template
        html = render_to_string(
            "projects/_project_cards.html", context, request=request
        )

        return HttpResponse(html)

    def _search_with_elasticsearch(
        self, query: str, request: HttpRequest
    ) -> tuple[list[Project], dict]:
        """
        Search projects using Elasticsearch with highlighting.
        Returns a tuple of (projects, highlights_dict).
        """
        from elasticsearch_dsl import Q as ESQ
        from elasticsearch.exceptions import ConnectionError, NotFoundError

        try:
            from search.documents import ProjectDocument
        except ImportError:
            logger.warning("ProjectDocument not found, falling back to DB search")
            return list(self.get_queryset()), {}

        try:
            detected_lang = detect_language(query)

            # Build the search query with dis_max for ranking
            search_fields = [
                "title^3",
                "title.arabic^3",
                "title.english^3",
                "title.phonetic^1",
                "description^2",
                "description.arabic^2",
                "description.english^2",
                "coordinator.full_name^1.5",
                "institution.name^1.5",
                "institution.name.arabic^1.5",
                "institution.name.english^1.5",
            ]

            # Build multi_match query
            es_query = ESQ(
                "multi_match",
                query=query,
                fields=search_fields,
                type="best_fields",
                fuzziness="AUTO",
                prefix_length=1,
            )

            # Create search
            search = ProjectDocument.search()
            search = search.query(es_query)

            # Apply filters
            # Status filter
            status_filter = request.GET.get("status", "").strip()
            if status_filter:
                search = search.filter("term", **{"status.raw": status_filter})

            # My projects filter (coordinator)
            if request.GET.get("my_projects"):
                search = search.filter("term", **{"coordinator.id": request.user.id})

            # Sorting
            sort_by = request.GET.get("sort", "newest").strip()
            if sort_by == "oldest":
                search = search.sort(
                    {"created_at": {"order": "asc", "unmapped_type": "date"}}
                )
            elif sort_by == "alphabetical":
                search = search.sort(
                    {"title.raw": {"order": "asc", "unmapped_type": "keyword"}}
                )
            elif sort_by == "updated":
                # Use date_end or fall back to created_at for "updated"
                search = search.sort(
                    {"date_end": {"order": "desc", "unmapped_type": "date"}}
                )
            else:  # newest (default) - but for search, prefer relevance
                pass  # Keep relevance-based sorting from ES

            # Add highlighting
            search = search.highlight_options(
                pre_tags=['<mark class="search-highlight">'],
                post_tags=["</mark>"],
                encoder="html",
                fragment_size=200,
            )
            search = search.highlight("title", "title.arabic", "title.english")
            search = search.highlight(
                "description", "description.arabic", "description.english"
            )

            # Execute search (limit to reasonable number)
            search = search[:50]
            response = search.execute()

            # Collect project IDs and highlights
            project_ids = []
            highlights = {}

            for hit in response:
                project_id = hit.meta.id
                project_ids.append(project_id)

                # Extract highlights
                if hasattr(hit.meta, "highlight"):
                    hit_highlights = {}
                    highlight_dict = hit.meta.highlight.to_dict()

                    # Get title highlight (check all variants)
                    for field in ["title", "title.arabic", "title.english"]:
                        if field in highlight_dict:
                            hit_highlights["title"] = highlight_dict[field][0]
                            break

                    # Get description highlight
                    for field in [
                        "description",
                        "description.arabic",
                        "description.english",
                    ]:
                        if field in highlight_dict:
                            hit_highlights["description"] = highlight_dict[field][0]
                            break

                    if hit_highlights:
                        highlights[str(project_id)] = hit_highlights

            if not project_ids:
                return [], {}

            # Fetch actual Project objects from database
            # Preserve Elasticsearch ordering
            membership = ProjectMember.objects.filter(
                project=OuterRef("pk"), member=request.user
            )

            projects_qs = Project.objects.filter(pk__in=project_ids)
            projects_qs = exclude_hidden_users(
                projects_qs, request.user, ("coordinator",)
            )

            # Public list is approved-only. "My projects" can include owner's pending.
            if request.GET.get("my_projects"):
                projects_qs = projects_qs.filter(coordinator=request.user)
            else:
                projects_qs = projects_qs.filter(approval_status="approved")

            projects_qs = projects_qs.annotate(is_member=Exists(membership))

            # Convert to dict for ordering
            projects_dict = {str(p.pk): p for p in projects_qs}

            # Preserve ES ordering
            ordered_projects = []
            for pid in project_ids:
                if str(pid) in projects_dict:
                    ordered_projects.append(projects_dict[str(pid)])

            return ordered_projects, highlights

        except (ConnectionError, NotFoundError) as e:
            logger.warning(f"Elasticsearch unavailable, falling back to DB: {e}")
            return list(self.get_queryset()), {}
        except Exception as e:
            logger.error(f"Elasticsearch search error: {e}")
            return list(self.get_queryset()), {}

    def get_queryset(self) -> QuerySet[Project]:
        qs = super().get_queryset()
        qs = exclude_hidden_users(qs, self.request.user, ("coordinator",))

        # Public projects list is strictly approved-only.
        if self.request.GET.get("my_projects"):
            qs = qs.filter(coordinator=self.request.user)
        else:
            qs = qs.filter(approval_status="approved")

        membership = ProjectMember.objects.filter(
            project=OuterRef("pk"), member=self.request.user
        )

        # Ajouter le filtre par statut
        status_filter = self.request.GET.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        # Ajouter la recherche (support both 'q' and 'search' for compatibility)
        search_query = self.request.GET.get("q") or self.request.GET.get("search", "")
        if search_query:
            qs = qs.filter(
                Q(title__icontains=search_query)
                | Q(title_ar__icontains=search_query)
                | Q(title_en__icontains=search_query)
                | Q(description__icontains=search_query)
                | Q(description_ar__icontains=search_query)
                | Q(description_en__icontains=search_query)
                | Q(institution__name__icontains=search_query)
                | Q(institution__acronym__icontains=search_query)
                | Q(coordinator__full_name__icontains=search_query)
                | Q(coordinator__username__icontains=search_query)
            )

        # Sorting functionality
        sort_by = self.request.GET.get("sort", "newest").strip()
        if sort_by == "oldest":
            qs = qs.order_by("created_at")
        elif sort_by == "alphabetical":
            qs = qs.order_by("title")
        elif sort_by == "updated":
            qs = qs.order_by("-updated_at")
        else:  # newest (default)
            qs = qs.order_by("-created_at")

        return qs.annotate(is_member=Exists(membership))

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["project_statuses"] = Project.STATUS_CHOICES
        context["page"] = "research_projects"
        context["search_query"] = self.request.GET.get("q") or self.request.GET.get(
            "search", ""
        )
        context["current_sort"] = self.request.GET.get("sort", "newest").strip()
        context["highlights"] = {}  # Empty for non-AJAX requests (no ES highlighting)
        context["pending_project_invitations_count"] = ProjectInvitation.objects.filter(
            invited_user=self.request.user,
            status=ProjectInvitation.Status.PENDING,
        ).count()
        return context


class ProjectDetailView(LoginAndVerifiedRequiredMixin, DetailView):
    model = Project
    template_name = "project_detail.html"
    context_object_name = "project"

    def get_queryset(self) -> QuerySet[Project]:
        qs = super().get_queryset()
        qs = exclude_hidden_users(qs, self.request.user, ("coordinator",))
        if self.request.user.is_staff or self.request.user.is_superuser:
            return qs
        return qs.filter(approval_status="approved")

    def get_object(self, queryset: QuerySet[Project] | None = None) -> Project:
        project: Project = super().get_object(queryset)  # type: ignore[assignment]
        if (
            not (self.request.user.is_staff or self.request.user.is_superuser)
            and project.approval_status != "approved"
        ):
            raise Http404(_("Project not found."))
        return project

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        project: Project = self.get_object()  # type: ignore[assignment]

        # Récupérer les membres de l'équipe (exclure les rejetés)
        team_members = project.members.filter(status="accepted").select_related(
            "member"
        )

        # Récupérer les demandes en attente
        pending_requests = project.members.filter(status="pending").select_related(
            "member"
        )

        # Récupérer les demandes de départ en attente
        leave_requests = project.members.filter(
            status="accepted", leave_request_status="pending"
        ).select_related("member")

        # Vérifier le statut du membre actuel
        current_member = project.members.filter(
            member=self.request.user, status="accepted"
        ).first()

        context.update(
            {
                "team_members": [pm.member for pm in team_members],
                "pending_requests": pending_requests,
                "leave_requests": leave_requests,
                "is_coordinator": project.coordinator == self.request.user,
                "can_invite_members": _can_manage_project_invitations(
                    project, self.request.user
                ),
                "is_member": current_member is not None,
                "has_pending_request": project.members.filter(
                    member=self.request.user, status="pending"
                ).exists(),
                "has_pending_leave_request": current_member
                and current_member.leave_request_status == "pending"
                if current_member
                else False,
                "leave_request_rejected": current_member
                and current_member.leave_request_status == "rejected"
                if current_member
                else False,
                "pending_invitations_count": project.invitations.filter(
                    status=ProjectInvitation.Status.PENDING
                ).count(),
            }
        )
        context["page"] = "research_projects"
        return context


class ProjectCreateView(LoginAndVerifiedRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = "project_new.html"
    success_url = reverse_lazy("projects:project_list")

    def form_valid(self, form: "BaseModelForm") -> HttpResponse:  # type: ignore[override]
        import logging

        logger = logging.getLogger(__name__)

        # Set coordinator and approval status
        form.instance.coordinator = self.request.user
        try:
            response = super().form_valid(form)
        except Exception as e:
            # post_save ES signal may raise BulkIndexError even though DB write succeeded
            if Project.objects.filter(pk=form.instance.pk).exists():
                logger.warning(
                    "ES indexing error during project creation (project saved OK): %s",
                    e,
                )
                response = redirect(self.success_url)
            else:
                raise
        # Ensure project discussion room exists immediately after project creation.
        _ensure_project_chatroom(form.instance)
        # Show pending approval message - don't notify all users until approved
        messages.info(
            self.request,
            _(
                "Your project '%(title)s' has been submitted and is pending admin review."
            )
            % {"title": form.instance.title},
        )
        return response

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["page"] = "research_projects"
        return context


class ProjectUpdateView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = "project_update.html"
    success_url = reverse_lazy("projects:project_list")

    def get_object(self, queryset: QuerySet[Project] | None = None) -> Project:
        project: Project = super().get_object(queryset)  # type: ignore[assignment]
        if (
            not (self.request.user.is_staff or self.request.user.is_superuser)
            and project.approval_status != "approved"
        ):
            raise Http404(_("Project not found."))
        return project

    def test_func(self) -> bool:
        obj: Project = self.get_object()  # type: ignore[assignment]
        return (
            self.request.user.is_staff
            or self.request.user.is_superuser
            or obj.coordinator == self.request.user
        )

    def form_valid(self, form: "BaseModelForm") -> HttpResponse:  # type: ignore[override]
        project = form.instance

        try:
            response = super().form_valid(form)
        except Exception as e:
            if Project.objects.filter(pk=project.pk).exists():
                logger.warning(
                    "ES indexing error during project update (project saved OK): %s", e
                )
                response = redirect(self.success_url)
            else:
                raise

        # Handle bilingual fields from POST AFTER form save
        # (form.save() overwrites current-language bilingual field from generic field)
        if self.request.user.is_staff:
            bilingual_updates = {}
            for field_name in (
                "title_ar",
                "title_en",
                "description_ar",
                "description_en",
            ):
                value = self.request.POST.get(field_name, "").strip()
                if value:
                    bilingual_updates[field_name] = value
            if bilingual_updates:
                project.refresh_from_db()
                for field_name, value in bilingual_updates.items():
                    setattr(project, field_name, value)
                try:
                    project.save(update_fields=list(bilingual_updates.keys()))
                except Exception as e:
                    logger.warning(
                        "ES indexing error during bilingual update (saved OK): %s", e
                    )

        # Handle "Approve & Publish" button
        if self.request.POST.get("approve_and_publish") and self.request.user.is_staff:
            project.refresh_from_db()
            missing = []
            if not (project.title_ar or "").strip():
                missing.append(str(_("Title (Arabic)")))
            if not (project.title_en or "").strip():
                missing.append(str(_("Title (English)")))
            if not (project.description_ar or "").strip():
                missing.append(str(_("Description (Arabic)")))
            if not (project.description_en or "").strip():
                missing.append(str(_("Description (English)")))

            if missing:
                messages.error(
                    self.request,
                    _("Cannot approve: Missing translations for %(fields)s.")
                    % {"fields": ", ".join(missing)},
                )
                return redirect(self.request.get_full_path())

            project.approval_status = "approved"
            try:
                project.save(update_fields=["approval_status"])
            except Exception as e:
                logger.warning(
                    "ES indexing error during project approval (saved OK): %s", e
                )

            # Notify coordinator
            coordinator = project.coordinator
            if coordinator:
                NotificationService.create_notification(
                    recipient=coordinator,
                    notification_type="POST_APPROVED",
                    title=_("Your project has been approved"),
                    message=_(
                        "Your project '%(title)s' has been approved and is now visible to the public."
                    ),
                    message_kwargs={"title": project.title},
                )

            messages.success(
                self.request,
                _("'%(title)s' has been approved and published.")
                % {"title": project.title},
            )
            return redirect(f"{reverse('pages:admin_projects')}?tab=pending")

        # In review mode, redirect back to admin after save draft
        if self.request.GET.get("review") == "1" and self.request.user.is_staff:
            messages.success(self.request, _("Draft saved successfully."))
            return redirect(f"{reverse('pages:admin_projects')}?tab=pending")

        # In admin edit-only mode, return to review detail page for approve/reject actions.
        if (
            self.request.user.is_staff
            and self.request.GET.get("edit_only") == "1"
            and self.request.GET.get("review_model")
            and self.request.GET.get("review_pk")
        ):
            return redirect(
                "pages:admin_view_item",
                model_type=self.request.GET.get("review_model"),
                pk=self.request.GET.get("review_pk"),
            )

        return response

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["page"] = "research_projects"
        context["review_mode"] = self.request.GET.get("review") == "1"
        project = self.get_object()
        context["is_pending"] = project.approval_status == "pending"
        context["project"] = project
        return context


class ProjectDeleteView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Project
    template_name = "project_delete.html"
    success_url = reverse_lazy("projects:project_list")

    def test_func(self) -> bool:
        obj: Project = self.get_object()  # type: ignore[assignment]
        return (
            self.request.user.is_staff
            or self.request.user.is_superuser
            or obj.coordinator == self.request.user
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["page"] = "research_projects"
        return context


class JoinProjectView(LoginAndVerifiedRequiredMixin, View):
    def post(self, request: HttpRequest, pk: str) -> HttpResponse:
        project: Project = get_object_or_404(Project, pk=pk)  # type: ignore[assignment]

        # Vérifier si le projet est terminé
        if project.status == "completed":
            messages.error(
                request,
                "This project is closed and is no longer accepting new members.",
            )
            return redirect("projects:project_detail", pk=pk)

        # Vérifie si l'utilisateur n'est pas déjà membre
        if not ProjectMember.objects.filter(
            project=project, member=request.user
        ).exists():
            # Créer une demande en attente
            ProjectMember.objects.create(
                project=project, member=request.user, role="member", status="pending"
            )
            # Notification au coordinateur du projet via le service
            NotificationService.create_membership_request(
                recipient=project.coordinator, project=project, sender=request.user
            )
            messages.success(
                request,
                "Your membership request has been sent to the project coordinator.",
            )
        return redirect("projects:project_detail", pk=pk)


class AcceptMemberView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, View):
    def test_func(self) -> bool:
        project: Project = get_object_or_404(Project, pk=self.kwargs["pk"])  # type: ignore[assignment]
        return self.request.user == project.coordinator

    def post(self, request: HttpRequest, pk: str, member_id: str) -> HttpResponse:
        project: Project = get_object_or_404(Project, pk=pk)  # type: ignore[assignment]
        member = get_object_or_404(ProjectMember, project=project, member_id=member_id)

        if member.status == "pending":
            member.status = "accepted"
            member.save()
            _ensure_project_chatroom(project)

            # Notification au membre accepté via le service
            NotificationService.create_notification(
                recipient=member.member,
                notification_type="SYSTEM",
                title=_("Membership application accepted"),
                message=_(
                    "Your request to join the project « %(title)s » was accepted."
                ),
                message_kwargs={"title": project.title},
            )
            messages.success(
                request,
                _("%(name)s was accepted into the project.")
                % {"name": member.member.full_name},
            )  # type: ignore[attr-defined]

        return redirect("projects:project_members", pk=pk)


class RejectMemberView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, View):
    def test_func(self) -> bool:
        project: Project = get_object_or_404(Project, pk=self.kwargs["pk"])  # type: ignore[assignment]
        return self.request.user == project.coordinator

    def post(self, request: HttpRequest, pk: str, member_id: str) -> HttpResponse:
        project: Project = get_object_or_404(Project, pk=pk)  # type: ignore[assignment]
        member = get_object_or_404(ProjectMember, project=project, member_id=member_id)

        if member.status == "pending":
            member.status = "rejected"
            member.save()

            # Notification au membre refusé via le service
            NotificationService.create_notification(
                recipient=member.member,
                notification_type="SYSTEM",
                title=_("Membership application refused"),
                message=_(
                    "Your request to join the project « %(title)s » was refused."
                ),
                message_kwargs={"title": project.title},
            )
            messages.success(
                request,
                _("The request for %(name)s was refused.")
                % {"name": member.member.full_name},
            )  # type: ignore[attr-defined]

        return redirect("projects:project_members", pk=pk)


class ProjectMembersView(
    LoginAndVerifiedRequiredMixin, UserPassesTestMixin, DetailView
):
    model = Project
    template_name = "project_members.html"
    context_object_name = "project"

    def test_func(self) -> bool:
        project: Project = self.get_object()  # type: ignore[assignment]
        return self.request.user == project.coordinator

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        project: Project = self.object  # type: ignore[assignment]
        context["pending_members"] = project.members.filter(status="pending")
        context["accepted_members"] = project.members.filter(status="accepted")
        context["rejected_members"] = project.members.filter(status="rejected")
        context["leave_requests"] = project.members.filter(
            status="accepted", leave_request_status="pending"
        )
        context["page"] = "research_projects"
        return context


class ProjectUserLookupView(LoginAndVerifiedRequiredMixin, View):
    def get(self, request: HttpRequest, pk: str) -> HttpResponse:
        project: Project = get_object_or_404(Project, pk=pk)  # type: ignore[assignment]
        if not _can_manage_project_invitations(project, request.user):
            return JsonResponse({"ok": False, "error": _("Unauthorized.")}, status=403)

        query = (request.GET.get("q") or "").strip()
        UserModel = get_user_model()
        pending_ids = set(
            str(uid)
            for uid in ProjectInvitation.objects.filter(
                project=project,
                status=ProjectInvitation.Status.PENDING,
            ).values_list("invited_user_id", flat=True)
        )
        member_ids = ProjectMember.objects.filter(
            project=project,
            status="accepted",
        ).values_list("member_id", flat=True)

        # Friend list to show by default
        friend_ids = set()
        for a, b in Friendship.objects.filter(
            status=Friendship.Status.ACCEPTED
        ).filter(Q(requester=request.user) | Q(addressee=request.user)).values_list("requester_id", "addressee_id"):
            friend_ids.update([a, b])
        friend_ids.discard(request.user.id)
        friend_ids -= set(member_ids)
        friend_ids -= set(int(pid) for pid in pending_ids if pid.isdigit())

        UserModel = get_user_model()
        if len(query) < 2:
            candidates = UserModel.objects.filter(id__in=friend_ids)[:20]
            return JsonResponse(
                {"ok": True, "results": [_serialize_user(u, pending_ids) for u in candidates]}
            )

        # Build search predicates only for fields that exist on the active User model.
        user_field_names = {
            f.name for f in UserModel._meta.get_fields() if hasattr(f, "name")
        }
        searchable_fields = [
            fname
            for fname in (
                "email",
                "username",
                "full_name",
                "full_name_ar",
                "full_name_en",
            )
            if fname in user_field_names
        ]
        if not searchable_fields:
            return JsonResponse({"ok": True, "results": []})

        search_q = Q()
        for fname in searchable_fields:
            search_q |= Q(**{f"{fname}__icontains": query})

        candidates = (
            UserModel.objects.filter(search_q)
            .exclude(pk=request.user.pk)
            .exclude(pk__in=member_ids)[:20]
        )

        results = [_serialize_user(u, pending_ids) for u in candidates]
        return JsonResponse({"ok": True, "results": results})


class InviteProjectMembersView(LoginAndVerifiedRequiredMixin, View):
    def post(self, request: HttpRequest, pk: str) -> HttpResponse:
        project: Project = get_object_or_404(Project, pk=pk)  # type: ignore[assignment]
        if not _can_manage_project_invitations(project, request.user):
            return JsonResponse({"ok": False, "error": _("Unauthorized.")}, status=403)

        raw_ids = request.POST.getlist("invited_users[]") or request.POST.getlist(
            "invited_users"
        )
        invited_ids = [uid for uid in raw_ids if uid]
        if not invited_ids:
            return JsonResponse(
                {"ok": False, "error": _("Select at least one user.")}, status=400
            )

        UserModel = get_user_model()
        users_map = {
            str(user.pk): user for user in UserModel.objects.filter(pk__in=invited_ids)
        }
        missing_ids = [uid for uid in invited_ids if uid not in users_map]
        if missing_ids:
            return JsonResponse(
                {"ok": False, "error": _("Some selected users do not exist.")},
                status=400,
            )

        existing_member_ids = set(
            str(uid)
            for uid in ProjectMember.objects.filter(
                project=project, member_id__in=invited_ids
            ).values_list("member_id", flat=True)
        )
        existing_pending_ids = set(
            str(uid)
            for uid in ProjectInvitation.objects.filter(
                project=project,
                invited_user_id__in=invited_ids,
                status=ProjectInvitation.Status.PENDING,
            ).values_list("invited_user_id", flat=True)
        )

        created = []
        skipped = []
        with transaction.atomic():
            for uid in invited_ids:
                if uid in existing_member_ids or uid in existing_pending_ids:
                    skipped.append(uid)
                    continue
                invited_user = users_map[uid]
                inv = ProjectInvitation.objects.create(
                    project=project,
                    invited_user=invited_user,
                    invited_by=request.user,
                    status=ProjectInvitation.Status.PENDING,
                )
                created.append(inv)
                NotificationService.create_notification(
                    recipient=invited_user,
                    notification_type="PROJECT_INVITE",
                    title=_("Project Invitation"),
                    message=_(
                        "You have been invited to join the project '%(project)s'."
                    ),
                    project_id=project.pk,
                    sender_id=request.user.id,
                    message_kwargs={"project": project.title},
                )

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "ok": True,
                    "created": len(created),
                    "skipped": len(skipped),
                    "message": _("Invitations sent: %(count)s")
                    % {"count": len(created)},
                }
            )

        if created:
            messages.success(
                request, _("Invitations sent: %(count)s") % {"count": len(created)}
            )
        if skipped:
            messages.warning(
                request,
                _("Some users were skipped (already members or already invited)."),
            )
        return redirect("projects:project_detail", pk=pk)


class ProjectInvitationsView(LoginAndVerifiedRequiredMixin, ListView):
    model = ProjectInvitation
    template_name = "project_invitations.html"
    context_object_name = "invitations"

    def get_queryset(self) -> QuerySet[ProjectInvitation]:
        return ProjectInvitation.objects.filter(
            invited_user=self.request.user,
            status=ProjectInvitation.Status.PENDING,
        ).select_related("project", "invited_by", "project__institution")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user
        pending_invitation_projects = list(
            context["invitations"].values_list("project_id", flat=True)
        )
        legacy_notification_project_ids = (
            Notification.objects.filter(
                recipient=user,
                type__in=["PROJECT_INVITE", "PROJECT_INVITATION"],
            )
            .exclude(project_id__isnull=True)
            .values_list("project_id", flat=True)
        )
        legacy_received_member_invites = (
            ProjectMember.objects.filter(
                member=user,
                status="pending",
                project_id__in=legacy_notification_project_ids,
            )
            .exclude(project_id__in=pending_invitation_projects)
            .select_related(
                "project",
                "project__coordinator",
            )
        )
        incoming_join_requests = (
            ProjectMember.objects.filter(
                project__coordinator=user,
                status="pending",
            )
            .select_related("project", "member")
            .order_by("-created_at")[:120]
        )
        context["sent_invitations"] = ProjectInvitation.objects.filter(
            invited_by=user,
        ).select_related("project", "invited_user", "project__institution")[:80]
        context["legacy_received_member_invites"] = legacy_received_member_invites
        context["incoming_join_requests"] = incoming_join_requests
        context["received_total_count"] = (
            context["invitations"].count()
            + legacy_received_member_invites.count()
            + incoming_join_requests.count()
        )
        context["manageable_projects"] = (
            Project.objects.filter(
                Q(coordinator=user)
                | Q(
                    members__member=user,
                    members__status="accepted",
                    members__role__iexact="admin",
                )
            )
            .distinct()
            .order_by("-updated_at")[:20]
        )
        context["page"] = "project_invitations"
        return context


class AcceptProjectInvitationView(LoginAndVerifiedRequiredMixin, View):
    def post(self, request: HttpRequest, invitation_id: str) -> HttpResponse:
        invitation = get_object_or_404(
            ProjectInvitation.objects.select_related(
                "project", "invited_user", "invited_by"
            ),
            pk=invitation_id,
            invited_user=request.user,
        )
        if invitation.status != ProjectInvitation.Status.PENDING:
            messages.warning(request, _("This invitation is no longer pending."))
            return redirect("projects:project_invitations")

        with transaction.atomic():
            ProjectMember.objects.update_or_create(
                project=invitation.project,
                member=request.user,
                defaults={"role": "member", "status": "accepted"},
            )
            _ensure_project_chatroom(invitation.project)
            invitation.status = ProjectInvitation.Status.ACCEPTED
            invitation.save(update_fields=["status", "updated_at"])

        NotificationService.create_notification(
            recipient=invitation.invited_by,
            notification_type="SYSTEM",
            title=_("Invitation accepted"),
            message=_("%(user)s accepted your invitation to '%(project)s'."),
            project_id=invitation.project.pk,
            sender_id=request.user.id,
            message_kwargs={
                "user": getattr(
                    request.user, "get_full_name_display", request.user.email
                ),
                "project": invitation.project.title,
            },
        )
        messages.success(request, _("You joined the project successfully."))
        return redirect("projects:project_detail", pk=invitation.project.pk)


class RejectProjectInvitationView(LoginAndVerifiedRequiredMixin, View):
    def post(self, request: HttpRequest, invitation_id: str) -> HttpResponse:
        invitation = get_object_or_404(
            ProjectInvitation.objects.select_related(
                "project", "invited_user", "invited_by"
            ),
            pk=invitation_id,
            invited_user=request.user,
        )
        if invitation.status != ProjectInvitation.Status.PENDING:
            messages.warning(request, _("This invitation is no longer pending."))
            return redirect("projects:project_invitations")

        invitation.status = ProjectInvitation.Status.REJECTED
        invitation.save(update_fields=["status", "updated_at"])

        NotificationService.create_notification(
            recipient=invitation.invited_by,
            notification_type="SYSTEM",
            title=_("Invitation rejected"),
            message=_("%(user)s rejected your invitation to '%(project)s'."),
            project_id=invitation.project.pk,
            sender_id=request.user.id,
            message_kwargs={
                "user": getattr(
                    request.user, "get_full_name_display", request.user.email
                ),
                "project": invitation.project.title,
            },
        )
        messages.info(request, _("Invitation rejected."))
        return redirect("projects:project_invitations")


class LeaveProjectView(LoginAndVerifiedRequiredMixin, View):
    def post(self, request: HttpRequest, pk: str) -> HttpResponse:
        project: Project = get_object_or_404(Project, pk=pk)  # type: ignore[assignment]

        # Trouver le membre
        member = ProjectMember.objects.filter(
            project=project, member=request.user, status="accepted"
        ).first()

        if member:
            # Vérifier s'il n'y a pas déjà une demande de départ en attente
            if member.leave_request_status == "pending":
                messages.warning(
                    request,
                    _("You already have a pending leave request for this project."),
                )
                return redirect("projects:project_detail", pk=pk)

            # Marquer la demande de départ comme en attente
            member.leave_request_status = "pending"
            member.leave_request_date = timezone.now()
            member.save()

            # Notification au coordinateur
            NotificationService.create_notification(
                recipient=project.coordinator,
                notification_type="LEAVE_REQUEST",
                title=_("Leave request"),
                message=_(
                    "%(sender_name)s wants to leave your project « %(project_title)s »."
                ),
                related_object=project,
                project_id=project.id,  # type: ignore[attr-defined]
                sender_id=request.user.id,  # type: ignore[attr-defined]
                message_kwargs={
                    "sender_name": LocalizedValue.from_user(request.user),
                    "project_title": project.title,
                },
            )

            messages.success(
                request,
                _("Your leave request has been sent to the project coordinator."),
            )
        else:
            messages.error(request, _("You are not a member of this project."))

        return redirect("projects:project_detail", pk=pk)


class RespondToLeaveRequestView(
    LoginAndVerifiedRequiredMixin, UserPassesTestMixin, View
):
    def test_func(self) -> bool:
        project: Project = get_object_or_404(Project, pk=self.kwargs["pk"])  # type: ignore[assignment]
        return project.coordinator == self.request.user

    def post(self, request: HttpRequest, pk: str, member_id: str) -> HttpResponse:
        project: Project = get_object_or_404(Project, pk=pk)  # type: ignore[assignment]
        member = get_object_or_404(ProjectMember, project=project, member_id=member_id)

        response = request.POST.get("response")
        notification_id = request.POST.get("notification_id")

        # Récupérer la notification originale si elle existe
        notification = None
        if notification_id:
            try:
                notification = Notification.objects.get(
                    id=notification_id, recipient=request.user
                )
            except Notification.DoesNotExist:
                pass

        if member.leave_request_status == "pending":
            if response == "approve":
                # Approuver le départ - supprimer le membre
                leaving_user = member.member
                member.delete()

                # Notification au membre qui quitte
                NotificationService.create_notification(
                    recipient=leaving_user,
                    notification_type="SYSTEM",
                    title=_("Leave request approved"),
                    message=_(
                        "Your request to leave the project « %(project_title)s » has been approved."
                    ),
                    related_object=project,
                    message_kwargs={"project_title": project.title},
                )

                # Mettre à jour la notification originale
                if notification:
                    notification.response_given = True
                    notification.response = "approve"
                    notification.read = True
                    notification.save()

                messages.success(
                    request,
                    _(
                        "Leave request approved. {} has been removed from the project."
                    ).format(leaving_user.full_name),
                )  # type: ignore[attr-defined]

            elif response == "reject":
                # Refuser le départ - réinitialiser le statut
                member.leave_request_status = "rejected"
                member.save()

                # Notification au membre
                NotificationService.create_notification(
                    recipient=member.member,
                    notification_type="SYSTEM",
                    title=_("Leave request rejected"),
                    message=_(
                        "Your request to leave the project « %(project_title)s » has been rejected by the coordinator."
                    ),
                    related_object=project,
                    message_kwargs={"project_title": project.title},
                )

                # Mettre à jour la notification originale
                if notification:
                    notification.response_given = True
                    notification.response = "reject"
                    notification.read = True
                    notification.save()

                messages.success(request, _("Leave request rejected."))

        # Rediriger vers les notifications si la demande vient de là
        if notification_id:
            return redirect("notifications:list")

        return redirect("projects:project_members", pk=pk)


class ProjectSearchView(LoginAndVerifiedRequiredMixin, ListView):
    model = Project
    template_name = "project_search.html"
    context_object_name = "projects"
    paginate_by = 10

    def get_queryset(self) -> QuerySet[Project]:
        qs = exclude_hidden_users(
            Project.objects.filter(approval_status="approved"),
            self.request.user,
            ("coordinator",),
        )
        query = self.request.GET.get("q")
        if query:
            qs = qs.filter(
                Q(title__icontains=query)
                | Q(title_ar__icontains=query)
                | Q(title_en__icontains=query)
                | Q(institution__name__icontains=query)
                | Q(coordinator__full_name__icontains=query)
            )
        return qs


class RemoveMemberView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, View):
    def test_func(self) -> bool:
        project: Project = get_object_or_404(Project, pk=self.kwargs["pk"])  # type: ignore[assignment]
        return project.coordinator == self.request.user

    def post(self, request: HttpRequest, pk: str, member_id: str) -> HttpResponse:
        project: Project = get_object_or_404(Project, pk=pk)  # type: ignore[assignment]
        member = get_object_or_404(ProjectMember, project=project, member_id=member_id)

        # Récupérer l'utilisateur membre avant la suppression
        removed_user = member.member

        # Supprimer le membre
        member.delete()

        # Envoyer une notification au membre retiré
        NotificationService.create_notification(
            recipient=removed_user,
            notification_type="SYSTEM",
            title=_("Removed from project"),
            message=_(
                "You have been removed from the project « %(project_title)s » by the coordinator."
            ),
            related_object=project,
            message_kwargs={"project_title": project.title},
        )

        messages.success(request, _("Member removed successfully."))
        return redirect("projects:project_members", pk=pk)


class RespondToRequestView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, View):
    def test_func(self) -> bool:
        project: Project = get_object_or_404(Project, pk=self.kwargs["pk"])  # type: ignore[assignment]
        return project.coordinator == self.request.user

    def post(self, request: HttpRequest, pk: str, request_id: str) -> HttpResponse:
        project: Project = get_object_or_404(Project, pk=pk)  # type: ignore[assignment]
        join_request = get_object_or_404(ProjectMember, pk=request_id, project=project)

        response = request.POST.get("response")
        if response == "accept":
            join_request.status = "accepted"
            join_request.save()
            _ensure_project_chatroom(project)
            messages.success(request, _("Request accepted successfully."))

            # Créer une notification pour le membre
            NotificationService.create_notification(
                recipient=join_request.member,
                title=_("Project Request Accepted"),
                message=_("Your request to join %(project_title)s has been accepted."),
                notification_type="project_request_accepted",
                related_object=project,
                message_kwargs={"project_title": project.title},
            )
        elif response == "reject":
            join_request.status = "rejected"
            join_request.save()
            messages.success(request, _("Request rejected successfully."))

            # Créer une notification pour le membre
            NotificationService.create_notification(
                recipient=join_request.member,
                title=_("Project Request Rejected"),
                message=_("Your request to join %(project_title)s has been rejected."),
                notification_type="project_request_rejected",
                related_object=project,
                message_kwargs={"project_title": project.title},
            )

        return redirect("projects:project_detail", pk=pk)


def _project_chat_access(project: Project, user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user == project.coordinator:
        return True
    return ProjectMember.objects.filter(
        project=project, member=user, status="accepted"
    ).exists()


def _project_chat_blocked(project: Project, user) -> bool:
    # Project discussion access is strictly tied to project membership.
    return False


@login_required
@require_http_methods(["GET"])
def project_chatroom(request: HttpRequest, pk: str) -> HttpResponse:
    project: Project = get_object_or_404(Project, pk=pk)  # type: ignore[assignment]
    if not _project_chat_access(project, request.user):
        return HttpResponseForbidden(
            _("Only project members can access this chatroom.")
        )
    room = _ensure_project_chatroom(project)
    room_messages = (
        room.messages.filter(is_deleted=False)
        .select_related("sender")
        .prefetch_related("seen_by")
    )
    unseen_messages = room_messages.exclude(sender=request.user).exclude(
        seen_by=request.user
    )
    for msg in unseen_messages:
        msg.seen_by.add(request.user)

    member_projects = (
        Project.objects.filter(
            Q(coordinator=request.user)
            | Q(members__member=request.user, members__status="accepted")
        )
        .distinct()
        .order_by("-updated_at")
    )

    return render(
        request,
        "project_chatroom.html",
        {
            "project": project,
            "room": room,
            "chat_messages": room_messages,
            "form": ProjectChatMessageForm(),
            "member_projects": member_projects,
            "page": "research_projects",
        },
    )


@login_required
@require_http_methods(["POST"])
def project_chat_send(request: HttpRequest, pk: str) -> HttpResponse:
    project: Project = get_object_or_404(Project, pk=pk)  # type: ignore[assignment]
    if not _project_chat_access(project, request.user):
        return JsonResponse(
            {"ok": False, "error": _("Only members can send messages.")}, status=403
        )
    room = _ensure_project_chatroom(project)
    form = ProjectChatMessageForm(
        request.POST,
        request.FILES,
        instance=ProjectChatMessage(room=room, sender=request.user),
    )
    if not form.is_valid():
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "ok": False,
                    "errors": form.errors,
                    "non_field_errors": form.non_field_errors(),
                },
                status=400,
            )
        messages.error(request, _("Please correct chat form errors."))
        return redirect("projects:project_chatroom", pk=project.pk)

    msg = form.save(commit=False)
    msg.room = room
    msg.sender = request.user
    msg.save()
    msg.seen_by.add(request.user)
    sender_raw = getattr(request.user, "get_full_name_display", "")
    sender_name = sender_raw() if callable(sender_raw) else sender_raw
    sender_name = (str(sender_name) if sender_name is not None else "").strip() or request.user.email

    # Broadcast freshly persisted message to all room participants via Channels.
    try:
        channel_layer = get_channel_layer()
        if channel_layer is not None:
            async_to_sync(channel_layer.group_send)(
                f"project_chat_{project.pk}",
                {
                    "type": "chat_message",
                    "message_id": str(msg.id),
                    "sender_id": str(msg.sender_id),
                    "sender_name": escape(sender_name),
                    "content": escape(msg.content),
                    "message_type": msg.message_type,
                    "file_url": msg.file_path.url if msg.file_path else "",
                    "created_at": msg.created_at.strftime("%Y-%m-%d %H:%M"),
                },
            )
    except Exception:
        logger.exception("Project chat websocket broadcast failed for project=%s", project.pk)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse(
            {
                "ok": True,
                "message": {
                    "id": str(msg.id),
                    "sender_id": str(msg.sender_id),
                    "sender_name": sender_name,
                    "message_type": msg.message_type,
                    "content": escape(msg.content),
                    "file_url": msg.file_path.url if msg.file_path else "",
                    "created_at": msg.created_at.strftime("%Y-%m-%d %H:%M"),
                },
            }
        )
    return redirect("projects:project_chatroom", pk=project.pk)


@login_required
@require_http_methods(["POST", "DELETE"])
def project_chat_delete_message(
    request: HttpRequest, pk: str, message_id: str
) -> HttpResponse:
    project: Project = get_object_or_404(Project, pk=pk)  # type: ignore[assignment]
    if not _project_chat_access(project, request.user):
        return JsonResponse({"ok": False, "error": _("Access denied.")}, status=403)

    room, _ = ProjectChatRoom.objects.get_or_create(project=project)
    msg = get_object_or_404(ProjectChatMessage, pk=message_id, room=room)
    is_project_admin = (
        request.user == project.coordinator
        or ProjectMember.objects.filter(
            project=project,
            member=request.user,
            status="accepted",
            role__iexact="admin",
        ).exists()
    )
    if not (msg.sender_id == request.user.id or is_project_admin):
        return JsonResponse(
            {
                "ok": False,
                "error": _("Only sender or project admin can delete message."),
            },
            status=403,
        )

    msg.is_deleted = True
    msg.content = ""
    msg.save(update_fields=["is_deleted", "content", "updated_at"])
    return JsonResponse({"ok": True})


@login_required
def project_invitations_count_api(request):
    """Return pending received items for project invitations UI badges."""
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)
    invitation_project_ids = list(
        ProjectInvitation.objects.filter(
            invited_user=request.user,
            status=ProjectInvitation.Status.PENDING,
        ).values_list("project_id", flat=True)
    )
    legacy_notification_project_ids = (
        Notification.objects.filter(
            recipient=request.user,
            type__in=["PROJECT_INVITE", "PROJECT_INVITATION"],
        )
        .exclude(project_id__isnull=True)
        .values_list("project_id", flat=True)
    )
    legacy_project_ids = list(
        ProjectMember.objects.filter(
            member=request.user,
            status="pending",
            project_id__in=legacy_notification_project_ids,
        ).values_list("project_id", flat=True)
    )
    incoming_join_requests_count = ProjectMember.objects.filter(
        project__coordinator=request.user,
        status="pending",
    ).count()
    count = (
        len(set(invitation_project_ids) | set(legacy_project_ids))
        + incoming_join_requests_count
    )
    return JsonResponse({"ok": True, "count": count})
