from django.contrib import admin

from events.models import Event, EventRegistration

class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'event_type', 'start_date', 'end_date', 'is_approved', 'is_upcoming')
    list_filter = ('event_type', 'is_approved', 'start_date', 'domains')
    search_fields = ('title', 'description', 'organizer')
    date_hierarchy = 'start_date'
    actions = ['approve_events']
    
    def approve_events(self, request, queryset):
        queryset.update(is_approved=True)
    approve_events.short_description = "Approve selected events"
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'registration_date')
    list_filter = ('registration_date',)
    search_fields = ('user__username', 'user__email', 'event__title')
    
admin.site.register(Event)
admin.site.register(EventRegistration)
