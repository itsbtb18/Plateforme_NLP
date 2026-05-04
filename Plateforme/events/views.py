import logging
<<<<<<< HEAD
import os
=======
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
from datetime import UTC, datetime, time
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from accounts.blocking import blocked_user_ids_for

# CRITICAL: Import your custom Mixin
from accounts.views import LoginAndVerifiedRequiredMixin
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db import transaction
from django.db.models import Q
<<<<<<< HEAD
from django.http import HttpResponse, JsonResponse
=======
from django.http import HttpResponse
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
<<<<<<< HEAD
from django.views.decorators.http import require_GET
=======
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)
from notifications.services import NotificationService
from pages.moderation import approve_object

from .forms import EventForm, EventSearchForm, SpeakerFormSet

# App specific imports
from .models import Event, EventRegistration

logger = logging.getLogger(__name__)

#


def _event_datetime_bounds(event: Event):
    """
    Build timezone-aware datetime bounds from date-only event fields.
    """
    tz_name = getattr(settings, "TIME_ZONE", "UTC")
    tz = ZoneInfo(tz_name)
    start_naive = datetime.combine(event.start_date, time.min)
    end_naive = datetime.combine(event.end_date, time.max.replace(microsecond=0))
    return start_naive.replace(tzinfo=tz), end_naive.replace(tzinfo=tz), tz


def _google_calendar_link(event: Event) -> str:
    start_dt, end_dt, _tz = _event_datetime_bounds(event)
    start_utc = start_dt.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    end_utc = end_dt.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    details = (event.description or "").strip()
    if event.source_url:
        details = f"{details}\n\nSource: {event.source_url}".strip()
    location = event.location or ("Online" if event.is_online else "")
    params = {
        "action": "TEMPLATE",
        "text": event.title,
        "dates": f"{start_utc}/{end_utc}",
        "details": details,
        "location": location,
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(params)


class EventListView(LoginAndVerifiedRequiredMixin, ListView):
    """View for listing events - Restricted to logged-in and verified users."""

    model = Event
    template_name = "events/event_list.html"
    context_object_name = "events"
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            queryset = queryset.filter(
                approval_status="approved",
                scrape_status=Event.SCRAPE_STATUS_APPROVED,
            )

        form = EventSearchForm(self.request.GET)
        if form.is_valid():
            keyword = form.cleaned_data.get("keyword")
            event_type = form.cleaned_data.get("event_type")
            domain = form.cleaned_data.get("domain")
            start_date = form.cleaned_data.get("start_date")
            include_past = form.cleaned_data.get("include_past")

            if keyword:
                queryset = queryset.filter(
                    Q(title__icontains=keyword)
                    | Q(title_ar__icontains=keyword)
                    | Q(title_en__icontains=keyword)
                    | Q(description__icontains=keyword)
                    | Q(description_ar__icontains=keyword)
                    | Q(description_en__icontains=keyword)
                    | Q(organizer__name__icontains=keyword)
                    | Q(domains__icontains=keyword)
                    | Q(location__icontains=keyword)
                )
            if event_type:
                queryset = queryset.filter(event_type=event_type)
            if domain:
                queryset = queryset.filter(domains__icontains=domain)
            if start_date:
                queryset = queryset.filter(start_date__gte=start_date)
            if not include_past:
                queryset = queryset.filter(
                    submission_deadline__gte=timezone.now().date(),
                    is_past_event=False,
                )
        else:
            queryset = queryset.filter(
                submission_deadline__gte=timezone.now().date(),
                is_past_event=False,
            )

        return queryset.select_related("organizer", "created_by")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = EventSearchForm(self.request.GET or None)
        context['page'] = 'events'
        context['is_create_mode'] = True
        context['is_update_mode'] = False
        return context


class EventDetailView(LoginAndVerifiedRequiredMixin, DetailView):
    """View for displaying event details - Restricted to verified users."""

    model = Event
    template_name = "events/event_detail.html"
    context_object_name = "event"

    def get_queryset(self):
        queryset = Event.objects.select_related("organizer", "created_by")
        if self.request.user.is_staff:
            return queryset

        # Now that we use the Mixin, user is guaranteed to be authenticated here
        queryset = queryset.filter(
            Q(approval_status="approved") | Q(created_by=self.request.user)
        )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_registered"] = EventRegistration.objects.filter(
            event=self.object, user=self.request.user
        ).exists()
        context["registration_count"] = self.object.registrations.count()
        context["speakers"] = self.object.speakers.all().order_by("order", "name")
        context["google_calendar_url"] = _google_calendar_link(self.object)
        context["page"] = "events"

        if self.request.user == self.object.created_by or self.request.user.is_staff:
            context["show_approval_status"] = True
        return context


def event_ics_export(request, pk):
    """
    Export event as .ics for Google Calendar/Outlook/Apple Calendar.
    """
    try:
        from icalendar import Calendar
        from icalendar import Event as ICalEvent
    except ImportError:
        return HttpResponse(
            "Calendar export is temporarily unavailable.",
            status=503,
            content_type="text/plain; charset=utf-8",
        )

    event = get_object_or_404(Event, pk=pk, approval_status="approved")
    start_dt, end_dt, tz = _event_datetime_bounds(event)

    cal = Calendar()
    cal.add("prodid", "-//Arabic NLP Platform//Events Calendar//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")

    ics_event = ICalEvent()
    ics_event.add("uid", f"event-{event.pk}@arabic-nlp-platform")
    ics_event.add("summary", event.title)
    ics_event.add("description", event.description or "")
    ics_event.add("dtstart", start_dt)
    ics_event.add("dtend", end_dt)
    ics_event.add("dtstamp", timezone.now().astimezone(UTC))
    if event.location:
        ics_event.add("location", event.location)
    elif event.is_online:
        ics_event.add("location", "Online")
    if event.source_url:
        ics_event.add("url", event.source_url)
    ics_event.add("X-WR-TIMEZONE", str(tz))
    cal.add_component(ics_event)

    response = HttpResponse(cal.to_ical(), content_type="text/calendar; charset=utf-8")
    safe_title = (
        "".join(
            ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in event.title
        ).strip("_")
        or "event"
    )
    response["Content-Disposition"] = f'attachment; filename="{safe_title}.ics"'
    return response


<<<<<<< HEAD
@require_GET
def event_convert_to_text(request, pk):
    """
    API endpoint: extract raw text from an event attached file.
    Supports PDF (with OCR fallback), DOCX, and plain text formats.
    """
    queryset = Event.objects.select_related("created_by")
    if request.user.is_staff or request.user.is_superuser:
        event = get_object_or_404(queryset, pk=pk)
    else:
        event = get_object_or_404(
            queryset.filter(Q(approval_status="approved") | Q(created_by=request.user)),
            pk=pk,
        )

    if not event.attachment:
        return JsonResponse(
            {"success": False, "error": _("This event has no attached file.")},
            status=400,
        )

    file_path = event.attachment.path
    if not os.path.isfile(file_path):
        return JsonResponse(
            {
                "success": False,
                "error": _("The file could not be found on the server."),
            },
            status=404,
        )

    filename = os.path.basename(file_path)
    ext = os.path.splitext(filename)[1].lower()

    try:
        from resources.views import (
            _extract_text_from_docx,
            _extract_text_from_pdf,
            _extract_text_from_txt,
        )

        extraction_meta: dict[str, int | float | bool] = {}
        if ext == ".pdf":
            text, extraction_meta = _extract_text_from_pdf(file_path)
        elif ext in (".docx", ".doc"):
            text = _extract_text_from_docx(file_path)
        elif ext in (".txt", ".md", ".csv", ".json", ".xml", ".log"):
            text = _extract_text_from_txt(file_path)
        else:
            return JsonResponse(
                {
                    "success": False,
                    "error": _("Unsupported file format: %(ext)s") % {"ext": ext},
                },
                status=400,
            )

        if not text or not text.strip():
            return JsonResponse(
                {
                    "success": False,
                    "error": _(
                        "No text could be extracted from this document. It may be empty or contain only images without recognisable text."
                    ),
                },
                status=200,
            )

        return JsonResponse(
            {
                "success": True,
                "text": text,
                "filename": filename,
                "char_count": len(text),
                "word_count": len(text.split()),
                **extraction_meta,
            }
        )

    except Exception:
        logger.exception("Text extraction failed for event %s", pk)
        return JsonResponse(
            {
                "success": False,
                "error": _("An error occurred while processing the document."),
            },
            status=500,
        )


=======
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
class EventCreateView(LoginAndVerifiedRequiredMixin, CreateView):
    """View for creating new events - Restricted."""

    model = Event
    form_class = EventForm
    template_name = "events/event_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if "speaker_formset" not in context:
            context["speaker_formset"] = SpeakerFormSet(
                self.request.POST or None,
                self.request.FILES or None,
                instance=self.object if getattr(self, "object", None) else Event(),
                prefix="speakers",
            )
        context["page"] = "events"
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def _save_bilingual_fields(self, instance):
        """Save bilingual fields from POST data to the model instance."""
        bilingual_fields = {
            "title": ("title_en", "title_ar"),
            "description": ("description_en", "description_ar"),
            "location": ("location_en", "location_ar"),
        }
        for base, (en_field, ar_field) in bilingual_fields.items():
            en_val = self.request.POST.get(en_field, "").strip()
            ar_val = self.request.POST.get(ar_field, "").strip()
            setattr(instance, en_field, en_val)
            setattr(instance, ar_field, ar_val)
            # Set the legacy base field from the English value (or Arabic as fallback)
            if not getattr(instance, base, ""):
                setattr(instance, base, en_val or ar_val)
        instance.save()

    def form_valid(self, form):
        import logging

        logger = logging.getLogger(__name__)

        form.instance.is_approved = self.request.user.is_staff
        form.instance.approval_status = (
            "approved" if self.request.user.is_staff else "pending"
        )
        form.instance.created_by = self.request.user

        logger.info(
            f"[EVENT_CREATE] Creating event by user: {self.request.user.email}, "
            f"title: {form.instance.title}, status: {form.instance.approval_status}"
        )
        speaker_formset = SpeakerFormSet(
            self.request.POST,
            self.request.FILES,
            instance=Event(),
            prefix="speakers",
        )
        if not speaker_formset.is_valid():
            return self.form_invalid(form, speaker_formset=speaker_formset)

        try:
            with transaction.atomic():
                self.object = form.save()
                self._save_bilingual_fields(self.object)
                speaker_formset.instance = self.object
                speaker_formset.save()

            logger.info(
                f"[EVENT_CREATE] ✓ Event created successfully "
                f"(ID: {self.object.id}, Status: {self.object.approval_status})"
            )

            if self.object.is_approved:
                messages.success(self.request, _("Event created successfully!"))
                User = get_user_model()
                active_users = User.objects.filter(is_active=True)
                NotificationService.notify_group(
                    active_users,
                    "EVENT_APPROVED",
                    _("New event approved: %(title)s"),
                    _("A new event has been approved: %(title)s."),
                    self.object,
                    title_kwargs={"title": self.object.title},
                    message_kwargs={"title": self.object.title},
                )
                return redirect(self.object.get_absolute_url())
            else:
                messages.success(
                    self.request,
                    _(
                        "Event created successfully! It will be visible after admin approval."
                    ),
                )
                NotificationService.create_notification(
                    recipient=self.request.user,
                    notification_type="EVENT_CREATED",
                    title=_("Your event is awaiting approval"),
                    message=_("Your event '%(title)s' is awaiting approval."),
                    related_object=self.object,
                    message_kwargs={"title": self.object.title},
                )
                return redirect("events:event_list")

        except Exception as e:
            logger.error(
                f"[EVENT_CREATE] ✗ Error creating event: {str(e)}", exc_info=True
            )
            messages.error(
                self.request,
                _("An error occurred while creating the event. Please try again."),
            )
            return self.form_invalid(form)

    def form_invalid(self, form, speaker_formset=None):
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"[EVENT_CREATE] Form validation failed: {form.errors.as_json()}"
        )
        messages.error(self.request, _("Please correct the errors in the form."))
        context = self.get_context_data(form=form)
        context["speaker_formset"] = speaker_formset or SpeakerFormSet(
            self.request.POST or None,
            self.request.FILES or None,
            instance=self.object if getattr(self, "object", None) else Event(),
            prefix="speakers",
        )
        return self.render_to_response(context)


class EventUpdateView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for updating events - Restricted."""

    model = Event
    form_class = EventForm
    template_name = "events/event_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if "speaker_formset" not in context:
            context["speaker_formset"] = SpeakerFormSet(
                self.request.POST or None,
                self.request.FILES or None,
                instance=self.object,
                prefix="speakers",
            )
        context['page'] = 'events'
        context['is_create_mode'] = False
        context['is_update_mode'] = True
        context['review_mode'] = self.request.GET.get('review') == '1' and self.request.user.is_staff
        context['is_pending'] = self.object.approval_status == 'pending'
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def test_func(self):
        event = self.get_object()
        return self.request.user == event.created_by or self.request.user.is_staff

    def _save_bilingual_fields(self, instance):
        """Save bilingual fields from POST data to the model instance."""
        bilingual_fields = {
            "title": ("title_en", "title_ar"),
            "description": ("description_en", "description_ar"),
            "location": ("location_en", "location_ar"),
        }
        for base, (en_field, ar_field) in bilingual_fields.items():
            en_val = self.request.POST.get(en_field, "").strip()
            ar_val = self.request.POST.get(ar_field, "").strip()
            setattr(instance, en_field, en_val)
            setattr(instance, ar_field, ar_val)
            if not getattr(instance, base, ""):
                setattr(instance, base, en_val or ar_val)
        instance.save()

    def form_valid(self, form):
        speaker_formset = SpeakerFormSet(
            self.request.POST,
            self.request.FILES,
            instance=self.get_object(),
            prefix="speakers",
        )
        if not speaker_formset.is_valid():
            return self.form_invalid(form, speaker_formset=speaker_formset)

        if not self.request.user.is_staff and self.get_object().is_approved:
            form.instance.is_approved = False
            form.instance.approval_status = "pending"
            messages.info(
                self.request,
                _("Your changes will be reviewed before becoming visible."),
            )
        else:
            messages.success(self.request, _("Event updated successfully!"))
        with transaction.atomic():
            response = super().form_valid(form)
            self._save_bilingual_fields(self.object)
            speaker_formset.instance = self.object
            speaker_formset.save()

        # In admin edit-only mode, return to review detail page for approve/reject actions.
        if (
            self.request.user.is_staff
            and self.request.GET.get("edit_only") == "1"
            and self.request.GET.get("review_model")
            and self.request.GET.get("review_pk")
        ):
            return redirect(self.request.get_full_path())
        return response

    def form_invalid(self, form, speaker_formset=None):
        context = self.get_context_data(form=form)
        context["speaker_formset"] = speaker_formset or SpeakerFormSet(
            self.request.POST or None,
            self.request.FILES or None,
            instance=self.object,
            prefix="speakers",
        )
        return self.render_to_response(context)


class EventDeleteView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for deleting events - Restricted."""

    model = Event
    template_name = "events/event_confirm_delete.html"
    success_url = reverse_lazy("events:event_list")

    def test_func(self):
        event = self.get_object()
        return self.request.user == event.created_by or self.request.user.is_staff

    def delete(self, request, *args, **kwargs):
        event = self.get_object()
        event_title = event.title
        event.soft_delete(request.user)
        messages.success(
            request,
            _('Event "%(title)s" moved to trash.') % {"title": event_title},
        )
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page"] = "events"
        return context


def register_for_event(request, pk):
    """Function view for registering - Now checks for verification and deadline."""
    # Check if user is authenticated AND verified
    if not request.user.is_authenticated or not getattr(
        request.user, "is_verified", False
    ):
        messages.error(
            request, _("You must be logged in and verified to register for events.")
        )
        return redirect("account_login")

    # Only allow POST for state-changing operations
    if request.method != "POST":
        messages.error(request, _("Invalid request method."))
        return redirect("events:event_detail", pk=pk)

    event = get_object_or_404(Event, pk=pk, approval_status="approved")
    if request.user.id in blocked_user_ids_for(event.created_by):
        messages.error(request, _("You cannot register for this event."))
        return redirect("events:event_detail", pk=pk)

    if event.is_past:
        messages.error(request, _("Registration for past events is not allowed."))
        return redirect("events:event_detail", pk=pk)

    # Check submission deadline
    if event.submission_deadline and event.submission_deadline < timezone.now().date():
        messages.error(
            request, _("The registration deadline for this event has passed.")
        )
        return redirect("events:event_detail", pk=pk)

    if EventRegistration.objects.filter(event=event, user=request.user).exists():
        messages.info(request, _("You are already registered for this event."))
    else:
        EventRegistration.objects.create(event=event, user=request.user)
        messages.success(
            request, _('You have successfully registered for "{}".').format(event.title)
        )
    return redirect("events:event_detail", pk=pk)


def unregister_from_event(request, pk):
    """Function view for unregistering - Now checks for verification and requires POST."""
    if not request.user.is_authenticated or not getattr(
        request.user, "is_verified", False
    ):
        return redirect("account_login")

    # Only allow POST for state-changing operations
    if request.method != "POST":
        messages.error(request, _("Invalid request method."))
        return redirect("events:event_detail", pk=pk)

    event = get_object_or_404(Event, pk=pk)
    if event.is_past:
        messages.error(request, _("Unregistering from past events is not allowed."))
        return redirect("events:event_detail", pk=pk)

    registration = get_object_or_404(EventRegistration, event=event, user=request.user)
    registration.delete()
    messages.success(request, _('You have unregistered from "{}".').format(event.title))
    return redirect("events:event_detail", pk=pk)


@user_passes_test(lambda u: u.is_staff)
def event_validate(request, pk):
    """Admin view for event approval."""
    event = get_object_or_404(Event, pk=pk)
    approve_object(event, moderator=request.user, save=True)

    NotificationService.create_notification(
        recipient=event.created_by,
        notification_type="EVENT_APPROVED",
        title=_("Your event has been approved"),
        message=_("Your event '%(title)s' is now visible."),
        related_object=event,
        message_kwargs={"title": event.title},
    )

    User = get_user_model()
    active_users = User.objects.filter(is_active=True)
    NotificationService.notify_group(
        active_users,
        "EVENT_APPROVED",
        _("New event approved: %(title)s"),
        _("A new event has been approved: %(title)s."),
        event,
        title_kwargs={"title": event.title},
        message_kwargs={"title": event.title},
    )

    messages.success(request, _("Event has been approved successfully!"))
    return redirect("pages:admin_calls")
