from rest_framework import serializers
from .models import City, Activity, TransportOption, AccommodationOption


class CityShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ['id', 'city']


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = [
            'id',
            'city',
            'country',
            'region',
            'short_description',
            'ideal_durations',
            'budget_level',
            'culture',
            'nature',
            'beaches',
            'nightlife',
            'cuisine',
        ]


class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = ['id', 'title', 'description', 'category']


class TransportOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransportOption
        fields = [
            'id',
            'departure_point',
            'arrival_point',
            'transport_type',
            'carrier_name',
            'route_number',
            'base_price',
        ]


class AccommodationOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccommodationOption
        fields = [
            'id',
            'name',
            'address',
            'rating',
            'description',
            'price_per_night',
        ]