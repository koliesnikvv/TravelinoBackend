from django.contrib import admin
from .models import Trip, TransportBooking, AccommodationBooking, TripActivity, TripParticipant


class TransportBookingInline(admin.TabularInline):
    model = TransportBooking
    extra = 0
    fields = ('departure_point', 'arrival_point', 'departure_datetime', 'price', 'passengers_count')
    show_change_link = True


class AccommodationBookingInline(admin.TabularInline):
    model = AccommodationBooking
    extra = 0
    fields = ('accommodation_name', 'check_in_date', 'check_out_date', 'total_price')
    show_change_link = True


class TripActivityInline(admin.TabularInline):
    model = TripActivity
    extra = 0
    fields = ('activity', 'activity_name', 'scheduled_date', 'start_time', 'end_time')
    show_change_link = True


class TripParticipantInline(admin.TabularInline):
    model = TripParticipant
    extra = 0
    fields = ('invitee_email', 'user', 'access_level', 'status')


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    inlines = (TripParticipantInline, TransportBookingInline, AccommodationBookingInline, TripActivityInline)

    list_display = ('title', 'owner', 'city', 'start_date', 'end_date')
    list_filter = ('city', 'start_date')
    search_fields = ('title', 'owner__email', 'owner__first_name', 'owner__last_name')
    date_hierarchy = 'start_date'
    autocomplete_fields = ('owner', 'city')


@admin.register(TransportBooking)
class TransportBookingAdmin(admin.ModelAdmin):
    list_display = ('trip', 'departure_point', 'arrival_point', 'departure_datetime', 'price', 'passengers_count')
    list_filter = ('transport_option__transport_type',)
    search_fields = ('departure_point', 'arrival_point', 'trip__title')


@admin.register(AccommodationBooking)
class AccommodationBookingAdmin(admin.ModelAdmin):
    list_display = ('accommodation_name', 'trip', 'check_in_date', 'check_out_date', 'total_price')
    search_fields = ('accommodation_name', 'trip__title')


@admin.register(TripActivity)
class TripActivityAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'trip', 'scheduled_date', 'start_time', 'end_time')
    list_filter = ('scheduled_date',)
    search_fields = ('activity__title', 'activity_name', 'trip__title')


@admin.register(TripParticipant)
class TripParticipantAdmin(admin.ModelAdmin):
    list_display = ('invitee_email', 'trip', 'access_level', 'status')
    list_filter = ('access_level', 'status')
    search_fields = ('invitee_email', 'trip__title')