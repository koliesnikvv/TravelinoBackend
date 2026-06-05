import uuid

from django.contrib.auth import get_user_model
from django.db import models

from catalog.models import City, Activity, TransportOption, AccommodationOption

User = get_user_model()


class Trip(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name='trips')
    start_date = models.DateField()
    end_date = models.DateField()
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trips')

    def __str__(self):
        return self.title


class TransportBooking(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='transport_bookings')
    departure_point = models.CharField(max_length=200)
    arrival_point = models.CharField(max_length=200)
    departure_datetime = models.DateTimeField()
    arrival_datetime = models.DateTimeField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    passengers_count = models.PositiveIntegerField()
    transport_option = models.ForeignKey(TransportOption, on_delete=models.SET_NULL, null=True, blank=True)
    transport_details_id = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return f"{self.departure_point} -> {self.arrival_point}"


class AccommodationBooking(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='accommodation_bookings')
    accommodation_name = models.CharField(max_length=200)
    check_in_date = models.DateField()
    check_out_date = models.DateField()
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    accommodation_option = models.ForeignKey(AccommodationOption, on_delete=models.SET_NULL, null=True, blank=True)
    accommodation_details_id = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return self.accommodation_name


class TripActivity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='activities')
    activity = models.ForeignKey(Activity, on_delete=models.SET_NULL, null=True, blank=True, related_name='trip_activities')
    activity_details_id = models.CharField(max_length=200, null=True, blank=True)
    scheduled_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        activity_title = self.activity.title if self.activity else "Custom Activity"
        return f"{activity_title} {self.scheduled_date}"


class AccessLevel(models.TextChoices):
    VIEW = 'View', 'View'
    EDIT = 'Edit', 'Edit'


class InviteStatus(models.TextChoices):
    PENDING = 'Pending', 'Pending'
    ACCEPTED = 'Accepted', 'Accepted'


class TripParticipant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='participations')
    invitee_email = models.EmailField()
    access_level = models.CharField(max_length=10, choices=AccessLevel.choices)
    status = models.CharField(max_length=10, choices=InviteStatus.choices, default=InviteStatus.PENDING)

    def __str__(self):
        return f"{self.invitee_email} - {self.trip.title}"