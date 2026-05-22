from django.contrib import admin
from .models import City, Activity, TransportOption, AccommodationOption

admin.site.register(City)
admin.site.register(Activity)
admin.site.register(TransportOption)
admin.site.register(AccommodationOption)