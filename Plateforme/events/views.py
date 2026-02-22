from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls import reverse_lazy
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test
from django.urls import reverse
import logging

# App specific imports
from .models import Event, EventRegistration
from .forms import EventForm, EventSearchForm
from accounts import models
from notifications.services import NotificationService

# CRITICAL: Import your custom Mixin
from accounts.views import LoginAndVerifiedRequiredMixin

logger = logging.getLogger(__name__)

# 

class EventListView(LoginAndVerifiedRequiredMixin, ListView):
    """View for listing events - Restricted to logged-in and verified users."""
    model = Event
    template_name = 'events/event_list.html'
    context_object_name = 'events'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            queryset = queryset.filter(approval_status='approved')
        
        form = EventSearchForm(self.request.GET)
        if form.is_valid():
            keyword = form.cleaned_data.get('keyword')
            event_type = form.cleaned_data.get('event_type')
            domain = form.cleaned_data.get('domain')
            start_date = form.cleaned_data.get('start_date')
            include_past = form.cleaned_data.get('include_past')
            
            if keyword:
                queryset = queryset.filter(
                    Q(title__icontains=keyword) | 
                    Q(title_ar__icontains=keyword) | 
                    Q(title_en__icontains=keyword) | 
                    Q(description__icontains=keyword) |
                    Q(description_ar__icontains=keyword) |
                    Q(description_en__icontains=keyword) |
                    Q(organizer__name__icontains=keyword) |
                    Q(domains__icontains=keyword) |
                    Q(location__icontains=keyword)
                )
            if event_type:
                queryset = queryset.filter(event_type=event_type)
            if domain:
                queryset = queryset.filter(domains__icontains=domain)
            if start_date:
                queryset = queryset.filter(start_date__gte=start_date)
            if not include_past:
                queryset = queryset.filter(submission_deadline__gte=timezone.now().date())
        else:
            queryset = queryset.filter(submission_deadline__gte=timezone.now().date())
        
        return queryset.select_related('organizer', 'created_by')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = EventSearchForm(self.request.GET or None)
        context['page'] = 'events'
        return context


class EventDetailView(LoginAndVerifiedRequiredMixin, DetailView):
    """View for displaying event details - Restricted to verified users."""
    model = Event
    template_name = 'events/event_detail.html'
    context_object_name = 'event'

    def get_queryset(self):
        queryset = Event.objects.select_related('organizer', 'created_by')
        if self.request.user.is_staff:
            return queryset
        
        # Now that we use the Mixin, user is guaranteed to be authenticated here
        queryset = queryset.filter(
            Q(approval_status='approved') | 
            Q(created_by=self.request.user)
        )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_registered'] = EventRegistration.objects.filter(
            event=self.object,
            user=self.request.user
        ).exists()
        context['registration_count'] = self.object.registrations.count()
        context['page'] = 'events'
        
        if self.request.user == self.object.created_by or self.request.user.is_staff:
            context['show_approval_status'] = True
        return context


class EventCreateView(LoginAndVerifiedRequiredMixin, CreateView):
    """View for creating new events - Restricted."""
    model = Event
    form_class = EventForm
    template_name = 'events/event_form.html'
    
    def _save_bilingual_fields(self, instance):
        """Save bilingual fields from POST data to the model instance."""
        bilingual_fields = {
            'title': ('title_en', 'title_ar'),
            'description': ('description_en', 'description_ar'),
            'location': ('location_en', 'location_ar'),
        }
        for base, (en_field, ar_field) in bilingual_fields.items():
            en_val = self.request.POST.get(en_field, '').strip()
            ar_val = self.request.POST.get(ar_field, '').strip()
            setattr(instance, en_field, en_val)
            setattr(instance, ar_field, ar_val)
            # Set the legacy base field from the English value (or Arabic as fallback)
            if not getattr(instance, base, ''):
                setattr(instance, base, en_val or ar_val)
        instance.save()

    def form_valid(self, form):
        import logging
        logger = logging.getLogger(__name__)
        
        form.instance.is_approved = self.request.user.is_staff
        form.instance.approval_status = 'approved' if self.request.user.is_staff else 'pending'
        form.instance.created_by = self.request.user
        
        logger.info(
            f"[EVENT_CREATE] Creating event by user: {self.request.user.email}, "
            f"title: {form.instance.title}, status: {form.instance.approval_status}"
        )
        
        try:
            self.object = form.save()
            self._save_bilingual_fields(self.object)
            
            logger.info(
                f"[EVENT_CREATE] ✓ Event created successfully "
                f"(ID: {self.object.id}, Status: {self.object.approval_status})"
            )
            
            if self.object.is_approved:
                messages.success(self.request, _('Event created successfully!'))
                User = get_user_model()
                active_users = User.objects.filter(is_active=True)
                NotificationService.notify_group(
                    active_users,
                    'EVENT_APPROVED',
                    _("New event approved: %(title)s"),
                    _("A new event has been approved: %(title)s."),
                    self.object,
                    title_kwargs={'title': self.object.title},
                    message_kwargs={'title': self.object.title}
                )
                return redirect(self.object.get_absolute_url())
            else:
                messages.success(self.request, _('Event created successfully! It will be visible after admin approval.'))
                NotificationService.create_notification(
                    recipient=self.request.user,
                    notification_type='EVENT_CREATED',
                    title=_("Your event is awaiting approval"),
                    message=_("Your event '%(title)s' is awaiting approval."),
                    related_object=self.object,
                    message_kwargs={'title': self.object.title}
                )
                return redirect('events:event_list')
                
        except Exception as e:
            logger.error(f"[EVENT_CREATE] ✗ Error creating event: {str(e)}", exc_info=True)
            messages.error(self.request, _('An error occurred while creating the event. Please try again.'))
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"[EVENT_CREATE] Form validation failed: {form.errors.as_json()}")
        messages.error(self.request, _('Please correct the errors in the form.'))
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page'] = 'events'  
        return context


class EventUpdateView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for updating events - Restricted."""
    model = Event
    form_class = EventForm
    template_name = 'events/event_form.html'
    
    def test_func(self):
        event = self.get_object()
        return self.request.user == event.created_by or self.request.user.is_staff
    
    def _save_bilingual_fields(self, instance):
        """Save bilingual fields from POST data to the model instance."""
        bilingual_fields = {
            'title': ('title_en', 'title_ar'),
            'description': ('description_en', 'description_ar'),
            'location': ('location_en', 'location_ar'),
        }
        for base, (en_field, ar_field) in bilingual_fields.items():
            en_val = self.request.POST.get(en_field, '').strip()
            ar_val = self.request.POST.get(ar_field, '').strip()
            setattr(instance, en_field, en_val)
            setattr(instance, ar_field, ar_val)
            if not getattr(instance, base, ''):
                setattr(instance, base, en_val or ar_val)
        instance.save()

    def form_valid(self, form):
        if not self.request.user.is_staff and self.get_object().is_approved:
            form.instance.is_approved = False
            form.instance.approval_status = 'pending'
            messages.info(self.request, _('Your changes will be reviewed before becoming visible.'))
        else:
            messages.success(self.request, _('Event updated successfully!'))
        response = super().form_valid(form)
        self._save_bilingual_fields(self.object)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page'] = 'events'  
        return context


class EventDeleteView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, DeleteView):
    """View for deleting events - Restricted."""
    model = Event
    template_name = 'events/event_confirm_delete.html'
    success_url = reverse_lazy('events:event_list')
    
    def test_func(self):
        event = self.get_object()
        return self.request.user == event.created_by or self.request.user.is_staff
    
    def delete(self, request, *args, **kwargs):
        event_title = self.get_object().title
        messages.success(request, _('Event "{}" deleted successfully.').format(event_title))
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page'] = 'events'  
        return context


def register_for_event(request, pk):
    """Function view for registering - Now checks for verification and deadline."""
    # Check if user is authenticated AND verified
    if not request.user.is_authenticated or not getattr(request.user, 'is_verified', False):
        messages.error(request, _('You must be logged in and verified to register for events.'))
        return redirect('account_login')
    
    # Only allow POST for state-changing operations
    if request.method != 'POST':
        messages.error(request, _('Invalid request method.'))
        return redirect('events:event_detail', pk=pk)
    
    event = get_object_or_404(Event, pk=pk, approval_status='approved')
    if event.is_past:
        messages.error(request, _('Registration for past events is not allowed.'))
        return redirect('events:event_detail', pk=pk)
    
    # Check submission deadline
    if event.submission_deadline and event.submission_deadline < timezone.now().date():
        messages.error(request, _('The registration deadline for this event has passed.'))
        return redirect('events:event_detail', pk=pk)
    
    if EventRegistration.objects.filter(event=event, user=request.user).exists():
        messages.info(request, _('You are already registered for this event.'))
    else:
        EventRegistration.objects.create(event=event, user=request.user)
        messages.success(request, _('You have successfully registered for "{}".').format(event.title))
    return redirect('events:event_detail', pk=pk)


def unregister_from_event(request, pk):
    """Function view for unregistering - Now checks for verification and requires POST."""
    if not request.user.is_authenticated or not getattr(request.user, 'is_verified', False):
        return redirect('account_login')
    
    # Only allow POST for state-changing operations
    if request.method != 'POST':
        messages.error(request, _('Invalid request method.'))
        return redirect('events:event_detail', pk=pk)
    
    event = get_object_or_404(Event, pk=pk)
    if event.is_past:
        messages.error(request, _('Unregistering from past events is not allowed.'))
        return redirect('events:event_detail', pk=pk)
    
    registration = get_object_or_404(EventRegistration, event=event, user=request.user)
    registration.delete()
    messages.success(request, _('You have unregistered from "{}".').format(event.title))
    return redirect('events:event_detail', pk=pk)


@user_passes_test(lambda u: u.is_staff)
def event_validate(request, pk):
    """Admin view for event approval."""
    event = get_object_or_404(Event, pk=pk)
    event.is_approved = True
    event.approval_status = 'approved'
    event.save()
    
    NotificationService.create_notification(
        recipient=event.created_by,
        notification_type='EVENT_APPROVED',
        title=_("Your event has been approved"),
        message=_("Your event '%(title)s' is now visible."),
        related_object=event,
        message_kwargs={'title': event.title}
    )
    
    User = get_user_model()
    active_users = User.objects.filter(is_active=True)
    NotificationService.notify_group(
        active_users,
        'EVENT_APPROVED',
        _("New event approved: %(title)s"),
        _("A new event has been approved: %(title)s."),
        event,
        title_kwargs={'title': event.title},
        message_kwargs={'title': event.title}
    )
    
    messages.success(request, _('Event has been approved successfully!'))
    return redirect('pages:admin_calls')
