from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.db.models.deletion import ProtectedError
from django.db.models import Q
from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth import get_user_model
from django.http import HttpResponse, Http404
from typing import Any, cast
import logging

from .models import Institution
from .forms import InstitutionFilterForm, InstitutionForm
from resources.models import Thesis, Memoir

# CRITICAL: Import your custom Mixin
from accounts.views import LoginAndVerifiedRequiredMixin

logger = logging.getLogger(__name__)

class InstitutionVisibilityMixin:
    """Shared visibility rules for institutions."""

    def can_view_institution(self, institution: Institution) -> bool:
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return True
        if institution.approval_status == "approved":
            return True
        return bool(user.is_authenticated and institution.created_by_id == user.id)

    def get_visible_institutions_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Institution.objects.all()
        return Institution.objects.filter(
            Q(approval_status="approved") | Q(created_by=user)
        )

# 

class InstitutionListView(LoginAndVerifiedRequiredMixin, InstitutionVisibilityMixin, ListView):
    """Restricted: Only logged-in and verified users can see the institution list."""
    model = Institution
    template_name = 'institutions/institution_list.html'
    context_object_name = 'institutions'
    paginate_by = 10

    def get_queryset(self):
        queryset = self.get_visible_institutions_queryset()
        
        # Apply filters from form
        form = InstitutionFilterForm(self.request.GET)
        if form.is_valid():
            institution_type = form.cleaned_data.get('institution_type')
            country = form.cleaned_data.get('country')
            specialty = form.cleaned_data.get('specialty')
            search_term = form.cleaned_data.get('search_term')
            sort = form.cleaned_data.get('sort', 'name')
            
            # Also check for 'q' parameter for consistency
            if not search_term:
                search_term = self.request.GET.get('q', '').strip()
            
            if institution_type:
                queryset = queryset.filter(type=institution_type)
            
            if country:
                queryset = queryset.filter(country=country)
            
            if specialty:
                queryset = queryset.filter(specialties=specialty)
            
            if search_term:
                queryset = queryset.filter(
                    Q(name__icontains=search_term) | 
                    Q(name_ar__icontains=search_term) | 
                    Q(name_en__icontains=search_term) | 
                    Q(description__icontains=search_term) |
                    Q(description_ar__icontains=search_term) |
                    Q(description_en__icontains=search_term) |
                    Q(acronym__icontains=search_term) |
                    Q(city__icontains=search_term) |
                    Q(specialties__name_en__icontains=search_term) |
                    Q(specialties__name_ar__icontains=search_term)
                )
            
            # Apply sort
            if sort == 'name_desc':
                queryset = queryset.order_by('-name')
            elif sort == 'newest':
                queryset = queryset.order_by('-created_at')
            elif sort == 'oldest':
                queryset = queryset.order_by('created_at')
            else:  # 'name' or default
                queryset = queryset.order_by('name')
        else:
            queryset = queryset.order_by('name')
        
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = InstitutionFilterForm(self.request.GET)
        context['page'] = 'institutions'
        return context


class InstitutionDetailView(LoginAndVerifiedRequiredMixin, InstitutionVisibilityMixin, DetailView):
    """Restricted: Only logged-in and verified users can see institution details."""
    model = Institution
    template_name = 'institutions/institution_detail.html'
    context_object_name = 'institution'

    def get_object(self, queryset=None):
        institution = cast(Institution, super().get_object(queryset))
        if not self.can_view_institution(institution):
            raise Http404(_("Institution not found."))
        return institution
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page'] = 'institutions'
        return context


class InstitutionCreateView(LoginAndVerifiedRequiredMixin, CreateView):
    """All verified users can suggest institutions; staff-created ones are auto-approved."""
    model = Institution
    form_class = InstitutionForm
    template_name = 'institutions/institution_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['mode'] = 'create'
        return context

    def form_valid(self, form) -> HttpResponse:
        import logging
        logger = logging.getLogger(__name__)
        
        form.instance.created_by = self.request.user
        if self.request.user.is_staff:
            form.instance.approval_status = 'approved'
            logger.info(f"[INSTITUTION_CREATE] Auto-approving institution by staff: {self.request.user.email}")
        else:
            form.instance.approval_status = 'pending'
            logger.info(f"[INSTITUTION_CREATE] Setting institution to pending by user: {self.request.user.email}")
        
        try:
            self.object = form.save()
            logger.info(
                f"[INSTITUTION_CREATE] ✓ Institution created successfully "
                f"(ID: {self.object.id}, Name: {self.object.name}, Status: {self.object.approval_status})"
            )
            
            if self.request.user.is_staff:
                messages.success(self.request, _("Institution created successfully!"))
            else:
                messages.info(
                    self.request,
                    _("Your institution suggestion has been submitted and is pending admin review.")
                )
            return redirect(self.get_success_url())
            
        except Exception as e:
            logger.error(f"[INSTITUTION_CREATE] ✗ Error creating institution: {str(e)}", exc_info=True)
            messages.error(
                self.request,
                _("An error occurred while creating the institution. Please try again.")
            )
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"[INSTITUTION_CREATE] Form validation failed: {form.errors.as_json()}")
        messages.error(self.request, _('Please correct the errors in the form.'))
        return super().form_invalid(form)

    def get_success_url(self):
        if self.request.user.is_staff:
            return str(reverse_lazy('pages:admin_institutions'))
        return str(reverse_lazy('institutions:institution_list'))


class InstitutionUpdateView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, UpdateView):
    """Restricted: Only owner/staff who are verified can update."""
    model = Institution
    form_class = InstitutionForm
    template_name = 'institutions/institution_form.html'
    
    def test_func(self) -> bool:
        institution = self.get_object()
        created_by = getattr(institution, 'created_by', None)
        return (self.request.user == created_by or 
                self.request.user.is_staff)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['mode'] = 'update'
        return context
    
    def form_valid(self, form) -> HttpResponse:
        try:
            institution_form = cast(InstitutionForm, form)
            self.object = institution_form.save()
            
            created_specialties = institution_form.get_created_specialties()
            if created_specialties:
                specialty_names = ', '.join(created_specialties)
                messages.info(
                    self.request, 
                    _("New specialties created : {}").format(specialty_names)
                )
            
            logger.info(f"Institution mise à jour avec succès - ID: {self.object.id}")
            messages.success(self.request, _("The institution has been successfully updated."))
            return redirect(self.get_success_url())
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de l'institution : {str(e)}")
            messages.error(
                self.request, 
                _("Une erreur s'est produite lors de la mise à jour de l'institution : {}").format(str(e))
            )
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        logger.error(f"Formulaire de modification invalide - Erreurs : {form.errors}")
        messages.error(self.request, _("Veuillez corriger les erreurs dans le formulaire."))
        return super().form_invalid(form)
    
    def get_success_url(self):
        return reverse_lazy('institutions:institution_detail', kwargs={'pk': self.object.pk})


class InstitutionDeleteView(LoginAndVerifiedRequiredMixin, UserPassesTestMixin, DeleteView):
    """Restricted: Only owner/staff who are verified can delete."""
    model = Institution
    template_name = 'institutions/institution_confirm_delete.html'
    success_url = reverse_lazy('institutions:institution_list')
    
    def test_func(self) -> bool:
        institution = self.get_object()
        created_by = getattr(institution, 'created_by', None)
        return (self.request.user == created_by or 
                self.request.user.is_staff)

    def _get_blocking_resources(self, institution: Institution):
        """Return theses and memoirs that protect this institution from deletion."""
        blocking_theses = Thesis.objects.filter(institution=institution).select_related("document")
        blocking_memoirs = Memoir.objects.filter(institution=institution).select_related("document")
        return blocking_theses, blocking_memoirs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        institution = self.get_object()
        blocking_theses, blocking_memoirs = self._get_blocking_resources(institution)
        context["blocking_theses"] = blocking_theses
        context["blocking_memoirs"] = blocking_memoirs
        context["has_blocking_resources"] = blocking_theses.exists() or blocking_memoirs.exists()
        context.setdefault("deletion_error", None)
        return context
        
    def delete(self, request, *args, **kwargs):
        institution = self.get_object()
        logger.info(f"Institution Deletion - ID: {institution.pk}")
        try:
            response = super().delete(request, *args, **kwargs)
            messages.success(self.request, _("The institution has been successfully abolished."))
            return response
        except ProtectedError:
            blocking_theses, blocking_memoirs = self._get_blocking_resources(institution)
            error_message = _(
                "This institution cannot be deleted because it is referenced by existing theses or memoirs."
            )
            messages.error(self.request, error_message)
            context = self.get_context_data(
                object=institution,
                deletion_error=error_message,
                blocking_theses=blocking_theses,
                blocking_memoirs=blocking_memoirs,
                has_blocking_resources=True,
            )
            return self.render_to_response(context, status=400)
    
