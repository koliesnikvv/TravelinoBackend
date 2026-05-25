import uuid

from django.contrib.postgres.fields import ArrayField
from django.db import models


class BudgetLevel(models.TextChoices):
    BUDGET = 'Budget', 'Budget'
    MID_RANGE = 'Mid-range', 'Mid-range'
    LUXURY = 'Luxury', 'Luxury'


class IdealDuration(models.TextChoices):
    DAY_TRIP = 'Day trip', 'Day trip'
    WEEKEND = 'Weekend', 'Weekend'
    SHORT_TRIP = 'Short trip', 'Short trip'
    ONE_WEEK = 'One week', 'One week'
    LONG_TRIP = 'Long trip', 'Long trip'


class ActivityCategory(models.TextChoices):
    CULTURE = 'Culture', 'Culture'
    ADVENTURE = 'Adventure', 'Adventure'
    NATURE = 'Nature', 'Nature'
    BEACHES = 'Beaches', 'Beaches'
    NIGHTLIFE = 'Nightlife', 'Nightlife'
    CUISINE = 'Cuisine', 'Cuisine'
    WELLNESS = 'Wellness', 'Wellness'
    URBAN = 'Urban', 'Urban'
    SECLUSION = 'Seclusion', 'Seclusion'


class TransportType(models.TextChoices):
    FLIGHT = 'Flight', 'Flight'
    TRAIN = 'Train', 'Train'
    BUS = 'Bus', 'Bus'


class City(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    region = models.CharField(max_length=100)
    short_description = models.TextField()
    ideal_durations = ArrayField(
        base_field=models.CharField(max_length=50, choices=IdealDuration.choices),
        blank=True,
        default=list
    )
    budget_level = models.CharField(max_length=20, choices=BudgetLevel.choices)

    culture = models.IntegerField()
    adventure = models.IntegerField()
    nature = models.IntegerField()
    beaches = models.IntegerField()
    nightlife = models.IntegerField()
    cuisine = models.IntegerField()
    wellness = models.IntegerField()
    urban = models.IntegerField()
    seclusion = models.IntegerField()

    # reserve: for transport and accommodation API integration
    # latitude = models.DecimalField(max_digits=19, decimal_places=16)
    # longitude = models.DecimalField(max_digits=19, decimal_places=16)

    # reserve: for city detail page
    # avg_temp_monthly = models.JSONField()

    def __str__(self):
        return self.city


class Activity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='activities')
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=50, choices=ActivityCategory.choices)

    def __str__(self):
        return self.title


class TransportOption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    departure_point = models.CharField(max_length=200)
    arrival_point = models.CharField(max_length=200)
    transport_type = models.CharField(max_length=20, choices=TransportType.choices)
    carrier_name = models.CharField(max_length=200)
    route_number = models.CharField(max_length=50)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.transport_type} {self.route_number} {self.departure_point} -> {self.arrival_point}"


class AccommodationOption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='accommodations')
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=300)
    rating = models.DecimalField(max_digits=3, decimal_places=1)
    description = models.TextField()
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.name