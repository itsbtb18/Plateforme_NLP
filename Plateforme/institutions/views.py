from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.db.models import Q
from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth import get_user_model
from notifications.services import NotificationService
import logging

from .models import Institution
from .forms import InstitutionFilterForm, InstitutionForm

logger = logging.getLogger(__name__)


class InstitutionListView(ListView):
    model = Institution
    template_name = 'institution_list.html'
    context_object_name = 'institutions'
    paginate_by = 9

    def get_queryset(self):
        queryset = Institution.objects.all()
        
        # Apply filters from form
        form = InstitutionFilterForm(self.request.GET)
        if form.is_valid():
            institution_type = form.cleaned_data.get('institution_type')
            country = form.cleaned_data.get('country')
            specialty = form.cleaned_data.get('specialty')
            search_term = form.cleaned_data.get('search_term')
            
            if institution_type:
                queryset = queryset.filter(type=institution_type)
            
            if country:
                queryset = queryset.filter(country=country)
            
            if specialty:
                queryset = queryset.filter(specialties=specialty)
            
            if search_term:
                queryset = queryset.filter(
                    Q(name__icontains=search_term) | 
                    Q(description__icontains=search_term) |
                    Q(acronym__icontains=search_term)
                )
        
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = InstitutionFilterForm(self.request.GET)
        context['page'] = 'institutions'
        return context


class InstitutionDetailView(DetailView):
    model = Institution
    template_name = 'institutions/institution_detail.html'
    context_object_name = 'institution'
    def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context['page'] = 'institutions'  
            return context


class InstitutionCreateView(LoginRequiredMixin, CreateView):
    model = Institution
    form_class = InstitutionForm
    template_name = 'institutions/institution_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['mode'] = 'create'
        return context
    
    def form_valid(self, form):
        try:
            logger.info("Form is valid")
            form.instance.created_by = self.request.user
            
            # Sauvegarder l'institution
            self.object = form.save()

            # Afficher un message pour les spécialités créées
            created_specialties = form.get_created_specialties()
            if created_specialties:
                specialty_names = ', '.join(created_specialties)
                messages.info(
                    self.request, 
                    _("New specialties created : {}").format(specialty_names)
                )

            # Notifications aux modérateurs
           

            
            messages.success(
                self.request, 
                _("The institution has been successfully added .")
            )
            return redirect(self.get_success_url())
            
        except Exception as e:
            logger.error(f"Erreur lors de la création de l'institution : {str(e)}")
            messages.error(
                self.request, 
                _("Une erreur s'est produite lors de la création de l'institution : {}").format(str(e))
            )
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        logger.error(f"Invalid form : {form.errors}")
        messages.error(self.request, _("Please correct any errors in the form."))
        return super().form_invalid(form)
    
    def get_success_url(self):
        return reverse_lazy('institutions:institution_list')

    


class InstitutionUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Institution
    form_class = InstitutionForm
    template_name = 'institutions/institution_form.html'
    
    def test_func(self):
        institution = self.get_object()
        return self.request.user == institution.created_by or self.request.user.is_staff
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['mode'] = 'update'
        return context
    
    def form_valid(self, form):
        try:
            # Sauvegarder l'institution
            self.object = form.save()
            
            # Afficher un message pour les spécialités créées
            created_specialties = form.get_created_specialties()
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

class InstitutionDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Institution
    template_name = 'institutions/institution_confirm_delete.html'
    success_url = reverse_lazy('institutions:institution_list')
    
    def test_func(self):
        institution = self.get_object()
        return self.request.user == institution.created_by or self.request.user.is_staff
        
    def delete(self, request, *args, **kwargs):
        logger.info(f"Institution Deletion - ID: {self.get_object().id}")
        messages.success(self.request, "The institution has been successfully abolished.")
        return super().delete(request, *args, **kwargs)
