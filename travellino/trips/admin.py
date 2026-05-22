from django.contrib import admin
from .models import Trip, TransportBooking, AccommodationBooking, TripActivity

admin.site.register(Trip)
admin.site.register(TransportBooking)
admin.site.register(AccommodationBooking)
admin.site.register(TripActivity)