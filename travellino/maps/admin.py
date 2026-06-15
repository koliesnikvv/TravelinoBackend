from django.contrib import admin
from .models import VisitedCountry


@admin.register(VisitedCountry)
class VisitedCountryAdmin(admin.ModelAdmin):
    list_display = ('user', 'country_name', 'country_code', 'visited_at')
    list_filter = ('country_name',)
    search_fields = ('user__email', 'country_name', 'country_code')