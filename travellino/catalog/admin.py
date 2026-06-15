from django.contrib import admin
from .models import City, Activity, TransportOption, AccommodationOption


class ActivityInline(admin.TabularInline):
    model = Activity
    extra = 0
    fields = ('title', 'category')
    show_change_link = True


class AccommodationInline(admin.TabularInline):
    model = AccommodationOption
    extra = 0
    fields = ('name', 'rating', 'price_per_night')
    show_change_link = True


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    inlines = (ActivityInline, AccommodationInline)

    list_display = ('city', 'country', 'region', 'budget_level')
    list_filter = ('budget_level', 'country')
    search_fields = ('city', 'country', 'region')


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('title', 'city', 'category')
    list_filter = ('category', 'city')
    search_fields = ('title', 'description')
    autocomplete_fields = ('city',)


@admin.register(TransportOption)
class TransportOptionAdmin(admin.ModelAdmin):
    list_display = ('transport_type', 'carrier_name', 'route_number', 'departure_point', 'arrival_point', 'base_price')
    list_filter = ('transport_type',)
    search_fields = ('carrier_name', 'route_number', 'departure_point', 'arrival_point')


@admin.register(AccommodationOption)
class AccommodationOptionAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'rating', 'price_per_night', 'address')
    list_filter = ('city',)
    search_fields = ('name', 'address')
    autocomplete_fields = ('city',)